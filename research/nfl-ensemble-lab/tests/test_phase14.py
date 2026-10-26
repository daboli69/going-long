import unittest

import numpy as np
import pandas as pd

from lab import phase14 as P
from lab.sequential import THRESHOLD, e_process


class TestSequential(unittest.TestCase):
    def test_false_positive_rate_under_null(self):
        rng = np.random.default_rng(0)
        crossed = sum(e_process(rng.uniform(-1, 1, 300))["crossed"] for _ in range(400))
        self.assertLessEqual(crossed / 400, 0.05 + 0.02)   # Ville: at most alpha at any stopping time

    def test_detects_real_improvement(self):
        rng = np.random.default_rng(1)
        r = e_process(np.clip(rng.normal(0.15, 0.4, 400), -1, 1))
        self.assertTrue(r["crossed"])
        self.assertGreaterEqual(r["max_e"], THRESHOLD)

    def test_first_bet_is_zero(self):
        self.assertEqual(e_process([1.0])["e_value"], 1.0)


class TestQBModel(unittest.TestCase):
    def test_posterior_shrinks_small_samples_to_prior(self):
        a = pd.DataFrame({"n_eff": [1000.0, 5.0], "ebar": [0.25, 0.60], "cs": [0, 0], "cn": [0, 0]}, index=["vet", "rookie"])
        pl = pd.DataFrame({"log_pick": [np.log(10), np.log(200)], "rookie": [2015, 2026]}, index=["vet", "rookie"])
        hyper = {"b": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "tau2": 0.01, "sigma2": 2.4}
        th = P.posterior(a, ["vet", "rookie"], 2026, pl, hyper)
        self.assertGreater(th["vet"], 0.2)                 # lots of data: near its own mean
        self.assertLess(abs(th["rookie"]), 0.05)           # five dropbacks: near the prior (replacement level)

    def test_asof_excludes_current_and_later_weeks(self):
        q = pd.DataFrame({"game_id": ["a", "b", "c"], "season": [2026, 2026, 2026], "wk": [1, 2, 3], "posteam": "X", "qb": "Q",
                          "n": [30, 30, 30], "epa": [3.0, 30.0, 300.0], "cpoe_sum": 0.0, "cpoe_n": 0})
        a = P.asof_table(q, 2026, 2)
        self.assertAlmostEqual(a.loc["Q", "ebar"], 0.1)     # only week 1 is visible before week 2


if __name__ == "__main__":
    unittest.main()
