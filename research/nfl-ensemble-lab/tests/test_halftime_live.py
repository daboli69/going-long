import unittest

import pandas as pd

from lab import halftime as H
from lab import halftime_live as L


def play(pid, period, clock, text):
    return {"id": pid, "period": {"number": period}, "clock": {"displayValue": clock}, "text": text}


def snapshot():
    dal = [
        play("1", 1, "14:00", "(Shotgun) D.Prescott pass short right to C.Lamb to DAL 40 for 12 yards (B.Baker)."),
        play("2", 1, "13:20", "D.Prescott pass incomplete deep left to C.Lamb."),
        play("3", 1, "12:50", "D.Prescott pass short middle intended for J.Ferguson INTERCEPTED by B.Baker at ARI 30."),
        play("4", 2, "10:00", "T.Guyton reported in as eligible.  J.Williams left guard to DAL 33 for 2 yards (Z.Collins)."),
        play("5", 2, "9:30", "D.Prescott sacked at DAL 25 for -8 yards (J.Sweat)."),
        play("6", 2, "9:00", "PENALTY on DAL-T.Smith, False Start, 5 yards, enforced at DAL 25 - No Play."),
        play("7", 2, "0:05", "D.Prescott kneels to DAL 24 for -1 yards."),
        play("8", 3, "15:00", "J.Williams right end to DAL 40 for 15 yards (B.Baker)."),
        play("5", 2, "9:30", "D.Prescott sacked at DAL 25 for -8 yards (J.Sweat)."),
    ]
    ari = [
        play("9", 1, "11:00", "(Shotgun) K.Murray scrambles right end to ARI 45 for 9 yards (D.Overshown)."),
        play("10", 2, "5:00", "K.Murray to ARI 40 for -5 yards. FUMBLES, and recovers at ARI 40."),
        play("11", 2, "4:00", "J.Conner left end to ARI 44 for 4 yards.The Replay Official reviewed the runner was down ruling, "
                               "and the play was REVERSED.J.Conner left end to ARI 47 for 7 yards (M.Bell)."),
    ]

    def team(code, side, quarters):
        return {"homeAway": side, "team": {"abbreviation": code}, "score": "99",
                "linescores": [{"displayValue": str(q)} for q in quarters]}

    return {
        "header": {"id": "999", "week": 8, "season": {"year": 2026},
                   "competitions": [{"status": {"type": {"name": "STATUS_HALFTIME"}, "period": 2},
                                     "competitors": [team("DAL", "home", [7, 10]), team("ARI", "away", [3, 0])]}]},
        "pickcenter": [{"spread": -7.0, "overUnder": 48.5}],
        "drives": {"previous": [{"team": {"abbreviation": "ARI"}, "plays": ari}],
                   "current": {"team": {"abbreviation": "DAL"}, "plays": dal}},
    }


SCHEDULE = pd.DataFrame(columns=["espn", "game_id", "season", "week", "spread_line", "total_line"])


def hist():
    pre = [c for c in H.PLAYER_FEATURES if c.startswith("pre_")]
    rows = [{"player_id": "id-lamb", "team": "DAL", "name": "C.Lamb", "last_season": 2026},
            {"player_id": "id-conner", "team": "SF", "name": "J.Conner", "last_season": 2026}]
    return pd.DataFrame([{**r, **{c: 1.0 for c in pre}} for r in rows])


class Plays(unittest.TestCase):
    def setUp(self):
        self.p = L.first_half_plays(snapshot())

    def test_only_first_half_plays_are_kept_once(self):
        self.assertEqual(len(self.p), 9)   # second half, No Play and the repeated id are dropped
        self.assertTrue((self.p.qtr <= 2).all())

    def test_pass_outcomes(self):
        lamb = self.p[self.p.player == "C.Lamb"]
        self.assertEqual(lamb.complete.tolist(), [1.0, 0.0])
        self.assertEqual(lamb.yards.tolist(), [12.0, 0.0])
        picked = self.p[self.p.player == "J.Ferguson"].iloc[0]
        self.assertEqual((picked.kind, picked.complete, picked.yards), ("pass", 0.0, 0.0))

    def test_runs(self):
        runs = self.p[self.p.kind == "rush"].set_index("player").yards
        self.assertEqual(runs["J.Williams"], 2.0)    # the eligible-lineman notice is not the runner
        self.assertEqual(runs["K.Murray"].tolist(), [9.0, -5.0])   # a scramble, and a run with no direction
        self.assertEqual(runs["J.Conner"], 7.0)      # the reversed ruling stands

    def test_sack_and_kneel_have_no_player(self):
        other = self.p[self.p.kind.isin(["dropback", "kneel"])]
        self.assertEqual(other.kind.tolist(), ["dropback", "kneel"])
        self.assertTrue(other.player.isna().all())
        self.assertEqual(other.yards.tolist(), [-8.0, -1.0])

    def test_clock_counts_down_from_the_start_of_the_game(self):
        self.assertEqual(self.p.left.max(), 2 * 900 + 14 * 60 + 900)
        self.assertEqual(self.p.left.min(), 1800 + 5)


class Tables(unittest.TestCase):
    def test_game_info(self):
        info = L.game_info(snapshot(), SCHEDULE)
        self.assertEqual((info["home_team"], info["away_team"]), ("DAL", "ARI"))
        self.assertEqual((info["h1_home"], info["h1_away"]), (17.0, 3.0))
        self.assertEqual(info["spread_line"], 7.0)   # home favourite is positive, as in nflverse
        self.assertEqual(info["total_line"], 48.5)
        self.assertEqual(info["game_id"], "2026_08_ARI_DAL")
        self.assertEqual(info["home_receives_h2"], 1.0)   # ARI had the opening drive

    def test_tables(self):
        game, players = L.tables(snapshot(), SCHEDULE, hist())
        g = game.iloc[0]
        self.assertEqual((g.h1_total, g.h1_margin), (20.0, 14.0))
        self.assertEqual((g.home_h1_pass, g.home_h1_rush, g.home_h1_yards), (4.0, 2.0, 5.0))
        self.assertEqual((g.away_h1_pass, g.away_h1_rush), (0.0, 3.0))
        p = players.set_index("name")
        self.assertEqual((p.loc["C.Lamb", "h1_tgt"], p.loc["C.Lamb", "h1_rec"], p.loc["C.Lamb", "h1_rec_yds"]), (2, 1.0, 12.0))
        self.assertAlmostEqual(p.loc["C.Lamb", "tgt_share"], 2 / 3)
        self.assertEqual(p.loc["C.Lamb", "player_id"], "id-lamb")
        self.assertEqual(p.loc["J.Conner", "player_id"], "id-conner")   # changed teams, name is unique
        self.assertEqual(p.loc["K.Murray", "pre_games"], 0)
        self.assertTrue(pd.isna(p.loc["K.Murray", "player_id"]))
        self.assertEqual(p.loc["K.Murray", "team_spread"], -7.0)
        self.assertEqual(p.loc["J.Williams", "receives_h2"], 1.0)
        self.assertFalse(set(H.PLAYER_FEATURES) - set(players.columns))
        self.assertFalse(set(H.GAME_FEATURES) - set(game.columns))


if __name__ == "__main__":
    unittest.main()
