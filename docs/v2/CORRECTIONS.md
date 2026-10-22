# Corrections after the first final evaluation

## CSV preamble validation — 2026-10-22

After the first frozen full evaluation completed, a final product audit found
that a blank line before a CSV header bypassed the new provenance check.
The header inspector read the first empty CSV record while pandas skipped it.
Prepending a newline to the saved v1 repaired export therefore again accepted
2,064 finite values instead of protecting its 2,022 observations and 42 estimates.

The parser now inspects the first nonblank record, matching pandas' default
preamble handling. Regression tests cover ordinary/whitespace/CRLF preambles,
both input roles, newly introduced gaps, duplicate headers and valid raw CSVs.
This correction changes input validation only. It does not change any source
data, model, hyperparameter, mask, metric, uncertainty rule or analysis script.

The original freeze is commit `dc43d472` (full hash in freeze_receipt.json).
Its manifest is preserved as `configs/v2_freeze_initial.json`. The amended
freeze at that checkpoint changed only the protected SHA-256 for `src/gaplens/data.py` and added
this explanation; the protocol, configuration and mask hashes remain identical.
The correction commit is recorded in `results/v2/correction_receipt.json`.

All first-run measurements, predictions, calibration scores and logs remain in
`results/v2/initial_benchmark`; its first generated analysis remains in
`results/v2/initial_final`. The corrected full run occupies the canonical
`results/v2/benchmark`, with analysis in `results/v2/final`. Independent clean
replays and exact numerical comparisons are recorded under `results/v2/validation`.

The first holdout outcomes were already seen. The corrected replay is explicitly
a corrected analysis of the same evaluation, **not another unseen holdout**.
No performance tuning followed exposure. Numerical identity is a verification
requirement; timings, source hashes and environment metadata may differ.

## Atomic ExtraTrees refit — 2026-10-22

The delivered checkpoint `6e9a53d2413dad15a8546d6bb354da2fcf315d18` still
published reference values, timestamps, scales and the training-window count
before `ExtraTreesBridge.fit` finished. After a successful fit, a reference with
enough finite observations but no complete training windows raised an exception
while leaving the old forest paired with new reference statistics. A failure
inside the tree backend could also replace the working forest with an incomplete
one. The earlier timestamp-validation fix did not cover these later failures.

The corrected method prepares reference state, training windows, the window
count and a new forest privately. It replaces the fitted instance state only
after all training steps succeed. Failed initial fits remain unfitted; failed
refits preserve the complete previous working model. A subsequent successful
refit still replaces the model normally. Features, window order and selection,
random seeds, hyperparameters and successful-fit calculations are unchanged.

Four regression cases cover missing complete windows and a partially failed
tree backend, both on a previously fitted model and on a fresh instance.
They failed before the correction. The refit cases require exactly unchanged
predictions and scales, reference/timestamps, forest identity and training count;
they also compare a later successful refit with a freshly trained model.

Only the protected hash for `src/gaplens/core.py` changes in the active freeze:

- Previous: `16dc7108f0078d790fe3ccb3d0266572990638dff36e22a8b8ef2fc3fe9aa49a`
- Corrected: `cd74fc391e9d733333923ec283c913c5c7f72b820a59e01da3aecf337dbbd6ea`

The `validation_amendments` entry records this transition after holdout exposure.
The original freeze, saved run metadata, predictions, metrics and figures retain
their historical hashes. The protocol, masks, data, selected parameters and
immutable `_core_v1.py` are unchanged. The amendment is a correctness repair,
not a new prospective evaluation or a change to the study's conclusions.

`scripts/verify_v2.py` reports registered source amendments separately from
numerical checks. A changed source must match the active protected hash and be
reachable from the run's recorded hash through a unique, connected amendment
chain for that exact file. Unregistered changes, wrong endpoints, broken chains,
cycles and ambiguous transitions are rejected. This permits verification of
historical artifacts without rewriting their `run.json`; the chain alone does
not establish numerical equivalence.

Validation records are stored in
[`results/v2/validation/atomic_refit`](../../results/v2/validation/atomic_refit).
Replay outputs use a new directory; historical experiment directories are never
overwritten. The replay compares all predictions, scales, intervals, calibration
scores, coverage curves and case metrics, excluding runtime measurements.

To repeat the corrected run from a Git checkout, choose a new output directory:

```sh
uv run python scripts/run_experiments_v2.py --output results/atomic-refit-replay
uv run python scripts/verify_v2.py --input results/v2/benchmark
uv run python scripts/verify_v2.py --input results/atomic-refit-replay --compare results/v2/benchmark
```

The corrected code was committed as `3545d5865ec859c4c5dd9eaeb0240490631f26d1`
before replay. All **192 tests passed**. Both saved full runs passed independent
verification, with their applicable source amendments disclosed. The
[full replay comparison](../../results/v2/validation/atomic_refit/reproduction.json)
confirmed byte-identical **162,126 point rows**, **42,890 calibration-score rows**
and **70,587 coverage-curve rows**. All **23,529 case-method rows** matched exactly
apart from prediction timing. The new run's current source hashes were checked
directly, in addition to comparing its outputs with the saved benchmark.

Regenerated analysis matched all **14 scientific CSV tables**, Markdown tables
and **eight PNG/SVG figures** byte for byte; scientific summary fields matched
exactly after excluding measured performance. See the
[summary comparison](../../results/v2/validation/atomic_refit/summary_reproduction.json).
The [preservation receipt](../../results/v2/validation/atomic_refit/preservation.json)
also confirms all 205 checked historical files remain unchanged. New logs and
validation receipts are stored alongside these records; original outputs are
preserved in place. Runtime, memory and provenance metadata of the new execution
are recorded separately and are not presented as unchanged measurements.
