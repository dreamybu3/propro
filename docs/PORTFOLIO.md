# Portfolio evidence and a path toward a paper

## Accurate positioning

GapLens is an AI-assisted research software project with an implemented numerical method, a complete CSV-to-report workflow, a fixed evaluation protocol and executed measurements. It is not a publication, production deployment, invention of conformal prediction, or evidence that the owner personally conducted all development. Review the source, reproduce the study and make your own justified extension before claiming individual ownership in an application or interview.

The current artifact demonstrates competence worth learning: avoiding hidden-target leakage, preserving provenance, matching an uncertainty metric to an entire missing block, separating empirical results from guarantees, and reporting a failed hypothesis. These are stronger claims than a generic model wrapper.

## Three evidence-based CV lines

The following wording describes the repository. Use first-person achievement language only after personally reproducing and being able to defend the relevant work; disclose AI assistance when asked or required.

- **GapLens — AI-assisted research software:** CPU-only Python tool for offline monitoring-gap reconstruction, with historical-analog endpoint conditioning, whole-gap uncertainty calibration, and auditable CSV/JSON/interactive HTML exports.
- Reproducible study artifact covering **648 masked gaps and 3,888 method cases** across three real NAB streams; AnalogBridge achieved **51.8% lower macro normalized MAE than linear** and **14.4% lower than ExtraTrees**, with documented temporal-split and artificial-missingness limits.
- Explicit uncertainty failure analysis: **85.8% whole-gap coverage at a 90% target**, only **78.7% on NYC taxi**, and wider adaptive bands than the ablation; includes automated numerical/integration tests, preserved raw predictions, and a **259 MiB** measured Linux process peak for the benchmark.

These lines claim neither users nor accepted papers, and do not turn a small benchmark into general superiority. If a short CV cannot include all caveats, link the report and retain “three streams,” “masked gaps,” and “AI-assisted.”

## Existing evidence

- Real, licensed and checksum-pinned data; runnable input examples and actual output artifacts.
- Original implementation of a specific retrieval/bridge/scale mechanism with clear library attribution.
- A preserved pre-experiment protocol, chronological split, same masks for all methods, independent calibration and ablations.
- Complete measurements and a negative width result retained alongside positive reconstruction results.
- Linux installation, product integration, tests and browser verification recorded in `VALIDATION.md`.

## A defensible research direction

**Question:** can shift-aware analog selection plus rolling calibration improve conditional whole-gap coverage without intervals becoming operationally useless?

1. **Review the closest pattern-search methods.** Read TKCM and related stream-imputation papers directly, and compare formulations; imputeTS/ImputeGAP already solve much of the surrounding product problem. Decide whether the contribution is methodological or a narrower systems/benchmark result.
2. **Freeze an independent evaluation design.** Obtain many independent operational streams; reserve future chronological origins and at least one unseen data source. Choose gap durations in physical time and separate development-only tuning from final evaluation. Do not reuse this test split to report a newly tuned method as unbiased.
3. **Strengthen baselines.** Add task-compatible seasonal/Kalman and TKCM baselines, and a probabilistic/learned method if making a broad uncertainty claim. Equalize observations available on both sides, calibration budgets, and compute limits.
4. **Target the observed failure.** Compare rolling versus static quantiles, stratification by gap duration and context novelty, and bounded-support intervals. Evaluate conditional coverage, width and downstream decision loss; do not reward narrow bands that miss hidden bursts.
5. **Expand missingness and uncertainty analysis.** Study simultaneous outages, damaged context, MNAR stress tests and a genuine outage case study. Use time/dependence-respecting interval estimates and independent series as the unit of generalization where possible. Mask-seed ranges are not confidence intervals.
6. **Demonstrate practical usability.** Measure native Windows performance on the actual 16 GB laptop, record startup/latency/memory separately, and conduct a small analyst study with an approved protocol if human participants are involved.

The current evidence is sufficient for a transparent technical report and portfolio demonstration. A workshop, reproducibility or applied methods submission could become plausible after these additions, depending on what the results support. No venue fit, acceptance or publication is guaranteed.

## Demonstration and interview preparation

The precise 90-second/5-minute demo script and twelve technical questions are in [LEARNING_GUIDE.md](LEARNING_GUIDE.md). Emphasize one successful repair and one retained failure. Show the original-value preservation invariant, the source of interval calibration, and the failed hypothesis before discussing future improvements.
