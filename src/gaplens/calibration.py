"""Split calibration on whole-gap maximum standardized residuals.

The finite-sample order statistic is conformal under exchangeable gap examples.
Monitoring series are dependent and can shift: coverage here is empirical, not
an unconditional distribution-free guarantee for future operational data.
"""
from __future__ import annotations

import math
import numpy as np


def gap_score(truth: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> float:
    truth, mean, scale = (np.asarray(x, dtype=float) for x in (truth, mean, scale))
    if truth.ndim != 1 or not truth.size or truth.shape != mean.shape or truth.shape != scale.shape:
        raise ValueError("truth, mean and scale must be equal nonempty one-dimensional arrays")
    if not all(np.isfinite(x).all() for x in (truth, mean, scale)) or (scale <= 0).any():
        raise ValueError("calibration needs finite values and strictly positive scales")
    return float(np.max(np.abs(truth - mean) / scale))


def conformal_quantile(scores: list[float] | np.ndarray, alpha: float = 0.1) -> float:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("scores must be a nonempty vector of finite nonnegative numbers")
    rank = math.ceil((len(values) + 1) * (1 - alpha))
    if rank > len(values):
        raise ValueError(f"at least {math.ceil(1 / alpha) - 1} calibration gaps required for alpha={alpha}")
    return float(np.sort(values)[rank - 1])


def sample_gaps(values: np.ndarray, length: int, context: int, count: int, seed: int) -> list[tuple[int, int]]:
    """Sample complete, nonoverlapping gap-and-context windows, deterministically.

    Overlap is prevented within this call, not across lengths or random seeds.
    Return fewer examples if finite history is insufficient; never fill data.
    """
    a = np.asarray(values, dtype=float)
    if a.ndim != 1 or length < 1 or context < 1 or count < 1:
        raise ValueError("expected one-dimensional values and positive length/context/count")
    width = length + 2 * context
    if len(a) < width:
        return []
    good = np.isfinite(a)
    bad = np.r_[0, np.cumsum(~good)]
    starts = np.flatnonzero((bad[width:] - bad[:-width]) == 0)
    np.random.default_rng(seed).shuffle(starts)
    occupied = np.zeros(len(a), dtype=bool)
    result = []
    for window_start in starts:
        end = window_start + width
        if not occupied[window_start:end].any():
            occupied[window_start:end] = True
            result.append((int(window_start + context), int(window_start + context + length)))
            if len(result) == count:
                break
    return sorted(result)
