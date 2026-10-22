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
freeze changes only the protected SHA-256 for `src/gaplens/data.py` and adds
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
