# GapLens handoff and continuation record

## Selected workflow completed

The repository contains the complete GapLens product, original AnalogBridge implementation, real attributed data, runnable examples, executed benchmarks, tests, interactive reports and English/Russian documentation. After initial local development, the owner explicitly authorized delivery of source, documentation and experimental results through the separate `gaplens-delivery` branch of `dreamybu3/propro`. No deployment, paid action or research-paper publication is implied.

The selected problem is offline missing-block reconstruction in univariate monitoring data. Exactly three candidates are compared in DECISION.md. UCI access was denied by the proxy; the selected official NAB distribution was downloaded, parsed and licensed before the main experiment. No network restriction or verification mechanism was bypassed. Data are pinned to NAB commit `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140` under its inspected MIT license.

## Completed artifacts

- `src/gaplens`: validation, analog bridge, linear/ExtraTrees baselines, whole-gap calibration, CLI and report.
- `examples`: real history, incomplete input, separate ground truth and mask provenance.
- `results/demo`: actual completed product output.
- `configs/benchmark.json`, `docs/PROTOCOL.md`: preserved pre-experiment settings and criteria.
- `results/benchmark`: complete run `26ff839c-11c3-4576-b64c-3e104315b402`, 648 gap cases, 3,888 method cases, 54,432 point predictions, logs/hashes and generated figures/tables.
- `results/validation-tests.*`, `results/browser_validation.json`, `docs/assets`: captured numerical/integration tests and actual browser evidence.
- Documentation: README, QUICKSTART_RU, ARCHITECTURE, RESEARCH_REPORT, SOURCES, RELATED_WORK, LEARNING_GUIDE, PORTFOLIO, THIRD_PARTY, VALIDATION.
- `uv.lock`, `requirements.lock`: exact versions and distribution hashes. Clean-install/distribution evidence is in `results/validation.json`.

## Reproduction from the project root

```sh
uv sync --frozen
uv run gaplens repair --reference examples/reference.csv --input examples/with_gaps.csv --output new-repair --require-complete
uv run python -m pytest -q
uv run python scripts/run_experiments.py --config configs/benchmark.json --output results/new-run
uv run python scripts/plot_results.py --input results/new-run
uv run python scripts/summarize_results.py --input results/new-run
```

Choose new output directories; existing files are protected by default. No long-running service is needed. This cloud task has an isolated checkout at `/workspace/propro`; use it and do not create a Git worktree unless explicitly requested. The portable project does not depend on that absolute path.

## Findings to preserve

AnalogBridge macro normalized MAE is 51.8% lower than linear and 14.4% lower than ExtraTrees on this study; endpoint correction improves error by 20.0% versus its ablation. Whole-gap coverage is 85.8% at a 90% target and only 78.7% on NYC taxi. Adaptive bands are 16.5% wider than constant-scale bands: the full hypothesis failed. CPU interval widths can be operationally unhelpful. Do not rewrite these as universal accuracy or coverage guarantees.

The main run took 99.86 seconds with 259.18 MiB process peak RSS on Linux. Native Windows/the user's GPU were not tested; no GPU is needed. Mask-seed repeats are dependent sensitivity checks, not independent evidence of significance.

## Future research, not pending implementation

The selected product and initial experiment are complete. Publication-level novelty, stronger pattern/Kalman/probabilistic baselines, independent datasets, shift-aware calibration, native Windows resource measurements and user studies remain separate research steps. Do not tune to the current test split and present it as a fresh evaluation. Follow PORTFOLIO.md and disclose AI assistance/personal learning honestly.

## Cloud configuration persistence

The install_script and start_skill fields are saved in the environment draft. Current-instance installation and startup were tested separately. The environment draft is not published or active for new tasks; review/save/publication of that environment is a separate owner action if later desired. Source-code delivery through `gaplens-delivery` is separately authorized. See CLOUD_ENVIRONMENT.md.
