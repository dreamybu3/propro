#!/usr/bin/env python3
"""Independently reconcile saved v2 masks and aggregate estimands; never fit models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = {"mcar_short", "mcar_long", "mar", "mnar"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, message):
    if not np.allclose(actual, expected, rtol=1e-12, atol=1e-12, equal_nan=True):
        raise ValueError(message)


def review(benchmark, summary_dir, plan_path):
    benchmark, summary_dir, plan_path = map(Path, (benchmark, summary_dir, plan_path))
    summary = json.loads((summary_dir / "summary.json").read_text())
    run = json.loads((benchmark / "run.json").read_text())
    check(run["status"] == "complete" and not run["is_smoke_run"], "Need a completed final run")
    plan = json.loads(plan_path.read_text())
    cases = pd.read_csv(benchmark / "case_metrics.csv", float_precision="round_trip")
    primary = cases[cases.regime.isin(PRIMARY)]
    manifest = json.loads((ROOT / "data/v2/manifest.json").read_text())
    collections = {item["id"]: item["collection"] for item in manifest["datasets"]}
    source_groups = cases.groupby("dataset").source_group.first()
    methods = sorted(cases.method.unique())
    check(set(methods) == set(run["config"]["methods"]), "A declared method is missing")
    planned = {case["case_id"]: case for case in plan["cases"]}
    check(set(planned) == set(cases.case_id), "Case denominator differs from saved plan")
    check(not cases.duplicated(["case_id", "method"]).any(), "Duplicate case/method")
    check((cases.groupby("case_id").size() == len(methods)).all(), "Missing method or refusal")
    means = primary.pivot(index=["dataset", "case_id"], columns="method", values="mae")
    available = primary.pivot(index=["dataset", "case_id"], columns="method", values="point_available")
    means = means.where(available)
    paired_checks = []
    for effect in summary["paired_effects"]:
        candidate, reference = effect["candidate"], effect["reference"]
        common = means[[candidate, reference]].dropna()
        per_series = common.groupby("dataset").mean()
        ratios = per_series[candidate] / per_series[reference]
        check((ratios > 0).all(), "This audit requires explicit handling of zero-error ratios")
        geometric = float(np.exp(np.log(ratios).mean()))
        close(geometric, effect["geometric_mean_mae_ratio"], "Paired geometric effect differs")
        close(float(ratios.median()), effect["median_mae_ratio"], "Paired median effect differs")
        check(len(common) == effect["common_cases"], "Paired common-case count differs")
        # A vectorized weighted-log implementation independently checks the
        # loop-based whole-group bootstrap in summarize_v2.py.
        for column, reported in [
            (source_groups, effect["bootstrap"]),
            (pd.Series(collections), effect.get("collection_bootstrap_sensitivity")),
        ]:
            if reported is None:
                continue
            grouped = pd.DataFrame({"log_ratio": np.log(ratios), "group": column.loc[ratios.index]})
            sums = grouped.groupby("group", sort=True).log_ratio.agg(["sum", "count"])
            rng = np.random.default_rng(reported["seed"])
            draws = rng.integers(0, len(sums), size=(reported["draws"], len(sums)))
            replicates = np.exp(sums["sum"].to_numpy()[draws].sum(axis=1)
                                / sums["count"].to_numpy()[draws].sum(axis=1))
            close(np.quantile(replicates, [.025, .975]), [reported["lower"], reported["upper"]],
                  "Whole-group bootstrap differs")
        paired_checks.append({"candidate": candidate, "reference": reference,
                              "common_cases": len(common), "geometric_mae_ratio": geometric})
    static = [method for method in methods if method.endswith("_static")]
    common_static = means[static].dropna()
    expected_ranks = common_static.groupby("dataset").mean().rank(axis=1)
    reported_ranks = pd.read_csv(summary_dir / "ranks.csv").pivot(
        index="dataset", columns="method", values="rank")
    close(expected_ranks[reported_ranks.columns], reported_ranks, "Common-case method ranks differ")
    uncertainty = []
    for model in ("v1", "diverse"):
        a = primary[primary.method == model + "_static"].set_index("case_id")
        b = primary[primary.method == model + "_rolling"].set_index("case_id")
        ids = a.index[a.serviced & b.loc[a.index].serviced]
        paired = pd.DataFrame({"dataset": a.loc[ids].dataset,
                               "static_coverage": a.loc[ids].gap_coverage,
                               "rolling_coverage": b.loc[ids].gap_coverage,
                               "static_width": a.loc[ids].normalized_width,
                               "rolling_width": b.loc[ids].normalized_width})
        macro = paired.groupby("dataset").mean().mean()
        reported = next(item for item in summary["h2"] if item["model"] == model)
        close(macro.to_numpy(), [reported["static_gap_coverage"], reported["rolling_gap_coverage"],
                                reported["static_normalized_width"], reported["rolling_normalized_width"]],
              "Common-case uncertainty estimand differs")
        check(len(ids) == reported["common_interval_cases"], "Uncertainty common count differs")
        uncertainty.append({"model": model, "common_interval_cases": len(ids),
                            "static_coverage": float(macro.static_coverage),
                            "rolling_coverage": float(macro.rolling_coverage),
                            "width_ratio": float(macro.rolling_width / macro.static_width)})

    source_values = {}
    for dataset, info in plan["datasets"].items():
        check(source_groups[dataset] == info["source_group"], "Source-group assignment differs from frozen plan")
        path = ROOT / info["path"]
        check(digest(path) == info["sha256"], "Source differs from the frozen mask source")
        source_values[dataset] = pd.read_csv(path, float_precision="round_trip").value.to_numpy()
    prior_masks = {}
    for dataset in plan["datasets"]:
        relevant = [case for case in planned.values() if case["dataset"] == dataset]
        for seed in sorted({case["seed"] for case in relevant}):
            prior = set()
            for origin in sorted({case["origin_index"] for case in relevant}):
                prior_masks[(dataset, seed, origin)] = prior.copy()
                for case in relevant:
                    if case["seed"] == seed and case["origin_index"] == origin and case["regime"] == "simultaneous":
                        prior.update(case["hidden_indices"])
    window_checks = 0
    for cal in plan["calibration"]:
        info = plan["datasets"][cal["dataset"]]
        context = info["context"]
        prior = prior_masks[(cal["dataset"], cal["seed"], cal["origin_index"])]
        expected = sorted(i for i in prior if cal["begin"] <= i < cal["end"])
        check(expected == cal["unavailable_history_indices"], "Prior hidden history differs")
        check(cal["begin"] >= info["fit_end"], "Calibration overlaps model fitting")
        occupied = set()
        for start, end in cal["windows"]:
            window = set(range(start - context, end + context))
            check(min(window) >= cal["begin"] and max(window) < cal["end"], "Context crosses calibration split")
            check(not window & occupied and not window & prior, "Calibration reuses hidden or overlapping truth")
            check(np.isfinite(source_values[cal["dataset"]][sorted(window)]).all(), "Calibration has native missing truth")
            occupied.update(window)
            window_checks += 1
    case_groups = {key: group for key, group in cases.groupby("case_id")}
    for case_id, case in planned.items():
        context = plan["datasets"][case["dataset"]]["context"]
        indices = list(range(case["start"] - context, case["start"])) + list(range(case["end"], case["end"] + context))
        complete = (min(indices) >= case["query_begin"] and max(indices) < case["query_end"]
                    and not set(indices) & set(case["hidden_indices"]))
        if complete:
            complete = bool(np.isfinite(source_values[case["dataset"]][indices]).all())
        if not complete:
            check(not case_groups[case_id].point_available.any(), "Incomplete context silently served")
    for name in ("series_primary.csv", "regimes.csv", "lengths.csv", "origins.csv"):
        table = pd.read_csv(summary_dir / name)
        expected = (table.gap_coverage * table.interval_cases / table.planned_cases).fillna(0)
        close(table.accepted_and_covered_fraction, expected, "Accepted-and-covered denominator differs")
    return {
        "status": "passed", "scope": "Independent saved-artifact audit; no fitting or new holdout scoring",
        "case_method_rows": len(cases), "planned_gaps": len(planned),
        "primary_gaps": int(primary.case_id.nunique()), "primary_point_service_complete": bool(primary.point_available.all()),
        "paired_effects_and_bootstraps_checked": paired_checks, "primary_ranks_match": True,
        "uncertainty_estimands_checked": uncertainty,
        "calibration_strata": len(plan["calibration"]), "calibration_windows_checked": window_checks,
        "prior_outage_and_query_context_checks_passed": True,
        "accepted_covered_denominators_match": True,
        "input_sha256": {
            str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): digest(path)
            for path in [benchmark / "case_metrics.csv", benchmark / "run.json", plan_path,
                         ROOT / "data/v2/manifest.json", *[summary_dir / name for name in (
                             "summary.json", "ranks.csv", "series_primary.csv", "regimes.csv",
                             "lengths.csv", "origins.csv")]]},
        "script_sha256": digest(Path(__file__)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=ROOT / "results/v2/benchmark")
    parser.add_argument("--summary", type=Path, default=ROOT / "results/v2/final")
    parser.add_argument("--plan", type=Path, default=ROOT / "results/v2/masks.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v2/methodology_review.json")
    args = parser.parse_args()
    result = review(args.benchmark.resolve(), args.summary.resolve(), args.plan.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Methodology audit passed: {result['planned_gaps']} gaps, {result['calibration_windows_checked']} calibration windows")
