"""Synthetic accounting tests; these fixtures are not empirical evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("summary_v2", ROOT/"scripts/summarize_v2.py")
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)


def row(dataset, case_id, method, mae, *, available=True, serviced=True, length=2, **changes):
    result = {"dataset": dataset, "case_id": case_id, "source_group": dataset,
              "method": method, "regime": "mcar_short", "gap_length": length,
              "point_available": available, "serviced": serviced and available,
              "mae": mae if available else np.nan, "mse": mae**2 if available else np.nan,
              "normalized_mae": mae if available else np.nan, "normalization_scale": 1.,
              "gap_coverage": float(mae <= 2) if serviced and available else np.nan,
              "point_coverage": float(mae <= 2) if serviced and available else np.nan,
              "mean_width": 4. if serviced and available else np.nan,
              "normalized_width": 4. if serviced and available else np.nan,
              "point_interval_score": 4., "normalized_point_interval_score": 4.,
              "origin_index": 0, "history": "full", "prediction_seconds": .001,
              "reason": None if serviced and available else "unsupported"}
    result.update(changes)
    return result


def test_paired_ratios_use_common_cases_and_equal_series_weight():
    rows = []
    for i in range(30):
        rows += [row("a", f"a{i}", "candidate", 1.), row("a", f"a{i}", "reference", 2.)]
    rows += [row("a", "a_refused", "candidate", 0., available=False),
             row("a", "a_refused", "reference", 10000.),
             row("b", "b0", "candidate", 4.), row("b", "b0", "reference", 2.)]
    effect, series, loo = summary.paired_effect(pd.DataFrame(rows), "candidate", "reference", draws=100)
    assert effect["geometric_mean_mae_ratio"] == pytest.approx(1.)
    assert effect["arithmetic_mean_mae_ratio"] == pytest.approx(1.25)
    assert effect["common_cases"] == 31
    assert series.set_index("dataset").loc["a", "mae_ratio"] == .5
    assert series.set_index("dataset").loc["a", "candidate_point_cases"] == 30
    assert effect["series_won"] == effect["series_lost"] == 1
    assert sorted(loo.geometric_mean_mae_ratio) == [.5, 2.]


def test_cluster_bootstrap_keeps_whole_dependent_group_together():
    series = pd.DataFrame({"dataset": ["a", "b", "c"], "source_group": ["one"]*3,
                           "mae_ratio": [.25, 1., 4.]})
    result = summary.cluster_bootstrap(series, draws=100)
    assert result["groups"] == 1
    assert result["lower"] == result["upper"] == pytest.approx(1.)
    assert summary.cluster_bootstrap(series, draws=100) == result


def test_service_and_point_coverage_do_not_drop_refusals_or_weight_gaps_as_points():
    frame = pd.DataFrame([
        row("a", "a0", "m", 1., length=2, point_coverage=1., gap_coverage=1., mean_width=10.),
        row("a", "a1", "m", 3., length=6, point_coverage=0., gap_coverage=0., mean_width=14.),
        row("a", "a2", "m", 0., length=10, available=False),
    ])
    measured = summary.aggregate(frame, ["dataset", "method"]).iloc[0]
    assert measured.mae == 2.
    assert measured.point_mae == 2.5
    assert measured.point_coverage == .25
    assert measured.gap_coverage == .5
    assert measured.mean_width == 12.
    assert measured.interval_service_fraction == pytest.approx(2/3)
    assert measured.predicted_sample_fraction == pytest.approx(8/18)
    assert measured.point_refusals == 1
    assert measured.accepted_and_covered_fraction == pytest.approx(1/3)
    assert measured.accepted_and_covered_sample_fraction == pytest.approx(2/18)


def test_context_proxy_thresholds_keep_unknowns_and_synthetic_labels_explicit():
    cases = pd.DataFrame([
        row("a", "a0", "m", 1., context_shift=2., context_spread_ratio=3., context_endpoint_change=-1.1),
        row("a", "a1", "m", 1., context_shift=-3., context_spread_ratio=1., context_endpoint_change=0., regime="level_shift"),
        row("a", "a2", "m", 0., available=False),
    ])
    diagnostic = summary.context_diagnostics(cases)
    selected = diagnostic[diagnostic.diagnostic == "context_shift"]
    assert set(selected.context_bin) == {"above_threshold", "within_threshold", "unavailable"}
    assert selected[selected.context_bin == "above_threshold"].regime.tolist() == ["level_shift"]
    assert selected.planned_cases.sum() == 3


def test_undefined_zero_reference_error_is_not_silently_reported_as_support():
    rows = [row("a", "a0", "c", 1.), row("a", "a0", "r", 0.),
            row("b", "b0", "c", 0.), row("b", "b0", "r", 0.)]
    effect, series, _ = summary.paired_effect(pd.DataFrame(rows), "c", "r", draws=10)
    assert effect["supported_series"] == 1
    assert not effect["all_series_supported"]
    assert series.set_index("dataset").loc["b", "mae_ratio"] == 1.
    assert series.set_index("dataset").loc["a", "reason"] == "positive_error_against_zero_reference_error"


def test_h2_uses_common_interval_cases_and_records_unsupported_counts():
    rows = []
    for case_id, static_cover, recent_cover in [("a0", 1., 1.), ("a1", 0., 1.)]:
        rows += [row("a", case_id, "v1_static", 1., gap_coverage=static_cover, normalized_width=2.),
                 row("a", case_id, "v1_rolling", 1., gap_coverage=recent_cover, normalized_width=2.1)]
    rows += [row("a", "a2", "v1_static", 1., normalized_width=1000.),
             row("a", "a2", "v1_rolling", 1., serviced=False)]
    result, per_series = summary.uncertainty_comparison(pd.DataFrame(rows), "v1")
    assert result["common_interval_cases"] == 2
    assert result["static_interval_cases"] == 3
    assert result["rolling_interval_cases"] == 2
    assert result["normalized_width_ratio"] == pytest.approx(1.05)
    assert result["h2_met_on_common_cases"]
    assert per_series.iloc[0].static_normalized_width == 2.


def test_curve_denominators_include_missing_prediction_rows():
    cases = pd.DataFrame([row("a", "a0", "x", 1.), row("a", "a0", "y", 1., available=False)])
    curves = pd.DataFrame([{"case_id": "a0", "method": "x", "alpha": .1, "serviced": True,
                            "mae": 1., "mse": 1., "normalized_mae": 1., "gap_coverage": 1.,
                            "point_coverage": 1., "mean_width": 2., "normalized_width": 2.}])
    own, common, support = summary.curve_tables(cases, curves, [.1])
    assert len(own) == 2
    assert own.set_index("method").loc["y", "interval_service_fraction"] == 0
    assert common.empty and "method" in common.columns
    assert support["common_cases_across_all_methods_and_alphas"] == 0


def test_ablation_rejects_changed_point_prediction_under_new_calibration():
    cases = pd.DataFrame([row("a", "a0", method, 1.) for method in ["v1_static", "v1_rolling"]])
    predictions = pd.DataFrame([
        {"case_id": "a0", "method": method, "offset": offset, "truth": 0., "prediction": 1., "relative_scale": 2.}
        for method in ["v1_static", "v1_rolling"] for offset in [0, 1]])
    result = summary.check_calibration_ablation(cases, predictions)
    assert result["v1"]["identical_point_predictions_and_scales"]
    predictions.loc[3, "prediction"] += .1
    with pytest.raises(ValueError, match="calibration changed point"):
        summary.check_calibration_ablation(cases, predictions)


def test_validation_rejects_dropped_methods_duplicate_cases_and_bad_service():
    frame = pd.DataFrame([row("a", "a0", "x", 1.), row("a", "a0", "y", 1.),
                          row("a", "a1", "x", 1.)])
    with pytest.raises(ValueError, match="retain every method"):
        summary.validate_cases(frame)
    with pytest.raises(ValueError, match="Duplicate"):
        summary.validate_cases(pd.concat([frame.iloc[:2], frame.iloc[:1]]))
    frame = frame.iloc[:2].copy()
    frame.loc[0, "point_available"] = False
    with pytest.raises(ValueError, match="without a point"):
        summary.validate_cases(frame)


def create_saved_fixture(tmp_path):
    folder = tmp_path/"measurements"
    folder.mkdir()
    methods = [*summary.STATIC_METHODS, "v1_rolling", "diverse_rolling"]
    errors = {"linear": 2., "extra_trees": .7, "raw_knn": 1.5, "seasonal": 1.2,
              "kalman": 1.1, "pca": 1.3, "v1": 1., "diverse": .9, "diverse_k12": .95}
    cases, points, curves, perf, cal = [], [], [], [], []
    for dataset in ["synthetic_a", "synthetic_b"]:
        for index in range(2):
            case_id = f"{dataset}{index}"
            for method in methods:
                error = errors[method.rsplit("_", 1)[0]]
                cases.append(row(dataset, case_id, method, error))
                for offset in [0, 1]:
                    points.append({"dataset": dataset, "case_id": case_id, "method": method, "offset": offset,
                                   "truth": 0., "prediction": error, "relative_scale": 1., "lower": error-2, "upper": error+2})
                for alpha in [.2, .1, .05]:
                    curves.append({**cases[-1], "alpha": alpha})
        for name in errors:
            perf.append({"dataset": dataset, "model": name, "stage": "fit", "history": "full", "seconds": .01})
            cal.append({"dataset": dataset, "model": name, "mode": "static", "history": "full", "length": 2, "score": 1.})
    pd.DataFrame(cases).to_csv(folder/"case_metrics.csv", index=False)
    pd.DataFrame(points).to_csv(folder/"predictions.csv.gz", index=False, compression="gzip")
    pd.DataFrame(curves).to_csv(folder/"coverage_width.csv", index=False)
    pd.DataFrame(perf).to_csv(folder/"performance.csv", index=False)
    pd.DataFrame(cal).to_csv(folder/"calibration_scores.csv", index=False)
    selection = tmp_path/"selection.json"
    summary.write_json(selection, {"product_model": "v1", "product_calibration": "static",
                                   "best_non_retrieval_competitor": "extra_trees"})
    summary.write_json(folder/"run.json", {"status": "complete", "is_smoke_run": False,
        "selection_sha256": summary.sha256(selection), "elapsed_seconds": 3., "process_peak_rss_mb": 20.,
        "artifact_sha256": {path.name: summary.sha256(path) for path in folder.iterdir()},
        "config": {"selection": str(selection), "manifest": str(tmp_path/"no_manifest.json"),
                   "curve_alphas": [.2, .1, .05], "hypothesis": {"primary_regimes": list(summary.PRIMARY_REGIMES)}}})
    return folder, selection


def test_complete_saved_fixture_generates_tables_figures_and_consistent_hypothesis(tmp_path):
    folder, selection = create_saved_fixture(tmp_path)
    output = tmp_path/"summary"
    result = summary.generate(folder, output, selection_path=selection, draws=20)
    assert result["series"] == 2 and result["source_groups"] == 2
    assert result["h1"]["at_least_5_percent_better_than_v1"]
    assert not result["h1"]["better_than_development_selected_competitor"]
    assert not result["h1"]["met"]
    assert result["curve_support"]["common_cases_across_all_methods_and_alphas"] == 4
    assert (output/"figures/failure_example.png").stat().st_size > 1000
    assert len(pd.read_csv(output/"series_primary.csv")) == 22
    assert "NaN" not in (output/"summary.json").read_text()
    assert json.loads((output/"summary_provenance.json").read_text())["bootstrap_draws"] == 20


def test_changed_artifact_or_smoke_run_cannot_be_summarized_as_final(tmp_path):
    folder, selection = create_saved_fixture(tmp_path)
    with (folder/"case_metrics.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        summary.generate(folder, tmp_path/"bad", selection_path=selection)
    metadata = json.loads((folder/"run.json").read_text())
    metadata["is_smoke_run"] = True
    summary.write_json(folder/"run.json", metadata)
    with pytest.raises(ValueError, match="smoke/partial"):
        summary.generate(folder, tmp_path/"bad", selection_path=selection)
