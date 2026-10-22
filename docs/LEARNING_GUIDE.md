# Learning, demonstration, and research development

This repository was developed with AI assistance. Treat it as material to
understand, reproduce, critique, and extend. Do not describe all implementation
or experiments as your own independent work if you did not perform them. A
defensible portfolio statement explains what this version implements and then
identifies the reproduction, modifications, or additional analysis you personally
completed. No publication, adoption, or production deployment is implied.

## A practical route through the code

1. Read `data/README.md` and `docs/PROTOCOL.md`. Explain the difference between
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

## Ninety-second demonstration

Use a terminal in the repository root after the documented installation. The
commands below use `uv run`, which selects the project's pinned environment.

```console
uv run python scripts/make_demo.py --overwrite
uv run gaplens repair --reference examples/reference.csv --input examples/with_gaps.csv --output demo-output
```

The explicit `--overwrite` regenerates the known demo files; omit it to protect
any copies you have edited, or skip generation when the bundled examples suffice.
The generator produces `examples/reference.csv`, `examples/with_gaps.csv`,
`examples/ground_truth.csv`, and `examples/provenance.json` from the bundled real
NYC taxi series. Ground truth is for demonstration verification; the repair
command receives only earlier history and the incomplete input. A rerun into the
same output directory needs explicit `--overwrite`, or use a different directory.

Suggested narration:

- **0–20 seconds:** “Monitoring exports can contain missing blocks. GapLens
  reconstructs eligible blocks from earlier similar patterns and the observations
  on both sides. It keeps the result distinguishable from actual measurements.”
- **20–45 seconds:** Run the command and show its repaired/unresolved counts.
  Open `demo-output/report.html` directly in a browser. Select a gap and show the
  estimated path, band, and supporting historical neighbors.
- **45–70 seconds:** Inspect `demo-output/repaired.csv` and `report.json`. Point
  out preserved observations, per-gap status, calibration count, and provenance.
  If a gap is unresolved, explain the recorded reason instead of hiding it.
- **70–90 seconds:** Show the saved benchmark comparison. Explain that narrower
  bands are useful only with adequate empirical coverage, and that the report
  retains unfavorable outcomes. State the strongest supported conclusion and its
  principal limitation using the actual results.

This is a local-file workflow, without a public deployment or a localhost link.
The report can be opened on Windows by double-clicking the HTML file; the project
does not require a server for the main scenario.

## Five-minute technical demonstration

Begin with the same commands and spend roughly a minute on the problem, data,
and provenance. Spend another minute comparing an observed context to its
historical neighbors and writing the endpoint-correction equation on paper.
Use the next minute to explain why the calibration suffix is disjoint from the
training prefix and why the maximum standardized residual targets a whole gap.

Then show the completed benchmark artifacts in `results/benchmark/`, including
case-level measurements, summary tables, and the fixed hypothesis evaluation.
Compare the analog method with both linear interpolation and ExtraTrees; show the
bridge and scale ablations. Explain one poor case or coverage failure. Use the
last minute for the strongest limitations and one concrete follow-up experiment.

To reproduce the checks and experiment rather than just display an existing run:

```console
uv run pytest
uv run python scripts/run_experiments.py --config configs/benchmark.json --output results/my-reproduction
uv run python scripts/plot_results.py --input results/my-reproduction
```

The separate output path preserves the recorded pilot. Expect timings to differ
by hardware. Identical seeds specify sampling and estimator randomness, but
library/platform arithmetic can still affect numerical details. Do not present a
quick smoke run as the full fixed experiment.

## Interview questions with substantive answers

**1. What is the project's own technical contribution?**

An explicit, auditable reconstruction pipeline: retrieve historical windows from
two-sided observed context, transfer their interior shapes through endpoint
correction, estimate local relative error from neighbor disagreement and context
novelty, and calibrate whole-gap bands separately by length. The code and
evaluation isolate these components. Nearest neighbors, interpolation, ExtraTrees,
and conformal calibration are established ideas; novelty beyond this engineering
combination requires additional literature comparison and evidence.

**2. Why is this offline reconstruction instead of forecasting?**

The right endpoint and subsequent observed context are available to the method.
That is legitimate when repairing a completed log, but unavailable while a live
outage is still in progress. Calling the method a forecaster would conceal future
information. Both baselines receive the same two-sided information in the
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
underlying forest is scikit-learn's implementation, and this project authors the
gap-specific training features, target construction, and evaluation wrapper.

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
seeds. Seed ranges therefore are not independent-dataset confidence intervals,
and this pilot does not claim statistical significance from them. A stronger study
would use more independent sources and a dependence-aware uncertainty analysis.

**12. What would make a negative result scientifically useful?**

A fixed protocol can reveal that local historical shapes fail under regime
change, that interpolation is already sufficient for short gaps, or that the
adaptive scale is poorly calibrated. Ablations and saved worst cases let a reader
test those explanations. The honest next step is to narrow the supported claim or
form a new hypothesis, then evaluate it on newly held-out data—not to discard
unfavorable series or retune against the original test set.

## From this pilot toward a possible paper

The existing code provides a concrete method, useful end-to-end scenario,
explicit baselines, component ablations, immutable real-data provenance, a fixed
protocol, and machine-readable measurements when the full benchmark completes.
These are a starting point for research, not evidence that a venue will accept a
paper. The actual report determines which empirical claims survived the pilot.

A defensible next study would address these gaps in roughly this order:

1. **Broader independent evidence:** add more sources/domains with clear reuse
   rights, keep a genuinely new final test set, and evaluate several gap durations
   in comparable physical units. Distinguish within-series, cross-series, and
   cross-domain generalization.
2. **Stronger comparisons:** include well-configured seasonal/state-space/Kalman
   reconstruction and other relevant nearest-neighbor imputers, then resource-
   matched learned imputation methods where their assumptions fit this univariate
   offline task. Allocate comparable validation budgets; do not tune only the
   proposed method.
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
   CPU latency on the intended Windows laptop.
6. **A claim matched to the evidence:** articulate whether the contribution is
   better accuracy, a coverage/width/resource tradeoff, an auditable workflow, or
   a documented limitation of analog repair. Update related-work analysis before
   claiming novelty. Release a reproducibility package only after explicit
   publication permission and review of source attribution.

For your own progression, keep a research log of commands you reproduced,
explanations you verified by hand, changes you designed, and new results you
obtained. Those records support accurate CV statements and a stronger technical
interview than memorizing a claim of superiority.
