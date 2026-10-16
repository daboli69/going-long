"""Phase 2 engine tests. Synthetic data here validates SOFTWARE only; nothing in
these tests is an NFL finding."""
import numpy as np
import pandas as pd
import pytest

from lab import discovery as D

SEASONS = list(range(2018, 2026))
FAST = {"baselines": ["ensemble"], "rule_trees": 10, "pair_top_features": 8, "symbolic_top_features": 6,
        "gbm_top_features": 20, "n_clusters": 4}


def synthetic_base(effect: float, seed: int, n_per_season: int = 420):
    """Underdog-oriented base table with an optional planted interaction:
    logit(P(underdog wins)) = logit(p_dog) + effect * [dmf_a > 0.4 AND dog_b <= -0.3]."""
    rng = np.random.default_rng(seed)
    n = n_per_season * len(SEASONS)
    X = pd.DataFrame({f"dmf_f{i}": rng.normal(size=n) for i in range(12)})
    X["dmf_a"], X["dog_b"] = rng.normal(size=n), rng.normal(size=n)
    X["dog_inj_out_OL"] = np.where(rng.random(n) < 0.3, np.nan, rng.exponential(0.3, n))
    X["ctx_playoff"] = (rng.random(n) < 0.05).astype(float)
    p_dog = rng.uniform(0.15, 0.49, n)
    X["base_p_dog"] = p_dog
    planted = (X["dmf_a"] > 0.4) & (X["dog_b"] <= -0.3)
    y = (rng.random(n) < D.sigmoid(D.logit(p_dog) + effect * planted)).astype(float)
    season = np.repeat(SEASONS, n_per_season)
    meta = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)], "season": season, "week": 1, "split": "x",
                         "home_win": y, "train_seasons": [f"2016-{s - 1}" for s in season], "p_home": p_dog,
                         "dog_home": True, "y_dog": y, "p_dog": p_dog, "home_team": "AAA", "away_team": "BBB"})
    return {"meta": meta, "X": X, "baseline": "ensemble", "model_version": "synthetic"}


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    return D.run_experiment(FAST, progress=lambda m: None, base_loader=lambda b: synthetic_base(1.3, 1),
                            out_dir=tmp_path_factory.mktemp("planted"))


@pytest.fixture(scope="module")
def null(tmp_path_factory):
    return D.run_experiment(FAST, progress=lambda m: None, base_loader=lambda b: synthetic_base(0.0, 2),
                            out_dir=tmp_path_factory.mktemp("null"))


def test_planted_interaction_is_discovered_and_validated(planted):
    info = planted["summary"]["baselines"]["ensemble"]["origins"]["primary"]
    assert info["n_validated"] >= 1
    val = planted["bundle"][("ensemble", "primary")]["validated"]
    assert any({"dmf_a", "dog_b"} <= set(c.features) or "dmf_a" in c.features for c in val)
    # the planted effect also improves held-out log loss
    ev = info["evals"]["evaluation"]
    assert ev["validated_patterns"]["delta_log_loss"] < 0 or ev["gbm_residual"]["delta_log_loss"] < 0


def test_null_data_produces_no_validated_discoveries(null):
    for o in null["summary"]["baselines"]["ensemble"]["origins"].values():
        assert o["n_validated"] == 0
    assert all("not demonstrated" in v for v in null["summary"]["baselines"]["ensemble"]["verdict"].values())


def test_discovery_validation_evaluation_are_disjoint_and_ordered():
    base = synthetic_base(0.0, 3, n_per_season=120)
    meta = base["meta"]
    for o in D.DEFAULT_CONFIG["origins"]:
        d, v, e = (D._split(meta, o[k]) for k in ("discovery", "validation", "evaluation"))
        assert not (d & v).any() and not (v & e).any() and not (d & e).any()
        assert meta.loc[d, "season"].max() < meta.loc[v, "season"].min()
        assert meta.loc[v, "season"].max() < meta.loc[e, "season"].min()
        assert 2025 not in set(meta.loc[d | v | e, "season"])     # 2025 is diagnostic only


def test_in_sample_base_predictions_are_refused(monkeypatch):
    from lab import data_pipeline, training
    oof = pd.DataFrame({"game_id": ["g1"], "season": [2022], "week": [1], "split": ["development"], "home_win": [1.0],
                        "train_seasons": ["2016-2022"], "p_weighted_average": [0.6], "market_p_home_novig": [0.6]})
    monkeypatch.setattr(training, "load_run", lambda: {"oof": oof, "selection": {"champion": "weighted_average"}, "version": "x"})
    monkeypatch.setattr(data_pipeline, "load_feature_store", lambda: pd.DataFrame({"game_id": ["g1"], "features_built_at": [1]}))
    with pytest.raises(ValueError, match="in-sample"):
        D.load_base("ensemble")


def test_multiple_testing_helpers():
    pv = np.array([0.001, 0.01, 0.02, 0.5])
    np.testing.assert_allclose(D.holm(pv), [0.004, 0.03, 0.04, 0.5])
    q = D.bh_qvalues(pv)
    np.testing.assert_allclose(q, [0.004, 0.02, 0.026666666, 0.5], rtol=1e-6)


def test_offset_effect_recovers_planted_logodds():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.2, 0.5, 20000)
    x = (rng.random(20000) < 0.3).astype(float)
    y = (rng.random(20000) < D.sigmoid(D.logit(p) + 0.7 * x)).astype(float)
    b, se = D.offset_effect(x, y, p)
    assert abs(b - 0.7) < 3 * se


def test_orientation_and_missing_injuries():
    fs = pd.DataFrame({"diff_blend_epa_pp": [0.1, 0.1], "home_inj_out_OL": [0.5, np.nan], "away_inj_out_OL": [0.0, np.nan],
                       "ctx_home_field": [1, 1]})
    X, dog_home = D.orient(fs, np.array([0.3, 0.7]))
    assert list(dog_home) == [True, False]
    assert X["dmf_blend_epa_pp"].tolist() == [0.1, -0.1]          # underdog minus favorite
    assert X["dog_inj_out_OL"].iloc[0] == 0.5 and np.isnan(X["dog_inj_out_OL"].iloc[1])   # missing stays missing
    np.testing.assert_allclose(X["base_p_dog"], [0.3, 0.3])
    spec = {"type": "conds", "conds": [("dog_inj_out_OL", "gt", 0.2)]}
    m = D.eval_mask(spec, X, {})
    assert m[0] == 1 and np.isnan(m[1])                             # not evaluable, not "false"


def test_reproducible(tmp_path):
    a = D.run_experiment(FAST, progress=lambda m: None, base_loader=lambda b: synthetic_base(0.8, 5, 200), out_dir=tmp_path / "a")
    b = D.run_experiment(FAST, progress=lambda m: None, base_loader=lambda b: synthetic_base(0.8, 5, 200), out_dir=tmp_path / "b")
    ca = pd.read_csv(a["dir"] / "catalog_ensemble_primary.csv")
    cb = pd.read_csv(b["dir"] / "catalog_ensemble_primary.csv")
    pd.testing.assert_frame_equal(ca, cb)


def test_artifacts_are_read_only(planted):
    import os
    for f in planted["dir"].iterdir():
        assert not os.access(f, os.W_OK)
