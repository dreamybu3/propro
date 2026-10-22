"""Input invariants that protect both reconstruction and chronological evaluation."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gaplens.data import find_gaps, read_series


def write_csv(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "series.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_gaps_without_changing_observed_values(tmp_path):
    path = write_csv(tmp_path, "timestamp,value\n2024-01-01T00:00:00,1.25\n2024-01-01T01:00:00,\n2024-01-01T02:00:00,3.75\n")
    before = path.read_bytes()
    frame = read_series(path)
    assert frame["value"].iloc[[0, 2]].tolist() == [1.25, 3.75]
    assert frame["value"].isna().tolist() == [False, True, False]
    assert str(frame.timestamp.dt.tz) == "UTC"
    assert path.read_bytes() == before


@pytest.mark.parametrize("text,match", [
    ("time,value\n2024-01-01,1\n2024-01-02,2\n", "timestamp and value"),
    ("timestamp,value\n2024-01-01,1\n2024-01-01,2\n", "Duplicate"),
    ("timestamp,value\n2024-01-02,1\n2024-01-01,2\n", "increasing"),
    ("timestamp,value\n2024-01-01,1\n2024-01-02,2\n2024-01-04,3\n", "regular cadence"),
    ("timestamp,value\n2024-01-01,1\n,2\n", "must not be missing"),
    ("timestamp,value\ninvalid,1\n2024-01-02,2\n", "ISO-8601"),
    ("timestamp,value\n2024-01-01,1\n2024-01-02,foo\n", "numeric"),
    ("timestamp,value\n2024-01-01,1\n2024-01-02,inf\n", "Infinite"),
    ("timestamp,value\n2024-01-01,1\n", "between 2"),
    ("timestamp,value\n2024-01-01,\n2024-01-02,\n", "two finite"),
])
def test_rejects_invalid_input(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        read_series(write_csv(tmp_path, text))


def test_offsets_are_normalized_before_cadence_validation(tmp_path):
    path = write_csv(tmp_path, "timestamp,value\n2024-01-01T00:00:00+02:00,1\n2023-12-31T23:00:00Z,2\n")
    frame = read_series(path)
    assert frame.timestamp.diff().iloc[1] == pd.Timedelta(hours=1)


def test_file_limits_reject_large_input_without_loading(tmp_path, monkeypatch):
    import gaplens.data as module
    path = write_csv(tmp_path, "timestamp,value\n2024-01-01,1\n2024-01-02,2\n")
    monkeypatch.setattr(module, "MAX_FILE_BYTES", 8)
    with pytest.raises(ValueError, match="exceeds"):
        read_series(path)


def test_row_limit(tmp_path, monkeypatch):
    import gaplens.data as module
    monkeypatch.setattr(module, "MAX_ROWS", 2)
    path = write_csv(tmp_path, "timestamp,value\n2024-01-01,1\n2024-01-02,2\n2024-01-03,3\n")
    with pytest.raises(ValueError, match="between 2"):
        read_series(path)


@pytest.mark.parametrize("values,expected", [
    ([], []), ([1, 2], []), ([np.nan, np.nan], [(0, 2)]),
    ([np.nan, 1, np.nan, np.nan, 2, np.nan], [(0, 1), (2, 4), (5, 6)]),
])
def test_gap_boundaries(values, expected):
    assert find_gaps(values) == expected


def test_gap_detection_rejects_multidimensional_input():
    with pytest.raises(ValueError, match="one-dimensional"):
        find_gaps([[1.0, np.nan]])


def test_bundled_data_agrees_with_manifest():
    import hashlib
    import json
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "data/manifest.json").read_text())
    for item in manifest["datasets"]:
        path = root / item["processed_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["processed_sha256"]
        frame = read_series(path)
        assert len(frame) == item["processed_rows"]
        assert frame["value"].isna().sum() == item["native_missing_rows"]


@pytest.fixture
def fetch_module():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "scripts/fetch_data.py"
    spec = importlib.util.spec_from_file_location("fetch_data_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preparation_inserts_missing_rows_without_synthesizing_values(fetch_module):
    body = b"timestamp,value\n2024-01-01 00:00:00,1.25\n2024-01-01 02:00:00,7.75\n"
    frame = fetch_module.regularize(body, "1h")
    assert frame.value.iloc[[0, 2]].tolist() == [1.25, 7.75]
    assert np.isnan(frame.value.iloc[1])
    assert len(frame) == 3


def test_preparation_rejects_off_grid_observations(fetch_module):
    body = b"timestamp,value\n2024-01-01 00:00:00,1\n2024-01-01 00:30:00,2\n2024-01-01 02:00:00,3\n"
    with pytest.raises(ValueError, match="documented sampling grid"):
        fetch_module.regularize(body, "1h")


def test_cached_fetch_verifies_checksum_and_never_overwrites(tmp_path, fetch_module):
    path = tmp_path / "raw.csv"
    body = b"a,b\n1,2\n"
    path.write_bytes(body)
    assert fetch_module.fetch_verified("https://invalid.invalid/unused", fetch_module.sha256(body), path) == body
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        fetch_module.fetch_verified("https://invalid.invalid/unused", "0" * 64, path)
    assert path.read_bytes() == body


def test_generated_output_does_not_overwrite_user_changes(tmp_path, fetch_module):
    path = tmp_path / "processed.csv"
    path.write_bytes(b"user data")
    with pytest.raises(ValueError, match="move it aside explicitly"):
        fetch_module.write_once_or_identical(path, b"different data")
    assert path.read_bytes() == b"user data"
