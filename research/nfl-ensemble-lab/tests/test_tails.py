"""Tails: tail-rate arithmetic, multiple-test correction, and write-once hashed weekly records."""
import json

import numpy as np
import pytest

from lab import tails, tails_tests, tails_week


def test_expected_tail_matches_a_normal_curve():
    assert tails.expected_tail(13.5, 14) == pytest.approx(2 * (1 - 0.8413), abs=0.03)
    assert tails.expected_tail(13.5, 21) < tails.expected_tail(13.5, 14)


def test_holm_is_monotone_and_never_below_raw_p():
    p = {"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5}
    h = tails_tests.holm(p)
    assert all(h[k] >= p[k] for k in p)
    assert h["a"] == pytest.approx(0.004) and h["d"] == pytest.approx(0.5)
    assert h["a"] <= h["b"] <= h["c"] <= h["d"]


def test_rule_is_locked_to_the_preregistered_hash():
    ledger = json.loads((tails.ROOT / "docs" / "tails_prereg_ledger.jsonl").read_text().splitlines()[0])
    assert tails.freeze_rule_hash() == ledger["rule_sha256"]


def test_weekly_record_is_write_once_and_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(tails_week, "FROZEN", tmp_path / "frozen")
    monkeypatch.setattr(tails_week, "LEDGER", tmp_path / "ledger.jsonl")
    calls = []
    monkeypatch.setattr(tails_week, "weekly", lambda week=None: calls.append(1) or {"season": 2026, "week": 9, "games": [{"gid": "g", "u_any": True}]})
    first = tails_week.freeze(9)
    again = tails_week.freeze(9)
    assert len(calls) == 2 and again["sha256"] == first["sha256"]       # second call recomputes but returns the saved file
    assert tails_week.verify(first)
    first["forecast"]["games"][0]["u_any"] = False
    assert not tails_week.verify(first)
    assert len((tmp_path / "ledger.jsonl").read_text().splitlines()) == 1


def test_tail_tests_find_nothing_in_pure_normal_noise():
    rng = np.random.default_rng(3)
    import pandas as pd
    n = 3000
    g = pd.DataFrame({"season": rng.integers(2006, 2027, n), "result": 1.0, "e": rng.normal(0, 13.5, n), "u_qb": rng.random(n) < 0.3})
    g["u_gap"], g["u_any"] = g["u_qb"], g["u_qb"]
    R = {**tails.rule(), "discovery": [2006, 2019], "confirmation": [2020, 2026]}
    out = tails_tests.tail_tests(g, 13.5, R, rng)
    assert out["passed"] == []
