"""Referee trends: ATS and push handling, shrinkage, a planted penalty effect, shuffles that stay inside a week, write-once hashed assignments."""
import json

import numpy as np
import pandas as pd
import pytest

from lab import refs as R


def test_shrinkage_pulls_small_samples_toward_the_league_rate():
    rng = np.random.default_rng(0)
    rows = [("big", int(rng.random() < 0.5)) for _ in range(400)] + [("tiny", 1) for _ in range(5)]
    d = pd.DataFrame(rows, columns=["referee", "home_ats"])
    t = R.shrink_binary(d, "home_ats").set_index("referee")
    assert t.loc["tiny", "rate"] == 1.0 and 0.5 < t.loc["tiny", "shrunk"] < 0.8
    assert abs(t.loc["big", "shrunk"] - t.loc["big", "rate"]) < 0.02
    assert t.loc["tiny", "lo"] < 1.0 <= t.loc["tiny", "hi"]


def test_holm():
    h = R.holm({"a": 0.01, "b": 0.04, "c": 0.5})
    assert h["a"] == pytest.approx(0.03) and h["b"] == pytest.approx(0.08) and h["c"] == pytest.approx(0.5)


def test_shuffle_keeps_referees_inside_their_season_and_week():
    f = pd.DataFrame({"season": [2024] * 6 + [2025] * 6, "week": [1, 1, 1, 2, 2, 2] * 2, "referee": list("AAABBB") + list("CCCDDD")})
    out = R._shuffle(f, np.random.default_rng(3))
    for _, ix in f.groupby(["season", "week"]).indices.items():
        assert sorted(out[ix]) == sorted(f["referee"].to_numpy()[ix])


def test_a_planted_home_penalty_effect_is_recovered_and_a_null_is_not():
    rng = np.random.default_rng(1)
    n = 1200
    f = pd.DataFrame({"referee": rng.choice(list("ABCD"), n), "plays": rng.integers(110, 140, n), "spread_line": rng.normal(0, 5, n), "msd_home": rng.normal(0, 6, n)})
    base = 0.05 * f["plays"]
    f["pen_home"] = rng.poisson(base * np.where(f["referee"] == "A", 1.4, 1.0))
    f["pen_away"] = rng.poisson(base)
    c = R._fit_pen(f, list("ABCD"))
    assert c["A"] > 0.1 and abs(c[["B", "C", "D"]]).max() < 0.1


def test_frozen_assignments_are_write_once_and_detect_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "FROZEN", tmp_path / "f")
    monkeypatch.setattr(R, "LEDGER", tmp_path / "ledger.jsonl")
    games = [{"gid": "g1", "away": "A", "home": "B", "kickoff": "2026-11-09", "referee": "Shawn Smith"}, {"gid": "g2", "away": "C", "home": "D", "kickoff": "2026-11-09", "referee": None}]
    monkeypatch.setattr(R, "this_week", lambda f=None: {"season": 2026, "week": 9, "source": "test", "games": games})
    monkeypatch.setattr(R, "frame", lambda: None)
    monkeypatch.setattr(R, "tab_numbers", lambda f, refs: {r: {"games": 100, "home_cover_shrunk": 0.5} for r in refs})
    first = R.freeze_week(9)
    assert [g["gid"] for g in first["forecast"]["games"]] == ["g1"]                      # the unassigned game is not written
    again = R.freeze_week(9)
    assert again["sha256"] == first["sha256"]
    path = tmp_path / "f" / "9.json"
    rec = json.loads(path.read_text())
    rec["forecast"]["games"][0]["referee"] = "Someone Else"
    path.write_text(json.dumps(rec))
    with pytest.raises(RuntimeError):
        R.freeze_week(9)


def test_nothing_is_written_when_no_referee_is_assigned(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "FROZEN", tmp_path / "f")
    monkeypatch.setattr(R, "this_week", lambda f=None: {"season": 2026, "week": 9, "source": "test", "games": [{"gid": "g1", "away": "A", "home": "B", "kickoff": "x", "referee": None}]})
    out = R.freeze_week(9)
    assert out["games"] == [] and not (tmp_path / "f").exists()
