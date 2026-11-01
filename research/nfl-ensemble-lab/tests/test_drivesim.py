"""Independent drive simulation: synthetic inputs only."""
import numpy as np
import pandas as pd
import pytest

from lab import drivesim as DS


def _rates():
    rows = []
    for gid, team, td in (("g1", "HHH", 0.30), ("g1", "AAA", 0.15)):
        rows.append({"game_id": gid, "team": team, "drives": 11.0, "td": td, "fg": 0.15, "def_drives": 11.0, "def_td": 0.22, "def_fg": 0.15})
    return pd.DataFrame(rows).set_index(["game_id", "team"])


def test_matchup_combines_offense_and_what_the_defense_allows():
    r = _rates()
    m = DS.matchup(r, "g1", "HHH", "AAA", {"td": 0.22, "fg": 0.15, "drives": 11.0})
    assert m["home"]["td"] == pytest.approx(0.30 + 0.22 - 0.22) and m["away"]["td"] == pytest.approx(0.15)
    assert DS.matchup(r, "g1", "HHH", "ZZZ") is None


def test_simulation_scores_are_touchdowns_and_field_goals_and_favor_the_better_offense():
    m = DS.matchup(_rates(), "g1", "HHH", "AAA", {"td": 0.22, "fg": 0.15, "drives": 11.0})
    h, a = DS.simulate(m, 4000, 3)
    assert (h >= 0).all() and h.dtype.kind == "i"
    s = DS.summarize(h, a)
    assert s["p_home"] > 0.6 and s["margin"] > 3 and 10 < s["sd_m"] < 20
    h2, a2 = DS.simulate(m, 4000, 3)
    assert (h == h2).all() and (a == a2).all()  # same seed, same games


def test_home_edge_helps_the_home_side():
    m = DS.matchup(_rates(), "g1", "AAA", "HHH", {"td": 0.22, "fg": 0.15, "drives": 11.0})
    flat = DS.summarize(*DS.simulate(m, 6000, 1, edge=0.0))["margin"]
    edge = DS.summarize(*DS.simulate(m, 6000, 1, edge=0.08))["margin"]
    assert edge > flat
