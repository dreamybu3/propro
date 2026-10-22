# V2 continuation record

Baseline: `ecf22de604d14e747bf6607d50b62b4870d24fcf`. Working branch: `gaplens-v2`.
The owner authorizes development, experiments, publishing this branch and a
draft PR targeting `gaplens-delivery`. No merge, paid compute or deployment.

Completed: baseline provenance bug reproduced and fixed through explicit
repair-export rejection; regression coverage added; original artifacts hashed.

In progress: product audit fixes, primary-source review, licensed 14-series
dataset, comparator implementations, development tuning and executable
protocol. No v2 final holdout scores have been inspected or generated yet.

Next gate: finish development tuning on the original three series, save all
trials and chosen parameters; freeze protocol/config/masks in a commit before
running final new-series evaluation. Then independent review, clean reproduction,
documentation, publication and GitHub verification.

Infrastructure: native Git HTTPS works. GitHub API requests currently receive
a proxy CONNECT 403 (api.github.com is absent from the configured allowlist).
Public GitHub HTML works; existing GH_TOKEN binding is present. Do not extract
credentials or request a duplicate token. A draft PR may require the API domain
to be enabled through environment settings; continue all independent work.
