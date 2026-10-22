"""Information-boundary and numerical tests for the v2 CPU comparators."""

import numpy as np
import pandas as pd
import pytest

from gaplens.core import AnalogBridge
from gaplens.models_v2 import (
    ConditionalTrajectoryPCA, DiverseAnalogBridge, LocalLinearKalman, SeasonalBridge,
)


FACTORIES = (
    lambda: DiverseAnalogBridge(context=3, k=8),
    lambda: ConditionalTrajectoryPCA(context=3, rank=4, ridge=0.01),
    lambda: LocalLinearKalman(context=3, process_ratio=0.1),
    lambda: SeasonalBridge(context=3, period=24),
)


def series(count=600):
    x = np.arange(count)
    return 10 + np.sin(2 * np.pi * x / 24) + 0.2 * np.cos(x / 7)


@pytest.mark.parametrize("factory", FACTORIES)
def test_predictions_ignore_hidden_truth_and_all_nonlocal_query_values(factory):
    reference, query = series(600), series(70)
    reference_times = pd.date_range("2020-01-01", periods=len(reference), freq="h")
    query_times = pd.date_range(reference_times[-1] + pd.Timedelta(hours=1), periods=len(query), freq="h")
    start, end, c = 25, 32, 3
    original_reference, original_query = reference.copy(), query.copy()
    model = factory().fit(reference, reference_times)
    expected = model.predict(query, start, end, query_times)
    altered = np.full(len(query), 9e10)
    altered[start-c:start], altered[end:end+c] = query[start-c:start], query[end:end+c]
    altered[start:end] = np.nan
    actual = model.predict(altered, start, end, query_times)
    np.testing.assert_array_equal(actual.mean, expected.mean)
    np.testing.assert_array_equal(actual.scale, expected.scale)
    assert actual.neighbors == expected.neighbors
    assert np.isfinite(actual.mean).all()
    assert np.isfinite(actual.scale).all() and (actual.scale > 0).all()
    np.testing.assert_array_equal(reference, original_reference)
    np.testing.assert_array_equal(query, original_query)


@pytest.mark.parametrize("factory", FACTORIES)
def test_constant_series_and_missing_context(factory):
    reference, query = np.full(600, 4.5), np.full(50, 4.5)
    times = pd.date_range("2020-01-01", periods=650, freq="h")
    model = factory().fit(reference, times[:600])
    prediction = model.predict(query, 20, 27, times[600:])
    np.testing.assert_allclose(prediction.mean, 4.5, atol=1e-8)
    assert (prediction.scale > 0).all()
    query[19] = np.nan
    with pytest.raises(ValueError, match="context contains missing"):
        model.predict(query, 20, 27, times[600:])


def test_diverse_windows_are_separated_and_short_history_does_not_refill():
    reference = series(50)
    model = DiverseAnalogBridge(context=3, k=40, seasonal_weight=0).fit(reference)
    prediction = model.predict(series(40), 15, 22)
    starts = np.asarray(prediction.neighbors)
    assert 1 <= len(starts) <= len(reference) // 13 < model.k
    assert np.all(np.diff(np.sort(starts)) >= 13)
    assert prediction.distance >= 0
    repeated = model.predict(series(40), 15, 22)
    assert repeated.neighbors == prediction.neighbors


def test_one_neighbor_diverse_matches_literal_v1():
    reference, query = series(500), series(60)
    original = AnalogBridge(context=3, k=1, seasonal_weight=0).fit(reference).predict(query, 20, 27)
    separated = DiverseAnalogBridge(context=3, k=1, seasonal_weight=0).fit(reference).predict(query, 20, 27)
    np.testing.assert_array_equal(original.mean, separated.mean)
    np.testing.assert_array_equal(original.scale, separated.scale)
    assert original.neighbors == separated.neighbors


def test_trajectory_pca_recovers_low_rank_periodic_signal():
    reference = 5 + np.sin(2 * np.pi * np.arange(720) / 24)
    query = 5 + np.sin(2 * np.pi * np.arange(80) / 24)
    model = ConditionalTrajectoryPCA(context=6, rank=2, ridge=1e-8).fit(reference)
    prediction = model.predict(query, 30, 42)
    np.testing.assert_allclose(prediction.mean, query[30:42], atol=1e-6)
    assert len(model._projections) == 1
    model.fit(reference + 7)
    assert model._projections == {}


def test_trajectory_pca_requires_complete_training_windows():
    reference = np.arange(50, dtype=float)
    reference[::4] = np.nan
    model = ConditionalTrajectoryPCA(context=3).fit(reference)
    with pytest.raises(ValueError, match="complete trajectory windows"):
        model.predict(series(50), 15, 22)


def test_kalman_recovers_linear_trend_and_uses_right_context():
    reference, query = np.arange(500, dtype=float), np.arange(70, dtype=float)
    model = LocalLinearKalman(context=6, process_ratio=0.1).fit(reference)
    prediction = model.predict(query, 30, 40)
    np.testing.assert_allclose(prediction.mean, query[30:40], atol=1e-5)
    changed = query.copy()
    changed[40:46] += 10
    revised = model.predict(changed, 30, 40)
    assert revised.mean[-1] > prediction.mean[-1] + 5


def test_seasonal_profile_uses_absolute_phase_and_context_level():
    times = pd.date_range("2020-01-01", periods=560, freq="h")
    reference = np.tile(np.arange(24, dtype=float), 20)
    query = (np.arange(480, 560) % 24).astype(float) + 12.5
    model = SeasonalBridge(context=3, period=24).fit(reference, times[:480])
    prediction = model.predict(query, 10, 17, times[480:])
    np.testing.assert_allclose(prediction.mean, query[10:17], atol=1e-12)
    with pytest.raises(ValueError, match="fitted seasonal grid"):
        model.predict(query, 10, 17, times[480:] + pd.Timedelta(minutes=1))


def test_seasonal_refuses_unobserved_phase_and_missing_timestamps():
    times = pd.date_range("2020-01-01", periods=200, freq="h")
    reference = np.ones(100)
    reference[np.arange(100) % 24 == 10] = np.nan
    model = SeasonalBridge(context=3, period=24).fit(reference, times[:100])
    with pytest.raises(ValueError, match="required seasonal phase"):
        model.predict(np.ones(100), 5, 12, times[100:])
    with pytest.raises(ValueError, match="requires timestamps"):
        SeasonalBridge(context=3).fit(np.ones(100))


@pytest.mark.parametrize("factory", [
    lambda: ConditionalTrajectoryPCA(rank=0),
    lambda: ConditionalTrajectoryPCA(ridge=0),
    lambda: ConditionalTrajectoryPCA(ridge=np.nan),
    lambda: ConditionalTrajectoryPCA(max_candidates=1),
    lambda: LocalLinearKalman(process_ratio=0),
    lambda: LocalLinearKalman(process_ratio=np.inf),
    lambda: SeasonalBridge(period=1),
])
def test_invalid_hyperparameters_fail_before_fit(factory):
    with pytest.raises(ValueError):
        factory()
