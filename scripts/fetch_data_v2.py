#!/usr/bin/env python3
"""Fetch the immutable, licensed v2 evaluation corpus without imputing observations.

Run ``python scripts/fetch_data_v2.py`` from a pinned GapLens environment.
``--verify-only`` checks bundled processed files without network access.
Source bytes are cached under ignored ``data/raw/v2``. Existing differing files
are errors; neither downloaded sources nor prepared observations are overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def write_once_or_identical(path: Path, body: bytes) -> None:
    """Publish atomically; require explicit intervention for a differing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError(f"Existing file differs: {path}; move it aside explicitly")
        return
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(body)
        os.replace(temporary, path)
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()


def fetch_verified(url: str, expected_sha256: str, path: Path) -> bytes:
    if path.exists():
        body = path.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "GapLens-research-data/2.0"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read(MAX_DOWNLOAD_BYTES + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ValueError(
                f"Could not retrieve {url}: {exc}. Keep TLS/proxy verification enabled; "
                "bundled processed data support offline evaluation."
            ) from exc
    if len(body) > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"Source exceeds {MAX_DOWNLOAD_BYTES} bytes: {url}")
    if sha256(body) != expected_sha256:
        raise ValueError(f"Source SHA-256 mismatch: {path.name}")
    write_once_or_identical(path, body)
    return body


def prepare(body: bytes, specification: dict) -> pd.DataFrame:
    """Apply only the declared column/date conversion and insert explicit NaNs.

    COVID observations are signed *reporting increments*, not occurrence-date
    deaths. The first cumulative observation is omitted because its increment
    is unknown. Negative retrospective revisions are retained. No smoothing,
    clipping, interpolation, normalization, or outcome-dependent selection is
    performed anywhere in this preparation.
    """
    raw = pd.read_csv(io.BytesIO(body), float_precision="round_trip")
    transformation = specification["transformation"]
    if transformation == "nab":
        if list(raw.columns) != ["timestamp", "value"]:
            raise ValueError("Unexpected NAB schema")
        timestamps = pd.to_datetime(raw["timestamp"], format="ISO8601", utc=True)
        values = pd.to_numeric(raw["value"], errors="raise")
    elif transformation == "co2":
        if list(raw.columns) != ["date", "co2"]:
            raise ValueError("Unexpected CO2 schema")
        timestamps = pd.to_datetime(raw["date"].astype(str), format="%Y%m%d", utc=True)
        values = pd.to_numeric(raw["co2"], errors="raise")
    elif transformation == "brent":
        if list(raw.columns) != ["Date", "Price"]:
            raise ValueError("Unexpected Brent schema")
        timestamps = pd.to_datetime(raw["Date"], format="%Y-%m-%d", utc=True)
        values = pd.to_numeric(raw["Price"], errors="raise")
    elif transformation == "births":
        expected = ["year", "month", "date_of_month", "day_of_week", "births"]
        if list(raw.columns) != expected:
            raise ValueError("Unexpected SSA births schema")
        timestamps = pd.to_datetime(raw[["year", "month", "date_of_month"]].rename(
            columns={"date_of_month": "day"}
        ), utc=True)
        # An independently encoded weekday catches calendar assembly mistakes.
        if not (timestamps.dt.dayofweek + 1 == raw["day_of_week"]).all():
            raise ValueError("Birth-date weekday does not match the source")
        values = pd.to_numeric(raw["births"], errors="raise")
    elif transformation == "seattle":
        expected = ["date", "precipitation", "temp_max", "temp_min", "wind", "weather"]
        if list(raw.columns) != expected:
            raise ValueError("Unexpected Seattle weather schema")
        timestamps = pd.to_datetime(raw["date"], format="%Y-%m-%d", utc=True)
        values = pd.to_numeric(raw["temp_max"], errors="raise")
    elif transformation == "jhu_reporting_increment":
        if list(raw.columns[:4]) != ["Province/State", "Country/Region", "Lat", "Long"]:
            raise ValueError("Unexpected JHU schema")
        selected = raw.loc[raw["Country/Region"] == specification["country"]]
        # These three pinned countries each have one national row. Never add a
        # national total to provincial rows or silently change aggregation.
        if len(selected) != 1 or selected["Province/State"].notna().any():
            raise ValueError("Expected exactly one national JHU row")
        cumulative = pd.to_numeric(selected.iloc[0, 4:], errors="raise")
        timestamps = pd.to_datetime(cumulative.index[1:], format="%m/%d/%y", utc=True)
        values = cumulative.diff().iloc[1:]
    else:
        raise ValueError(f"Unknown transformation: {transformation}")
    index = pd.DatetimeIndex(timestamps)
    numeric = np.asarray(values, dtype=float)
    if len(index) == 0 or index.isna().any() or index.duplicated().any() or not index.is_monotonic_increasing:
        raise ValueError("Empty, invalid, duplicate, or unsorted source dates")
    if np.isinf(numeric).any():
        raise ValueError("Infinite source measurement")
    grid = pd.date_range(index[0], index[-1], freq=specification["frequency"])
    if not index.isin(grid).all():
        raise ValueError("Source dates do not lie on the declared regular grid")
    output = pd.DataFrame({"value": numeric}, index=index).reindex(grid)
    output.index.name = "timestamp"
    return output.reset_index()


def encoded(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ", na_rep="", lineterminator="\n").encode("utf-8")


def validate_processed(body: bytes, specification: dict) -> dict:
    if sha256(body) != specification["processed_sha256"]:
        raise ValueError(f"Processed SHA-256 mismatch: {specification['id']}")
    frame = pd.read_csv(io.BytesIO(body), float_precision="round_trip")
    if list(frame.columns) != ["timestamp", "value"]:
        raise ValueError("Unexpected processed schema")
    index = pd.DatetimeIndex(pd.to_datetime(frame["timestamp"], format="ISO8601", utc=True))
    values = pd.to_numeric(frame["value"], errors="raise").to_numpy(dtype=float)
    if len(index) != specification["processed_rows"] or index.isna().any():
        raise ValueError("Processed row count/date mismatch")
    expected = pd.date_range(index[0], periods=len(index), freq=specification["frequency"])
    if not index.equals(expected) or np.isinf(values).any():
        raise ValueError("Processed grid or finite-value contract violated")
    missing = int(np.isnan(values).sum())
    if missing != specification["native_missing_rows"]:
        raise ValueError("Processed native missing count mismatch")
    return {"dataset": specification["id"], "rows": len(frame), "native_missing": missing, "sha256": sha256(body)}


def run(root: Path = ROOT, verify_only: bool = False) -> list[dict]:
    manifest = json.loads((root / "data/v2/manifest.json").read_text(encoding="utf-8"))
    summaries = []
    for specification in manifest["datasets"]:
        processed = root / specification["processed_path"]
        if verify_only:
            output = processed.read_bytes()
        else:
            body = fetch_verified(specification["url"], specification["sha256"], root / specification["raw_path"])
            output = encoded(prepare(body, specification))
        row = validate_processed(output, specification)
        if not verify_only:
            write_once_or_identical(processed, output)
        summaries.append(row)
        print(json.dumps(row))
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Project directory containing data/v2/manifest.json")
    parser.add_argument("--verify-only", action="store_true", help="Verify bundled processed files offline")
    arguments = parser.parse_args()
    try:
        run(arguments.root, arguments.verify_only)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Data preparation failed: {exc}\n")


if __name__ == "__main__":
    main()
