# Independent review of the v2 results

## Status and audit scope

This review was written by a separate AI agent after the first final-result
exposure. It distinguishes the frozen criteria from exploratory interpretation.
It did not fit a model, choose new hyperparameters, alter masks, or run another
holdout experiment. The first outputs are retained in
`results/v2/initial_benchmark` and `results/v2/initial_final`.

After that exposure, the lead agent found a product-input validation bypass:
adding a leading blank line to an exported `repaired.csv` allowed the header
check to disagree with pandas and accept repaired values as observations. The
subsequent correction concerns CSV provenance validation. It requires an
explicit correction record and numerical replay; the corrected analysis is not
a new unseen holdout. See `CORRECTIONS.md` for the exact chronology and replay
evidence. No positive performance claim is justified by calling this correction
an independent replication on fresh data.

The independently written `scripts/review_v2_methodology.py` checks saved
artifacts without importing the experiment runner or summary implementation.
For the first final outputs, it verifies:

* all 2,139 planned gaps and 23,529 method-case rows, including refusals;
* 1,008 primary gaps with finite point predictions for every method;
* all paired per-series effects and both eight-domain-group and six-release-group
  bootstrap intervals using a separate vectorized implementation;
* ranks on the common prediction intersection and both static/recent uncertainty
  estimands on their 982 jointly interval-serviced gaps;
* all 13,369 calibration windows across 756 strata against fitting boundaries,
  within-stratum nonoverlap, natural missingness, and previous outage masks;
* that missing query context is not silently served, and that accepted-and-covered
  fractions use the published planned-case denominator.

The numerical reconciliation of individual point predictions, scales, intervals
and calibration quantiles is a separate check in `scripts/verify_v2.py`; this
review complements rather than replaces it.

Reproduce the independent review of the preserved first outputs:

```bash
python scripts/review_v2_methodology.py \
  --benchmark results/v2/initial_benchmark \
  --summary results/v2/initial_final \
  --output results/v2/initial_methodology_review.json
```

Review the corrected canonical artifacts:

```bash
python scripts/review_v2_methodology.py
```

The latter writes `results/v2/methodology_review.json`; its hashes identify the
exact inputs audited. Both the preserved first-output and corrected-output
methodology audits passed. `results/v2/validation/summary_replay.json` additionally
confirms byte-identical scientific CSV tables, Markdown tables and all eight
figure files, with summary fields unchanged except performance measurements.
Clean-environment replay is separately documented under
`results/v2/validation`; it is not inferred from aggregate agreement alone.

## Reconstruction: the proposed modification fails H1

The frozen diverse-neighbor candidate has a geometric mean per-series MAE ratio
of **1.045317** to literal v1, with four wins and ten losses. Its exploratory
eight-group 95% interval is **1.019865–1.074449**; collapsing related NAB groups
to source release gives **1.011325–1.070308** across six groups. These intervals
summarize this small panel and do not establish a population-wide theorem.

Fixing the diverse model to v1's `k=12` gives ratio **1.039258**, also four wins
and ten losses. Thus the failure is not explained solely by the selected
neighbor-count difference. Temporal exclusion is an established mechanism and
this result supplies no basis for a novelty or accuracy-improvement claim.

The candidate's ratio to the development-selected ExtraTrees competitor is
0.986822, with seven wins and seven losses and an interval crossing one. This
small point advantage does not rescue the failed v1 comparison. The original
point method remains the development-selected default; it should not be
described as a universal winner either. In the new protocol, its ratio to linear
is 1.154309 with seven wins and seven losses, while its ratio to ExtraTrees is
0.944041 with ten wins and four losses. Results against the simple interpolation
and Kalman alternatives must remain visible.

## Uncertainty: the frozen H2 passes, with a narrow interpretation

On 982 common interval-serviced primary cases, the equal-series macro values are:

| Predictor | Static block coverage | Recent block coverage | Recent/static normalized mean width | Static interval service | Recent interval service |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1 | 0.926348 | 0.909483 | 0.341245 | 996/1,008 | 984/1,008 |
| Diverse | 0.909483 | 0.902579 | 0.407043 | 996/1,008 | 984/1,008 |

Both satisfy the frozen macro criterion, but the result is not a uniform
improvement in useful uncertainty. Recent calibration supplies fewer intervals.
For the diverse model, mean per-series absolute deviation from 90% actually
increases from **0.044800** to **0.046627**: eight series worsen and four improve,
with the remainder unchanged. The macro coverage error can improve while
opposing series-level errors become more heterogeneous.

The network stream accounts for approximately **99.397%** of v1's static mean
normalized width and **98.676%** of the diverse model's. The following checks
were motivated by that observed dominance and are explicitly **post-result
exploratory sensitivity analyses**, not replacement H2 criteria:

| Predictor | Median per-series width ratio | Geometric mean per-series width ratio | Normalized mean-width ratio omitting network |
| --- | ---: | ---: | ---: |
| v1 | 0.922586 | 0.977810 | 1.073172 |
| Diverse | 0.940726 | 0.974649 | 1.103690 |

Eight series become narrower and six wider for each predictor. Without network,
the diverse model would exceed the frozen 10% width-increase condition. That
post-result omission must not be substituted for the originally specified
all-series result, nor should the all-series reduction be presented without
its dependence on this stream.

The common coverage-width curve contains only **616 of 1,008** primary cases and
13 of 14 series, because all 11 methods at all three calibration levels must
support a case. Its selection is explicit, and the separate own-service tables
retain the full denominators. It is a useful conditional comparison rather than
a full-panel replacement. Coverage is empirical throughout; blockwise scores do
not by themselves establish exchangeability or 90% guarantees for these data.

Reproduce the post-result sensitivity analysis:

```bash
python scripts/analyze_v2_sensitivity.py
```

It writes `results/v2/sensitivity`, including `sensitivity.json`, per-series
width ratios, leave-one-series-out effects, and source fitting/calibration
extremes with input hashes. It does not change the frozen model, protocol or
primary aggregate.

## What the network failure shows

This is not explained solely by a tiny IQR. The network fitting prefix has
median 251,011, IQR 25,676.5 and maximum 4,206,500 in source units. Its initial
calibration interval contains a value of **245,126,000**, whereas the maxima of
the three evaluation chunks are 255,514, 296,345 and 1,246,660. The extreme is
retained as source data, not removed because it is inconvenient.

The v1 static calibration quantile reaches approximately 6,648.95. Its mean
network interval width is about **3.394 billion source units**, compared with
1.143 billion for recent calibration. Even the reduced width is impractical
relative to much of the observed signal. The same stream's primary-case MAE is
approximately 845,061 for v1 versus 15,260 for linear interpolation. These values
expose failures of both analog reconstruction and a global empirical score
calibration in a heterogeneous history; they do not prove one unique causal
mechanism. More targeted experiments on event contamination and local support
would be needed before adding a new rejection or calibration rule.

## Operational conclusions and remaining limits

Boundary and deliberately missing-context gaps are refused consistently. In the
simultaneous scenario, the near pair cannot supply the required context, so only
one of the three target gaps is serviced. These refusals are part of the outcome,
not excluded difficult cases. Some weekly long gaps and many long-gap stress
cases have finite point predictions but insufficient calibration; these are
research point-only outputs rather than serviced product reconstructions.

The data are 14 real streams grouped conservatively into eight domain/provider
groups, with six source-release groups in sensitivity analysis. They are not 14
independent draws, and the many masks are not additional independent systems.
Natural level/spread/context-change bins are descriptive proxies, not verified
structural-break labels. Missing-context damage was tested; this is not a
comprehensive study of every form of value corruption. Performance applies to
artificial masking with known truth, not unobserved real outages.

The justified result is a more auditable product and a reproducible negative
test of a plausible modification, with a mixed calibration finding. A future
article needs broader independent evidence, stronger externally implemented
competitors where feasible, and prospective testing of any new support or
calibration mechanism. It should retain the failed hypotheses, the network
failure, the post-exposure correction history, and the disclosure that AI agents
performed substantial implementation, analysis and review.
