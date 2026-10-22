"""Strict, non-destructive input validation and gap detection.

Dataset-specific regularization belongs to ``scripts/fetch_data.py``. User
inputs are never silently sorted, deduplicated, resampled, or interpolated.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MAX_ROWS = 200_000
MAX_FILE_BYTES = 32 * 1024 * 1024


def read_series(path: str | Path) -> pd.DataFrame:
    """Read a regular CSV with ``timestamp,value`` columns.

    Missing numeric values are allowed. Timestamps must be valid ISO-8601,
    unique, increasing, and equally spaced. Offset-aware times are converted
    to UTC; naive times are interpreted as UTC, without changing clock values.
    Additional columns are ignored so an exported result can be inspected
    alongside its original values. The original file is never modified.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Input CSV does not exist or is not a file: {path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"Input CSV exceeds {MAX_FILE_BYTES // (1024 * 1024)} MiB")
    try:
        frame = pd.read_csv(
            path, nrows=MAX_ROWS + 1, dtype={"timestamp": "string"},
            float_precision="round_trip",
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise ValueError(f"Cannot parse input CSV: {exc}") from exc
    if not {"timestamp", "value"}.issubset(frame.columns):
        raise ValueError("CSV must contain timestamp and value columns")
    if not 2 <= len(frame) <= MAX_ROWS:
        raise ValueError(f"CSV must contain between 2 and {MAX_ROWS:,} rows")
    if frame["timestamp"].isna().any():
        raise ValueError("Timestamps must not be missing")
    try:
        timestamps = pd.to_datetime(frame["timestamp"], format="ISO8601", utc=True)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Timestamps must be valid ISO-8601 dates/times") from exc
    if timestamps.isna().any():
        raise ValueError("Timestamps must not be missing")
    if timestamps.duplicated().any():
        raise ValueError("Duplicate timestamps are not allowed")
    if not timestamps.is_monotonic_increasing:
        raise ValueError("Timestamps must be strictly increasing; input is not sorted automatically")
    differences = timestamps.diff().iloc[1:]
    if not differences.eq(differences.iloc[0]).all():
        raise ValueError(
            "Timestamps must have a regular cadence; explicitly insert absent timestamps "
            "with empty values before repair"
        )
    try:
        values = pd.to_numeric(frame["value"], errors="raise").astype(float)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Values must be numeric; use empty cells for missing observations") from exc
    if np.isinf(values.to_numpy()).any():
        raise ValueError("Infinite values are not allowed")
    if values.notna().sum() < 2:
        raise ValueError("At least two finite observations are required")
    return pd.DataFrame({"timestamp": timestamps, "value": values})


def find_gaps(values: np.ndarray | list[float] | pd.Series) -> list[tuple[int, int]]:
    """Return half-open ``(start, end)`` runs of missing values, including edges."""
    try:
        array = np.asarray(values, dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError("Gap detection requires numeric values") from exc
    if array.ndim != 1:
        raise ValueError("Gap detection requires a one-dimensional array")
    missing = np.isnan(array)
    boundaries = np.diff(np.r_[False, missing, False].astype(np.int8))
    return list(zip(np.flatnonzero(boundaries == 1).tolist(), np.flatnonzero(boundaries == -1).tolist()))
