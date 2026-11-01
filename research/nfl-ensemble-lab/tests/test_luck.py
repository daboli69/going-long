"""Luck-adjusted strength test: scoring, statistics, the as-of rule and the pieces that can be checked on synthetic inputs (no data files)."""
import numpy as np
import pytest
from scipy.stats import norm

from lab import luck_elo as LE
from lab import luck_eval as EV
from lab import luck_strength as LS


def test_crps_matches_the_closed_form_and_penalizes_bad_spread():
    y = np.array([0.0])
    assert EV.crps(y, 0.0, 1.0)[0] == pytest.approx((np.sqrt(2) - 1) / np.sqrt(np.pi))     # known value for a standard normal at its median
    assert EV.crps(y, 5.0, 1.0)[0] > EV.crps(y, 0.0, 1.0)[0] and EV.crps(y, 0.0, 0.1)[0] < EV.crps(np.array([3.0]), 0.0, 0.1)[0]


def test_week_bootstrap_brackets_the_mean_and_sees_a_clear_gain():
    rng = np.random.default_rng(1)
    weeks = np.repeat(np.arange(60), 5)
    d = rng.normal(-0.5, 1.0, 300)
    r = EV.week_bootstrap(d, weeks, draws=800)
    assert r["lo"] < r["mean"] < r["hi"] and r["hi"] < 0 and r["weeks"] == 60
    assert EV.week_bootstrap(rng.normal(0, 1, 300), weeks, draws=800)["lo"] < 0 < EV.week_bootstrap(rng.normal(0, 1, 300), weeks, draws=800)["hi"] + 0.5


def test_diebold_mariano_flags_a_steady_difference_and_not_noise():
    rng = np.random.default_rng(2)
    weeks = np.repeat(np.arange(120), 4)
    assert EV.diebold_mariano(rng.normal(-0.4, 1, 480), weeks)["p"] < 0.01
    assert EV.diebold_mariano(rng.normal(0, 1, 480), weeks)["p"] > 0.01


def test_holm_adjusts_in_order_and_never_lowers_a_p_value():
    h = EV.holm({"a": 0.01, "b": 0.04})
    assert h["a"] == pytest.approx(0.02) and h["b"] == pytest.approx(0.04)
    assert EV.holm({"a": 0.03, "b": 0.03})["b"] >= 0.03


def test_placebo_shuffle_is_worse_than_the_real_forecast_when_the_forecast_has_signal():
    rng = np.random.default_rng(3)
    n = 400
    weeks = np.repeat(np.arange(40), 10)
    mu = rng.normal(0, 6, n)
    y = mu + rng.normal(0, 10, n)
    sd = np.full(n, 11.0)
    real = EV.crps(y, mu, sd)
    ref = EV.crps(y, np.zeros(n), np.full(n, 12.0))
    assert real.mean() < ref.mean()
    p = EV.placebo(mu, sd, y, ref, weeks, np.zeros(n), shuffles=40)
    assert p["mean_diff"] > (real - ref).mean()


def test_coverage_pit_and_brier_decomposition():
    rng = np.random.default_rng(4)
    y = rng.normal(0, 1, 20000)
    assert EV.coverage80(y, 0.0, 1.0) == pytest.approx(0.8, abs=0.01)
    pit = EV.pit_hist(y, 0.0, 1.0)
    assert max(pit) / min(pit) < 1.15
    p = rng.uniform(0.05, 0.95, 20000)
    win = (rng.uniform(size=20000) < p).astype(float)
    b = EV.brier_decomposition(p, win)
    assert b["brier"] == pytest.approx(b["reliability"] - b["resolution"] + b["uncertainty"], abs=0.01) and b["reliability"] < 0.01


def test_blend_weight_is_one_when_the_new_probability_is_the_truth_and_zero_when_it_is_noise():
    rng = np.random.default_rng(5)
    truth = rng.uniform(0.2, 0.8, 20000)
    win = (rng.uniform(size=20000) < truth).astype(float)
    line = np.clip(truth + rng.normal(0, 0.08, 20000), 0.02, 0.98)
    assert EV.best_blend_weight(line, truth, win) > 0.5
    assert abs(EV.best_blend_weight(truth, np.clip(truth + rng.normal(0, 0.15, 20000), 0.02, 0.98), win)) < 0.3


def test_history_window_uses_only_earlier_rows_of_the_same_key_within_three_seasons():
    P = LS.Panel.__new__(LS.Panel)
    P.season = np.array([2005, 2006, 2008, 2008, 2009, 2009])
    key = np.array([1, 1, 1, 2, 1, 2])
    vals = np.arange(1, 7, dtype=float)[:, None]
    h = P._hist(key, vals)[:, 0]
    # the window is this season and the two before: the 2009 game of key 1 sees only the 2008 row (3); the 2008 game sees 2006 (2) but not 2005
    assert list(h) == [0.0, 1.0, 2.0, 0.0, 3.0, 4.0]


def test_asof_rule_flags_a_game_that_feeds_itself_and_passes_an_honest_week_gap():
    P = LS.Panel.__new__(LS.Panel)
    t = np.datetime64("2020-09-13T17:00")
    P.G, P.nb = 4, 2
    P.g_kick = np.array([t, t + np.timedelta64(1, "h"), t + np.timedelta64(7, "D"), t + np.timedelta64(7, "D") + np.timedelta64(3, "h")])
    P.g_batch = np.array([0, 0, 1, 1])
    P.g_start = np.array([0, 2, 4])
    P.games = type("G", (), {"__getitem__": lambda s, k: type("C", (), {"iloc": list(range(4))})()})()
    assert LS.check_asof(P)["violations"] == 0
    assert LS.check_asof(P, P.g_batch)["violations"] == 4          # each target using its own week as a source is flagged
    P.g_kick[2] = t + np.timedelta64(5, "h")                         # a next-"week" game starting 5 hours after: too close
    assert LS.check_asof(P)["violations"] == 1


def test_elo_moves_toward_the_winner_and_regresses_by_a_third_at_a_new_season():
    import pandas as pd

    def games(third_season):
        return pd.DataFrame({"game_id": ["a", "b", "c"], "season": [2020, 2020, third_season], "home": ["X", "Y", "X"], "away": ["Y", "X", "Y"],
                             "home_score": [30.0, 10.0, 20.0], "away_score": [10.0, 30.0, 17.0], "neutral": [False] * 3, "played": [True] * 3})
    same = LE.elo_history(games(2020))
    assert same["p_home"].iloc[0] == pytest.approx(1 / (1 + 10 ** (-55 / 400)))
    assert same["away_elo"].iloc[1] > 1500 > same["home_elo"].iloc[1]          # X won game a, so X is above and Y below 1500 before game b
    r2 = same["home_elo"].iloc[2]
    assert r2 > 1500
    nxt = LE.elo_history(games(2021))
    assert nxt["home_elo"].iloc[2] == pytest.approx(1500 + (2 / 3) * (r2 - 1500))
