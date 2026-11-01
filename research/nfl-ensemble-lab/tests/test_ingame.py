import numpy as np
import pandas as pd
import pytest

from lab import ingame as G
from lab import ingame_feed as F


def _params():
    p = G.Params()
    for fam in G.FAMILIES:
        p.pool[fam] = np.array([0, 0, 5, 8, 12, 20.0])
        p.pool_catch[fam] = 0.65
    p.vol_beta = {"pass": np.array([20.0, 0.0, 0.0, 0.0]), "rush": np.array([25.0, 0.0, 0.0, 0.0])}
    p.vol_theta = {"pass": 50.0, "rush": 50.0}
    return p


def _state(**kw):
    base = dict(fam="rec", pre_O=6.0, pre_share=0.25, pre_ypo=7.0, pre_cr=0.65, O=0, Y=0.0, C=0.0, A=0, t=0.0, d=0.0, pre_vol=30.0)
    base.update(kw)
    return G.PlayerState(**base)


def test_crps_of_a_two_point_ensemble_is_known():
    assert G.crps_samples(np.array([0.0, 2.0]), 1.0) == pytest.approx(0.5)
    assert G.crps_samples(np.array([3.0, 3.0, 3.0]), 3.0) == pytest.approx(0.0)


def test_volume_fit_recovers_a_planted_rule():
    rng = np.random.default_rng(0)
    n = 4000
    rho = rng.uniform(0.1, 1, n)
    pre, d = rng.uniform(20, 40, n), rng.uniform(-14, 14, n)
    y = rng.poisson(rho * (3 + 0.5 * pre - 0.2 * d))
    p = G.Params()
    G.fit_volume(pd.DataFrame({"rho": rho, "pre": pre, "d": d, "y": y}), "pass", p)
    lead, trail = G.volume_mean(p, "pass", 1800.0, 30.0, 10.0), G.volume_mean(p, "pass", 1800.0, 30.0, -10.0)
    assert abs((trail - lead) - 2.0) < 0.3        # 0.2 attempts per point of score, 20 points apart, half a game left


def test_nothing_left_to_play_means_the_final_stat_is_what_he_has():
    p = _params()
    out = G.predict_player(p, _state(O=7, Y=64.0, C=5.0, A=31, t=3600.0), 200)
    assert np.all(out["yards"] == 64.0) and np.all(out["catches"] == 5.0)


def test_a_player_with_no_targets_late_loses_share_and_a_busy_one_gains():
    p = _params()
    p.kappa["rec"] = 10.0
    quiet = G.role_check(p, _state(O=0, A=25, t=1800.0))
    busy = G.role_check(p, _state(O=14, A=25, t=1800.0))
    assert quiet["share_post"] < 0.25 < busy["share_post"]
    assert quiet["p_lower"] > 0.9 and busy["p_higher"] > 0.8
    assert G.role_check(p, _state(O=6, A=25, t=1800.0))["p_lower"] < 0.5


def test_the_update_moves_the_mean_toward_what_has_been_seen():
    p = _params()
    base = G.predict_player(p, _state(), 600, 1)["yards"].mean()
    hot = G.predict_player(p, _state(O=12, Y=140.0, C=9.0, A=25, t=1800.0), 600, 1)["yards"].mean()
    cold = G.predict_player(p, _state(O=0, Y=0.0, C=0.0, A=25, t=1800.0), 600, 1)["yards"].mean()
    assert cold < base < hot


def test_the_split_of_the_change_adds_up():
    p = _params()
    d = G.decompose(p, _state(O=9, Y=70.0, C=6.0, A=22, t=1500.0, d=-10.0))
    assert float(d["script"] + d["role"] + d["luck_and_efficiency"]) == pytest.approx(float(d["updated"] - d["pre"]))


def test_only_role_changes_are_warned():
    p = _params()
    rows = [{"team": "A", "name": "quiet", "team_attempts": 25, "p_lower": 0.99, "p_higher": 0.0},
            {"team": "A", "name": "lucky", "team_attempts": 25, "p_lower": 0.1, "p_higher": 0.1},
            {"team": "A", "name": "early", "team_attempts": 5, "p_lower": 0.99, "p_higher": 0.0}]
    assert [w["name"] for w in F.warnings(rows)] == ["quiet"]


def test_baselines_use_only_earlier_games():
    rows = []
    for i in range(12):
        gid = f"g{i}"
        for n in range(5):
            rows.append({"gid": gid, "season": 2024, "week": i + 1, "team": "AAA", "t": 100.0 * n, "kind": "pass", "passer": "qb", "player": "wr",
                         "yards": 8.0, "pyards": 8.0, "catch": 1.0, "diff": 0.0, "ep": 0.0, "down": 1, "yl": 50})
        rows.append({"gid": gid, "season": 2024, "week": i + 1, "team": "AAA", "t": 900.0, "kind": "rush", "passer": None, "player": "rb",
                     "yards": 4.0, "pyards": 0.0, "catch": 0.0, "diff": 0.0, "ep": 0.0, "down": 1, "yl": 50})
    e = pd.DataFrame(rows)
    games = pd.DataFrame({"gid": [f"g{i}" for i in range(12)], "season": 2024, "week": range(1, 13)})
    tv = G.team_volume(e, games)
    pool = {f: np.array([5.0]) for f in G.FAMILIES}
    pc = {f: 0.6 for f in G.FAMILIES}
    me = {f: 10.0 for f in G.FAMILIES}
    b1 = G.baselines(e, tv, pool, pc, me, 10.0)["rec"].set_index("gid")
    e2 = e.copy()
    e2.loc[e2["gid"] == "g9", "yards"] = 100.0           # a huge game
    b2 = G.baselines(e2, G.team_volume(e2, games), pool, pc, me, 10.0)["rec"].set_index("gid")
    assert b1.loc["g9", "ypo"] == pytest.approx(b2.loc["g9", "ypo"]) and b1.loc["g9", "share"] == pytest.approx(b2.loc["g9", "share"])
    assert b2.loc["g10", "ypo"] > b1.loc["g10", "ypo"]    # the next game does see it


def test_parse_reads_a_summary_and_leaves_missing_fields_empty():
    raw = {"header": {"competitions": [{"id": "1", "status": {"period": 3, "displayClock": "5:30", "type": {"state": "in", "completed": False}},
                                        "competitors": [{"homeAway": "home", "score": "10", "team": {"abbreviation": "DET", "id": "8"}},
                                                        {"homeAway": "away", "score": "13", "team": {"abbreviation": "MIN", "id": "16"}}]}]},
           "drives": {}, "boxscore": {"players": [{"team": {"abbreviation": "DET"}, "statistics": [
               {"name": "passing", "labels": ["C/ATT", "YDS"], "athletes": [{"athlete": {"displayName": "Jared Goff", "id": "1"}, "stats": ["14/22", "170"]}]},
               {"name": "receiving", "labels": ["REC", "YDS", "TGTS"], "athletes": [{"athlete": {"displayName": "A", "id": "2"}, "stats": ["4", "40", "6"]}]}]}]}}
    s = F.parse(raw)
    assert s["elapsed"] == 2 * 900 + (900 - 330) and s["score"] == {"home": 10, "away": 13}
    assert s["possession"] is None and s["down"] is None and s["yardline_100"] is None      # not shown by the feed: not invented
    assert s["team_attempts"]["DET"]["pass"] == 22 and s["players"][("DET", "A")]["targets"] == 6.0


def test_freeze_is_write_once_and_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "FROZEN", tmp_path / "frozen")
    monkeypatch.setattr(F, "LEDGER", tmp_path / "ledger.jsonl")
    detail = {"away": "A", "home": "B", "week": 8, "forecast_saved_at": "x", "expected": {"margin": 3.0}, "headline": {}, "kickoff_utc": "2099-01-01T00:00:00Z",
              "props": [{"player": "P", "team": "B", "stat": "Receiving yards", "typical": 50.0}]}
    monkeypatch.setattr(F.S, "game_detail_adjusted", lambda gid, with_props=False: detail)
    r1 = F.freeze("g1")
    assert r1["before_kickoff"] is True
    detail["props"][0]["typical"] = 99.0                    # later change to the app's number
    r2 = F.freeze("g1")
    assert r2["projection"]["props"][0]["typical"] == 50.0 and r2["sha256"] == r1["sha256"]
    path = tmp_path / "frozen" / "g1.json"
    path.write_text(path.read_text().replace("50.0", "51.0"), encoding="utf-8")
    with pytest.raises(RuntimeError):
        F.freeze("g1")


def test_a_finished_game_has_its_full_clock_and_quarterback_share_rises_are_not_warned():
    raw = {"header": {"competitions": [{"id": "1", "status": {"period": 4, "displayClock": "0:00", "type": {"state": "post", "completed": True}},
                                        "competitors": [{"homeAway": "home", "score": "20", "team": {"abbreviation": "DET", "id": "8"}},
                                                        {"homeAway": "away", "score": "17", "team": {"abbreviation": "MIN", "id": "16"}}]}]}, "drives": {}, "boxscore": {"players": []}}
    assert F.parse(raw)["elapsed"] == 3600.0
    raw["header"]["competitions"][0]["status"]["displayClock"] = "Final"
    assert F.parse(raw)["elapsed"] == 3600.0
    qb = {"team": "A", "name": "qb", "fam": "pass", "team_attempts": 30, "p_lower": 0.0, "p_higher": 0.99}
    assert F.warnings([qb]) == [] and len(F.warnings([{**qb, "fam": "rec"}])) == 1
