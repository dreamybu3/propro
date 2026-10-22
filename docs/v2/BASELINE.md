# Verified v1 baseline and v2 provenance contract

V2 starts at commit `ecf22de604d14e747bf6607d50b62b4870d24fcf` on
`gaplens-delivery`. That branch and the original `results/benchmark`,
`results/demo`, and `data/processed` artifacts are preserved. Their SHA-256
manifest is [baseline_hashes.json](baseline_hashes.json).

The owner independently reported: all 58 baseline tests pass; all 54,432 saved
prediction rows, including interval boundaries, reproduce; the reported v1
effects reproduce; GitHub Actions passed on Ubuntu and Windows. This is CI
evidence, not a claim that the owner's laptop or GPU was tested. The original
three series are development data for v2, never new confirmatory evidence.

## Confirmed defect and chosen contract

At v1, reimporting `results/demo/repaired.csv` with `examples/reference.csv`
reports 2,064 observations, zero missing values and zero intervals. In fact,
only 2,022 values were measured and 42 were estimates. The parser ignored
`original_value`, `status` and uncertainty metadata. Reproduction evidence:
[before.json](../../results/v2/provenance/before.json).

V2 explicitly rejects repair exports in **both** input roles, before fitting,
calibration or output creation. Reserved columns are `original_value`, `status`,
`lower`, `upper`, `gap_id`. Use the original `timestamp,value` measurement file,
keeping unavailable measurements empty. Do not strip metadata from an export
to make it pass validation. If new observations arrive, update the original
measurement record only with genuinely measured values. The program cannot
detect estimates deliberately relabelled as raw measurements.

This is an intentional limitation, not a round-trip import feature. It prevents
estimates becoming targets, calibration truth or context. The CLI returns 2
with an actionable error; existing CSV/JSON/HTML bytes, statuses, intervals
and refusal reasons are untouched. Regression tests cover both roles, an
export with a newly introduced gap, original-file preservation and output
preservation. [after.json](../../results/v2/provenance/after.json) records the
same reproducer after the fix.

Duplicate CSV header names are rejected before pandas can rename and silently
ignore them. Unrelated, unique metadata columns remain supported.
