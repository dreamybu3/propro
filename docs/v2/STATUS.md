# V2 continuation record

Baseline: `ecf22de604d14e747bf6607d50b62b4870d24fcf`. Working branch: `gaplens-v2`.
The owner authorizes development, experiments, publishing this branch and a
draft PR targeting `gaplens-delivery`. No merge, paid compute or deployment.

Completed: baseline provenance bug reproduced and fixed through explicit
repair-export rejection; regression coverage added; original artifacts hashed.

Completed before final scoring: product fixes, primary-source review, licensed
14-series dataset, comparator implementations, development tuning (diverse
3.994% worse than v1; keep analog default), independent code and methodology
reviews, original-value/uncertainty browser checks, 2,139 saved target masks.
The full suite passed 152 tests before adding 11 passing synthetic summary tests.
No v2 final holdout scores have been inspected or generated at this checkpoint.

Next gate: commit configs/v2_freeze.json with protected source/config/protocol
hashes, write freeze receipt, run scripts/run_experiments_v2.py to
results/v2/benchmark, generate summaries in results/v2/final. Then independent
result review, clean reproduction with scripts/verify_v2.py, final documentation,
publication and GitHub verification. Root owns README, RESEARCH_REPORT and
VALIDATION; product audit agent updates four existing user/architecture guides.

Infrastructure: native Git HTTPS works. GitHub API requests currently receive
a proxy CONNECT 403 (api.github.com is absent from the configured allowlist).
Public GitHub HTML works; existing GH_TOKEN binding is present. Do not extract
credentials or request a duplicate token. A draft PR may require the API domain
to be enabled through environment settings; continue all independent work.
