"""Leans: edge arithmetic, ladder collapse, fair-odds market numbers, design effect, Holm and write-once hashed files. Synthetic rows, no data files."""
import json

import numpy as np
import pandas as pd
import pytest

from lab import leans as L


def frame(rows):
    d = pd.DataFrame(rows, columns=["gid", "pid", "k", "stat", "p_A", "p_market90", "p_marketC", "y"])
    d["m_use"] = d["p_market90"]
    d["season"], d["week"], d["key"] = 2026, 3, 202603
    return d


def test_sides_sizes_and_the_three_edges():
    d = frame([("g1", "a", 50, "rec_yds", 0.60, 0.50, 0.52, 1),    # over, 10 points, medium, won
               ("g2", "b", 50, "rec_yds", 0.30, 0.40, 0.37, 1),    # under, 10 points, medium, lost
               ("g3", "c", 50, "rec_yds", 0.52, 0.50, 0.50, 1)])   # inside the 5 point threshold
    x = L.make_leans(d, "p_A")
    assert list(x["side"]) == ["over", "under"] and list(x["size"]) == ["medium", "medium"]
    assert x["real"].round(3).tolist() == [0.5, -0.6]
    assert x["clv"].round(3).tolist() == [0.02, 0.03]


def test_a_ladder_counts_once_at_its_largest_edge():
    d = frame([("g1", "a", 40, "rec_yds", 0.70, 0.60, 0.6, 1),
               ("g1", "a", 50, "rec_yds", 0.60, 0.40, 0.4, 1),     # biggest gap on this ladder
               ("g1", "a", 60, "rec_yds", 0.50, 0.35, 0.3, 0)])
    x = L.make_leans(d, "p_A")
    assert len(x) == 1 and x["k"].iloc[0] == 50


def test_edges_use_the_chosen_market_number_and_clv_uses_the_raw_mid():
    d = frame([("g1", "a", 50, "rec", 0.70, 0.50, 0.58, 1)])
    d["m_use"] = 0.55                                               # a corrected market number
    x = L.make_leans(d, "p_A")
    assert x["edge"].iloc[0] == pytest.approx(0.15) and x["price"].iloc[0] == pytest.approx(0.55)
    assert x["real"].iloc[0] == pytest.approx(0.45)                 # won at a fair price of 0.55, no fee
    assert x["clv"].iloc[0] == pytest.approx(0.08)                  # close 0.58 minus raw mid 0.50


def test_market_candidates_and_choice_default_to_the_plain_mid():
    rng = np.random.default_rng(0)
    n = 900
    mid = rng.uniform(0.1, 0.9, n)
    d = pd.DataFrame({"gid": [f"g{i // 3}" for i in range(n)], "pid": "a", "k": 50, "stat": "rec_yds", "p_A": mid, "p_market90": mid, "p_marketC": mid,
                      "y": (rng.random(n) < mid).astype(int), "bid90": mid - 0.01, "ask90": mid + 0.01, "season": 2026, "week": np.repeat(np.arange(1, 10), 100)})
    d["key"], d["mid"] = d["season"] * 100 + d["week"], (d["bid90"] + d["ask90"]) / 2
    d["devig"] = d["ask90"] / (1 + d["ask90"] - d["bid90"])
    out = L.calibrate_market(d)
    assert out["market_name"].iloc[0] in ("mid", "devig", "calibrated")
    assert (out.loc[out["key"] < 202603, "m_use"] == out.loc[out["key"] < 202603, "mid"]).all()      # before the first test week it is the mid
    assert (out["devig"] - out["mid"]).abs().max() < 0.01                                            # a 2 point spread barely moves it


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
    d = frame([(f"g{i}", "a", 50, "rec", 0.7, 0.5, 0.55, int(rng.random() < 0.7)) for i in range(40)])
    s = L.summarize(L.make_leans(d, "p_A"))
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
