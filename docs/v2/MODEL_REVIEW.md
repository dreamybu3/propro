# Independent model implementation review

Reviewed on 2026-10-22 by an AI agent other than the author of
`src/gaplens/models_v2.py`, before the new final holdout was evaluated. The
review used source inspection, synthetic inputs, existing unit tests, and two
independent numerical oracles. No final-data predictions, scores, or plots were
used. After reporting the findings, the lead authorized this reviewer to make
the two narrowly scoped validation fixes described below.

## Findings and resolutions

| Finding | Reproduction and consequence | Resolution |
|---|---|---|
| Seasonal phase arithmetic depended on datetime storage units. | `DatetimeIndex.asi8` uses the index's own unit. Identical physical labels with fit timestamps stored in microseconds and query timestamps in nanoseconds gave an 11-unit maximum error on an exact 24-phase toy. The reversed unit combination incorrectly refused. | Normalize both fit and query indices to nanoseconds before phase arithmetic. Test every pair of seconds, milliseconds, microseconds, and nanoseconds: 16 combinations. |
| A failed refit could combine a new reference with old learned state. | Fit a model, populate its cache, then call `fit(reference * 7 + 100, timestamps[:-1])`. Timestamp validation raised after `reference_` had changed; subsequent predictions still used old cached trajectories/profile/parameters. This affected the shared base used by both public v1-compatible and v2 estimators. | Compute and validate timestamps and scale statistics in local variables before assigning fitted state. Seasonal timestamp/grid validation also runs before base state publication. Regressions check both a failed initial fit and preservation of an existing fitted model, including its predictions and reference. |
| Finite source measurements can overflow reference-scale arithmetic. | Alternating finite values near the float limit produce an infinite standard deviation/scale. | Reject nonfinite computed scales without overwriting a previously fitted model. This does not change the order of valid numerical operations. |

The fixes change validation and datetime representation handling. They do not
change retrieval ranking, bridge correction, relative-scale formulas, or the
operation order for supported v1 numerical inputs. The exact original
`core.py` from checkpoint `ecf22de604d14e747bf6607d50b62b4870d24fcf` is retained
as `src/gaplens/_core_v1.py` for literal research controls. That archival module
intentionally retains its original failed-refit behavior; research creates a
new estimator for each fit and does not recover/reuse an estimator after a
failed fit. The public product imports the corrected `core.py`.

The reviewer compared the archived module bytes with `git show` of the baseline:
they match exactly (SHA-256
`b656f9ba2ef3cd2f36ac2b802a0beedd23ead0601aaa5f59a8f9b47ef433c295`).
Supported-input predictions from current AnalogBridge, LinearBridge, and
ExtraTreesBridge matched the frozen implementation exactly on the review's
synthetic reference/query, including means, scales, and neighbor indices.

## Numerical checks

**Conditional trajectory PCA.** The implemented projection is algebraically
equivalent to conditioning a learned low-rank window basis on the two observed
context blocks with ridge regularization. An independent oracle computes the
basis with a rectangular SVD, then solves an augmented least-squares problem
instead of forming covariance eigenvectors and normal equations. On a noisy
synthetic cumulative signal, predictions agreed to about `8.7e-14`; the saved
test checks both means and training residual scales. Training residual RMS is
correctly described as a relative scale requiring separate calibration, not a
held-out uncertainty estimate. All means, bases, and normalization use the fit
partition only.

**Local-linear Kalman/RTS comparator.** The filter uses a two-state level/slope
model, Joseph-form measurement covariance update, and the standard RTS gain.
The independent oracle constructs the entire joint Gaussian distribution and
conditions its observation covariance in one dense solve, without a filter or
smoother recursion. Mean and scale differences were approximately `4e-7` on the
review signal; tests allow `1e-6` absolute/relative tolerance because the diffuse
prior has variance `1e6` and the dense covariance calculation subtracts large
near-equal terms. Prediction scale includes observation noise. The estimator
fits its normalization/noise parameters on history and constructs a fresh
smoother from only the adjacent context at each query.

**Seasonal bridge.** The phase profile is a fit-only median per metadata-defined
period. The context residual mean changes its level. An exact periodic signal
with a known level shift is recovered, unseen historical phases refuse, and
unit-invariant timestamp arithmetic is now covered. A supplied period is a
metadata prior, not proof that a particular source is seasonal.

**Diverse retrieval.** Stable sorting matches the v1 ranking. Greedy selection
excludes overlapping complete historical windows, including both contexts.
Returning fewer than `k` candidates is intentional; the code does not refill
with overlapping candidates. The one-neighbor case matches v1 exactly. Window
separation is not statistical independence or an established novelty claim.

## Information boundaries, caches, and limitations

Existing tests poison all hidden targets and nonlocal query values while
holding the two permitted context blocks fixed; means, scales, and selected
neighbors remain identical. Additional review probes replaced every nonlocal
query observation with NaN, with the same result. Input arrays are not modified.
These checks concern available information, not a claim that the caller's
unmasked full array is a safe research protocol: the runner must still mask
hidden truth explicitly and retain it only for scoring.

For all four v2 models, a successful refit after prior predictions matched a
freshly constructed model on the new reference exactly. Mutating returned
prediction arrays did not alter later results. PCA and retrieval caches are
length-specific and reset after a successful fit. Cache construction is lazy
and belongs in the benchmark's first-query/calibration preparation costs.

Determinism was checked within the pinned environment. Eigenvalue degeneracy
and platform-specific floating-point libraries can prevent bitwise identity
of a PCA decomposition across machines; no broader bitwise guarantee follows.
All estimators rely on the high-level input reader and benchmark for the full
regular-grid/chronology contract; the shared low-level timestamp helper checks
length and missing dates. The product checks reconstructed output finiteness.
The review found no remaining blocking numerical or hidden-target-access defect
for the declared supported inputs, but it is not a proof over arbitrary floating
point magnitudes, caller mutations of estimator attributes, or malformed inputs
outside the product contract.

## Validation evidence

```bash
python -m pytest tests/test_model_refit.py tests/test_model_oracles.py \
  tests/test_models_v2.py tests/test_core.py -q
```

**67 tests passed** in the Linux cloud environment. The two new files contain
failed-fit/state regressions, all datetime-unit combinations, and the independent
Gaussian/SVD oracle checks. This focused result precedes the final whole-project
validation and does not claim that final experiments or Windows CI have already
run for v2.
