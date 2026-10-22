# V2 validation and delivery evidence

The v2 product and experiments were executed on Linux x86-64 with Python 3.12.
Cloud measurements are not measurements on the owner's laptop. Python 3.11–3.13
are declared package-supported; the executed platform matrix uses Python 3.12.

## Baseline and independent review

The preserved baseline is `ecf22de604d14e747bf6607d50b62b4870d24fcf` on
`gaplens-delivery`. The owner independently reproduced its 58 tests and all
54,432 numerical predictions. We subsequently verified the actual [Ubuntu and
Windows GitHub jobs](https://github.com/dreamybu3/propro/actions/runs/39843959679)
through the API; [saved job evidence](../../results/v2/validation/baseline_ci.json)
records both successes. Initial v1 documents describing untested Windows are
historical, not the current compatibility statement.

Separate agents reviewed [product behavior](PRODUCT_AUDIT.md),
[numerical models](MODEL_REVIEW.md), [protocol and information boundaries](PROTOCOL_REVIEW.md),
[results and estimands](RESULT_REVIEW.md), and [publication contents](DELIVERY_AUDIT.md).
Substantive findings were fixed or are explicitly limited in those records.
This is independent review within an AI-assisted workflow, not external peer review.

## Input/product regressions

The plain reimport defect was reproduced before correction: 42 estimates were
silently promoted to observations. V2 rejects provenance exports in both query
and reference roles, including exports with a new missing gap. The original
measurement file is required; removing provenance to relabel estimates is unsafe.
Regression checks preserve existing file bytes, statuses, bands and reasons.

The final audit found a blank-preamble bypass, corrected in `ed799ef` after the
first final evaluation. [CORRECTIONS.md](CORRECTIONS.md) preserves chronology,
old/new parser hashes and the original outputs; no performance choices changed.
All 45 focused parser/provenance tests passed. Other tests cover duplicate
headers, time/grid validation, boundary/adjacent/long/unsupported gaps, output
conflicts, failed-refit state, timestamp-resolution invariance, local-context
isolation, nonoverlapping neighbors, and independent PCA/Kalman numerical oracles.

The default and optional diverse CLI demos each reconstruct 3 gaps / 42 samples
and preserve 2,022 observations. The boundary demo exports explicit refusal
and exits 3 under `--require-complete`; reimport exits 2 without overwriting files.
Saved current-version reports are in [demo](../../results/v2/demo) and
[demo-diverse](../../results/v2/demo-diverse).

## Tests, clean installation and numerical reproduction

The pre-freeze suite passed **163 tests**. A new Python 3.12 virtual environment
was created in a clean local clone; it did not reuse/copy the project environment.
Dependencies were installed from `requirements.lock` with hash verification,
then the project installed editable without dependency resolution. `pip check`
and all 14 bundled data-hash checks passed. The corrected checkout `ed799ef`
passed **174 tests** in that environment; the two later sensitivity tests are
additional analysis checks. The complete final local suite passed **176 tests**,
with no failures/skips and 14 third-party deprecation warnings. Results are in
[final_tests.log](../../results/v2/validation/final_tests.log) and
[JUnit XML](../../results/v2/validation/final_tests.xml).

The same isolated environment was retained across the parser-only correction;
dependency lock hashes were unchanged. This is explicitly recorded in
[clean_setup.json](../../results/v2/validation/clean_setup.json), with installation
and test logs alongside it. Both default and diverse demos passed there.

The corrected clean full replay also passed:
[reproduction.json](../../results/v2/validation/reproduction.json) confirms exact
predictions, scores, curves and case metrics (except timing).
[clean_summary_reproduction.json](../../results/v2/validation/clean_summary_reproduction.json)
confirms exact regenerated scientific tables, Markdown, figures and scientific
summary fields. The first clean full replay is separately verified in
[reproduction_initial.json](../../results/v2/validation/reproduction_initial.json).
The corrected canonical comparison against the preserved first run is verified in
[correction_equivalence.json](../../results/v2/validation/correction_equivalence.json):

- **162,126** point rows, including predictions, scales, intervals and neighbors,
  are byte-identical in the deterministic compressed CSV.
- **42,890** calibration-score rows and **70,587** coverage-curve rows are
  byte-identical.
- All **23,529** case-method rows match exactly after excluding prediction timing.
- **18,006** fitted calibration quantiles independently reconcile with their
  saved scores; all **24** preserved v1 artifact hashes match.

The [summary replay](../../results/v2/validation/summary_replay.json) confirms
byte-identical 14 scientific CSV tables, Markdown tables and eight PNG/SVG
figures. Scientific summary fields are identical after excluding measured times.
An independent [methodology verifier](../../results/v2/methodology_review.json)
also reconciles paired effects, both group bootstrap variants, ranks, service
denominators and 13,369 calibration windows across 756 strata, including exclusion
of previous hidden outages. These checks are distinct from merely rerunning tests.

## Browser and resource checks

[Chromium 154 evidence](../../results/v2/browser_validation.json) covers gap
selection, reference provenance, status filters, overview, exact CSV download,
visible singleton intervals, desktop/mobile overflow, zero JavaScript exceptions
and zero remote resource requests. Screenshots are in [assets](assets).

The corrected full experiment took **161.74 s** with **497.66 MiB** cumulative
process peak RSS; the first run took 155.80 s / 505.29 MiB. Per-method fit,
first prediction/cache construction, calibration and warm prediction are recorded
in [performance.csv](../../results/v2/benchmark/performance.csv) and the generated
[performance summary](../../results/v2/final/performance_summary.csv).
RSS is cumulative process peak, not separate per-model allocation.

A separate fresh-process CLI measurement, including interpreter and imports,
took **1.332 s**, with **76.39 MiB** child peak RSS; its internal pipeline timer
was 0.283 s. [Cold-start evidence](../../results/v2/validation/cli_cold_start.json)
distinguishes that end-to-end measurement from already-loaded model timings.
The bundled new processed corpus is 1,671,412 bytes. Times are descriptive
shared-cloud measurements, not hardware-independent performance guarantees.

## CI, obtaining the project, and remaining limits

The [workflow](../../.github/workflows/ci.yml) runs on Ubuntu and Windows with
Python 3.12. It installs hash-pinned dependencies, runs tests, checks bundled
data, independently reconciles the saved v2 experiment, and executes both
product demos. Both jobs at the completed code/results checkpoint
`ef5e2c17ec502cd1f3e2b01038f8780949348d03` [passed on GitHub](https://github.com/dreamybu3/propro/actions/runs/39852421927);
[saved API evidence](../../results/v2/validation/v2_ci.json) records every step's
successful status. Current hosted outcomes are visible in the
[branch checks](https://github.com/dreamybu3/propro/actions?query=branch%3Agaplens-v2)
and the delivery PR; the final delivery response links the verified run.

Get source through the [gaplens-v2 branch](https://github.com/dreamybu3/propro/tree/gaplens-v2)
or [GitHub ZIP](https://github.com/dreamybu3/propro/archive/refs/heads/gaplens-v2.zip).
Use a Git clone for guarded experiment replay; ZIP supports the product and
analysis of saved artifacts. No filesystem path is presented as a download link.

Unverified scope remains: the owner's physical laptop/GPU, macOS, other Python
versions, genuinely unobserved outage ground truth, multivariate/neural claims,
production deployment and user studies. No paper acceptance or mathematical
coverage guarantee is claimed. These are limitations of the research/product
scope, not hidden failed checks.
