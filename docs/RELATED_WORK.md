# Related work and positioning

This review was completed on 2026-10-22 using the primary sources recorded in
[SOURCES.md](SOURCES.md). It is a bounded literature and software review, not a
systematic review or a proof of novelty. Performance claims in other authors'
READMEs are not treated as measurements of GapLens.

## User and task

A researcher or monitoring analyst receives a regularly sampled **univariate**
CSV with contiguous missing observations. After later observations have arrived,
they need an inspectable reconstruction, uncertainty bands, a record of which
values were estimated, and a file suitable for further analysis. GapLens handles
this offline task. It is not an online forecasting or anomaly-detection product.
Using the observed right-hand context is legitimate for this task and must be
stated when comparing it with causal forecasting methods.

## Existing solutions and what this project tests

| Closest family or product | What primary sources establish | GapLens positioning and unverified assumptions |
|---|---|---|
| **imputeTS** [S2] | A mature R package specializes in univariate time-series missing-value replacement; its documented methods include interpolation, Kalman smoothing, moving averages and seasonal decomposition. | Missing-value repair is already useful and well served. GapLens offers a small Python/CSV workflow with a deliberately explicit historical-reference method and whole-gap calibration. We have **not** established that users prefer it or that it is more accurate than Kalman/seasonal methods. |
| **ImputeGAP** [S3] | Its primary repository describes a complete Python repair/analysis/benchmarking library, over 40 methods, configurable missingness and downstream evaluation. Its README specifies a Unix-compatible environment and includes pattern-search methods (TKCM, ST-MVL, DynaMMo), KNN and interpolation. | A repair interface, pattern search, or combining evaluation and imputation is **not** a new contribution. GapLens deliberately narrows the task to a small CPU-only, univariate, auditable implementation and an intended Windows workflow. Native Windows execution remains unverified. ImputeGAP's listed Unix requirement is a documented packaging difference, not evidence that every algorithm fundamentally requires Unix. |
| **BRITS** [S4] and **SAITS** [S5] | Authors provide trainable recurrent and attention-based imputation implementations. The SAITS paper explicitly uses temporal and feature dependencies in multivariate data; its main setup masks observed entries to evaluate reconstruction. | GapLens trades learned cross-variable representations for retrieval from one historical stream. This is a scope and engineering choice, not evidence of better accuracy, lower memory or greater speed than these systems. They are not benchmarked in the present run. |
| **CSDI** [S6] | Authors provide conditional diffusion-based **probabilistic** time-series imputation, sample-generation options and pretrained evaluation examples. | Uncertainty in imputation already has substantial prior work. GapLens returns calibrated bands around a point estimate, not a joint generative distribution or multiple imputations. It makes no claim to replace CSDI. |
| **EnbPI** [S7], the conformal tutorial [S8], and **MAPIE** [S9] | These sources establish existing conformal uncertainty methods and implementations, including time-series settings. EnbPI's author repository also points to later time-adaptive residual-quantile work. | Finite-sample conformal quantiles are established methodology. GapLens applies a maximum standardized residual per gap and groups scores by exact gap length. This **does not** create a distribution-free guarantee for dependent, chronologically split streams. Comparison with adaptive/rolling methods is future work. |
| **ExtraTrees** [S10] | Scikit-learn provides randomized tree ensembles; its primary documentation explains random split thresholds and cites Geurts, Ernst and Wehenkel (2006). | The stronger benchmark uses the library's regressor with our observed-context and residual-target representation. The tree algorithm is external work, not our contribution. |

NAB [S1] is an anomaly-detection corpus. Its real signals supply a small, varied,
public test bed, but its anomaly labels are **not** imputation truth. We evaluate
artificial outages in real observed values, retain native missing values, and do
not interpret this as observed performance on genuine unobserved outages.

## What was implemented here

The technical artifact is the complete **AnalogBridge** reconstruction mechanism
and its auditable evaluation path:

1. Index complete historical windows separately for each requested gap length.
   Rank their two observed context segments using std/MAD-scaled value distance
   and optional cyclic calendar features. Training/reference data alone supply
   candidates.
2. Correct each retrieved trajectory using a linear bridge between the two
   endpoint residuals, then combine trajectories by context-similarity weights.
   This explicitly separates reusable historical shape from local endpoint level.
3. Build a positive relative error scale from retrieved-trajectory disagreement,
   training innovations and context novelty. This scale alone is not a probability
   or uncertainty guarantee.
4. Use held-out chronological calibration gaps to convert that scale into bands,
   scoring each whole gap by its maximum standardized residual. Calibrate per
   exact length; report both point and simultaneous gap coverage.
5. Preserve observed inputs, expose unsupported gaps and export provenance. Keep
   the reference, calibration and evaluation roles separate and make hidden-value
   leakage an explicit tested invariant.

Every item uses established ideas; we claim an original implementation and a
specific testable **system/method design**, not the invention of nearest-neighbor
imputation, bridge interpolation, local uncertainty or conformal prediction.
The empirical question is whether this particular design offers a useful
error/width/CPU tradeoff against linear and ExtraTrees baselines. The protocol's
no-bridge, constant-scale and pooled-calibration ablations test component value.
It is possible for all or part of that hypothesis to fail.

## What would be required for a paper

The current evidence can support a reproducible small-scale technical report.
It cannot establish state-of-the-art imputation. A paper-level study should add:

- a direct pattern-search baseline such as TKCM and a classical Kalman/seasonal
  baseline, with task-compatible input availability;
- probabilistic and modern learned baselines, including CSDI or an appropriate
  contemporary method, if the paper claims a broad uncertainty advantage;
- many independent datasets and chronological origins, preregistered selection
  rules, meaningful physical gap durations and a sensitivity analysis using only
  development data;
- simultaneous multiple outages, context corruption, unseen gap lengths,
  missing-not-at-random stress tests and a separate native-outage case study;
- rolling/adaptive calibration or a clearly justified dependence-aware coverage
  analysis, plus an assessment of downstream harm from false confidence;
- native Windows/16 GB measurements and a fair common hardware budget before
  making portability or efficiency comparisons.

The authors' repositories and toolkit examples already show that nearest
neighbors, pattern retrieval, imputation products and time-series uncertainty
are active, populated areas. A stronger novelty claim would require a focused
review of pattern-search and probabilistic imputation papers, not merely a longer
list of broad deep-learning citations.
