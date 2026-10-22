# Independent methodology review for GapLens v2

## Scope and review status

This review was prepared by a separate AI agent before new holdout results were
run. The reviewer read the complete stage-two request, the frozen v1 protocol,
the v1 reconstruction and calibration implementations, and the data acquisition
agent's metadata findings. This is a review of the design, not evidence that the
new method works. Implementation and final-result checks must be recorded below
after their artifacts exist. The lead implementation agent owns the final
protocol and algorithm decisions.

The three original NAB series are development data. Their published v1 results
and the independently reproduced checkpoint remain historical evidence, not new
validation of v2. New-series errors, intervals, or rankings were not used in this
review.

## Findings addressed in the proposed design

| Finding | Consequence | Agreed design response |
| --- | --- | --- |
| A change of reconstruction and calibration together is confounded. | Comparing diverse retrieval with rolling calibration against v1 with static calibration cannot isolate either change. | Run all four combinations of v1/diverse retrieval and static/rolling calibration. Treat optional refusal as a separate overlay. |
| Many neighboring reference windows share almost all their observations. | Twelve nearest windows need not represent twelve distinct historical episodes; their dispersion can understate uncertainty. | Evaluate greedy exclusion of overlapping complete reference windows; retain v1 unchanged as a control. Save the number and locations of selected neighbors. Do not call these windows independent. |
| Generic `context=6`, `length=24` is infeasible on some shorter series. | A JHU series of 1,142 rows has about 228 calibration rows and at most six disjoint 36-sample windows, below the nine scores required for a finite 90% conformal quantile. | The lead proposed `context=3`, lengths 3/7 below 2,000 rows; `context=6`, lengths 6/24 on longer series. Run a metadata-only mask feasibility check for every temporal origin, including persistent prior outages. Record unsupported long-gap stress cases as refusals. |
| Calibration and model-fitting histories can overlap if models are casually refitted at each origin. | A calibration target can also become a training target for the model being calibrated. | Fix model fitting to the first 40%; compare initial calibration `[40%,60%)` with the most recent 20% preceding each origin. Any later refitting would require a separately specified nonoverlapping fit/calibration design. |
| Rolling history can silently recover hidden truth from an earlier benchmark slice. | The benchmark gives the method measurements that the simulated user never received. | Remove all earlier hidden positions belonging to the same outage scenario from later calibration/history. Never insert model estimates as observations or calibration targets. |
| Cross-series normalized MAE can be dominated by a small training IQR. | An equal-series average can still mostly reflect one series' unstable normalization. | Publish raw per-series errors, paired method ratios, ranks and median effects; retain IQR-normalized metrics as secondary diagnostics. |
| Artificial gaps and repeated masks are not independent real outages. | Point-level confidence intervals exaggerate evidence. | State that these are real signals with artificial masking. Resample source/physical-system clusters; keep all related origins, masks and lengths in a cluster. |

The proposed size rule is a feasibility rule, not a claim that seven samples are
long in every domain. Physical durations and the relation to plausible seasonal
periods must accompany the settings. A 24-sample weekly gap is 24 weeks; a
24-sample five-minute gap is two hours. Extra length-48 diagnostics should be
identified as support/refusal stress where adequate calibration is unavailable.

## Information boundary and temporal evaluation

Use several disjoint evaluation intervals, for example 10%-wide chunks beginning
at 60%, 75%, and 90% of each series. The precise rounding and boundaries belong
in the executable configuration. All fitting transformations, model parameters,
noise scales, and learned periodicities use the permitted fitting prefix only.
Calendar periods supplied by documented domain metadata may be fixed before
evaluation. Period estimates from the complete series are not permitted.

Every model receives the same historical reference and the same `context`
observations on each side of a queried gap. This is retrospective reconstruction,
so the right context is legitimate. A state-space smoother must not receive the
entire final chunk while retrieval receives only local context. A seasonal model
may use the permitted history but cannot consult other hidden query targets.

Models should be passed an array in which hidden targets are actually `NaN`, even
if a particular implementation currently reads only the surrounding context.
This makes the boundary explicit and protects against future accidental reads.
The scoring process holds truth separately. Tests should alter hidden truth while
holding allowed observations fixed and confirm identical model predictions.

An outage chain is scenario-specific. At the second and third origins, prior
hidden positions in that same chain remain unavailable. Counterfactual isolated
gaps, other seeds, and other regimes must not all be unioned into one fictitious
history unless that is explicitly the scenario being tested. Conversely, all gaps
of a simultaneous batch must be hidden together before predicting its first gap;
predicting each gap against otherwise complete data is not a simultaneous-gap
experiment.

## Mask generation, context stress, and exclusions

Persist the case table or an exact deterministic generator with the dataset,
origin, random seed, regime, length, hidden indices, and any corrupted-context
indices. All methods must see identical cases. Boundary eligibility and naturally
missing observations must be handled before prediction, with exclusion reasons
and counts retained.

* **MCAR:** uniformly sample eligible gap starts with the specified exclusion or
  separation rule. Eligibility conditions mean this is MCAR conditional on the
  observed-grid and complete-context selection, not unrestricted MCAR over every
  timestamp.
* **Simultaneous:** draw and apply the complete batch together. Neighboring gaps
  can remove the context needed by another gap; retain the resulting refusals.
* **Missing context:** remove predetermined context measurements and report
  deliberate inability to reconstruct. This is distinct from a model failure.
* **Corrupted context:** perturb observed context by a fixed noise mechanism
  whose magnitude is based on the fitting prefix. The pristine truth is available
  to the scorer, not to any model. Do not silently replace corrupted context with
  the original values during prediction.
* **MNAR:** fix an explicit value-dependent selection rule before results. The
  generator may inspect hidden truth (for example, using magnitude or innovation
  relative to a fitting-prefix scale); models may not. Do not select masks using
  any method's errors. If a rule merely selects high-magnitude blocks, describe
  it as that targeted MNAR stress rather than representative real sensor failure.
* **Regime changes:** use a prespecified label definition for level, trend,
  variability, or seasonality change. A label based on hidden truth is an
  explanatory scoring stratum and cannot route the deployed model or calibration.
  Failure to find enough natural examples is a reportable limitation. Controlled
  transformations belong in a separate synthetic diagnostic table.

The data agent excluded TravelTime387 on complete-window/missingness feasibility
before method evaluation. Such exclusions should remain in the data manifest,
including the reason. Do not discard a series because it later produces poor
errors, wide intervals, or a model exception. If a software correction after
holdout inspection is necessary, describe exactly what changed and distinguish
bug correction from method selection.

## Competitors and development budget

Keep exact v1, endpoint linear interpolation and ExtraTrees. Include a seasonal
bridge, a state-space/Kalman smoother, and a low-rank conditional window model as
CPU-feasible alternatives. A raw nearest-context retrieval variant without
boundary correction is useful for identifying what the endpoint correction
contributes; it should not be presented as a faithful implementation of a named
published system without matching that system's algorithm.

The low-rank competitor should learn its subspace from historical complete
windows and condition that subspace on the same query context. Its rank and ridge
regularization require a reasonable development search, just as neighbor count
and temporal exclusion do for retrieval. Kalman process/measurement variances and
ExtraTrees leaf/training-budget choices require documented development decisions.
Record the configurations actually evaluated and their development scores; an
unused nominal budget is not evidence of tuning. Fixed metadata parameters, such
as a documented seasonal period, should be distinguished from tuned parameters.

Daily/weekly calendar features in literal v1 have limited meaning for weekly or
other slow series. Preserve them if the goal is an exact v1 control and disclose
the limitation. A period-aware change to v2 is another mechanism requiring its
own declaration or ablation; it must not be fitted on new final data after seeing
results. Neural baselines are optional when data and compute do not justify them;
do not imply that this establishes superiority over modern neural imputation.

## Uncertainty and refusal accounting

The maximum standardized residual over a block is an appropriate score for a
whole-block interval objective. The finite-sample rank formula alone does not
establish 90% coverage for dependent or shifted time series. Preserve the
distinction between a nominal target and measured coverage.

For `alpha=0.1`, fewer than nine finite calibration scores cannot produce the
usual finite split-conformal quantile. Calibration preflight must use the actual
disjoint sampler after naturally missing and previously hidden positions have
been removed. A theoretical packing bound is insufficient: a randomized greedy
sampler often selects fewer windows. Do not make up scores, sample duplicates as
if independent, or quietly use a different quantile rule. Save the actual count,
quantile, score distribution, and any failure reason for each method/origin/length.

Different-length scores may be pooled only as a declared, separately evaluated
calibration strategy, not as an undocumented rescue for a failed stratum. The
length-48 support stress may legitimately produce unavailable uncertainty; retain
that outcome and distinguish a missing interval from a missing point prediction.

Use the same calibration masks across methods. A method-specific failure can
reduce its calibration count and must be reported. A width-based refusal rule
must use observable predictions and calibration/development information only.
The simplest clean choice is a threshold frozen on development data. If the
threshold is optimized on new-series calibration cases, disclose the extra
selection and use a distinct calibration portion when feasible; conditional
coverage after selection does not follow from the unconditional quantile rule.

Report, by series, length and regime:

* planned and eligible cases; successful point predictions; available intervals;
* accepted-case MAE, point coverage, whole-block coverage and interval width;
* refused fraction with reasons, plus accepted-and-covered blocks divided by all
  planned eligible blocks;
* paired comparisons on the common accepted cases, alongside each method's own
  service fraction, so selective acceptance cannot masquerade as better accuracy.

Widths are informative only alongside attained coverage. Fixed nominal settings
can produce different empirical coverages. Show coverage/width pairs or a
prespecified calibration-level curve and avoid claiming an efficient interval
from a narrower but materially less covering band. Do not choose a final-test
threshold simply to obtain a desired coverage or acceptance rate.

## Aggregation and dependence

Average within series with explicitly stated weights for origins, lengths and
regimes, then report series-level paired effects. Raw cross-series MAE mixes
physical units. Ratios to a shared baseline are interpretable, but near-zero
baseline error needs a prespecified fitting-scale stabilizer or explicit handling
of zero/undefined ratios. Publish the denominator and sensitivity where it
matters. Median paired ratio, geometric-mean ratio, win count and rank are useful
complements; none should replace the complete per-series table.

Source-family clustering is conservative for the proposed panel: related NAB
channels and related national reporting series can share acquisition mechanisms
even when they represent different physical objects. Declare both the count of
series and the smaller count of source/physical-system clusters. Cluster
bootstrap samples must keep all masks, lengths and origins for a selected cluster
together. Explain whether the estimand weights series equally or clusters equally
and preserve that choice in the bootstrap. With only roughly seven or eight
clusters, uncertainty intervals are exploratory and do not establish broad
population-level generalization. Repeated masks are sensitivity analysis, not
additional independent systems.

## Runtime and reproducibility

Record fitting, calibration, first-query/cache-building, and warm-query costs
separately. In v1, reference-window caches are built lazily, so warm prediction
time alone omits a material preparation cost. Report aggregate process peak RSS
as such; do not assign it to individual methods without isolated measurement.
Record source data size and cloud hardware/software. These measurements do not
measure performance on the user's laptop.

Before a final run, save the protocol, effective configuration, source manifest,
mask-generation code, development-selection artifact, and code hashes in an
identifiable commit. Save predictions including intervals and refusals, timing,
logs, and selected masks. Reproduction should compare the complete prediction
records as well as report tables. Timing fields need not be byte-identical.
Changes motivated by final results require a new holdout or an explicit
exploratory label. A failed v2 hypothesis is a valid outcome and should leave the
simpler supported product default intact.

## Implementation and final-artifact review

The reviewer inspected `scripts/run_experiments_v2.py`,
`configs/benchmark_v2.json`, `scripts/summarize_v2.py`, and the protocol before
new-series scoring. Eight synthetic runner tests were independently executed
and passed. No new holdout run was performed by this reviewer.

The following concrete findings were raised and addressed before scoring:

* The initial config included simultaneous gaps in the primary objective while
  the written protocol did not. Both now use MCAR short/long, MAR and MNAR;
  simultaneous batches remain operational diagnostics.
* Static and recent calibration initially used different random masks at the
  first origin despite identical available intervals. A common calibration seed
  now makes those masks identical; later differences reflect permitted history.
* Point comparisons were initially described as jointly interval-serviced
  cases. The protocol and summary now use jointly finite point predictions,
  retaining CO2/Brent cases with insufficient calibration; interval service has
  its own denominator.
* The runner now saves cadence, physical gap durations, context spread and
  signed context change. The summary produces prespecified bins at absolute
  level shift above two training scales, spread ratio above two, and absolute
  context endpoint change above one training scale. These are descriptive
  quantities, do not prove structural breaks, and do not route a predictor.
* An additional separated-retrieval variant fixes `k=12` to match v1. This
  isolates exclusion from a development-selected change in neighbor count.
* Coverage-width rows retain unsuccessful cases. The summary checks that static
  and rolling variants have identical point predictions/scales, uses common
  point cases for paired errors, and common all-method cases for ranks. It also
  reports accepted-and-covered blocks divided by all planned eligible blocks.
* The literal v1 control imports the byte-preserved `_core_v1.py` module. Product
  validation fixes to `core.py` therefore cannot change the control. The freeze
  guard verifies that the local freeze manifest equals its committed contents,
  as well as checking its protected artifact hashes.

Code inspection found that `local_query` exposes only the declared context and
sets every other value to `NaN`; calibration windows exclude the prior actual
outage chain and remain outside the fitting prefix. Calibration-cache reuse is
keyed by model/history and exact windows. Although the unavailable-history list
is not part of that key, it cannot affect any visible context of a validated
window, so this reuse does not expose hidden truth. The outcome generator's
access to targets for MNAR selection is explicitly separated from prediction.

The summary keeps each source group intact in bootstrap draws and also provides
source-release grouping sensitivity. It excludes undefined positive-error/zero-
reference ratios explicitly and makes the complete H1 criterion unsupported
if any series lacks a valid comparison. Its calibration comparison reports both
absolute error of macro coverage and average per-series absolute coverage error,
because the former can conceal opposite errors across series.

The first final-artifact review passed. The independently written
`scripts/review_v2_methodology.py` verifies all 13,369 calibration windows,
previous-outage exclusion, query-context refusals, per-series paired effects,
both group-bootstrap definitions, common-case ranks, and coverage/service
denominators. Its receipt is `results/v2/initial_methodology_review.json`; the
interpretation and limitations are in `RESULT_REVIEW.md`.

A CSV provenance-validation bypass was discovered after first result exposure:
a leading blank line could let the header guard and pandas disagree. The lead
agent corrected that product validation path and preserved first outputs. This
is a disclosed correctness correction after exposure, not an unseen holdout or
a performance-tuning opportunity. `CORRECTIONS.md` records it. The independent
methodology audit also passed on the corrected canonical outputs, with its
receipt in `results/v2/methodology_review.json`. The scientific tables and all
eight figure files match the first outputs byte for byte; see
`results/v2/validation/summary_replay.json`. No model, mask, primary metric or
hypothesis was changed by this review.

The final review covered:

1. Trace every model input, calibration mask and prior-outage mask to the permitted
   history; check simultaneous batches and context corruption against saved cases.
2. Verify source hashes and source/physical-system grouping, actual calibration
   counts, per-series physical gap durations, and all recorded exclusions.
3. Check development search logs and the freeze commit precede final outcomes.
4. Recompute core aggregate and per-series comparisons from saved rows, including
   service denominators, failures, and the four reconstruction/calibration cells.
5. Verify that conclusions distinguish preregistered criteria, exploratory
   diagnostics, empirical coverage, and theoretical assumptions.

## Development-only diagnosis of the preserved v1 uncertainty results

The following descriptive checks use only
`results/benchmark/case_metrics.csv`, filtered to `method=analog_bridge` unless
otherwise stated. No new data or predictions were used. Each series has 216
case rows; these are correlated masks, not 216 independent experiments.

| v1 development series | Block coverage, length 6 | Length 12 | Length 24 | Earlier sampled half | Later sampled half |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ambient temperature | 0.8611 | 0.8611 | 0.8472 | 0.9259 | 0.7870 |
| CPU utilization | 0.9167 | 0.9444 | 0.9306 | 0.9259 | 0.9352 |
| NYC taxi | 0.7917 | 0.7361 | 0.8333 | 0.7037 | 0.8704 |

The length columns average `gap_coverage` within `(dataset,gap_length)` (72 rows
each). The sampled halves partition each dataset at the median `source_start`
(108 rows each); they are not a new train/test split. Undercoverage is not
monotone in length. Large changes across temporal halves motivate a temporal
diagnostic but do not prove that calibration drift caused the difference.

Quartiles of `context_distance` within each dataset show a further caution. NYC
coverage is 0.8148 in the lowest-distance quartile and 0.7222 in the highest.
CPU coverage is 0.8519 and 0.9630 respectively, but its mean normalized width
increases from 21.9779 to 78.4120. Distance is therefore not an established
universal threshold for unreliable intervals. These quartiles mix lengths and
seeds and are descriptive, not an adjusted causal analysis.

| Series | Adaptive block coverage | Constant-scale block coverage | Adaptive normalized width | Constant-scale normalized width |
| --- | ---: | ---: | ---: | ---: |
| Ambient temperature | 0.8565 | 0.7176 | 1.2996 | 1.0044 |
| CPU utilization | 0.9306 | 0.9306 | 36.6090 | 31.3878 |
| NYC taxi | 0.7870 | 0.7917 | 0.8502 | 0.8692 |

These rows average the saved case metrics by dataset and method. The aggregate
v1 width failure does not justify globally replacing adaptive scale: the smaller
ambient intervals also have substantially worse coverage. CPU is the principal
normalized-width contributor, while the NYC adaptive/constant difference is
small. The v2 diagnosis should examine these mechanisms separately rather than
presenting an unconditional claim that one scale construction is superior.
