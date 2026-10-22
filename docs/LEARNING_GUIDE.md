# GapLens: algorithm guide, demonstration, and research roadmap

This guide traces the reconstruction algorithm, provides runnable demonstration
scripts, and explains the main design decisions and experimental limitations.
It also outlines the evidence needed for a further research study.

## A practical route through the code

1. Read `data/README.md`, `docs/PROTOCOL.md`, and `docs/v2/PROTOCOL.md`. Explain the difference between
   real signals with artificially hidden blocks and genuine missing ground truth.
2. Trace one interval in `src/gaplens/data.py`: a missing run is `[start, end)`,
   and a context consists of finite samples outside that run.
3. In `src/gaplens/core.py`, manually calculate the bridge correction for a
   three-point historical gap. Check that a query shifted by a constant receives
   the corresponding endpoint correction.
4. Read `src/gaplens/calibration.py`. Compute the order statistic by hand for
   ten scores and `alpha=0.1`; the rank is ten, not the interpolated 90th percentile.
5. Follow `repair()` in `src/gaplens/pipeline.py` from the two validated CSVs to the
   three exported artifacts. Identify each branch that leaves a gap unresolved.
6. Run the tests, reproduce the fixed experiment, and explain one **failure** as
   well as any favorable result. Change parameters only in a separately labeled
   exploratory run; do not rewrite the fixed study after seeing its test results.
7. Read `models_v2.py` beside the preserved `_core_v1.py` research control.
   Explain separated-window selection, the seasonal/Kalman/PCA comparators, and
   why these known constructions do not establish algorithmic novelty.
8. Inspect the development selection and frozen masks before reading the v2
   outcome tables. Identify what data selected parameters, what data calibrated
   intervals, and what data supplied the final comparison.

## Ninety-second demonstration

Use a terminal in the repository root after the documented installation. The
commands below use `uv run`, which selects the project's pinned environment.

```console
uv run gaplens repair --reference examples/reference.csv --input examples/with_gaps.csv --output demo-output --require-complete
uv run gaplens repair --reference examples/reference.csv --input demo-output/repaired.csv --output rejected-reimport
```

Use a new `demo-output` path. The bundled examples already contain the fixed
demonstration; no regeneration or overwrite is needed. The first command should
reconstruct **3/3 gaps and 42/42 missing values**, preserve **2,022 observations**,
and return 0. The second command intentionally returns **2**: a repair export is
not a new measurement input. It creates no replacement report and leaves the
first result unchanged. Display the code with `$LASTEXITCODE` in PowerShell or
`echo $?` in Bash immediately after that command.

The examples come from the real NYC taxi series. `examples/ground_truth.csv` is
only for verification; neither repair command receives it. To regenerate an
independent copy, use `scripts/make_demo.py --output new-examples`, preserving
`examples/` and `results/demo/` as v1 evidence.

Suggested narration:

- **0–20 seconds:** “Monitoring exports can contain missing blocks. GapLens
  reconstructs eligible blocks from earlier similar patterns and the observations
  on both sides. It keeps the result distinguishable from actual measurements.”
- **20–45 seconds:** Run the first command and show its repaired/unresolved counts.
  Open `demo-output/report.html` directly in a browser. Select a gap and show the
  estimated path, band, and supporting historical neighbors.
- **45–70 seconds:** Inspect `demo-output/repaired.csv` and `report.json`. Point
  out preserved observations, per-gap status, calibration count, and provenance.
  Run the second command and show the explicit rejection: the 42 estimates must
  not become measurements merely because they were exported.
- **70–90 seconds:** State that bands are empirical estimates, not a guaranteed
  90% accuracy claim. Point to the separate v2 report for held-out comparisons,
  including failures. The default remains the v1 analog rule because the diverse
  candidate failed its development selection criterion.

This is a local-file workflow, without a public deployment or a localhost link.
The report can be opened on Windows by double-clicking the HTML file; the project
does not require a server for the main scenario.

## Five-minute technical demonstration

Begin with the same commands and spend roughly a minute on the problem, data,
and provenance. Spend another minute comparing an observed context to its
historical neighbors and writing the endpoint-correction equation on paper.
Use the next minute to explain why the calibration suffix is disjoint from the
training prefix and why the maximum standardized residual targets a whole gap.

Show one retained refusal by adding a boundary gap to a new copy of the original
measurement input, preserving the original three gaps:

```console
uv run python -c "import pandas as pd; frame=pd.read_csv('examples/with_gaps.csv'); frame.loc[:2,'value']=float('nan'); frame.to_csv('demo-boundary.csv',index=False,mode='x')"
uv run gaplens repair --reference examples/reference.csv --input demo-boundary.csv --output demo-boundary-output --require-complete
```

The expected return code is **3**, with a saved partial report: 42 of 45 missing
samples reconstructed, 2,019 original observations preserved, and the boundary
gap unresolved because six observed samples on both sides are unavailable.
The file-creation command refuses to overwrite an existing `demo-boundary.csv`.
Inspect the refusal reason and the empty value/band cells in that gap.

Then show `results/v2/final/tables.md`, the saved case-level measurements in
`results/v2/benchmark/`, and the [v2 report](v2/RESEARCH_REPORT.md). Compare v1 and
diverse on the same new masks, then include the stronger development-selected
competitor. Explain coverage together with width and service rate, and show the
documented failure example. Distinguish the older `results/benchmark/` study,
which is now development evidence. Use the final minute for the failed
hypotheses that the actual report records and one justified next experiment.

To reproduce the checks and experiment rather than just display an existing run:

```console
uv run pytest
uv run python scripts/run_experiments_v2.py --config configs/benchmark_v2.json --plan results/v2/masks.json --output results/my-v2-reproduction
uv run python scripts/summarize_v2.py --input results/my-v2-reproduction --output results/my-v2-summary
uv run python scripts/verify_v2.py --input results/v2/benchmark --compare results/my-v2-reproduction
```

Use new output paths. Replay the bundled frozen masks; do not run `--prepare`
or retune parameters as part of reproduction. The summary command reads saved
results without training. The verifier independently reconciles truth, metrics,
quantiles and the repeat's numerical outputs, excluding elapsed-time fields.
Expect timings to differ by hardware; platform/library arithmetic can also
affect exact reproducibility. Record any discrepancy rather than relaxing checks
silently. A smoke run is not the complete fixed experiment.

## Interview questions with substantive answers

**1. What is the project's own technical contribution?**

An explicit, auditable reconstruction pipeline: retrieve historical windows from
two-sided observed context, transfer their interior shapes through endpoint
correction, estimate local relative error from neighbor disagreement and context
novelty, and calibrate whole-gap bands separately by length. The code and
evaluation isolate these components. Nearest neighbors, interpolation, ExtraTrees,
and conformal calibration are established ideas; novelty beyond this engineering
combination requires additional literature comparison and evidence.
V2 adds input-provenance protection and a broader controlled comparison of known
mechanisms. Its primary contribution is inspectable software and evidence about
conditions of usefulness, not a theorem or an established new retrieval idea.

**2. Why is this offline reconstruction instead of forecasting?**

The right endpoint and subsequent observed context are available to the method.
That is legitimate when repairing a completed log, but unavailable while a live
outage is still in progress. Calling the method a forecaster would conceal future
information. The benchmark methods receive the same two-sided information in the
benchmark so the comparison matches the intended task.

**3. Why not just interpolate?**

Interpolation is fast, transparent, and often difficult to beat on short smooth
gaps. It cannot reconstruct a recurring interior peak that is absent from both
endpoints. Historical analogs can supply such a shape, but can also hallucinate an
irrelevant pattern. That tradeoff must be measured; the project does not assume
the more complicated algorithm always wins.

**4. What exactly does endpoint correction do?**

For position `t` inside a historical gap, add `(1−t)` times the difference between
query and historical left endpoints plus `t` times the right-endpoint difference.
The historical deviation from its straight endpoint chord is retained, while its
level and linear trend are adapted to the query anchors. This can help when the
same shape recurs at a different level. It cannot reveal an unseen event in the
missing interior.

**5. Where could data leakage enter, and how is it prevented?**

Leakage could arise by retrieving an analog that overlaps the test gap, training
on hidden target values, computing normalization from the full series, tuning on
the test results, or calibrating with test errors. GapLens fits only an earlier
training portion; calibration is separate; the query begins later than the full
reference; features exclude hidden interiors; and normalization is fitted on
training history. Tests also check that changing hidden interior values does not
change predictions. These protections do not make dependent samples independent.
An exported estimate is another possible leakage source. V2 rejects repair
exports as both query and reference, rather than silently using their `value`
column as observed context, fitting targets or calibration truth.

**6. Why use the maximum standardized error for calibration?**

The consumer sees a reconstructed block, so a useful question is whether its
entire trajectory is covered. A gap score is the largest standardized point
error within that block. Calibrating this maximum targets simultaneous block
coverage rather than treating every point as an unrelated event. It usually
requires wider bands than pointwise calibration, especially for longer gaps.

**7. Does “90% coverage” mean the future gap is guaranteed to be covered?**

No. The construction's finite-sample distribution-free result depends on
exchangeability of calibration and future examples. Chronological monitoring
series have dependence and possible drift. Here 90% is a nominal target, and
coverage is measured empirically on held-out gaps. Nine examples permit a finite
90% order statistic but are weak evidence; a large calibration sample alone also
cannot repair a severe distribution shift.

**8. Why not report only MAE or only coverage?**

MAE measures point reconstruction accuracy but says nothing about how cautiously
the system communicates errors. Coverage alone can be increased by making bands
arbitrarily wide. The study jointly reports error, point/gap coverage, width,
interval score, runtime, and ablations. Cross-series error uses training-scale
normalization because a passenger-count error and a temperature error have
different units. The normalization and aggregation choices must remain visible.

**9. What does the stronger baseline contribute?**

ExtraTrees learns nonlinear residual corrections to interpolation from artificial
training gaps, using the same type of observed contexts and calendar information.
It checks whether the historical-analog design adds value beyond a reasonable
generic CPU learner. It is neither a pretrained model nor a remote API. The
underlying forest is scikit-learn's implementation; GapLens supplies the
gap-specific training features, target construction, and evaluation wrapper.
V2 adds seasonal profiles, local-linear Kalman/RTS smoothing and conditional
trajectory PCA using the same context information. The latter tests whether a
learned low-rank window model is a better explanation than nearest-window
retrieval. These are project implementations of known ideas, not exact replicas
of published packages or evidence against modern neural imputation.

**10. Why leave some gaps unresolved instead of filling every cell?**

Boundary gaps, adjacent gaps that contaminate context, very long gaps, or gaps
without enough reference/calibration support do not satisfy the implemented
method's prerequisites. Filling them anyway would hide missing information. The
pipeline preserves their NaNs, records reasons, and can return a nonzero status
with `--require-complete`. It also never chains one reconstruction into the
observed context for another, which would silently compound uncertainty.

**11. What do repeated seeds prove?**

They show sensitivity to the selected mask locations and estimator randomness.
The same underlying series are reused, and windows can overlap across lengths or
seeds. Seed ranges therefore are not independent-dataset confidence intervals.
V2 reports 14 real streams in eight provider/domain groups and uses grouped
resampling, with a coarser six-source-group sensitivity. This respects more of
the known dependence, but the small number of source groups still limits
generalization. Fourteen dataset names do not establish fourteen independent
systems.

**12. What would make a negative result scientifically useful?**

A fixed protocol can reveal that local historical shapes fail under regime
change, that interpolation is already sufficient for short gaps, or that the
adaptive scale is poorly calibrated. Ablations and saved worst cases let a reader
test those explanations. The honest next step is to narrow the supported claim or
form a new hypothesis, then evaluate it on newly held-out data—not to discard
unfavorable series or retune against the original test set.

**13. Why retain analog as the default if diverse was implemented?**

The frozen development rule required at least 5% improvement over v1. The tuned
diverse candidate selected `k=4` but had a 3.994% worse geometric mean
relative-error objective on the three development streams. It therefore failed
that rule. The CLI retains `analog`; `--method diverse --neighbors 4` is an
explicit alternative. Final outcomes cannot retrospectively select a different
default while still being called an independent selection test.

**14. Why are rolling calibration and the research comparators absent from the CLI?**

The normal CLI has one earlier reference file and one later input. Research
rolling calibration requires a documented history of which true observations
would be available at each origin; previously reconstructed values cannot supply
that truth. That scenario is implemented in the experiment harness. Restricting
the CLI to its supported contract avoids inventing availability from a repaired
file. Seasonal/Kalman/PCA comparators likewise are study methods, not promised
product options.

## From v2 toward a possible paper

The existing code provides a concrete method, useful end-to-end scenario,
explicit baselines, component ablations, real-data provenance, a fixed expanded
protocol, and machine-readable measurements. The v2 report states which
hypotheses survive its evaluation. These are evidence for a technical report,
not a publication acceptance or a general algorithmic superiority claim.

A defensible next study should build on the executed v2 comparisons rather than
presenting them as future work:

1. **New independent evidence:** add further sources/domains with clear reuse
   rights, keep a genuinely new final test set, and evaluate several gap durations
   in comparable physical units. Distinguish within-series, cross-series, and
   cross-domain generalization.
2. **External reference implementations:** compare relevant author-maintained
   retrieval/state-space implementations and resource-matched learned methods
   where their assumptions fit. V2's seasonal/Kalman/PCA implementations are
   useful controls, but do not reproduce every published method. Allocate
   comparable validation budgets; do not tune only the proposed method.
3. **Realistic missingness and drift:** examine dense simultaneous gaps,
   sensor-failure-dependent missingness, abrupt new regimes, and missing right
   context. Obtain redundant reference measurements if claiming accuracy on
   genuine outages. Synthetic masks alone cannot establish that claim.
4. **Uncertainty assessment:** evaluate enough independent blocks/sources to
   quantify uncertainty in coverage and paired error differences; use temporal
   block resampling or another justified dependence-aware design. Compare against
   calibration methods specifically designed for nonexchangeable time series.
5. **Mechanism and resource analysis:** measure neighbor quality, calendar
   sensitivity, candidate-cap effects, endpoint correction, scale calibration,
   and failure under mismatch. Measure memory in isolated processes and benchmark
   CPU latency on a representative Windows laptop.
6. **A claim matched to the evidence:** articulate whether the contribution is
   better accuracy, a coverage/width/resource tradeoff, an auditable workflow, or
   a documented limitation of analog repair. Update related-work analysis before
   claiming novelty. Include source attribution, data licenses and reproduction
   instructions in the study's release package.

A research log can record reproduced commands, worked numerical examples,
design decisions and new results. It provides a useful reference for further
experiments and technical discussion.
