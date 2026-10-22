#!/usr/bin/env python3
"""Development-only uncertainty diagnostics; never modify preserved v1 results."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from gaplens.calibration import conformal_quantile, gap_score, sample_gaps
from gaplens._core_v1 import AnalogBridge
from gaplens.data import read_series

ROOT = Path(__file__).resolve().parents[1]
REQUESTED_COUNTS = (9, 16, 24, 32, 48)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def descriptive_diagnostics(cases: pd.DataFrame) -> pd.DataFrame:
    analog = cases[cases.method == "analog_bridge"].copy()
    analog["distance_quartile"] = analog.groupby("dataset")["context_distance"].transform(
        lambda values: pd.qcut(values, 4, labels=False, duplicates="drop")
    )
    analog["sampled_time_half"] = analog.groupby("dataset")["source_start"].transform(
        lambda starts: (starts >= starts.median()).astype(int)
    )
    frames = []
    specifications = [
        ("gap_length", analog, "gap_length"),
        ("sampled_time_half", analog, "sampled_time_half"),
        ("distance_quartile", analog, "distance_quartile"),
        ("scale_comparison", cases[cases.method.isin(
            ["analog_bridge", "analog_constant_scale"])], "method"),
    ]
    for diagnostic, frame, stratum in specifications:
        groups = ["dataset", "method"] + ([] if stratum == "method" else [stratum])
        summary = frame.groupby(groups, sort=True).agg(
            n_cases=("case_id", "count"),
            block_coverage=("gap_coverage", "mean"),
            point_coverage=("point_coverage", "mean"),
            mae=("mae", "mean"),
            normalized_mae=("normalized_mae", "mean"),
            mean_width=("mean_width", "mean"),
            normalized_width=("normalized_width", "mean"),
            median_context_distance=("context_distance", "median"),
            calibration_count_min=("calibration_count", "min"),
            calibration_count_max=("calibration_count", "max"),
            calibration_quantile_min=("calibration_quantile", "min"),
            calibration_quantile_max=("calibration_quantile", "max"),
        ).reset_index()
        summary.insert(0, "diagnostic", diagnostic)
        summary.insert(3, "stratum", summary[stratum].astype(str))
        if stratum != "method":
            summary = summary.drop(columns=stratum)
        frames.append(summary)
    return pd.concat(frames, ignore_index=True)


def calibration_count_sensitivity(cases, predictions, configuration):
    """Vary calibration count with fixed saved v1 predictions and nested masks.

    Counts share a shuffled eligible-start order through sample_gaps(seed); the
    smaller selected set is a subset of the larger set. Each calibration gap is
    isolated. Other seeds/lengths may overlap, exactly as in the old experiment.
    """
    records = []
    selected_masks = []
    analog_cases = cases[cases.method == "analog_bridge"]
    analog_points = predictions[predictions.method == "analog_bridge"].copy()
    analog_points["score"] = np.abs(
        analog_points.truth - analog_points.prediction
    ) / analog_points.relative_scale
    original_count_checks = []
    for dataset in configuration["datasets"]:
        frame = read_series(ROOT / configuration["data_directory"] / f"{dataset}.csv")
        n = len(frame)
        fit_end = int(n * configuration["split_fractions"][0])
        cal_end = int(n * sum(configuration["split_fractions"][:2]))
        train, calibration = frame.iloc[:fit_end], frame.iloc[fit_end:cal_end]
        values = calibration.value.to_numpy(dtype=float)
        times = pd.DatetimeIndex(calibration.timestamp)
        model = AnalogBridge(
            context=configuration["context"], k=configuration["neighbors"],
            max_candidates=configuration["max_candidates"],
            seasonal_weight=configuration["seasonal_weight"],
        ).fit(train.value.to_numpy(dtype=float), pd.DatetimeIndex(train.timestamp))
        score_cache = {}
        for seed in configuration["seeds"]:
            for length in configuration["gap_lengths"]:
                group = analog_cases[(analog_cases.dataset == dataset)
                                     & (analog_cases.seed == seed)
                                     & (analog_cases.gap_length == length)]
                points = analog_points[(analog_points.dataset == dataset)
                                       & (analog_points.seed == seed)
                                       & (analog_points.gap_length == length)]
                if group.empty or points.empty:
                    raise ValueError(f"Missing saved v1 cases for {dataset}/{seed}/{length}")
                test_scores = points.groupby("case_id", sort=True).score.max()
                mean_scales = points.groupby("case_id", sort=True).relative_scale.mean()
                norm = float(group.normalization_scale.iloc[0])
                for requested in REQUESTED_COUNTS:
                    mask_seed = seed + 1009 * length
                    masks = sample_gaps(values, length, configuration["context"],
                                        requested, mask_seed)
                    scores = []
                    for start, end in masks:
                        key = (start, end)
                        if key not in score_cache:
                            query = values.copy()
                            query[start:end] = np.nan
                            pred = model.predict(query, start, end, times)
                            score_cache[key] = gap_score(values[start:end], pred.mean, pred.scale)
                        scores.append(score_cache[key])
                    selected_masks.append({
                        "dataset": dataset, "seed": seed, "length": length,
                        "requested_count": requested, "calibration_mask_seed": mask_seed,
                        "calibration_local_indices": masks,
                    })
                    record = {
                        "dataset": dataset, "seed": seed, "gap_length": length,
                        "requested_count": requested, "actual_count": len(scores),
                        "requested_count_reached": len(scores) == requested,
                        "test_cases": len(test_scores),
                        "calibration_score_median": float(np.median(scores)) if scores else None,
                        "calibration_score_max": float(max(scores)) if scores else None,
                    }
                    try:
                        q = conformal_quantile(scores, configuration["alpha"])
                    except ValueError as exc:
                        record.update(status="unavailable", reason=str(exc))
                    else:
                        covered = points.score <= q
                        width = float((2 * q * mean_scales).mean())
                        record.update(
                            status="ok", reason="", calibration_quantile=q,
                            block_coverage=float((test_scores <= q).mean()),
                            point_coverage=float(covered.groupby(points.case_id).mean().mean()),
                            mean_width=width, normalized_width=width / norm,
                        )
                        if requested == configuration["calibration_cases_per_length"]:
                            expected = float(group.calibration_quantile.iloc[0])
                            matches = bool(np.isclose(q, expected, atol=1e-12, rtol=1e-12))
                            original_count_checks.append({
                                "dataset": dataset, "seed": seed, "gap_length": length,
                                "saved_quantile": expected, "recomputed_quantile": q,
                                "matches": matches,
                            })
                            if not matches:
                                raise AssertionError("Original v1 calibration quantile did not reproduce")
                    records.append(record)
        print(f"Development calibration-count sensitivity completed: {dataset}", flush=True)
    return pd.DataFrame(records), selected_masks, original_count_checks


def run(output: Path, *, skip_calibration_sensitivity=False):
    input_paths = [ROOT / "results/benchmark" / name
                   for name in ("case_metrics.csv", "predictions.csv", "run.json")]
    metadata = json.loads(input_paths[2].read_text(encoding="utf-8"))
    configuration = metadata["config"]
    source_paths = input_paths + [ROOT / configuration["data_directory"] / f"{name}.csv"
                                 for name in configuration["datasets"]]
    hashes = {str(path.relative_to(ROOT)): sha256(path) for path in source_paths}
    cases = pd.read_csv(input_paths[0])
    descriptions = descriptive_diagnostics(cases)
    output.mkdir(parents=True, exist_ok=True)
    descriptions.to_csv(output / "v1_diagnostics.csv", index=False)
    result = {
        "scope": "Development-only analysis of the three preserved v1 series",
        "source_sha256": hashes,
        "script_sha256": sha256(Path(__file__)),
        "descriptive_rows": len(descriptions),
        "independence_note": "Seeds, lengths, windows and temporal strata can share observations",
        "half_definition": "Per-dataset source_start below/at-or-above the median sampled start",
        "distance_definition": "Per-dataset qcut(context_distance,4), across lengths and seeds",
        "calibration_count_interpretation": (
            "Requested counts use nested but different selected masks; observed differences combine "
            "calibration sample size, added-window composition, and the discrete quantile rank. "
            "This is sensitivity analysis, not identification of a pure sample-count effect."
        ),
        "calibration_count_sensitivity": "skipped" if skip_calibration_sensitivity else "completed",
    }
    if not skip_calibration_sensitivity:
        # Guard the control algorithm against accidental replacement by a v2 implementation.
        core_path = ROOT / "src/gaplens/_core_v1.py"
        current_core = sha256(core_path)
        if current_core != metadata["code_sha256"]["src/gaplens/core.py"]:
            raise RuntimeError("The v1 core hash changed; explicitly restore the verified control first")
        sensitivity, masks, checks = calibration_count_sensitivity(
            cases, pd.read_csv(input_paths[1]), configuration
        )
        sensitivity.to_csv(output / "v1_calibration_count_sensitivity.csv", index=False)
        result.update(
            frozen_core_path=str(core_path.relative_to(ROOT)),
            frozen_core_sha256=current_core,
            requested_counts=list(REQUESTED_COUNTS),
            sensitivity_rows=len(sensitivity),
            unavailable_interval_rows=int((sensitivity.status != "ok").sum()),
            requested_count_not_reached_rows=int((~sensitivity.requested_count_reached).sum()),
            original_count_quantile_checks=checks,
            selected_calibration_masks=masks,
        )
    for relative, original_hash in hashes.items():
        if sha256(ROOT / relative) != original_hash:
            raise AssertionError(f"Preserved v1 source changed during diagnostics: {relative}")
    result["preserved_v1_sources_unchanged"] = True
    result["artifact_sha256"] = {path.name: sha256(path) for path in sorted(output.glob("v1_*.csv"))}
    (output / "v1_diagnostics.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/v2/development")
    parser.add_argument("--skip-calibration-sensitivity", action="store_true")
    args = parser.parse_args()
    summary = run(args.output, skip_calibration_sensitivity=args.skip_calibration_sensitivity)
    print(json.dumps({key: summary[key] for key in (
        "descriptive_rows", "calibration_count_sensitivity", "preserved_v1_sources_unchanged"
    )}, indent=2))
