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


def _row(player, stat, typical, team="AAA"):
    return {"player": player, "team": team, "stat": stat, "typical": typical, "range_low": typical / 2, "range_high": typical * 2,
            "market_line": None, "market_chance": None, "our_chance": None}


def test_out_receiver_production_moves_to_teammates():
    rows = [_row("QB One", "Passing yards", 250), _row("WR Out", "Receiving yards", 80), _row("WR Out", "Receptions", 6),
            _row("WR Two", "Receiving yards", 60), _row("WR Two", "Receptions", 4), _row("TE", "Receiving yards", 20), _row("TE", "Receptions", 2),
            _row("Other team WR", "Receiving yards", 70, team="HHH")]
    new, moves = S.apply_injuries(rows, "AAA", {S._norm("WR Out"): ("WR Out", "Out")}, ["QB One"])
    assert not any(r["player"] == "WR Out" for r in new)
    got = {(r["player"], r["stat"]): r["typical"] for r in new}
    assert got[("WR Two", "Receiving yards")] == pytest.approx(60 + 0.75 * 80 * 60 / 80)
    assert got[("TE", "Receptions")] == pytest.approx(2 + 0.75 * 6 * 2 / 6)
    assert got[("Other team WR", "Receiving yards")] == 70
    assert moves[0]["player"] == "WR Out" and "WR Two" in moves[0]["text"]


def test_out_quarterback_is_replaced_by_the_next_healthy_backup():
    rows = [_row("Starter Jr.", "Passing yards", 250), _row("WR", "Receiving yards", 60)]
    out = {S._norm("Starter"): ("Starter", "Injured Reserve"), S._norm("Backup One"): ("Backup One", "Out")}
    new, moves = S.apply_injuries(rows, "AAA", out, ["Starter", "Backup One", "Backup Two"])
    qb = [r for r in new if r["stat"] == "Passing yards"]
    assert [r["player"] for r in qb] == ["Backup Two"] and qb[0]["typical"] == 250
    assert "Backup Two starts" in moves[0]["text"]


def test_weather_indoors_too_early_and_forecast(tmp_path, monkeypatch):
    from lab import gameweather as W
    monkeypatch.setattr(W, "CACHE", tmp_path)
    now = pd.Timestamp.now(tz="UTC").floor("h")
    assert W.kickoff_weather("g1", "Ford Field", "dome", now, False)["status"] == "indoors"
    assert W.kickoff_weather("g2", "Lambeau Field", "outdoors", now + pd.Timedelta(days=30), False)["status"] == "too_early"
    hours = pd.date_range(now - pd.Timedelta(hours=2), periods=8, freq="h")
    fake = {"hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in hours], "temperature_2m": [40.0] * 8, "precipitation_probability": [10, 20, 30, 60, 5, 5, 5, 5],
                       "precipitation": [0.0] * 8, "weather_code": [61] * 8, "wind_speed_10m": [5, 6, 7, 18, 9, 30, 1, 1], "wind_gusts_10m": [9] * 8}}
    w = W.kickoff_weather("g3", "Lambeau Field", "outdoors", now + pd.Timedelta(hours=1), False, fetch=lambda url: fake)
    assert w["status"] == "forecast" and w["temp_f"] == 40 and w["condition"] == "Rain"
    assert w["wind_mph"] == 30 and w["precip_chance"] == 60
    assert W.kickoff_weather("g3", "Lambeau Field", "outdoors", now + pd.Timedelta(hours=1), False, fetch=lambda url: 1 / 0) == w  # cached
    down = W.kickoff_weather("g4", "Lambeau Field", "outdoors", now + pd.Timedelta(hours=1), False, fetch=lambda url: 1 / 0)
    assert down["status"] == "unavailable"


def test_every_stadium_on_the_schedule_has_a_location():
    from lab import gamecenter_data as D, gameweather as W
    G = D.games_table()
    if G.empty:
        pytest.skip("no games table")
    assert set(G[G["season"] == D.SEASON]["stadium"].dropna()) <= set(W.STADIUMS)
