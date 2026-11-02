"""Leans: edge arithmetic, ladder collapse, executable prices and fees, design effect, Holm and write-once hashed files. Synthetic rows, no data files."""
import json

import numpy as np
import pandas as pd
import pytest

from lab import leans as L


def frame(rows):
    d = pd.DataFrame(rows, columns=["gid", "pid", "k", "stat", "p_A", "p_market90", "p_marketC", "y", "bid90", "ask90", "bidC", "askC"])
    d["season"], d["week"], d["key"], d["executable"] = 2026, 3, 202603, True
    return d


def test_sides_sizes_and_the_three_edges_at_mid():
    d = frame([("g1", "a", 50, "rec_yds", 0.60, 0.50, 0.52, 1, 0.48, 0.52, 0.5, 0.54),    # over, 10 points, medium, won
               ("g2", "b", 50, "rec_yds", 0.30, 0.40, 0.37, 1, 0.38, 0.42, 0.35, 0.39),   # under, 10 points, medium, lost
               ("g3", "c", 50, "rec_yds", 0.52, 0.50, 0.50, 1, 0.48, 0.52, 0.48, 0.52)])  # inside the 5 point threshold
    x = L.make_leans(d, "p_A", "mid")
    assert list(x["side"]) == ["over", "under"] and list(x["size"]) == ["medium", "medium"]
    assert x["real"].round(3).tolist() == [0.5, -0.6]
    assert x["clv"].round(3).tolist() == [0.02, 0.03]


def test_a_ladder_counts_once_at_its_largest_edge():
    d = frame([("g1", "a", 40, "rec_yds", 0.70, 0.60, 0.6, 1, 0.58, 0.62, 0.6, 0.62),
               ("g1", "a", 50, "rec_yds", 0.60, 0.40, 0.4, 1, 0.38, 0.42, 0.38, 0.42),     # biggest gap on this ladder
               ("g1", "a", 60, "rec_yds", 0.50, 0.35, 0.3, 0, 0.33, 0.37, 0.3, 0.34)])
    x = L.make_leans(d, "p_A", "mid")
    assert len(x) == 1 and x["k"].iloc[0] == 50


def test_executable_prices_fee_and_thin_markets():
    d = frame([("g1", "a", 50, "rec", 0.70, 0.50, 0.5, 1, 0.48, 0.54, 0.52, 0.56),         # over: buy at the ask 0.54
               ("g2", "b", 50, "rec", 0.30, 0.50, 0.5, 0, 0.46, 0.52, 0.40, 0.44)])        # under: pay 1 - bid = 0.54
    d.loc[1, "executable"] = False
    x = L.make_leans(d, "p_A", "exec")
    assert len(x) == 1                                                                      # the thin one is dropped
    assert x["price"].iloc[0] == pytest.approx(0.54)
    assert x["fee"].iloc[0] == pytest.approx(0.07 * 0.54 * 0.46)
    assert x["real"].iloc[0] == pytest.approx(1 - 0.54 - 0.07 * 0.54 * 0.46)
    assert x["clv"].iloc[0] == pytest.approx(0.52 - 0.54)                                   # sell at the close bid, bought at the ask
    assert L.dropped_share(d, "p_A")["dropped_thin"] == pytest.approx(0.5)


def test_design_effect_grows_when_leans_in_a_game_move_together():
    gid = np.repeat(np.arange(20), 5)
    shared = np.repeat(np.random.default_rng(1).normal(size=20), 5)
    alone = np.random.default_rng(2).normal(size=100)
    assert L._icc(shared + 0.1 * alone, gid) > 0.8
    assert L._icc(alone, gid) < 0.2


def test_holm_and_small_samples():
    h = L.holm({"a": 0.01, "b": 0.04, "c": 0.5})
    assert h["a"] == pytest.approx(0.03) and h["b"] == pytest.approx(0.08) and h["c"] == pytest.approx(0.5)
    rng = np.random.default_rng(0)
    d = frame([(f"g{i}", "a", 50, "rec", 0.7, 0.5, 0.55, int(rng.random() < 0.7), 0.48, 0.52, 0.5, 0.54) for i in range(40)])
    s = L.summarize(L.make_leans(d, "p_A", "mid"))
    assert "Too few leans" in s["note"] and s["effective_n"] <= s["n"]


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
