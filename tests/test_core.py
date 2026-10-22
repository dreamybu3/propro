"""Tests of leakage boundaries and substantive reconstruction invariants."""

import unittest

import numpy as np
import pandas as pd

from gaplens.core import AnalogBridge, ExtraTreesBridge, LinearBridge


class CoreTests(unittest.TestCase):
    def setUp(self):
        t = np.arange(360, dtype=float)
        self.reference = 10 + np.sin(t * 2 * np.pi / 24) + 0.1 * np.sin(t / 7)
        self.times = pd.date_range("2020-01-01", periods=360, freq="h")
        self.query = self.reference[-80:].copy()
        self.query_times = pd.date_range("2021-01-01", periods=80, freq="h")

    def test_hidden_target_values_are_never_read(self):
        models = [AnalogBridge(context=3), LinearBridge(context=3),
                  ExtraTreesBridge(context=3, n_estimators=8, training_gaps=24, lengths=(6,))]
        for model in models:
            model.fit(self.reference, self.times)
            hidden = self.query.copy()
            hidden[25:31] = np.nan
            poison = self.query.copy()
            poison[25:31] = 100000
            a = model.predict(hidden, 25, 31, self.query_times)
            b = model.predict(poison, 25, 31, self.query_times)
            np.testing.assert_array_equal(a.mean, b.mean)
            np.testing.assert_array_equal(a.scale, b.scale)
            self.assertEqual(a.neighbors, b.neighbors)

    def test_fit_and_predict_preserve_input(self):
        ref_before = self.reference.copy()
        query_before = self.query.copy()
        model = AnalogBridge(context=3).fit(self.reference, self.times)
        model.predict(self.query, 25, 31, self.query_times)
        np.testing.assert_array_equal(ref_before, self.reference)
        np.testing.assert_array_equal(query_before, self.query)
        self.reference[:] = 0
        np.testing.assert_array_equal(model.reference_, ref_before)

    def test_bridge_exact_for_linear_references_despite_offset(self):
        reference = 10 + 2 * np.arange(200, dtype=float)
        query = 1000 + 3 * np.arange(40, dtype=float)
        query[12:20] = np.nan
        model = AnalogBridge(context=3, k=8, seasonal_weight=0).fit(reference)
        prediction = model.predict(query, 12, 20)
        np.testing.assert_allclose(prediction.mean, 1000 + 3 * np.arange(12, 20), atol=1e-10)
        without = AnalogBridge(context=3, k=8, bridge=False).fit(reference).predict(query, 12, 20)
        self.assertGreater(np.abs(prediction.mean - without.mean).mean(), 100)

    def test_reference_missing_values_never_enter_candidates(self):
        reference = self.reference.copy()
        reference[90:130] = np.nan
        model = AnalogBridge(context=3).fit(reference)
        result = model.predict(self.query, 25, 31)
        for start in result.neighbors:
            self.assertTrue(np.isfinite(reference[start - 3:start + 6 + 3]).all())

    def test_positive_scales_for_constant_reference(self):
        for model in [AnalogBridge(context=3), LinearBridge(context=3),
                      ExtraTreesBridge(context=3, n_estimators=4, training_gaps=12, lengths=(6,))]:
            model.fit(np.full(100, 5.0))
            result = model.predict(np.full(40, 5.0), 12, 18)
            np.testing.assert_allclose(result.mean, 5)
            self.assertTrue(np.isfinite(result.scale).all())
            self.assertTrue((result.scale > 0).all())

    def test_context_missing_and_boundary_gaps_are_rejected(self):
        model = AnalogBridge(context=3).fit(self.reference)
        for start, end in [(0, 6), (75, 79), (20, 20), (30, 20)]:
            with self.assertRaises(ValueError):
                model.predict(self.query, start, end)
        missing = self.query.copy()
        missing[24] = np.nan
        with self.assertRaisesRegex(ValueError, "context contains"):
            model.predict(missing, 25, 31)

    def test_empty_candidate_pool_is_rejected(self):
        reference = self.reference[:40].copy()
        reference[::7] = np.nan
        model = AnalogBridge(context=3).fit(reference)
        with self.assertRaisesRegex(ValueError, "no complete"):
            model.predict(self.query, 25, 31)

    def test_deterministic_neighbors_and_trees(self):
        a = AnalogBridge(context=3, max_candidates=30).fit(self.reference)
        b = AnalogBridge(context=3, max_candidates=30).fit(self.reference)
        pa, pb = a.predict(self.query, 25, 31), b.predict(self.query, 25, 31)
        np.testing.assert_array_equal(pa.mean, pb.mean)
        self.assertEqual(pa.neighbors, pb.neighbors)
        trees = [ExtraTreesBridge(context=3, seed=7, n_estimators=4,
                                 training_gaps=12, lengths=(6,)).fit(self.reference) for _ in range(2)]
        np.testing.assert_array_equal(trees[0].predict(self.query, 25, 31).mean,
                                      trees[1].predict(self.query, 25, 31).mean)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            AnalogBridge(context=0)
        with self.assertRaises(ValueError):
            AnalogBridge(k=0)
        with self.assertRaises(ValueError):
            AnalogBridge().fit(np.array([1, 2, np.inf] * 10))
        with self.assertRaises(ValueError):
            AnalogBridge().fit(np.ones((10, 2)))
        with self.assertRaises(ValueError):
            LinearBridge().predict(self.query, 25, 31)
        with self.assertRaises(ValueError):
            AnalogBridge().fit(self.reference, self.times[:-1])

    def test_training_gap_budget_is_respected(self):
        for budget in (1, 5):
            model = ExtraTreesBridge(context=3, n_estimators=4, training_gaps=budget,
                                     lengths=(3, 6, 12)).fit(self.reference)
            self.assertEqual(model.training_examples_, budget)


if __name__ == "__main__":
    unittest.main()
