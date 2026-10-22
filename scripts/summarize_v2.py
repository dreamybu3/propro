#!/usr/bin/env python3
"""Generate v2 tables and figures from saved measurements, never fit a model.

Primary effects average case MAE within each series on paired common cases,
then give each series equal weight on the log-ratio scale. Uncertainty and
service denominators are kept separate. Group bootstrap intervals are
exploratory: repeated masks and correlated channels are not independent data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_REGIMES = ("mcar_short", "mcar_long", "mar", "mnar")
STATIC_METHODS = ("linear_static", "extra_trees_static", "raw_knn_static", "seasonal_static",
                  "kalman_static", "pca_static", "v1_static", "diverse_static", "diverse_k12_static")
METRICS = ("mae", "mse", "normalized_mae", "gap_coverage", "point_coverage",
           "mean_width", "normalized_width", "point_interval_score",
           "normalized_point_interval_score")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native(value):
    """JSON has no NaN; unsupported statistics are explicit nulls."""
    if isinstance(value, dict):
        return {str(key): native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [native(item) for item in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(native(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
                          encoding="utf-8")


def _bool(values):
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    mapped = values.map({True: True, False: False, "True": True, "False": False,
                         "true": True, "false": False, 1: True, 0: False})
    if (values.notna() & mapped.isna()).any():
        raise ValueError("Invalid boolean service flag")
    return mapped.astype("boolean").fillna(False).astype(bool)


def validate_cases(frame):
    required = {"case_id", "dataset", "source_group", "method", "regime", "gap_length",
                "point_available", "serviced", "mae", "mse", "normalization_scale"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing case columns: {sorted(required-set(frame.columns))}")
    if frame.duplicated(["case_id", "method"]).any():
        raise ValueError("Duplicate case/method rows")
    frame = frame.copy()
    for name in ("point_available", "serviced"):
        frame[name] = _bool(frame[name])
    if ((frame.gap_length <= 0) | (frame.normalization_scale <= 0)).any():
        raise ValueError("Lengths and normalization scales must be positive")
    if (frame.serviced & ~frame.point_available).any():
        raise ValueError("An interval cannot be serviced without a point prediction")
    for metric in METRICS:
        if metric not in frame:
            frame[metric] = np.nan
    for name in ("mae", "mse", "normalized_mae"):
        if not np.isfinite(frame.loc[frame.point_available, name]).all():
            raise ValueError(f"Point-available rows have invalid {name}")
    for name in ("gap_coverage", "point_coverage", "mean_width", "normalized_width"):
        if not np.isfinite(frame.loc[frame.serviced, name]).all():
            raise ValueError(f"Serviced rows have invalid {name}")
    methods = sorted(frame.method.unique())
    if not frame.groupby("case_id").method.nunique().eq(len(methods)).all():
        raise ValueError("Each planned case must retain every method, including refusals")
    return frame


def aggregate(frame, keys):
    """Case-weighted MAE/width, point-weighted point coverage, explicit service."""
    rows = []
    for key, group in frame.groupby(keys, sort=True, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, key))
        point = group[group.point_available]
        interval = group[group.serviced]
        planned_samples = int(group.gap_length.sum())
        row.update(planned_cases=len(group), point_cases=len(point), interval_cases=len(interval),
                   point_refusals=len(group)-len(point), interval_refusals=len(group)-len(interval),
                   planned_samples=planned_samples, predicted_samples=int(point.gap_length.sum()),
                   interval_samples=int(interval.gap_length.sum()),
                   point_service_fraction=len(point)/len(group),
                   interval_service_fraction=len(interval)/len(group),
                   predicted_sample_fraction=float(point.gap_length.sum()/planned_samples),
                   interval_sample_fraction=float(interval.gap_length.sum()/planned_samples))
        for name in ("mae", "mse", "normalized_mae"):
            row[name] = float(point[name].mean()) if len(point) else np.nan
        row["rmse"] = float(np.sqrt(row["mse"]))
        row["point_mae"] = float(np.average(point.mae, weights=point.gap_length)) if len(point) else np.nan
        row["point_rmse"] = float(np.sqrt(np.average(point.mse, weights=point.gap_length))) if len(point) else np.nan
        for name in ("gap_coverage", "mean_width", "normalized_width", "point_interval_score",
                     "normalized_point_interval_score"):
            row[name] = float(interval[name].mean()) if len(interval) else np.nan
        row["point_coverage"] = (float(np.average(interval.point_coverage, weights=interval.gap_length))
                                 if len(interval) else np.nan)
        row["accepted_and_covered_cases"] = int(interval.gap_coverage.sum())
        row["accepted_and_covered_fraction"] = float(interval.gap_coverage.sum()/len(group))
        row["accepted_and_covered_sample_fraction"] = float(
            (interval.point_coverage*interval.gap_length).sum()/planned_samples)
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=list(keys)+[
            "planned_cases", "point_cases", "interval_cases", "point_refusals", "interval_refusals",
            "planned_samples", "predicted_samples", "interval_samples", "point_service_fraction",
            "interval_service_fraction", "predicted_sample_fraction", "interval_sample_fraction",
            *METRICS, "rmse", "point_mae", "point_rmse", "accepted_and_covered_cases",
            "accepted_and_covered_fraction", "accepted_and_covered_sample_fraction"])
    return pd.DataFrame(rows)


def ratio(numerator, denominator):
    if denominator == 0:
        return 1.0 if numerator == 0 else np.nan
    return float(numerator/denominator)


def geometric_mean(values):
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all() or (values < 0).any():
        return np.nan
    if (values == 0).any():
        return 0.0
    return float(np.exp(np.log(values).mean()))


def cluster_bootstrap(series, draws=5000, seed=2026, group_column="source_group"):
    """Resample whole groups, retaining all series within each selected group."""
    if not len(series) or not np.isfinite(series.mae_ratio).all():
        return {"groups": int(series[group_column].nunique()), "draws": draws,
                "lower": None, "upper": None, "reason": "Undefined ratio or no common cases"}
    grouped = [group.mae_ratio.to_numpy() for _, group in series.groupby(group_column, sort=True)]
    rng = np.random.default_rng(seed)
    effects = np.empty(draws)
    for index in range(draws):
        chosen = rng.integers(0, len(grouped), size=len(grouped))
        effects[index] = geometric_mean(np.concatenate([grouped[item] for item in chosen]))
    lo, hi = np.quantile(effects, [.025, .975])
    return {"groups": len(grouped), "draws": draws, "seed": seed,
            "lower": float(lo), "upper": float(hi),
            "interpretation": "Exploratory 95% whole-group percentile interval; few groups, not IID masks/points"}


def paired_effect(frame, candidate, reference, draws=5000, seed=2026):
    """Raw per-series error ratios use exactly the same jointly predicted gaps."""
    chosen = frame[frame.method.isin([candidate, reference])]
    rows = []
    for dataset, group in chosen.groupby("dataset", sort=True):
        a = group[group.method == candidate].set_index("case_id")
        b = group[group.method == reference].set_index("case_id")
        common = a.index.intersection(b.index)
        common = common[a.loc[common].point_available.to_numpy() & b.loc[common].point_available.to_numpy()]
        amean = float(a.loc[common].mae.mean()) if len(common) else np.nan
        bmean = float(b.loc[common].mae.mean()) if len(common) else np.nan
        value = ratio(amean, bmean) if len(common) else np.nan
        rows.append({"dataset": dataset, "source_group": group.source_group.iloc[0],
                     **({"collection": group.collection.iloc[0]} if "collection" in group else {}),
                     "candidate": candidate, "reference": reference,
                     "planned_cases": int(max(len(a), len(b))), "common_cases": len(common),
                     "candidate_point_cases": int(a.point_available.sum()),
                     "reference_point_cases": int(b.point_available.sum()),
                     "candidate_mae": amean, "reference_mae": bmean, "mae_ratio": value,
                     "reason": ("no_common_predictions" if not len(common) else
                                "positive_error_against_zero_reference_error" if not np.isfinite(value) else None)})
    series = pd.DataFrame(rows)
    valid = series[np.isfinite(series.mae_ratio)] if len(series) else series
    values = valid.mae_ratio.to_numpy() if len(valid) else np.array([])
    effect = {"candidate": candidate, "reference": reference,
              "series": len(series), "supported_series": len(valid),
              "common_cases": int(series.common_cases.sum()) if len(series) else 0,
              "geometric_mean_mae_ratio": geometric_mean(values),
              "arithmetic_mean_mae_ratio": float(values.mean()) if len(values) else None,
              "median_mae_ratio": float(np.median(values)) if len(values) else None,
              "series_won": int((values < 1-1e-12).sum()),
              "series_lost": int((values > 1+1e-12).sum()),
              "series_tied": int((np.abs(values-1) <= 1e-12).sum()),
              "all_series_supported": len(valid) == len(series) and len(series) > 0,
              "bootstrap": cluster_bootstrap(valid, draws, seed) if len(valid) else None}
    if "collection" in valid:
        effect["collection_bootstrap_sensitivity"] = cluster_bootstrap(valid, draws, seed, "collection")
    loo = []
    for dataset in valid.dataset:
        remaining = valid[valid.dataset != dataset]
        loo.append({"candidate": candidate, "reference": reference, "omitted_dataset": dataset,
                    "remaining_series": len(remaining),
                    "geometric_mean_mae_ratio": geometric_mean(remaining.mae_ratio)})
    return effect, series, pd.DataFrame(loo)


def rank_methods(frame, methods=STATIC_METHODS):
    rows = []
    methods = [method for method in methods if method in frame.method.unique()]
    for dataset, group in frame.groupby("dataset", sort=True):
        matrix = group[group.method.isin(methods)].pivot(index="case_id", columns="method", values="mae")
        available = group[group.method.isin(methods)].pivot(index="case_id", columns="method", values="point_available")
        complete = matrix[available.reindex(columns=methods).fillna(False).all(axis=1)]
        means = complete.reindex(columns=methods).mean()
        ranks = means.rank(method="average")
        for method in methods:
            rows.append({"dataset": dataset, "method": method, "common_cases": len(complete),
                         "mae": means[method], "rank": ranks[method]})
    return pd.DataFrame(rows)


def uncertainty_comparison(frame, model, target=.9):
    static, recent = f"{model}_static", f"{model}_rolling"
    rows = []
    for dataset, group in frame[frame.method.isin([static, recent])].groupby("dataset", sort=True):
        a, b = (group[group.method == method].set_index("case_id") for method in (static, recent))
        common = a.index.intersection(b.index)
        common = common[a.loc[common].serviced.to_numpy() & b.loc[common].serviced.to_numpy()]
        row = {"dataset": dataset, "model": model, "planned_cases": max(len(a), len(b)),
               "common_interval_cases": len(common), "static_interval_cases": int(a.serviced.sum()),
               "rolling_interval_cases": int(b.serviced.sum())}
        for label, source in (("static", a), ("rolling", b)):
            selected = source.loc[common]
            row[f"{label}_gap_coverage"] = selected.gap_coverage.mean()
            row[f"{label}_normalized_width"] = selected.normalized_width.mean()
            row[f"{label}_point_coverage"] = (float(np.average(selected.point_coverage, weights=selected.gap_length))
                                               if len(selected) else np.nan)
        rows.append(row)
    series = pd.DataFrame(rows)
    valid = series[series.common_interval_cases > 0]
    summary = {"model": model, "target": target, "series": len(series), "supported_series": len(valid),
               "planned_cases": int(series.planned_cases.sum()),
               "common_interval_cases": int(series.common_interval_cases.sum()),
               "static_interval_cases": int(series.static_interval_cases.sum()),
               "rolling_interval_cases": int(series.rolling_interval_cases.sum())}
    for label in ("static", "rolling"):
        coverage = float(valid[f"{label}_gap_coverage"].mean())
        summary[f"{label}_gap_coverage"] = coverage
        summary[f"{label}_normalized_width"] = float(valid[f"{label}_normalized_width"].mean())
        summary[f"{label}_absolute_coverage_error"] = abs(coverage-target)
        summary[f"{label}_mean_series_absolute_coverage_error"] = float(
            np.abs(valid[f"{label}_gap_coverage"]-target).mean())
    summary["normalized_width_ratio"] = ratio(summary["rolling_normalized_width"], summary["static_normalized_width"])
    summary["coverage_closer"] = bool(summary["rolling_absolute_coverage_error"] < summary["static_absolute_coverage_error"]-1e-12)
    summary["width_within_10_percent"] = bool(summary["normalized_width_ratio"] <= 1.1)
    summary["h2_met_on_common_cases"] = bool(len(valid) and summary["coverage_closer"] and summary["width_within_10_percent"])
    summary["all_series_supported"] = len(valid) == len(series) and len(series) > 0
    return summary, series


def check_calibration_ablation(cases, predictions):
    evidence = {}
    for model in ("v1", "diverse"):
        methods = [f"{model}_static", f"{model}_rolling"]
        if not set(methods).issubset(cases.method.unique()):
            continue
        a, b = (cases[cases.method == name].set_index("case_id").sort_index() for name in methods)
        if not a.index.equals(b.index) or not np.array_equal(a.point_available, b.point_available):
            raise ValueError(f"{model} calibration modes have different point availability")
        keys = ["case_id", "offset"]
        first, second = (predictions[predictions.method == name].set_index(keys).sort_index() for name in methods)
        if first.index.has_duplicates or second.index.has_duplicates or not first.index.equals(second.index):
            raise ValueError(f"{model} calibration modes have different prediction indices")
        columns = ["truth", "prediction", "relative_scale"]
        if not np.array_equal(first[columns].to_numpy(), second[columns].to_numpy()):
            raise ValueError(f"{model} calibration changed point predictions or scales")
        evidence[model] = {"identical_point_predictions_and_scales": True, "point_rows": len(first),
                           "planned_cases": len(a)}
    return evidence


def curve_tables(cases, curves, alphas):
    """Include absent prediction rows as unsupported; fixed common set for plot."""
    base = cases[cases.regime.isin(PRIMARY_REGIMES)][[
        "case_id", "dataset", "method", "regime", "gap_length", "source_group"]]
    grid = base.merge(pd.DataFrame({"alpha": alphas}), how="cross")
    keys = ["case_id", "method", "alpha"]
    if curves.duplicated(keys).any():
        raise ValueError("Duplicate coverage-width rows")
    measures = [name for name in METRICS if name in curves]
    merged = grid.merge(curves[keys+["serviced"]+measures], on=keys, how="left", validate="one_to_one")
    merged["serviced"] = _bool(merged.serviced)
    merged["point_available"] = merged.serviced
    for name in METRICS:
        if name not in merged:
            merged[name] = np.nan
    own = aggregate(merged, ["dataset", "method", "alpha"])
    expected = len(base.method.unique())*len(alphas)
    support = merged.groupby("case_id").serviced.agg(["size", "sum"])
    common_ids = support.index[(support["size"] == expected) & (support["sum"] == expected)]
    common = aggregate(merged[merged.case_id.isin(common_ids)], ["dataset", "method", "alpha"])
    return own, common, {"common_cases_across_all_methods_and_alphas": len(common_ids),
                         "common_series": int(merged[merged.case_id.isin(common_ids)].dataset.nunique()),
                         "planned_cases": int(base.case_id.nunique()),
                         "methods": int(base.method.nunique()), "alphas": alphas,
                         "note": "Common curve set excludes every case unsupported by any plotted method/alpha; own-service table retains full denominators."}


def timing_table(performance, cases):
    parts = [performance.copy()]
    warm = cases.copy()
    warm["model"] = warm.method.str.rsplit("_", n=1).str[0]
    warm = warm.drop_duplicates(["case_id", "model"])
    warm = warm[np.isfinite(warm.prediction_seconds)]
    warm["stage"], warm["seconds"] = "warm_prediction", warm.prediction_seconds
    parts.append(warm)
    combined = pd.concat(parts, ignore_index=True)
    rows = []
    for (model, stage, history), group in combined.groupby(["model", "stage", "history"], sort=True):
        finite = group.seconds[np.isfinite(group.seconds)]
        rows.append({"model": model, "stage": stage, "history": history,
                     "measurements": len(finite), "total_seconds": finite.sum(),
                     "mean_seconds": finite.mean(), "median_seconds": finite.median(),
                     "min_seconds": finite.min(), "max_seconds": finite.max()})
    return pd.DataFrame(rows)


def context_diagnostics(cases):
    """Fixed context-only proxy bins; descriptive, never predictor routing."""
    parts = []
    for column, threshold, absolute in [
        ("context_shift", 2., True), ("context_spread_ratio", 2., False),
        ("context_endpoint_change", 1., True),
    ]:
        part = cases.copy()
        values = part[column] if column in part else pd.Series(np.nan, index=part.index)
        extreme = values.abs() > threshold if absolute else values > threshold
        part["diagnostic"] = column
        part["context_bin"] = np.where(values.isna(), "unavailable", np.where(extreme, "above_threshold", "within_threshold"))
        parts.append(part)
    result = aggregate(pd.concat(parts, ignore_index=True), ["dataset", "regime", "diagnostic", "context_bin", "method"])
    return result


def markdown_table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"]*len(headers)) + " |"] +
                     ["| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows])


def formatted(value, digits=3):
    return "unsupported" if value is None or not np.isfinite(value) else f"{value:.{digits}f}"


def render_tables(summary, series, ranks, uncertainty):
    lines = ["<!-- Generated by scripts/summarize_v2.py from saved measurements. -->", "",
             "Primary regimes: MCAR short, MCAR long, MAR, MNAR. Each paired effect uses identical jointly predicted gaps within a series; series receive equal weight. Ratios below 1 favor the candidate. Whole-group bootstrap intervals are exploratory, with few provider/domain groups. Refusals remain in service denominators.", "",
             markdown_table(["Candidate", "Reference", "Common gaps", "Series", "Geometric MAE ratio", "Median ratio", "Wins/losses", "Exploratory group 95% interval"], [
                 [item["candidate"], item["reference"], item["common_cases"], f"{item['supported_series']}/{item['series']}",
                  formatted(item["geometric_mean_mae_ratio"]), formatted(item["median_mae_ratio"]),
                  f"{item['series_won']}/{item['series_lost']}",
                  f"{formatted((item['bootstrap'] or {}).get('lower'))}–{formatted((item['bootstrap'] or {}).get('upper'))}"]
                 for item in summary["paired_effects"]]), "",
             "Raw errors and service (primary regimes; source units differ between series):", "",
             markdown_table(["Series", "Method", "MAE", "RMSE", "Gap coverage", "Point coverage", "Mean width", "Point service", "Interval service", "Accepted and covered / planned"], [
                 [row.dataset, row.method, formatted(row.mae), formatted(row.rmse), formatted(row.gap_coverage),
                  formatted(row.point_coverage), formatted(row.mean_width), f"{row.point_cases}/{row.planned_cases}",
                  f"{row.interval_cases}/{row.planned_cases}", formatted(row.accepted_and_covered_fraction)] for row in series.itertuples()]), "",
             "Ranks use the intersection of finite predictions across all static methods:", "",
             markdown_table(["Method", "Mean rank", "Median rank", "Series with common cases"], [
                 [method, formatted(group["rank"].mean()), formatted(group["rank"].median()), int(group["rank"].notna().sum())]
                 for method, group in ranks.groupby("method", sort=True)]), "",
             "Static/recent comparison uses identical jointly interval-serviced cases and equal series weights:", "",
             markdown_table(["Predictor", "Common gaps", "Static gap coverage", "Recent gap coverage", "Width ratio recent/static", "H2 effect criterion"], [
                 [item["model"], item["common_interval_cases"], formatted(item["static_gap_coverage"]),
                  formatted(item["rolling_gap_coverage"]), formatted(item["normalized_width_ratio"]),
                  item["h2_met_on_common_cases"]] for item in uncertainty]), "",
             "Point estimates without sufficient calibration are research point-only outputs, not serviced product reconstructions. Per-regime, per-length, per-origin, refusal, calibration and performance tables are separate CSV files. Normalized widths are secondary scale-adjusted descriptions, not physical-unit averages.", ""]
    return "\n".join(lines)


def make_figures(output, paired_series, curves_common, regimes, predictions, cases, candidate):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"svg.hashsalt": "gaplens-v2", "font.size": 9})
    output.mkdir(parents=True, exist_ok=True)

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(output/f"{name}.png", dpi=160, metadata={"Software": "GapLens v2"})
        fig.savefig(output/f"{name}.svg", metadata={"Date": None})
        plt.close(fig)

    chosen = paired_series[(paired_series.candidate == "diverse_static") &
                           (paired_series.reference == "v1_static")].sort_values("dataset")
    if len(chosen):
        fig, ax = plt.subplots(figsize=(8, max(4, len(chosen)*.3)))
        positions = np.arange(len(chosen))
        ax.barh(positions, chosen.mae_ratio, color=np.where(chosen.mae_ratio <= 1, "#16806a", "#c45b4a"))
        ax.axvline(1, color="#333333", linewidth=1)
        ax.set(yticks=positions, yticklabels=chosen.dataset, xlabel="Paired per-series MAE ratio: diverse / v1",
               title="Primary regimes; identical cases within each pair")
        save(fig, "paired_series_ratios")
    if len(curves_common):
        fig, ax = plt.subplots(figsize=(8, 5))
        for method, group in curves_common.groupby("method", sort=True):
            macro = group.groupby("alpha", sort=True).agg(gap_coverage=("gap_coverage", "mean"),
                                                           normalized_width=("normalized_width", "mean"))
            ax.plot(macro.gap_coverage, macro.normalized_width, marker="o", label=method)
            for alpha, row in macro.iterrows():
                ax.annotate(f"{alpha:g}", (row.gap_coverage, row.normalized_width), fontsize=6)
        ax.axvline(.9, color="gray", linestyle="--", linewidth=1)
        count = int(curves_common.groupby(["method", "alpha"]).interval_cases.sum().iloc[0])
        ax.set(xlabel="Empirical whole-gap coverage (equal-series mean)", ylabel="Mean width / training scale",
               title=f"Coverage–width curves on {count} common gaps; alpha labels")
        ax.legend(fontsize=6, ncol=2)
        save(fig, "coverage_width_common")
    heat = regimes.groupby(["regime", "method"]).interval_service_fraction.mean().unstack("method")
    if len(heat):
        fig, ax = plt.subplots(figsize=(10, 6))
        image = ax.imshow(heat.to_numpy(), vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
        ax.set(xticks=np.arange(len(heat.columns)), xticklabels=heat.columns,
               yticks=np.arange(len(heat.index)), yticklabels=heat.index,
               title="Interval service fraction; equal weight per series")
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        for i in range(len(heat)):
            for j in range(len(heat.columns)):
                ax.text(j, i, f"{heat.iloc[i,j]:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if heat.iloc[i,j] > .6 else "black")
        fig.colorbar(image, ax=ax, label="Serviced / planned gaps")
        save(fig, "service_by_regime")
    eligible = cases[(cases.method == candidate) & cases.regime.isin(PRIMARY_REGIMES) & cases.point_available]
    selection = None
    if len(eligible):
        worst = eligible.sort_values(["normalized_mae", "case_id"], ascending=[False, True]).iloc[0]
        selected = predictions[(predictions.case_id == worst.case_id) & (predictions.method == candidate)].sort_values("offset")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(selected.offset, selected.truth, "o-", label="Hidden measured truth (evaluation only)")
        ax.plot(selected.offset, selected.prediction, "o-", label=candidate)
        if np.isfinite(selected.lower).all():
            ax.fill_between(selected.offset, selected.lower, selected.upper, alpha=.2, label="Whole-gap calibrated band")
        ax.set(xlabel="Offset within hidden gap", ylabel="Value in source units",
               title=f"Saved failure diagnostic: {worst.dataset}, {worst.regime}\nMAE / training scale = {worst.normalized_mae:.3g}")
        ax.legend(fontsize=8)
        save(fig, "failure_example")
        selection = {"case_id": worst.case_id, "method": candidate, "dataset": worst.dataset,
                     "normalized_mae": float(worst.normalized_mae), "mae": float(worst.mae),
                     "interval_serviced": bool(worst.serviced),
                     "rule": "Highest normalized MAE among frozen product candidate primary-regime point predictions; ties by case_id. Diagnostic, not an aggregate result."}
    return selection


def generate(input_dir, output_dir, *, selection_path=None, draws=5000, seed=2026, figures=True):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    run = json.loads((input_dir/"run.json").read_text(encoding="utf-8"))
    if run.get("status") != "complete" or run.get("is_smoke_run", True):
        raise ValueError("A complete frozen final run is required; smoke/partial runs are not final evidence")
    for name, digest in run.get("artifact_sha256", {}).items():
        if sha256(input_dir/name) != digest:
            raise ValueError(f"Saved measurement checksum mismatch: {name}")
    selection_path = Path(selection_path) if selection_path else ROOT/run["config"]["selection"]
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if run.get("selection_sha256") and sha256(selection_path) != run["selection_sha256"]:
        raise ValueError("Development selection differs from the one used by the run")
    config_primary = run["config"].get("hypothesis", {}).get("primary_regimes", list(PRIMARY_REGIMES))
    if tuple(config_primary) != PRIMARY_REGIMES:
        raise ValueError("Saved config primary regimes differ from this predeclared summary")
    cases = validate_cases(pd.read_csv(input_dir/"case_metrics.csv", float_precision="round_trip"))
    manifest_path = ROOT/run["config"].get("manifest", "data/v2/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    if manifest:
        collections = {item["id"]: item["collection"] for item in manifest["datasets"]}
        if set(cases.dataset).issubset(collections):
            cases["collection"] = cases.dataset.map(collections)
    predictions = pd.read_csv(input_dir/"predictions.csv.gz", float_precision="round_trip")
    curves = pd.read_csv(input_dir/"coverage_width.csv", float_precision="round_trip")
    performance = pd.read_csv(input_dir/"performance.csv", float_precision="round_trip")
    calibration = pd.read_csv(input_dir/"calibration_scores.csv", float_precision="round_trip")
    ablations = check_calibration_ablation(cases, predictions)
    primary = cases[cases.regime.isin(PRIMARY_REGIMES)]
    effects, paired, leaveouts = [], [], []
    pairs = [("diverse_static", "v1_static")]
    if "diverse_k12_static" in primary.method.unique():
        pairs.append(("diverse_k12_static", "v1_static"))
    for candidate in ("diverse_static", "v1_static"):
        pairs += [(candidate, reference) for reference in STATIC_METHODS
                  if reference not in {"diverse_static", "v1_static"} and reference in primary.method.unique()]
    for candidate, reference in pairs:
        effect, per_series, loo = paired_effect(primary, candidate, reference, draws, seed)
        effects.append(effect)
        paired.append(per_series)
        leaveouts.append(loo)
    paired, leaveouts = pd.concat(paired, ignore_index=True), pd.concat(leaveouts, ignore_index=True)
    ranks = rank_methods(primary)
    uncertainty, uncertainty_series = [], []
    for model in ("v1", "diverse"):
        effect, by_series = uncertainty_comparison(primary, model)
        uncertainty.append(effect)
        uncertainty_series.append(by_series)
    own_curve, common_curve, curve_support = curve_tables(cases, curves, run["config"]["curve_alphas"])
    series = aggregate(primary, ["dataset", "method"])
    regimes = aggregate(cases, ["dataset", "regime", "method"])
    source_groups = primary[["dataset", "source_group"]].drop_duplicates()
    non_retrieval = ["linear", "extra_trees", "seasonal", "kalman", "pca"]
    best = selection.get("best_non_retrieval_competitor") or min(non_retrieval, key=lambda name: selection["selected_objectives"][name])
    if not best.endswith("_static"):
        best += "_static"
    v1_effect = next(item for item in effects if item["candidate"] == "diverse_static" and item["reference"] == "v1_static")
    competitor_effect = next(item for item in effects if item["candidate"] == "diverse_static" and item["reference"] == best)
    h1_supported = v1_effect["all_series_supported"] and competitor_effect["all_series_supported"]
    h1 = {"candidate": "diverse_static", "best_competitor_selected_on_development": best,
          "geometric_mean_mae_ratio_to_v1": v1_effect["geometric_mean_mae_ratio"],
          "geometric_mean_mae_ratio_to_competitor": competitor_effect["geometric_mean_mae_ratio"],
          "at_least_5_percent_better_than_v1": bool(v1_effect["geometric_mean_mae_ratio"] <= .95),
          "better_than_development_selected_competitor": bool(competitor_effect["geometric_mean_mae_ratio"] < 1),
          "all_series_supported": h1_supported}
    h1["met"] = bool(h1_supported and h1["at_least_5_percent_better_than_v1"] and h1["better_than_development_selected_competitor"])
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {"series_primary.csv": series, "series_all_regimes.csv": aggregate(cases, ["dataset", "method"]),
               "regimes.csv": regimes, "lengths.csv": aggregate(cases, ["dataset", "gap_length", "method"]),
               "origins.csv": aggregate(cases, ["dataset", "origin_index", "method"]),
               "paired_series.csv": paired, "leave_one_series_out.csv": leaveouts,
               "ranks.csv": ranks, "uncertainty_pairs.csv": pd.concat(uncertainty_series, ignore_index=True),
               "curves_own_service.csv": own_curve, "curves_common_service.csv": common_curve,
               "context_diagnostics.csv": context_diagnostics(cases),
               "performance_summary.csv": timing_table(performance, cases)}
    refused = cases[~cases.serviced].copy()
    refused["reason"] = refused.reason.fillna("unspecified")
    outputs["refusals.csv"] = refused.groupby(["dataset", "regime", "method", "reason"], dropna=False).size().reset_index(name="cases")
    outputs["calibration_support.csv"] = calibration.groupby(["dataset", "model", "mode", "history", "length"], dropna=False).agg(
        attempted_scores=("score", "size"), finite_scores=("score", "count"),
        mean_score=("score", "mean"), max_score=("score", "max")).reset_index()
    for name, frame in outputs.items():
        frame.to_csv(output_dir/name, index=False, lineterminator="\n")
    candidate = selection["product_model"] + "_" + selection.get("product_calibration", "static")
    failure = make_figures(output_dir/"figures", paired, common_curve, regimes, predictions, cases, candidate) if figures else None
    sizes = {name: (input_dir/name).stat().st_size for name in ["case_metrics.csv", "predictions.csv.gz", "calibration_scores.csv", "coverage_width.csv", "performance.csv"]}
    data_bytes = None
    if manifest:
        data_bytes = sum((ROOT/item["processed_path"]).stat().st_size for item in manifest["datasets"])
    summary = {"schema_version": 2, "primary_regimes": list(PRIMARY_REGIMES),
               "series": int(primary.dataset.nunique()), "source_groups": int(source_groups.source_group.nunique()),
               "planned_cases_all_regimes": int(cases.case_id.nunique()), "primary_cases": int(primary.case_id.nunique()),
               "source_group_membership": source_groups.to_dict("records"),
               "frozen_product_method": candidate, "h1": h1, "h2": uncertainty,
               "paired_effects": effects, "calibration_ablation_check": ablations,
               "curve_support": curve_support, "failure_example": failure,
               "performance": {"elapsed_seconds": run.get("elapsed_seconds"),
                               "cumulative_process_peak_rss_mb": run.get("process_peak_rss_mb"),
                               "processed_data_bytes": data_bytes, "measurement_artifact_bytes": sizes,
                               "note": "Linux/cloud measurements; process peak RSS is cumulative, not isolated method RSS. Fit/cold/calibration/warm table separates cache construction."},
               "estimands": {"mae": "Mean case MAE within series; per-series ratios use jointly finite predictions.",
                             "point_coverage": "Target-point weighted within a series; macro comparisons weight series equally.",
                             "gap_coverage_width": "Case means within series; uncertainty comparisons weight series equally on jointly interval-serviced gaps.",
                             "zero_errors": "Both paired errors zero gives ratio1; positive candidate error against zero reference is undefined and explicitly excluded, making H1 unsupported.",
                             "bootstrap": "Whole source groups resampled with replacement; all series in each draw retained. Few groups; exploratory intervals.",
                             "point_only": "A finite point prediction with insufficient calibration is not a serviced product reconstruction."}}
    summary["context_diagnostic_rules"] = {
        "context_shift": "abs(context_shift) > 2", "context_spread_ratio": "context_spread_ratio > 2",
        "context_endpoint_change": "abs(context_endpoint_change) > 1",
        "interpretation": "Fixed observed-context proxies, not proven structural breaks. Descriptive only, no routing; regime column keeps synthetic level shift distinct."}
    write_json(output_dir/"summary.json", summary)
    (output_dir/"tables.md").write_text(render_tables(summary, series, ranks, uncertainty), encoding="utf-8")
    provenance = {"script_sha256": sha256(__file__), "input_sha256": {name: sha256(input_dir/name) for name in ["run.json", *sizes]},
                  "selection_sha256": sha256(selection_path), "bootstrap_draws": draws, "bootstrap_seed": seed,
                  "generated_table_sha256": {name: sha256(output_dir/name) for name in sorted(outputs)},
                  "summary_sha256": sha256(output_dir/"summary.json")}
    write_json(output_dir/"summary_provenance.json", provenance)
    return native(summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT/"results/v2/benchmark")
    parser.add_argument("--output", type=Path, default=ROOT/"results/v2/final")
    parser.add_argument("--selection", type=Path)
    args = parser.parse_args(argv)
    result = generate(args.input, args.output, selection_path=args.selection)
    print(f"Generated saved-result tables and figures for {result['series']} series; H1 met={result['h1']['met']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
