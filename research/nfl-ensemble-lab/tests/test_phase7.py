import numpy as np
import pandas as pd
import pytest

from lab import extra_sources as X
from lab import features as F
from lab import live

HTML = """<h1>Official Latest NFL Injury Report for Players - Week 6 of the 2026 Season | NFL.com</h1>
<div class="d3-o-section-sub-title"><span>Ravens</span></div><div><table class="d3-o-table"><thead><tr><th>Player</th><th>Position</th>
<th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr></thead><tbody>
<tr><td scope="row"><a href="/players/x/"> Lamar Jackson </a></td><td>QB</td><td>Ankle</td><td>Did Not Participate In Practice</td><td>Out</td></tr>
<tr><td scope="row"><a href="/players/y/"> Odell Beckham Jr. </a></td><td>WR</td><td></td><td>Full Participation in Practice</td><td></td></tr>
</tbody></table></div>
<div class="d3-o-section-sub-title"><span>Browns</span></div><div><table><thead><tr><th>Player</th></tr></thead><tbody>
<tr><td><a> Deshaun Watson </a></td><td>QB</td><td>Knee</td><td>Limited Participation in Practice</td><td>Questionable</td></tr>
</tbody></table></div>"""


def test_parse_nflcom_and_gsis_mapping():
    rep, season, week = X.parse_nflcom(HTML)
    assert (season, week) == (2026, 6) and len(rep) == 3
    assert rep.set_index("full_name").loc["Lamar Jackson", ["team", "report_status"]].tolist() == ["BAL", "Out"]
    assert rep.set_index("full_name").loc["Odell Beckham Jr.", "report_status"] is None
    roster = pd.DataFrame({"season": 2026, "week": [6, 6, 6], "team": ["BAL", "BAL", "CLE"],
                           "full_name": ["Lamar Jackson", "Odell Beckham", "Deshaun Watson"], "gsis_id": ["A", "B", "C"]})
    m = X.map_gsis(rep, roster).set_index("full_name")["gsis_id"]
    assert m.to_dict() == {"Lamar Jackson": "A", "Odell Beckham Jr.": "B", "Deshaun Watson": "C"}   # suffixes normalised


def _row(**kw):
    base = {"week": 6, "home_team": "CHI", "away_team": "BAL", "away_qb_projected_id": "H", "away_qb_projected_out": 0,
            "away_qb_questionable": 0, "away_qb_name": "Lamar Jackson", "away_qb7_projected_id": "H"}
    return pd.Series(base | kw)


def test_qb_certainty_ignores_officially_out_alternative():
    names = {"H": "Tyler Huntley"}
    qb1 = {"BAL": ("Lamar Jackson", "L")}
    off = {("BAL", "Lamar Jackson"): "Out", "_week": 6}
    lab_, note = live._qb_certainty(_row(), "away", qb1, pd.DataFrame(), names, off)
    assert lab_ == "consistent" and "lists him Out" in note
    # a report only covers its own week: next week the static sources still conflict
    lab2, _ = live._qb_certainty(_row(week=7), "away", qb1, pd.DataFrame(), names, off)
    assert lab2 == "uncertain"
    lab3, _ = live._qb_certainty(_row(), "away", qb1, pd.DataFrame(), names, {})
    assert lab3 == "uncertain"


def _qb_history():
    k = pd.Timestamp("2026-09-10", tz="UTC")
    games = pd.DataFrame({"game_id": [f"2026_0{i}_CHI_OPP" for i in range(1, 6)], "season": 2026,
                          "home_team": "CHI", "away_team": "OPP", "kickoff_utc": [k + pd.Timedelta(days=7 * i) for i in range(5)]})
    qb = pd.DataFrame({"game_id": games["game_id"][:4].repeat(1).tolist(), "team": "CHI",
                       "qb_id": ["S", "S", "S", "B"], "qb_dropbacks": [40, 38, 41, 35]})
    return games, qb


@pytest.mark.parametrize("status,expect,returning", [
    ({("2026_05_CHI_OPP", "CHI", "S"): "Questionable"}, "S", 1),     # listed and not Out -> returning starter
    ({}, "B", 0),                                                    # not on the report -> keep last starter
    ({("2026_05_CHI_OPP", "CHI", "S"): "Out"}, "B", 0),              # listed Out -> keep last starter
])
def test_qb_v2_returning_starter_rule(status, expect, returning):
    games, qb = _qb_history()
    t = F.project_starters_v2(games, qb, status, covered={("2026_05_CHI_OPP", "CHI")}).set_index(["game_id", "team"])
    r = t.loc[("2026_05_CHI_OPP", "CHI")]
    assert r["qb7_projected_id"] == expect and r["qb7_returning"] == returning


def test_qb_v2_no_returning_without_verified_report():
    games, qb = _qb_history()
    t = F.project_starters_v2(games, qb, {("2026_05_CHI_OPP", "CHI", "S"): "Questionable"}, covered=set()).set_index(["game_id", "team"])
    assert t.loc[("2026_05_CHI_OPP", "CHI"), "qb7_projected_id"] == "B"


def test_snap_model_recovers_player_and_is_asof():
    from lab.snap_model import SAPM
    rng = np.random.default_rng(1)
    n_g = 120
    kick = pd.Timestamp("2018-09-01", tz="UTC") + pd.to_timedelta(np.arange(n_g), unit="D")
    rows, shares = [], []
    for i in range(n_g):
        star = i % 2 == 0
        gid = f"g{i}"
        rows.append({"game_id": gid, "team": "A", "opp": "B", "home": 1.0, "kickoff_utc": kick[i], "season": 2018, "plays": 60,
                     "epa_pp": 0.25 * star + rng.normal(0, 0.05)})
        shares += [{"game_id": gid, "team": "A", "gsis_id": "star" if star else "backup", "offense_pct": 1.0, "defense_pct": 0.0},
                   {"game_id": gid, "team": "B", "gsis_id": "d1", "offense_pct": 0.0, "defense_pct": 1.0}]
    rows, shares = pd.DataFrame(rows), pd.DataFrame(shares)
    cut = pd.DataFrame({"season": [2018], "week": [1], "cutoff_utc": [kick[60]]})
    f1 = SAPM(rows, shares, 1.0).fit_schedule(cut, progress=lambda m: None)[(2018, 1)]
    m = SAPM(rows, shares, 1.0)
    assert f1["off"][m.pid["star"]] - f1["off"][m.pid["backup"]] > 0.15
    later = rows.copy()
    later.loc[later["kickoff_utc"] >= kick[60], "epa_pp"] = 9.0          # games at/after the cutoff must not matter
    later.loc[later["kickoff_utc"] >= kick[60], "plays"] = 5             # including their play counts (penalty scale)
    f2 = SAPM(later, shares, 1.0).fit_schedule(cut, progress=lambda m: None)[(2018, 1)]
    assert np.allclose(f1["off"], f2["off"], atol=1e-6)


def test_source_health_log(tmp_path, monkeypatch):
    monkeypatch.setattr(X, "HEALTH", tmp_path / "h.jsonl")
    X.log_health("NFL.com injury report", True, 10)
    X.log_health("NFL.com injury report", False, error="timeout")
    h = X.source_health().set_index("source").loc["NFL.com injury report"]
    assert not h["ok"] and h["failures_24h"] == 1 and pd.notna(h["last_ok"]) and h["error"] == "timeout"


def test_phase7_groups_do_not_touch_champion_inputs():
    cols = ["diff_qb_eff", "diff_qb7_eff", "home_qb7_returning", "diff_p7s_off_proj", "p7smx_net_expected_epa", "diff_p7s_staleness_days"]
    g = F.feature_groups(cols)
    assert set(g[F.P7_QB]) == {"diff_qb7_eff", "home_qb7_returning"}
    assert set(g[F.P7_SNAP]) == {"diff_p7s_off_proj", "p7smx_net_expected_epa"}
    for name in F.DEFAULT_GROUPS:
        assert not any("qb7" in c or "p7s" in c for c in g.get(name, []))
