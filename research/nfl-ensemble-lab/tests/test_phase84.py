import unittest

import numpy as np
import pandas as pd

from lab import upsets84 as U


class TestPhase84(unittest.TestCase):
    def test_lr_test_detects_predeclared_negative_effect(self):
        rng = np.random.default_rng(1)
        n = 3000
        base = rng.normal(0.6, 0.8, n)
        z = rng.normal(size=n)
        y = (rng.random(n) < 1 / (1 + np.exp(-(base - 0.4 * z)))).astype(float)
        r = U._test(y, base, z, np.repeat(np.arange(4), n // 4))
        self.assertLess(r["coef_per_sd"], 0)
        self.assertLess(r["p_one_sided"], 0.001)
        self.assertEqual(r["seasons_with_predeclared_sign"], 4)
        self.assertGreater(r["upset_prob_plus_1sd"], r["upset_prob_at_65pct_fav"])

    def test_wrong_direction_gives_large_one_sided_p(self):
        rng = np.random.default_rng(2)
        n = 3000
        base = rng.normal(0.6, 0.8, n)
        z = rng.normal(size=n)
        y = (rng.random(n) < 1 / (1 + np.exp(-(base + 0.4 * z)))).astype(float)
        self.assertGreater(U._test(y, base, z, np.zeros(n))["p_one_sided"], 0.99)

    def test_espn_movement_orientation(self):
        # ESPN home spread is negative when home is favoured. Home -3 open -> -1.5 latest = moved 1.5 toward the away underdog.
        fs = pd.DataFrame({"home_team": ["JAX", "KC"], "away_team": ["HOU", "DEN"]}, index=["g1", "g2"])
        arc = pd.DataFrame([
            {"home": "JAX", "away": "HOU", "home_spread_open": "-3", "home_spread_close": "-1.5", "retrieved_at": "2026-10-19T12:00Z"},
            {"home": "JAX", "away": "HOU", "home_spread_open": "-3", "home_spread_close": "+2", "retrieved_at": "2026-10-19T20:00Z"},
            {"home": "KC", "away": "DEN", "home_spread_open": "+2.5", "home_spread_close": "+4", "retrieved_at": "2026-10-19T12:00Z"}])
        champ = pd.DataFrame({"game_id": ["g1", "g2"], "predicted_at": pd.to_datetime(["2026-10-19T13:00Z"] * 2, utc=True),
                              "p": [0.6, 0.45], "home_win": [0.0, 0.0]})
        x = U.prospective_frame(champ, arc, fs).set_index("game_id")
        self.assertAlmostEqual(x.loc["g1", "m"], 1.5)           # the later (post-forecast) quote is never used
        self.assertAlmostEqual(x.loc["g1", "p_champ_fav"], 0.6)
        self.assertEqual(x.loc["g1", "fav_won"], 0.0)
        self.assertAlmostEqual(x.loc["g2", "m"], -1.5)          # away favourite 2.5 -> 4: moved toward the favourite
        self.assertAlmostEqual(x.loc["g2", "p_champ_fav"], 0.55)
        self.assertEqual(x.loc["g2", "fav_won"], 1.0)

    def test_registration_is_frozen_and_results_saved(self):
        r = U.load()
        if not r:
            self.skipTest("phase 8.4 not run")
        self.assertIn("holm", r)
        reg = U.register_prospective()
        self.assertEqual(reg["registered_at"], U.REGISTERED_AT)
        self.assertEqual(reg["m_scale"], r["m_scale_2018_21"])


if __name__ == "__main__":
    unittest.main()
