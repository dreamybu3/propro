# Project selection and alternatives

Decision: build **GapLens**, an auditable offline gap-reconstruction tool for
univariate monitoring time series. The product must retain observed values,
explain reconstructed blocks, export results and show empirically calibrated
uncertainty. It must run on CPU without paid services.

This document compares exactly three candidates. It records the rationale and
primary-source checks made during this development session (22 October 2026).
The selected data were downloaded, parsed and licensed before committing to the
implementation. Checks of alternative tools continued while GapLens was being
implemented; this is not a claim that all three candidates underwent full
feasibility studies or experiments. Candidate 2 and 3 were not implemented.

## Comparison

| Candidate | Concrete user and problem | Proposed technical core | Research question and evaluation | Resources and principal risk |
|---|---|---|---|---|
| **1. Offline monitoring-gap reconstruction — selected** | An analyst receives a regularly sampled sensor or operational CSV containing contiguous outages. Filling every gap with a smooth line can hide real variation, while a point estimate alone gives no indication of uncertainty. | Historical context retrieval, endpoint-corrected analog trajectories, disagreement/novelty-dependent scale, and gap-length-specific calibration. Export observed/reconstructed status, bands and audit metadata. | Can this mechanism improve blocked-gap reconstruction and the coverage/width tradeoff against interpolation and a stronger tree baseline? Chronological training/calibration/test splits, real observations hidden in blocks, fixed seeds and component ablations. | Tens of thousands of samples, CPU and modest memory. Main risks: abrupt regime changes, hidden events, autocorrelation invalidating exchangeability, and weak analog matches. Empirical results may be negative. |
| **2. Leakage and near-duplicate audit for tabular ML** | A researcher wants to know whether related or nearly repeated records cross train/test boundaries and inflate evaluation. | Mixed-type similarity graph, interpretable edge reasons, group-aware partition repair and a reproducible before/after evaluation. | Does repair reduce contamination-driven optimism without excessive data loss, beyond exact hashing and existing near-neighbor detection? Need independently known entities/duplicates, group-held-out evaluation and controlled injected contamination. | CPU feasible for moderate tables using sparse neighbor search. Biggest risk: no reliable real-world duplicate/entity ground truth; similarity is not proof of leakage. A graph view alone would not be a research contribution. |
| **3. Dependency-upgrade planning under a change budget** | A maintainer has vulnerable direct/transitive packages but cannot safely upgrade everything at once. | Explicit constrained optimization of candidate upgrades and dependency constraints, reporting risk removed, change cost and alternative plans. | Does a budgeted optimizer improve vulnerability reduction per verified compatible change against severity-first, greedy return-on-investment and existing remediation? Test historical lockfiles with time-correct advisory data and actual package resolution/tests. | Optimization itself is CPU feasible; registry access, compatibility testing and reconstructing historical metadata dominate effort. Severity is not exploitability; version distance is not a reliable breakage-cost label. Existing tools already do substantial remediation planning. |

## Closest existing solutions and what remains to prove

### 1. Gap reconstruction

[imputeTS](https://github.com/SteffenMoritz/imputeTS) explicitly supports
univariate time-series imputation, including interpolation, Kalman smoothing,
seasonal methods and missingness diagnostics. Its verified README is evidence
that this is an established problem, not an empty product category.
[PyPOTS](https://github.com/WenjieDu/PyPOTS) provides a broad collection of
methods for partially observed multivariate time series, including imputation
models. The existence of these libraries precludes claims that imputation,
context-based reconstruction or combining methods is itself novel.

GapLens tests one narrower, explicit mechanism with an auditable CLI workflow:
how much endpoint correction, local scale and length-specific calibration help
when paired with historical context retrieval. These are hypotheses about a
particular implementation and tradeoff, not demonstrated limitations of every
existing imputer. The current experiment does not reproduce imputeTS, PyPOTS or
all state-of-the-art methods. See [PROTOCOL.md](PROTOCOL.md) for fixed criteria
and the research report for measured outcomes and needed stronger comparisons.

**Data feasibility.** The official [Numenta Anomaly Benchmark
repository](https://github.com/numenta/NAB) provides downloadable real and
artificial series. Only three files explicitly described as real in its
[data documentation](https://github.com/numenta/NAB/blob/ea702d75cc2258d9d7dd35ca8e5e2539d71f3140/data/README.md)
are used: NYC taxi passenger counts (10,320 rows), AWS CPU utilization (18,050)
and ambient office temperature (7,267 raw observations). The pinned repository
has an [MIT license](https://github.com/numenta/NAB/blob/ea702d75cc2258d9d7dd35ca8e5e2539d71f3140/LICENSE.txt).
Attribution, source hashes, sampling and preprocessing are recorded in
`data/manifest.json`. The upstream benchmark was designed for anomaly detection;
our gap masking is a new experimental use, not an official NAB imputation task.
Originally considered UCI endpoints were blocked by this environment's network
policy. No access restrictions were bypassed.

### 2. Leakage audit

[Cleanlab](https://github.com/cleanlab/cleanlab) is a particularly close existing
solution. Its actual
[near-duplicate issue manager source](https://github.com/cleanlab/cleanlab/blob/master/cleanlab/datalab/internal/issue_manager/duplicate.py)
defines near-duplicate groups using a nearest-neighbor graph, records nearest
neighbor identities/distances, and makes duplicate relationships reciprocal.
Thus simply finding similar rows and displaying an interpretable graph would
overlap substantially with an established Apache-2.0 component. A stronger
project would need to demonstrate reliable split-repair decisions and downstream
bias reduction. Whether such repair is useful for a particular domain remains
an untested hypothesis here; no blanket absence of this functionality elsewhere
is claimed.

**Data feasibility.** The official
[Palmer Penguins repository](https://github.com/allisonhorst/palmerpenguins)
README states that its data are released under CC0. Its
[CSV](https://raw.githubusercontent.com/allisonhorst/palmerpenguins/main/inst/extdata/penguins.csv)
was fetched and parsed successfully: 344 rows, 8 columns. This verifies a small
licensed demonstration input, **not** an adequate leakage benchmark. The file
does not establish real duplicate identities. Injecting duplicates into it would
provide only controlled synthetic-contamination evidence. A stronger real audit
corpus and independently verified labels were not established in this session.

### 3. Dependency planning

[OSV-Scanner](https://github.com/google/osv-scanner) already offers guided
remediation. Its current README explicitly lists upgrade recommendations based
on dependency depth, minimum severity, fix strategy and return on investment,
with supported npm and Maven workflows. This is a direct competitor to a naive
budget-prioritized planner. Its code is Apache-2.0 licensed.
[Renovate](https://github.com/renovatebot/renovate) discovers dependencies and
automates upgrade pull requests; its README identifies the software as
AGPL-3.0-only. A standalone planner could propose a more explicit constrained
objective and explanations, but superiority to existing remediation is unproven
and must be established rather than assumed.

**Data feasibility.** The official
[Python Packaging Advisory Database](https://github.com/pypa/advisory-database)
documents advisory files in an OSV-compatible YAML representation; its
[LICENSE](https://github.com/pypa/advisory-database/blob/main/LICENSE) is Creative
Commons Attribution 4.0. The README and license were retrieved successfully.
The direct OSV API was blocked in this environment. No complete historical
advisory/lockfile/test corpus was downloaded or validated, and permission for
individual project fixtures would need to be checked separately. This is a
larger evidence gap than for candidate 1.

## Why GapLens

GapLens has the strongest verified path from licensed real observations to a
complete useful workflow and an honest falsifiable comparison within available
CPU resources. Its own technical mechanism can be isolated in ablations, and
negative results still reveal when interpolation is safer than context analogs.
The choice is not based on the user's degree title or on an assumed publication
promise. The resulting evidence is deliberately limited to offline isolated
gaps in three public series. A publishable claim would need broader data,
stronger comparators, more missingness mechanisms and better handling of shift.

## Verification scope

Primary repository sources above were read directly over HTTPS during the
session. Product documentation endpoints for Cleanlab, Renovate and OSV, plus
the UCI and OSV API endpoints, returned proxy access denials; accessible official
repository source was used where sufficient. No web-wide exhaustive prior-art
search, live deployment of alternative tools or novelty certification is claimed.
The selected method's fuller literature context belongs in the research report.
