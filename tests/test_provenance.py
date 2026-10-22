"""Regression for v1 silently promoting estimates to measured truth."""
from pathlib import Path
import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from gaplens.data import read_series
from gaplens.pipeline import repair

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("role", ["input", "reference"])
@pytest.mark.parametrize("new_gap", [False, True])
def test_export_cannot_become_observed_query_or_calibration_truth(tmp_path, role, new_gap):
    # Real saved export includes 42 estimates, with provenance and intervals.
    original = pd.read_csv(ROOT / "results/demo/repaired.csv", float_precision="round_trip")
    assert (original.status == "reconstructed").sum() == 42
    if new_gap:
        original.loc[30:32, "value"] = np.nan
    exported = tmp_path / "export.csv"
    original.to_csv(exported, index=False)
    before = exported.read_bytes()
    reference = exported if role == "reference" else ROOT / "examples/reference.csv"
    query = exported if role == "input" else ROOT / "examples/with_gaps.csv"
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="Repair-export/provenance"):
        repair(reference, query, output)
    assert not output.exists()
    # Rejection cannot erase/change status, original values or interval metadata.
    assert exported.read_bytes() == before


def test_failed_reimport_preserves_existing_report_and_reasons(tmp_path):
    result = repair(ROOT / "examples/reference.csv", ROOT / "examples/with_gaps.csv", tmp_path / "first")
    assert result["summary"]["unchanged_observations"] == 2022
    first = tmp_path / "first"
    before = {p.name: p.read_bytes() for p in first.iterdir()}
    existing = tmp_path / "existing"
    existing.mkdir()
    for name, content in before.items():
        (existing / name).write_bytes(content)
    with pytest.raises(ValueError, match="Do not remove provenance"):
        repair(ROOT / "examples/reference.csv", first / "repaired.csv", existing, overwrite=True)
    assert before == {p.name: p.read_bytes() for p in first.iterdir()}
    assert before == {p.name: p.read_bytes() for p in existing.iterdir()}
    assert json.loads(before["report.json"])["gaps"] == result["gaps"]


def test_cli_reimport_explains_measurement_contract(tmp_path):
    run = subprocess.run([sys.executable, "-m", "gaplens.cli", "repair", "--reference",
                          str(ROOT / "examples/reference.csv"), "--input",
                          str(ROOT / "results/demo/repaired.csv"), "--output", str(tmp_path / "out")],
                         capture_output=True, text=True)
    assert run.returncode == 2
    assert "original timestamp,value measurement CSV" in run.stderr
    assert "Traceback" not in run.stderr
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("column", ["value", "timestamp", "comment"])
def test_duplicate_csv_headers_rejected_before_pandas_mangling(tmp_path, column):
    path = tmp_path / "ambiguous.csv"
    path.write_text(f"timestamp,value,{column},{column}\n2024-01-01,1,999,777\n2024-01-02,2,888,666\n")
    with pytest.raises(ValueError, match="Duplicate CSV column"):
        read_series(path)


def test_ordinary_metadata_columns_remain_supported(tmp_path):
    path = tmp_path / "measurement.csv"
    path.write_text("timestamp,value,sensor\n2024-01-01,1,a\n2024-01-02,2,a\n")
    assert read_series(path).value.tolist() == [1, 2]
