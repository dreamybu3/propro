# Fixed evaluation protocol, version 1.0

This protocol and `configs/benchmark.json` were written before running the main
benchmark. They are a local design record, not a registered study. The test split
must not be used to tune model settings or select methods. Negative and mixed
outcomes are retained. No method or dataset is dropped because of poor results.

## Question and falsifiable criteria

Can an endpoint-conditioned historical analog method reconstruct missing blocks
of operational time series with a useful CPU cost and calibrated error bands?
The engineering contribution is the explicit context retrieval, endpoint
correction, disagreement scale and gap-length calibration pipeline, rather than
a claim to have invented analog imputation or conformal prediction.

The pre-experiment hypothesis has separate, demanding criteria:

1. AnalogBridge reduces mean train-IQR-normalized MAE by at least 10% versus
   endpoint linear interpolation, averaged equally over datasets, seeds and gap
   lengths. Its error is no more than 10% above the stronger ExtraTrees baseline.
2. At nominal 90% simultaneous gap coverage, observed macro gap coverage is at
   least 85%, and normalized interval width is lower than the constant-scale
   ablation. Coverage and width must be considered together; narrow invalid
   intervals are not a success.

Failure of any criterion is evidence against that part of the hypothesis.
Results on only three datasets cannot establish broad superiority.

## Data and task

Use all three preselected real NAB files in `data/manifest.json`: NYC taxi
passenger counts, AWS CPU utilization and office ambient temperature. Data are
pinned to upstream commit
`ea702d75cc2258d9d7dd35ca8e5e2539d71f3140`. Only ambient timestamps need explicit
hourly reindexing; newly inserted values remain missing. Native missing values
are not treated as known ground truth. No artificial NAB signal is used.

The evaluation artificially hides contiguous blocks of **real observed values**.
This tests offline reconstruction after observations on both sides are available.
It does not test forecasting, online recovery, naturally missing ground truth,
causal inference, anomaly detection, or missing-not-at-random mechanisms.

Each series is split by row/time into the first 60% for reference/training, next
20% for interval calibration and final 20% for testing. Split indices are recorded
in `run.json`. Both sides of every evaluated gap, with six context points per
side, stay wholly within their own split. References and ExtraTrees targets come
only from the training split. Calibration adjusts interval quantiles only, not
point predictions. Known timestamps may be used as calendar features.

For each seed (17, 29, 43) and gap length (6, 12, 24 samples), deterministically
permute eligible complete windows, then greedily select up to 24 calibration and
24 test windows without overlap, **including context**, within that
seed/split/length. Missing or invalid windows are ineligible. Actual counts are
saved; insufficient calibration is an error, not silently accepted. Across gap
lengths and across seeds, selected windows may overlap. Each case is an isolated
gap: hidden points in one case are not concurrently hidden in another. Thus the
experiment does not measure dense, simultaneous missingness.

Gap lengths are sample counts, not equal physical durations: NYC taxi is every
30 minutes, CPU every 5 minutes and ambient temperature hourly. Cross-series
aggregation uses normalized errors and equal series weights.

## Methods and ablations

- **Linear:** endpoint interpolation, with a bridge-shaped relative error scale.
- **ExtraTrees:** 64 single-threaded trees, trained on up to 600 sampled training
  gaps; observed contexts, calendar, length, position and interpolation features
  predict the residual to interpolation. No hidden interior point is a feature.
- **AnalogBridge:** 12 context neighbors, at most 4,000 deterministically spaced
  complete reference windows, fixed calendar weight 0.15; endpoint-corrected
  trajectories are weighted by context similarity. Disagreement, a training
  innovation floor and context novelty determine relative scale.
- **No bridge:** same retrieval and averaging without endpoint correction.
- **Constant scale:** same point predictions as AnalogBridge but a fixed training
  noise scale, isolating the local scale's effect on intervals.
- **Pooled calibration:** same AnalogBridge point predictions and relative scale,
  using one pooled calibration quantile rather than one per exact gap length.

All settings are fixed before the main run. The stronger baseline is a practical
CPU baseline, not a claim to reproduce all state-of-the-art imputation systems.

## Intervals and dependence caveat

For each calibration gap, the score is the maximum over its hidden points of
`abs(truth - prediction) / relative_scale`. For each exact gap length, use the
`ceil((n + 1) * (1 - alpha))`-th smallest score, with alpha=0.1. A score count
insufficient to yield a finite quantile is rejected. Each predicted point's band
is its mean plus/minus this quantile times its scale. Pooled calibration combines
scores from all lengths.

This is the split-conformal finite-sample quantile construction for simultaneous
gap bands. Its distribution-free coverage theorem requires exchangeability,
which chronological, autocorrelated and shifting time series do **not** establish.
The project therefore reports empirical coverage, not a coverage guarantee. Seed
repeats measure mask sensitivity, not independent datasets; their ranges are not
confidence intervals or significance tests. Windows can overlap between repeats.

## Measurements and artifacts

Per gap: MAE, MSE/RMSE, train-IQR-normalized MAE, point coverage, all-points gap
coverage, interval width, normalized width, a pointwise interval score at alpha
0.1, and prediction wall time. Training-IQR normalization has a tiny positive
floor for constant references; the actual scale is saved. The interval score is
pointwise despite the bands being calibrated for whole gaps.

Record model fit time and total process peak RSS where supported. RSS is a
cumulative high-water mark for this Python process, not an isolated per-method
memory benchmark; Windows may not provide this measurement. Time measurements
include Python overhead and are machine-specific. All methods execute on CPU,
with ExtraTrees single-threaded and no API calls during modeling.
Analog candidate windows are cached lazily during calibration, so fit times do
not include cache construction and test prediction times use warm caches.
Per-method calibration prediction/scoring time, including candidate construction
for every length, is recorded separately; it excludes common mask creation.

`case_metrics.csv` contains every gap/method result; `predictions.csv` contains
all hidden real observations and predicted bands; `summary.csv` groups by
dataset/seed/method/length; `series_summary.csv` and `aggregate_summary.csv`
provide equal-weight summaries; `hypothesis.json` evaluates the fixed criteria.
`run.json` records exact configuration, code/data hashes, versions, hardware,
split boundaries, case counts, seeds, and execution timestamps. `run.log` records
progress and failures. Plots and worst cases are derived only from saved files.

Run the definitive experiment from the repository root:

```sh
python scripts/run_experiments.py --config configs/benchmark.json --output results/benchmark
python scripts/plot_results.py --input results/benchmark
```

`--quick` is a separate smoke run with fewer cases/trees and writes by default to
`results/smoke`. It is not evidence for the fixed hypothesis. Existing nonempty
output directories require explicit `--overwrite`; successful run metadata is
marked complete only after all selected cases have executed.
