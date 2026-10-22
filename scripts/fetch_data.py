#!/usr/bin/env python3
"""Fetch checksum-pinned NAB data and construct explicit regular observation grids.

Run from any directory: ``python /path/to/propro/scripts/fetch_data.py``.
No gap values are synthesized. Existing valid source files support offline
reruns; an unexpected existing file is an error, never silently overwritten.
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

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_once_or_identical(path: Path, data: bytes) -> None:
    """Publish a complete file atomically, preserving pre-existing differences."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Existing file differs from reproducible output: {path}; move it aside explicitly")
        return
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(data)
        os.replace(temporary, path)
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()


def fetch_verified(url: str, expected_sha256: str, destination: Path) -> bytes:
    if destination.exists():
        body = destination.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "GapLens-research-data/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read(MAX_DOWNLOAD_BYTES + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ValueError(
                f"Could not retrieve {url}: {exc}. Keep TLS/proxy verification enabled; "
                "the bundled processed datasets support offline experiments."
            ) from exc
    if len(body) > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"Download exceeds the {MAX_DOWNLOAD_BYTES} byte safety limit: {url}")
    observed = sha256(body)
    if observed != expected_sha256:
        raise ValueError(f"SHA-256 mismatch for {destination.name}: expected {expected_sha256}, got {observed}")
    write_once_or_identical(destination, body)
    return body


def regularize(body: bytes, frequency: str) -> pd.DataFrame:
    """Insert absent timestamps with NaNs; preserve every observed measurement."""
    frame = pd.read_csv(io.BytesIO(body), float_precision="round_trip")
    if list(frame.columns) != ["timestamp", "value"]:
        raise ValueError("Unexpected upstream columns")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], format="ISO8601", utc=True)
    frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    if frame["timestamp"].duplicated().any() or not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("Upstream timestamps are duplicate or unsorted")
    grid = pd.date_range(frame["timestamp"].iloc[0], frame["timestamp"].iloc[-1], freq=frequency)
    if not frame["timestamp"].isin(grid).all():
        raise ValueError("Upstream observations do not lie on the documented sampling grid")
    output = frame.set_index("timestamp").reindex(grid)
    output.index.name = "timestamp"
    return output.reset_index()


def run(root: Path = ROOT) -> list[dict]:
    manifest = json.loads((root / "data/manifest.json").read_text(encoding="utf-8"))
    summary = []
    for source in manifest["datasets"]:
        raw = root / source["raw_path"]
        body = fetch_verified(source["url"], source["sha256"], raw)
        frame = regularize(body, source["frequency"])
        if len(frame) != source["processed_rows"] or int(frame["value"].isna().sum()) != source["native_missing_rows"]:
            raise ValueError(f"Unexpected processed counts for {source['id']}")
        output = frame.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ", na_rep="").encode("utf-8")
        if sha256(output) != source["processed_sha256"]:
            raise ValueError(f"Processed checksum mismatch for {source['id']}; check pinned pandas version")
        write_once_or_identical(root / source["processed_path"], output)
        row = {"dataset": source["id"], "rows": len(frame), "native_missing": source["native_missing_rows"], "sha256": sha256(output)}
        summary.append(row)
        print(json.dumps(row))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Project directory containing data/manifest.json")
    arguments = parser.parse_args()
    try:
        run(arguments.root)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Data preparation failed: {exc}\n")


if __name__ == "__main__":
    main()
