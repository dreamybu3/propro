import numpy as np
import pytest
from gaplens.calibration import conformal_quantile, gap_score, sample_gaps


def test_finite_sample_order_statistic():
    assert conformal_quantile(list(range(1, 25)), .1) == 23
    with pytest.raises(ValueError, match="calibration gaps"):
        conformal_quantile([1] * 8, .1)


def test_simultaneous_score_uses_worst_point():
    assert gap_score(np.array([0, 5]), np.array([1, 1]), np.array([1, 2])) == 2
    with pytest.raises(ValueError):
        gap_score(np.array([1]), np.array([1]), np.array([0]))


def test_sampler_respects_native_missingness_and_disjoint_context():
    values = np.arange(500, dtype=float)
    values[200:250] = np.nan
    windows = sample_gaps(values, 12, 6, 20, 17)
    assert windows == sample_gaps(values, 12, 6, 20, 17)
    assert len(windows) > 8
    for s, e in windows:
        assert np.isfinite(values[s-6:e+6]).all()
    for (_, e), (s, _) in zip(windows, windows[1:]):
        assert e + 6 <= s - 6
