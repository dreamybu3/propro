#!/usr/bin/env python3
"""Independently reconcile saved v2 predictions; optionally compare a rerun."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, label):
    if not np.allclose(actual, expected, rtol=1e-10, atol=1e-9, equal_nan=True):
        raise ValueError(f"Numerical reconciliation failed: {label}")


def verify(directory, comparison=None):
    directory = Path(directory)
    run = json.loads((directory / "run.json").read_text())
    check(run["status"] == "complete" and not run["is_smoke_run"], "Need a completed full run")
    for name, expected in run["artifact_sha256"].items():
        check(digest(directory / name) == expected, f"Run artifact hash differs: {name}")
    for name, expected in run["code_sha256"].items():
        check(digest(ROOT / name) == expected, f"Numerical source differs: {name}")
    baseline = json.loads((ROOT / "docs/v2/baseline_hashes.json").read_text())
    for name, expected in baseline["sha256"].items():
        check(digest(ROOT / name) == expected, f"Preserved v1 artifact differs: {name}")
    plan = json.loads((ROOT / "results/v2/masks.json").read_text())
    check(digest(ROOT / "results/v2/masks.json") == run["plan_file_sha256"], "Mask file differs")
    planned = {c["case_id"]: c for c in plan["cases"]}
    cases = pd.read_csv(directory / "case_metrics.csv", float_precision="round_trip")
    points = pd.read_csv(directory / "predictions.csv.gz", float_precision="round_trip")
    scores = pd.read_csv(directory / "calibration_scores.csv", float_precision="round_trip")
    check(len(cases) == run["case_method_rows"], "Case count differs")
    check(len(points) == run["prediction_rows"], "Prediction count differs")
    check(set(cases.case_id) == set(planned), "Planned/refused case denominator changed")
    check(not cases.duplicated(["case_id", "method"]).any(), "Duplicate case-method rows")
    check((cases.groupby("case_id").method.nunique() == len(run["config"]["methods"])).all(),
          "Not every case has every method, including refusals")
    sources = {name: pd.read_csv(ROOT / info["path"], float_precision="round_trip").value.to_numpy()
               for name, info in plan["datasets"].items()}
    case_lookup = cases.set_index(["case_id", "method"])
    alpha = run["config"]["alpha"]
    scored = 0
    for (case_id, method), group in points.groupby(["case_id", "method"], sort=False):
        row = case_lookup.loc[(case_id, method)]
        mask = planned[case_id]
        check(bool(row.point_available), "Points attached to a refused estimate")
        group = group.sort_values("offset")
        check(group.offset.tolist() == list(range(mask["length"])), "Wrong target offsets")
        check(group.source_index.tolist() == list(range(mask["start"], mask["end"])), "Wrong source indices")
        truth = sources[mask["dataset"]][mask["start"]:mask["end"]] + mask["shift"]
        close(group.truth, truth, f"{case_id} evaluation truth")
        mean = group.prediction.to_numpy()
        scale = group.relative_scale.to_numpy()
        check(np.isfinite(mean).all() and np.isfinite(scale).all() and (scale > 0).all(), "Invalid mean/scale")
        error = np.abs(truth - mean)
        close(row.mae, error.mean(), "MAE")
        close(row.mse, np.square(error).mean(), "MSE")
        close(row.normalized_mae, error.mean() / row.normalization_scale, "normalized MAE")
        check(all(len(json.loads(n)) == row.neighbor_count for n in group.neighbors), "Neighbor count differs")
        if row.serviced:
            radius = row.calibration_quantile * scale
            close(group.lower, mean - radius, "lower band")
            close(group.upper, mean + radius, "upper band")
            covered = error <= radius
            close(row.gap_coverage, float(covered.all()), "whole-gap coverage")
            close(row.point_coverage, covered.mean(), "point coverage")
            close(row.mean_width, (2 * radius).mean(), "width")
            close(row.normalized_width, (2 * radius).mean() / row.normalization_scale, "normalized width")
            interval_score = 2 * radius + 2 / alpha * np.maximum(error - radius, 0)
            close(row.point_interval_score, interval_score.mean(), "interval score")
        else:
            check(group.lower.isna().all() and group.upper.isna().all(), "Unserviced estimate has fake bands")
            check(row.reason == "insufficient_calibration", "Unexplained point-only estimate")
        scored += 1
    check(scored == int(cases.point_available.sum()), "Missing saved point predictions")
    check(cases.loc[~cases.point_available, "reason"].notna().all(), "Refusal without reason")
    quantile_checks = 0
    if "calibration_id" in cases and "calibration_id" in scores:
        groups = {key: g.score.dropna().to_numpy() for key, g in scores.groupby("calibration_id")}
        for _, row in cases[cases.point_available].iterrows():
            values = groups.get(row.calibration_id, np.array([]))
            check(len(values) == row.calibration_count, "Calibration score count differs")
            rank = math.ceil((len(values) + 1) * (1 - alpha))
            if rank > len(values):
                check(pd.isna(row.calibration_quantile), "Quantile fabricated with insufficient support")
            else:
                close(row.calibration_quantile, np.sort(values)[rank - 1], "corrected order statistic")
            quantile_checks += 1
    else:
        raise ValueError("Calibration IDs required for independent quantile verification")
    reproduced = None
    if comparison:
        comparison = Path(comparison)
        details = {}
        for name in ["predictions.csv.gz", "calibration_scores.csv", "coverage_width.csv"]:
            left = pd.read_csv(directory / name, float_precision="round_trip")
            right = pd.read_csv(comparison / name, float_precision="round_trip")
            pd.testing.assert_frame_equal(left, right, check_exact=True)
            details[name] = {"rows": len(left), "exact_parsed_match": True,
                             "byte_identical": digest(directory / name) == digest(comparison / name)}
        repeated = pd.read_csv(comparison / "case_metrics.csv", float_precision="round_trip")
        pd.testing.assert_frame_equal(cases.drop(columns=["prediction_seconds"]),
                                      repeated.drop(columns=["prediction_seconds"]), check_exact=True)
        repeated_run = json.loads((comparison / "run.json").read_text())
        check(run["plan_sha256"] == repeated_run["plan_sha256"], "Reproduction masks changed")
        details["case_metrics.csv"] = {"rows": len(cases), "exact_except_prediction_seconds": True}
        reproduced = details
    return {"status": "passed", "case_method_rows": len(cases), "prediction_rows": len(points),
            "planned_gaps": len(planned), "scored_case_method_rows": scored,
            "calibration_quantile_checks": quantile_checks,
            "preserved_v1_files_verified": len(baseline["sha256"]), "reproduction": reproduced}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/v2/benchmark")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.input, args.compare)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
