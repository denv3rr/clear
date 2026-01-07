import unittest
import numpy as np
from modules.client_mgr.regime import RegimeModels

class TestRegimeModels(unittest.TestCase):
    def test_discretize(self):
        returns = [-0.03, -0.01, 0.0, 0.01, 0.03]
        bins = [-float('inf'), -0.02, 0.0, 0.02, float('inf')]
        states = RegimeModels._discretize(returns, bins)
        self.assertEqual(states, [0, 1, 2, 2, 3])

    def test_transition_matrix(self):
        states = [0, 1, 2, 2, 3, 3, 3, 2, 1, 0]
        n = 4
        k = 0.75
        
        # Manually calculate expected smoothed probabilities
        counts = np.zeros((n, n))
        for i in range(len(states) - 1):
            counts[states[i], states[i+1]] += 1
        
        smoothed_counts = counts + k
        row_sums = smoothed_counts.sum(axis=1, keepdims=True)
        expected_P = smoothed_counts / row_sums

        P = RegimeModels._transition_matrix(states, n, k=k)
        
        self.assertEqual(len(P), n)
        self.assertEqual(len(P[0]), n)
        for i in range(n):
            for j in range(n):
                self.assertAlmostEqual(P[i][j], expected_P[i][j], places=6)

    def test_make_bins_quantiles(self):
        returns = np.random.normal(0, 1, 1000).tolist()
        bins = RegimeModels._make_bins_quantiles(returns)
        self.assertEqual(len(bins), 6)
        self.assertEqual(bins[0], -float('inf'))
        self.assertEqual(bins[-1], float('inf'))

    def test_stationary_distribution(self):
        P = [[0.1, 0.9], [0.5, 0.5]]
        pi = RegimeModels._stationary_distribution(P)
        self.assertAlmostEqual(pi[0], 5.0/14.0, places=6)
        self.assertAlmostEqual(pi[1], 9.0/14.0, places=6)

    def test_compute_markov_snapshot(self):
        returns = np.random.normal(0, 1, 100).tolist()
        snapshot = RegimeModels.compute_markov_snapshot(returns)
        self.assertIn("model", snapshot)
        self.assertEqual(snapshot["model"], "Markov")
        self.assertIn("current_regime", snapshot)
        self.assertIn("state_probs", snapshot)
        self.assertIn("transition_matrix", snapshot)
        self.assertIn("metrics", snapshot)
        self.assertIn("stationary", snapshot)
        self.assertIn("evolution", snapshot)


if __name__ == "__main__":
    unittest.main()
