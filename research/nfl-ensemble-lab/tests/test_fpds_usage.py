"""FantasyPoints metrics in the simulation: scales, masking, blends, the gate, touchdown weights. Synthetic inputs; one real-data sanity check."""
import numpy as np
import pandas as pd
import pytest

from lab import fpds_usage as X
from lab import gamesim as S
from lab import usage as U


def _usage(n_thin=1):
    players = pd.DataFrame([
        {"pid": "a", "pos": "WR", "n": 6, "last": 6, "active": True, "share_rec_yds": 0.40, "share_rec": 0.35, "share_rush_yds": 0.0},
        {"pid": "b", "pos": "WR", "n": 6, "last": 6, "active": True, "share_rec_yds": 0.30, "share_rec": 0.30, "share_rush_yds": 0.0},
        {"pid": "c", "pos": "TE", "n": 2, "last": 6, "active": True, "share_rec_yds": 0.30, "share_rec": 0.35, "share_rush_yds": 0.0},
    ])
    return U.Usage("AAA", 6, {"rec_yds": 200.0, "rec": 20.0, "rush_yds": 100.0}, players)


def _feats(**cols):
    return pd.DataFrame(cols, index=["a", "b", "c"])


def test_share_from_fills_missing_players_from_their_base_share():
    base = np.array([0.5, 0.3, 0.2])
    got = X.share_from(np.array([0.30, np.nan, 0.10]), base)
    assert got.sum() == pytest.approx(1.0)
    assert got[1] == pytest.approx(0.3 * (0.40 / 0.7) / (0.40 + 0.3 * 0.40 / 0.7))  # missing player takes the value his base share implies
    assert np.allclose(X.share_from(np.array([np.nan] * 3), base), base)


def test_nearly_empty_weeks_are_masked_but_partial_weeks_are_used():
    rows = [{"season": 2026, "week": float(w), "team": "T", "pid": f"p{i}", "tgt_pct": 0.1} for w in (1, 2, 3) for i in range(100)]
    rows += [{"season": 2026, "week": 4.0, "team": "T", "pid": f"p{i}", "tgt_pct": 0.9} for i in range(5)]    # almost empty
    rows += [{"season": 2026, "week": 5.0, "team": "T", "pid": f"p{i}", "tgt_pct": 0.3} for i in range(20)]   # partial but real
    out = X._mask_thin_weeks(pd.DataFrame(rows))
    assert out.loc[out["week"] == 4, "tgt_pct"].isna().all()
    assert out.loc[out["week"] == 5, "tgt_pct"].notna().all() and out.loc[out["week"] == 1, "tgt_pct"].notna().all()


def test_blend_applies_only_to_the_group_and_keeps_the_total(monkeypatch):
    monkeypatch.setattr(X, "features_asof", lambda *a, **k: _feats(tgt_pct=[0.1, 0.1, 0.8]))
    rule = {"weights": {"rec_yds": {"group": "thin", "max_n": 3, "mix": {"base": 0.5, "tgt_pct": 0.5}}}}
    u2, info = X.blend_shares(_usage(), "AAA", 2026, 8, frozenset(), rule)
    old, new = _usage().players["share_rec_yds"].to_numpy(), u2.players["share_rec_yds"].to_numpy()
    assert info["used"] and info["stats"] == ["rec_yds"]
    assert new.sum() == pytest.approx(old.sum())
    assert new[2] > old[2]                               # thin-history player c moves toward his 80% target share
    assert new[0] / new[1] == pytest.approx(old[0] / old[1])  # regulars a and b keep their relative shares
    same, info0 = X.blend_shares(_usage(), "AAA", 2026, 8, frozenset(), {})
    assert not info0["used"] and np.allclose(same.players["share_rec_yds"], old)


def test_blend_group_can_cover_everyone(monkeypatch):
    monkeypatch.setattr(X, "features_asof", lambda *a, **k: _feats(tgt_pct=[0.1, 0.1, 0.8]))
    rule = {"weights": {"rec_yds": {"max_n": 6, "mix": {"base": 0.0, "tgt_pct": 1.0}}}}
    u2, _ = X.blend_shares(_usage(), "AAA", 2026, 8, frozenset(), rule)
    assert u2.players["share_rec_yds"].to_numpy() == pytest.approx([0.1, 0.1, 0.8])


def test_gate_needs_both_years_clearly_better():
    def res(d25, d26):
        t = lambda hi: {"thin_history": {"diff_hi": hi}}
        return {"stats": {"rec": {"weights": {"base": 0.5}, "test_2025": t(d25), "test_2026": t(d26)}}}
    assert X.gate(res(-0.1, -0.1)) and not X.gate(res(-0.1, 0.01)) and not X.gate(res(0.0, -0.1))


def test_touchdown_weights_clip_negative_yards_and_use_fpds_only_when_it_passed(monkeypatch):
    u = _usage()
    u.players.loc[0, "share_rec_yds"] = -0.2          # a player who lost yards in some games
    monkeypatch.setattr(X, "_td_table", lambda season: pd.DataFrame({"week": [1, 2], "team": ["AAA", "AAA"], "pid": ["b", "b"], "rec_td": [1, 1], "rush_td": [0, 0]}))
    monkeypatch.setattr(X, "features_asof", lambda *a, **k: _feats(eztgt=[0.0, 0.0, 3.0], i20_tgt=[0.0, 0.0, 2.0]))
    off = X.rec_td_weights(u, "AAA", 2026, 8, frozenset(), {"td": {"rec_td": {"uses_fpds": False, "weights": {"yards": 0.9, "td_history": 0.1, "fpds": 0.0}}}})
    on = X.rec_td_weights(u, "AAA", 2026, 8, frozenset(), {"td": {"rec_td": {"uses_fpds": True, "weights": {"yards": 0.5, "td_history": 0.1, "fpds": 0.4}}}})
    assert min(off.values()) >= 0 and sum(off.values()) == pytest.approx(1.0) and sum(on.values()) == pytest.approx(1.0)
    assert on["c"] > off["c"]                         # red-zone targets lift the tight end


def _play(team, kind, player, yards, event=None):
    return {"team": team, "kind": kind, "player": player, "passer": "QB", "yards": yards, "event": event, "text": ""}


def test_touchdown_swap_keeps_each_players_total_within_four_yards():
    plays = [_play("AAA", "pass", "Low", 6, "TD"), _play("AAA", "pass", "Star", 8), _play("AAA", "pass", "Star", 20), _play("AAA", "pass", "Low", 11)]
    before = {}
    for p in plays:
        before[p["player"]] = before.get(p["player"], 0) + p["yards"]
    swaps = S._assign_scorers(plays, {"AAA": {"Star": 1.0, "Low": 0.0}}, np.random.default_rng(1))
    after = {}
    for p in plays:
        after[p["player"]] = after.get(p["player"], 0) + p["yards"]
    assert swaps == 1 and plays[0]["player"] == "Star" and "TOUCHDOWN" in plays[0]["text"] and "TOUCHDOWN" not in plays[1]["text"]
    assert sum(after.values()) == sum(before.values()) + (6 - 6)  # nothing is created or lost
    assert abs(after["Star"] - before["Star"]) <= 4 and abs(after["Low"] - before["Low"]) <= 4


def test_touchdown_swap_leaves_the_play_alone_when_no_similar_catch_exists():
    plays = [_play("AAA", "pass", "Low", 40, "TD"), _play("AAA", "pass", "Star", 5)]
    assert S._assign_scorers(plays, {"AAA": {"Star": 1.0}}, np.random.default_rng(1)) == 0 and plays[0]["player"] == "Low"


def test_newer_import_percents_become_fractions_and_never_overwrite(tmp_path, monkeypatch):
    base = pd.DataFrame([{"season": 2026, "week": 4.0, "team": "TEN", "pid": "00-1", "tgt_pct": 0.20, "rte_pct": 0.80, "ay_share": 30.0}])
    pd.DataFrame([{"season": 2026, "week": 7.0, "team": "TEN", "pid": "00-1", "receiving__tgt_pct": 24.0, "receiving__rte_pct": 90.0, "receiving__ay_share": 35.0},
                  {"season": 2026, "week": 4.0, "team": "TEN", "pid": "00-1", "receiving__tgt_pct": 99.0, "receiving__rte_pct": 99.0, "receiving__ay_share": 99.0}]
                 ).to_parquet(tmp_path / "receiving_stats__working_usable.parquet")
    monkeypatch.setattr(X, "_a6_dir", lambda: tmp_path)
    out = X._add_latest_weeks(base).set_index("week")
    assert out.loc[7.0, "tgt_pct"] == pytest.approx(0.24) and out.loc[7.0, "rte_pct"] == pytest.approx(0.90)
    assert out.loc[7.0, "ay_share"] == pytest.approx(35.0)   # air yards share is a percent in both exports
    assert out.loc[4.0, "tgt_pct"] == pytest.approx(0.20)    # the first import's value is kept


def test_latest_weeks_take_the_first_value_present_across_tables(tmp_path, monkeypatch):
    base = pd.DataFrame([{"season": 2026, "week": 4.0, "team": "TEN", "pid": "00-9", "tgt_pct": 0.1}])
    pd.DataFrame([{"season": 2026, "week": 5.0, "team": "TEN", "pid": "00-1", "receiving__tgt_pct": 20.0}]).to_parquet(tmp_path / "receiving_stats__working_usable.parquet")
    pd.DataFrame([{"season": 2026, "week": 5.0, "team": "TEN", "pid": "00-1", "receiving__tgt_pct": 99.0, "receiving__rte_pct": 80.0},
                  {"season": 2026, "week": 5.0, "team": "TEN", "pid": "00-2", "receiving__tgt_pct": 10.0, "receiving__rte_pct": 60.0}]).to_parquet(tmp_path / "bell_cow_report__working_usable.parquet")
    monkeypatch.setattr(X, "_a6_dir", lambda: tmp_path)
    out = X._add_latest_weeks(base).set_index(["week", "pid"])
    assert out.loc[(5.0, "00-1"), "tgt_pct"] == pytest.approx(0.20)   # the main receiving table wins
    assert out.loc[(5.0, "00-1"), "rte_pct"] == pytest.approx(0.80)   # a metric only another table has still comes through
    assert out.loc[(5.0, "00-2"), "tgt_pct"] == pytest.approx(0.10)   # players only the other table lists are kept


def test_rush_touchdown_share_leans_on_the_team_but_not_too_far(monkeypatch):
    td = pd.DataFrame({"week": [1, 2, 3], "team": ["TEN"] * 3, "pid": ["a", "a", "b"], "rec_td": [0, 0, 1], "rush_td": [2, 3, 0], "season": [2026] * 3})
    monkeypatch.setattr(X, "_td_table", lambda season: td)
    share = X.rush_td_share("TEN", 2026, 4)
    assert 0.38 < share < 5 / 6 and share == pytest.approx((5 + 0.38 * 4) / (6 + 4))
    assert X.rush_td_share("XXX", 2026, 4) == pytest.approx(0.38)  # no history: the league share
