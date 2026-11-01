"""Coverage features: lagged, shrunk and neutral when there is no history. Synthetic inputs, no local data files needed."""
import numpy as np
import pandas as pd

from lab import coverage_usage as C


def _lag():
    lag = C.Lagged.__new__(C.Lagged)
    lag._dcache, lag._rcache = {}, {}
    rows = [(2026, w, t, m) for w in (1, 2, 3) for t, m in (("AAA", 0.4), ("BBB", 0.2))]
    lag.d = pd.DataFrame(rows, columns=["season", "week", "team", "man"]).assign(c1=0.1, c2=0.1, c3=0.3, c4=0.1, c6=0.1, blitz=0.2)
    lag.r = pd.DataFrame([(2026, w, "p1", 30, 2.0, 15, 3.0, 15, 1.0) for w in (1, 2, 3)],
                         columns=["season", "week", "pid", "rte", "yprr", "m_rte", "m_yprr", "z_rte", "z_yprr"])
    return lag


def test_only_earlier_weeks_feed_a_game():
    lag = _lag()
    assert lag.defense(2026, 3).shape[0] == 2 and lag.defense(2026, 2).shape[0] == 0   # week 2 has one earlier week; two are needed
    assert lag.receivers(2026, 1).empty


def test_defense_mix_is_measured_against_the_league_and_receiver_splits_are_shrunk():
    lag = _lag()
    d = lag.defense(2026, 4)
    assert abs(d.loc["AAA", "man"] - 0.1) < 1e-9 and abs(d.loc["BBB", "man"] + 0.1) < 1e-9
    r = lag.receivers(2026, 4).loc["p1"]
    assert r["man"] > r["overall"] > r["zone"] and r["man"] < 3.0   # his man split is pulled toward his overall number


def test_features_are_zero_without_history_and_signed_with_it():
    lag = _lag()
    opp = {(2026, 4, "XXX"): "AAA", (2026, 4, "YYY"): "ZZZ"}
    f = C.team_game_features(lag, opp, 2026, 4, "XXX", ["p1", "nobody"], ["WR", "WR"])
    names = C.feature_names()
    assert f[0, names.index("matched")] > 0 and f[1, names.index("matched")] == 0 and abs(f[0, names.index("man_WR")] - 0.1) < 1e-9
    assert not C.team_game_features(lag, opp, 2026, 4, "YYY", ["p1"], ["WR"]).any()
