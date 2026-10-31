"""NBA Game Center API: read-only, validated, and free of invented numbers."""
import re

import pytest
from fastapi.testclient import TestClient

from nba_lab import gamecenter_data as D
from web.server import app

client = TestClient(app)


def test_clean_makes_everything_json_safe():
    import numpy as np
    import pandas as pd
    out = D.clean({"a": np.float64("nan"), "b": np.int64(3), "c": [np.float32(1.5), float("inf")], "d": pd.Timestamp("2026-10-30", tz="UTC"), "e": np.bool_(True)})
    assert out == {"a": None, "b": 3, "c": [1.5, None], "d": "2026-10-30T00:00:00+00:00", "e": True}


def test_bad_inputs_are_rejected_not_executed():
    for path in ("/api/game/../../etc/passwd", "/api/game/401909893; drop", "/api/game/xx", "/api/day/2026-13-45", "/api/day/abc", "/api/day/2026-10-29x"):
        assert client.get(path).status_code in (404, 422)


def test_only_get_is_allowed():
    for method in (client.post, client.put, client.delete, client.patch):
        assert method("/api/meta").status_code in (404, 405)


def test_pmf_sums_to_one_and_peaks_at_the_mean():
    p = D.pmf(3.0, 15.0, -40, 40)
    assert abs(sum(r["p"] for r in p) - 1) < 1e-6
    assert max(p, key=lambda r: r["p"])["x"] == 3


def test_every_team_has_a_name_and_color():
    assert len(D.TEAMS) == 30 and all(re.match(r"^#[0-9a-f]{6}$", c) for _, c in D.TEAMS.values())


def test_missing_data_is_reported_not_guessed(tmp_path, monkeypatch):
    for name in ("ARCHIVES", "CACHE", "REPORTS"):
        monkeypatch.setattr(D, name, tmp_path / name)
    assert client.get("/api/meta").json()["ok"] is False
    assert client.get("/api/day/2026-10-29").json() == []
    assert client.get("/api/game/401909893").status_code == 404


def test_meta_and_a_game_on_real_local_data_if_present():
    meta = client.get("/api/meta").json()
    if not meta.get("ok"):
        pytest.skip("no local saved forecasts")
    assert meta["default_date"] in meta["dates"]
    games = client.get(f"/api/day/{meta['default_date']}").json()
    assert games and all(re.match(D.GID_PATTERN, g["gid"]) for g in games)
    d = client.get(f"/api/game/{games[0]['gid']}").json()
    assert d["gid"] == games[0]["gid"] and "matchup" in d
    if d.get("has_forecast"):
        assert d["headline"]["p_favored"] >= 0.5 and len(d["models"]) == 6
        assert all(s["name"] != "Betting market" for s in d["sources"])
    if d.get("distribution"):
        assert abs(sum(r["p"] for r in d["distribution"]["margin"]) - 1) < 1e-6
