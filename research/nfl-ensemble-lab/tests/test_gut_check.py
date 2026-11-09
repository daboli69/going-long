import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gut_check as gc  # noqa: E402


class GutCheckTests(unittest.TestCase):
    def test_shrink_pulls_small_samples_to_league(self):
        g = np.array([[10.0, 10.0]])  # 10 dropbacks averaging 1.0
        self.assertAlmostEqual(gc.shrunk(g, 0.0), 10 / 260)

    def test_identical_quarterbacks_are_a_coin_flip(self):
        rng = np.random.default_rng(1)
        g = np.array([[5.0, 30.0], [-2.0, 28.0], [1.0, 35.0], [3.0, 31.0]])
        r = gc.compare(g, g.copy(), 0.0, rng)
        self.assertEqual(r["diff"], 0.0)
        self.assertTrue(0.3 < r["p_a_better"] < 0.7)


if __name__ == "__main__":
    unittest.main()
