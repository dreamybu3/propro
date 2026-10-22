"""CPU comparators and an explicitly non-novel retrieval adaptation for v2.

These estimators share the v1 fit/predict interface. Only the historical fit
partition and exactly ``context`` observed samples on each side of a gap are
available to them. Their scales require external calibration; they are not
confidence intervals. This module deliberately leaves the v1 implementation
unchanged so the original experiment remains an exact control.
"""

from __future__ import annotations

from numbers import Integral

import numpy as np

from .core import (
    AnalogBridge, Prediction, _ReferenceMethod, _calendar, _complete_starts,
)


class DiverseAnalogBridge(AnalogBridge):
    """Greedy nearest-context retrieval with separated historical windows.

    Rank candidates as in v1, then accept a candidate only if its entire
    left-context/target/right-context window does not overlap an accepted one.
    This can return fewer than ``k`` neighbors. No overlapping replacement is
    inserted. Separation does not establish statistical independence, and
    non-overlapping pattern selection is established prior art (e.g. TKCM).
    """

    def predict(self, values, start, end, timestamps=None):
        _, context, times = self._query(values, start, end, timestamps)
        length = end - start
        starts, contexts, targets, calendar = self._candidates(length)
        squared = np.mean(((contexts - context) / self.global_scale_) ** 2, axis=1)
        if self.timestamps_ is not None and times is not None and self.seasonal_weight:
            query_calendar = _calendar(times, np.asarray([start]))[0]
            calendar_diff = (calendar - query_calendar) ** 2
            squared += self.seasonal_weight * (
                calendar_diff[:, :2].sum(axis=1)
                + 0.25 * calendar_diff[:, 2:].sum(axis=1)
            )
        distances = np.sqrt(squared)
        selected = []
        width = length + 2 * self.context
        for candidate in np.argsort(distances, kind="stable"):
            if all(abs(int(starts[candidate]) - int(starts[other])) >= width
                   for other in selected):
                selected.append(int(candidate))
                if len(selected) == self.k:
                    break
        chosen = np.asarray(selected, dtype=int)
        nearest = distances[chosen]
        weights = 1.0 / (0.05 + nearest) ** 2
        weights /= weights.sum()
        trajectories = targets[chosen].copy()
        fraction = np.arange(1, length + 1, dtype=float) / (length + 1)
        if self.bridge:
            left_delta = context[self.context - 1] - contexts[chosen, self.context - 1]
            right_delta = context[self.context] - contexts[chosen, self.context]
            trajectories += left_delta[:, None] * (1 - fraction) + right_delta[:, None] * fraction
        mean = weights @ trajectories
        if self.adaptive_scale:
            disagreement = weights @ ((trajectories - mean) ** 2)
            scale = np.sqrt(disagreement + self.noise_floor_ ** 2)
            scale *= np.sqrt(1 + nearest[0] ** 2)
        else:
            scale = np.full(length, self.noise_floor_)
        return Prediction(mean, scale, starts[chosen].astype(int).tolist(),
                          float(nearest[0]), "diverse_analog")


class ConditionalTrajectoryPCA(_ReferenceMethod):
    """Low-rank complete-window model, conditioned on the observed context.

    Each complete training window is a row of the trajectory matrix. A
    training-only scalar normalization and column mean precede PCA. At query
    time ridge regression infers latent coordinates using only the two context
    blocks; the missing columns are projected from those coordinates. Relative
    scales are the training conditional residual RMS at each target position,
    with the same positive innovation floor as v1. They are not held-out errors.

    This is our conditional trajectory-PCA comparator, not a reproduction of
    SSA gap filling or DynaMMo. Length-specific decompositions are lazy and
    cached, so benchmark timings must count their first construction.
    """

    def __init__(self, context=6, rank=4, ridge=0.01, max_candidates=4000):
        super().__init__(context)
        if not isinstance(rank, Integral) or rank < 1:
            raise ValueError("rank must be a positive integer.")
        if not np.isfinite(ridge) or ridge <= 0:
            raise ValueError("ridge must be finite and positive.")
        if not isinstance(max_candidates, Integral) or max_candidates < 2:
            raise ValueError("max_candidates must be an integer of at least two.")
        self.rank, self.ridge = int(rank), float(ridge)
        self.max_candidates = int(max_candidates)

    def fit(self, values, timestamps=None):
        super().fit(values, timestamps)
        self._projections = {}
        self.center_ = float(np.median(self.reference_[np.isfinite(self.reference_)]))
        return self

    def _projection(self, length):
        if length in self._projections:
            return self._projections[length]
        starts = _complete_starts(self.reference_, length, self.context)
        if len(starts) < 2:
            raise ValueError("Reference needs at least two complete trajectory windows.")
        if len(starts) > self.max_candidates:
            starts = starts[np.linspace(0, len(starts) - 1, self.max_candidates, dtype=int)]
        c = self.context
        windows = self.reference_[starts[:, None] + np.arange(-c, length + c)]
        normalized = (windows - self.center_) / self.global_scale_
        center = normalized.mean(axis=0)
        centered = normalized - center
        covariance = centered.T @ centered / max(len(centered) - 1, 1)
        if not np.isfinite(covariance).all():
            raise ValueError("Nonfinite trajectory covariance: input magnitude is unsupported.")
        _, vectors = np.linalg.eigh(covariance)
        rank = min(self.rank, len(starts) - 1, centered.shape[1])
        basis = vectors[:, -rank:]
        observed_indices = np.r_[np.arange(c), np.arange(c + length, 2 * c + length)]
        target_indices = np.arange(c, c + length)
        observed_basis, target_basis = basis[observed_indices], basis[target_indices]
        coefficients = np.linalg.solve(
            observed_basis.T @ observed_basis + self.ridge * np.eye(rank),
            observed_basis.T,
        ).T @ target_basis.T
        residual = centered[:, target_indices] - centered[:, observed_indices] @ coefficients
        scale = np.sqrt(np.mean(residual ** 2, axis=0) * self.global_scale_ ** 2
                        + self.noise_floor_ ** 2)
        projection = (center[observed_indices], center[target_indices], coefficients, scale)
        self._projections[length] = projection
        return projection

    def predict(self, values, start, end, timestamps=None):
        _, context, _ = self._query(values, start, end, timestamps)
        context_center, target_center, coefficients, scale = self._projection(end - start)
        normalized = (context - self.center_) / self.global_scale_ - context_center
        mean = self.center_ + self.global_scale_ * (target_center + normalized @ coefficients)
        return Prediction(mean, scale.copy(), [], 0.0, "conditional_pca")


class SeasonalBridge(_ReferenceMethod):
    """Training phase-profile baseline with a query-context level adjustment.

    ``period`` is supplied from metadata before evaluating the final data. Its
    phase zero is the first fit timestamp, on that fit series' regular grid.
    A phase median is estimated only from fit values. At prediction, the mean
    residual across the same two context blocks shifts the profile. Missing
    historical phases cause refusal rather than fabrication of observations.
    """

    def __init__(self, context=6, period=24):
        super().__init__(context)
        if not isinstance(period, Integral) or period < 2:
            raise ValueError("period must be an integer of at least two.")
        self.period = int(period)

    def fit(self, values, timestamps=None):
        super().fit(values, timestamps)
        if self.timestamps_ is None:
            raise ValueError("SeasonalBridge requires timestamps to align seasonal phases.")
        differences = np.diff(self.timestamps_.asi8)
        if not len(differences) or differences[0] <= 0 or not np.all(differences == differences[0]):
            raise ValueError("SeasonalBridge requires a regular increasing timestamp grid.")
        self.origin_ = int(self.timestamps_.asi8[0])
        self.step_ = int(differences[0])
        phase = np.arange(len(self.reference_)) % self.period
        self.profile_ = np.full(self.period, np.nan)
        self.phase_scale_ = np.full(self.period, np.nan)
        for index in range(self.period):
            samples = self.reference_[(phase == index) & np.isfinite(self.reference_)]
            if len(samples):
                self.profile_[index] = np.median(samples)
                self.phase_scale_[index] = np.sqrt(np.mean((samples - self.profile_[index]) ** 2)
                                                  + self.noise_floor_ ** 2)
        return self

    def predict(self, values, start, end, timestamps=None):
        _, context, times = self._query(values, start, end, timestamps)
        if times is None:
            raise ValueError("SeasonalBridge requires timestamps to align seasonal phases.")
        offsets = times.asi8 - self.origin_
        if np.any(offsets % self.step_):
            raise ValueError("Query timestamps must lie on the fitted seasonal grid.")
        phases = (offsets // self.step_) % self.period
        context_phases = np.r_[phases[start-self.context:start], phases[end:end+self.context]]
        target_phases = phases[start:end]
        expected_context = self.profile_[context_phases]
        expected_target = self.profile_[target_phases]
        if not np.isfinite(np.r_[expected_context, expected_target]).all():
            raise ValueError("Reference has no observations for a required seasonal phase.")
        correction = float(np.mean(context - expected_context))
        return Prediction(expected_target + correction, self.phase_scale_[target_phases].copy(),
                          [], 0.0, "seasonal")


class LocalLinearKalman(_ReferenceMethod):
    """Two-state local-linear Gaussian filter followed by an RTS smoother.

    The fit partition supplies the noise scale, median slope, and normalization.
    ``process_ratio`` controls slope-process variance relative to measurement
    variance and is chosen on development data. At prediction a fresh smoother
    sees exactly the two adjacent context blocks; the target is always missing
    internally, regardless of the caller's target array. No previous estimates
    or other query observations are read. This is a structural state-space
    comparator, not a reproduction of imputeTS or a learned neural model.
    """

    def __init__(self, context=6, process_ratio=0.1):
        super().__init__(context)
        if not np.isfinite(process_ratio) or process_ratio <= 0:
            raise ValueError("process_ratio must be finite and positive.")
        self.process_ratio = float(process_ratio)

    def fit(self, values, timestamps=None):
        super().fit(values, timestamps)
        self.center_ = float(np.median(self.reference_[np.isfinite(self.reference_)]))
        normalized = (self.reference_ - self.center_) / self.global_scale_
        diffs = np.diff(normalized)
        diffs = diffs[np.isfinite(diffs)]
        self.slope_ = float(np.median(diffs)) if len(diffs) else 0.0
        second_diffs = np.diff(normalized, n=2)
        second_diffs = second_diffs[np.isfinite(second_diffs)]
        noise = (1.4826 * np.median(np.abs(second_diffs - np.median(second_diffs)))
                 / np.sqrt(6)) if len(second_diffs) else 0.0
        floor = self.noise_floor_ / self.global_scale_
        self.observation_variance_ = float(max(noise, floor, 1e-8) ** 2)
        return self

    def predict(self, values, start, end, timestamps=None):
        _, context, _ = self._query(values, start, end, timestamps)
        c, length = self.context, end - start
        observations = np.r_[context[:c], np.full(length, np.nan), context[c:]]
        observations = (observations - self.center_) / self.global_scale_
        count = len(observations)
        transition = np.array([[1.0, 1.0], [0.0, 1.0]])
        variance = self.observation_variance_
        process = variance * self.process_ratio * np.array([[0.25, 0.5], [0.5, 1.0]])
        process += np.eye(2) * variance * 1e-9
        predicted_mean, filtered_mean = np.empty((count, 2)), np.empty((count, 2))
        predicted_cov, filtered_cov = np.empty((count, 2, 2)), np.empty((count, 2, 2))
        state = np.array([0.0, self.slope_])
        covariance = np.eye(2) * 1e6
        for index, observation in enumerate(observations):
            if index:
                state = transition @ state
                covariance = transition @ covariance @ transition.T + process
            predicted_mean[index], predicted_cov[index] = state, covariance
            if np.isfinite(observation):
                gain = covariance[:, 0] / (covariance[0, 0] + variance)
                state = state + gain * (observation - state[0])
                residual_operator = np.eye(2) - np.outer(gain, [1.0, 0.0])
                covariance = (residual_operator @ covariance @ residual_operator.T
                              + variance * np.outer(gain, gain))
            filtered_mean[index], filtered_cov[index] = state, covariance
        smoothed_mean, smoothed_cov = filtered_mean.copy(), filtered_cov.copy()
        for index in range(count - 2, -1, -1):
            gain = np.linalg.solve(predicted_cov[index + 1],
                                   transition @ filtered_cov[index]).T
            smoothed_mean[index] += gain @ (smoothed_mean[index + 1] - predicted_mean[index + 1])
            smoothed_cov[index] += gain @ (smoothed_cov[index + 1] - predicted_cov[index + 1]) @ gain.T
        mean = self.center_ + self.global_scale_ * smoothed_mean[c:c+length, 0]
        scale = self.global_scale_ * np.sqrt(
            np.maximum(smoothed_cov[c:c+length, 0, 0], 0) + variance,
        )
        return Prediction(mean, np.maximum(scale, 1e-8), [], 0.0, "kalman")
