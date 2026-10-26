import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from lab import phase13 as P


def _toy_games(n_weeks=10, seed=0):
    rng = np.random.default_rng(seed)
    teams = ["A", "B", "C", "D"]
    strength = {"A": 6, "B": 2, "C": -2, "D": -6}
    rows = []
    for s in (2015, 2016):
        for w in range(n_weeks):
            h, a = rng.choice(teams, 2, replace=False)
            m = strength[h] - strength[a] + 2 + rng.normal(0, 12)
            m = m if round(m) != 0 else 1
            rows.append({"season": s, "week": w + 1, "home_team": h, "away_team": a, "margin": round(m)})
    return pd.DataFrame(rows)


class TestPhase13(unittest.TestCase):
    def test_murphy_identity(self):
        rng = np.random.default_rng(1)
        p = rng.uniform(0.2, 0.8, 5000)
        y = (rng.random(5000) < p).astype(float)
        m = P.murphy(y, p)
        # Brier = reliability - resolution + uncertainty (exact up to within-bin variance of p)
        self.assertAlmostEqual(m["brier"], m["reliability"] - m["resolution"] + m["uncertainty"], delta=0.01)

    def test_kalman_predictions_are_made_before_each_update(self):
        g = _toy_games()
        p1, _, _ = P.kalman_run(g, 1.0, 2.0, 144.0, None)
        g2 = g.copy()
        g2.loc[len(g2) - 1, "margin"] = 99             # change the LAST result only
        p2, _, _ = P.kalman_run(g2, 1.0, 2.0, 144.0, None)
        np.testing.assert_allclose(p1, p2)             # no prediction may use its own or a later result

    def test_kalman_learns_strength_order(self):
        g = pd.concat([_toy_games(60, s) for s in range(3)]).sort_values(["season", "week"], kind="stable")
        _, _, ends = P.kalman_run(g, 1.0, 2.0, 144.0, None)
        e = ends[2016]
        self.assertGreater(e["A"], e["D"])

    def test_evaluation_requires_ablation_first(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(P, "OUT", Path(d)):
            with self.assertRaises(FileNotFoundError):
                P.evaluate(pd.DataFrame(), None)

    def test_paired_bootstrap_direction(self):
        rng = np.random.default_rng(2)
        a = rng.normal(0.60, 0.2, 3000)
        r = P._paired(a - 0.02, a)
        self.assertLess(r["mean_diff"], 0)
        self.assertLess(r["p_bootstrap"], 0.01)


if __name__ == "__main__":
    unittest.main()
