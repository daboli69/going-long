import numpy as np
import pandas as pd
import pytest

from lab.props.ensemble import features as F
from lab.props.ensemble.combine import combine, first_td_reweight
from lab.props.ensemble.members import Members, make_member
from lab.props.independent import IndependentAnchor, spread_label


def test_holdout_files_and_fitting_are_forbidden():
    with pytest.raises(ValueError, match="forbidden"):
        F.load_plays([2023])
    with pytest.raises(ValueError, match="2021"):
        Members().fit(pd.DataFrame({"season": [2022]}), "rec", [])


def test_features_ignore_same_and_later_weeks():
    history = pd.DataFrame([{**{c: 0. for c in F.RAW_STATS}, "game_id": f"g{w}", "season": 2022, "week": w,
        "pid": "p", "position": "WR", "opponent": "CHI", "targets": w, "rec_yds": w * 10,
        "target_share": .3, "off_td": 0} for w in (1, 2, 3)])
    candidates = pd.DataFrame([{"season": 2022, "week": 2, "pid": "p", "position": "WR", "opponent": "CHI"}])
    a = F.earlier_features(history, candidates)
    history.loc[history["week"] >= 2, "rec_yds"] = 999999
    b = F.earlier_features(history, candidates)
    pd.testing.assert_frame_equal(a, b)
    assert a["hist_rec_yds"].item() == 10
    assert a["history_last_week"].item() == 1


def test_count_models_use_likelihood_and_cpu_limit():
    assert isinstance(make_member("pass_tds", "logreg").named_steps["model"].__class__.__name__, str)
    assert make_member("rec", "xgboost", 2).get_params()["model__objective"] == "count:poisson"
    assert make_member("rec_yds", "random_forest", 2).get_params()["model__n_jobs"] == 2


def test_meta_learning_cannot_see_target_week():
    history = pd.DataFrame({"season": [2022] * 200, "week": [1] * 100 + [2] * 100,
                            "actual": np.tile([0, 1], 100), "a": .3, "b": .6,
                            "raw_equal": .45, "raw_weighted": .45, "raw_stacked": .45})
    first, _, state = combine("anytime_td", {"a": np.array([.2]), "b": np.array([.7])}, history, 2)
    history.loc[history["week"] == 2, "actual"] = 1
    second, _, _ = combine("anytime_td", {"a": np.array([.2]), "b": np.array([.7])}, history, 2)
    assert state["history_rows"] == 100
    assert state["meta_max_week"] == 1
    for k in first:
        np.testing.assert_array_equal(first[k], second[k])


def test_first_td_probability_mass_and_none():
    p = first_td_reweight([.4, .5], [.5, .6], [.8, .3], .1)
    assert p.sum() == pytest.approx(1)
    assert p[-1] == .1
    assert p[0] > .4
    np.testing.assert_array_equal(first_td_reweight([0, 0], [0, 0], [0, 0], 1), [0, 0, 1])


def test_anchor_market_independence_and_sign(league, feature_store):
    anchor = IndependentAnchor().fit(feature_store)
    target = feature_store[feature_store["season"] == 2022].head(3).copy()
    a = anchor.predict(target)
    target["spread_line"], target["total_line"], target["home_moneyline"] = 99, 999, 99999
    pd.testing.assert_frame_equal(a, anchor.predict(target))
    assert not any("market" in c or "line" in c or "moneyline" in c for c in anchor.columns)
    assert spread_label("SF", "CHI", 6.5) == "SF -6.5"
    assert spread_label("SF", "CHI", -6.5) == "CHI -6.5"
    assert (a["total_q10"] <= a["total_q50"]).all()


def test_td_instrumentation_preserves_v1_random_stream():
    from lab.props import sim
    from test_props import _toy_tables
    T = _toy_tables()
    teams, players = sim.neutral_game()
    a = sim.simulate(T, teams, players, 100, [0, 0], np.random.default_rng(1))
    b = sim.simulate(T, teams, players, 100, [0, 0], np.random.default_rng(1), record_td=True)
    np.testing.assert_array_equal(a["points"], b["points"])
    for k in a["stats"]:
        np.testing.assert_array_equal(a["stats"][k], b["stats"][k])
    assert np.array_equal(b["stats"]["pass_tds"].sum(1), b["stats"]["rec_tds"].sum(1))
    assert np.all((b["first_td_col"] == -1) == (b["stats"]["anytime_td"].sum(1) == 0))


def test_longrun_dev_only_disables_later_finalization(monkeypatch):
    from lab import longrun
    captured = {}
    def create(*a, **kw):
        captured.update(kw)
        return "fixture"
    monkeypatch.setattr(longrun, "create_job", create)
    monkeypatch.setattr(longrun, "launch_detached", lambda *a, **kw: 1)
    longrun.main(["start", "--hours", "1", "--threads", "7", "--dev-only"])
    assert captured["finalize_after"] is False


def test_combinations_report_actual_available_members_only():
    from lab.props.ensemble.run import chronological_combinations
    frame = pd.DataFrame({"game_id": ["g1", "g2"], "pid": ["p1", "p2"], "season": 2022,
                          "week": [1, 2], "stat": "rec", "actual": [1, 2],
                          "logreg": [1., 2.], "random_forest": [3., 4.], "sim_independent": [np.nan, 3.]})
    out = chronological_combinations(frame).set_index("game_id")
    assert out.loc["g1", "equal"] == 2
    assert out.loc["g1", "members"] == "logreg,random_forest"
    assert out.loc["g2", "members"].endswith("sim_independent")
    assert out.loc["g2", "meta_rows"] == 0  # no structural history to weight this member set
    frame["simulator_v1"] = [1000., 1000.]
    independent = chronological_combinations(frame).set_index("game_id")
    assert independent.loc["g1", "equal"] == 2
    assert "simulator_v1" not in independent.loc["g1", "members"]
    market = chronological_combinations(frame, variant="market-informed").set_index("game_id")
    assert market.loc["g1", "equal"] > 100
