"""Leans: edge arithmetic, sides and sizes, the pass rule and write-once hashed files. Synthetic rows, no data files."""
import json

import numpy as np
import pandas as pd
import pytest

from lab import leans as L


def frame(rows):
    d = pd.DataFrame(rows, columns=["gid", "stat", "p_A", "p_market90", "p_marketC", "y"])
    d["season"], d["week"], d["k"], d["pid"] = 2026, 3, 50.0, "p"
    return d


def test_sides_sizes_and_the_three_edges():
    d = frame([("g1", "rec_yds", 0.60, 0.50, 0.52, 1),    # over, +10 points, medium, won
               ("g2", "rec_yds", 0.30, 0.40, 0.37, 1),    # under, 10 points, medium, lost
               ("g3", "rec_yds", 0.52, 0.50, 0.50, 1)])   # inside the 5 point threshold: no lean
    x = L.make_leans(d, "p_A")
    assert list(x["side"]) == ["over", "under"] and list(x["size"]) == ["medium", "medium"]
    assert list(x["win"]) == [1.0, 0.0]
    assert x["real"].round(3).tolist() == [0.5, -0.6]                   # win minus the price of the side taken
    assert x["clv"].round(3).tolist() == [0.02, 0.03]                   # the price moved toward each lean
    s = L.summarize(x, boot=False)
    assert s["n"] == 2 and s["stated_edge"] == pytest.approx(0.10) and s["realized_edge"] == pytest.approx(-0.05)


def test_selection_filters_and_empty_selection_is_plain():
    d = frame([("g1", "rec_yds", 0.70, 0.50, 0.55, 1), ("g2", "rush_yds", 0.20, 0.40, 0.35, 0)])
    x = L.make_leans(d, "p_A")
    assert len(L.select(x, "Rushing yards", None, None, "All", None)) == 1
    assert len(L.select(x, "All", 4, None, "All", None)) == 0
    assert L.summarize(x.iloc[0:0])["n"] == 0
    assert set(L.NOT_TESTABLE) == {"Game total", "Spread", "Moneyline", "Touchdowns"}


def test_small_samples_never_claim_an_edge():
    rng = np.random.default_rng(0)
    d = frame([(f"g{i}", "rec", 0.7, 0.5, 0.55, int(rng.random() < 0.7)) for i in range(40)])
    s = L.summarize(L.make_leans(d, "p_A"))
    assert s["finds_edge"] is False and "Too few leans" in s["note"]


def test_frozen_leans_are_write_once_and_detect_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "FROZEN", tmp_path / "f")
    monkeypatch.setattr(L, "LEDGER", tmp_path / "ledger.jsonl")
    calls = []
    monkeypatch.setattr(L, "live_leans", lambda w: calls.append(w) or {"week": w, "created": "t", "rule_sha256": "x", "leans": [{"edge": 0.1}], "no_lean": 0})
    first = L.freeze_week(9)
    again = L.freeze_week(9)
    assert again["sha256"] == first["sha256"] and calls == [9]
    path = tmp_path / "f" / "9.json"
    rec = json.loads(path.read_text())
    rec["forecast"]["leans"][0]["edge"] = 0.9
    path.write_text(json.dumps(rec))
    with pytest.raises(RuntimeError):
        L.freeze_week(9)
