import json
import os
import stat

import numpy as np
import pandas as pd

from lab import market81 as M
from lab import scheduler as S


def test_odds_conversion_and_novig_methods():
    p = M.american_to_prob([-150, 130])
    assert np.allclose(p, [0.6, 100 / 230])
    for m in ("multiplicative", "additive", "power"):
        h = M.novig(np.array([p[0]]), np.array([p[1]]), m)[0]
        a = M.novig(np.array([p[1]]), np.array([p[0]]), m)[0]
        assert 0.5 < h < 0.6 and abs(h + a - 1) < 1e-6, m          # margin removed, favourite stays the favourite


SBR_HTML = """<table><tr><th>Date</th><th>Rot</th><th>VH</th><th>Team</th><th>1st</th><th>2nd</th><th>3rd</th><th>4th</th><th>Final</th>
<th>Open</th><th>Close</th><th>ML</th><th>2H</th></tr>
<tr><td>909</td><td>451</td><td>V</td><td>Dallas</td><td>7</td><td>9</td><td>10</td><td>3</td><td>29</td><td>52.5</td><td>52.5</td><td>375</td><td>27</td></tr>
<tr><td>909</td><td>452</td><td>H</td><td>TampaBay</td><td>7</td><td>14</td><td>7</td><td>3</td><td>31</td><td>7</td><td>10</td><td>-450</td><td>2</td></tr>
</table>"""


def test_sbr_parsing_spread_total_and_side(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "MKT_RAW", tmp_path)
    (tmp_path / "sbr_2021.html").write_text(SBR_HTML, encoding="utf-8")
    games = pd.DataFrame({"game_id": ["2021_01_DAL_TB"], "season": [2021], "home_team": ["TB"], "away_team": ["DAL"],
                          "kickoff_utc": [pd.Timestamp("2021-09-10 00:20", tz="UTC")]})
    d = M.sbr_season(2021, games)
    r = d.iloc[0]
    assert r["game_id"] == "2021_01_DAL_TB" and r["sbr_home_spread_open"] == 7 and r["sbr_home_spread_close"] == 10   # home favoured
    assert r["sbr_total_open"] == 52.5 and r["sbr_home_ml_close"] == -450 and r["timestamp_class_open"].startswith("T2")


SB = {"events": [{"id": "1", "date": "2026-10-18T17:00Z", "competitions": [{
    "competitors": [{"homeAway": "home", "team": {"abbreviation": "ATL"}}, {"homeAway": "away", "team": {"abbreviation": "CHI"}}],
    "odds": [{"provider": {"name": "DraftKings"}, "details": "CHI -1.5", "spread": 1.5, "overUnder": 52.5,
              "moneyline": {"home": {"open": {"odds": "+140"}, "close": {"odds": "+100"}}, "away": {"open": {"odds": "-166"}, "close": {"odds": "-120"}}},
              "pointSpread": {"home": {"open": {"line": "+3"}, "close": {"line": "+1.5"}}}, "total": {"over": {"open": {"line": "o51.5"}}}}]}]}]}


def test_espn_odds_archive_is_append_only_and_read_only(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "MKT_ARCHIVE", tmp_path)
    sb = dict(SB, retrieved_at="2026-10-17T18:54:13+00:00")
    r1 = M.archive_espn_odds(sb)
    r2 = M.archive_espn_odds(sb)                                      # identical content -> nothing new
    assert r1["new"] and not r2["new"] and len(list(tmp_path.glob("*.json"))) == 1
    f = next(tmp_path.glob("*.json"))
    assert not (os.stat(f).st_mode & stat.S_IWRITE)
    row = json.loads(f.read_text())["rows"][0]
    assert row["home_ml_open"] == "+140" and row["home_ml_close"] == "+100" and row["provider"] == "DraftKings"
    assert M.archive_espn_odds({"events": "broken"})["ok"] is False     # never raises


def test_research_hook_only_after_forecasts_and_never_in_mocked_ticks(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(S, "_post_forecast_research", lambda due, written: called.append(1) or {})
    monkeypatch.setattr(S, "acquire_lock", lambda: True)
    monkeypatch.setattr(S, "release_lock", lambda: None)
    monkeypatch.setattr(S, "_append", lambda *a, **k: None)
    monkeypatch.setattr(S, "_read", lambda *a, **k: [])
    monkeypatch.setattr(S, "event_status", lambda: {})
    monkeypatch.setattr(S, "PLAN", tmp_path / "plan.json")
    now = pd.Timestamp("2026-10-18 12:00", tz="UTC")
    plan = pd.DataFrame([{"event_id": "daily:x", "kind": "daily", "stage": None, "game_id": None, "time_utc": now - pd.Timedelta(minutes=1),
                          "deadline_utc": now + pd.Timedelta(hours=1), "action": "live"}])
    monkeypatch.setattr(S, "build_plan", lambda *a, **k: plan)
    monkeypatch.setattr(S, "_supersede", lambda *a, **k: [])
    S.tick(now=now, progress=lambda m: None, actions={"live": lambda p: {}}, schedule=pd.DataFrame())
    assert called == []                                                 # mocked actions: research hook skipped


def test_post_forecast_research_never_raises(monkeypatch):
    import lab.archive_scheduler10 as MM
    monkeypatch.setattr(MM, "collect_local", lambda: (_ for _ in ()).throw(RuntimeError("local archive unavailable")))
    monkeypatch.setattr(MM, "collect_context", lambda games: {})
    r = S._post_forecast_research(pd.DataFrame({"event_id": ["e"], "action": ["live"]}), {})
    assert r["market"]["ok"] is False and "local archive unavailable" in r["market"]["reason"]


def test_drive_sim_evaluate_empty_archive(tmp_path, monkeypatch):
    from lab import scoring81
    monkeypatch.setattr(scoring81, "ARCH", tmp_path)
    ev = scoring81.evaluate()
    assert ev.empty
