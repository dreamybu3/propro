"""Independent behavioral checks for evaluation-data preparation and provenance."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gaplens.data import read_series

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fetch_v2():
    specification = importlib.util.spec_from_file_location("fetch_v2_under_test", ROOT / "scripts/fetch_data_v2.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_jhu_reports_keep_negative_revisions_and_omit_unknown_initial_increment(fetch_v2):
    source = (
        b"Province/State,Country/Region,Lat,Long,1/1/20,1/2/20,1/3/20,1/4/20\n"
        b",Japan,36,138,8,13,11,17\n"
        b",Other,0,0,900,1000,1100,1200\n"
    )
    output = fetch_v2.prepare(source, {"transformation": "jhu_reporting_increment", "country": "Japan", "frequency": "D"})
    assert output.value.tolist() == [5.0, -2.0, 6.0]
    assert output.timestamp.tolist() == list(pd.date_range("2020-01-02", periods=3, freq="D", tz="UTC"))


def test_jhu_refuses_mixing_province_and_national_totals(fetch_v2):
    source = (
        b"Province/State,Country/Region,Lat,Long,1/1/20,1/2/20\n"
        b",Japan,36,138,8,13\nTokyo,Japan,36,138,2,3\n"
    )
    with pytest.raises(ValueError, match="exactly one national"):
        fetch_v2.prepare(source, {"transformation": "jhu_reporting_increment", "country": "Japan", "frequency": "D"})


def test_weekly_co2_preserves_source_and_grid_missingness(fetch_v2):
    source = b"date,co2\n19580329,316.1\n19580412,\n19580419,317.6\n"
    output = fetch_v2.prepare(source, {"transformation": "co2", "frequency": "7D"})
    assert len(output) == 4
    assert output.value.iloc[[0, 3]].tolist() == [316.1, 317.6]
    assert output.value.isna().tolist() == [False, True, True, False]
    assert output.timestamp.iloc[1] == pd.Timestamp("1958-04-05", tz="UTC")


def test_birth_calendar_uses_real_leap_day_and_checks_weekday(fetch_v2):
    source = b"year,month,date_of_month,day_of_week,births\n2000,2,28,1,10\n2000,2,29,2,12\n2000,3,1,3,14\n"
    output = fetch_v2.prepare(source, {"transformation": "births", "frequency": "D"})
    assert output.timestamp.dt.day.tolist() == [28, 29, 1]
    assert output.value.tolist() == [10.0, 12.0, 14.0]
    with pytest.raises(ValueError, match="weekday"):
        fetch_v2.prepare(source.replace(b"2000,2,29,2", b"2000,2,29,3"), {"transformation": "births", "frequency": "D"})


@pytest.mark.parametrize("rows", [
    b"2020-01-01,1\n2020-01-01,2\n",
    b"2020-01-02,1\n2020-01-01,2\n",
    b"2020-01-01,1\n2020-01-01T12:00:00,2\n2020-01-02,3\n",
])
def test_nab_rejects_duplicate_unsorted_or_off_grid_dates(fetch_v2, rows):
    with pytest.raises(ValueError):
        fetch_v2.prepare(b"timestamp,value\n" + rows, {"transformation": "nab", "frequency": "D"})


def test_bundled_v2_hashes_grids_provenance_and_source_grouping(fetch_v2):
    manifest = json.loads((ROOT / "data/v2/manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["datasets"]) == 14
    assert len({r["source_group"] for r in manifest["datasets"]}) == 8
    assert len({r["collection"] for r in manifest["datasets"]}) == 6
    assert not set(manifest["development_only"]) & {r["id"] for r in manifest["datasets"]}
    for item in manifest["datasets"]:
        path = ROOT / item["processed_path"]
        fetch_v2.validate_processed(path.read_bytes(), item)
        frame = read_series(path)
        assert np.isfinite(frame.value).sum() == item["finite_rows"]
        assert item["source_commit"] in item["url"]
    for item in manifest["provenance_files"]:
        assert fetch_v2.sha256((ROOT / item["local_path"]).read_bytes()) == item["sha256"]


def test_v2_output_refuses_overwrite_and_cached_source_requires_hash(fetch_v2, tmp_path):
    path = tmp_path / "source.csv"
    body = b"unmodified observation bytes\n"
    path.write_bytes(body)
    with pytest.raises(ValueError, match="differs"):
        fetch_v2.write_once_or_identical(path, b"changed\n")
    with pytest.raises(ValueError, match="SHA-256"):
        fetch_v2.fetch_verified("https://invalid.example/unused", "0" * 64, path)
    assert path.read_bytes() == body
