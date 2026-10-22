"""Independent dense/SVD oracles for the new recursive and low-rank models."""

import numpy as np
import pytest

from gaplens.models_v2 import ConditionalTrajectoryPCA, LocalLinearKalman


def signals():
    rng = np.random.default_rng(81)
    return 4 + np.cumsum(rng.normal(size=160)), 4 + np.cumsum(rng.normal(size=50))


@pytest.mark.parametrize("length", [3, 7])
def test_rts_smoother_matches_dense_joint_gaussian_conditioning(length):
    reference, query = signals()
    model = LocalLinearKalman(context=3, process_ratio=0.3).fit(reference)
    start, end, context = 20, 20 + length, 3
    count = length + 2 * context
    transition = np.array([[1.0, 1.0], [0.0, 1.0]])
    variance = model.observation_variance_
    process = variance * model.process_ratio * np.array([[0.25, 0.5], [0.5, 1.0]])
    process += np.eye(2) * variance * 1e-9
    # Build the unconditional joint distribution of every state. Condition the
    # complete observation covariance in one dense solve, with no filtering or
    # smoothing recursions. This checks both recursive means and uncertainty.
    means = np.empty((count, 2))
    covariance = np.zeros((count, count, 2, 2))
    means[0] = [0, model.slope_]
    covariance[0, 0] = np.eye(2) * 1e6
    for t in range(1, count):
        means[t] = transition @ means[t - 1]
        covariance[t, t] = transition @ covariance[t - 1, t - 1] @ transition.T + process
        for s in range(t):
            covariance[t, s] = transition @ covariance[t - 1, s]
            covariance[s, t] = covariance[t, s].T
    joint = covariance[:, :, 0, 0] + np.eye(count) * variance
    observed = np.r_[np.arange(context), np.arange(count - context, count)]
    target = np.arange(context, count - context)
    measurements = np.r_[query[start-context:start], query[end:end+context]]
    normalized = (measurements - model.center_) / model.global_scale_
    coefficients = np.linalg.solve(joint[np.ix_(observed, observed)], joint[np.ix_(observed, target)]).T
    expected_mean = model.center_ + model.global_scale_ * (
        means[target, 0] + coefficients @ (normalized - means[observed, 0])
    )
    expected_scale = model.global_scale_ * np.sqrt(np.diag(
        joint[np.ix_(target, target)] - coefficients @ joint[np.ix_(observed, target)]
    ))
    actual = model.predict(query, start, end)
    # The diffuse prior has variance 1e6; dense conditioning subtracts large
    # nearly equal covariance terms, so bitwise equivalence is inappropriate.
    np.testing.assert_allclose(actual.mean, expected_mean, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(actual.scale, expected_scale, rtol=1e-6, atol=1e-6)


def test_conditional_pca_matches_svd_and_augmented_least_squares():
    reference, query = signals()
    model = ConditionalTrajectoryPCA(context=3, rank=4, ridge=0.1, max_candidates=1000).fit(reference)
    start, end, context = 20, 27, 3
    length = end - start
    windows = np.lib.stride_tricks.sliding_window_view(reference, length + 2 * context)
    normalized = (windows - model.center_) / model.global_scale_
    column_mean = normalized.mean(axis=0)
    centered = normalized - column_mean
    # A direct rectangular SVD avoids the implementation's covariance-eigen
    # decomposition; augmented least squares avoids its normal equations.
    _, _, right_vectors = np.linalg.svd(centered, full_matrices=False)
    basis = right_vectors[:model.rank].T
    observed = np.r_[np.arange(context), np.arange(context + length, 2 * context + length)]
    target = np.arange(context, context + length)
    design = np.vstack([basis[observed], np.sqrt(model.ridge) * np.eye(model.rank)])
    query_context = np.r_[query[start-context:start], query[end:end+context]]
    response = (query_context - model.center_) / model.global_scale_ - column_mean[observed]
    latent = np.linalg.lstsq(design, np.r_[response, np.zeros(model.rank)], rcond=None)[0]
    expected_mean = model.center_ + model.global_scale_ * (column_mean[target] + basis[target] @ latent)
    training_response = np.vstack([centered[:, observed].T, np.zeros((model.rank, len(windows)))])
    training_latent = np.linalg.lstsq(design, training_response, rcond=None)[0]
    residual = centered[:, target] - training_latent.T @ basis[target].T
    expected_scale = np.sqrt(np.mean(residual ** 2, axis=0) * model.global_scale_ ** 2 + model.noise_floor_ ** 2)
    actual = model.predict(query, start, end)
    np.testing.assert_allclose(actual.mean, expected_mean, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(actual.scale, expected_scale, rtol=1e-12, atol=1e-12)
