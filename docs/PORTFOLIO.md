# Portfolio evidence and a path toward a paper

## Accurate positioning

GapLens is an AI-assisted research software project with an implemented numerical method, a complete CSV-to-report workflow, fixed evaluation protocols and reproducible measurements. It is not a publication, production deployment, invention of conformal prediction, or evidence that the owner personally conducted all development. The owner reported independently reproducing v1, including its 58 tests, 54,432 saved prediction rows, and Ubuntu/Windows CI checks. Do not transfer that attribution to the agent-developed v2 implementation or evaluation. Record the commands and extensions you personally complete before describing them as independent contributions.

The artifact provides concrete material to learn: avoiding hidden-target leakage, preventing exported estimates from becoming measurements, matching uncertainty to an entire missing block, separating empirical results from guarantees, and preserving failed hypotheses. No algorithmic novelty is established by using a new name or by implementing known ideas independently.

## CV wording for the v2 repository

The following wording describes the repository. Use first-person achievement language only after personally reproducing and being able to defend the relevant work; disclose AI assistance when asked or required.

- **GapLens — AI-assisted research software:** CPU-only Python tool for retrospective gap reconstruction, with historical-analog endpoint conditioning, whole-gap calibration, explicit provenance validation, and auditable CSV/JSON/HTML exports.
- Expanded reproducibility package with **14 real streams in eight provider/domain groups**, several chronological evaluation origins, shared frozen masks, development-only model selection, and seasonal, Kalman/RTS, trajectory-PCA and retrieval comparisons. Correlated channels are grouped rather than presented as independent systems.
- Preserves point errors, coverage, interval widths and refusal rates together; retains the original analog default after the diverse candidate failed its development selection rule. Held-out conclusions and failed hypotheses are reported in the [v2 technical report](v2/RESEARCH_REPORT.md), with [machine-generated tables](../results/v2/final/tables.md) and [verification evidence](v2/VALIDATION.md).

These lines describe the repository rather than assigning personal authorship.
They claim neither users nor accepted papers. If a shorter CV uses a numerical
v2 effect, copy it from the final report with its comparison, dataset scope,
service denominator and uncertainty limits; do not replace a failed hypothesis
with a favorable isolated metric. A negative result is compatible with a strong
software/reproducibility project.

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
- V1 Ubuntu/Windows CI independently reported verified by the owner. V2 CI must be assessed from its own recorded commit/check links; neither is a measurement on the owner's laptop.

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
6. **Measure practical usability.** Test the actual 16 GB Windows laptop, separate cold-start latency and memory from warm inference, and evaluate an analyst workflow if appropriate. Cloud measurements and CI results are different evidence.

The appropriate current label is a transparent technical report and portfolio
artifact. A submission decision requires a claim supported by the final results,
verified references and personal understanding of the work. No venue fit,
acceptance or publication is guaranteed; publishing this branch/draft PR is not
the same action as submitting a paper.

## Demonstration and interview preparation

The 90-second/5-minute scripts and interview questions are in [LEARNING_GUIDE.md](LEARNING_GUIDE.md). Show a successful repair, the rejected reimport, and a boundary gap left unresolved. Explain the original-value invariant, source of calibration truth, default-method decision and actual hypothesis outcomes before discussing future work.
