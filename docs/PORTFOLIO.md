# GapLens: portfolio summary and research roadmap

## Project scope

GapLens is research software for retrospective reconstruction of missing time-series blocks. It combines an inspectable numerical method, a complete CSV-to-report workflow, fixed evaluation protocols and reproducible measurements. The current research output is a technical report; production deployment and user studies remain outside the evaluated scope. The [development record](DEVELOPMENT.md) documents contributions to the project.

Its engineering contribution includes protection against hidden-target leakage, explicit separation of estimates and measurements, whole-block uncertainty estimates, and reproducible evaluation that retains failed hypotheses. The method combines established ideas; algorithmic novelty has not been established.

## CV wording for the v2 repository

The following project summaries describe implemented capabilities and recorded evidence.

- **GapLens — time-series reconstruction and evaluation:** CPU-only Python tool with historical-analog endpoint conditioning, whole-gap calibration, explicit provenance validation, and auditable CSV/JSON/HTML exports.
- Expanded reproducibility package with **14 real streams in eight provider/domain groups**, several chronological evaluation origins, shared frozen masks, development-only model selection, and seasonal, Kalman/RTS, trajectory-PCA and retrieval comparisons. Correlated channels are grouped rather than presented as independent systems.
- Preserves point errors, coverage, interval widths and refusal rates together; retains the original analog default after the diverse candidate failed its development selection rule. Held-out conclusions and failed hypotheses are reported in the [v2 technical report](v2/RESEARCH_REPORT.md), with [machine-generated tables](../results/v2/final/tables.md) and [verification evidence](v2/VALIDATION.md).

Numerical comparisons need their dataset scope, metric and service denominator.
On the 14 new series, the selected diverse candidate had a **1.0453 geometric
MAE ratio to v1**, with four series wins and ten losses. V1 remains the default;
the study does not establish universal superiority over interpolation. Recent
calibration met its frozen aggregate criterion, but its apparent width benefit
was dominated by one extreme network calibration episode.

## Preserved v1 evidence, now development data

The original study covered **648 masked gaps and 3,888 method cases** across
three real NAB streams. It reported **51.8% lower macro normalized MAE than
linear** and **14.4% lower than ExtraTrees**. Whole-gap coverage was **85.8% at a
90% target**, including **78.7% for NYC taxi**; adaptive bands were wider than the
constant-scale ablation. Its measured Linux process peak was **259 MiB**.

These remain valid descriptions of that fixed v1 artifact, not universal
accuracy or v2 performance claims. The three streams are now development data.
V2 tuning selected diverse `k=4`, but its geometric mean relative-error objective
was **3.994% worse than v1**, failing the required 5% improvement rule; hence the
default remains `analog`. This development decision is separate from the final
new-series comparison. See [selection.json](../results/v2/development/tuning/selection.json).

## Existing evidence

- Real, licensed and checksum-pinned data; runnable input examples and actual output artifacts.
- Inspectable implementations of retrieval/bridge/scale and known comparison mechanisms, with primary-source and library attribution.
- Preserved v1 artifacts and a separate v2 protocol, development selections, frozen masks, calibration boundaries and ablations.
- An explicit rejection contract for unsupported repair-export reimports, duplicate-header validation, observation-preservation tests and saved refusal reasons.
- Case-level predictions, calibration scores, summary/figure generation and an independent reconciliation script; [v2 validation](v2/VALIDATION.md) records what actually ran.
- [V2 Ubuntu/Windows CI](https://github.com/dreamybu3/propro/actions/runs/39853118660): tests, data hashes, independent saved-result verification and both product demos passed with Python 3.12. Resource measurements were made separately on a cloud Linux machine.

## A defensible research direction

The v2 question is whether full-window-separated retrieval improves masked-block
reconstruction and whether recent calibration improves the coverage/width
tradeoff. Both mechanisms have precedents. The fixed hypotheses, including
their failure criteria, are in [the v2 protocol](v2/PROTOCOL.md); their outcomes
belong in the [v2 report](v2/RESEARCH_REPORT.md), not in a presumption that a newer
version must improve accuracy.

1. **Establish a narrower contribution.** Use the [primary-source review](v2/RELATED_WORK.md) to distinguish this engineering study from claims about new retrieval or conformal theory. TKCM already uses non-overlapping patterns.
2. **Reserve genuinely new evidence for the next change.** The v2 holdout becomes inspected data after this study. Any further tuning needs a new test or an explicitly exploratory label.
3. **Compare external reference implementations where compatible.** V2 implements seasonal/Kalman/PCA controls, but is not a reproduction of all author packages or a neural-imputation benchmark. Add such comparisons only with compatible information and compute budgets.
4. **Investigate the measured failure mechanism.** Choose a further calibration or retrieval change from the retained diagnostics, then test it on new data. Existing rolling/static and fixed-neighbor-count ablations should not be rewritten after observing outcomes.
5. **Study genuine outages and decision benefit.** Controlled MCAR/MAR/MNAR masks, damaged contexts and synthetic shifts do not establish accuracy on unknown outage truth. A redundant sensor or other independent reference would support that stronger claim.
6. **Measure practical usability.** Test a representative 16 GB Windows laptop, separate cold-start latency and memory from warm inference, and evaluate an analyst workflow if appropriate. Cloud measurements and CI results are different evidence.

The current deliverables support a technical report and a reproducible portfolio
project. A future paper needs a clearly scoped contribution supported by new
evidence, verified references and external review.

## Demonstration and interview preparation

The 90-second/5-minute scripts and interview questions are in [LEARNING_GUIDE.md](LEARNING_GUIDE.md). Show a successful repair, the rejected reimport, and a boundary gap left unresolved. Explain the original-value invariant, source of calibration truth, default-method decision and actual hypothesis outcomes before discussing future work.
