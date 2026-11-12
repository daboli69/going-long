import unittest
import numpy as np
from lab import halftime2 as V


class Halftime2(unittest.TestCase):
    def test_posterior_share_moves_from_prior_toward_first_half(self):
        self.assertAlmostEqual(V.posterior_share(0.2, 0, 0, 40), 0.2)
        self.assertAlmostEqual(V.posterior_share(0.2, 10, 20, 20), 0.35)
        self.assertGreater(V.posterior_share(0.2, 10, 20, 5), V.posterior_share(0.2, 10, 20, 80))

    def test_prob_over_reads_the_fitted_quantiles(self):
        q = np.array([np.arange(10.0, 100.0, 10.0)])
        self.assertAlmostEqual(V.prob_over(q, 50.0)[0], 0.5, places=6)
        self.assertAlmostEqual(V.prob_over(q, 0.0)[0], 1.0, places=6)
        self.assertEqual(V.prob_over(q, 1000.0)[0], 0.0)
        self.assertGreater(V.prob_over(q, 20.0)[0], V.prob_over(q, 80.0)[0])

    def test_pinball_is_lower_for_better_placed_quantiles(self):
        y = np.array([50.0])
        good = np.array([np.arange(10.0, 100.0, 10.0)])
        self.assertLess(V.pinball(y, good)[0], V.pinball(y, good + 40)[0])
        self.assertEqual(V.pinball(y, np.full((1, 9), 50.0))[0], 0.0)


if __name__ == "__main__":
    unittest.main()
