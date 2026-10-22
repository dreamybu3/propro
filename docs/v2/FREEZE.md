# Pre-evaluation freeze

The commit introducing `configs/v2_freeze.json` is the prospective freeze.
It includes the protocol, selected development parameters, final masks,
numerical implementations, analysis script and protected-file hashes.
`results/v2/freeze_receipt.json` records its exact commit after creation.
No new-series predictions, errors or outcome plots were generated before it.

Development used the three previously inspected NAB series: 96 shared masked
cases and 1,536 case/configuration measurements. Selected configurations:
separated retrieval k=4; ExtraTrees 32 trees/300 training gaps; Kalman process
ratio 0.01; PCA rank 4/ridge 0.1. Separated retrieval's geometric mean error
ratio to v1 was 1.0399390708282688. The predeclared rule therefore retains v1
as the product default. ExtraTrees is the development-selected non-retrieval
comparator. All trials, masks and choices are preserved under development/tuning.

An independent review found timestamp-resolution and failed-refit timestamp-validation
bugs before freeze. Both were corrected. Repeating development afterwards
reproduced all five numerical/selection artifacts byte-for-byte. The immutable
`_core_v1.py` exactly matches the baseline source; corrected `core.py` is used
by the public product. The review and replay evidence are retained.

Metadata-only preflight: 14 streams, 3 seeds, 3 origins, 2,139 generated targets
out of 2,142 requested. Three boundary probes have native-missing truth and
cannot be evaluated; they remain listed as exclusions. Of 756 calibration
strata, 595 contain at least nine complete disjoint windows before any model
prediction. This is a feasibility count, not a coverage result. Insufficient
support remains an explicit outcome. See `results/v2/preflight.json` and masks.

There are 11 method/calibration outputs, including the fixed-k=12 separated
ablation needed to distinguish temporal exclusion from k tuning. H1 concerns
point errors on common available predictions; H2 concerns static versus recent
calibration on common interval-serviced cases. Every summary includes service
and refusal denominators. Details and thresholds are in PROTOCOL.md.

The runner verifies the committed freeze, masks and protected hashes. Use a Git
checkout to replay the experiment. ZIP downloads support installation, the CLI,
saved artifacts and analysis; the guarded scoring command requires Git history
to verify the freeze commit. Subsequent correctness corrections must be recorded
explicitly; final outcomes cannot be used for silent tuning.

Post-evaluation corrections are listed in [CORRECTIONS.md](CORRECTIONS.md).
The active manifest includes explicit source-hash amendments for CSV preamble
validation and atomic ExtraTrees refitting. Saved runs retain their original
manifests and source hashes; reproduction of the corrected code is checked
separately against those historical numerical outputs.
