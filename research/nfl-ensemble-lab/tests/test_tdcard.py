"""Touchdown card and Kalshi market value: zone work, windows, name and team matching, edge arithmetic. Synthetic inputs, plus one check on real local data."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from lab import tdcard as T
from lab import tdmarket as M
from web.server import app


def _touches():
    rows = []
    for wk in range(1, 9):                      # one team, eight weeks; one back (RB1) and one receiver (WR1)
        for i, yl in enumerate((3, 12, 30, 60)):
            rows.append({"season": 2026, "week": wk, "game_id": f"g{wk}", "team": "AAA", "opp": "BBB", "pid": "RB1", "kind": 0, "yl": yl,
                         "td": int(yl == 3), "yards": 4.0, "complete": 1, "zone": int(np.select([yl <= 5, yl <= 20, yl <= 40], [0, 1, 2], 3)), "pos": "RB", "xtd": 0.1})
        rows.append({"season": 2026, "week": wk, "game_id": f"g{wk}", "team": "AAA", "opp": "BBB", "pid": "WR1", "kind": 1, "yl": 8, "td": 0, "yards": 9.0,
                     "complete": 1, "zone": 1, "pos": "WR", "xtd": 0.2})
    return pd.DataFrame(rows)


def test_games_window_keeps_only_the_last_n_games_before_the_week_and_counts_zones():
    pg = T._games(_touches(), 2026, 8, 5)
    assert sorted(pg["week"].unique()) == [3, 4, 5, 6, 7]                       # five games before week 8
    rb = pg[pg["pid"] == "RB1"]
    assert list(rb["carries"]) == [4.0] * 5 and rb["gl_carries"].sum() == 5 and rb["rz_carries"].sum() == 10 and rb["rush_td"].sum() == 5
    assert rb["xtd"].iloc[0] == pytest.approx(0.4) and rb["role_rank"].eq(1).all()
    wr = pg[pg["pid"] == "WR1"]
    assert wr["targets"].sum() == 5 and wr["rz_targets"].sum() == 5 and wr["role_rank"].eq(1).all()
    assert sorted(T._games(_touches(), 2026, 3, 5)["week"].unique()) == [1, 2]   # early in the season: fewer games, never the week itself


def test_ordinals_and_role_names():
    assert [T.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]
    assert T._role_name("RB", 1) == "Lead back" and T._role_name("WR", 3) == "WR3" and T._role_name("WR", 4) is None and T._role_name("K", 1) is None


def test_kalshi_names_and_teams_are_matched_the_way_the_lab_names_them():
    assert M.name_key("Matt Hibner") == ("m", "hibner") and M.name_key("Kenneth Walker III") == ("k", "walker") and M.name_key("Omar Cooper Jr.") == ("o", "cooper")
    assert M.name_key("D'Andre Swift") == ("d", "swift") and M.name_key("Jaxon Smith-Njigba") == ("j", "njigba")   # hyphenated names key on the last piece on both sides
    assert M.player_team("26NOV01ATLTB", "ATLBROBINSON7") == "ATL" and M.player_team("26NOV01ATLTB", "TBBMAYFIELD6") == "TB"
    assert M.player_team("26NOV01PHIWAS", "WASBSINNOTT82") == "WAS" and M.player_team("26NOV01CHISEA", "SEAZCHARBONNET26") == "SEA"
    assert M.player_team("26NOV01CHISEA", "NONEXYZ") is None


def test_edge_is_our_chance_minus_the_ask_minus_the_fee_and_wide_markets_have_no_price():
    v = M.verdict(0.50, 0.38, 0.40)
    assert v["edge"] == pytest.approx(0.10) and v["edge_after_fee"] == pytest.approx(0.10 - 0.07 * 0.4 * 0.6) and v["value"] is True
    assert M.verdict(0.30, 0.38, 0.40)["edge_after_fee"] < -0.04 and M.verdict(0.30, 0.38, 0.40)["label"] == "Price is above our number"
    assert M.verdict(0.11, 0.05, 0.06)["value"] is False                          # a big gap on a tiny chance is not flagged (chance under 12%)
    assert M.verdict(0.5, 0.2, 0.5)["label"] == "No real price" and M.verdict(0.5, None, 0.3)["edge"] is None and M.verdict(0.5, 0.2, None)["edge"] is None


def test_routes_validate_their_inputs(monkeypatch):
    c = TestClient(app)
    assert c.get("/api/tdcard/2026_08_TEN_CIN?team=lower&player=Someone").status_code == 422
    assert c.get("/api/tdcard/2026_08_TEN_CIN?team=TEN").status_code == 422
    assert c.get("/api/tdmarket/99").status_code == 422
    monkeypatch.setattr(M, "week_market", lambda w: (_ for _ in ()).throw(RuntimeError("down")))
    assert c.get("/api/tdmarket/8").status_code == 502
