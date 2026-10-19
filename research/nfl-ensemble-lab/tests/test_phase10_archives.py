import json

import pandas as pd
import pytest

from lab.archive10 import save, temporal
from lab.market81 import archive_local_markets, local_market_rows
from lab.props.lines import archive_lines, archived_lines, player_map


@pytest.fixture
def quotes():
    return {"generated_at": "2026-10-01T10:00:00Z", "games_raw": [{
        "id": "event", "home_team": "San Francisco 49ers", "away_team": "Chicago Bears",
        "commence_time": "2026-10-02T00:15:00Z", "bookmakers": [{"key": "fixture",
        "last_update": "2026-10-01T09:59:00Z", "markets": [{"key": "spreads", "outcomes": [
            {"name": "San Francisco 49ers", "point": -6.5, "price": -110}]}]}]}],
        "period_quotes": [{"match_id": "event", "home_team": "San Francisco 49ers",
        "away_team": "Chicago Bears", "source": "fixture", "market": "totals", "period_key": "1H",
        "side": "Over", "line": 23.5, "price": -110, "updatedAt": "2026-10-01T09:58:00Z",
        "kickoff": "2026-10-02T00:15:00Z"}], "props": [{"player": "Test Player", "market": "rec_yds",
        "line": 50.5, "bookKey": "fixture", "updatedAt": "2026-10-01T09:59:00Z",
        "kickoff": "2026-10-02T00:15:00Z"}]}


def test_markets_preserve_sign_period_and_immutable_change_only(tmp_path, quotes):
    rows = local_market_rows(quotes)
    assert next(r for r in rows if r["period"] == "FULL")["point"] == -6.5
    assert next(r for r in rows if r["period"] == "1H")["point"] == 23.5
    meta = {"source": "fixture", "available_at": "2026-10-01T10:00:00Z"}
    a = archive_local_markets(quotes, meta, root=tmp_path)
    assert a["new"]
    before = (tmp_path / "market" / a["file"].split("\\")[-1]).read_bytes()
    assert not archive_local_markets(quotes, meta | {"commit": "another"}, root=tmp_path)["new"]
    quotes["period_quotes"][0]["line"] = 24.5
    assert archive_local_markets(quotes, meta, root=tmp_path)["new"]
    assert len(list((tmp_path / "market").glob("*.json"))) == 2
    assert before in [p.read_bytes() for p in (tmp_path / "market").glob("*.json")]


def test_t1_requires_quote_and_observation_before_kickoff():
    assert temporal("2026-10-01", "2026-10-01T12:00Z", "2026-10-02")["timestamp_class"] == "T1"
    for q, a in ((None, "2026-10-01"), ("2026-10-01", "2026-10-03"),
                 ("2026-10-01T13:00Z", "2026-10-01T12:00Z")):
        assert not temporal(q, a, "2026-10-02")["pregame_verified"]


def test_props_exact_identity_and_unknowns(tmp_path, quotes):
    players = pd.DataFrame({"gsis_id": ["p1", "p2", "p3"],
                            "display_name": ["Test Player", "Same Name", "Same Name"]})
    mapping = player_map(players)
    assert "samename" not in mapping
    quotes["props"].append(quotes["props"][0] | {"player": "Unknown Player", "market": "atd"})
    quotes["props"].append({"market": "not-supported"})
    meta = {"source": "fixture", "available_at": "2026-10-01T10:00:00Z"}
    a = archive_lines(quotes, meta, mapping, root=tmp_path)
    assert a["unmatched"] == ["Unknown Player"]
    assert a["unknown_markets"] == ["not-supported"]
    d = archived_lines(root=tmp_path, asof="2026-10-01T11:00Z")
    assert d["pregame_verified"].all()
    assert d.loc[d["player"] == "Test Player", "gsis_id"].item() == "p1"
    assert archived_lines(root=tmp_path, asof="2026-09-30T00:00Z").empty


def test_explicit_team_and_period_labels_never_become_full_game_lines(quotes):
    from lab.props.lines import line_rows
    quotes["props"][0].update(player="Test Player (CHI) - 1H", market="rec_yds_1h")
    rows, unknown = line_rows(quotes, {"testplayer": "p1"})
    assert unknown == []
    assert rows[0]["gsis_id"] == "p1"
    assert rows[0]["period"] == "1H"
    assert rows[0]["player_raw"] == "Test Player (CHI) - 1H"


def test_weather_archives_every_pull(tmp_path, monkeypatch):
    from lab import archive10, geo, prospective
    original = save
    monkeypatch.setattr(archive10, "save", lambda *a, **kw: original(*a, **kw, root=tmp_path))
    forecast = {"hourly": {"time": ["2026-10-20T12:00"], "temperature_2m": [10],
                          "wind_speed_10m": [5], "precipitation_probability": [20]}}
    monkeypatch.setattr(prospective.sources, "_fetch", lambda *a, **kw: (json.dumps(forecast).encode(), {}))
    monkeypatch.setattr(geo, "site_key", lambda *a: next(iter(geo.STADIUMS)))
    games = pd.DataFrame([{"game_id": "fixture", "kickoff_utc": pd.Timestamp("2026-10-20T12:00Z"), "roof_type": "outdoors"}])
    for _ in range(2):
        assert prospective.fetch_weather(games)["fixture"]["status"] == "ok"
    paths = list((tmp_path / "weather").glob("*.json"))
    assert len(paths) == 2
    record = json.loads(paths[0].read_text())
    assert record["context_only"] is True
    assert record["valid_time"] == forecast["hourly"]["time"]
    assert record["forecast_retrieved_at"]
