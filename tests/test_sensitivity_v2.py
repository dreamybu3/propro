"""Post-result diagnostics preserve the original estimand and show its fragility."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sensitivity_v2", ROOT/"scripts/analyze_v2_sensitivity.py")
sensitivity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sensitivity)


def test_width_outlier_can_reverse_macro_without_changing_majority_of_series():
    pairs = pd.DataFrame({"dataset": ["huge", "ordinary_a", "ordinary_b"], "model": ["v1"]*3,
                          "common_interval_cases": [10]*3,
                          "static_normalized_width": [1000., 1., 1.],
                          "rolling_normalized_width": [10., 1.2, 1.2],
                          "static_gap_coverage": [.9, .8, .9], "rolling_gap_coverage": [.9, .9, .8]})
    effects, rows, loo = sensitivity.width_sensitivity(pairs)
    effect = effects[0]
    assert effect["frozen_macro_normalized_width_ratio"] < .02
    assert effect["median_series_width_ratio"] == pytest.approx(1.2)
    assert effect["series_wider"] == 2 and effect["series_narrower"] == 1
    assert effect["series_coverage_closer"] == effect["series_coverage_farther"] == 1
    without_huge = loo.set_index("omitted_dataset").loc["huge"]
    assert without_huge.normalized_width_ratio == pytest.approx(1.2)
    assert not without_huge.width_within_frozen_10_percent_effect_bound
    assert len(rows) == len(pairs)


def test_source_extremes_use_exact_fit_and_initial_calibration_boundaries(tmp_path):
    path = tmp_path/"data.csv"
    pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=8),
                  "value": [1., 2., 3., 4., 1000., None, 1e9, 1e9]}).to_csv(path, index=False)
    plan = {"datasets": {"example": {"path": "data.csv", "fit_end": 4,
             "initial_calibration_end": 6, "normalization_scale": 2., "sha256": sensitivity.sha256(path)}}}
    row = sensitivity.source_extremes(plan, root=tmp_path).iloc[0]
    assert row.fit_max == 4.
    assert row.initial_calibration_max == 1000.
    assert row.initial_calibration_missing_rows == 1
    assert row.initial_calibration_maximum_source_index == 4
    assert row.calibration_max_fit_max_ratio == 250.
