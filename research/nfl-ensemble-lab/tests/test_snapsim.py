"""Snap simulator: the engine conserves the basics (scores are legal, a seed repeats, a louder crowd adds false starts) and saved records are write-once. Small fitted parameters, a few hundred games."""
import json

import numpy as np
import pytest

from lab import snapfit, snapgame, snapsim


@pytest.fixture(scope="module")
def fitted():
    P = snapfit.fit(8)
    p = snapfit.load(8)
    return P, p


def pools_for(P, p, a, h, n):
    import pandas as pd
    rng = np.random.default_rng(0)
    inj = pd.read_parquet(snapgame.RAW / "injuries_2026.parquet")
    inj = inj[inj["week"] == 8]
    return [snapgame.build_pool(P, p, a, 8, None, n, rng, inj), snapgame.build_pool(P, p, h, 8, None, n, rng, inj)]


def test_games_end_with_legal_scores_and_a_seed_repeats(fitted):
    P, p = fitted
    pools = pools_for(P, p, "CHI", "SEA", 300)
    a = snapsim.simulate(P, "CHI", "SEA", pools, n=300, seed=3)
    b = snapsim.simulate(P, "CHI", "SEA", pools, n=300, seed=3)
    assert (a["score"] == b["score"]).all()
    s = a["score"]
    assert s.min() >= 0 and s.max() < 80 and 25 < s.sum(1).mean() < 70
    assert a["stats"]["snaps"].sum(1).mean() > 90


def test_a_louder_crowd_means_more_visiting_false_starts(fitted):
    P, p = fitted
    pools = pools_for(P, p, "CHI", "SEA", 600)
    lo = snapsim.simulate(P, "CHI", "SEA", pools, n=600, seed=5, crowd_mult=1.0)
    hi = snapsim.simulate(P, "CHI", "SEA", pools, n=600, seed=5, crowd_mult=3.0)
    assert hi["stats"]["false_starts"][:, 0].mean() > lo["stats"]["false_starts"][:, 0].mean()
    assert hi["stats"]["false_starts"][:, 1].mean() == pytest.approx(lo["stats"]["false_starts"][:, 1].mean(), abs=0.2)


def test_the_rookie_and_starter_split_follows_the_scenario(fitted):
    P, p = fitted
    import pandas as pd
    rng = np.random.default_rng(1)
    inj = pd.read_parquet(snapgame.RAW / "injuries_2026.parquet")
    inj = inj[inj["week"] == 8]
    pl, _ = snapgame._roster_info()
    sc = {"star": pl.index[pl["display_name"] == "Zach Charbonnet"][0], "rookie": pl.index[pl["display_name"] == "Jadarian Price"][0]}
    lo = snapgame.build_pool(P, p, "SEA", 8, sc, 400, rng, inj, fixed=(0.40, 0.88))
    hi = snapgame.build_pool(P, p, "SEA", 8, sc, 400, rng, inj, fixed=(0.65, 1.02))
    k = lo["names"].index("Zach Charbonnet")
    share = lambda pool: np.diff(np.concatenate([[0], pool["ccum"][0, 0]]))[k]
    assert share(hi) > share(lo)
    assert (hi["rush_mult"][:, k] > lo["rush_mult"][:, k]).all()


def test_saved_game_records_are_write_once_and_detect_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(snapgame, "OUT", tmp_path)
    calls = []
    monkeypatch.setattr(snapgame, "full_run", lambda gid: calls.append(gid) or {"gid": gid, "created": "t", "win": {"A": 0.5}})
    first = snapgame.freeze("g1")
    again = snapgame.freeze("g1")
    assert calls == ["g1"] and again["sha256"] == first["sha256"] and first["frozen"]
    path = tmp_path / "frozen" / "g1.json"
    rec = json.loads(path.read_text())
    rec["forecast"]["win"]["A"] = 0.9
    path.write_text(json.dumps(rec))
    assert snapgame.get("g1")["frozen_ok"] is False


def test_scenarios_are_skipped_not_crashed_when_a_game_has_no_returning_starter(monkeypatch):
    monkeypatch.setattr(snapgame, "run_game", lambda gid, n=0, fixed=None, seed=0: {"scenario": {}, "win": {}, "cover": {}, "over": 0.5, "_players": []})
    assert snapgame.scenarios("2026_09_JAX_BAL") == {}
