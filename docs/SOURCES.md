# Primary sources and access record

Accessed **2026-10-22**. Ten substantive sources informed the project. Links below
identify primary authors/maintainers rather than secondary summaries. “Read”
means the indicated resource was successfully downloaded and inspected in this
run; it does not imply every linked paper, benchmark or claim was independently
reproduced. The SAITS paper was read from its authors' own repository. Other
paper details are explicitly attributed to primary repository documentation.

## S1 — Numenta Anomaly Benchmark (NAB)

- Primary repository: <https://github.com/numenta/NAB>
- Pinned data description, **read**:
  <https://raw.githubusercontent.com/numenta/NAB/ea702d75cc2258d9d7dd35ca8e5e2539d71f3140/data/README.md>
- Pinned license, **read**:
  <https://raw.githubusercontent.com/numenta/NAB/ea702d75cc2258d9d7dd35ca8e5e2539d71f3140/LICENSE.txt>
- Repository overview, **read**:
  <https://raw.githubusercontent.com/numenta/NAB/master/README.md>
- Suggested source citation in that overview: Ahmad, S., Lavin, A., Purdy, S.,
  and Agha, Z. (2017), *Unsupervised real-time anomaly detection for streaming
  data*, DOI **10.1016/j.neucom.2017.04.070**.
- Verified relevance: real versus artificial corpus categories; office ambient
  temperature, AWS cluster CPU usage, and taxi passengers aggregated to
  30-minute buckets. The taxi description attributes underlying records to the
  NYC Taxi and Limousine Commission.
- The repository license is **MIT**, copyright 2014–2024 Numenta Inc.; preserve
  its notice. No per-file exception for the selected files was found in the
  inspected repository data documentation. This records the upstream corpus's
  distribution terms and attribution; original providers' separate terms were
  not independently audited. See `data/manifest.json` for exact URLs, SHA-256,
  row counts and preprocessing. Do not substitute older NAB license claims for
  the checked pinned license.

## S2 — imputeTS

- Moritz, S., and Bartz-Beielstein, T. (2017), *imputeTS: Time Series Missing
  Value Imputation in R*, **The R Journal 9(1)**,
  DOI **10.32614/RJ-2017-009**.
- Authors' README, **read**:
  <https://raw.githubusercontent.com/SteffenMoritz/imputeTS/master/README.md>
- Package metadata, **read**:
  <https://raw.githubusercontent.com/SteffenMoritz/imputeTS/master/DESCRIPTION>
- Evidence: univariate focus; interpolation, Kalman smoothing, seasonal
  decomposition and related available methods; package license GPL-3.
  imputeTS code is not incorporated into GapLens.

## S3 — ImputeGAP

- Nater, Q., Khayati, M., and Pasquier, J. (2025), *ImputeGAP: A Comprehensive
  Library for Time Series Imputation*, **arXiv:2503.15250** as cited in the
  primary repository.
- Authors' README, **read**:
  <https://raw.githubusercontent.com/eXascaleInfolab/ImputeGAP/main/README.md>
- Evidence: a substantial existing repair product and benchmark suite; six
  method families, block missingness, tuning, downstream evaluation and an
  explicitly stated Unix-compatible requirement. The pattern-search list
  includes TKCM, ST-MVL and DynaMMo. The README cites Wellenzohn et al. (2017),
  *Continuous Imputation of Missing Values in Streams of Pattern-Determining
  Time Series*, EDBT, pp. 330–341, for TKCM. That original TKCM paper was **not**
  independently accessed in this run, so no detailed claim about its algorithm
  or inferiority is made.

## S4 — BRITS

- Cao, W., Wang, D., Li, J., Zhou, H., Li, L., and Li, Y. (2018),
  *BRITS: Bidirectional Recurrent Imputation for Time Series*, **NeurIPS**.
- Authors' README, **read**:
  <https://raw.githubusercontent.com/caow13/BRITS/master/README.md>
- Publisher link supplied by the authors:
  <https://papers.nips.cc/paper/7911-brits-bidirectional-recurrent-imputation-for-time-series>
- Evidence: official PyTorch implementation and model-training commands.
  This is related work, not a baseline executed in our experiment.

## S5 — SAITS

- Du, W., Cote, D., and Liu, Y. (2023), *SAITS: Self-Attention-based Imputation
  for Time Series*, **Expert Systems with Applications 219**, 119619,
  DOI **10.1016/j.eswa.2023.119619**.
- Authors' README, **read**:
  <https://raw.githubusercontent.com/WenjieDu/SAITS/main/README.md>
- Authors' deposited paper, **downloaded, extracted and read**:
  <https://raw.githubusercontent.com/WenjieDu/SAITS/main/Paper_SAITS.pdf>
  (extracted heading: arXiv:2202.08516v5, July 2023).
- Evidence: multivariate imputation via two diagonally masked self-attention
  blocks, use of temporal/feature dependencies, and evaluation by artificially
  hiding observed entries. The paper's main missingness assumption is MCAR.
  The repository offers a PyPOTS workflow. We do not transfer its published
  performance claims to GapLens or claim to have reproduced them.

## S6 — CSDI

- Tashiro, Y., Song, J., Song, Y., and Ermon, S. (2021), *CSDI: Conditional
  Score-based Diffusion Models for Probabilistic Time Series Imputation*,
  **NeurIPS**, arXiv:2107.03502.
- Authors' README, **read**:
  <https://raw.githubusercontent.com/ermongroup/CSDI/main/README.md>
- Evidence: probabilistic imputation is established; repository commands expose
  training, pretrained inference and number-of-samples settings. Its healthcare
  and air-quality workflows were not executed for this project.

## S7 — EnbPI

- Xu, C., and Xie, Y. (2021), *Conformal Prediction Interval for Dynamic
  Time-Series*, **ICML / Proceedings of Machine Learning Research 139**.
- Authors' README, **read**:
  <https://raw.githubusercontent.com/hamrel-cxu/EnbPI/main/README.md>
- Publisher reference supplied by authors:
  <https://proceedings.mlr.press/v139/xu21h.html>
- Evidence: time-series conformal inference, bootstrap-based intervals, and
  comparison code for split/weighted conformal methods already exist. Authors
  also point to *Sequential Predictive Conformal Inference for Time Series*
  (ICML 2023) and time-adaptive residual quantiles.
- Direct publisher access returned a proxy HTTP 403 here. We inspected the
  authors' primary implementation documentation, not the publisher full text.

## S8 — Conformal prediction tutorial

- Angelopoulos, A. N., and Bates, S. (2021), *A Gentle Introduction to Conformal
  Prediction and Distribution-Free Uncertainty Quantification*,
  **arXiv:2107.07511** (citation as supplied by the authors).
- Authors' accompanying README, **read**:
  <https://raw.githubusercontent.com/aangelopoulos/conformal-prediction/main/README.md>
- Evidence: calibration-based regression bands, conformalized quantile
  regression and a time-series/distribution-shift example are established
  components. The project uses the conventional finite-sample rank correction;
  the exchangeability requirement is not established by our time split.

## S9 — MAPIE

- Maintainers' README, **read**:
  <https://raw.githubusercontent.com/scikit-learn-contrib/MAPIE/master/README.md>
- Product: *MAPIE — Model Agnostic Prediction Interval Estimator*.
- Evidence: existing Python wrappers support regression, classification and time
  series; the README explicitly discusses assumptions and exchangeability tests.
  GapLens does not claim novelty for exposing uncertainty through an API.
  MAPIE is related work, not a dependency or executed baseline.

## S10 — Scikit-learn ExtraTrees documentation

- Maintainers' ensemble documentation, **read**:
  <https://raw.githubusercontent.com/scikit-learn/scikit-learn/main/doc/modules/ensemble.rst>
- Section: **Extremely Randomized Trees**. It explains random candidate split
  thresholds and cites Geurts, P., Ernst, D., and Wehenkel, L. (2006),
  *Extremely randomized trees*, **Machine Learning 63(1)**, pp. 3–42.
- Evidence: implementation and algorithm provenance of our strong practical
  baseline. The documentation inspected is the current upstream source; actual
  executed package versions are recorded in the dependency lock and run metadata.

## Access constraints and reproducibility

The initially considered UCI Air Quality route
on `archive.ics.uci.edu` was blocked by the configured
network proxy. No access restriction was bypassed, and no UCI observations or
license assertions are used in the final experiment. The selected alternative
was the openly distributed **official** NAB repository; files were downloaded,
parsed, inspected and hashed before the main experiment.

Direct publisher availability was not necessary to verify the author-repository
resources above. No papers were fabricated or counted as fully read merely
because their title appeared in another source. This source review does not
establish exhaustive novelty, superior performance, or a publication outcome.
