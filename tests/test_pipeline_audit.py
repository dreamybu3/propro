"""Behavioral regressions from the independent v2 product audit."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gaplens.pipeline import RepairConfig, repair
from gaplens.cli import main, parser


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


def test_diverse_cli_preserves_observations_and_exports_separated_neighbors(tmp_path, capsys):
    reference, query, _ = write_inputs(tmp_path)
    indices = np.arange(2700)
    signal = 10 + .002 * indices + 2 * np.sin(2 * np.pi * indices / 12) + .3 * np.cos(indices / 5.3)
    original = signal[2400:].copy()
    original[80:88] = np.nan
    for path, values in ((reference, signal[:2400]), (query, original)):
        frame = pd.read_csv(path)
        frame["value"] = values
        frame.to_csv(path, index=False)
    before = {path: path.read_bytes() for path in (reference, query)}
    output = tmp_path / "diverse-output"

    code = main(["repair", "--reference", str(reference), "--input", str(query),
                 "--output", str(output), "--method", "diverse", "--neighbors", "8",
                 "--require-complete"])

    assert code == 0
    assert "Preserved 292 observed values" in capsys.readouterr().out
    report = json.loads((output / "report.json").read_text())
    assert report["config"]["method"] == "diverse"
    assert report["config"]["neighbors"] == 8
    assert report["summary"]["reconstructed_samples"] == 8
    assert any("does not establish statistical independence" in warning for warning in report["warnings"])
    gap = report["gaps"][0]
    starts = sorted(neighbor["reference_index"] for neighbor in gap["neighbors"])
    assert 1 < len(starts) <= 8
    assert all(right - left >= 20 for left, right in zip(starts, starts[1:]))
    assert all(start + 8 + 6 <= report["reference"]["training_rows"] for start in starts)
    assert gap["calibration_count"] >= 9
    saved = pd.read_csv(output / "repaired.csv", float_precision="round_trip")
    measured = np.isfinite(original)
    np.testing.assert_array_equal(saved.loc[measured, "value"], original[measured])
    np.testing.assert_array_equal(saved.loc[measured, "original_value"], original[measured])
    assert saved.loc[measured, "status"].eq("observed").all()
    assert saved.loc[~measured, "status"].eq("reconstructed").all()
    assert saved.loc[~measured, "original_value"].isna().all()
    assert saved.loc[measured, ["lower", "upper"]].isna().all().all()
    repaired = saved.loc[~measured]
    assert (repaired.lower < repaired.value).all()
    assert (repaired.value < repaired.upper).all()
    assert "diverse" in (output / "report.html").read_text(encoding="utf-8")
    assert {path: path.read_bytes() for path in before} == before


def test_analog_remains_the_default_product_method():
    args = parser().parse_args(["repair", "--reference", "reference.csv", "--input", "input.csv", "--output", "output"])
    assert args.method == RepairConfig().method == "analog"


def test_eligible_gaps_with_unusable_training_support_export_refusals(tmp_path, capsys):
    reference, query, original = write_inputs(tmp_path, [(0, 3), (80, 88), (160, 170)], sparse_reference=True)
    output = tmp_path / "output"

    code = main(["repair", "--reference", str(reference), "--input", str(query),
                 "--output", str(output), "--method", "extra-trees", "--require-complete"])

    assert code == 3
    assert not capsys.readouterr().err
    report = json.loads((output / "report.json").read_text())
    assert report["summary"]["unresolved_gaps"] == 3
    assert report["summary"]["reconstructed_samples"] == 0
    assert "boundary context is unavailable" in report["gaps"][0]["reason"]
    assert all("Insufficient usable training/reference support" in gap["reason"] for gap in report["gaps"][1:])
    saved = pd.read_csv(output / "repaired.csv")
    np.testing.assert_array_equal(saved.value.to_numpy(), original)
    assert saved[["lower", "upper"]].isna().all().all()
