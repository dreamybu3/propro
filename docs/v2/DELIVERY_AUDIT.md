# Delivery contents audit

Latest snapshot reviewed: **2026-10-22 20:46 UTC**, with HEAD at correction
commit `ed799ef058432615d6c2bae4c0b3118729b77b06`. Both the preserved initial
evaluation and corrected canonical evaluation, summaries, sensitivity outputs,
and clean-validation evidence were present. The lead's validation document and
research write-up were being finalized. This audit did not publish, push, or
modify protected files; it supersedes the 20:34 UTC inventory.

## Contents and credentials

The audit enumerated 170 tracked files and 108 untracked files eligible for
inclusion, then scanned 260 text payloads, including decompressed initial and
canonical `predictions.csv.gz` files. It also scanned all 86 new text blobs
in Git history since the verified v1 checkpoint, so a removed working-tree file
would not hide an earlier committed credential.

No candidate private keys, recognizable GitHub/OpenAI/AWS/Slack tokens, JWTs,
credential-bearing URLs, or quoted credential assignments were found. No
credential values were printed. No environment directories, package caches,
raw download caches, `.env` files, private-key files, or symlinks were in the
publication file set. The ignored inventory contained 9,180 local files,
principally the virtual environment, Python/test caches, and 15 raw source files;
those remain excluded by `.gitignore`.

Recorded local paths occur in historical run/install logs and documentation;
two matches are paths inside preserved public source URLs. They are not copied
environments, filesystem dumps, or credentials. New result files contain the
declared public-data experiment and execution metadata. The visible report
screenshots are expected product artifacts.

The largest file is the expected `coverage_width.csv` (13,402,383 bytes), followed
by the preserved v1 predictions (12,151,406 bytes) and v2 case metrics
(11,182,560 bytes in the canonical run). Compressed v2 point predictions occupy
5,757,624 bytes per preserved run. Keeping both runs is deliberate audit evidence,
not an accidentally included execution cache. No
unexpected large archive, environment, database, or file approaching GitHub's
100 MiB per-file limit was found.

## Rights and attribution

All 14 v2 sources are marked redistributable in the manifest, and every preserved
provenance/license document still matches its recorded source hash. The selected
terms are NAB MIT, CC BY 4.0 for the SSA/JHU releases, and the documented public
domain/PDDL designations for CO₂, EIA, and NOAA-derived Seattle observations.
The full notices and transformation descriptions accompany the data.

Source-derived truth values, predictions, tables, and figures can be distributed
under those permissions with their applicable attribution retained. Project MIT
licensing does not replace third-party data terms. The audit found that
`docs/THIRD_PARTY.md` initially covered only the three v1 datasets; the lead
updated it to link the v2 rights ledger and explicitly cover source-derived
result artifacts. That documentation gap is resolved.

Licensing review scope remains as declared in `data/v2/README.md`: NAB's release
license is the redistribution evidence, without a separate audit of every
earlier provider; direct NOAA/EIA policy pages were inaccessible to this
environment, while their pinned dataset/package permission statements were
preserved. ETT's restricted derivative license is not part of this delivery.

## Baseline and freeze preservation

- All **24** SHA-256 entries in `docs/v2/baseline_hashes.json` match.
- Git comparison with the baseline shows no changes to v1 benchmark, demo,
  smoke, processed data, examples, original data manifest, benchmark config,
  or original protocol.
- All **15** protected-file hashes in `configs/v2_freeze.json` match.
- The frozen protocol and mask-file hashes match. The configuration matches
  both its protected raw-file hash and its canonical-JSON hash.
- No versioned file was deleted between the baseline and correction commit.

The correction's source diff was inspected: it only changes inspection of a
CSV's effective header to skip blank preambles before provenance/duplicate-header
validation. It adds no network access, credential handling, or external action.
Comparing initial and amended freeze manifests confirms that **only
`src/gaplens/data.py`** changes among protected hashes. Protocol, configuration,
masks, numerical models, and the analysis script are unchanged.

`initial_benchmark/run.json` correctly retains the original parser hash, which
therefore differs from the current working file. This is an explicitly recorded
historical mismatch, not an unexplained modification: the original source is
still present at the original freeze commit and matches that hash. The canonical
run embeds the amended hash. Both runs are complete. The preserved
`correction_equivalence.json` records byte-identical predictions, calibration
scores, and coverage/width tables; case metrics match apart from timing. The
correction is documented in [CORRECTIONS.md](CORRECTIONS.md) as a replay of an
already inspected holdout, not fresh independent confirmation.

## Links and final staging

A separate read-only reviewer checked 28 Markdown documents and 116 local
targets. All resolved except five links to the lead's then-pending
`docs/v2/VALIDATION.md`. External URLs and illustrative code blocks were excluded
from that local-path check. `git diff --check` passed with no whitespace findings.
The pending validation document must exist before publication; new final text
should be included in the lead's last link/staging inventory.

No credential, rights, baseline-preservation, or unexplained-code-change blocker
was found in this snapshot. Files added
after the recorded cutoff still require the lead's final staging/inventory
check; this snapshot does not claim to audit future files or verify remote
GitHub publication. Pattern scanning reduces accidental disclosure risk but is
not a proof that arbitrary unknown secret formats cannot occur.

## Final staged inventory

The lead agent repeated the scanner after final staging: 284 tracked/staged files, no nonignored untracked files, 266 text payloads scanned, zero credential/key/token candidates, no symlinks, and all 24 baseline artifact hashes matching. The environment/cache/raw files remained ignored. A separate link check resolved all 150 local Markdown targets, including the completed VALIDATION.md. This records the inventory before the delivery commit; hosted branch/ZIP/CI verification follows publication.
