import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
from scipy import stats

from lab.props import evaluate as E
from lab.props import models as M
from lab.props import sim as S


def _fourth():
    g = np.stack(np.meshgrid(np.arange(7), np.arange(7), np.arange(7), np.arange(4), indexing="ij"), -1).reshape(-1, 4)
    near = g[:, 1] <= 3                                    # yardline bucket: inside the 40 -> field goal, else punt
    return np.where(near[:, None], [0.1, 0.0, 0.9], [0.1, 0.9, 0.0])


def _toy_tables():
    G = M._grid()
    n = len(G)
    T = {"p_pass": np.full(n, 0.55), "p_sack": np.full(n, 0.06), "air": np.tile([.2, .3, .2, .1, .1, .05, .05], (n, 1)),
         "outcome": np.tile([.65, .33, .02], (147, 1)), "yac": np.tile([.3, .3, .2, .1, .07, .03], (49, 1)),
         "rush": np.tile([.15, .25, .25, .2, .1, .04, .01], (n, 1)),
         "air_vals": [np.array([-2.0]), np.array([3.0]), np.array([7.0]), np.array([12.0]), np.array([17.0]), np.array([25.0]), np.array([40.0])],
         "yac_vals": [np.array([0.0]), np.array([2.0]), np.array([4.0]), np.array([8.0]), np.array([14.0]), np.array([30.0])],
         "rush_vals": [np.array([-1.0]), np.array([1.0]), np.array([3.0]), np.array([5.0]), np.array([9.0]), np.array([15.0]), np.array([30.0])],
         "rz_rush": {}, "rz_pass": {}, "sack_vals": np.array([-7.0]), "fum_comp": 0.005, "fum_run": 0.006, "fum_sack": 0.1,
         "fourth": _fourth(), "fg_coef": (6.0, -0.12), "pat": 0.94, "kick_start": np.array([75.0]),
         "punt_start": [np.array([80.0])] * 7, "clock": {(k, h): np.array([30.0 if k == 1 else 6.0]) for k in range(3) for h in (False, True)},
         "pen_rate": 0.05, "pen_gain": np.array([-5.0, 5.0]), "pen_fd": np.array([False, True]), "sigma_e": 0.15, "kappa": 30.0}
    return T


def _toy_teams():
    P = 8
    pl = {"w_recv": np.zeros(P), "dist_recv": np.full((P, 7), 1 / 7), "coff": np.zeros(P), "w_rush": np.zeros(P), "dist_rush": np.full((P, 7), 1 / 7)}
    tm = [{"pass_off": 0.0, "recv_cols": np.array([0, 1]), "recv_cum": np.array([.6, 1.]), "rush_cols": np.array([2, 3]), "rush_cum": np.array([.8, 1.]), "qb_col": 3},
          {"pass_off": 0.0, "recv_cols": np.array([4, 5]), "recv_cum": np.array([.6, 1.]), "rush_cols": np.array([6, 7]), "rush_cum": np.array([.8, 1.]), "qb_col": 7}]
    return tm, pl


class TestProps(unittest.TestCase):
    def test_crps_samples_matches_normal_closed_form(self):
        x = np.random.default_rng(0).normal(50, 10, 200_000)
        self.assertAlmostEqual(E.crps_samples(x, 63.0), E.crps_normal(50, 10, 63.0), delta=0.05)

    def test_qb_yards_equal_receivers_and_game_ends(self):
        tm, pl = _toy_teams()
        r = S.simulate(_toy_tables(), tm, pl, 500, [0, 0], np.random.default_rng(1))
        st = r["stats"]
        np.testing.assert_allclose(st["pass_yds"][:, 3], st["rec_yds"][:, 0] + st["rec_yds"][:, 1])   # same simulated plays
        np.testing.assert_allclose(st["pass_yds"][:, 7], st["rec_yds"][:, 4] + st["rec_yds"][:, 5])
        self.assertTrue((r["points"] >= 0).all() and r["points"].mean() > 3)

    def test_market_calibration_moves_points_toward_targets(self):
        tm, pl = _toy_teams()
        T = _toy_tables()
        base = S.simulate(T, tm, pl, 1500, [0, 0], np.random.default_rng(5), record=False)["points"].mean()
        tgt = [base * 1.3, base * 0.75]
        e, pts = S.calibrate(T, tm, pl, tgt, np.random.default_rng(2), n=1500, iters=8)
        self.assertGreater(base, 8)
        self.assertGreater(e[0], e[1])
        self.assertLess(abs(pts[0] - tgt[0]), 0.15 * tgt[0])
        self.assertLess(abs(pts[1] - tgt[1]), 0.15 * tgt[1])

    def test_state_buckets(self):
        self.assertEqual(M.b_togo(np.array([1, 2, 4, 7, 10, 15, 25])).tolist(), [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(M.b_sd(np.array([-21, -10, -3, 0, 3, 10, 21])).tolist(), [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(M.b_time(np.array([3000, 1850, 1700, 600, 200])).tolist(), [0, 1, 0, 2, 3])

    def test_bootstrap_detects_clear_improvement(self):
        rng = np.random.default_rng(3)
        df = pd.DataFrame({"game_id": np.repeat(np.arange(200), 5), "crps_base": rng.normal(20, 3, 1000)})
        df["crps_sim"] = df["crps_base"] - 1.0 + rng.normal(0, 1, 1000)
        obs, p, ci = E.boot_test(df)
        self.assertLess(obs, 0)
        self.assertLess(p, 0.01)
        _, p2, _ = E.boot_test(df.assign(crps_sim=df["crps_base"] + 0.5))
        self.assertGreater(p2, 0.5)

    def test_evaluation_look_cannot_be_retaken(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(E, "OUT", Path(d)):
            (Path(d) / "eval").mkdir()
            (Path(d) / "eval" / "player_games.parquet").write_bytes(b"x")
            with self.assertRaises(FileExistsError):
                E.run("eval", E.EVAL)


if __name__ == "__main__":
    unittest.main()
