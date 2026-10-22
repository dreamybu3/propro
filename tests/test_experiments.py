"""Meaningful checks on evaluation accounting, chronology and uncertainty metrics."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_experiments", ROOT / "scripts/run_experiments.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_chronological_splits_are_disjoint_and_cover_rows():
    frame = pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=31, freq="h"), "value": np.arange(31)})
    splits = runner.split_series(frame, [.6, .2, .2])
    assert [(part["start"], part["end"]) for part in splits.values()] == [(0, 18), (18, 24), (24, 31)]
    restored = np.concatenate([part["frame"].value.to_numpy() for part in splits.values()])
    np.testing.assert_array_equal(restored, np.arange(31))
    assert splits["train"]["frame"].timestamp.max() < splits["calibration"]["frame"].timestamp.min()


def test_gap_coverage_differs_from_point_coverage():
    metrics = runner.case_metrics([0, 4], [1, 1], [0, 0], [2, 2], 2, .1)
    assert metrics["mae"] == 2
    assert metrics["mse"] == 5
    assert metrics["normalized_mae"] == 1
    assert metrics["point_coverage"] == .5
    assert metrics["gap_coverage"] == 0
    assert metrics["point_interval_score"] == 22
    assert metrics["normalized_width"] == 1


@pytest.mark.parametrize("lower,upper", [([2, 2], [1, 1]), ([np.nan, 0], [2, 2])])
def test_invalid_bands_fail_instead_of_creating_metrics(lower, upper):
    with pytest.raises(ValueError):
        runner.case_metrics([0, 4], [1, 1], lower, upper, 2, .1)


def test_summary_uses_equal_dataset_weight_not_observation_count(tmp_path):
    rows = []
    for dataset, count, normalized in [("a", 12, 1.), ("b", 2, 9.)]:
        for method in runner.METHODS:
            for index in range(count):
                rows.append({"dataset": dataset, "seed": 17, "method": method, "gap_length": 6,
                             "case_id": f"{dataset}{index}",
                             **{metric: normalized for metric in runner.METRICS}})
    config = json.loads((ROOT / "configs/benchmark.json").read_text())
    runner.summarize(pd.DataFrame(rows), tmp_path, config, False)
    aggregate = pd.read_csv(tmp_path / "aggregate_summary.csv")
    np.testing.assert_allclose(aggregate.normalized_mae, 5.)
    assert "mae" not in aggregate.columns  # Mixed physical units must not be averaged.
    assert len(pd.read_csv(tmp_path / "summary.csv")) == 12


def test_fixed_protocol_cannot_silently_drop_failed_methods():
    config = json.loads((ROOT / "configs/benchmark.json").read_text())
    config["methods"].remove("extra_trees")
    with pytest.raises(ValueError, match="all six"):
        runner.validate_config(config)


def test_saved_benchmark_metrics_recompute_from_individual_predictions():
    """Audit real artifacts independently of the runner's case_metrics helper."""
    folder = ROOT / "results/benchmark"
    if not (folder / "run.json").exists():
        pytest.skip("Main benchmark artifacts have not been generated")
    metadata = json.loads((folder / "run.json").read_text())
    assert metadata["status"] == "complete"
    points = pd.read_csv(folder / "predictions.csv")
    cases = pd.read_csv(folder / "case_metrics.csv").set_index(["case_id", "method"]).sort_index()
    assert set(points.run_id) == {metadata["run_id"]}
    assert len(cases) == metadata["case_method_rows"]
    assert len(points) == metadata["prediction_rows"]
    measured = points.assign(
        absolute_error=(points.truth - points.prediction).abs(),
        covered=(points.truth >= points.lower) & (points.truth <= points.upper),
        width=points.upper - points.lower,
    ).groupby(["case_id", "method"], sort=True).agg(
        mae=("absolute_error", "mean"), point_coverage=("covered", "mean"),
        gap_coverage=("covered", "all"), mean_width=("width", "mean"),
    )
    assert measured.index.equals(cases.index)
    for name in ["mae", "point_coverage", "gap_coverage", "mean_width"]:
        np.testing.assert_allclose(measured[name].astype(float), cases[name], rtol=1e-10, atol=1e-10)
    predictions = points.pivot(index=["case_id", "source_index"], columns="method", values="prediction")
    for method in ["analog_constant_scale", "analog_pooled_calibration"]:
        np.testing.assert_array_equal(predictions.analog_bridge, predictions[method])
