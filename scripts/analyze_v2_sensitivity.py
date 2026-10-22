#!/usr/bin/env python3
"""Post-result width sensitivity; never changes frozen hypotheses or models.

This diagnostic was added after the first final-result inspection showed that
one calibration extreme dominated the mean normalized width. It preserves the
predeclared result and shows its dependence on individual series. It is not an
independent confirmation, retuning step, or replacement hypothesis test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite_or_none(value):
    return float(value) if np.isfinite(value) else None


def width_sensitivity(pairs, target=.9):
    """All widths refer to the frozen pair's jointly interval-serviced cases."""
    pairs = pairs.copy()
    pairs["rolling_static_width_ratio"] = pairs.rolling_normalized_width / pairs.static_normalized_width
    pairs["static_absolute_coverage_error"] = (pairs.static_gap_coverage-target).abs()
    pairs["rolling_absolute_coverage_error"] = (pairs.rolling_gap_coverage-target).abs()
    pairs["absolute_coverage_error_change"] = pairs.rolling_absolute_coverage_error-pairs.static_absolute_coverage_error
    effects, leaveouts = [], []
    for model, group in pairs.groupby("model", sort=True):
        valid = group[(group.common_interval_cases > 0) & np.isfinite(group.rolling_static_width_ratio)]
        widths = valid.rolling_static_width_ratio.to_numpy()
        if not len(widths):
            effects.append({"model": model, "supported_series": 0})
            continue
        denominator = valid.static_normalized_width.sum()
        contributions = valid.static_normalized_width / denominator
        dominating_index = contributions.idxmax()
        effect = {"model": model, "supported_series": len(valid),
                  "frozen_macro_normalized_width_ratio": float(valid.rolling_normalized_width.mean()/valid.static_normalized_width.mean()),
                  "median_series_width_ratio": float(np.median(widths)),
                  "geometric_mean_series_width_ratio": float(np.exp(np.log(widths).mean())),
                  "series_narrower": int((widths < 1-1e-12).sum()),
                  "series_wider": int((widths > 1+1e-12).sum()),
                  "series_same_width": int((np.abs(widths-1) <= 1e-12).sum()),
                  "mean_series_absolute_coverage_error_static": float(valid.static_absolute_coverage_error.mean()),
                  "mean_series_absolute_coverage_error_rolling": float(valid.rolling_absolute_coverage_error.mean()),
                  "series_coverage_closer": int((valid.absolute_coverage_error_change < -1e-12).sum()),
                  "series_coverage_farther": int((valid.absolute_coverage_error_change > 1e-12).sum()),
                  "series_coverage_equal": int((valid.absolute_coverage_error_change.abs() <= 1e-12).sum()),
                  "largest_static_width_contributor": str(valid.loc[dominating_index, "dataset"]),
                  "largest_static_normalized_width_share": float(contributions.max())}
        effects.append(effect)
        for dataset in valid.dataset:
            remaining = valid[valid.dataset != dataset]
            if not len(remaining):
                continue
            width_ratio = float(remaining.rolling_normalized_width.mean()/remaining.static_normalized_width.mean())
            static_coverage = float(remaining.static_gap_coverage.mean())
            rolling_coverage = float(remaining.rolling_gap_coverage.mean())
            leaveouts.append({"model": model, "omitted_dataset": dataset, "remaining_series": len(remaining),
                              "normalized_width_ratio": width_ratio,
                              "static_gap_coverage": static_coverage, "rolling_gap_coverage": rolling_coverage,
                              "coverage_closer": abs(rolling_coverage-target) < abs(static_coverage-target)-1e-12,
                              "width_within_frozen_10_percent_effect_bound": width_ratio <= 1.1})
    return effects, pairs, pd.DataFrame(leaveouts)


def source_extremes(plan, root=ROOT):
    """Observed fit/calibration descriptions only; no inference or model calls."""
    rows = []
    for dataset, info in sorted(plan["datasets"].items()):
        path = Path(root)/info["path"]
        if info.get("sha256") and sha256(path) != info["sha256"]:
            raise ValueError(f"Data checksum mismatch: {dataset}")
        frame = pd.read_csv(path, float_precision="round_trip")
        values = frame.value.to_numpy(dtype=float)
        row = {"dataset": dataset, "fit_end": info["fit_end"],
               "initial_calibration_end": info["initial_calibration_end"],
               "normalization_scale": info["normalization_scale"], "data_sha256": sha256(path)}
        for label, start, end in [("fit", 0, info["fit_end"]),
                                  ("initial_calibration", info["fit_end"], info["initial_calibration_end"])]:
            selected = values[start:end]
            finite_indices = np.flatnonzero(np.isfinite(selected))
            observed = selected[finite_indices]
            row[f"{label}_rows"] = len(selected)
            row[f"{label}_finite_rows"] = len(observed)
            row[f"{label}_missing_rows"] = len(selected)-len(observed)
            for name, operation in [("min", np.min), ("max", np.max), ("median", np.median), ("std", np.std)]:
                row[f"{label}_{name}"] = float(operation(observed)) if len(observed) else None
            row[f"{label}_iqr"] = float(np.subtract(*np.percentile(observed, [75, 25]))) if len(observed) else None
            if len(observed):
                maximum_index = int(start+finite_indices[np.argmax(observed)])
                row[f"{label}_maximum_source_index"] = maximum_index
                row[f"{label}_maximum_timestamp"] = str(frame.timestamp.iloc[maximum_index])
        fit_max, calibration_max = row["fit_max"], row["initial_calibration_max"]
        row["calibration_max_fit_max_ratio"] = calibration_max/fit_max if fit_max and fit_max > 0 else None
        rows.append(row)
    return pd.DataFrame(rows)


def run(input_dir, summary_dir, plan_path, output):
    input_dir, summary_dir, plan_path, output = map(Path, (input_dir, summary_dir, plan_path, output))
    metadata = json.loads((input_dir/"run.json").read_text(encoding="utf-8"))
    provenance = json.loads((summary_dir/"summary_provenance.json").read_text(encoding="utf-8"))
    if metadata.get("status") != "complete" or metadata.get("is_smoke_run", True):
        raise ValueError("Only complete final measurement runs can be diagnosed")
    if provenance["input_sha256"]["run.json"] != sha256(input_dir/"run.json"):
        raise ValueError("Summary and measurement run do not match")
    if metadata["plan_file_sha256"] != sha256(plan_path):
        raise ValueError("Plan differs from the measurement run")
    pairs_path = summary_dir/"uncertainty_pairs.csv"
    if provenance["generated_table_sha256"]["uncertainty_pairs.csv"] != sha256(pairs_path):
        raise ValueError("Frozen generated uncertainty table changed")
    effects, pairs, leaveouts = width_sensitivity(pd.read_csv(pairs_path, float_precision="round_trip"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    extremes = source_extremes(plan)
    cases_path = input_dir/"case_metrics.csv"
    if provenance["input_sha256"]["case_metrics.csv"] != sha256(cases_path):
        raise ValueError("Saved case measurements changed")
    cases = pd.read_csv(cases_path, float_precision="round_trip")
    quantiles = cases[cases.history == "full"].groupby(["dataset", "method", "origin_index", "gap_length"], dropna=False).agg(
        case_rows=("case_id", "size"), finite_quantile_rows=("calibration_quantile", "count"),
        minimum_quantile=("calibration_quantile", "min"), maximum_quantile=("calibration_quantile", "max"),
        minimum_calibration_count=("calibration_count", "min"), maximum_calibration_count=("calibration_count", "max")).reset_index()
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in [("series_width_ratios.csv", pairs), ("width_leave_one_series_out.csv", leaveouts),
                        ("source_fit_calibration_extremes.csv", extremes), ("quantile_extremes.csv", quantiles)]:
        frame.to_csv(output/name, index=False, lineterminator="\n")
    result = {"status": "post-result descriptive sensitivity", "changes_frozen_hypotheses_or_decisions": False,
              "reason": "First final inspection identified extreme normalized widths; disclose sensitivity instead of treating the frozen macro criterion as uniform improvement.",
              "interpretation": "LOO and median/geometric ratios are post-result diagnostics, not replacement thresholds or independent confirmation. Coverage means, coverage deviations and width tradeoffs can disagree across series.",
              "effects": effects,
              "source_sha256": {"run.json": sha256(input_dir/"run.json"), "plan.json": sha256(plan_path),
                                "uncertainty_pairs.csv": sha256(pairs_path), "case_metrics.csv": sha256(cases_path),
                                "script": sha256(__file__)}}
    (output/"sensitivity.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT/"results/v2/benchmark")
    parser.add_argument("--summary", type=Path, default=ROOT/"results/v2/final")
    parser.add_argument("--plan", type=Path, default=ROOT/"results/v2/masks.json")
    parser.add_argument("--output", type=Path, default=ROOT/"results/v2/sensitivity")
    args = parser.parse_args(argv)
    result = run(args.input, args.summary, args.plan, args.output)
    print(json.dumps(result["effects"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
