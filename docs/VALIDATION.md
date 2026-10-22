# Executed validation

These checks actually ran on Linux x86-64, Python 3.12.14. The machine had more than 16 GB RAM; the measured process peak is the evidence for modest resource use. Windows, the user's laptop, other Python versions, hosted CI and production operation are not claimed.

## Installation and data

- Created a fresh virtual environment using `uv sync`; repeated `uv sync --frozen` successfully without lock changes.
- Independently created `/tmp/gaplens-pip-check`, installed `requirements.lock` with pip `--require-hashes`, installed the project with `--no-deps -e .`, and completed the real demo. This validates the pip path on Linux; Windows commands remain unexecuted.
- Built the standalone wheel with `uv build --wheel`, installed it into the independent environment, and ran the demo from outside the checkout. Distribution evidence is in `results/validation.json`.
- Downloaded all three immutable official NAB CSVs into a fresh temporary root, verified every SHA-256, and regenerated processed data with matching hashes. Cached preparation was also rerun successfully.
- Bundled processed data support offline experiments after installation. Source counts are 10,320 NYC, 18,050 CPU, and 7,267 ambient observations; the latter has 7,888 regular-grid rows including 621 native missing values.

## Automated tests

```sh
.venv/bin/python -m pytest -q --junitxml=results/validation-tests.xml
```

**58 passed, 0 failed, 0 skipped**, in 5.83 seconds in the final captured run. Exact output and JUnit evidence: [validation-tests.log](../results/validation-tests.log), [validation-tests.xml](../results/validation-tests.xml).

Tests exercise hidden-target invariance, reference/query immutability, endpoint correction, finite scales, deterministic retrieval/trees, exact training budgets, calibration order statistics, disjoint sampling, data validation, natural-missing preservation, chronology/grid checks, abstention, protected outputs, HTML escaping, both baselines, CLI exit codes and singleton uncertainty rendering.

An independent accounting test recomputes error, point/gap coverage and width from all 54,432 saved prediction rows across 3,888 method cases, and verifies that interval-only ablations preserve point predictions. No empty test run is used as evidence.

## Complete product scenario

```sh
.venv/bin/gaplens repair --reference examples/reference.csv --input examples/with_gaps.csv --output results/demo --require-complete
```

The actual [demo artifacts](../results/demo) reconstruct **3/3 gaps and 42/42 missing samples**, preserve **2,022 observed values**, and include repaired CSV, audit JSON and interactive HTML. The separate known-truth file is never read by the repair pipeline. Known generated outputs were refreshed using explicit `--overwrite` after a presentation-only singleton-interval fix.

## Actual browser checks

```sh
python3 scripts/validate_report_browser.py --report results/demo/report.html
```

Platform-provided Playwright and **Chromium 154.0.8037.57** tested the real exported report: gap selection, reference-neighbor display, overview, status filters, exact downloaded CSV bytes, and visible singleton uncertainty bars. Desktop 1440 px and mobile 390 px layouts have no horizontal overflow. There were **zero JavaScript exceptions and zero remote resource requests**. Screenshots were saved and visually inspected.

Evidence: [browser_validation.json](../results/browser_validation.json), [desktop](assets/report.png), [mobile](assets/report-mobile.png). Cloud policy blocks file-URL navigation, so the checker used a temporary loopback HTTP server and shut it down afterward, without altering browser security. The report itself is self-contained and needs no persistent server. Optional Playwright/Chromium tooling is separate from product dependencies.

## Executed research

The definitive run `26ff839c-11c3-4576-b64c-3e104315b402` is marked complete in [run.json](../results/benchmark/run.json): three datasets, three seeds, three lengths, 24 test gaps per combination, six methods, **648 gaps / 3,888 method cases**. Every selected target completed.

Recorded resources: **99.858 seconds**, **259.176 MiB** cumulative process peak RSS. Numerical code, protocol and data hashes still match the saved run. Later presentation/documentation/test changes do not alter the benchmark. Figure/table provenance ties them to saved measurements.

The full hypothesis failed: error criteria passed on the limited test bed, but adaptive intervals were not narrower, and empirical coverage was below the nominal target, especially for NYC taxi. The research report retains all methods, failures and worst cases.

## Not executed or established

Native Windows/macOS, Python versions other than 3.12, the user's actual 16 GB laptop/GPU, hosted GitHub Actions, publication/deployment, real-outage ground-truth recovery, multivariate evaluation, modern deep-imputation baselines, independent statistical significance and user studies. These limitations are explicit; the selected local product and initial study are complete.
