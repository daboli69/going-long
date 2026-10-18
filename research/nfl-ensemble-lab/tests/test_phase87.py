import unittest

import numpy as np
import pandas as pd

from lab import ngs87 as N


def _ngs(rows):
    return pd.DataFrame([{"season_type": "REG", **r} for r in rows])


class TestPhase87(unittest.TestCase):
    def test_team_week_is_target_weighted_and_drops_week0_post(self):
        n = _ngs([{"season": 2021, "week": 1, "team_abbr": "KC", "avg_separation": 2.0, "targets": 3},
                  {"season": 2021, "week": 1, "team_abbr": "KC", "avg_separation": 4.0, "targets": 1},
                  {"season": 2021, "week": 0, "team_abbr": "KC", "avg_separation": 9.0, "targets": 50}])
        n = pd.concat([n, pd.DataFrame([{"season": 2021, "season_type": "POST", "week": 19, "team_abbr": "KC",
                                         "avg_separation": 9.0, "targets": 5}])])
        tw = N.team_week_sep(n)
        self.assertEqual(len(tw), 1)
        self.assertAlmostEqual(tw["off_sep"].iloc[0], (2 * 3 + 4 * 1) / 4)

    def test_defense_sep_is_opponent_offense(self):
        g = N.games(pd.DataFrame([{"game_id": "g1", "season": 2021, "week": 1, "game_type": "REG", "home_team": "KC",
                                   "away_team": "DEN", "home_score": 20, "away_score": 10}]))
        tw = pd.DataFrame({"season": 2021, "week": 1, "team": ["KC", "DEN"], "off_sep": [3.0, 2.0]})
        tg = N.team_games(g, tw).set_index("team")
        self.assertEqual((tg.loc["KC", "off_sep"], tg.loc["KC", "def_sep"]), (3.0, 2.0))
        self.assertEqual((tg.loc["DEN", "off_sep"], tg.loc["DEN", "def_sep"]), (2.0, 3.0))

    def test_edges_are_as_of_same_season_with_minimum_prior_games(self):
        rows = [{"season": 2020, "team": "KC", "week": w, "off_sep": 50.0, "def_sep": 0.0} for w in range(1, 6)]
        for w in range(1, 7):
            rows.append({"season": 2021, "team": "KC", "week": w, "off_sep": 9.0 if w == 5 else 3.0, "def_sep": 1.0})
        e = N.team_edges(pd.DataFrame(rows)).set_index(["season", "team", "week"])["E"]
        self.assertTrue(np.isnan(e[(2021, "KC", 3)]))          # only 2 earlier games; 2020 never carries over
        self.assertAlmostEqual(e[(2021, "KC", 4)], 2.0)
        self.assertAlmostEqual(e[(2021, "KC", 5)], 2.0)         # week 5's own extreme value is not used
        self.assertAlmostEqual(e[(2021, "KC", 6)], (3 * 4 + 9) / 5 - 1.0)

    def test_angle_orientation_dog_minus_fav(self):
        g = N.games(pd.DataFrame([
            {"game_id": "a", "season": 2021, "week": 5, "game_type": "REG", "home_team": "KC", "away_team": "DEN",
             "home_score": 10, "away_score": 20, "home_moneyline": -200, "away_moneyline": 170},
            {"game_id": "b", "season": 2021, "week": 5, "game_type": "REG", "home_team": "LV", "away_team": "LAC",
             "home_score": 30, "away_score": 20, "home_moneyline": 150, "away_moneyline": -170}]))
        edges = pd.DataFrame({"season": 2021, "week": 5, "team": ["KC", "DEN", "LV", "LAC"], "E": [1.0, -0.5, 0.2, 0.7]})
        oof = pd.DataFrame({"game_id": ["a", "b"], "p_weighted_average": [0.7, 0.6]})
        f = N.game_frame(g, edges, oof).set_index("game_id")
        # a: home KC favoured by champion and market; dog DEN minus fav KC; favourite lost
        self.assertAlmostEqual(f.loc["a", "angle"], -1.5)
        self.assertAlmostEqual(f.loc["a", "mkt_angle"], -1.5)
        self.assertEqual(f.loc["a", "fav_won"], 0.0)
        # b: champion favours home LV, market favours away LAC -> opposite orientations
        self.assertAlmostEqual(f.loc["b", "angle"], 0.7 - 0.2)
        self.assertAlmostEqual(f.loc["b", "mkt_angle"], 0.2 - 0.7)
        self.assertEqual(f.loc["b", "fav_won"], 1.0)
        self.assertEqual(f.loc["b", "mkt_fav_won"], 0.0)
        self.assertGreater(f.loc["b", "p_close_fav"], 0.5)

    def test_samples_exclude_2023_and_2026(self):
        self.assertNotIn(2023, N.CONFIRMATION + N.DISCOVERY + N.DISCOVERY_CLOSE)
        self.assertNotIn(2026, N.CONFIRMATION)
        self.assertTrue(set(N.DISCOVERY).isdisjoint(N.CONFIRMATION))


if __name__ == "__main__":
    unittest.main()
