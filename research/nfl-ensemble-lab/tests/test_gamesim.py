"""Simulated game: synthetic inputs, no network, no saved files needed."""
import numpy as np
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
    {"player": "Home WR", "team": "HHH", "stat": "Receiving yards", "typical": 150.0},
    {"player": "Home WR", "team": "HHH", "stat": "Receptions", "typical": 11.0},
    {"player": "Home TE", "team": "HHH", "stat": "Receiving yards", "typical": 110.0},
    {"player": "Home TE", "team": "HHH", "stat": "Receptions", "typical": 9.0},
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


def _usage():
    from lab import usage as U
    players = pd.DataFrame([
        {"pid": "wr1", "pos": "WR", "n": 6, "last": 6, "active": True, "share_rec_yds": 0.40, "share_rec": 0.35, "share_rush_yds": 0.0, "pass_yds": 0, "att": 0, "carries": 0, "rush_pg": 0},
        {"pid": "wr2", "pos": "WR", "n": 6, "last": 6, "active": True, "share_rec_yds": 0.30, "share_rec": 0.30, "share_rush_yds": 0.0, "pass_yds": 0, "att": 0, "carries": 0, "rush_pg": 0},
        {"pid": "te1", "pos": "TE", "n": 6, "last": 6, "active": True, "share_rec_yds": 0.20, "share_rec": 0.20, "share_rush_yds": 0.0, "pass_yds": 0, "att": 0, "carries": 0, "rush_pg": 0},
        {"pid": "rb1", "pos": "RB", "n": 6, "last": 6, "active": True, "share_rec_yds": 0.10, "share_rec": 0.15, "share_rush_yds": 1.0, "pass_yds": 0, "att": 0, "carries": 18, "rush_pg": 80},
    ])
    return U.Usage("AAA", 6, {"rec_yds": 220.0, "rec": 20.0, "rush_yds": 110.0, "pass_yds": 230.0, "att": 34.0, "carries": 26.0}, players)


def test_usage_projection_accounts_for_every_yard():
    from lab import usage as U
    proj = U.Rule("all").project(_usage(), set())
    assert proj["rec_yds"].sum() == pytest.approx(220.0) and proj["rush_yds"].sum() == pytest.approx(110.0)


def test_missing_receiver_split_between_regulars_and_replacement():
    from lab import usage as U
    rule = U.Rule("r", k={"rec_yds": 0.9, "rec": 0.9, "rush_yds": 1.0}, to_new={"rec_yds": 0.2, "rec": 0.2, "rush_yds": 0.1}, m={"WR->WR": 2.0})
    proj = rule.project(_usage(), {"wr1"}).set_index("pid")
    lost = 0.40 * 220.0
    assert "wr1" not in proj.index
    assert proj.loc["NEW:WR", "rec_yds"] == pytest.approx(0.9 * 0.2 * lost)
    regulars_gain = proj.drop(index="NEW:WR")["rec_yds"].sum() - (220.0 - lost)
    assert regulars_gain == pytest.approx(0.9 * 0.8 * lost)
    gain = {j: proj.at[j, "rec_yds"] - base for j, base in (("wr2", 0.30 * 220), ("te1", 0.20 * 220))}
    assert gain["wr2"] / gain["te1"] == pytest.approx(2.0 * 0.30 / 0.20)  # position weight times usage
    assert proj["rec_yds"].sum() == pytest.approx(220.0 - 0.1 * lost)


def test_saved_rule_is_used_when_present(tmp_path):
    from lab import usage as U
    rule = U.Rule("saved", k={"rec_yds": 0.5, "rec": 0.5, "rush_yds": 0.5}, to_new={"rec_yds": 0.1}, m={"WR->WR": 1.5})
    U.save_rule(rule, [2025, 2026], path=tmp_path / "r.json")
    got, meta = U.current_rule(tmp_path / "r.json")
    assert got.k == rule.k and got.m == rule.m and meta["fitted_on"] == [2025, 2026]
    assert U.current_rule(tmp_path / "missing.json")[0].k == {s: 1.0 for s in U.STATS}


def test_every_ball_carrier_in_a_real_game_is_named():
    from lab import gamecenter_data as D
    G = D.games_table()
    if G.empty or not (S.RAW_DIR / "play_by_play_2026.parquet").exists():
        pytest.skip("no local data")
    g = G[(G["season"] == D.SEASON) & (G["game_type"] == "REG")]
    for gid in list(g[g["week"] == g["week"].min() + 2]["game_id"])[:4]:
        s = S.simulate(gid)
        players = {p["player"] for p in s["replay"]["plays"] if p["kind"] in ("pass", "rush")}
        assert players and not any(n.startswith("another ") or n.endswith((" receiver", " runner", " running back")) for n in players), gid


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


def _draws(mu_m=7.0, sd=13.0):
    return S.score_draws("2026_08_AAA_HHH", mu_m, sd, 46.0, 13.0)


def test_pick_game_typical_is_the_middle_and_random_and_upset_are_repeatable():
    h, a = _draws()
    typ = S.pick_game("g", "HHH", "AAA", h, a, "typical", 0)
    assert abs(typ["points"]["HHH"] - np.median(h)) <= 3 and abs(typ["points"]["AAA"] - np.median(a)) <= 3 and typ["favorite"] == "HHH"
    assert all(7 * td + 3 * fg == v for v in typ["points"].values() for td, fg in [S.reachable_score(v)])  # a score football can produce
    r1, r1b, r2 = (S.pick_game("g", "HHH", "AAA", h, a, "random", k) for k in (1, 1, 2))
    assert r1["points"] == r1b["points"] and r1["points"] != r2["points"]
    assert all(S.pick_game("g", "HHH", "AAA", h, a, "upset", k)["points"]["AAA"] > S.pick_game("g", "HHH", "AAA", h, a, "upset", k)["points"]["HHH"] for k in range(1, 30))


def test_random_games_win_for_the_underdog_at_the_simulated_rate_and_never_tie():
    h, a = _draws(mu_m=7.0)
    picks = [S.pick_game("g", "HHH", "AAA", h, a, "random", k) for k in range(1, 801)]
    assert all(p["points"]["HHH"] != p["points"]["AAA"] for p in picks)
    rate = np.mean([p["points"]["AAA"] > p["points"]["HHH"] for p in picks])
    assert abs(rate - picks[0]["p_underdog"]) < 0.05


def test_volume_scale_moves_the_yards_in_the_pool():
    import numpy.random as npr
    plain = S._pool("AAA", PROPS, None, npr.default_rng(1))[0]
    big = S._pool("AAA", PROPS, None, npr.default_rng(1), 1.25)[0]
    y = lambda pool: sum(p["yards"] for p in pool if p["kind"] in ("pass", "rush"))
    assert y(big) > y(plain) * 1.1


def test_replay_realises_what_the_players_were_projected_for():
    rp = S.replay("2026_08_AAA_HHH", "AAA", "HHH", {"AAA": 20, "HHH": 27}, PROPS, pd.DataFrame())
    for t, (ep, er) in rp["expect"].items():
        passing = sum(p["yards"] for p in rp["plays"] if p["team"] == t and p["kind"] == "pass")
        rushing = sum(p["yards"] for p in rp["plays"] if p["team"] == t and p["kind"] == "rush")
        assert abs(passing - ep) <= 0.25 * max(ep, 1) and abs(rushing - er) <= 0.25 * max(er, 1)


def test_roster_statuses_count_as_absences(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "RAW_DIR", tmp_path)
    pd.DataFrame([{"team": "KC", "week": 8, "status": st, "gsis_id": f"00-{i}", "full_name": nm} for i, (st, nm) in enumerate(
        [("ACT", "Healthy Guy"), ("RES", "Tyquan Thornton"), ("INA", "Game Day Out"), ("DEV", "Practice Squad")])]).to_parquet(tmp_path / "roster_weekly_2026.parquet")
    now = S.roster_out("KC", 8)
    assert set(now) == {S._norm("Tyquan Thornton"), S._norm("Game Day Out")} and now[S._norm("Tyquan Thornton")][1] == "Injured Reserve"
    later = S.roster_out("KC", 11)  # a later week keeps only the lasting statuses
    assert set(later) == {S._norm("Tyquan Thornton")}


def test_no_pick_ends_in_a_tie_even_in_a_pickem():
    h, a = S.score_draws("g", 0.2, 13.0, 40.0, 12.0)
    for mode in ("typical", "random", "upset"):
        for k in range(1, 60):
            pts = S.pick_game("g", "HHH", "AAA", h, a, mode, k)["points"]
            assert pts["HHH"] != pts["AAA"]


def test_the_announced_starter_comes_first_then_the_depth_chart_not_the_recent_volume_leader(monkeypatch):
    G = pd.DataFrame({"season": [S.D.SEASON], "week": [8], "home_team": ["BAL"], "away_team": ["BUF"], "home_qb_id": ["JACKSON"], "away_qb_id": [None]})
    monkeypatch.setattr(S.D, "games_table", lambda: G)
    monkeypatch.setattr(S, "depth_chart_qbs", lambda: {"BAL": ["JACKSON", "HUNTLEY"], "BUF": ["ALLEN", "BACKUP"]})
    monkeypatch.setattr(S, "current_week", lambda: 8)
    assert S.starting_qbs("BAL", 8) == ["JACKSON", "HUNTLEY"]          # the schedule's name first, then the depth chart, no repeats
    assert S.starting_qbs("BUF", 8) == ["ALLEN", "BACKUP"]             # nobody announced: depth chart QB1 first
    assert S.starting_qbs("BUF", 7) == []                              # a played week has no announced starter here and the depth chart is only for the coming game


def _feed(rows):
    return pd.DataFrame(rows, columns=["team", "player", "pos", "status", "note"])


def test_the_official_inactive_list_counts_as_posted_only_with_enough_inactive_notes_in_the_current_week(monkeypatch):
    posted = _feed([("TB", f"P{i}", "WR", "Out", "inactive") for i in range(4)] + [("DEN", "Q", "QB", "Out", "inactive"), ("DEN", "R", "RB", "Out", "knee")])
    monkeypatch.setattr(S.D, "injuries_now", lambda: (posted, "20261101T1724"))
    monkeypatch.setattr(S, "current_week", lambda: 8)
    assert S.inactives_final("TB", 8) is True            # four players Out with the note "inactive"
    assert S.inactives_final("DEN", 8) is False          # one emergency-quarterback note is not a posted list
    assert S.inactives_final("TB", 9) is False           # a later week has no list yet


def test_saved_projections_for_players_who_are_out_are_removed_and_listed(monkeypatch):
    detail = {"week": 8, "away": "ATL", "home": "TB", "props": [
        {"player": "Emeka Egbuka", "team": "TB", "stat": "Receiving yards", "typical": 44.0},
        {"player": "Emeka Egbuka", "team": "TB", "stat": "Receptions", "typical": 3.9},
        {"player": "Chris Godwin Jr.", "team": "TB", "stat": "Receiving yards", "typical": 60.0},
        {"player": "Drake London", "team": "ATL", "stat": "Receiving yards", "typical": 70.0}]}
    monkeypatch.setattr(S, "unavailable", lambda team, week, season=S.D.SEASON: ({"emeka egbuka": ("Emeka Egbuka", "Out")} if team == "TB" else {}, "feed"))
    monkeypatch.setattr(S.D, "injuries_now", lambda: (_feed([("ATL", "Drake London", "WR", "Questionable", "hip")]), "20261101T1724"))
    out = S.drop_unavailable_props(detail)
    assert [p["player"] for p in out["props"]] == ["Chris Godwin Jr.", "Drake London"]
    assert out["props_left_out"] == [{"player": "Emeka Egbuka", "team": "TB", "status": "Out"}]      # listed once, though he had two projections
    assert out["props_questionable"] == [{"player": "Drake London", "team": "ATL", "status": "Questionable"}]
    assert len(detail["props"]) == 4                                                                   # the saved detail is not changed


def test_name_matching_ignores_suffixes_so_jr_does_not_hide_a_ruled_out_player():
    assert S._norm("Brian Robinson Jr.") == S._norm("Brian Robinson") and S._norm("Kenneth Walker III") == S._norm("Kenneth Walker")


def _adjust_setup(monkeypatch, then, now):
    monkeypatch.setattr(S.D, "injuries_now", lambda: (now, "20261101T1730"))
    monkeypatch.setattr(S.D, "injuries_at", lambda when, raw=None: (then, "20261031T1400"))
    monkeypatch.setattr(S, "inactives_final", lambda team, week: False)
    monkeypatch.setattr(S, "injury_coefficients", lambda: {"lost_share": -5.0, "qb": -4.0})
    monkeypatch.setattr(S, "_share_table", lambda team, week: ({"star wr": 0.30, "slot wr": 0.10}, "starter qb", {"star wr": "WR", "slot wr": "WR"}))


def test_only_absences_new_since_the_forecast_move_a_teams_points(monkeypatch):
    then = _feed([("NE", "Slot WR", "WR", "Out", "knee")])
    now = _feed([("NE", "Slot WR", "WR", "Out", "knee"), ("NE", "Star WR", "WR", "Out", "ankle")])
    _adjust_setup(monkeypatch, then, now)
    a = S.new_absences("NE", 8, pd.Timestamp("2026-10-31T14:07Z"))
    assert a["known"] and a["lost_share"] == pytest.approx(0.30)           # the slot receiver was out when the line was set: not counted again
    assert a["points"] == pytest.approx(-1.5)
    assert [p["player"] for p in a["new_out"]] == ["Star WR"] and a["back"] == []


def test_a_starting_quarterback_ruled_out_costs_the_qb_coefficient_and_a_return_adds_it_back(monkeypatch):
    _adjust_setup(monkeypatch, _feed([]).iloc[0:0], _feed([("NE", "Starter QB", "QB", "Out", "ill")]))
    out = S.new_absences("NE", 8, pd.Timestamp("2026-10-31T14:07Z"))
    assert out["known"] is False                                             # no older snapshot: nothing is claimed
    _adjust_setup(monkeypatch, _feed([("NE", "Other", "WR", "Questionable", "x")]), _feed([("NE", "Starter QB", "QB", "Out", "ill")]))
    assert S.new_absences("NE", 8, pd.Timestamp("2026-10-31T14:07Z"))["points"] == pytest.approx(-4.0)
    _adjust_setup(monkeypatch, _feed([("NE", "Starter QB", "QB", "Out", "ill")]), _feed([("NE", "Other", "WR", "Questionable", "x")]))
    assert S.new_absences("NE", 8, pd.Timestamp("2026-10-31T14:07Z"))["points"] == pytest.approx(4.0)


def test_game_numbers_shift_by_the_home_minus_away_change_and_win_chance_follows(monkeypatch):
    base = {"gid": "NE_MIA", "week": 8, "home": "MIA", "away": "NE", "completed": False, "forecast_saved_at": "2026-10-31T14:07:00Z",
            "expected": {"margin": -7.0, "total": 45.0, "sd_m": 13.0, "sd_t": 10.0, "home_pts": 19.0, "away_pts": 26.0},
            "headline": {"p_home": 0.30, "p_label": "x"}, "props": []}
    monkeypatch.setattr(S.D, "game_detail", lambda gid: dict(base))
    monkeypatch.setattr(S.D, "_outcomes", lambda m, a, h: [])
    monkeypatch.setattr(S.D, "pmf", lambda *a, **k: [])
    pts = {"NE": -2.0, "MIA": 0.0}
    monkeypatch.setattr(S, "new_absences", lambda t, w, s: {"known": True, "points": pts[t], "new_out": [], "back": []})
    d = S.game_detail_adjusted("NE_MIA")
    assert d["expected"]["margin"] == pytest.approx(-5.0) and d["expected"]["total"] == pytest.approx(43.0)   # the away team lost 2 points
    assert d["headline"]["p_home"] > 0.30                                                                    # home chance rises
    assert d["injury_adjustment"]["saved"]["margin"] == -7.0
    pts["NE"] = 0.0
    d = S.game_detail_adjusted("NE_MIA")
    assert d["expected"]["margin"] == -7.0 and d["headline"]["p_home"] == 0.30                              # nothing new: unchanged
