# GapLens v2: prospective evaluation protocol

Status: frozen before new-series scoring; exact selected parameters,
mask counts and freeze evidence are recorded in FREEZE.md before the final run.
The original v1 benchmark is preserved and is now development evidence.

## Question and scope

Does replacing overlapping nearest historical windows with temporally separated
windows improve retrospective block reconstruction, and does recent whole-gap
calibration help uncertainty under temporal change? This is an empirical study
of established mechanisms, not a new imputation or conformal theorem. TKCM
already selects nonoverlapping patterns; related-work distinctions matter.

The primary candidate is diverse retrieval. Point-error hypothesis H1: its
per-series geometric mean MAE ratio to the unchanged v1 algorithm is at most
0.95 on the predefined ordinary real-data regimes. Comparison to the best
development-selected non-retrieval competitor must also be reported, including
losses. H2: recent calibration improves absolute deviation of equal-series
mean empirical whole-gap coverage from 0.90 without increasing common-case mean normalized
width by more than 10%, versus static calibration of the **same** predictor.
This is an effect criterion, not a statistical coverage guarantee. Point and
uncertainty hypotheses may fail independently.

Also show the mean of per-series absolute coverage deviations: a macro average
can conceal opposing overcoverage and undercoverage. The displayed failure
example is the frozen product predictor's highest training-scale-normalized MAE
case in the primary regimes, with case ID as deterministic tie-breaker. Show raw
units and disclose this worst-case selection; do not imply typical behavior.

The ordinary primary regimes are MCAR short, MCAR long, MAR and MNAR. Compare
methods on identical cases with finite point predictions within each paired
comparison, even if calibration cannot provide an interval. Report their counts
and both point availability and interval service over all planned cases.
Other regimes are diagnostics. No claim may be based solely on excluding
refusals. Evaluate exact v1 in this protocol; do not compare v2 numbers directly
to the old 60/20/20 study as evidence of improvement.

## Data and independence

The fixed data inventory is `data/v2/manifest.json`: 14 real streams, multiple
cadences and domains, eight conservative provider/domain groups. Country-level
COVID series, social channels, cloud channels and advertising channels remain
correlated groups. Fourteen rows are not fourteen independent draws from all
possible systems. Use the manifest group labels for resampling; additionally
show sensitivity to source-release grouping where possible.

Sources include public-domain CO2, EIA oil prices and NOAA weather, attributed
SSA births, JHU reporting increments, and NAB-distributed cloud/social/ad data.
The license ledger and exact upstream commits/hashes accompany the inventory.
Negative JHU reporting revisions are retained. No target interpolation occurs.
Metadata-only exclusions (license or insufficient complete windows) are recorded
before scoring. Natural holes have unknown truth and are never scored as if
they were observed. Controlled masks hide finite measured values.

No final-series error, model prediction, test plot or outcome was used to choose
data or hyperparameters. The three original NAB series alone are development
data. Their previously inspected test sections confer no new independent
confirmation; development results are labelled accordingly.

## Splits and information boundary

For each new series: first 40% fits all models, transformations and normalizers;
40–60% provides initial static calibration. Evaluate at origins 60%, 75%, 90%,
using the next 10% at each origin. Each origin has local context wholly within
its test chunk. All indices are half-open and saved in the mask artifact.

Model fitting is frozen at the first 40% at **every** origin. Recent calibration
uses `[origin−20%, origin)` only. It cannot refit a point model. For each mask
seed, simultaneous outage batches form an explicitly defined observed-history
chain. Previously hidden batch values remain unavailable to later calibration;
their union is masked permanently. Isolated counterfactual masks are separate
scenarios, not additional real outages. No earlier reconstruction is truth.

Each method receives the same fit history, timestamps and exactly `c` original
measurements on either side of a target gap. All other query values, including
the target, are masked before calling the model. Right context is legitimate
in this offline task. No method receives extra future observations.

The scarce-history diagnostic fits on the first quarter of the normal training
prefix, with the same calibration and query observations. All methods receive
that identical reduced history. It is a separate condition, not a new dataset.

For fewer than 2,000 rows use `c=3`, lengths 3/7, stress length 21; otherwise
`c=6`, lengths 6/24, stress length 48. These are metadata rules, not chosen from
errors. Save physical durations per series: six weekly samples mean six weeks,
six five-minute samples mean thirty minutes. A seasonal period is specified
from source cadence and domain (not test autocorrelation). V1's calendar
features remain unchanged and may be unhelpful at daily/weekly cadences.

## Methods and development budget

Keep linear interpolation, literal v1 `AnalogBridge`, raw context retrieval
without endpoint correction, and ExtraTrees residual prediction. Add seasonal
phase-profile plus local level correction, local-linear Kalman/RTS smoothing,
conditional trajectory PCA, and full-window-separated analog retrieval.
Kalman and PCA are our disclosed baseline implementations, not reproductions
of DynaMMo, SSA, TKCM or a published leaderboard implementation.

Conditional PCA is a relevant CPU rival chosen to challenge retrieval: it learns a low-rank trajectory
subspace from complete fit windows and conditions on the same two contexts.
Kalman conditions a fitted structural process on those contexts. These small
univariate histories do not establish a fair pretraining setting for a large
neural model; no claim against neural imputation is made.

Tune diverse k, PCA rank/ridge, Kalman process ratio and ExtraTrees size with
three declared configurations each on identical development masks. Fixed
controls (v1, linear, raw retrieval, metadata-seasonal) are not retuned. Preserve
all trial errors, failures, timings and selected parameters. The tuning objective
is the geometric mean of per-series MAE ratios to linear, avoiding tiny-IQR
domination. Tie-breaking is deterministic and favors the earlier/simpler grid
configuration. Exact grids and masks are in the executable configuration and
development artifacts, frozen before final evaluation.

Use the separated point predictor as the default candidate only if development
shows at least 5% improvement over v1 by that objective; otherwise retain the
simpler v1 point rule. Still report both candidates on the final holdout. Final
outcomes cannot select a new configuration or justify retuning on that holdout.

## Masks and operational failures

Seeds 17, 29 and 43; three chronological origins each. Exact deterministic
generator formulas and all resulting indices are persisted before scoring.
MCAR chooses uniformly among eligible complete windows. MAR weights starts
using observed left context standardized by training statistics. MNAR weights
using the hidden block's fit-standardized magnitude: truth is available only
to this explicitly labelled mask generator and the scorer, never the models.

Include short/long MCAR, MAR, MNAR, simultaneous batches with a near pair,
damaged context, boundary gaps, scarce history and stress-long gaps. Apply all
batch gaps and damaged positions before predicting any constituent gap. Never
repair one gap to serve as context for another. Ineligible context or insufficient
support produces a recorded refusal, not a fabricated estimate.

A separately labelled synthetic level-shift stress adds two training IQRs to
both hidden targets and available local context on a real source window. This
is a controlled diagnostic only. Save observed-context novelty/shift diagnostics
on unchanged real cases. Also save local-context spread relative to training
spread and right-minus-left context means divided by the training scale, as
descriptive dispersion/trend indicators. They do not prove a structural break;
these diagnostics and any descriptive outcome strata cannot route the predictor.
Freeze descriptive high-change bins before scoring: absolute context level
shift >2 training scales; context spread / training standard deviation >2;
absolute right-minus-left mean change >1 training scale. Report performance,
counts and service in both sides of each threshold. Missing context statistics
remain an explicit unavailable category. These are proxies, not change-point
detectors or statistically established regime labels.

## Calibration and ablations

The score is the maximum absolute standardized residual over an entire gap.
Use corrected order statistic `ceil((n+1)*(1-alpha))`, alpha=0.1, up to 32
nonoverlapping full gap-and-context calibration windows per length. At least
nine usable scores are needed at alpha=0.1. No duplication, silent pooling,
lowered quantile or interpolation creates missing support. Insufficient support
is an explicit refusal and remains in the denominator.

Save calibration masks and scores, fitted quantiles, selected neighbors/counts,
distance, point predictions/scales/bands and reasons. The four-cell ablation is
v1/static, v1/recent, selected-separated/static, selected-separated/recent.
An additional separated/static variant fixes k=12 to match v1, isolating
temporal exclusion from the selected candidate's k tuning. Raw retrieval isolates
endpoint correction. Prior v1 adaptive/constant-scale diagnostics remain separate.
Temporally separated analogs are not asserted independent samples.

Coverage-width curves at alpha 0.20/0.10/0.05 use the same saved calibration
scores; unavailable quantiles remain unsupported. Compare widths on identical
serviced cases and at comparable achieved coverage. Report comparisons that
cannot be matched, rather than inferring improvement from narrower misses.
No width-based rejection threshold is tuned on final outcomes.

## Metrics, dependence and compute

Per series, length, origin and regime: MAE/RMSE, whole-gap and point coverage,
width, interval score, service fraction and refusal reasons.
Report accepted-and-whole-gap-covered / **all planned** cases as well as
coverage conditional on service, so abstention cannot disappear from accounting.
Primary paired
effects use per-series MAE ratios/geometric mean and ranks, with raw per-series
errors. Training-IQR-normalized error is a secondary descriptive aggregate;
show leave-one-series-out sensitivity rather than allow small IQR to dominate.

Resample whole conservative source/provider groups for exploratory paired
effect intervals, keeping all their series, origins, masks and points together.
Use 5,000 deterministic bootstrap draws. Eight groups are few: intervals do
not establish universal population superiority or independent mask trials.
Do not use pointwise IID bootstrap. Save losses and all exceptions.

Measure fit, first prediction/cache construction, calibration, warm prediction,
total runtime, cumulative process peak RSS and data/artifact sizes. Resource
figures describe this Linux cloud execution, not the owner's laptop. Lazy PCA
and analog-window work belongs to cold prediction/calibration, not just fit.

## Reproduction and changes

The freeze commit must contain this protocol, config, selected development
parameters, source/data hashes and preflight/masks. A run records their hashes.
Generated tables/figures derive from saved predictions and case measurements.
Clean reproduction compares numerical outputs, masks, scores and selected
decisions, excluding timings, UUIDs and platform strings.

Correctness fixes after a first final run require an explicit dated correction
record, independent review and rerun. The first exposure remains disclosed;
such reruns are corrected analysis, not a fresh unseen holdout. Performance
retuning requires new data or explicit exploratory labelling.
