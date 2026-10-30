"""Game Center API: read-only, validated, and free of invented numbers."""
import re

import pytest
from fastapi.testclient import TestClient

from lab import gamecenter_data as D
from web.server import app

client = TestClient(app)
JARGON = ["crps", "log loss", "logit", "bonferroni", "conformal", "nats", "kappa", "bootstrap", "permutation", "brier", "isotonic"]


def test_clean_makes_everything_json_safe():
    import numpy as np
    import pandas as pd
    out = D.clean({"a": np.float64("nan"), "b": np.int64(3), "c": [np.float32(1.5), float("inf")], "d": pd.Timestamp("2026-10-30", tz="UTC"), "e": np.bool_(True)})
    assert out == {"a": None, "b": 3, "c": [1.5, None], "d": "2026-10-30T00:00:00+00:00", "e": True}


def test_bad_inputs_are_rejected_not_executed():
    for path in ("/api/game/../../etc/passwd", "/api/game/2026_08_ARI_DAL; drop", "/api/game/xx", "/api/week/0", "/api/week/99", "/api/week/abc"):
        assert client.get(path).status_code in (404, 422)


def test_only_get_is_allowed():
    for method in (client.post, client.put, client.delete, client.patch):
        assert method("/api/meta").status_code in (404, 405)


def test_pmf_sums_to_one_and_peaks_at_the_mean():
    p = D.pmf(3.0, 13.0, -60, 60)
    assert abs(sum(r["p"] for r in p) - 1) < 1e-4
    assert max(p, key=lambda r: r["p"])["x"] == 3


def test_glossary_is_plain_english():
    text = " ".join(g["term"] + " " + g["text"] for g in client.get("/api/glossary").json()).lower()
    assert not [w for w in JARGON if w in text]


def test_meta_and_a_game_on_real_local_data_if_present():
    meta = client.get("/api/meta").json()
    if not meta.get("ok"):
        pytest.skip("no local games table")
    assert meta["default_week"] in meta["weeks"] and "market" in meta["reality_check"]
    games = client.get(f"/api/week/{meta['default_week']}").json()
    assert games and all(re.match(D.GID_PATTERN, g["gid"]) for g in games)
    d = client.get(f"/api/game/{games[0]['gid']}").json()
    assert d["gid"] == games[0]["gid"] and "matchup" in d
    if d.get("has_forecast") and d.get("distribution"):
        assert abs(sum(r["p"] for r in d["distribution"]["margin"]) - 1) < 1e-3
        assert 0 <= d["headline"]["p_favored"] <= 1 and d["headline"]["p_favored"] >= 0.5
        assert not [w for w in JARGON if w in (d["lean"] or {"text": ""})["text"].lower()]


def test_verify_results_script_lists_all_studies():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_results.py"
    spec = importlib.util.spec_from_file_location("verify_results", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert len(mod.STUDIES) == 7
    assert all(len(proto) == 8 and codes for _, proto, codes in mod.STUDIES)
