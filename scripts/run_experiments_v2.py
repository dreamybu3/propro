#!/usr/bin/env python3
"""Run the frozen v2 study; create and inspect all masks before model scoring.

Only this module's plan builder reads hidden values to generate MNAR masks.
Estimators receive fitted history and exactly the declared observed context.
Final data never select parameters: selected parameters come from the three
already-inspected development series in ``tune_v2.py``.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import pandas as pd

from gaplens.calibration import conformal_quantile, gap_score, sample_gaps
from gaplens._core_v1 import AnalogBridge
from gaplens.core import ExtraTreesBridge, LinearBridge
from gaplens.data import read_series

ROOT = Path(__file__).resolve().parents[1]
METHODS = (
    "linear_static", "extra_trees_static", "raw_knn_static", "seasonal_static",
    "kalman_static", "pca_static", "v1_static", "v1_rolling",
    "diverse_static", "diverse_rolling", "diverse_k12_static",
)
MODEL_NAMES = ("linear", "extra_trees", "raw_knn", "seasonal", "kalman", "pca", "v1", "diverse", "diverse_k12")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def peak_rss_mb():
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return float(value / (1024 * 1024) if sys.platform == "darwin" else value / 1024)
    except ImportError:
        return None


def stable_seed(dataset, seed, *parts):
    """No dependence on Python's per-process randomized hash."""
    raw = "|".join(map(str, (dataset, seed, *parts)))
    return int.from_bytes(hashlib.sha256(raw.encode()).digest()[:4], "little")


def series_settings(n, config):
    prefix = "small" if n < config["small_series_threshold"] else "large"
    return {
        "context": config[f"{prefix}_context"],
        "lengths": config[f"{prefix}_lengths"],
        "stress_length": config[f"{prefix}_stress_length"],
    }


def training_scale(values):
    finite = np.asarray(values)[np.isfinite(values)]
    if len(finite) < 2:
        raise ValueError("At least two training observations required")
    iqr = float(np.subtract(*np.percentile(finite, [75, 25])))
    return float(max(iqr, np.std(finite) * 1e-3, 1e-8))


def eligible_starts(values, begin, finish, length, context):
    """Complete target+context windows contained in the allowed split."""
    begin, finish = int(begin), int(finish)
    width = length + 2 * context
    if finish - begin < width:
        return np.empty(0, dtype=int)
    bad = np.r_[0, np.cumsum(~np.isfinite(values[begin:finish]))]
    starts = np.flatnonzero(bad[width:] == bad[:-width])
    return starts + begin + context


def weighted_starts(values, begin, finish, length, context, count, seed,
                    mechanism="mcar", fit_center=0., fit_scale=1.):
    """Sample disjoint windows; MAR sees left context, MNAR sees hidden truth.

    Native missingness is an eligibility condition, never filled to add cases.
    Magnitude weighting is capped at ten to avoid effectively deterministic
    extreme-case selection. No model error participates in any mask decision.
    """
    candidates = eligible_starts(values, begin, finish, length, context)
    if not len(candidates):
        return []
    weights = np.ones(len(candidates), dtype=float)
    if mechanism not in {"mcar", "mar", "mnar"}:
        raise ValueError("Unknown missingness mechanism")
    if mechanism != "mcar":
        offsets = np.arange(-context, 0) if mechanism == "mar" else np.arange(length)
        level = np.mean(values[candidates[:, None] + offsets], axis=1)
        weights += np.minimum(np.abs(level - fit_center) / fit_scale, 9.)
    rng = np.random.default_rng(seed)
    # Exponential race gives a weighted random permutation without replacement.
    order = np.argsort(-np.log(np.maximum(rng.random(len(candidates)), 1e-300)) / weights,
                       kind="stable")
    occupied = np.zeros(len(values), dtype=bool)
    result = []
    for index in order:
        start = int(candidates[index])
        if not occupied[start-context:start+length+context].any():
            result.append(start)
            occupied[start-context:start+length+context] = True
            if len(result) == count:
                break
    return sorted(result)


def local_query(values, start, end, context, begin, finish, hidden=(), shift=0.):
    """Expose exactly the same 2c measurements to every method.

    Deliberately hide all other query values, including the target, even if a
    future estimator accidentally reads beyond its documented context API.
    """
    result = np.full(len(values), np.nan)
    left = np.arange(max(begin, start-context), start)
    right = np.arange(end, min(finish, end+context))
    indices = np.r_[left, right]
    result[indices] = values[indices] + shift
    if len(hidden):
        result[np.asarray(hidden, dtype=int)] = np.nan
    result[start:end] = np.nan
    return result


def _case(dataset, seed, origin_index, regime, number, start, length, begin, finish,
          hidden=None, shift=0., history="full"):
    end = int(start + length)
    hidden = list(range(int(start), end)) if hidden is None else sorted(set(map(int, hidden)))
    return {
        "case_id": f"{dataset}__s{seed}__o{origin_index}__{regime}__{number}",
        "dataset": dataset, "seed": seed, "origin_index": origin_index,
        "regime": regime, "number": number, "start": int(start), "end": end,
        "length": int(length), "query_begin": int(begin), "query_end": int(finish),
        "hidden_indices": hidden, "shift": float(shift), "history": history,
    }


def build_plan(config, datasets, frames):
    """Persist source-index masks and available calibration history before fit.

    Each seed represents a separate simulated outage history. Only simultaneous
    batches are actual historical outages; isolated cases are counterfactual
    probes and do not remove truth from subsequent batches. All earlier batch
    targets remain unavailable at every later rolling calibration origin.
    """
    if tuple(config["methods"]) != METHODS:
        raise ValueError("All eleven predeclared method/calibration combinations are required")
    plan = {"schema_version": 2, "config_sha256": digest_json(config), "datasets": {},
            "cases": [], "calibration": [], "unavailable_regimes": []}
    for entry in datasets:
        dataset = entry["id"]
        values = frames[dataset].value.to_numpy()
        n = len(values)
        fit_end = int(n * config["fit_fraction"])
        initial_end = int(n * config["initial_calibration_end"])
        settings = series_settings(n, config)
        context = settings["context"]
        short, long = settings["lengths"]
        all_lengths = sorted(set([short, long, settings["stress_length"]]))
        fit_values = values[:fit_end]
        scale = training_scale(fit_values)
        center = float(np.nanmedian(fit_values))
        plan["datasets"][dataset] = {
            **settings, "rows": n, "fit_end": fit_end,
            "scarce_fit_end": max(2*context+1, int(fit_end * config["scarce_fit_fraction"])),
            "initial_calibration_end": initial_end,
            "normalization_scale": scale, "training_median": center,
            "training_variance": float(np.nanvar(fit_values)),
            "source_group": entry["source_group"], "system_group": entry["system_group"],
            "period": config["seasonal_periods"][dataset],
            "cadence_seconds": float((frames[dataset].timestamp.iloc[1]-frames[dataset].timestamp.iloc[0]).total_seconds()),
            "length_duration_seconds": {str(length): float(length*(frames[dataset].timestamp.iloc[1]-frames[dataset].timestamp.iloc[0]).total_seconds()) for length in all_lengths},
            "path": entry["processed_path"], "sha256": sha256(ROOT / entry["processed_path"]),
            "all_lengths": all_lengths,
        }
        for seed in config["seeds"]:
            prior_hidden = set()
            for oi, origin in enumerate(config["origins"]):
                begin = int(n * origin)
                finish = min(n, int(n * (origin + config["test_fraction"]) + 1e-9))
                # Generate calibration before adding this origin's outages.
                for mode in ("static", "rolling"):
                    a, b = (fit_end, initial_end) if mode == "static" else (
                        max(fit_end, int(n * (origin-config["rolling_fraction"]) + 1e-9)), begin)
                    available = values[a:b].copy()
                    unavailable = sorted(i for i in prior_hidden if a <= i < b)
                    if unavailable:
                        available[np.asarray(unavailable)-a] = np.nan
                    for length in all_lengths:
                        mask_seed = stable_seed(dataset, seed, "calibration", length)
                        windows = sample_gaps(available, length, context,
                                              config["calibration_cases_per_length"], mask_seed)
                        plan["calibration"].append({
                            "dataset": dataset, "seed": seed, "origin_index": oi, "mode": mode,
                            "length": length, "begin": a, "end": b,
                            "unavailable_history_indices": unavailable,
                            "windows": [[int(s+a), int(e+a)] for s, e in windows],
                            "mask_seed": mask_seed,
                        })
                cases = []
                for regime, length, mechanism, history in [
                    ("mcar_short", short, "mcar", "full"),
                    ("mcar_long", long, "mcar", "full"),
                    ("mar", short, "mar", "full"),
                    ("mnar", short, "mnar", "full"),
                    ("scarce_history", short, "mcar", "scarce"),
                ]:
                    starts = weighted_starts(values, begin, finish, length, context,
                        config["cases_per_random_regime"], stable_seed(dataset, seed, oi, regime),
                        mechanism, center, scale)
                    for j, start in enumerate(starts):
                        cases.append(_case(dataset, seed, oi, regime, j, start, length, begin, finish,
                                           history=history))
                    if len(starts) < config["cases_per_random_regime"]:
                        plan["unavailable_regimes"].append({"dataset": dataset, "seed": seed,
                            "origin_index": oi, "regime": regime,
                            "requested": config["cases_per_random_regime"], "available": len(starts),
                            "reason": "Insufficient finite disjoint windows in the fixed test split"})
                for regime, length in [("stress_long", settings["stress_length"]),
                                       ("damaged_context", short), ("level_shift", short)]:
                    starts = weighted_starts(values, begin, finish, length, context, 1,
                                             stable_seed(dataset, seed, oi, regime))
                    if starts:
                        start = starts[0]
                        hidden = list(range(start, start+length))
                        if regime == "damaged_context":
                            hidden.append(start-1)
                        shift = config["shift_training_scale_multiplier"] * scale if regime == "level_shift" else 0.
                        cases.append(_case(dataset, seed, oi, regime, 0, start, length, begin, finish,
                                           hidden=hidden, shift=shift))
                    else:
                        plan["unavailable_regimes"].append({"dataset": dataset, "seed": seed,
                            "origin_index": oi, "regime": regime, "requested": 1, "available": 0,
                            "reason": "No finite complete window in the fixed test split"})
                if np.isfinite(values[begin:begin+short]).all():
                    cases.append(_case(dataset, seed, oi, "boundary", 0, begin, short, begin, finish))
                else:
                    plan["unavailable_regimes"].append({"dataset": dataset, "seed": seed,
                        "origin_index": oi, "regime": "boundary", "requested": 1, "available": 0,
                        "reason": "Boundary target has native missing ground truth"})
                # A neighboring pair (one observed sample apart) plus a distant
                # third target creates an explicit simultaneous-context failure.
                pair_width = 2*short + 1
                pairs = weighted_starts(values, begin, finish, pair_width, context, 1,
                                         stable_seed(dataset, seed, oi, "simultaneous_pair"))
                simultaneous = []
                if pairs:
                    first = pairs[0]
                    simultaneous = [first, first+short+1]
                    others = weighted_starts(values, begin, finish, short, context, 8,
                                              stable_seed(dataset, seed, oi, "simultaneous_other"))
                    for candidate in others:
                        if candidate+short+context <= first-context or candidate-context >= first+pair_width+context:
                            simultaneous.append(candidate)
                            break
                hidden = sorted({i for s in simultaneous for i in range(s, s+short)})
                for j, start in enumerate(simultaneous):
                    cases.append(_case(dataset, seed, oi, "simultaneous", j, start, short,
                                       begin, finish, hidden=hidden))
                if len(simultaneous) < 3:
                    plan["unavailable_regimes"].append({"dataset": dataset, "seed": seed,
                        "origin_index": oi, "regime": "simultaneous", "requested": 3,
                        "available": len(simultaneous), "reason": "Insufficient finite pair/third windows"})
                prior_hidden.update(hidden)
                plan["cases"].extend(cases)
    plan["plan_sha256"] = digest_json(plan)
    validate_plan(plan)
    return plan


def validate_plan(plan):
    case_ids = [case["case_id"] for case in plan["cases"]]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Duplicate case identifiers")
    for cal in plan["calibration"]:
        info = plan["datasets"][cal["dataset"]]
        c = info["context"]
        occupied = set()
        forbidden = set(cal["unavailable_history_indices"])
        if cal["begin"] < info["fit_end"]:
            raise ValueError("Calibration overlaps fitting history")
        for start, end in cal["windows"]:
            window = set(range(start-c, end+c))
            if start-c < cal["begin"] or end+c > cal["end"]:
                raise ValueError("Calibration context crosses split boundary")
            if window & occupied or window & forbidden:
                raise ValueError("Calibration overlaps another window or hidden history")
            occupied.update(window)
    for case in plan["cases"]:
        if case["start"] < case["query_begin"] or case["end"] > case["query_end"]:
            raise ValueError("Target crosses query split boundary")
        if not set(range(case["start"], case["end"])).issubset(case["hidden_indices"]):
            raise ValueError("Target must be hidden")


def make_model(name, context, lengths, seed, period, parameters=None, max_candidates=4000):
    from gaplens.models_v2 import (ConditionalTrajectoryPCA, DiverseAnalogBridge,
                                  LocalLinearKalman, SeasonalBridge)
    parameters = parameters or {}
    if name == "linear":
        return LinearBridge(context=context)
    if name == "v1":
        return AnalogBridge(context=context, max_candidates=max_candidates)
    if name == "raw_knn":
        return AnalogBridge(context=context, max_candidates=max_candidates, bridge=False)
    if name == "diverse_k12":
        return DiverseAnalogBridge(context=context, max_candidates=max_candidates, k=12)
    if name == "diverse":
        return DiverseAnalogBridge(context=context, max_candidates=max_candidates, **parameters)
    if name == "extra_trees":
        return ExtraTreesBridge(context=context, seed=seed, lengths=tuple(lengths), **parameters)
    if name == "seasonal":
        return SeasonalBridge(context=context, period=period, **parameters)
    if name == "kalman":
        return LocalLinearKalman(context=context, **parameters)
    if name == "pca":
        return ConditionalTrajectoryPCA(context=context, **parameters)
    raise ValueError(f"Unknown model {name}")


def prediction_metrics(truth, mean, scale, q, normalization, alpha):
    truth, mean, scale = map(np.asarray, (truth, mean, scale))
    if truth.shape != mean.shape or truth.shape != scale.shape:
        raise ValueError("Prediction shape mismatch")
    if not all(np.isfinite(a).all() for a in (truth, mean, scale)) or (scale <= 0).any():
        raise ValueError("Nonfinite prediction or invalid scale")
    error = truth - mean
    result = {"mae": float(np.abs(error).mean()), "mse": float(np.square(error).mean()),
              "normalized_mae": float(np.abs(error).mean()/normalization)}
    if q is not None:
        radius = q * scale
        if not np.isfinite(radius).all():
            raise ValueError("Nonfinite interval radius")
        covered = np.abs(error) <= radius
        width = 2*radius
        interval_score = width + 2/alpha*np.maximum(np.abs(error)-radius, 0)
        result.update(point_coverage=float(covered.mean()), gap_coverage=float(covered.all()),
                      mean_width=float(width.mean()), normalized_width=float(width.mean()/normalization),
                      point_interval_score=float(interval_score.mean()),
                      normalized_point_interval_score=float(interval_score.mean()/normalization))
    return result


def _guard_final_run(config, plan_path):
    protocol = ROOT / "docs/v2/PROTOCOL.md"
    freeze = ROOT / "configs/v2_freeze.json"
    if not protocol.exists() or not freeze.exists():
        raise ValueError("Final scoring requires docs/v2/PROTOCOL.md and committed configs/v2_freeze.json")
    frozen = json.loads(freeze.read_text(encoding="utf-8"))
    if frozen.get("config_sha256") != digest_json(config):
        raise ValueError("Configuration differs from pre-evaluation freeze")
    if frozen.get("protocol_sha256") != sha256(protocol):
        raise ValueError("Protocol differs from pre-evaluation freeze")
    if frozen.get("plan_sha256") != sha256(plan_path):
        raise ValueError("Masks differ from pre-evaluation freeze")
    for path, digest in frozen.get("protected_sha256", {}).items():
        if sha256(ROOT/path) != digest:
            raise ValueError(f"Frozen artifact changed: {path}")
    try:
        committed = subprocess.run(["git", "show", "HEAD:configs/v2_freeze.json"], cwd=ROOT,
                                   check=True, capture_output=True).stdout
        if committed != freeze.read_bytes():
            raise ValueError("Local freeze differs from committed pre-evaluation manifest")
    except subprocess.CalledProcessError as exc:
        raise ValueError("Freeze manifest must be committed before final scoring") from exc
    return frozen


def load_inputs(config):
    manifest = json.loads((ROOT / config["manifest"]).read_text(encoding="utf-8"))
    datasets = manifest["datasets"]
    frames = {}
    for item in datasets:
        path = ROOT / item["processed_path"]
        if sha256(path) != item["processed_sha256"]:
            raise ValueError(f"Source checksum mismatch: {item['id']}")
        frames[item["id"]] = read_series(path)
    return datasets, frames


def _write_csv_gz(frame, path):
    # Filename is deliberately empty, timestamp fixed: output bytes reproduce.
    with Path(path).open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(frame.to_csv(index=False, lineterminator="\n").encode())


def run(config_path, plan_path, output, *, smoke=False):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    datasets, frames = load_inputs(config)
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    if plan["config_sha256"] != digest_json(config):
        raise ValueError("Plan does not match configuration")
    validate_plan(plan)
    frozen = None if smoke else _guard_final_run(config, plan_path)
    selection = json.loads((ROOT/config["selection"]).read_text(encoding="utf-8"))
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output is not empty: {output}. Use a new path; original results are preserved.")
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    run_meta = {"schema_version": 2, "status": "running", "started_at": utc_now(),
                "is_smoke_run": smoke, "config": config, "config_sha256": digest_json(config),
                "plan_file_sha256": sha256(plan_path), "plan_sha256": plan["plan_sha256"],
                "selection_sha256": sha256(ROOT/config["selection"]), "freeze": frozen,
                "code_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in [
                    Path(__file__).resolve(), ROOT/"src/gaplens/core.py", ROOT/"src/gaplens/_core_v1.py", ROOT/"src/gaplens/models_v2.py",
                    ROOT/"src/gaplens/calibration.py", ROOT/"src/gaplens/data.py"]},
                "versions": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "scipy", "scikit-learn"]},
                "python": sys.version, "platform": platform.platform(),
                "measurement_notes": {
                    "rss": "Cumulative process peak, not isolated per-method RSS; Windows may be unavailable.",
                    "cold": "First prediction per fitted model/length includes lazy window/cache construction.",
                    "warm": "Case prediction after calibration; timing is hardware-dependent.",
                    "point_only": "Point estimates remain scored when calibration is insufficient; these cases are not serviced product reconstructions.",
                    "denominators": "All generated eligible target gaps retained, including refusals; unavailable_regimes in masks additionally records requested targets lacking finite truth. Nuisance damaged-context samples are not extra target cases.",
                    "timing_reuse": "Static and rolling variants of the same predictor reuse point predictions and copy their timing; do not sum these rows as separate model work.",
                }}
    write_json(output/"run.json", run_meta)
    log_path = output/"run.log"

    def log(message):
        line = f"{utc_now()} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line+"\n")

    rows, points, scores_rows, curves, performance = [], [], [], [], []
    selected_datasets = datasets[:1] if smoke else datasets
    seeds = config["seeds"][:1] if smoke else config["seeds"]
    try:
        for entry in selected_datasets:
            dataset = entry["id"]
            info = plan["datasets"][dataset]
            frame = frames[dataset]
            values, timestamps = frame.value.to_numpy(), pd.DatetimeIndex(frame.timestamp)
            context = info["context"]
            log(f"dataset={dataset} rows={len(values)} context={context} lengths={info['all_lengths']}")
            for seed in seeds:
                models, fit_errors, seen_cold = {}, {}, set()
                for history in ("full", "scarce"):
                    fit_end = info["fit_end"] if history == "full" else info["scarce_fit_end"]
                    for name in MODEL_NAMES:
                        tick = time.perf_counter()
                        model = make_model(name, context, info["all_lengths"], seed, info["period"],
                                           selection["parameters"].get(name, {}), config["maximum_candidates"])
                        error = None
                        try:
                            model.fit(values[:fit_end], timestamps[:fit_end])
                            models[(history, name)] = model
                        except ValueError as exc:
                            error = str(exc)
                            fit_errors[(history, name)] = error
                        performance.append({"dataset": dataset, "seed": seed, "history": history,
                            "model": name, "stage": "fit", "seconds": time.perf_counter()-tick,
                            "training_rows": fit_end, "training_examples": getattr(model, "training_examples_", None),
                            "process_peak_rss_mb": peak_rss_mb(), "error": error})
                cal_cache = {}
                for oi, origin in enumerate(config["origins"]):
                    if smoke and oi > 0:
                        break
                    origin_cal = [c for c in plan["calibration"] if c["dataset"] == dataset and
                                  c["seed"] == seed and c["origin_index"] == oi]
                    origin_cases = [c for c in plan["cases"] if c["dataset"] == dataset and
                                    c["seed"] == seed and c["origin_index"] == oi]
                    for case in origin_cases:
                        start, end = case["start"], case["end"]
                        query = local_query(values, start, end, context, case["query_begin"], case["query_end"],
                                            case["hidden_indices"], case["shift"])
                        truth = values[start:end] + case["shift"]
                        if not np.isfinite(truth).all():
                            raise ValueError("Plan contains native-missing evaluation truth")
                        context_values = np.r_[query[max(0, start-context):start], query[end:end+context]]
                        context_ok = len(context_values) == 2*context and np.isfinite(context_values).all()
                        context_shift = (float(np.nanmean(context_values))-info["training_median"])/info["normalization_scale"] if np.isfinite(context_values).any() else None
                        context_variance_ratio = float(np.nanvar(context_values)/max(info["training_variance"], 1e-16)) if np.isfinite(context_values).any() else None
                        context_trend = float((np.mean(context_values[context:])-np.mean(context_values[:context]))/((end-start+context)*info["normalization_scale"])) if context_ok else None
                        model_predictions = {}
                        for method in METHODS:
                            name, mode = method.rsplit("_", 1)
                            history = case["history"]
                            row = {"case_id": case["case_id"], "dataset": dataset,
                                "source_group": entry["source_group"], "system_group": entry["system_group"],
                                "seed": seed, "origin_index": oi, "origin_fraction": origin,
                                "regime": case["regime"], "history": history, "method": method,
                                "gap_length": end-start, "source_start": start, "source_end_exclusive": end,
                                "normalization_scale": info["normalization_scale"], "context_shift": context_shift,
                                "context_variance_ratio": context_variance_ratio, "context_trend": context_trend,
                                "context_spread_ratio": None if context_variance_ratio is None else float(np.sqrt(context_variance_ratio)),
                                "context_endpoint_change": None if context_trend is None else context_trend*(end-start+context),
                                "status": "refused", "reason": None, "point_available": False, "serviced": False,
                                "calibration_count": 0, "calibration_quantile": None, "neighbor_count": 0,
                                "context_distance": None, "prediction_seconds": None, "calibration_id": None}
                            if not context_ok:
                                row["reason"] = "boundary_context" if case["regime"] == "boundary" else "missing_context"
                                rows.append(row)
                                continue
                            if (history, name) in fit_errors:
                                row["reason"] = "fit_failed: "+fit_errors[(history, name)]
                                rows.append(row)
                                continue
                            model = models[(history, name)]
                            cal = next(c for c in origin_cal if c["mode"] == mode and c["length"] == end-start)
                            # Exact masks, not just origin labels, define reuse.
                            cache_key = digest_json({"dataset": dataset, "seed": seed, "history": history,
                                "model": name, "windows": cal["windows"],
                                "fit_end": info["fit_end"] if history == "full" else info["scarce_fit_end"]})
                            row["calibration_id"] = cache_key
                            if cache_key not in cal_cache:
                                scores = []
                                tick = time.perf_counter()
                                for ci, (a, b) in enumerate(cal["windows"]):
                                    cal_query = local_query(values, a, b, context, cal["begin"], cal["end"],
                                                            cal["unavailable_history_indices"])
                                    cal_row = {"dataset": dataset, "seed": seed, "origin_index": oi,
                                        "mode": mode, "history": history, "model": name, "length": end-start,
                                        "calibration_id": cache_key,
                                        "source_start": a, "source_end_exclusive": b, "score": None, "error": None}
                                    cold_key = (history, name, b-a)
                                    cold = cold_key not in seen_cold
                                    prediction_started = time.perf_counter()
                                    try:
                                        pred = model.predict(cal_query, a, b, timestamps)
                                        score = gap_score(values[a:b], pred.mean, pred.scale)
                                        scores.append(score)
                                        cal_row["score"] = score
                                    except ValueError as exc:
                                        cal_row["error"] = str(exc)
                                    if cold:
                                        performance.append({"dataset": dataset, "seed": seed, "history": history,
                                            "model": name, "stage": "cold_prediction", "length": b-a,
                                            "seconds": time.perf_counter()-prediction_started,
                                            "process_peak_rss_mb": peak_rss_mb(), "error": cal_row["error"]})
                                        seen_cold.add(cold_key)
                                    scores_rows.append(cal_row)
                                quantiles = {}
                                for alpha in config["curve_alphas"]:
                                    try:
                                        quantiles[str(alpha)] = conformal_quantile(scores, alpha)
                                    except ValueError:
                                        quantiles[str(alpha)] = None
                                cal_cache[cache_key] = (scores, quantiles)
                                performance.append({"dataset": dataset, "seed": seed, "history": history,
                                    "model": name, "stage": "calibration", "origin_index": oi, "mode": mode,
                                    "calibration_id": cache_key,
                                    "length": end-start, "seconds": time.perf_counter()-tick,
                                    "calibration_count": len(scores), "process_peak_rss_mb": peak_rss_mb()})
                            scores, quantiles = cal_cache[cache_key]
                            q = quantiles[str(config["alpha"])]
                            row.update(calibration_count=len(scores), calibration_quantile=q)
                            if name not in model_predictions:
                                tick = time.perf_counter()
                                try:
                                    pred = model.predict(query, start, end, timestamps)
                                    prediction_metrics(truth, pred.mean, pred.scale, None,
                                                       info["normalization_scale"], config["alpha"])
                                    model_predictions[name] = (pred, time.perf_counter()-tick, None)
                                except ValueError as exc:
                                    model_predictions[name] = (None, time.perf_counter()-tick, str(exc))
                            pred, elapsed, error = model_predictions[name]
                            row["prediction_seconds"] = elapsed
                            if error:
                                row["reason"] = "prediction_failed: "+error
                                rows.append(row)
                                continue
                            metrics = prediction_metrics(truth, pred.mean, pred.scale, q,
                                                         info["normalization_scale"], config["alpha"])
                            row.update(**metrics, status="reconstructed" if q is not None else "point_only",
                                       reason=None if q is not None else "insufficient_calibration",
                                       point_available=True, serviced=q is not None,
                                       neighbor_count=len(pred.neighbors), context_distance=float(pred.distance))
                            rows.append(row)
                            for alpha in config["curve_alphas"]:
                                aq = quantiles[str(alpha)]
                                curve = {"case_id": case["case_id"], "dataset": dataset, "method": method,
                                         "regime": case["regime"], "alpha": alpha, "serviced": aq is not None,
                                         "calibration_count": len(scores)}
                                if aq is not None:
                                    curve.update(prediction_metrics(truth, pred.mean, pred.scale, aq,
                                                                  info["normalization_scale"], alpha))
                                curves.append(curve)
                            for offset in range(end-start):
                                points.append({"case_id": case["case_id"], "dataset": dataset, "method": method,
                                    "source_index": start+offset, "offset": offset, "truth": float(truth[offset]),
                                    "prediction": float(pred.mean[offset]), "relative_scale": float(pred.scale[offset]),
                                    "lower": None if q is None else float(pred.mean[offset]-q*pred.scale[offset]),
                                    "upper": None if q is None else float(pred.mean[offset]+q*pred.scale[offset]),
                                    "neighbors": json.dumps(pred.neighbors, separators=(",", ":"))})
                    log(f"dataset={dataset} seed={seed} origin={origin}: cases={len(origin_cases)}")
        curve_keys = {(r["case_id"], r["method"], r["alpha"]) for r in curves}
        for row in rows:
            for alpha in config["curve_alphas"]:
                if (row["case_id"], row["method"], alpha) not in curve_keys:
                    curves.append({"case_id": row["case_id"], "dataset": row["dataset"],
                        "method": row["method"], "regime": row["regime"], "alpha": alpha,
                        "serviced": False, "calibration_count": row["calibration_count"]})
        cases = pd.DataFrame(rows)
        cases.to_csv(output/"case_metrics.csv", index=False)
        _write_csv_gz(pd.DataFrame(points), output/"predictions.csv.gz")
        pd.DataFrame(scores_rows).to_csv(output/"calibration_scores.csv", index=False)
        pd.DataFrame(curves).to_csv(output/"coverage_width.csv", index=False)
        pd.DataFrame(performance).to_csv(output/"performance.csv", index=False)
        run_meta.update(status="complete", completed_at=utc_now(), elapsed_seconds=time.perf_counter()-started,
                        process_peak_rss_mb=peak_rss_mb(), unique_test_gaps=int(cases.case_id.nunique()),
                        case_method_rows=len(rows), prediction_rows=len(points),
                        point_available_rows=int(cases.point_available.sum()), serviced_rows=int(cases.serviced.sum()),
                        artifact_sha256={p.name: sha256(p) for p in output.iterdir() if p.suffix in {".csv", ".gz"}})
        log(f"COMPLETE gaps={run_meta['unique_test_gaps']} methodcases={len(rows)} elapsed={run_meta['elapsed_seconds']:.2f}s")
    except Exception as exc:
        run_meta.update(status="failed", failed_at=utc_now(), error=str(exc), elapsed_seconds=time.perf_counter()-started)
        log(f"FAILED {type(exc).__name__}: {exc}")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())
        # Preserve evidence rather than discard failed/unfinished cases.
        pd.DataFrame(rows).to_csv(output/"partial_case_metrics.csv", index=False)
        raise
    finally:
        write_json(output/"run.json", run_meta)
    return run_meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT/"configs/benchmark_v2.json")
    parser.add_argument("--plan", type=Path, default=ROOT/"results/v2/masks.json")
    parser.add_argument("--output", type=Path, default=ROOT/"results/v2/benchmark")
    parser.add_argument("--prepare", action="store_true", help="Generate masks only, without fitting/scoring")
    parser.add_argument("--smoke", action="store_true", help="Only after freeze: scored smoke is not final evidence")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.prepare:
        if args.plan.exists():
            parser.error("Plan already exists; use a separate path to preserve the frozen masks")
        datasets, frames = load_inputs(config)
        plan = build_plan(config, datasets, frames)
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.plan, plan)
        print(f"Prepared {len(plan['cases'])} targets and {len(plan['calibration'])} calibration strata; no models run.")
        return 0
    # A smoke run on final data is also an inspection; freeze first.
    _guard_final_run(config, args.plan)
    run(args.config, args.plan, args.output, smoke=args.smoke)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
