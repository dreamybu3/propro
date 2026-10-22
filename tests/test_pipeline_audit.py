"""Behavioral regressions from the independent v2 product audit."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gaplens.pipeline import RepairConfig, repair


def write_inputs(directory: Path, missing=(), *, sparse_reference=False):
    timestamps = pd.date_range("2020-01-01", periods=2700, freq="h", tz="UTC")
    history = np.arange(2400, dtype=float)
    if sparse_reference:
        # Plenty of finite observations, but never a complete training window.
        history[::5] = np.nan
    query = np.arange(300, dtype=float)
    for start, end in missing:
        query[start:end] = np.nan
    reference_path, query_path = directory / "reference.csv", directory / "query.csv"
    pd.DataFrame({"timestamp": timestamps[:2400], "value": history}).to_csv(reference_path, index=False)
    pd.DataFrame({"timestamp": timestamps[2400:], "value": query}).to_csv(query_path, index=False)
    return reference_path, query_path, query


@pytest.mark.parametrize("blocked_name", ["repaired.csv", "report.json", "report.html"])
def test_artifact_directory_is_rejected_before_any_existing_file_changes(tmp_path, blocked_name):
    reference, query, _ = write_inputs(tmp_path, [(80, 88)])
    output = tmp_path / "output"
    output.mkdir()
    for name in ("repaired.csv", "report.json", "report.html"):
        if name == blocked_name:
            (output / name).mkdir()
            (output / name / "keep.txt").write_text("user-owned directory contents")
        else:
            (output / name).write_text(f"previous artifact: {name}")
    (output / "notes.txt").write_text("unrelated user notes")
    watched = [reference, query, *(path for path in output.rglob("*") if path.is_file())]
    before = {path: path.read_bytes() for path in watched}

    with pytest.raises(ValueError, match="Output artifact must be a regular file or absent"):
        repair(reference, query, output, overwrite=True)

    assert (output / blocked_name).is_dir()
    assert {path: path.read_bytes() for path in watched} == before
    assert {path for path in output.rglob("*") if path.is_file()} == set(watched[2:])


@pytest.mark.parametrize("missing,reason", [
    ([], None),
    ([(0, 3), (298, 300)], "boundary context is unavailable"),
    ([(80, 140)], "exceeding max_gap"),
    ([(80, 82), (85, 87)], "Context contains another gap"),
])
def test_extra_trees_exports_ineligible_queries_without_complete_training_windows(tmp_path, missing, reason):
    reference, query, original = write_inputs(tmp_path, missing, sparse_reference=True)
    source_bytes = {path: path.read_bytes() for path in (reference, query)}
    output = tmp_path / "output"

    report = repair(reference, query, output, RepairConfig(method="extra-trees"))

    assert report["summary"] == {
        "gaps": len(missing), "reconstructed_gaps": 0, "unresolved_gaps": len(missing),
        "missing_samples": int(np.isnan(original).sum()), "reconstructed_samples": 0,
        "unchanged_observations": int(np.isfinite(original).sum()),
    }
    assert all(reason in gap["reason"] for gap in report["gaps"])
    assert all(gap["calibration_count"] == 0 and gap["quantile"] is None for gap in report["gaps"])
    exported = pd.read_csv(output / "repaired.csv")
    np.testing.assert_array_equal(exported.value.to_numpy(), original)
    np.testing.assert_array_equal(exported.original_value.to_numpy(), original)
    assert exported.loc[np.isfinite(original), "status"].eq("observed").all()
    assert exported.loc[np.isnan(original), "status"].eq("unresolved").all()
    assert exported[["lower", "upper"]].isna().all().all()
    assert (output / "report.json").is_file() and (output / "report.html").is_file()
    assert {path: path.read_bytes() for path in source_bytes} == source_bytes
