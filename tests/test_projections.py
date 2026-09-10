import copy
import importlib.util
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_pipeline import (fit_stat, build_profiles, normalize_name, match_player,
                            build_game_models, normalize_games)


class ProjectionTests(unittest.TestCase):
    def test_moments_and_nonpositive_mass(self):
        fit = fit_stat([-2, 0, 10, 20, 30], "lognormal")
        self.assertEqual(fit["n"], 5)
        self.assertEqual(fit["nonpositive"], [-2, 0])
        self.assertAlmostEqual(fit["positive_weight"], .6)
        self.assertAlmostEqual(math.exp(fit["mu_log"] + fit["sigma_log"]**2/2), 20)

    def test_counts_zeros_missing_and_minimum(self):
        self.assertEqual(fit_stat([0]*5, "poisson")["lambda"], 0)
        self.assertEqual(fit_stat([1, None, float("nan")], "poisson")["n"], 1)
        self.assertEqual(fit_stat([1, 2], "poisson")["status"], "insufficient")
        self.assertEqual(fit_stat([1.5]*5, "poisson")["status"], "invalid_counts")

    def test_name_matching_rejects_collision(self):
        self.assertEqual(normalize_name("Odell Béckham Jr."), "odell beckham")
        players = {"a": {"id": "a", "name_key": "josh allen", "team": "BUF"},
                   "b": {"id": "b", "name_key": "josh allen", "team": "JAX"}}
        self.assertEqual(match_player("Josh Allen", players)["status"], "ambiguous")
        self.assertEqual(match_player("Josh Allen", players, ["BUF"])["player_id"], "a")
        self.assertIsNone(match_player("Unknown Rookie", players)["player_id"])

    def test_fuzzy_threshold(self):
        p = {"a": {"id": "a", "name_key": "patrick mahomes", "team": "KC"}}
        self.assertEqual(match_player("Patrick Mahome", p)["status"], "fuzzy")
        self.assertIsNone(match_player("Pat", p)["player_id"])

    def test_zero_stat_participation_and_trailing_window(self):
        roster = [{"gsis_id":"a", "pfr_id":"p", "full_name":"A Player", "team":"BUF", "position":"WR"}]
        rows = [{"player_id":"a", "season":2025, "week":w, "season_type":"REG", "position":"WR",
                 "team":"BUF", "receiving_yards":w*10, "receptions":w,
                 "rushing_tds":0, "receiving_tds":1, "special_teams_tds":0} for w in [1, 2]]
        snaps = [{"pfr_player_id":"p", "season":2025, "week":3, "game_type":"REG", "offense_snaps":10, "team":"BUF"},
                 {"pfr_player_id":"p", "season":2025, "week":4, "game_type":"REG", "offense_snaps":0, "team":"BUF"}]
        schedule = [{"season":2025, "week":w, "home_team":"BUF", "away_team":"KC", "gameday":f"2025-09-{w:02}"} for w in range(1,5)]
        p = build_profiles(rows,roster,snaps,schedule,window=2,minimum=2)["a"]
        self.assertEqual([g["week"] for g in p["games"]], [2,3])
        self.assertEqual(p["stats"]["rec_yds"]["mean"],10)
        self.assertEqual(p["stats"]["atd"]["lambda"],.5)

    def test_spread_and_timezone_conventions(self):
        row = {"game_type":"REG", "game_id":"x", "season":2025, "home_team":"BUF", "away_team":"KC",
               "gameday":"2025-09-07", "gametime":"13:00", "spread_line":3.5}
        game = normalize_games([row], "nfl")[0]
        self.assertEqual(game["spread"], -3.5)
        self.assertEqual(game["kickoff"], "2025-09-07T17:00:00+00:00")
        self.assertFalse(game["completed"])

    def test_walk_forward_no_future_leakage(self):
        games = [{"id":str(i),"home":"A","away":"B","kickoff":f"2025-{i+1:02}-01T00:00:00Z",
                  "completed":True,"homeScore":20+i,"awayScore":14+i} for i in range(6)]
        target = {"id":"target","home":"A","away":"B","kickoff":"2025-07-01T00:00:00Z","completed":False}
        future = {"id":"future","home":"A","away":"B","kickoff":"2025-08-01T00:00:00Z",
                  "completed":True,"homeScore":1000,"awayScore":0}
        before = build_game_models(games+[target],minimum=2)[0][0]["model"]
        after = build_game_models(games+[target,future],minimum=2)[0][0]["model"]
        self.assertEqual(before,after)
        simultaneous = {**future,"kickoff":target["kickoff"]}
        self.assertEqual(before,build_game_models(games+[simultaneous,target],minimum=2)[0][0]["model"])

    def test_ncaa_bookmaker_integrity(self):
        import polars as pl
        from build_ncaa_lines import pivot_lines
        schedule = pl.DataFrame([{"game_id":1,"home_team":"A","away_team":"B"}])
        rows = pl.DataFrame([
            {"game_id":1,"book":"Bovada","market_type":"money_line","abbr":"A","lines":0.0,"odds":-200},
            {"game_id":1,"book":"DraftKings","market_type":"spread","abbr":"A","lines":-3.5,"odds":-110},
            {"game_id":1,"book":"DraftKings","market_type":"spread","abbr":"B","lines":4.5,"odds":-105},
        ])
        game = pivot_lines(rows,schedule)[0]
        self.assertEqual(game["book"],"DraftKings")
        self.assertNotIn("home_ml",game)
        self.assertNotIn("away_spread_odds",game)


if __name__ == "__main__":
    unittest.main()
