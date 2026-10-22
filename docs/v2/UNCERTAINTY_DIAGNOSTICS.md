# Development diagnosis of v1 uncertainty

These analyses use only the three already inspected v1 development series and
their preserved predictions. They were completed before scoring the new v2
series. They investigate calibration sensitivity and heterogeneous failures;
they do not establish a universal cause of undercoverage or select a final-data
threshold.

Reproduce after installing the project in the isolated environment:

```bash
python scripts/analyze_v1_failures.py
```

The script writes:

* `results/v2/development/v1_diagnostics.csv`: 33 descriptive strata;
* `results/v2/development/v1_calibration_count_sensitivity.csv`: 135 combinations
  of three series, three seeds, three gap lengths and five requested counts;
* `results/v2/development/v1_diagnostics.json`: input hashes, exact calibration
  masks, control checks and interpretation notes.

The script uses the pinned `src/gaplens/_core_v1.py` numerical module and checks
its bytes against the original `core.py` hash in the v1 run metadata. It
verifies that all input artifact hashes remain unchanged. All **27** recomputed
quantiles for the original 24-case calibration matched the saved v1 quantiles
within `rtol=atol=1e-12`. No v1 result file was overwritten. The complete v1
benchmark reproduction remains a separate validation from this focused check.

## Block length and time are different failure dimensions

Whole-block coverage from the original adaptive AnalogBridge:

| Development series | Length 6 | Length 12 | Length 24 | Earlier sampled half | Later sampled half |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ambient temperature | 86.1% | 86.1% | 84.7% | 92.6% | 78.7% |
| CPU utilization | 91.7% | 94.4% | 93.1% | 92.6% | 93.5% |
| NYC taxi | 79.2% | 73.6% | 83.3% | 70.4% | 87.0% |

The length columns each contain 72 case rows. The time halves split each series
at the median sampled gap start, with 108 rows in each half. Masks across seeds
and lengths overlap, so these counts are not independent experimental units.

Undercoverage is not monotone in length: NYC's length-12 gaps perform worse than
length-24 gaps. Ambient and NYC change substantially across temporal halves,
while CPU coverage changes little despite increasing error and width. These are
descriptive associations. They motivate separate temporal and length analyses
and a static/recent calibration ablation; they do not identify temporal drift as
the sole cause.

## More calibration cases do not automatically repair coverage

For each original dataset/seed/length, the point predictions and relative scales
on the original test cases remain exactly the saved v1 values. The frozen v1
model is fitted to its original 60% fitting prefix. Calibration is recomputed
within the original 20% calibration interval, using the original seed formula
and requesting 9, 16, 24, 32 or 48 disjoint complete windows. The quantile then
changes the intervals around the fixed predictions; no new final-series data
are accessed.

| Requested calibration cases | Ambient coverage | CPU coverage | NYC coverage | Equal-series coverage | Equal-series normalized width |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 9 | 78.7% | 87.5% | 76.9% | 81.0% | 12.619 |
| 16 | 88.0% | 94.4% | 86.6% | 89.7% | 15.944 |
| 24, original | 85.6% | 93.1% | 78.7% | 85.8% | 12.920 |
| 32 | 81.9% | 92.1% | 78.2% | 84.1% | 12.286 |
| 48 | 82.4% | 92.6% | 79.2% | 84.7% | 12.525 |

Within a series these are equal averages over the three seeds and three
lengths. The saved per-case definitions weight blocks equally. The last column
is secondary: CPU's small training IQR dominates normalized width, as in v1.

Actual counts are retained. At the 32-case request, one ambient length/seed
stratum has only 31 windows. At the 48-case request, ambient strata range from
31 to 48 and NYC strata from 42 to 48. Nine of the 135 requested combinations
cannot reach their requested count. All can still form a finite 90%-target
quantile; none silently fabricate additional observations.

The masks for increasing counts are nested but differ in their additional
windows. Consequently this combines sample size, the composition of added
windows, and the changing discrete quantile rank; it is not a pure causal
sample-size effect. For example, 16 scores use their maximum under the corrected
rank rule, whereas 24 use their second-largest score. With dependent time-series
blocks, neither rank establishes a coverage guarantee. The near-90% aggregate
at 16 is therefore not a reason to adopt 16 cases: it also gives wider intervals
and is one result on already inspected development data. The evidence supports
reporting actual calibration counts and sensitivity, not promising that a
larger count alone resolves shift or heterogeneity.

## Distance does not provide a universal refusal threshold

For the lowest and highest quartiles of nearest-context distance within each
series:

| Series | Lowest-distance coverage | Highest-distance coverage | Lowest normalized width | Highest normalized width |
| --- | ---: | ---: | ---: | ---: |
| Ambient temperature | 96.3% | 88.9% | 1.213 | 1.471 |
| CPU utilization | 85.2% | 96.3% | 21.978 | 78.412 |
| NYC taxi | 81.5% | 72.2% | 0.700 | 0.969 |

Each quartile has 54 correlated rows and combines lengths and seeds. NYC's
high-distance cases have worse coverage, whereas CPU's have higher coverage
with extremely wide intervals. Ambient's intermediate quartiles are not
monotone either. A distance-only cutoff is not an established calibrated rule;
any selective reconstruction policy must report coverage and service together
and be selected separately from final outcomes.

## Adaptive scale has different tradeoffs on different series

| Series | Adaptive block coverage | Constant-scale block coverage | Adaptive normalized width | Constant-scale normalized width |
| --- | ---: | ---: | ---: | ---: |
| Ambient temperature | 85.6% | 71.8% | 1.300 | 1.004 |
| CPU utilization | 93.1% | 93.1% | 36.609 | 31.388 |
| NYC taxi | 78.7% | 79.2% | 0.850 | 0.869 |

These variants use the same mean predictions. On ambient temperature,
constant-scale intervals are narrower but cover substantially fewer blocks.
On CPU, adaptive scale is wider at the same aggregate block coverage. NYC's
differences are small and both under-cover. The original aggregate width
criterion fails, but this does not justify replacing adaptive scale everywhere.

The v2 study therefore keeps separate reconstruction/calibration ablations,
reports interval width with achieved coverage, retains unsupported intervals as
explicit service failures, and does not add an outcome-chosen rejection
threshold or claim a new uncertainty theorem. Exact exchangeable-block
conformal theory and the dependent-data assumptions of related methods are
discussed in `RELATED_WORK.md`; they are not automatically satisfied here.
