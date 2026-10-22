"""CPU-only, historical-reference methods for offline gap reconstruction.

Every estimator learns from ``fit`` data only. At prediction time only the
context outside [start, end) and known timestamps are read; hidden gap values
are never features. ``scale`` is a relative error scale, NOT an interval or a
coverage guarantee. The separate calibration layer turns scales into bands.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


@dataclass(frozen=True)
class Prediction:
    mean: np.ndarray
    scale: np.ndarray
    neighbors: list[int]
    distance: float
    method: str


def _series(values: np.ndarray) -> np.ndarray:
    try:
        result = np.asarray(values, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise ValueError("Values must be a one-dimensional numeric array.") from exc
    if result.ndim != 1:
        raise ValueError("Values must be a one-dimensional numeric array.")
    if np.isinf(result).any():
        raise ValueError("Infinite values are not supported; use NaN for missing data.")
    return result


def _timestamps(timestamps, size: int) -> pd.DatetimeIndex | None:
    if timestamps is None:
        return None
    try:
        result = pd.DatetimeIndex(timestamps)
    except (ValueError, TypeError) as exc:
        raise ValueError("Timestamps must be parseable datetimes.") from exc
    if len(result) != size or result.hasnans:
        raise ValueError("Timestamps must match the values and contain no NaT.")
    return result


def _calendar(timestamps: pd.DatetimeIndex | None, indices: np.ndarray) -> np.ndarray:
    if timestamps is None:
        return np.zeros((len(indices), 4), dtype=np.float64)
    selected = timestamps[indices]
    hour = selected.hour.to_numpy() + selected.minute.to_numpy() / 60.0
    hour = hour + selected.second.to_numpy() / 3600.0
    daily = 2 * np.pi * hour / 24.0
    weekly = 2 * np.pi * (selected.dayofweek.to_numpy() + hour / 24.0) / 7.0
    return np.column_stack((np.sin(daily), np.cos(daily), np.sin(weekly), np.cos(weekly)))


def _complete_starts(values: np.ndarray, length: int, context: int) -> np.ndarray:
    width = length + 2 * context
    if len(values) < width:
        return np.empty(0, dtype=np.int64)
    valid = np.isfinite(sliding_window_view(values, width)).all(axis=1)
    return np.flatnonzero(valid) + context


class _ReferenceMethod:
    def __init__(self, context: int = 6):
        if not isinstance(context, Integral) or context < 1:
            raise ValueError("context must be a positive integer.")
        self.context = int(context)

    def fit(self, values: np.ndarray, timestamps=None):
        reference = _series(values)
        finite = reference[np.isfinite(reference)]
        if len(finite) < 2 * self.context + 1:
            raise ValueError("Reference has too few finite observations for the context.")
        # Validate and compute before publishing fitted state. A failed refit
        # must not combine a new reference with an old model/window cache.
        fitted_reference = reference.copy()
        fitted_timestamps = _timestamps(timestamps, len(reference))
        center = np.median(finite)
        robust = 1.4826 * np.median(np.abs(finite - center))
        global_scale = float(max(robust, np.std(finite), 1e-8))
        diffs = np.diff(reference)
        diffs = diffs[np.isfinite(diffs)]
        if len(diffs):
            noise = 1.4826 * np.median(np.abs(diffs - np.median(diffs))) / np.sqrt(2)
        else:
            noise = 0.0
        # Positive even for constant or perfectly linear reference signals.
        noise_floor = float(max(noise, 0.01 * global_scale, 1e-8))
        if not np.isfinite(global_scale) or not np.isfinite(noise_floor):
            raise ValueError("Nonfinite reference scale: input magnitude is unsupported.")
        self.reference_ = fitted_reference
        self.timestamps_ = fitted_timestamps
        self.global_scale_ = global_scale
        self.noise_floor_ = noise_floor
        return self

    def _query(self, values, start, end, timestamps):
        if not hasattr(self, "reference_"):
            raise ValueError("Call fit before predict.")
        query = _series(values)
        if not isinstance(start, Integral) or not isinstance(end, Integral):
            raise ValueError("Gap boundaries must be integer indices.")
        if start < self.context or end > len(query) - self.context or end <= start:
            raise ValueError("Gap needs a positive length and complete context on both sides.")
        observed = np.concatenate((query[start - self.context:start], query[end:end + self.context]))
        if not np.isfinite(observed).all():
            raise ValueError("Observed context contains missing values.")
        times = _timestamps(timestamps, len(query))
        return query, observed, times


class AnalogBridge(_ReferenceMethod):
    """Context-neighbor reconstruction with endpoint-conditioned analogs.

    Historical windows are ranked by normalized observed-context distance and
    an optional calendar distance. Each selected historical gap is corrected by
    the linear interpolation of its two endpoint residuals. Inverse-distance
    weights average these corrected trajectories. Relative uncertainty combines
    their disagreement, an innovation floor, and nearest-context novelty.

    The method is an explicit engineering combination of established analog,
    interpolation, and local-scale ideas; it does not claim a new theorem.
    """

    def __init__(self, context=6, k=12, max_candidates=4000, bridge=True,
                 adaptive_scale=True, seasonal_weight=0.15):
        super().__init__(context)
        if not isinstance(k, Integral) or k < 1:
            raise ValueError("k must be a positive integer.")
        if not isinstance(max_candidates, Integral) or max_candidates < 1:
            raise ValueError("max_candidates must be a positive integer.")
        if not np.isfinite(seasonal_weight) or seasonal_weight < 0:
            raise ValueError("seasonal_weight must be finite and nonnegative.")
        self.k = int(k)
        self.max_candidates = int(max_candidates)
        self.bridge = bool(bridge)
        self.adaptive_scale = bool(adaptive_scale)
        self.seasonal_weight = float(seasonal_weight)

    def fit(self, values, timestamps=None):
        super().fit(values, timestamps)
        self._windows = {}
        return self

    def _candidates(self, length):
        if length in self._windows:
            return self._windows[length]
        starts = _complete_starts(self.reference_, length, self.context)
        if len(starts) == 0:
            raise ValueError("Reference has no complete historical window for this gap length.")
        if len(starts) > self.max_candidates:
            selection = np.linspace(0, len(starts) - 1, self.max_candidates, dtype=int)
            starts = starts[selection]
        left = self.reference_[starts[:, None] + np.arange(-self.context, 0)]
        right = self.reference_[starts[:, None] + length + np.arange(self.context)]
        contexts = np.concatenate((left, right), axis=1)
        targets = self.reference_[starts[:, None] + np.arange(length)]
        calendar = _calendar(self.timestamps_, starts)
        result = starts, contexts, targets, calendar
        self._windows[length] = result
        return result

    def predict(self, values, start, end, timestamps=None):
        _, context, times = self._query(values, start, end, timestamps)
        length = end - start
        starts, contexts, targets, calendar = self._candidates(length)
        squared = np.mean(((contexts - context) / self.global_scale_) ** 2, axis=1)
        if self.timestamps_ is not None and times is not None and self.seasonal_weight:
            query_calendar = _calendar(times, np.asarray([start]))[0]
            calendar_diff = (calendar - query_calendar) ** 2
            squared += self.seasonal_weight * (
                calendar_diff[:, :2].sum(axis=1) + 0.25 * calendar_diff[:, 2:].sum(axis=1)
            )
        distances = np.sqrt(squared)
        # Stable ranking gives deterministic reference indices when distances tie.
        chosen = np.argsort(distances, kind="stable")[:self.k]
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
                          float(nearest[0]), "analog")


class LinearBridge(_ReferenceMethod):
    """Straight endpoint interpolation, with a Brownian-bridge-shaped scale."""

    def predict(self, values, start, end, timestamps=None):
        _, context, _ = self._query(values, start, end, timestamps)
        length = end - start
        fraction = np.arange(1, length + 1, dtype=float) / (length + 1)
        mean = context[self.context - 1] * (1 - fraction) + context[self.context] * fraction
        scale = self.noise_floor_ * np.sqrt((length + 1) * fraction * (1 - fraction))
        return Prediction(mean, np.maximum(scale, 1e-8), [], 0.0, "linear")


class ExtraTreesBridge(_ReferenceMethod):
    """Supervised ExtraTrees baseline predicting residuals to interpolation.

    Training examples mask complete windows exclusively in the reference split.
    Features are the two observed contexts, calendar encodings, gap length,
    relative position and interpolated value. No interior value is a feature.
    Tree disagreement provides a relative scale, calibrated by the same external
    procedure used for the other estimators.
    """

    def __init__(self, context=6, seed=0, n_estimators=64, training_gaps=600,
                 lengths=(6, 12, 24)):
        super().__init__(context)
        if not isinstance(n_estimators, Integral) or n_estimators < 1:
            raise ValueError("n_estimators must be a positive integer.")
        if not isinstance(training_gaps, Integral) or training_gaps < 1:
            raise ValueError("training_gaps must be a positive integer.")
        self.lengths = tuple(sorted(set(lengths)))
        if not self.lengths or any(not isinstance(n, Integral) or n < 1 for n in self.lengths):
            raise ValueError("lengths must contain positive integers.")
        self.seed = int(seed)
        self.n_estimators = int(n_estimators)
        self.training_gaps = int(training_gaps)

    def _features(self, context, start, end, times):
        length = end - start
        fraction = np.arange(1, length + 1, dtype=float) / (length + 1)
        chord = context[self.context - 1] * (1 - fraction) + context[self.context] * fraction
        repeated = np.broadcast_to(context, (length, len(context)))
        calendar = _calendar(times, np.arange(start, end))
        features = np.column_stack((repeated, np.full(length, length), fraction,
                                    fraction * (1 - fraction), chord, calendar))
        return features, chord

    def fit(self, values, timestamps=None):
        from sklearn.ensemble import ExtraTreesRegressor

        # Keep the working model intact until reference preparation and tree
        # training both succeed, including failures after estimator creation.
        reference_state = _ReferenceMethod(self.context).fit(values, timestamps)
        rng = np.random.default_rng(self.seed)
        x_parts, y_parts = [], []
        training_examples = 0
        per_length, remainder = divmod(self.training_gaps, len(self.lengths))
        for length_index, length in enumerate(self.lengths):
            each = per_length + int(length_index < remainder)
            if each == 0:
                continue
            starts = _complete_starts(reference_state.reference_, length, self.context)
            if not len(starts):
                continue
            selected = rng.choice(starts, size=min(each, len(starts)), replace=False)
            for start in selected:
                end = int(start + length)
                context = np.concatenate((reference_state.reference_[start - self.context:start],
                                          reference_state.reference_[end:end + self.context]))
                features, chord = self._features(context, start, end, reference_state.timestamps_)
                x_parts.append(features)
                y_parts.append(reference_state.reference_[start:end] - chord)
                training_examples += 1
        if not x_parts:
            raise ValueError("Reference has no complete training windows for requested lengths.")
        model = ExtraTreesRegressor(
            n_estimators=self.n_estimators, min_samples_leaf=3,
            max_features=1.0, random_state=self.seed, n_jobs=1,
        )
        model.fit(np.concatenate(x_parts), np.concatenate(y_parts))
        self.__dict__ = {
            **self.__dict__, **reference_state.__dict__,
            "training_examples_": training_examples, "model_": model,
        }
        return self

    def predict(self, values, start, end, timestamps=None):
        _, context, times = self._query(values, start, end, timestamps)
        if not hasattr(self, "model_"):
            raise ValueError("Call fit before predict.")
        features, chord = self._features(context, start, end, times)
        trees = np.asarray([tree.predict(features) for tree in self.model_.estimators_])
        mean = chord + trees.mean(axis=0)
        scale = np.sqrt(trees.var(axis=0) + self.noise_floor_ ** 2)
        return Prediction(mean, scale, [], 0.0, "extra_trees")
