"""Props simulator v2 fixes and the 2026 prospective archive (docs/PROPS_V2_PREREGISTRATION.md)."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from lab.props import evaluate as E
from lab.props import game as G
from lab.props import sim as S
from lab.props import v2 as V2
from lab.props import weekly as W
from tests.test_props import _toy_tables, _toy_teams


class TestV2Sim(unittest.TestCase):
    def test_v1_unchanged_when_v2_keys_are_neutral(self):
        tm, pl = _toy_teams()
        T = _toy_tables()
        a = S.simulate(T, tm, pl, 300, [0.1, -0.1], np.random.default_rng(4))
        T2 = copy.copy(T)
        T2.update(g_comp=1.0, g_rush=1.0, kappa_recv=30.0, kappa_rush=30.0)
        T2.pop("kappa")
        b = S.simulate(T2, tm, pl, 300, [0.1, -0.1], np.random.default_rng(4))
        np.testing.assert_array_equal(a["points"], b["points"])
        np.testing.assert_array_equal(a["stats"]["rec_yds"], b["stats"]["rec_yds"])

    def test_gain_multiplier_lowers_yardage(self):
        tm, pl = _toy_teams()
        T = _toy_tables()
        T2 = copy.copy(T)
        T2.update(g_comp=0.8, g_rush=0.8)
        a = S.simulate(T, tm, pl, 800, [0, 0], np.random.default_rng(6))["stats"]
        b = S.simulate(T2, tm, pl, 800, [0, 0], np.random.default_rng(6))["stats"]
        self.assertLess(b["rush_yds"][:, 2].mean(), a["rush_yds"][:, 2].mean())

    def test_receiving_share_noise_follows_kappa_recv(self):
        tm, pl = _toy_teams()
        sd = {}
        for k in (5.0, 500.0):
            T = _toy_tables()
            T.pop("kappa")
            T.update(kappa_recv=k, kappa_rush=30.0, sigma_e=0.0)
            sd[k] = S.simulate(T, tm, pl, 1500, [0, 0], np.random.default_rng(8))["stats"]["rec"][:, 0].std()
        self.assertGreater(sd[5.0], sd[500.0])

    def test_calibrate_v2_returns_a_verified_iterate(self):
        tm, pl = _toy_teams()
        T = _toy_tables()
        base = S.simulate(T, tm, pl, 1000, [0, 0], np.random.default_rng(5), record=False)["points"].mean()
        tgt = [base * 1.25, base * 0.8]
        rng = np.random.default_rng(2)
        seed = int(copy.deepcopy(rng).integers(0, 2**31))
        e, pts = S.calibrate_v2(T, tm, pl, tgt, rng, n=1000, iters=6)
        again = S.simulate(T, tm, pl, 1000, e, np.random.default_rng(seed), record=False)["points"].mean(0)
        np.testing.assert_allclose(pts, again)                      # the returned points were simulated at the returned e
        self.assertLess(np.max(np.abs(pts - tgt)), 0.15 * max(tgt))

    def test_mean_correction_is_clipped(self):
        x = np.array([100.0])
        self.assertAlmostEqual(V2.correct(x, "pass_yds", {"pass_yds": 0.5})[0], 85.0)
        self.assertAlmostEqual(V2.correct(x, "pass_yds", {"pass_yds": 1.2})[0], 105.0)


class TestQuantileScoring(unittest.TestCase):
    def test_quantile_crps_matches_sample_crps(self):
        x = np.random.default_rng(0).normal(50, 10, 100_000)
        q = np.quantile(x, G.LEVELS)
        for y in (35.0, 50.0, 71.0):
            self.assertAlmostEqual(float(G.qcrps(q, y)), E.crps_samples(x, y), delta=0.03 * E.crps_samples(x, y) + 0.05)

    def test_coverage(self):
        q = np.tile(G.LEVELS * 100, (2, 1))
        np.testing.assert_array_equal(G.coverage(q, [50.0, 95.0], 10, 90), [1.0, 0.0])


def _ros():
    return pd.DataFrame({"week": [6, 6, 6, 6, 5, 5], "posteam": ["GB", "GB", "DAL", "DAL", "NYG", "NYG"],
                         "pid": ["a", "b", "c", "d", "e", "f"], "status": ["ACT", "ACT", "ACT", "INA", "ACT", "ACT"],
                         "position": ["WR", "WR", "RB", "RB", "TE", "WR"]})


class TestWeekly(unittest.TestCase):
    def test_availability_rules(self):
        inj = pd.DataFrame({"team": ["GB", "DAL", "NYG"], "week": [6, 6, 6], "gsis_id": ["b", "c", "e"], "report_status": ["Out", "Out", "Out"]})
        av, rule = W.availability(_ros(), inj, 6, "DAL")              # inactives published -> ACT, injury report ignored
        self.assertEqual(av["pid"].tolist(), ["c"])
        self.assertTrue(rule.startswith("ACT (game-day"))
        av, rule = W.availability(_ros(), inj, 6, "GB")               # no INA yet -> ACT minus Out
        self.assertEqual(av["pid"].tolist(), ["a"])
        self.assertIn("minus injury-report Out", rule)
        av, rule = W.availability(_ros(), inj, 6, "NYG")              # no week-6 roster -> latest earlier week minus Out
        self.assertEqual(av["pid"].tolist(), ["f"])
        self.assertIn("week 5", rule)

    def test_pick_week_and_kickoff(self):
        g = pd.DataFrame({"season": [2026] * 3, "week": [6, 6, 7], "gameday": ["2026-10-18", "2026-10-19", "2026-10-22"],
                          "gametime": ["13:00", "20:15", "20:15"], "home_score": [20.0, np.nan, np.nan]})
        now = pd.Timestamp("2026-10-19 21:00", tz=W.TZ)
        self.assertEqual(W.pick_week(g, 2026, pd.Timestamp("2026-10-19 12:00", tz=W.TZ)), 6)
        self.assertEqual(W.pick_week(g, 2026, now), 7)                # Monday game has kicked off
        self.assertEqual(W.kickoff("2026-10-18", "20:20").tz_convert("UTC").hour, 0)

    def test_archive_files_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.parquet"
            W._write_once(f, b"one")
            with self.assertRaises(FileExistsError):
                W._write_once(f, b"two")
            self.assertEqual(f.read_bytes(), b"one")

    def test_archive_skips_started_and_lineless_games(self):
        g = pd.DataFrame({"game_id": ["g1", "g2"], "season": [2026, 2026], "week": [6, 6], "gameday": ["2026-10-18", "2026-10-19"],
                          "gametime": ["13:00", "20:15"], "home_team": ["A", "B"], "away_team": ["C", "D"], "home_score": [np.nan, np.nan],
                          "spread_line": [1.0, np.nan], "total_line": [40.0, np.nan], "home_qb_id": [None, None], "away_qb_id": [None, None]})
        with tempfile.TemporaryDirectory() as d, mock.patch.object(W, "load_games", return_value=g), \
                mock.patch.object(W.M, "fit", side_effect=AssertionError("nothing to simulate")):
            r = W.archive(2026, 6, now=pd.Timestamp("2026-10-18 14:00", tz=W.TZ), out=Path(d), log=lambda m: None)
        self.assertEqual(r["archived"], [])
        self.assertEqual(dict(r["skipped"]), {"g1": "kicked off", "g2": "no spread/total yet"})

    def test_projection_table(self):
        q = {c: v for c, v in zip(G.QCOLS, np.linspace(10, 108, 99))}             # q50 = 59, q10 = 19, q90 = 99
        arch = pd.DataFrame([{"game_id": "g1", "team": "A", "pid": "wr", "name": "W R", "stat": "rec_yds", "version": v, "mean": 60.0, **q}
                             for v in ("v1", "v2", "base")])
        t = W.projection_table(arch, pd.DataFrame({"game_id": ["g1"], "pid": ["wr"], "stat": ["rec_yds"], "actual": [71.0]}))
        r = t.iloc[0]
        self.assertEqual((r["Player"], r["Stat"], r["v2 median"], r["Actual"]), ("W R", "Receiving yards", 59.0, 71.0))
        self.assertEqual(r["v1 10-90%"], "19.0 - 99.0")

    def test_actuals_and_score_once(self):
        p = pd.DataFrame({"game_id": ["g1"] * 4, "qtr": [1, 2, 4, 5], "play_type": ["pass", "run", "pass", "pass"],
                          "two_point_attempt": 0, "qb_kneel": 0, "qb_spike": 0, "sack": 0, "complete_pass": [1, 0, 1, 1],
                          "receiver_player_id": ["wr", None, "wr", "wr"], "receiving_yards": [12.0, np.nan, 8.0, 30.0],
                          "rusher_player_id": [None, "rb", None, None], "rushing_yards": [np.nan, 5.0, np.nan, np.nan],
                          "passer_player_id": ["qb", None, "qb", "qb"], "passing_yards": [12.0, np.nan, 8.0, 30.0]})
        a = W.actuals(p).set_index("pid")
        self.assertEqual(a.loc["wr", "rec_yds"], 20.0)                 # overtime excluded (regulation only, as in v1)
        self.assertEqual(a.loc["wr", "rec"], 2.0)
        self.assertEqual(a.loc["qb", "pass_yds"], 20.0)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "2026_w06").mkdir()
            q = {c: v for c, v in zip(G.QCOLS, np.linspace(0, 40, 99))}
            arch = pd.DataFrame([{"game_id": "g1", "team": "A", "pid": pid, "name": pid, "stat": "rec_yds", "version": v, "mean": 20.0, **q}
                                 for pid in ("wr", "te", "gone") for v in ("v1", "v2")])
            arch.to_parquet(d / "2026_w06" / "g1.parquet", index=False)
            games = pd.DataFrame({"game_id": ["g1"], "week": [6], "home_score": [21.0]})
            ros = pd.DataFrame({"week": [6, 6], "gsis_id": ["wr", "te"], "status": ["ACT", "ACT"]})
            ros.to_parquet(d / "roster_weekly_2026.parquet")
            with mock.patch.object(W, "load_games", return_value=games), mock.patch.object(W.M, "load_pbp", return_value=p), \
                    mock.patch.object(W, "RAW_DIR", d):
                self.assertEqual(W.score(2026, out=d, log=lambda m: None), ["g1"])
                self.assertEqual(W.score(2026, out=d, log=lambda m: None), [])      # written once
            s = pd.read_parquet(d / "scores" / "g1.parquet")
            self.assertEqual(sorted(s["pid"].unique()), ["te", "wr"])           # "gone" did not play -> excluded from both versions
            self.assertEqual(s.loc[s["pid"] == "te", "actual"].tolist(), [0.0, 0.0])
            self.assertEqual(W.summary(d)["paired_v2_minus_v1"]["n"], 2)


if __name__ == "__main__":
    unittest.main()
