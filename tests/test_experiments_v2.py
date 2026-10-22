"""Check information boundaries and refusal accounting, not just formulas."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_experiments_v2", ROOT/"scripts/run_experiments_v2.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def inputs(tmp_path):
    values = np.arange(1200, dtype=float)/500 + np.sin(np.arange(1200)/11)
    frame = pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=len(values), freq="h", tz="UTC"),
                          "value": values})
    path = tmp_path/"synthetic.csv"
    frame.to_csv(path, index=False)
    entry = {"id": "synthetic", "processed_path": str(path), "processed_sha256": runner.sha256(path),
             "source_group": "synthetic", "system_group": "synthetic", "frequency_seconds": 3600}
    config = json.loads((ROOT/"configs/benchmark_v2.json").read_text())
    config.update(seeds=[17], seasonal_periods={"synthetic": 24})
    return config, [entry], {"synthetic": frame}


def test_all_unobserved_query_values_are_inaccessible():
    values = np.arange(80, dtype=float)
    query = runner.local_query(values, 30, 37, 3, 20, 60, hidden=[28, 34, 50])
    assert np.flatnonzero(np.isfinite(query)).tolist() == [27, 29, 37, 38, 39]
    modified = values.copy()
    modified[np.isnan(query)] = -999999
    np.testing.assert_array_equal(query, runner.local_query(modified, 30, 37, 3, 20, 60,
                                                           hidden=[28, 34, 50]))


def test_plan_removes_earlier_outages_from_rolling_calibration(inputs):
    config, entries, frames = inputs
    plan = runner.build_plan(config, entries, frames)
    repeated = runner.build_plan(config, entries, frames)
    assert plan == repeated
    prior = set()
    for oi in range(3):
        calibration = [c for c in plan["calibration"] if c["origin_index"] == oi]
        if oi == 0:
            for length in plan["datasets"]["synthetic"]["all_lengths"]:
                a, b = [c for c in calibration if c["length"] == length]
                assert a["windows"] == b["windows"]
        for cal in calibration:
            expected = sorted(i for i in prior if cal["begin"] <= i < cal["end"])
            assert cal["unavailable_history_indices"] == expected
            for a, b in cal["windows"]:
                assert not set(range(a-3, b+3)) & prior
        for case in plan["cases"]:
            if case["origin_index"] == oi and case["regime"] == "simultaneous":
                prior.update(case["hidden_indices"])
    assert prior
    assert any(c["unavailable_history_indices"] for c in plan["calibration"])


def test_simultaneous_context_is_masked_before_any_prediction(inputs):
    config, entries, frames = inputs
    plan = runner.build_plan(config, entries, frames)
    batch = [c for c in plan["cases"] if c["origin_index"] == 0 and c["regime"] == "simultaneous"]
    assert len(batch) == 3
    assert batch[0]["hidden_indices"] == batch[1]["hidden_indices"] == batch[2]["hidden_indices"]
    values = frames["synthetic"].value.to_numpy()
    for case in batch[:2]:
        query = runner.local_query(values, case["start"], case["end"], 3,
                                   case["query_begin"], case["query_end"], case["hidden_indices"])
        contexts = np.r_[query[case["start"]-3:case["start"]], query[case["end"]:case["end"]+3]]
        assert np.isnan(contexts).any()


def test_overlapping_or_hidden_calibration_truth_fails_validation(inputs):
    config, entries, frames = inputs
    plan = runner.build_plan(config, entries, frames)
    bad = copy.deepcopy(plan)
    window = bad["calibration"][0]["windows"][0]
    bad["calibration"][0]["unavailable_history_indices"] = [window[0]]
    with pytest.raises(ValueError, match="hidden history"):
        runner.validate_plan(bad)


def test_mcar_selection_does_not_depend_on_value_magnitude():
    a = np.arange(500, dtype=float)
    b = -a * 1e9
    assert runner.weighted_starts(a, 0, 500, 7, 3, 8, 29) == runner.weighted_starts(b, 0, 500, 7, 3, 8, 29)
    candidates = runner.weighted_starts(a, 0, 500, 7, 3, 8, 29, "mnar", 0, 10)
    assert candidates != runner.weighted_starts(a, 0, 500, 7, 3, 8, 29)


def test_point_metrics_survive_insufficient_interval_calibration():
    point = runner.prediction_metrics(np.array([2., 5.]), np.array([1., 4.]), np.ones(2), None, 2., .1)
    assert point["mae"] == 1.
    assert "gap_coverage" not in point
    band = runner.prediction_metrics(np.array([2., 5.]), np.array([1., 4.]), np.ones(2), 1., 2., .1)
    assert band["gap_coverage"] == 1.


def test_run_keeps_refusals_and_curve_denominators(inputs, tmp_path, monkeypatch):
    """A synthetic actual run checks that failed context is never dropped."""
    config, entries, frames = inputs
    selection = tmp_path/"selection.json"
    runner.write_json(selection, {"parameters": {}})
    config["selection"] = str(selection)
    plan = runner.build_plan(config, entries, frames)
    config_path, plan_path = tmp_path/"config.json", tmp_path/"plan.json"
    runner.write_json(config_path, config)
    runner.write_json(plan_path, plan)
    monkeypatch.setattr(runner, "load_inputs", lambda _: (entries, frames))

    class StrictLinear(runner.LinearBridge):
        def predict(self, values, start, end, timestamps=None):
            allowed = np.zeros(len(values), dtype=bool)
            allowed[start-self.context:start] = True
            allowed[end:end+self.context] = True
            assert not np.isfinite(values[~allowed]).any()
            return super().predict(values, start, end, timestamps)

    monkeypatch.setattr(runner, "make_model", lambda name, context, *args, **kwargs: StrictLinear(context))
    output = tmp_path/"output"
    meta = runner.run(config_path, plan_path, output, smoke=True)
    cases = pd.read_csv(output/"case_metrics.csv")
    curves = pd.read_csv(output/"coverage_width.csv")
    origin0 = [c for c in plan["cases"] if c["origin_index"] == 0]
    assert meta["case_method_rows"] == len(origin0)*len(runner.METHODS)
    assert len(curves) == len(cases)*3
    assert (cases[cases.regime.isin(["boundary", "damaged_context"])].status == "refused").all()
    assert (cases.groupby("case_id").size() == len(runner.METHODS)).all()
    q = cases[cases.regime == "mcar_short"].pivot(index="case_id", columns="method", values="calibration_quantile")
    np.testing.assert_array_equal(q.v1_static, q.v1_rolling)
    score_rows = pd.read_csv(output/"calibration_scores.csv")
    for cid, subset in cases[cases.serviced].groupby("calibration_id"):
        scores = score_rows[score_rows.calibration_id == cid].score.dropna()
        np.testing.assert_allclose(subset.calibration_quantile, runner.conformal_quantile(scores, .1))


def test_final_scoring_cannot_run_before_committed_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="requires"):
        runner._guard_final_run({}, tmp_path/"masks.json")
