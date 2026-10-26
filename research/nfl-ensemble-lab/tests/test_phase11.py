import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from lab import market_blend11 as MB

ROOT = Path(__file__).resolve().parents[1]
UTC = "UTC"


def _arc(rows):
    base = {"provider": "DraftKings", "home": "KC", "away": "DEN", "kickoff": "2026-11-01T18:00Z"}
    return pd.DataFrame([base | r for r in rows])


def _scored(rows):
    base = {"game_id": "g1", "season": 2026, "week": 9, "kickoff_utc": pd.Timestamp("2026-11-01T18:00Z"), "home_win": 1.0, "p_home": 0.6}
    return pd.DataFrame([base | r for r in rows])


TEAMS = pd.DataFrame([{"game_id": "g1", "home_team": "KC", "away_team": "DEN"}])


class TestPhase11(unittest.TestCase):
    def test_weights_match_preregistration(self):
        doc = (ROOT / MB.DOC).read_text(encoding="utf-8")
        for v in MB.WEIGHTS.values():
            self.assertIn(repr(v).replace("-", "−"), doc)

    def test_blend_formula(self):
        pc, po = 0.6, 0.7
        z = MB.WEIGHTS["intercept"] + MB.WEIGHTS["champion"] * np.log(pc / (1 - pc)) + MB.WEIGHTS["open"] * np.log(po / (1 - po))
        self.assertAlmostEqual(float(MB.blend(pc, po)), 1 / (1 + np.exp(-z)))

    def test_moneyline_novig(self):
        self.assertAlmostEqual(MB.ml_novig("-110", "-110"), 0.5)
        self.assertAlmostEqual(MB.ml_novig("EVEN", "+100"), 0.5)
        p = MB.ml_novig("-200", "+170")
        self.assertAlmostEqual(p, (2 / 3) / (2 / 3 + 100 / 270))
        self.assertTrue(np.isnan(MB.ml_novig(None, "+150")))
        self.assertTrue(np.isnan(MB.ml_novig("OFF", "+150")))

    def test_opener_is_earliest_before_stage_and_close_is_latest_before_kickoff(self):
        a = MB._prep_archive(_arc([
            {"retrieved_at": "2026-10-30T12:00Z", "home_ml_open": "-150", "away_ml_open": "+130", "home_ml_close": "-160", "away_ml_close": "+140"},
            {"retrieved_at": "2026-10-31T12:00Z", "home_ml_open": "-200", "away_ml_open": "+170", "home_ml_close": "-220", "away_ml_close": "+180"},
            {"retrieved_at": "2026-11-01T19:00Z", "home_ml_open": "-300", "away_ml_open": "+250", "home_ml_close": "-900", "away_ml_close": "+600"}]))
        k = pd.Timestamp("2026-11-01T18:00Z")
        p, src = MB.opener_before(a, "KC", "DEN", k, pd.Timestamp("2026-10-31T00:00Z"))
        self.assertAlmostEqual(p, MB.ml_novig("-150", "+130"))
        self.assertTrue(src.startswith("2026-10-30"))
        p, _ = MB.opener_before(a, "KC", "DEN", k, pd.Timestamp("2026-10-30T00:00Z"))
        self.assertTrue(np.isnan(p))
        self.assertAlmostEqual(MB.closer_before(a, "KC", "DEN", k), MB.ml_novig("-220", "+180"))
        # a different meeting of the same teams (kickoff > 24 h away) is not matched
        self.assertTrue(np.isnan(MB.opener_before(a, "KC", "DEN", k + pd.Timedelta(days=30), k + pd.Timedelta(days=29))[0]))

    def test_other_providers_ignored(self):
        a = MB._prep_archive(_arc([{"provider": "Other", "retrieved_at": "2026-10-30T12:00Z", "home_ml_open": "-150", "away_ml_open": "+130"}]))
        self.assertEqual(len(a), 0)

    def test_score_table_fallback_and_primary_flag(self):
        arc = _arc([{"retrieved_at": "2026-10-31T12:00Z", "home_ml_open": "-200", "away_ml_open": "+170", "home_ml_close": "-220",
                     "away_ml_close": "+180"}])
        t = _scored([{"window": "early", "predicted_at": pd.Timestamp("2026-10-27T12:00Z")},
                     {"window": "final", "predicted_at": pd.Timestamp("2026-11-01T16:00Z")}])
        s = MB.score_table(t, arc, TEAMS).set_index("stage")
        self.assertTrue(s.loc["early", "fallback_no_opener"])
        self.assertEqual(s.loc["early", "p_challenger"], 0.6)
        self.assertFalse(s.loc["final", "fallback_no_opener"])
        self.assertAlmostEqual(s.loc["final", "p_challenger"], float(MB.blend(0.6, MB.ml_novig("-200", "+170"))))
        self.assertTrue(s.loc["final", "counts_for_primary"])
        self.assertFalse(s.loc["early", "counts_for_primary"])

    def test_pre_registration_games_never_count(self):
        t = _scored([{"window": "final", "predicted_at": MB.REGISTERED_AT - pd.Timedelta(minutes=1)}])
        s = MB.score_table(t, _arc([]).iloc[:0], TEAMS)
        self.assertFalse(s["counts_for_primary"].any())
        r = MB.evaluate(s)
        self.assertEqual(r["primary"]["games"], 0)
        self.assertIn("accumulating", r["primary"]["status"])
        self.assertEqual(r["descriptive_pre_registration_final"]["games"], 1)

    def test_primary_needs_128_games_and_ci_below_zero(self):
        rng = np.random.default_rng(1)
        n = 140
        y = rng.integers(0, 2, n).astype(float)
        s = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)], "stage": "final", "home_win": y, "p_champion": 0.5,
                          "p_challenger": np.where(y == 1, 0.8, 0.2), "p_open": 0.5, "p_close": np.nan,
                          "fallback_no_opener": False, "counts_for_primary": True})
        self.assertTrue(MB.evaluate(s)["primary"]["status"].startswith("passes"))
        self.assertIn("accumulating", MB.evaluate(s.iloc[:100])["primary"]["status"])
        worse = s.assign(p_challenger=np.where(y == 1, 0.2, 0.8))
        self.assertEqual(MB.evaluate(worse)["primary"]["status"], "does not pass")

    def test_fit_weights_recovers_synthetic(self):
        rng = np.random.default_rng(0)
        lc, lo = rng.normal(0, 1, 20000), rng.normal(0, 1, 20000)
        y = (rng.random(20000) < 1 / (1 + np.exp(-(-0.1 + 0.3 * lc + 0.8 * lo)))).astype(int)
        w = MB.fit_weights(pd.DataFrame({"p_weighted_average": 1 / (1 + np.exp(-lc)), "p_open": 1 / (1 + np.exp(-lo)), "home_win": y}))
        self.assertAlmostEqual(w["champion"], 0.3, delta=0.06)
        self.assertAlmostEqual(w["open"], 0.8, delta=0.06)

    def test_empty_inputs(self):
        self.assertTrue(MB.score_table(pd.DataFrame(), pd.DataFrame(), TEAMS).empty)
        self.assertEqual(MB.evaluate(pd.DataFrame())["primary"]["games"], 0)


if __name__ == "__main__":
    unittest.main()
