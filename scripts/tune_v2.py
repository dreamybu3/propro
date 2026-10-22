#!/usr/bin/env python3
"""Fixed-budget tuning using only the three already-inspected v1 series.

No new-series file is read here. All configurations see identical validation
windows. The objective gives each development series one vote through a
geometric mean of raw per-series MAE ratios to the linear control.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runner_v2", ROOT/"scripts/run_experiments_v2.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

DEVELOPMENT = {"nyc_taxi": 48, "cpu_utilization": 288, "ambient_temperature": 24}
GRID = {
    "diverse": [{"k": 4}, {"k": 8}, {"k": 12}],
    "extra_trees": [{"n_estimators": n, "training_gaps": 300} for n in [32, 64, 96]],
    "kalman": [{"process_ratio": r} for r in [.01, .1, 1.]],
    "pca": [{"rank": 2, "ridge": .01}, {"rank": 4, "ridge": .1}, {"rank": 8, "ridge": 1.}],
}
CONTROLS = {name: [{}] for name in ["linear", "v1", "raw_knn", "seasonal"]}


def tune(output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Development output already exists; use another path to preserve trials")
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    meta = {"status": "running", "started_at": runner.utc_now(), "datasets": {},
            "development_only": list(DEVELOPMENT), "context": 6, "lengths": [6, 24],
            "fit_fraction": .4, "validation_ranges": [[.6, .8], [.8, 1.]],
            "mask_seed": 17, "validation_cases_per_length_per_origin": 8,
            "grid": GRID, "controls": CONTROLS,
            "objective": "Geometric mean across three series of mean case MAE / linear mean case MAE; ties choose first grid entry; any missing prediction makes a candidate ineligible.",
            "product_selection": "Use diverse only if its development objective is at most 95% of v1's; otherwise keep v1. Rolling calibration is a separately evaluated uncertainty ablation, never selected on final data.",
            "code_sha256": {str(p.relative_to(ROOT)): runner.sha256(p) for p in [Path(__file__), ROOT/"scripts/run_experiments_v2.py", ROOT/"src/gaplens/core.py", ROOT/"src/gaplens/_core_v1.py", ROOT/"src/gaplens/models_v2.py"]},
            "selection_status": "No final evaluation series used"}
    runner.write_json(output/"run.json", meta)
    rows, masks, fit_rows = [], [], []
    for dataset, period in DEVELOPMENT.items():
        path = ROOT/"data/processed"/f"{dataset}.csv"
        frame = runner.read_series(path)
        values, timestamps = frame.value.to_numpy(), pd.DatetimeIndex(frame.timestamp)
        n, fit_end = len(values), int(.4*len(values))
        scale = runner.training_scale(values[:fit_end])
        meta["datasets"][dataset] = {"sha256": runner.sha256(path), "rows": n, "fit_end": fit_end,
                                      "normalization_scale": scale, "seasonal_period": period}
        cases = []
        for oi, (begin_fraction, end_fraction) in enumerate(meta["validation_ranges"]):
            begin, finish = int(n*begin_fraction), int(n*end_fraction)
            for length in meta["lengths"]:
                seed = runner.stable_seed(dataset, 17, "development", oi, length)
                starts = runner.weighted_starts(values, begin, finish, length, 6, 8, seed)
                for j, start in enumerate(starts):
                    case = runner._case(dataset, 17, oi, "development", j, start, length, begin, finish)
                    case["case_id"] += f"__l{length}"
                    cases.append(case)
        masks.extend(cases)
        for model_name, candidates in {**CONTROLS, **GRID}.items():
            for candidate, parameters in enumerate(candidates):
                tick = time.perf_counter()
                model = runner.make_model(model_name, 6, [6, 24], 17, period, parameters)
                error = None
                try:
                    model.fit(values[:fit_end], timestamps[:fit_end])
                except ValueError as exc:
                    error = str(exc)
                fit_rows.append({"dataset": dataset, "model": model_name, "candidate": candidate,
                                 "seconds": time.perf_counter()-tick, "error": error})
                for case in cases:
                    a, b = case["start"], case["end"]
                    row = {"dataset": dataset, "case_id": case["case_id"], "model": model_name,
                           "candidate": candidate, "length": b-a, "source_start": a,
                           "parameters": json.dumps(parameters, sort_keys=True), "mae": None,
                           "normalized_mae": None, "error": error}
                    if error is None:
                        query = runner.local_query(values, a, b, 6, case["query_begin"], case["query_end"])
                        try:
                            pred = model.predict(query, a, b, timestamps)
                            metric = runner.prediction_metrics(values[a:b], pred.mean, pred.scale, None, scale, .1)
                            row.update(mae=metric["mae"], normalized_mae=metric["normalized_mae"])
                        except ValueError as exc:
                            row["error"] = str(exc)
                    rows.append(row)
                print(f"Development {dataset} {model_name} candidate={candidate}: {len(cases)} cases", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output/"trials.csv", index=False)
    pd.DataFrame(fit_rows).to_csv(output/"fit_times.csv", index=False)
    runner.write_json(output/"masks.json", masks)
    series = frame.groupby(["dataset", "model", "candidate"], sort=True).agg(
        mae=("mae", "mean"), planned=("case_id", "size"), predicted=("mae", "count")).reset_index()
    linear = series[series.model == "linear"].set_index("dataset").mae
    series["mae_ratio_to_linear"] = series.mae / series.dataset.map(linear)
    series.to_csv(output/"series_trials.csv", index=False)
    objectives = []
    for (name, candidate), group in series.groupby(["model", "candidate"], sort=True):
        valid = len(group) == len(DEVELOPMENT) and (group.planned == group.predicted).all()
        objective = float(np.exp(np.log(group.mae_ratio_to_linear).mean())) if valid else None
        objectives.append({"model": name, "candidate": int(candidate), "eligible": bool(valid),
                           "geometric_mean_mae_ratio_to_linear": objective})
    runner.write_json(output/"objectives.json", objectives)
    parameters, selected_objectives = {}, {}
    for name, candidates in {**CONTROLS, **GRID}.items():
        eligible = [item for item in objectives if item["model"] == name and item["eligible"]]
        if not eligible:
            raise ValueError(f"All development configurations failed for {name}")
        chosen = min(eligible, key=lambda item: (item["geometric_mean_mae_ratio_to_linear"], item["candidate"]))
        parameters[name] = candidates[chosen["candidate"]]
        selected_objectives[name] = chosen["geometric_mean_mae_ratio_to_linear"]
    ratio = selected_objectives["diverse"]/selected_objectives["v1"]
    selection = {"schema_version": 2, "development_only": list(DEVELOPMENT), "parameters": parameters,
                 "selected_objectives": selected_objectives,
                 "diverse_mae_ratio_to_v1": ratio,
                 "product_model": "diverse" if ratio <= .95 else "v1",
                 "candidate_model": "diverse",
                 "best_non_retrieval_competitor": min(["linear", "extra_trees", "seasonal", "kalman", "pca"], key=lambda name: selected_objectives[name]),
                 "product_calibration": "static",
                 "product_rule": meta["product_selection"],
                 "selection_status": "Frozen before final evaluation; no final-series outcomes inspected",
                 "trials_sha256": runner.sha256(output/"trials.csv"),
                 "masks_sha256": runner.sha256(output/"masks.json")}
    runner.write_json(output/"selection.json", selection)
    meta.update(status="complete", completed_at=runner.utc_now(), elapsed_seconds=time.perf_counter()-started,
                trial_rows=len(rows), case_count=len(masks), selection_sha256=runner.sha256(output/"selection.json"))
    runner.write_json(output/"run.json", meta)
    print(json.dumps(selection, indent=2), flush=True)
    return selection


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"results/v2/development/tuning")
    args = parser.parse_args(argv)
    tune(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
