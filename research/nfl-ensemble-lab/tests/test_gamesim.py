"""Simulated game: synthetic inputs, no network, no saved files needed."""
import pandas as pd
import pytest

from lab import gamesim as S

PROPS = [
    {"player": "Away QB", "team": "AAA", "stat": "Passing yards", "typical": 230.0},
    {"player": "Away WR", "team": "AAA", "stat": "Receiving yards", "typical": 80.0},
    {"player": "Away WR", "team": "AAA", "stat": "Receptions", "typical": 6.0},
    {"player": "Away RB", "team": "AAA", "stat": "Rushing yards", "typical": 70.0},
    {"player": "Home QB", "team": "HHH", "stat": "Passing yards", "typical": 260.0},
    {"player": "Home RB", "team": "HHH", "stat": "Rushing yards", "typical": 90.0},
]


@pytest.mark.parametrize("target,expect", [(0, (0, 0)), (17, (2, 1)), (20, (2, 2)), (28, (4, 0)), (10, (1, 1))])
def test_reachable_score(target, expect):
    assert S.reachable_score(target) == expect


def test_score_ranges_are_ordered_and_deterministic():
    a = S.score_ranges("2026_08_AAA_HHH", 6.5, 13.0, 45.5, 13.0)
    assert a == S.score_ranges("2026_08_AAA_HHH", 6.5, 13.0, 45.5, 13.0)
    for k in ("home", "away", "total"):
        assert a[k]["low"] <= a[k]["median"] <= a[k]["high"]
    assert a["home"]["median"] > a["away"]["median"]
    assert abs(a["total"]["median"] - 45.5) <= 1


def test_replay_lands_on_targets_and_keeps_a_valid_clock():
    rp = S.replay("2026_08_AAA_HHH", "AAA", "HHH", {"AAA": 17, "HHH": 24}, PROPS, pd.DataFrame())
    assert rp["final"] == {"AAA": 17, "HHH": 24}
    plays = rp["plays"]
    assert 80 <= len(plays) <= 170
    assert plays[-1]["score"] == rp["final"]
    elapsed = [(p["qtr"] - 1) * 900 + 900 - int(p["clock"][:2]) * 60 - int(p["clock"][3:]) for p in plays]
    assert elapsed == sorted(elapsed) and plays[0]["clock"] == "15:00" and plays[-1]["qtr"] == 4
    for p in plays:
        assert 0 <= p["x_start"] <= 100 and 0 <= p["x_end"] <= 100
        if p["event"] == "TD":
            assert p["x_end"] == (100 if p["team"] == "AAA" else 0)
    named = sum(p["yards"] for p in plays if p["player"] == "Home RB" and p["kind"] == "rush")
    assert 60 <= named <= 95
    assert rp == S.replay("2026_08_AAA_HHH", "AAA", "HHH", {"AAA": 17, "HHH": 24}, PROPS, pd.DataFrame())


def test_replay_without_player_projections_uses_generic_names():
    rp = S.replay("2026_08_AAA_HHH", "AAA", "HHH", {"AAA": 10, "HHH": 3}, [], pd.DataFrame())
    assert rp["final"] == {"AAA": 10, "HHH": 3}
    assert rp["qbs"] == {"AAA": "AAA quarterback", "HHH": "HHH quarterback"}


def test_score_changes_only_on_scoring_plays():
    plays = S.replay("2026_08_AAA_HHH", "AAA", "HHH", {"AAA": 17, "HHH": 24}, PROPS, pd.DataFrame())["plays"]
    prev = {"AAA": 0, "HHH": 0}
    for p in plays:
        if p["score"] != prev:
            assert p["event"] in ("TD", "FG")
        prev = p["score"]
