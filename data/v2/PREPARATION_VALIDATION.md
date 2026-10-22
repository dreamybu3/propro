# Preparation validation

Validated on the Linux cloud execution environment on 2026-10-22 with the
project's pinned Python dependencies. These checks do not evaluate any method
or inspect holdout performance.

- `python -m pytest tests/test_data_v2.py -q`: **9 passed**.
- `python scripts/fetch_data_v2.py --verify-only`: all 14 bundled datasets
  matched their recorded SHA-256, length, missing count, and regular grid.
- `python scripts/fetch_data_v2.py`: repeat preparation from cached verified
  raw sources produced identical processed bytes for all 14 datasets.
- Fresh-directory check: copied only `data/v2/manifest.json` into an empty
  temporary project root, then ran `python scripts/fetch_data_v2.py --root
  <temporary-root>`. All sources were downloaded again from their immutable
  URLs; every source and processed hash matched. No prior raw or processed
  cache was available to that command.
- Every bundled prepared series passed the product's `read_series` input
  contract. Exact numerical-vector duplicate checking found no duplicate pair.
- All preserved provenance documents contain LF line endings, consistent with
  the repository's `.gitattributes`; no checkout newline normalization changes
  their recorded source hashes.

The test suite checks negative reporting revisions and unknown initial
increments, national/province ambiguity, native versus inserted missing values,
leap-day/weekday correctness, malformed time grids, file preservation, checksums,
and the corpus's grouping/count metadata. No final performance scores or plots
were produced during preparation. An independent agent reviewed the preserved
license/provenance statements and found no blocking contradiction; its remaining
scope limitations are recorded in `README.md` and `manifest.json`.
