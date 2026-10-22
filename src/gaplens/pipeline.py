"""The complete offline repair workflow, with explicit abstention and provenance."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import tempfile
import time

import numpy as np
import pandas as pd

from .calibration import conformal_quantile, gap_score, sample_gaps
from .core import AnalogBridge, ExtraTreesBridge, LinearBridge
from .data import find_gaps, read_series


@dataclass(frozen=True)
class RepairConfig:
    method: str = "analog"
    context: int = 6
    neighbors: int = 12
    alpha: float = 0.1
    max_gap: int = 48
    calibration_fraction: float = 0.25
    calibration_gaps: int = 32
    seed: int = 17

    def validate(self):
        if self.method not in {"analog", "linear", "extra-trees"}:
            raise ValueError("method must be analog, linear or extra-trees")
        for name in ("context", "neighbors", "max_gap", "calibration_gaps"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.context > 256 or self.max_gap > 512 or self.neighbors > 256 or self.calibration_gaps > 256:
            raise ValueError("Resource limits: context<=256, max_gap<=512, neighbors<=256, calibration_gaps<=256")
        if not math.isfinite(self.alpha) or not 0 < self.alpha < 1:
            raise ValueError("alpha must be strictly between zero and one")
        if not math.isfinite(self.calibration_fraction) or not 0 < self.calibration_fraction < 1:
            raise ValueError("calibration_fraction must be strictly between zero and one")
        if not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        return self


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _time(value):
    return pd.Timestamp(value).isoformat()


def _model(config, lengths):
    if config.method == "analog":
        return AnalogBridge(context=config.context, k=config.neighbors)
    if config.method == "linear":
        return LinearBridge(context=config.context)
    return ExtraTreesBridge(context=config.context, seed=config.seed, lengths=tuple(lengths) or (6, 12, 24))


def repair(reference_path, input_path, output_dir, config=None, overwrite=False):
    """Repair CSV gaps using a disjoint earlier reference and write three artifacts.

    Ineligible gaps remain missing. All predictions use the original query;
    reconstructed values never become context for another reconstructed gap.
    Returned JSON contains no hidden ground truth or assumed accuracy figures.
    """
    from .report import render_report

    started = time.perf_counter()
    config = (config or RepairConfig()).validate()
    reference_path, input_path, output_dir = map(Path, (reference_path, input_path, output_dir))
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Output path is not a directory: {output_dir}")
    if output_dir.exists() and not overwrite:
        raise ValueError(f"Output directory already exists: {output_dir}. Choose another path or use --overwrite.")
    for name in ("repaired.csv", "report.json", "report.html"):
        if (output_dir / name).resolve() in {reference_path.resolve(), input_path.resolve()}:
            raise ValueError("Output artifacts must not overwrite input or reference files")
    reference, query = read_series(reference_path), read_series(input_path)
    cadence = reference.timestamp.iloc[1] - reference.timestamp.iloc[0]
    if query.timestamp.iloc[1] - query.timestamp.iloc[0] != cadence:
        raise ValueError("Reference and input must have the same sampling cadence")
    if query.timestamp.iloc[0] <= reference.timestamp.iloc[-1]:
        raise ValueError("Input timestamps must be strictly after the entire reference history; overlapping history risks leakage")
    # A phase mismatch is an incompatible sampling grid, even with equal deltas.
    if (query.timestamp.iloc[0] - reference.timestamp.iloc[0]) % cadence != pd.Timedelta(0):
        raise ValueError("Reference and input must lie on the same timestamp grid")
    split = int(len(reference) * (1 - config.calibration_fraction))
    if split < 2 * config.context + 1 or len(reference) - split < 2 * config.context + 1:
        raise ValueError("Reference is too short for separate training and calibration; provide more earlier observations")
    train, calibration = reference.iloc[:split], reference.iloc[split:]
    original = query.value.to_numpy(copy=True)
    gaps = find_gaps(original)
    if len(gaps) > 200:
        raise ValueError("At most 200 gaps per repair run are supported; split the input into smaller files")
    lengths = sorted({e - s for s, e in gaps if e - s <= config.max_gap})
    if len(lengths) > 32:
        raise ValueError("At most 32 distinct supported gap lengths per run are allowed; split the input")
    model = _model(config, lengths).fit(train.value.to_numpy(), pd.DatetimeIndex(train.timestamp))
    cal_values = calibration.value.to_numpy()
    cal_times = pd.DatetimeIndex(calibration.timestamp)
    query_times = pd.DatetimeIndex(query.timestamp)
    cache = {}
    repaired = original.copy()
    lower = np.full(len(query), np.nan)
    upper = np.full(len(query), np.nan)
    statuses = np.where(np.isfinite(original), "observed", "unresolved").astype(object)
    gap_ids = np.full(len(query), -1, dtype=int)
    records = []
    warnings = [
        "Offline reconstruction uses observations on both sides of each gap; it is not a forecasting or live alerting method.",
        "Bands target simultaneous coverage of an entire gap. Dependence and distribution shift mean nominal coverage is not guaranteed.",
        "Reconstructed values are estimates, not observations. Review them before downstream decisions; no physical bounds are imposed.",
    ]
    for gap_id, (start, end) in enumerate(gaps, start=1):
        length = end - start
        gap_ids[start:end] = gap_id
        record = {
            "id": gap_id, "start_index": start, "end_index_exclusive": end,
            "start_time": _time(query_times[start]), "end_time": _time(query_times[end - 1]),
            "length": length, "status": "unresolved", "reason": None,
            "mean": [], "lower": [], "upper": [], "neighbors": [],
            "nearest_context_distance": None, "calibration_count": 0, "quantile": None,
        }
        reason = None
        if length > config.max_gap:
            reason = f"Gap has {length} samples, exceeding max_gap={config.max_gap}"
        elif start < config.context or end + config.context > len(query):
            reason = f"Gap needs {config.context} observed samples on both sides; boundary context is unavailable"
        elif not np.isfinite(np.r_[original[start-config.context:start], original[end:end+config.context]]).all():
            reason = "Context contains another gap; estimates are never reused as observations"
        if reason is None:
            if length not in cache:
                windows = sample_gaps(cal_values, length, config.context, config.calibration_gaps, config.seed + length)
                scores = []
                try:
                    for a, b in windows:
                        masked = cal_values.copy()
                        masked[a:b] = np.nan
                        prediction = model.predict(masked, a, b, cal_times)
                        scores.append(gap_score(cal_values[a:b], prediction.mean, prediction.scale))
                    quantile = conformal_quantile(scores, config.alpha)
                    cache[length] = {"count": len(scores), "quantile": quantile, "error": None}
                except ValueError as exc:
                    cache[length] = {"count": len(scores), "quantile": None, "error": str(exc)}
            calibration_info = cache[length]
            record["calibration_count"] = calibration_info["count"]
            record["quantile"] = calibration_info["quantile"]
            if calibration_info["error"]:
                reason = "Insufficient usable calibration/reference support: " + calibration_info["error"]
        if reason is None:
            try:
                prediction = model.predict(original, start, end, query_times)
                radius = record["quantile"] * prediction.scale
                lo, hi = prediction.mean - radius, prediction.mean + radius
                if not all(np.isfinite(a).all() for a in (prediction.mean, lo, hi)):
                    raise ValueError("Nonfinite output: input magnitude or model scale is unsupported")
                repaired[start:end], lower[start:end], upper[start:end] = prediction.mean, lo, hi
                statuses[start:end] = "reconstructed"
                record.update(
                    status="reconstructed", mean=prediction.mean.tolist(), lower=lo.tolist(), upper=hi.tolist(),
                    nearest_context_distance=float(prediction.distance),
                    neighbors=[{"reference_index": int(i), "start_time": _time(train.timestamp.iloc[i]),
                                "end_time": _time(train.timestamp.iloc[i + length - 1])} for i in prediction.neighbors],
                )
                if prediction.neighbors and prediction.distance > 3:
                    record["warning"] = "Observed context differs strongly from historical analogs; inspect this reconstruction carefully"
            except ValueError as exc:
                reason = str(exc)
        record["reason"] = reason
        records.append(record)
    # This invariant is part of the product contract, not a statistical property.
    observed = np.isfinite(original)
    if not np.array_equal(original[observed], repaired[observed]):
        raise RuntimeError("Observed-value preservation invariant failed")
    frame = pd.DataFrame({"timestamp": query.timestamp, "original_value": original, "value": repaired,
                          "lower": lower, "upper": upper, "status": statuses,
                          "gap_id": [int(i) if i >= 0 else None for i in gap_ids]})
    report = {
        "schema_version": "1.0", "product": "GapLens", "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config), "target_gap_coverage": 1 - config.alpha,
        "reference": {"name": reference_path.name, "sha256": _hash(reference_path), "rows": len(reference),
                      "training_rows": split, "calibration_rows": len(reference) - split,
                      "start": _time(reference.timestamp.iloc[0]), "training_end": _time(train.timestamp.iloc[-1]),
                      "calibration_start": _time(calibration.timestamp.iloc[0]), "end": _time(reference.timestamp.iloc[-1])},
        "input": {"name": input_path.name, "sha256": _hash(input_path), "rows": len(query),
                  "start": _time(query_times[0]), "end": _time(query_times[-1]),
                  "cadence_seconds": cadence.total_seconds()},
        "summary": {"gaps": len(gaps), "reconstructed_gaps": sum(g["status"] == "reconstructed" for g in records),
                    "unresolved_gaps": sum(g["status"] == "unresolved" for g in records),
                    "missing_samples": int(np.isnan(original).sum()),
                    "reconstructed_samples": int((statuses == "reconstructed").sum()),
                    "unchanged_observations": int(observed.sum())},
        "gaps": records, "warnings": warnings,
        "runtime_seconds": time.perf_counter() - started,
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "packages": {n: version(n) for n in ("gaplens", "numpy", "pandas", "scikit-learn")}},
        "artifacts": {"csv": "repaired.csv", "json": "report.json", "html": "report.html"},
    }
    json_text = json.dumps(report, indent=2, allow_nan=False)
    html_text = render_report(report, frame)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    # Stage all content first; overwrite only the three documented artifacts.
    with tempfile.TemporaryDirectory(prefix=".gaplens-", dir=output_dir.parent) as stage:
        stage = Path(stage)
        frame.to_csv(stage / "repaired.csv", index=False)
        (stage / "report.json").write_text(json_text + "\n", encoding="utf-8")
        (stage / "report.html").write_text(html_text, encoding="utf-8")
        output_dir.mkdir(parents=True, exist_ok=True)
        for name in ("repaired.csv", "report.json", "report.html"):
            (stage / name).replace(output_dir / name)
    return report
