# Product audit for v2

The independent implementation audit started from v1 checkpoint
`ecf22de604d14e747bf6607d50b62b4870d24fcf`. It examined CSV validation,
chronological splitting, reconstruction and calibration, refusal reasons,
artifact publication, and the self-contained HTML report. The confirmed
provenance reimport defect supplied by the user is addressed by the separate
reader-contract change; this audit does not treat its prior presence as a
statistical-method failure.

## Confirmed findings and disposition

| Finding | Reproduction on v1 | Change / scope |
| --- | --- | --- |
| Ambiguous duplicate CSV headers | A file headed `timestamp,value,value` with rows `2024-01-01,1,999` and `2024-01-02,2,888` was accepted as values `[1, 2]`; pandas renamed and the reader discarded the second value column. | Reported to the reader-contract work item. Duplicate names must be rejected before pandas header mangling. |
| A predictable overwrite failure partially replaced a previous result | Generate a report, replace `report.json` with a directory, change one input observation, and run with `--overwrite`. v1 replaced `repaired.csv`, then raised `IsADirectoryError`, leaving the old HTML paired with new CSV. | The pipeline now checks all three artifact destinations before calculation or publication. An existing non-file destination produces an actionable error without changing any artifact, source file, or directory contents. |
| ExtraTrees training prevented an otherwise valid refusal report | In a 2,400-row reference, mask every fifth sample; provide a 300-row query with only its first three samples missing. There are sufficient finite reference observations but no complete training window. v1 ExtraTrees failed before recording the boundary refusal; analog and linear exported the correct refusal. | Model fitting now occurs only when a gap passes length, boundary, and observed-context checks. No-gap inputs and inputs containing only unsupported gaps export intact observations and explicit refusal records without requiring unnecessary model training. |

The overwrite fix preserves the existing publication contract: content is
staged and each named artifact is replaced individually. It does not introduce
a multi-file transaction or claim crash consistency. A concurrent filesystem
change or an unexpected I/O failure during publication can still interrupt the
sequence. Unrelated files are never selected for replacement.

Lazy fitting does not relax CSV, chronology, cadence, grid, or minimum reference
split validation. For an eligible gap, fitting and calibration still need to
succeed under the existing rules. In the subsequent integration step, an
estimator's `ValueError` during fitting was made an explicit support refusal for
eligible gaps, retaining separate boundary/context refusal reasons. The CLI
exports these unresolved results and honors `--require-complete` with exit code
3. Invalid files, chronology, grids, and configuration remain fatal input
errors. The training/calibration row counts describe the reserved history split,
including when no gap requires an estimator.

## Executed verification

Before modifications, the 50 existing tests in `test_core.py`,
`test_calibration.py`, `test_data.py`, and `test_pipeline.py` passed on Linux
with Python 3.12. The following additional probes ran against v1:

| Probe | Observed behavior |
| --- | --- |
| Constant reference and query, one eight-sample interior gap | Analog, linear, and ExtraTrees reconstructed all eight samples and preserved all 292 measured query values. Bands may have zero width on perfectly predicted constant calibration data; this is not evidence of guaranteed uncertainty coverage. |
| Finite values of magnitude `1e180` | Analog and linear left the gap unresolved with a finite-scale calibration error. ExtraTrees rejected its unsupported float32 feature range. No nonfinite prediction was published as a reconstructed value. |
| Output artifact symlink pointing to the input file | Rejected before export; input bytes were unchanged. |
| Separate training/calibration data and masked interiors | Code inspection and existing invariant tests found no new path by which a hidden query value entered model features or calibration truth. |
| UTC conversion, cadence/grid checks, boundary/neighboring/long gaps, HTML escaping | Existing behavioral tests passed; no additional substantive defect was established by this audit. |

After the two pipeline fixes, this command passed **20 tests**:

```bash
python -m pytest -q tests/test_pipeline_audit.py tests/test_pipeline.py
```

The new regression module contains seven cases: directory conflicts at each of
the three artifact names, plus ExtraTrees exports for gap-free, boundary-only,
too-long, and mutually obstructed gaps. These tests check source and observation
preservation, exact refusal counts, missing uncertainty on unresolved rows, and
the existence of all export formats. The existing pipeline tests additionally
exercise successful reconstruction with each supported estimator, calibration
insufficiency, historical-neighbor boundaries and JSON round-tripping, output protection,
CLI errors, and HTML escaping. This local audit does not establish performance
on the user's laptop or replace remote Windows/Linux CI evidence.

## Optional diverse retrieval integration

`--method diverse` uses `DiverseAnalogBridge` with the existing context and
neighbor options. `analog` remains the CLI and Python configuration default.
The report names the selected method and explains that the established rule of
selecting complete historical windows without overlap can return fewer than
the requested neighbors and does not establish statistical independence.

The additional CLI regression uses a synthetic oscillatory reference and a
later query with eight hidden samples. It checks the selected method, separated
historical windows, measured-value preservation, reconstructed statuses,
calibrated intervals, and all three artifacts. A separate case checks that
unusable ExtraTrees training history produces saved refusals for eligible gaps
without obscuring a boundary refusal. After this integration, the following
command passed **24 tests**:

```bash
python -m pytest -q tests/test_pipeline_audit.py tests/test_pipeline.py tests/test_entrypoint.py
```
