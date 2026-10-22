#!/usr/bin/env python3
"""Build standalone research figures from a completed saved benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "gaplens-matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "gaplens-cache"))
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ORDER = ["linear", "extra_trees", "analog_bridge", "analog_no_bridge", "analog_constant_scale", "analog_pooled_calibration"]
LABELS = ["Linear", "ExtraTrees", "AnalogBridge", "No bridge", "Constant scale", "Pooled calibration"]
COLORS = ["#7c8b98", "#a4b3be", "#176f9e", "#c8854b", "#c7a35c", "#a096bf"]


def save(fig, destination: Path, name: str):
    fig.savefig(destination / f"{name}.png", dpi=180, bbox_inches="tight")
    fig.savefig(destination / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def plot(input_dir: Path) -> list[str]:
    run = json.loads((input_dir / "run.json").read_text(encoding="utf-8"))
    if run["status"] != "complete":
        raise ValueError("Only completed experiment runs can be plotted")
    for filename in ["summary.csv", "aggregate_summary.csv", "predictions.csv", "worst_cases.csv"]:
        digest = hashlib.sha256((input_dir / filename).read_bytes()).hexdigest()
        if run["artifact_sha256"].get(filename) != digest:
            raise ValueError(f"Artifact checksum does not match this completed run: {filename}")
    summary = pd.read_csv(input_dir / "summary.csv")
    aggregate = pd.read_csv(input_dir / "aggregate_summary.csv").set_index("method").loc[ORDER]
    predictions = pd.read_csv(input_dir / "predictions.csv")
    if set(predictions.run_id.unique()) != {run["run_id"]}:
        raise ValueError("Prediction rows do not belong exclusively to the selected run")
    worst = pd.read_csv(input_dir / "worst_cases.csv").iloc[0]
    figures = input_dir / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    datasets = run["config"]["datasets"]
    fig, axes = plt.subplots(1, len(datasets), figsize=(5 * len(datasets), 4.6), squeeze=False)
    for ax, dataset in zip(axes.flat, datasets):
        sub = summary[summary.dataset == dataset]
        seed_means = sub.groupby(["method", "seed"]).normalized_mae.mean().unstack("method")
        means = seed_means.mean().reindex(ORDER)
        minima, maxima = seed_means.min().reindex(ORDER), seed_means.max().reindex(ORDER)
        bars = ax.bar(np.arange(len(ORDER)), means, color=COLORS)
        ax.errorbar(np.arange(len(ORDER)), means, yerr=[means - minima, maxima - means],
                    fmt="none", capsize=3, color="#263746", linewidth=1)
        ax.set_xticks(np.arange(len(ORDER)), LABELS, rotation=38, ha="right")
        ax.set_title(dataset.replace("_", " ").title())
        ax.set_ylabel("MAE / training IQR (lower is better)")
        ax.grid(axis="y", alpha=.2)
    fig.suptitle("Reconstruction error on real held-out observations", y=1.02)
    fig.text(.01, -.03, "Bars average gap lengths and seeds. Whiskers are seed ranges, not confidence intervals.", fontsize=9)
    fig.tight_layout()
    save(fig, figures, "quality")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    x = np.arange(len(ORDER))
    axes[0].bar(x, aggregate.gap_coverage, color=COLORS)
    axes[0].axhline(1 - run["config"]["alpha"], color="#b04b4b", linestyle="--", label="Nominal 90%")
    axes[0].set_ylim(0, 1.04)
    axes[0].set_ylabel("All hidden points covered / gap (higher is better)")
    axes[0].set_title("Empirical simultaneous gap coverage")
    axes[0].legend(frameon=False)
    axes[1].bar(x, aggregate.normalized_width, color=COLORS)
    axes[1].set_ylabel("Mean interval width / training IQR")
    axes[1].set_title("Band width: interpret together with coverage")
    for ax in axes:
        ax.set_xticks(x, LABELS, rotation=35, ha="right")
        ax.grid(axis="y", alpha=.2)
    fig.text(.01, -.03, "Equal dataset/seed/length weighting. Time-series dependence prevents an unconditional coverage guarantee.", fontsize=9)
    fig.tight_layout()
    save(fig, figures, "coverage_width")

    case = predictions[predictions.case_id == worst.case_id]
    fig, ax = plt.subplots(figsize=(11, 4.7))
    analog = case[case.method == "analog_bridge"].sort_values("offset")
    ax.plot(analog.offset, analog.truth, "o-", color="#182c3a", linewidth=2, markersize=3, label="Hidden real observations")
    for method, label, color in zip(ORDER[:3], LABELS[:3], COLORS[:3]):
        sub = case[case.method == method].sort_values("offset")
        ax.plot(sub.offset, sub.prediction, color=color, linewidth=1.8, label=label)
    ax.fill_between(analog.offset, analog.lower, analog.upper, alpha=.18, color=COLORS[2], label="AnalogBridge band")
    ax.set_xlabel("Offset within hidden block (samples)")
    ax.set_ylabel("Original series units")
    ax.set_title(f"Largest AnalogBridge normalized-MAE gap: {worst.dataset}, seed {worst.seed}, length {worst.gap_length}\n{worst.start_timestamp}")
    ax.grid(alpha=.2)
    ax.legend(frameon=False, loc="best", ncol=2)
    fig.tight_layout()
    save(fig, figures, "worst_gap")
    names = ["quality", "coverage_width", "worst_gap"]
    manifest = {
        "run_id": run["run_id"], "source_run_sha256": hashlib.sha256((input_dir / "run.json").read_bytes()).hexdigest(),
        "figures": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(figures.iterdir()) if p.suffix in [".svg", ".png"]},
        "note": "All figures are derived from checksummed measurement artifacts; no values are hand-entered.",
    }
    (figures / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return names


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/benchmark")
    args = parser.parse_args(argv)
    try:
        names = plot(args.input)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Plotting error: {exc}\n")
    print("Saved PNG and SVG figures:", ", ".join(names))


if __name__ == "__main__":
    main()
