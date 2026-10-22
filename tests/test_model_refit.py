"""Failed refits are transactional; timestamp units do not change time meaning."""

import numpy as np
import pandas as pd
import pytest

from gaplens.core import AnalogBridge, ExtraTreesBridge, LinearBridge
from gaplens.models_v2 import (
    ConditionalTrajectoryPCA, DiverseAnalogBridge, LocalLinearKalman, SeasonalBridge,
)


FACTORIES = (
    lambda: AnalogBridge(context=3),
    lambda: LinearBridge(context=3),
    lambda: ExtraTreesBridge(context=3, n_estimators=4, training_gaps=12, lengths=(7,)),
    lambda: DiverseAnalogBridge(context=3),
    lambda: ConditionalTrajectoryPCA(context=3),
    lambda: LocalLinearKalman(context=3),
    lambda: SeasonalBridge(context=3, period=24),
)


@pytest.mark.parametrize("factory", FACTORIES)
def test_failed_timestamp_refit_preserves_reference_and_predictions(factory):
    reference = 5 + np.sin(np.arange(200) / 5)
    query = 7 + np.sin(np.arange(50) / 5)
    times = pd.date_range("2020-01-01", periods=250, freq="h")
    model = factory().fit(reference, times[:200])
    before = model.predict(query, 20, 27, times[200:])
    scales = (model.global_scale_, model.noise_floor_)
    with pytest.raises(ValueError, match="Timestamps must match"):
        model.fit(reference * 7 + 100, times[:199])
    np.testing.assert_array_equal(model.reference_, reference)
    assert model.timestamps_.equals(times[:200])
    assert (model.global_scale_, model.noise_floor_) == scales
    after = model.predict(query, 20, 27, times[200:])
    np.testing.assert_array_equal(after.mean, before.mean)
    np.testing.assert_array_equal(after.scale, before.scale)
    assert after.neighbors == before.neighbors


@pytest.mark.parametrize("factory", FACTORIES)
def test_failed_initial_fit_does_not_enable_prediction(factory):
    model = factory()
    with pytest.raises(ValueError):
        model.fit(np.arange(100, dtype=float), pd.date_range("2020-01-01", periods=99))
    with pytest.raises(ValueError, match="Call fit before predict"):
        model.predict(np.ones(30), 10, 17)


def _reject_tree_fit(model, reference, times, failure, monkeypatch):
    from sklearn.ensemble import ExtraTreesRegressor

    with monkeypatch.context() as patch:
        if failure == "no_windows":
            reference = reference.copy()
            reference[::6] = np.nan
            # Enough finite observations for fit validation, but no contiguous
            # context + target + context window of width 3 + 7 + 3.
            error, message = ValueError, "no complete training windows"
        else:
            def fail_after_mutating_estimator(estimator, x, y):
                estimator.estimators_ = []
                raise RuntimeError("Tree training failed")

            patch.setattr(ExtraTreesRegressor, "fit", fail_after_mutating_estimator)
            error, message = RuntimeError, "Tree training failed"
        with pytest.raises(error, match=message):
            model.fit(reference, times)


@pytest.mark.parametrize("failure", ["no_windows", "estimator_failure"])
def test_extra_trees_failed_refit_preserves_complete_model(failure, monkeypatch):
    reference = 5 + np.sin(np.arange(200) / 5)
    times = pd.date_range("2020-01-01", periods=250, freq="h")
    query = 7 + np.sin(np.arange(50) / 5)
    query[20:27] = np.nan
    options = dict(context=3, seed=17, n_estimators=4, training_gaps=12, lengths=(7,))
    model = ExtraTreesBridge(**options).fit(reference, times[:200])
    before = model.predict(query, 20, 27, times[200:])
    scales = (model.global_scale_, model.noise_floor_)
    forest, training_examples = model.model_, model.training_examples_
    replacement = 1000 + 50 * np.arange(200, dtype=float)
    replacement_times = times[:200] + pd.Timedelta(days=365)

    _reject_tree_fit(model, replacement, replacement_times, failure, monkeypatch)

    after = model.predict(query, 20, 27, times[200:])
    np.testing.assert_array_equal(after.mean, before.mean)
    np.testing.assert_array_equal(after.scale, before.scale)
    np.testing.assert_array_equal(model.reference_, reference)
    pd.testing.assert_index_equal(model.timestamps_, times[:200])
    assert (model.global_scale_, model.noise_floor_) == scales
    assert model.model_ is forest
    assert model.training_examples_ == training_examples

    # A failed attempt must not prevent a later successful replacement.
    assert model.fit(replacement, replacement_times) is model
    expected = ExtraTreesBridge(**options).fit(replacement, replacement_times)
    np.testing.assert_array_equal(model.reference_, replacement)
    pd.testing.assert_index_equal(model.timestamps_, replacement_times)
    assert model.model_ is not forest
    assert (model.global_scale_, model.noise_floor_) == (
        expected.global_scale_, expected.noise_floor_)
    actual_prediction = model.predict(query, 20, 27, times[200:])
    expected_prediction = expected.predict(query, 20, 27, times[200:])
    np.testing.assert_array_equal(actual_prediction.mean, expected_prediction.mean)
    np.testing.assert_array_equal(actual_prediction.scale, expected_prediction.scale)


@pytest.mark.parametrize("failure", ["no_windows", "estimator_failure"])
def test_extra_trees_failed_initial_training_leaves_model_unfitted(failure, monkeypatch):
    model = ExtraTreesBridge(context=3, n_estimators=4, training_gaps=12, lengths=(7,))
    reference = 1000 + 50 * np.arange(200, dtype=float)
    times = pd.date_range("2021-01-01", periods=200, freq="h")
    _reject_tree_fit(model, reference, times, failure, monkeypatch)
    for attribute in ("reference_", "timestamps_", "global_scale_", "noise_floor_",
                      "training_examples_", "model_"):
        assert not hasattr(model, attribute)
    with pytest.raises(ValueError, match="Call fit before predict"):
        model.predict(np.ones(50), 20, 27)


def test_nonfinite_reference_statistics_refuse_without_overwriting_fitted_state():
    model = AnalogBridge(context=3).fit(np.arange(100, dtype=float))
    before = model.predict(np.arange(30, dtype=float), 10, 17)
    with np.errstate(over="ignore", invalid="ignore"):
        with pytest.raises(ValueError, match="Nonfinite reference scale"):
            model.fit(np.tile([-1e308, 1e308], 50))
    after = model.predict(np.arange(30, dtype=float), 10, 17)
    np.testing.assert_array_equal(model.reference_, np.arange(100, dtype=float))
    np.testing.assert_array_equal(after.mean, before.mean)
    np.testing.assert_array_equal(after.scale, before.scale)


def test_seasonal_irregular_refit_preserves_fitted_profile():
    times = pd.date_range("2020-01-01", periods=250, freq="h")
    reference = np.arange(200, dtype=float) % 24
    query = np.arange(200, 250, dtype=float) % 24
    model = SeasonalBridge(context=3, period=24).fit(reference, times[:200])
    before = model.predict(query, 20, 27, times[200:])
    invalid = times[:200].to_numpy().copy()
    invalid[50] = invalid[49]
    with pytest.raises(ValueError, match="regular increasing"):
        model.fit(reference + 100, invalid)
    np.testing.assert_array_equal(model.reference_, reference)
    after = model.predict(query, 20, 27, times[200:])
    np.testing.assert_array_equal(after.mean, before.mean)
    np.testing.assert_array_equal(after.scale, before.scale)


@pytest.mark.parametrize("fit_unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("query_unit", ["s", "ms", "us", "ns"])
def test_seasonal_alignment_is_invariant_to_datetime_storage_units(fit_unit, query_unit):
    times = pd.date_range("2020-01-01", periods=560, freq="h")
    reference = np.tile(np.arange(24, dtype=float), 20)
    query = (np.arange(480, 560) % 24).astype(float) + 12.5
    model = SeasonalBridge(context=3, period=24).fit(reference, times[:480].as_unit(fit_unit))
    result = model.predict(query, 10, 17, times[480:].as_unit(query_unit))
    np.testing.assert_allclose(result.mean, query[10:17], atol=1e-12)
    assert np.isfinite(result.scale).all() and (result.scale > 0).all()
