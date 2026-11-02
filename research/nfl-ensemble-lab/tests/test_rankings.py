"""Weekly player rankings: percentile scores, the blend, touchdown chances, tags and the route. Synthetic inputs, no data files needed."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from lab import rankings as R
from web.server import app


def test_percentile_rank_runs_zero_to_one_hundred_and_ties_share():
    assert list(R.pct_rank(np.array([5.0, 9.0, 1.0]))) == [50.0, 100.0, 0.0]
    assert list(R.pct_rank(np.array([2.0, 2.0, 8.0]))) == [25.0, 25.0, 100.0]
    assert list(R.pct_rank(np.array([7.0]))) == [50.0]


def test_blend_uses_the_stated_weights_and_reweights_around_missing_parts():
    full = {"projection": 100.0, "matchup": 0.0, "usage": 0.0}
    assert R.blend(full) == pytest.approx(50.0)                                    # 50% projection
    assert R.blend({"projection": 80.0, "matchup": None, "usage": 40.0}) == pytest.approx((0.5 * 80 + 0.25 * 40) / 0.75)
    assert R.blend({"projection": None, "matchup": None, "usage": None}) is None
    assert sum(R.WEIGHTS.values()) == pytest.approx(1.0)


def _sim():
    return {"td_model": {"AAA": {"exp_points": 27.0, "rush_share": 0.4, "rec_weights": {"WR One": 0.5, "RB One": 0.3, "TE One": 0.2}}},
            "players": [{"player": "RB One", "team": "AAA", "stat": "Rushing yards", "typical": 60.0},
                        {"player": "RB Two", "team": "AAA", "stat": "Rushing yards", "typical": 20.0},
                        {"player": "WR One", "team": "AAA", "stat": "Receiving yards", "typical": 70.0}],
            "questionable": [{"player": "TE One", "team": "AAA", "chance": 0.7, "plays": True}],
            "injury_moves": [{"team": "AAA", "text": "Usually 50 receiving yards a game. The team keeps about 80% of it: WR One +12, RB One +3."}]}


def test_touchdown_chances_follow_expected_points_and_split_by_rush_share():
    t = R.td_chances(_sim())
    exp_td = R.TD_PER_POINT * 27.0 + R.TD_INTERCEPT
    assert t[("WR One", "AAA")]["exp_td"] == pytest.approx(exp_td * 0.6 * 0.5)
    # RB One catches 30% of the receiving touchdowns and carries 75% of the team's rushing yards
    assert t[("RB One", "AAA")]["exp_td"] == pytest.approx(exp_td * (0.6 * 0.3 + 0.4 * 0.75))
    assert t[("RB One", "AAA")]["chance"] == pytest.approx(1 - np.exp(-t[("RB One", "AAA")]["exp_td"]))
    assert ("WR One", "AAA") in t and t[("RB Two", "AAA")]["exp_td"] == pytest.approx(exp_td * 0.4 * 0.25)


def test_expected_touchdowns_have_a_floor_for_very_low_scoring_teams():
    s = _sim()
    s["td_model"]["AAA"]["exp_points"] = 0.0
    assert R.td_chances(s)[("WR One", "AAA")]["exp_td"] == pytest.approx(R.TD_FLOOR * 0.6 * 0.5)


def test_tags_say_where_the_projection_sits_against_the_line_and_flag_questionable_and_shared_load():
    sim = _sim()
    above = {"player": "WR One", "stat": "rec_yds", "projection": 70.0, "market_line": 60.0}
    assert R._tags(above, sim, "AAA") == ["Above the line", "Gets a teammate's share"]
    assert R._tags({**above, "projection": 50.0}, sim, "AAA")[0] == "Below the line"
    assert R._tags({**above, "projection": 61.0}, sim, "AAA") == ["Gets a teammate's share"]
    assert "Questionable" in R._tags({"player": "TE One", "stat": "rec_yds", "projection": 30.0, "market_line": None}, sim, "AAA")
    assert R._tags({"player": "WR One", "stat": "td", "projection": 0.4, "market_line": 3.0}, sim, "AAA") == ["Gets a teammate's share"]   # no line tag on touchdowns


def test_fpds_usage_is_taken_from_whichever_row_has_it():
    assert R.fpds_of({"a": {"stat": "x"}, "b": {"fpds": {"tgt_pct": 0.2}}}) == {"tgt_pct": 0.2}
    assert R.fpds_of({"a": {"stat": "x"}}) == {}


def test_rankings_route_rejects_bad_weeks_and_returns_the_shape_the_screen_reads(monkeypatch):
    client = TestClient(app)
    assert client.get("/api/rankings/0").status_code == 422 and client.get("/api/rankings/99").status_code == 422
    fake = {"week": 8, "weights": R.WEIGHTS, "stats": {"rec_yds": {"label": "Receiving yards", "unit": "yds", "rows": []}}, "built_at": 1.0}
    monkeypatch.setattr(R, "week_rankings", lambda w: fake)
    r = client.get("/api/rankings/8")
    assert r.status_code == 200 and r.json()["stats"]["rec_yds"]["label"] == "Receiving yards" and r.json()["weights"]["projection"] == 0.5


def test_first_touchdown_is_his_share_of_both_teams_expected_touchdowns_times_the_chance_of_any_touchdown():
    s = _sim()
    s["td_model"]["BBB"] = {"exp_points": 20.0, "rush_share": 0.5, "rec_weights": {"WR Z": 1.0}}
    s["players"].append({"player": "RB Z", "team": "BBB", "stat": "Rushing yards", "typical": 50.0})
    t = R.td_chances(s)
    total = max(R.TD_FLOOR, R.TD_PER_POINT * 27.0 + R.TD_INTERCEPT) + max(R.TD_FLOOR, R.TD_PER_POINT * 20.0 + R.TD_INTERCEPT)
    one = t[("WR One", "AAA")]
    assert one["first"] == pytest.approx((1 - np.exp(-total)) * one["exp_td"] / total)
    assert sum(v["first"] for v in t.values()) <= 1 - np.exp(-total) + 1e-9     # at most one first touchdown per game
    assert all(v["first"] < v["chance"] for v in t.values())                  # a first touchdown is rarer than any touchdown
