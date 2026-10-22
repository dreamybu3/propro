# GapLens v2: verified literature and source ledger

Access date: **2026-10-22 UTC**. This ledger records what was actually read, rather than treating a repository README as evidence for an entire paper. It supplements the frozen [v1 source ledger](../SOURCES.md); v1's access claims should not be retroactively expanded. Sources are referenced by `[R#]` in [RELATED_WORK.md](RELATED_WORK.md).

Pinned GitHub source files were inspected at the commits below. For files initially downloaded from a branch URL, the pinned version was downloaded and compared byte for byte. PDFs were downloaded and text extracted; AnDA was obtained from an author's repository and the two ICML papers from the publisher's own GitHub repository. The publisher-facing domains, arXiv, the TKCM author site and the SSA author PDF host returned proxy HTTP 403 responses in this environment. Successful access to the primary publisher repository is reported precisely, without claiming access to blocked pages. Papers and external source trees are not redistributed with GapLens; these links and checksums identify the inspected material.

## R1 — TKCM: non-overlapping historical-pattern imputation

**Citation:** Kevin Wellenzohn, Michael H. Böhlen, Anton Dignös, Johann Gamper, Hannes Mitterer (2017). *Continuous Imputation of Missing Values in Streams of Pattern-Determining Time Series*. Proceedings of EDBT 2017, 330–341.

**Access level:** substantive **third-party implementation**, explicitly attributed to original author code; bibliographic details from that project's reference list. The original paper and author code download were not independently obtained. Do not cite this as a full primary-paper verification.

Inspected ImputeGAP commit `a18d5c5f619d05dced8348619150b4a06e138f8d`:

- [TKCM.cpp](https://github.com/eXascaleInfolab/ImputeGAP/blob/a18d5c5f619d05dced8348619150b4a06e138f8d/imputegap/wrapper/AlgoCollection/Algorithms/TKCM.cpp): `actionTkcm`, dynamic-programming recurrence, backtracking and averaging; `performRecovery` reference-channel access. Header identifies the original Wellenzohn author site and states that the code was adapted to C++.
- [TKCM.h](https://github.com/eXascaleInfolab/ImputeGAP/blob/a18d5c5f619d05dced8348619150b4a06e138f8d/imputegap/wrapper/AlgoCollection/Algorithms/TKCM.h): constants and API.
- [README reference 11](https://github.com/eXascaleInfolab/ImputeGAP/blob/a18d5c5f619d05dced8348619150b4a06e138f8d/README.md): authors, title, venue and pages.

**Verified:** squared differences over trailing reference patterns, sum over reference channels, Euclidean dissimilarity, exclusion of overlapping patterns via predecessor `j − l`, associated target-value mean. The inspected wrapper takes reference values from three columns. **Not verified:** original-paper experimental results, all original supported settings, or its full theorem/algorithm description. The code supports the prior-art warning about temporal diversity, but claims about the original method are qualified by this access limitation.

## R2 — AnDA: analog correction and retrospective assimilation

**Citation:** Redouane Lguensat, Pierre Tandeo, Pierre Ailliot, Manuel Pulido, Ronan Fablet (2017). *The Analog Data Assimilation*. Monthly Weather Review **145**(10), 4093–4107. DOI: [10.1175/MWR-D-16-0441.1](https://doi.org/10.1175/MWR-D-16-0441.1).

**Access level:** full primary paper and author implementation. Author repository commit `db198f17785c3d19f74a00f946cfffa5ee4175ab`:

- [Full paper PDF](https://github.com/ptandeo/AnDA/blob/db198f17785c3d19f74a00f946cfffa5ee4175ab/lguensat_2017_MWR.pdf): sections 2–4 for setting/operators/filtering/smoothing; section 5 for stated Lorenz experiment scope, catalog size and catalog mismatch studies.
- [AnDA_analog_forecasting.py](https://github.com/ptandeo/AnDA/blob/db198f17785c3d19f74a00f946cfffa5ee4175ab/AnDA_codes/AnDA_analog_forecasting.py): KDTree neighbors, Gaussian distance weights, local-constant/increment/local-linear cases, weighted covariance and sampling.
- [AnDA_data_assimilation.py](https://github.com/ptandeo/AnDA/blob/db198f17785c3d19f74a00f946cfffa5ee4175ab/AnDA_codes/AnDA_data_assimilation.py): observed-coordinate selection; forward ensemble update and backward `AnEnKS` pass.

**Verified:** available catalog plus partial/noisy observations; multiple analog-regression variants; incremental `query + successor − analog` correction; future observations participate in smoother reconstruction. **Limit:** its paper's synthetic chaotic-system evidence does not establish accuracy on univariate GapLens streams; full AnDA was not benchmarked here merely by reading it. Repository is GPL-3.0; its implementation was inspected, not copied into GapLens.

## R3 — SSA: two-sided gap filling and trajectory-subspace projection

**Citations:**

- Nina Golyandina, E. Osipov (2007). *The “Caterpillar”-SSA method for analysis of time series with missing values*. Journal of Statistical Planning and Inference **137**(8), 2642–2653. The inspected package documentation gives the authors as N. Golyandina and E. Osipov.
- Nina Golyandina, Anton Korobeynikov, Anatoly Zhigljavsky (2018). *Singular Spectrum Analysis with R*. Springer, Use R! series.

**Access level:** Rssa package-author implementation, method documentation and citation metadata; the linked 2007 author PDF was blocked, and neither full publication was read in this review. Repository commit `bab3ba18ba8dce3ec3c4cb2fa324b17930f50e99`:

- [R/gapfill.R](https://github.com/asl/rssa/blob/bab3ba18ba8dce3ec3c4cb2fa324b17930f50e99/R/gapfill.R): `.fill.in`, `gapfill.1d.ssa`, signal-subspace projections, trajectory reconstruction.
- [man/gapfill.Rd](https://github.com/asl/rssa/blob/bab3ba18ba8dce3ec3c4cb2fa324b17930f50e99/man/gapfill.Rd): sequential/simultaneous mechanisms, default linear weights for left/right predictions, insufficient-complete-observation warning, exact 2007 title/venue/pages and 2018 algorithms 3.8/3.9.
- [inst/CITATION](https://github.com/asl/rssa/blob/bab3ba18ba8dce3ec3c4cb2fa324b17930f50e99/inst/CITATION): 2018 book author/title metadata.

**Verified:** implementation contains genuine two-sided reconstruction, not just forecasting from the left. **Limit:** our conditional trajectory PCA would share a subspace motivation, not reproduce either package mode; the R implementation was not executed in this review.

## R4 — DynaMMo: latent dynamical-system imputation

**Citation:** Lei Li, James McCann, Nancy S. Pollard, Christos Faloutsos (2009). *DynaMMo: Mining and Summarization of Coevolving Sequences with Missing Values*. Proceedings of the 15th ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, 507–516. DOI: [10.1145/1557019.1557078](https://doi.org/10.1145/1557019.1557078).

**Access level:** original author MATLAB implementation and its citation metadata; full paper not obtained. Author repository commit `eccaca7430b853001918449e6192ef0c274a97e5`:

- [learn_lds_dynammo.m](https://github.com/lileicc/dynammo/blob/eccaca7430b853001918449e6192ef0c274a97e5/dynammo/learn_lds_dynammo.m): model definition, observed-mask handling, interpolation initialization, forward/backward/MLE loop, updating only missing entries.
- [backward.m](https://github.com/lileicc/dynammo/blob/eccaca7430b853001918449e6192ef0c274a97e5/dynammo/backward.m) and [estimate_missing.m](https://github.com/lileicc/dynammo/blob/eccaca7430b853001918449e6192ef0c274a97e5/dynammo/estimate_missing.m): smoothed latent expectation conditioned on the sequence and projection to observations.
- [README](https://github.com/lileicc/dynammo/blob/eccaca7430b853001918449e6192ef0c274a97e5/README.md): author list, paper title, KDD 2009 and DOI link. Page range is corroborated by ImputeGAP's bibliography at `[R1]`'s pinned revision.

**Verified:** dynamic latent-state mechanism, iterative reconstruction, explicit observed mask accepted; zero-as-missing fallback exists when no NaNs and no supplied mask. **Limit:** this default behavior is an integration concern, not an asserted statistical defect. Neither the original benchmark nor a GapLens DynaMMo run was reproduced by this review.

## R5 — Structural Kalman smoothing

**Citation:** Steffen Moritz, Thomas Bartz-Beielstein (2017). *imputeTS: Time Series Missing Value Imputation in R*. The R Journal **9**(1). DOI: [10.32614/RJ-2017-009](https://doi.org/10.32614/RJ-2017-009).

**Access level:** package-author implementation and detailed method docstrings; full imputeTS paper not read here. Inspected:

- [imputeTS R/na_kalman.R](https://github.com/SteffenMoritz/imputeTS/blob/bca3fcd312d531a0b78c671ad0147ae086a35d0a/R/na_kalman.R), commit `bca3fcd312d531a0b78c671ad0147ae086a35d0a`: `StructTS` / `auto.arima` model choices, `smooth=TRUE` default, `KalmanSmooth` vs `KalmanRun`, projection through the observation matrix and replacement of missing positions only.
- [statsmodels structural.py](https://github.com/statsmodels/statsmodels/blob/30df665e220dcb7b695d5b5611ec83072e5f5234/statsmodels/tsa/statespace/structural.py), commit `30df665e220dcb7b695d5b5611ec83072e5f5234`: model equations/documentation for local level, local linear trend, seasonal and frequency-seasonal states; configuration and state representation.

The statsmodels source cites **James Durbin and Siem Jan Koopman (2012), *Time Series Analysis by State Space Methods*, second edition, Oxford University Press**. That book was not read in this review; it is the implementation's attribution, not evidence of a completed book review.

**Verified:** imputation using a smoother is an existing practical baseline; state-space representation and seasonal components are documented in the inspected Python implementation. **Limit:** a separately implemented GapLens smoother must be validated on its own; reading these sources does not certify numerical equivalence or grant Gaussian coverage when a fitted state-space model is misspecified.

## R6 — Analog ensembles

**Citation:** Luca Delle Monache et al. (2013). *Probabilistic Weather Prediction with an Analog Ensemble*. Monthly Weather Review **141**(10), 3498–3516. DOI: [10.1175/MWR-D-12-00281.1](https://doi.org/10.1175/MWR-D-12-00281.1).

**Access level:** PAnEn implementation and its own bibliographic attribution; the 2013 full paper was not obtained. PAnEn is an implementation by Weiming Hu, Guido Cervone and collaborators, not described here as the 2013 paper's original code. Repository commit `40f9b1e5883da49db1c7d3eaf09195c6345cb358`:

- [README](https://github.com/Weiming-Hu/AnalogsEnsemble/blob/40f9b1e5883da49db1c7d3eaf09195c6345cb358/README.md): data setting and paper title/venue/pages/DOI; software citation **Hu, Cervone, Clemente-Harding and Calovi (2019), Parallel Analog Ensemble**, DOI [10.5281/zenodo.3384321](https://doi.org/10.5281/zenodo.3384321).
- [CAnEn/src/AnEnIS.cpp](https://github.com/Weiming-Hu/AnalogsEnsemble/blob/40f9b1e5883da49db1c7d3eaf09195c6345cb358/CAnEn/src/AnEnIS.cpp): forecast/observation pairing, similarity sorting, disallowing self-comparison and the `prevent_search_future` control.

**Verified:** probabilistic ensembles based on historical analog outcomes already exist; this package consumes forecasts and corresponding observations. **Limit:** not evidence that its uncertainty is block-conformal, nor a direct scalar-gap baseline. The inspected bibliography abbreviates the 2013 author list as “et al.”; this ledger does likewise rather than supplying an unchecked expansion.

## R7 — Temporal exclusion in nearest-match search

**Software:** STUMPY, pinned commit `248e34409dd09feac1d82422fa64ea887174ce13`.

**Access level:** implementation-author code, specifically [_find_matches and apply_exclusion_zone in stumpy/core.py](https://github.com/TDAmeritrade/stumpy/blob/248e34409dd09feac1d82422fa64ea887174ce13/stumpy/core.py).

**Verified:** the function repeatedly chooses a closest match and suppresses indices in an exclusion zone before selecting the next; docstring explicitly describes this behavior. This is a direct code-level precedent for greedy temporal separation. **Limit:** no claim that this software is an imputation method or that it proves independence/calibrated uncertainty. A separate history of Theiler windows or matrix-profile papers is not asserted as verified by this code inspection.

## R8 — EnbPI: residual feedback and assumptions

**Citation:** Chen Xu, Yao Xie (2021). *Conformal prediction interval for dynamic time-series*. Proceedings of the 38th International Conference on Machine Learning, PMLR **139**, 11559–11569.

**Access level:** full primary paper from publisher repository; author implementation. Inspected:

- [Publisher PDF at pinned revision](https://raw.githubusercontent.com/mlresearch/v139/fe61af4b98a13715b69788a4a5d30260ecf13c87/xu21h/xu21h.pdf), repository commit `fe61af4b98a13715b69788a4a5d30260ecf13c87`: sections 2–4, algorithm, assumptions 1/2, theorem 1, missing-feedback discussion and change-point limitations.
- [Publisher bibliographic record](https://github.com/mlresearch/v139/blob/fe61af4b98a13715b69788a4a5d30260ecf13c87/_posts/2021-07-01-xu21h.md): title, authors, volume and pages.
- [Author PI_class_EnbPI.py](https://github.com/hamrel-cxu/EnbPI/blob/60cd5b7530eb954b02ae94da967111f5b5c3c01b/PI_class_EnbPI.py), author commit `60cd5b7530eb954b02ae94da967111f5b5c3c01b`: bootstrap models, out-of-bag residuals, sliding interval updates and treatment of missing feedback.

**Verified:** sequential bootstrap-residual method and explicit assumptions for approximate marginal coverage. The original paper notes that its deployed interval does not add its theoretical coverage-error bound. **Limit:** no claim that a GapLens recent-block quantile implements EnbPI or inherits its theorem; no independent reproduction of EnbPI benchmarks.

## R9 — SPCI: conditional residual quantiles

**Citation:** Chen Xu, Yao Xie (2023). *Sequential Predictive Conformal Inference for Time Series*. Proceedings of the 40th International Conference on Machine Learning, PMLR **202**, 38707–38727.

**Access level:** full primary paper from publisher repository:

- [Publisher PDF](https://raw.githubusercontent.com/mlresearch/v202/3c987f88bec5665cb6e1fef60e6e4d9401148d6a/xu23r/xu23r.pdf), pinned commit `3c987f88bec5665cb6e1fef60e6e4d9401148d6a`: sections 2–4 for conditional residual-quantile method and proposition/theorem statements; Appendix A for assumptions.
- [Publisher metadata](https://github.com/mlresearch/v202/blob/3c987f88bec5665cb6e1fef60e6e4d9401148d6a/_posts/2023-07-03-xu23r.md): title, authors, volume and pages.

**Verified:** quantile prediction from residual history; distinction between exchangeable finite-sample marginal validity and asymptotic conditional validity with dependence and quantile-estimation assumptions. **Limit:** a fixed-size recent empirical quantile is not SPCI. The source review checked theorem conditions, not a new proof or a reproduction of all experiments.

## R10 — Standard calibration and joint trajectory coverage

**Citations:**

- Anastasios N. Angelopoulos, Stephen Bates (2021 preprint). *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification*. arXiv:2107.07511. The preprint identifier/year are used deliberately rather than assigning unchecked journal metadata.
- Kamilė Stankevičiūtė, Ahmed M. Alaa, Mihaela van der Schaar (2021). *Conformal time-series forecasting*. Advances in Neural Information Processing Systems.

**Access level:** both author implementations; full papers not obtained in this review.

- Angelopoulos/Bates author repository, commit `0426de356dbfa71c4c46be81d1973255ac66d050`: [meps-uncertainty-scalar.ipynb](https://github.com/aangelopoulos/conformal-prediction/blob/0426de356dbfa71c4c46be81d1973255ac66d050/notebooks/meps-uncertainty-scalar.ipynb) for normalized residual scores and finite-sample quantile correction; [weather-time-series-distribution-shift.ipynb](https://github.com/aangelopoulos/conformal-prediction/blob/0426de356dbfa71c4c46be81d1973255ac66d050/notebooks/weather-time-series-distribution-shift.ipynb) for time-varying weighted scores. We use the exact order-statistic definition in our own construction, not a claim of byte-identical quantile-library behavior.
- CFRNN author repository, commit `07e0e11b331a711d961fb58bafdee9f0032cd666`: [models/cfrnn.py](https://github.com/kamilest/conformal-rnn/blob/07e0e11b331a711d961fb58bafdee9f0032cd666/models/cfrnn.py) for horizon-specific scores, `alpha/horizon` Bonferroni adjustment and joint coverage; [utils/performance.py](https://github.com/kamilest/conformal-rnn/blob/07e0e11b331a711d961fb58bafdee9f0032cd666/utils/performance.py) for separate individual/joint evaluation; [README citation](https://github.com/kamilest/conformal-rnn/blob/07e0e11b331a711d961fb58bafdee9f0032cd666/README.md).

**Verified:** normalized-score calibration is established; sequentially adapted score weights have precedents; trajectory-wide coverage differs from coordinate coverage and is explicitly evaluated in author code. **Limit:** CFRNN's Bonferroni construction is not GapLens's maximum-score construction. No exact finite-sample claim for dependent GapLens blocks follows from citing these sources. SPCI `[R9]` supplies a directly inspected primary-paper statement of the exchangeability requirement for ordinary split conformal.

## Download integrity

SHA-256 checksums of the most consequential inspected PDFs/source files:

| Artifact | SHA-256 |
|---|---|
| AnDA author PDF `[R2]` | `40869af1a183ef4da7343ff4249e10820658be0a04a9dee1811a047893f80d58` |
| EnbPI publisher PDF `[R8]` | `d7f3850a67f7bc7d2326d2bff426130184272c802af6ae85e1d958f804b0568e` |
| SPCI publisher PDF `[R9]` | `c9d75513be1a1c16e089cd27a9b7d35516b658c1d4ef0077c881c5d4f83bf66b` |
| TKCM.cpp `[R1]` | `c89526196476940da7de82f32a11b486507ad4f47a34c737da7a011f29ad06a3` |
| TKCM.h `[R1]` | `eae2c5968c7bada68a78f1fbae21cb72977b05b373180a5ed236a0206f84a51e` |
| imputeTS na_kalman.R `[R5]` | `7d0b4b0d5580305522d52a0d38421bf9a38c80faad7c5418ef3e0fdf91824050` |
| statsmodels structural.py `[R5]` | `291e4a557b4c1369be45e6dfb534e00d3b6df82c5098d3565e335f6af6ebad71` |
| STUMPY core.py `[R7]` | `eb8f9e28d9580962be67672f4866908f0e2dc1bd794c0f7a7dd980bab87d005b` |

Use the raw links for PDFs; for a pinned GitHub source link, its **Raw** view yields the exact bytes. For example:

```bash
curl -L 'https://raw.githubusercontent.com/mlresearch/v139/fe61af4b98a13715b69788a4a5d30260ecf13c87/xu21h/xu21h.pdf' -o enbpi.pdf
python -c "import hashlib; print(hashlib.sha256(open('enbpi.pdf','rb').read()).hexdigest())"
```

Reading code does not authorize copying it under GapLens's license. No external implementation or restricted paper PDF was copied into the project by this review. Source code and bibliographic facts were used to identify mechanisms, comparison requirements and the limits of novelty/coverage claims.
