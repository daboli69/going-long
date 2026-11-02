"""King of the End Zone: the length multiplier, shrinkage, and the longest-touchdown arithmetic. Synthetic league tables, no data files needed."""
import numpy as np
import pytest

from lab import kingzone as K


def test_multiplier_is_flat_to_ten_yards_then_ramps_to_the_20_and_40_plus_values():
    m = K._mult(2.0, 4.0)
    assert m[:10] == pytest.approx(np.ones(10))                 # lengths 1 to 10 untouched
    assert m[24] == pytest.approx(2.0)                          # 25 yards: the 20+ multiplier in full
    assert m[49] == pytest.approx(4.0)                          # 50 yards: the 40+ multiplier
    assert m[98] == pytest.approx(4.0)                          # flat beyond
    assert np.all(np.diff(m) >= -1e-12)                         # never falls when both multipliers are above 1


def test_ratio_shrinks_toward_the_group_and_is_clipped():
    assert K._ratio(0, 0, 0.1, 8.0) == pytest.approx(1.0)       # no touches: the group rate
    assert K._ratio(20, 100, 0.05, 8.0) == pytest.approx(28 / 13)   # 20 events in 100 touches at a 5% group rate, 8 pseudo-events
    assert K._ratio(0, 5000, 0.1, 8.0) == K.CLIP[0]
    assert K._ratio(500, 100, 0.01, 1.0) == K.CLIP[1]


def _league():
    dens = np.full(99, 0.0004)
    base = {"n": 5000, "p20": 0.08, "p40": 0.02, "deep": 0.15, "yac": 5.0, "catch": 0.65, "dens": dens}
    lg = {(k, g): dict(base) for k in (0, 1) for g in ("QB", "RB", "WR", "TE", "ALL")}
    import pandas as pd
    return {"lg": lg, "player": pd.DataFrame(columns=["n", "c20", "c40", "deep", "comp", "yac", "air"]).set_index(pd.MultiIndex.from_arrays([[], []], names=["pid", "kind"])),
            "defense": pd.DataFrame(columns=["n", "c20", "c40", "games"]).set_index(pd.MultiIndex.from_arrays([[], []], names=["opp", "kind"])),
            "ret_rate": 0.1, "ret_dens": np.full(99, 1 / 99), "pool_dens": {0: dens, 1: dens}, "broken": {"rate": 0.06, "by": {}}}


def _sim():
    rows = []
    for team, names in (("AAA", ["A Back", "A Wide"]), ("BBB", ["B Back", "B Wide"])):
        rows += [{"player": names[0], "team": team, "stat": "Rushing yards", "typical": 60.0, "carries": 15.0, "pos": "RB"},
                 {"player": names[1], "team": team, "stat": "Receptions", "expected": 5.0, "typical": 5.0, "pos": "WR", "fpds": {"yprr": 1.8}}]
    tm = lambda a, b: {"exp_points": 24.0, "rush_share": 0.4, "rec_weights": {a: 0.6, b: 0.3}}
    return {"away": "AAA", "home": "BBB", "players": rows, "td_model": {"AAA": tm("A Wide", "A Back"), "BBB": tm("B Wide", "B Back")}}


def test_chances_plus_the_field_and_no_touchdown_sum_to_one(monkeypatch):
    monkeypatch.setattr(K, "_league", lambda week: _league())
    out = K.probabilities(_sim(), 8)
    total = sum(r["chance"] for r in out["rows"]) + sum(out["unlisted"].values()) + sum(out["field"].values()) + out["no_td"]
    assert total == pytest.approx(1.0, abs=1e-6)
    assert all(0 <= r["chance"] <= 1 for r in out["rows"])


def test_a_more_explosive_player_gets_the_larger_share_of_the_title(monkeypatch):
    lg = _league()
    monkeypatch.setattr(K, "_league", lambda week: lg)
    base = K.probabilities(_sim(), 8)
    even = {r["player"]: r["chance"] for r in base["rows"]}
    assert even["A Wide"] == pytest.approx(even["B Wide"], rel=1e-6)   # identical teams, identical inputs
    import pandas as pd
    idx = pd.MultiIndex.from_tuples([(None, 1)], names=["pid", "kind"])
    monkeypatch.setattr(K.S, "_pid_by_norm", lambda: {K.S._norm("A Wide"): "pidA"})
    lg["player"] = pd.DataFrame({"n": [400.0], "c20": [90.0], "c40": [30.0], "deep": [80.0], "comp": [260.0], "yac": [1500.0], "air": [4800.0]}, index=pd.MultiIndex.from_tuples([("pidA", 1)], names=["pid", "kind"]))
    hot = {r["player"]: r["chance"] for r in K.probabilities(_sim(), 8)["rows"]}
    assert hot["A Wide"] > even["A Wide"] * 1.3
    assert hot["B Wide"] < even["B Wide"]                          # a bigger rival lowers everyone else's chance
