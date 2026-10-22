#!/usr/bin/env python3
"""Execute the fixed, chronological GapLens benchmark on real observations."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys
import time
import traceback
import uuid

import numpy as np
import pandas as pd

from gaplens.calibration import conformal_quantile, gap_score, sample_gaps
from gaplens.core import AnalogBridge, ExtraTreesBridge, LinearBridge
from gaplens.data import read_series

ROOT = Path(__file__).resolve().parents[1]
METHODS = (
    "linear", "extra_trees", "analog_bridge", "analog_no_bridge",
    "analog_constant_scale", "analog_pooled_calibration",
)
METRICS = (
    "mae", "mse", "rmse", "normalized_mae", "point_coverage", "gap_coverage",
    "mean_width", "normalized_width", "point_interval_score",
    "normalized_point_interval_score", "prediction_seconds",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_series(frame: pd.DataFrame, fractions: list[float]) -> dict:
    """Return disjoint chronological slices; callers cannot borrow context."""
    if len(fractions) != 3 or any(f <= 0 for f in fractions) or not math.isclose(sum(fractions), 1):
        raise ValueError("Three positive split fractions must sum to one")
    n = len(frame)
    boundaries = [0, int(n * fractions[0]), int(n * sum(fractions[:2])), n]
    if any(b <= a for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("Series is too short for three nonempty splits")
    return {
        name: {"frame": frame.iloc[a:b].reset_index(drop=True), "start": a, "end": b}
        for name, a, b in zip(("train", "calibration", "test"), boundaries, boundaries[1:])
    }


def case_metrics(truth, mean, lower, upper, normalization: float, alpha: float) -> dict:
    """Compute per-gap measurements without pooling incompatible physical units."""
    arrays = [np.asarray(x, dtype=float) for x in (truth, mean, lower, upper)]
    truth, mean, lower, upper = arrays
    if truth.ndim != 1 or not len(truth) or any(a.shape != truth.shape for a in arrays):
        raise ValueError("Case arrays must be nonempty equal-length vectors")
    if not all(np.isfinite(a).all() for a in arrays) or np.any(lower > upper):
        raise ValueError("Case measurements require finite, ordered bands")
    if not np.isfinite(normalization) or normalization <= 0 or not 0 < alpha < 1:
        raise ValueError("Positive normalization and alpha in (0,1) are required")
    error = truth - mean
    covered = (truth >= lower) & (truth <= upper)
    width = upper - lower
    interval_score = width + 2 / alpha * np.maximum(lower - truth, 0)
    interval_score += 2 / alpha * np.maximum(truth - upper, 0)
    mae, mse = float(np.abs(error).mean()), float(np.square(error).mean())
    return {
        "mae": mae, "mse": mse, "rmse": float(np.sqrt(mse)),
        "normalized_mae": mae / normalization,
        "point_coverage": float(covered.mean()), "gap_coverage": float(covered.all()),
        "mean_width": float(width.mean()), "normalized_width": float(width.mean() / normalization),
        "point_interval_score": float(interval_score.mean()),
        "normalized_point_interval_score": float(interval_score.mean() / normalization),
    }


def validate_config(config: dict) -> None:
    if tuple(config["methods"]) != METHODS:
        raise ValueError("The fixed benchmark must retain all six preselected methods")
    if not 0 < config["alpha"] < 1:
        raise ValueError("alpha must be in (0,1)")
    for name in ("context", "neighbors", "max_candidates", "calibration_cases_per_length", "test_cases_per_length"):
        if not isinstance(config[name], int) or config[name] <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if not config["datasets"] or len(set(config["datasets"])) != len(config["datasets"]):
        raise ValueError("Dataset names must be nonempty and unique")
    if not config["seeds"] or len(set(config["seeds"])) != len(config["seeds"]):
        raise ValueError("Seeds must be nonempty and unique")
    if not config["gap_lengths"] or any(not isinstance(x, int) or x <= 0 for x in config["gap_lengths"]):
        raise ValueError("Gap lengths must be positive integers")
    if len(set(config["gap_lengths"])) != len(config["gap_lengths"]):
        raise ValueError("Gap lengths must be unique")


def make_models(config: dict, seed: int) -> dict:
    common = dict(context=config["context"], k=config["neighbors"],
                  max_candidates=config["max_candidates"], seasonal_weight=config["seasonal_weight"])
    return {
        "linear": LinearBridge(context=config["context"]),
        "extra_trees": ExtraTreesBridge(context=config["context"], seed=seed,
                                        lengths=tuple(config["gap_lengths"]), **config["extra_trees"]),
        "analog_bridge": AnalogBridge(**common),
        "analog_no_bridge": AnalogBridge(**common, bridge=False),
        "analog_constant_scale": AnalogBridge(**common, adaptive_scale=False),
    }


def peak_rss_mb() -> float | None:
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return float(peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024)
    except (ImportError, AttributeError):
        return None


def summarize(cases: pd.DataFrame, output: Path, config: dict, quick: bool) -> dict:
    grouping = ["dataset", "seed", "method", "gap_length"]
    summary = cases.groupby(grouping, sort=True)[list(METRICS)].mean().reset_index()
    summary["n_cases"] = cases.groupby(grouping, sort=True).size().to_numpy()
    # Reconstruct RMSE from MSE, rather than average per-gap RMSE.
    summary["rmse"] = np.sqrt(summary["mse"])
    summary.to_csv(output / "summary.csv", index=False)
    # Equal weight for every seed/length within a series, and every series overall.
    series = summary.groupby(["dataset", "method"], sort=True)[list(METRICS)].mean().reset_index()
    series["rmse"] = np.sqrt(series["mse"])
    series.to_csv(output / "series_summary.csv", index=False)
    aggregate = series.groupby("method", sort=True)[list(METRICS)].mean().reset_index()
    # Raw cross-series MAE/RMSE mix units; retain only explicitly normalized/coverage/time metrics.
    aggregate = aggregate.drop(columns=["mae", "mse", "rmse", "mean_width", "point_interval_score"])
    seed_level = summary.groupby(["method", "seed"])[["normalized_mae", "gap_coverage", "normalized_width"]].mean()
    for metric in ["normalized_mae", "gap_coverage", "normalized_width"]:
        ranges = seed_level.groupby("method")[metric].agg(["min", "max"])
        aggregate[f"{metric}_seed_min"] = aggregate["method"].map(ranges["min"])
        aggregate[f"{metric}_seed_max"] = aggregate["method"].map(ranges["max"])
    aggregate.to_csv(output / "aggregate_summary.csv", index=False)
    table = aggregate.set_index("method")
    analog = table.loc["analog_bridge"]
    linear = table.loc["linear"]
    trees = table.loc["extra_trees"]
    criteria = config["hypothesis"]
    reduction = 1 - float(analog.normalized_mae / linear.normalized_mae)
    excess = float(analog.normalized_mae / trees.normalized_mae - 1)
    checks = {
        "mae_reduction_vs_linear": {
            "observed": reduction, "required_at_least": criteria["minimum_relative_mae_reduction_vs_linear"],
            "supported": reduction >= criteria["minimum_relative_mae_reduction_vs_linear"],
        },
        "mae_excess_vs_extra_trees": {
            "observed": excess, "required_at_most": criteria["maximum_relative_mae_increase_vs_extra_trees"],
            "supported": excess <= criteria["maximum_relative_mae_increase_vs_extra_trees"],
        },
        "gap_coverage": {
            "observed": float(analog.gap_coverage), "required_at_least": criteria["minimum_gap_coverage"],
            "supported": bool(analog.gap_coverage >= criteria["minimum_gap_coverage"]),
        },
        "adaptive_width": {
            "observed": float(analog.normalized_width),
            "constant_scale_width": float(table.loc["analog_constant_scale", "normalized_width"]),
            "supported": bool(analog.normalized_width < table.loc["analog_constant_scale", "normalized_width"]),
        },
    }
    hypothesis = {
        "is_smoke_run": quick,
        "interpretation": "Smoke only; no hypothesis conclusion" if quick else "Fixed criteria evaluated; no significance claim",
        "all_criteria_supported": None if quick else all(c["supported"] for c in checks.values()),
        "criteria": checks,
    }
    (output / "hypothesis.json").write_text(json.dumps(hypothesis, indent=2) + "\n", encoding="utf-8")
    worst = cases[cases.method == "analog_bridge"].sort_values("normalized_mae", ascending=False).head(12)
    worst.to_csv(output / "worst_cases.csv", index=False)
    return hypothesis


def run(config_path: Path, output: Path, *, quick=False, overwrite=False) -> dict:
    config_path = config_path.resolve()
    original = json.loads(config_path.read_text(encoding="utf-8"))
    config = copy.deepcopy(original)
    if quick:
        config["datasets"] = config["datasets"][:1]
        config["seeds"] = config["seeds"][:1]
        config["calibration_cases_per_length"] = 12
        config["test_cases_per_length"] = 3
        config["extra_trees"] = {"n_estimators": 16, "training_gaps": 90}
    validate_config(config)
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise ValueError(f"Output directory is not empty: {output}; use --overwrite explicitly")
    output.mkdir(parents=True, exist_ok=True)
    # Truncate this run's files only; do not delete unrelated user files.
    log_path = output / "run.log"
    log_path.write_text("", encoding="utf-8")

    def log(message):
        line = f"{utc_now()} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    started = time.perf_counter()
    run_id = str(uuid.uuid4())
    meta = {
        "run_id": run_id, "status": "running", "started_at": utc_now(), "is_smoke_run": quick,
        "command": [sys.executable, *sys.argv], "working_directory": str(Path.cwd()),
        "config": config, "config_sha256": sha256(config_path),
        "effective_config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "protocol_sha256": sha256(ROOT / "docs/PROTOCOL.md"),
        "code_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in [
            ROOT / "src/gaplens/core.py", ROOT / "src/gaplens/calibration.py", Path(__file__).resolve()
        ]},
        "versions": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "scipy", "scikit-learn", "matplotlib"]},
        "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
        "processor": platform.processor(), "cpu_count": __import__("os").cpu_count(),
        "measurement_notes": {
            "rss": "Cumulative peak resident memory for this process, not isolated per-method memory",
            "seed_ranges": "Mask sensitivity only; seeds and lengths can share observations",
            "pooled_timing": "Reuses AnalogBridge predictions; recorded prediction time is copied from that method",
            "prediction_timing": "Test calls have warm reference-window caches; cache construction is included in calibration measurements, not fit_seconds",
            "data": "Real observations with artificial isolated contiguous missing blocks; not naturally missing ground truth",
        },
        "datasets": {}, "fit_measurements": [], "calibration_measurements": [], "selected_cases": [],
    }
    (output / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    rows, point_rows = [], []
    try:
        for dataset in config["datasets"]:
            path = ROOT / config["data_directory"] / f"{dataset}.csv"
            frame = read_series(path)
            splits = split_series(frame, config["split_fractions"])
            train = splits["train"]["frame"]
            train_values = train.value.to_numpy(dtype=float)
            finite_train = train_values[np.isfinite(train_values)]
            iqr = float(np.percentile(finite_train, 75) - np.percentile(finite_train, 25))
            normalization = float(max(iqr, np.std(finite_train) * 1e-3, 1e-8))
            meta["datasets"][dataset] = {
                "path": str(path.relative_to(ROOT)), "sha256": sha256(path), "rows": len(frame),
                "missing_values": int(frame.value.isna().sum()), "train_iqr": iqr,
                "normalization_scale": normalization,
                "cadence_seconds": float((frame.timestamp.iloc[1] - frame.timestamp.iloc[0]).total_seconds()),
                "splits": {n: {"start_index": s["start"], "end_index_exclusive": s["end"],
                                   "first_timestamp": str(s["frame"].timestamp.iloc[0]),
                                   "last_timestamp": str(s["frame"].timestamp.iloc[-1])}
                           for n, s in splits.items()},
            }
            for seed in config["seeds"]:
                log(f"dataset={dataset} seed={seed}: fitting reference-only models")
                models = make_models(config, seed)
                for method, model in models.items():
                    tick = time.perf_counter()
                    model.fit(train_values, pd.DatetimeIndex(train.timestamp))
                    meta["fit_measurements"].append({
                        "dataset": dataset, "seed": seed, "method": method,
                        "fit_seconds": time.perf_counter() - tick,
                        "training_examples": getattr(model, "training_examples_", None),
                        "process_peak_rss_mb": peak_rss_mb(),
                    })
                cal = splits["calibration"]["frame"]
                test = splits["test"]["frame"]
                cal_values, test_values = cal.value.to_numpy(dtype=float), test.value.to_numpy(dtype=float)
                cal_times, test_times = pd.DatetimeIndex(cal.timestamp), pd.DatetimeIndex(test.timestamp)
                scores = {method: {} for method in models}
                calibration_seconds = {method: 0.0 for method in models}
                first_calibration_seconds = {}
                test_cases = {}
                for length in config["gap_lengths"]:
                    cal_seed, test_seed = seed + 1009 * length, seed + 1009 * length + 1_000_003
                    calibration_cases = sample_gaps(cal_values, length, config["context"],
                                                    config["calibration_cases_per_length"], cal_seed)
                    selected_test = sample_gaps(test_values, length, config["context"],
                                                config["test_cases_per_length"], test_seed)
                    if not selected_test:
                        raise ValueError(f"No test windows for {dataset}, length {length}")
                    meta["selected_cases"].append({
                        "dataset": dataset, "seed": seed, "gap_length": length,
                        "calibration_mask_seed": cal_seed, "test_mask_seed": test_seed,
                        "calibration_local_indices": calibration_cases, "test_local_indices": selected_test,
                        "calibration_count": len(calibration_cases), "test_count": len(selected_test),
                    })
                    test_cases[length] = selected_test
                    for method in models:
                        scores[method][length] = []
                    for start, end in calibration_cases:
                        query = cal_values.copy()
                        query[start:end] = np.nan
                        for method, model in models.items():
                            tick = time.perf_counter()
                            pred = model.predict(query, start, end, cal_times)
                            scores[method][length].append(gap_score(cal_values[start:end], pred.mean, pred.scale))
                            elapsed = time.perf_counter() - tick
                            calibration_seconds[method] += elapsed
                            first_calibration_seconds.setdefault(method, elapsed)
                    # This raises if an exact-length group cannot calibrate at the requested alpha.
                    for method in models:
                        conformal_quantile(scores[method][length], config["alpha"])
                    log(f"dataset={dataset} seed={seed} length={length}: calibration={len(calibration_cases)} test={len(selected_test)}")
                for method in models:
                    meta["calibration_measurements"].append({
                        "dataset": dataset, "seed": seed, "method": method,
                        "calibration_prediction_and_score_seconds": calibration_seconds[method],
                        "first_calibration_prediction_and_score_seconds": first_calibration_seconds[method],
                        "n_cases": sum(map(len, scores[method].values())),
                        "note": "Includes lazy candidate-window construction for every gap length; excludes common mask creation",
                    })
                pooled_q = conformal_quantile(
                    [score for length in config["gap_lengths"] for score in scores["analog_bridge"][length]],
                    config["alpha"],
                )
                for length in config["gap_lengths"]:
                    qs = {method: conformal_quantile(scores[method][length], config["alpha"]) for method in models}
                    qs["analog_pooled_calibration"] = pooled_q
                    for case_number, (start, end) in enumerate(test_cases[length]):
                        source_start = start + splits["test"]["start"]
                        case_id = f"{dataset}__s{seed}__l{length}__i{source_start}"
                        query = test_values.copy()
                        query[start:end] = np.nan
                        predictions = {}
                        timings = {}
                        for method, model in models.items():
                            tick = time.perf_counter()
                            predictions[method] = model.predict(query, start, end, test_times)
                            timings[method] = time.perf_counter() - tick
                        predictions["analog_pooled_calibration"] = predictions["analog_bridge"]
                        timings["analog_pooled_calibration"] = timings["analog_bridge"]
                        truth = test_values[start:end]
                        for method in METHODS:
                            pred, q = predictions[method], qs[method]
                            lower, upper = pred.mean - q * pred.scale, pred.mean + q * pred.scale
                            metric = case_metrics(truth, pred.mean, lower, upper, normalization, config["alpha"])
                            row = {
                                "run_id": run_id, "case_id": case_id, "dataset": dataset, "seed": seed,
                                "method": method, "gap_length": length, "source_start": source_start,
                                "source_end_exclusive": source_start + length,
                                "start_timestamp": str(test_times[start]), "case_number": case_number,
                                "calibration_count": sum(map(len, scores["analog_bridge"].values())) if method == "analog_pooled_calibration" else len(scores[method][length]),
                                "calibration_quantile": q, "normalization_scale": normalization,
                                "context_distance": pred.distance, "prediction_seconds": timings[method],
                                **metric,
                            }
                            rows.append(row)
                            for offset in range(length):
                                point_rows.append({
                                    "run_id": run_id, "case_id": case_id, "dataset": dataset,
                                    "seed": seed, "method": method, "gap_length": length,
                                    "source_index": source_start + offset, "offset": offset,
                                    "timestamp": str(test_times[start + offset]), "truth": float(truth[offset]),
                                    "prediction": float(pred.mean[offset]), "relative_scale": float(pred.scale[offset]),
                                    "lower": float(lower[offset]), "upper": float(upper[offset]),
                                })
                log(f"dataset={dataset} seed={seed}: completed all six methods")
        cases = pd.DataFrame(rows)
        cases.to_csv(output / "case_metrics.csv", index=False)
        pd.DataFrame(point_rows).to_csv(output / "predictions.csv", index=False)
        hypothesis = summarize(cases, output, config, quick)
        meta.update({
            "status": "complete", "completed_at": utc_now(), "elapsed_seconds": time.perf_counter() - started,
            "process_peak_rss_mb": peak_rss_mb(), "case_method_rows": len(rows),
            "unique_test_gaps": int(cases.case_id.nunique()), "prediction_rows": len(point_rows),
            "artifact_sha256": {p.name: sha256(p) for p in output.glob("*.csv")},
            "hypothesis_all_criteria_supported": hypothesis["all_criteria_supported"],
        })
        log(f"COMPLETE gaps={meta['unique_test_gaps']} method_cases={len(rows)} elapsed={meta['elapsed_seconds']:.2f}s peak_rss={meta['process_peak_rss_mb']}MiB")
    except Exception as exc:
        meta.update({"status": "failed", "failed_at": utc_now(), "error": str(exc),
                     "elapsed_seconds": time.perf_counter() - started, "process_peak_rss_mb": peak_rss_mb()})
        log(f"FAILED {type(exc).__name__}: {exc}")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())
        raise
    finally:
        (output / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/benchmark.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quick", action="store_true", help="Run a separate smoke test, not the benchmark")
    parser.add_argument("--overwrite", action="store_true", help="Replace known outputs in an existing directory")
    args = parser.parse_args(argv)
    output = args.output or ROOT / "results" / ("smoke" if args.quick else "benchmark")
    try:
        run(args.config, output.resolve(), quick=args.quick, overwrite=args.overwrite)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Benchmark error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
