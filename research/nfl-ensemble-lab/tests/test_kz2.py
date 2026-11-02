"""King of the End Zone v2: tail draws, scoring of the real winner, the crowding estimate and write-once hashed forecasts. Synthetic inputs, no data files needed."""
import json

import numpy as np
import pytest

from lab import kz2 as K
from lab import kz2_board as B


def test_pareto_tail_draws_have_the_right_mean_and_are_positive():
    rng = np.random.default_rng(3)
    x = K._gpd(rng.random(200000), sigma=10.0, xi=0.1)
    assert (x >= 0).all()
    assert x.mean() == pytest.approx(10.0 / (1 - 0.1), rel=0.03)
    e = K._gpd(rng.random(200000), sigma=10.0, xi=0.0)   # the exponential limit
    assert e.mean() == pytest.approx(10.0, rel=0.03)


def test_score_entity_averages_ties_and_sends_unlisted_and_defense_to_the_field():
    rows = [{"pid": "a", "chance": 0.20}, {"pid": "b", "chance": 0.10}]
    assert K.score_entity(rows, 0.15, ["a"]) == pytest.approx(0.20)
    assert K.score_entity(rows, 0.15, ["a", "b"]) == pytest.approx(0.15)      # a tie: the average of the two
    assert K.score_entity(rows, 0.15, ["FIELD"]) == pytest.approx(0.15)
    assert K.score_entity(rows, 0.15, ["z"]) == pytest.approx(0.15)           # not on the roster


def test_crowd_shares_sum_to_one_and_a_higher_gamma_concentrates_on_favorites():
    rows = [{"crowd_base": 0.6}, {"crowd_base": 0.3}, {"crowd_base": 0.1}]
    lo, hi = B._crowd(rows, 0.5), B._crowd(rows, 1.5)
    assert lo.sum() == pytest.approx(1.0) and hi.sum() == pytest.approx(1.0)
    assert hi[0] > lo[0] and hi[2] < lo[2]


def test_frozen_forecast_is_write_once_and_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "FROZEN", tmp_path / "frozen")
    monkeypatch.setattr(B, "LEDGER", tmp_path / "ledger.jsonl")
    calls = []

    def fake_board(gid, n=0, force=False):
        calls.append(gid)
        return {"gid": gid, "week": 9, "fit": "fit.pkl", "code_sha256": "x", "sims": 10, "field": 0.15, "no_touchdown": 0.01, "kickoff_utc": "2099-01-01T00:00:00+00:00",
                "rows": [{"pid": "p1", "player": "P One", "team": "AAA", "chance": 0.2, "anytime": 0.5, "two_plus": 0.1, "first": 0.1, "p40": 0.1, "p60": 0.05, "market_anytime": None, "pool_index": 1.2}]}

    monkeypatch.setattr(B, "board", fake_board)
    first = B.freeze("2099_09_AAA_BBB")
    assert first["before_kickoff"] is True
    again = B.freeze("2099_09_AAA_BBB")
    assert again["sha256"] == first["sha256"] and len(calls) == 1               # a second call does not rebuild or overwrite
    assert len((tmp_path / "ledger.jsonl").read_text().splitlines()) == 1
    path = tmp_path / "frozen" / "2099_09_AAA_BBB.json"
    rec = json.loads(path.read_text())
    rec["forecast"]["players"][0]["chance"] = 0.9
    path.write_text(json.dumps(rec))
    with pytest.raises(RuntimeError):
        B.freeze("2099_09_AAA_BBB")
