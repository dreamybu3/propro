# GapLens v2 delivery checkpoint

Baseline: `ecf22de604d14e747bf6607d50b62b4870d24fcf`, preserved on `gaplens-delivery`.
Working/delivery branch: `gaplens-v2`; no merge or paid deployment authorized.

## Completed and verified

- Provenance reimport rejection in both roles, including blank preambles; duplicate headers and export-target checks; explicit support refusals; safe invalid refits and seasonal timestamp units.
- Fourteen licensed/pinned streams across six collections/eight conservative groups; three old NAB series used only for development.
- Protocol, masks, tuning and analysis frozen at `dc43d472f5a9e22bb510963eedeebdf4077e7234` before final scoring. Validation-only CSV correction at `ed799ef058432615d6c2bae4c0b3118729b77b06`, explicitly recorded after first exposure; no performance choices changed.
- Full study: 2,139 targets, 23,529 method cases, 162,126 point rows; first and corrected outputs preserved separately.
- Clean isolated install and replay: 174 tests at the corrected numerical checkpoint; final local suite 176 tests including two later sensitivity tests. No failed/skipped tests. Numerical outputs, scientific tables and all figures match exactly (timings excluded).
- Independent product/model/methodology/result/delivery reviews; actual Chromium report checks; English technical-report draft, Russian guide, architecture, demo/interview/CV materials updated.

## Scientific conclusion

Diverse retrieval fails H1: geometric MAE ratio to v1 1.0453, four wins and ten losses. V1 remains the development-selected default; it is not universally better than linear (ratio1.1543, seven wins/seven losses). H2 passes its frozen macro criterion, but width reduction is dominated by a network calibration extreme and does not establish uniform interval efficiency. See RESEARCH_REPORT.md and RESULT_REVIEW.md. No temporal coverage guarantee or established novelty claim.

## Reproduce and preserve

Use README.md and VALIDATION.md. Run experiments only into a fresh directory. Guarded replay requires a Git checkout and the committed freeze. Do not alter protected parameters/masks/code and silently reuse the final holdout. Original v1 data/results and the first v2 evaluation remain intact. Use CORRECTIONS.md for the post-freeze validation correction and exact comparisons.

## Publication

The user explicitly authorizes pushing `gaplens-v2` and creating a draft PR targeting `gaplens-delivery`. No further confirmation is needed. Git and GitHub API access work through supplied platform authentication. Final delivery must verify remote commit/files, Ubuntu/Windows CI and GitHub ZIP. No secret, environment, cache or raw download belongs in the push. The environment install/startup draft was refreshed; activating a future environment snapshot is separate from source delivery.
