"""Sampled receiving model and the availability source: synthetic inputs, no network, no local data files needed."""
import numpy as np
import pandas as pd
import pytest
from scipy.special import gammaln
from scipy.stats import multinomial

from lab import avail_source as A
from lab import gamesim as S
from lab import recvsim as R


# --------------------------------------------------------------------------- availability source
def _status(rows):
    return pd.DataFrame(rows, columns=["season", "week", "team", "gsis_id", "group", "roster", "official"])


def test_status_classes_follow_how_final_each_source_is():
    df = _status([(2025, 5, "KC", "a", "WR", "ACT", None), (2025, 5, "KC", "b", "WR", "RES", "Out"), (2025, 5, "KC", "c", "WR", "INA", None),
                  (2025, 5, "KC", "d", "WR", "ACT", "Questionable"), (2025, 5, "KC", "e", "WR", "DEV", None), (2025, 5, "KC", "f", "WR", "ACT", "Doubtful")])
    assert list(A.classify(df, game_day=False)) == ["clear", "reserve or gone", "clear", "Questionable", "practice squad", "Doubtful"]
    assert A.classify(df, game_day=True).iloc[2] == "inactive"          # inactive is known only on game day
    assert A.classify(df, game_day=True).iloc[1] == "reserve or gone"   # a roster status outranks an official one


def test_regulars_are_players_in_three_of_the_previous_four_games():
    rows = [(2025, w, "KC", "a", "WR", "ACT", None) for w in range(1, 9)] + [(2025, w, "KC", "b", "WR", "ACT", None) for w in range(1, 9)]
    ap = pd.DataFrame([(2025, w, "KC", "a") for w in range(1, 9)] + [(2025, 1, "KC", "b")], columns=["season", "week", "team", "gsis_id"])
    reg = A.regulars(_status(rows), ap)
    assert set(reg["gsis_id"]) == {"a"} and set(reg["week"]) == set(range(5, 9))


def test_chance_of_playing_comes_from_regulars_by_status(monkeypatch):
    rows, played = [], []
    for w in range(1, 41):
        rows.append((2024, w % 18 + 1, f"T{w}", "x", "WR", "ACT", "Questionable"))
    monkeypatch.setattr(A, "status_table", lambda seasons: _status([(2024, w, "KC", "a", "WR", "ACT", "Questionable" if w > 4 else None) for w in range(1, 25)]))
    monkeypatch.setattr(A, "appearances", lambda seasons: pd.DataFrame([(2024, w, "KC", "a") for w in range(1, 25) if not (w > 4 and w % 2 == 0)], columns=["season", "week", "team", "gsis_id"]))
    t = A.fit_p_play([2024], False)
    assert 0.3 < t[("Questionable", "WR")] < 0.7  # played about every other time he was listed


def test_paired_loss_interval_brackets_the_difference():
    groups = np.repeat(np.arange(50), 4)
    new, old = np.full(200, 0.2), np.full(200, 0.3)
    r = A._paired_loss(new, old, groups)
    assert r["diff"] == pytest.approx(-0.1) and r["lo"] <= r["diff"] + 1e-9 and r["diff"] <= r["hi"] + 1e-9


# --------------------------------------------------------------------------- the receiving model
def _case(n_players=5, games=6, muT=32.0):
    g = ["WR", "WR", "WR", "TE", "RB"][:n_players]
    return R.Case(2026, 8, "KC", [f"p{i}" for i in range(n_players)], g, np.full(n_players, 190.0), np.array([45, 38, 30, 22, 15.0])[:n_players],
                  np.array([29, 24, 18, 16, 12.0])[:n_players], np.array([380, 300, 220, 180, 90.0])[:n_players], np.full(n_players, np.nan), muT,
                  np.zeros(n_players), np.zeros(n_players), np.zeros(n_players), 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, games)


def test_expected_shares_add_to_one_with_an_outside_share_and_pool_short_records():
    p = R.Params(eps=0.04)
    c = _case()
    mu = R.expected_shares(c, p)
    assert mu.sum() == pytest.approx(1.0) and mu[-1] == pytest.approx(0.04) and np.all(np.diff(mu[:5]) < 0)
    short, long = _case(2), _case(2)                       # both show 40% of targets for player 0; only the long record has earned it
    short.N, short.tgt_w = np.array([20.0, 190.0]), np.array([8.0, 76.0])
    long.N, long.tgt_w = np.array([200.0, 190.0]), np.array([80.0, 76.0])
    assert R.expected_shares(short, p)[0] < R.expected_shares(long, p)[0] - 0.1


def test_dirichlet_multinomial_approaches_the_multinomial_for_a_huge_concentration():
    mu = np.array([0.5, 0.3, 0.2]); n = np.array([6, 3, 1])
    coef = gammaln(n.sum() + 1) - gammaln(n + 1).sum()    # dm_loglik leaves out the constant multinomial coefficient
    assert R.dm_loglik(n, mu, 1e7) + coef == pytest.approx(multinomial.logpmf(n, 10, mu), abs=1e-3)


def test_short_windows_use_the_lower_concentration():
    p = R.Params()
    assert R.alpha_for(_case(games=3), p) == p.alpha_short * p.alpha_mult and R.alpha_for(_case(games=6), p) == p.alpha * p.alpha_mult
    assert p.alpha_short < p.alpha


def test_samples_are_lumpier_than_a_plain_multinomial_and_keep_their_means():
    p = R.Params(alpha=20.0, alpha_mult=1.0)
    c = _case()
    s = R.sample(c, p, 4000, np.random.default_rng(1))
    mu = R.expected_shares(c, p)
    assert np.all(s["rec"] <= s["tgt"]) and np.all(s["yds"][s["rec"] == 0] == 0)
    assert s["tgt"].sum(1).mean() == pytest.approx(p.t_icpt + p.t_slope * c.muT, rel=0.03)
    assert s["tgt"][:, 0].mean() / s["tgt"].sum(1).mean() == pytest.approx(mu[0], abs=0.02)
    n = s["tgt"].sum(1).mean()
    assert s["tgt"][:, 0].var() > 1.5 * n * mu[0] * (1 - mu[0])        # a real game's split varies more than chance alone


def test_expected_targets_scale_with_game_flow():
    p, c = R.Params(), _case()
    fast = R.sample(c, p, 3000, np.random.default_rng(2))["tgt"].sum(1).mean()
    c.t_scale = 1.25
    assert R.sample(c, p, 3000, np.random.default_rng(2))["tgt"].sum(1).mean() > fast * 1.15


def test_team_box_counts_receivers_shares_and_tight_ends():
    rec = np.array([[5, 3, 0, 2], [1, 1, 1, 1]], float)
    n, top, te = R.team_box(rec, np.array([0.0, 2.0]), ["WR", "WR", "RB", "TE"])
    assert list(n) == [3, 6] and top[0] == pytest.approx(0.5) and te[0] == pytest.approx(0.2) and te[1] == pytest.approx((1 + 0.5) / 6)


def _block():
    T = np.array([30.0, 32.0, 34.0, 36.0])
    tgt = np.array([[10, 12, 13, 12], [8, 9, 9, 10], [6, 6, 7, 8], [0, 0, 5, 6.0]])
    return R.Block([1, 2, 3, 4], T, ["a", "b", "c", "d"], ["WR", "WR", "TE", "RB"], tgt, tgt * 0.6, tgt * 7.0, np.ones_like(tgt))


def test_future_case_drops_out_players_and_needs_two_games_on_record():
    blk = {(2026, "KC"): _block()}
    c = R.future_case(blk, 2026, "KC", 5, {"b"}, 1.1)
    assert c.pids == ["a", "c", "d"] and c.t_scale == 1.1 and c.games == 4
    assert R.future_case(blk, 2026, "KC", 2, set()) is None         # one game on record
    assert R.future_case(blk, 2026, "KC", 5, {"a", "b"}) is None    # fewer than three players left to draw from


def test_a_sampled_game_has_one_yard_figure_per_catch():
    blk = {(2026, "KC"): _block()}
    c = R.future_case(blk, 2026, "KC", 5, set())
    g = R.sample_game(c, R.Params(), np.random.default_rng(3))
    assert all(len(y) == r for y, r in zip(g["yards"], g["rec"])) and len(g["yards"][0]) == g["rec"][0] and len(g["other"]["yards"]) == g["other"]["rec"]


def test_rule_loads_only_when_written(tmp_path):
    assert R.load_rule(tmp_path / "none.json") == (None, False)
    (tmp_path / "r.json").write_text('{"passed": true, "params": {"k": 50.0, "c_g": {"WR": 0.6}}}', encoding="utf-8")
    params, ok = R.load_rule(tmp_path / "r.json")
    assert ok and params.k == 50.0 and params.c_g == {"WR": 0.6}


# --------------------------------------------------------------------------- the replay builds from a sampled game
def test_pool_from_a_sampled_game_names_every_target_and_keeps_its_yards():
    sampled = {"players": [{"name": "Star WR", "group": "WR", "tgt": 9, "rec": 6, "yards": [12, 8, 30, 5, 9, 14]},
                           {"name": "Tight End", "group": "TE", "tgt": 4, "rec": 2, "yards": [7, 11]},
                           {"name": "Backup RB", "group": "RB", "tgt": 1, "rec": 0, "yards": []}]}
    props = [{"player": "Pat QB", "team": "AAA", "stat": "Passing yards", "typical": 230.0, "expected": 230.0},
             {"player": "Run RB", "team": "AAA", "stat": "Rushing yards", "typical": 70.0, "expected": 75.0}]
    pool, qb, lead = S._pool("AAA", props, None, np.random.default_rng(1), 1.0, sampled)
    passes = [p for p in pool if p["kind"] == "pass"]
    assert sorted(p["yards"] for p in passes if p["player"] == "Star WR") == [5, 8, 9, 12, 14, 30] and len(passes) == 8
    inc = [p for p in pool if p["kind"] == "incomplete"]
    assert sorted(p["player"] for p in inc) == ["Backup RB", "Star WR", "Star WR", "Star WR", "Tight End", "Tight End"]
    assert qb == "Pat QB" and lead == "Run RB"


def test_incomplete_caption_names_the_intended_receiver():
    assert S._caption({"kind": "incomplete", "player": "Pat Ridley", "passer": "Cam Ward", "yards": 0}, "TEN") == "Cam Ward pass intended for Pat Ridley is incomplete."
    assert S._caption({"kind": "incomplete", "player": None, "passer": "Cam Ward", "yards": 0}, "TEN") == "Cam Ward pass incomplete."


def test_the_old_method_is_kept_until_the_sampled_model_passes_its_check(monkeypatch):
    monkeypatch.setattr(S.RS, "load_rule", lambda *a, **k: (R.Params(), False))
    assert S.receiving_for_game("KC", 8, set(), 1.0, np.random.default_rng(1)) is None
    monkeypatch.setattr(S.RS, "load_rule", lambda *a, **k: (None, False))
    assert S.receiving_for_game("KC", 8, set(), 1.0, np.random.default_rng(1)) is None
