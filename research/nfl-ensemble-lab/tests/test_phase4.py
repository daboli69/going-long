import json
import os
import threading
import time

import numpy as np
import pandas as pd
import pytest

from lab import advanced, explain
from lab import longrun as LR

K = pd.Timestamp("2024-09-08 17:00", tz="UTC")


def test_window_features_use_only_earlier_games():
    games = pd.DataFrame({"game_id": ["a", "b", "c", "d"], "season": [2023, 2024, 2024, 2024],
                          "kickoff_utc": [K - pd.Timedelta(days=200), K, K + pd.Timedelta(days=7), K + pd.Timedelta(days=14)],
                          "home_team": ["SEA"] * 4, "away_team": ["NYG"] * 4})
    tg = pd.DataFrame({"game_id": ["a", "b", "c"], "team": ["SEA"] * 3, "x": [1.0, 10.0, np.nan]})
    w = advanced.window_features(games, tg, "p4t_").set_index(["game_id", "team"])
    assert w.loc[("b", "SEA"), "p4t_blend_x"] == 1.0          # week 1: previous season only, not its own 10.0
    assert w.loc[("b", "SEA"), "p4t_l5_x"] == 1.0
    # game d sees a and b; c's value is missing and stays out of the averages
    assert w.loc[("d", "SEA"), "p4t_l5_x"] == pytest.approx(5.5)
    assert np.isnan(w.loc[("a", "SEA"), "p4t_blend_x"])        # nothing earlier: missing, not zero
    assert np.isnan(w.loc[("a", "NYG"), "p4t_l5_x"])


def test_defensive_mirror():
    off = pd.DataFrame({"game_id": ["g"], "team": ["SEA"], "pressure_allowed_rate": [0.3]})
    out = advanced._with_defense(off, {("g", "SEA"): "NYG", ("g", "NYG"): "SEA"}, {"pressure_allowed_rate": "pressure_rate"})
    assert out.set_index("team").loc["NYG", "def_pressure_rate"] == 0.3   # NYG's defense generated SEA's pressure


def test_factor_mapping_and_shares():
    assert explain.factor_of("diff_rating_margin") == "Opponent-adjusted strength"
    assert explain.factor_of("diff_l3_epa_pp") == "Recent form"
    assert explain.factor_of("diff_inj_out_OL") == "Player availability / injuries"
    assert explain.factor_of("diff_p4ngs_blend_ngs_cpoe") == "Next Gen Stats"
    assert explain.factor_of("diff_qb_eff") == "Quarterback"
    sh = explain.factor_shares({"all": {"diff_rating_margin": 0.3, "diff_l3_epa_pp": -0.1, "diff_qb_eff": 0.6}})
    assert sum(v["share"] for v in sh.values()) == pytest.approx(1.0)
    assert sh["Recent form"]["net"] < 0


@pytest.fixture(scope="module")
def lr_env(trained):
    return trained


def _run(max_trials, seed=7, finalize=False):
    jid = LR.create_job(max_trials=max_trials, threads=2, seed=seed, finalize_after=finalize)
    LR.run_job(jid, progress=lambda m: None)
    return jid


def test_all_six_families_get_trials(lr_env):
    jid = _run(12)
    t = pd.read_csv(LR.LR_DIR / jid / "trials.csv")
    assert len(t) == 12 and set(t["family"]) == set(LR.FAMILIES)
    assert (t.groupby("family").size() >= 2).all()
    st = LR.Job(jid).status()
    assert st["state"] == "completed" and st["trials_total"] == 12 and LR.active_job() is None


def test_resume_keeps_completed_trials(lr_env):
    jid = _run(6)
    first = pd.read_csv(LR.LR_DIR / jid / "trials.csv")
    job = LR.Job(jid)
    m = job.meta
    m["max_trials"] = 12
    job.save_meta(m)
    LR.run_job(jid, progress=lambda x: None)
    second = pd.read_csv(LR.LR_DIR / jid / "trials.csv")
    assert len(second) == 12 and job.meta["resumes"] == 1
    merged = first.merge(second, on=["family", "trial"], suffixes=("_a", "_b"))
    assert len(merged) == 6
    np.testing.assert_allclose(merged["dev_log_loss_a"].fillna(-1), merged["dev_log_loss_b"].fillna(-1))


def test_reproducible_with_same_seed(lr_env):
    a = pd.read_csv(LR.LR_DIR / _run(6, seed=11) / "trials.csv")
    b = pd.read_csv(LR.LR_DIR / _run(6, seed=11) / "trials.csv")
    cols = [c for c in a.columns if c != "seconds"]
    pd.testing.assert_frame_equal(a[cols], b[cols])


def test_stop_control_and_duplicate_lock(lr_env):
    jid = LR.create_job(minutes=30, threads=2, finalize_after=False)
    th = threading.Thread(target=LR.run_job, args=(jid,), kwargs={"progress": lambda m: None})
    th.start()
    for _ in range(100):
        if LR.active_job() == jid:
            break
        time.sleep(0.1)
    with pytest.raises(RuntimeError):
        LR.create_job(minutes=5)                       # a second job is refused while one runs
    time.sleep(1.0)
    LR.Job(jid).set_control("stop")
    th.join(timeout=120)
    assert LR.Job(jid).status()["state"] == "stopped" and LR.active_job() is None


def test_fold_evaluation_never_sees_its_own_outcomes(lr_env):
    data, groups = LR._prepare_data()
    p = {"groups": ["Opponent-adjusted ratings", "Efficiency differences (blended season)"], "max_features": 5,
         "calibration": "platt", "C": 0.1, "penalty": "l2"}
    a = LR.evaluate_config(data, "logreg", p, groups, (2021,))
    flipped = data.copy()
    m = flipped["season"] == 2021
    flipped.loc[m, "home_win"] = 1 - flipped.loc[m, "home_win"]
    b = LR.evaluate_config(flipped, "logreg", p, groups, (2021,))
    np.testing.assert_allclose(a["preds"][2021]["p"], b["preds"][2021]["p"])


def test_finalize_counts_validation_looks(lr_env):
    before = sum(1 for _ in open(LR.VAL_LEDGER)) if LR.VAL_LEDGER.exists() else 0
    jid = _run(6)
    r = LR.finalize(jid, progress=lambda m: None)
    assert r["validation_look"] == before + 1
    assert r["alpha_after_look_adjustment"] == pytest.approx(0.05 / (before + 1))
    assert {x["family"] for x in r["results"]} == set(LR.FAMILIES)


def test_challenger_bundle_with_per_model_features(lr_env):
    from lab import training, weekly
    from lab.data_pipeline import load_feature_store
    ov = {"logreg": {"groups": ["Opponent-adjusted ratings"], "max_features": 0, "calibration": "none", "C": 0.05, "penalty": "l2"}}
    cur = training.current_version()
    r = training.run_training(production=True, set_current=False, tag="ovtest", model_overrides=ov, progress=lambda m: None)
    assert training.current_version() == cur                       # champion untouched
    b = training.load_bundle(r["summary"]["version"])
    assert set(b["features_by_model"]["logreg"]) < set(b["features"])
    fs = load_feature_store()
    t, d = weekly.predict_games(fs[(fs["season"] == 2026) & (fs["week"] == 6)], b, training.load_run(r["summary"]["version"]))
    assert t["p_logreg"].between(0, 1).all() and len(d[0]["round2"]["logreg"]["all"]) == len(b["features_by_model"]["logreg"])
    assert "factor_net_by_model" in d[0]["round3"]


def test_discovery_look_count(tmp_path):
    from lab import discovery as D
    from test_discovery import FAST, synthetic_base
    a = D.run_experiment(FAST, progress=lambda m: None, base_loader=lambda b: synthetic_base(0.0, 4, 150), out_dir=tmp_path)
    b = D.run_experiment(FAST, progress=lambda m: None, base_loader=lambda b: synthetic_base(0.0, 4, 150), out_dir=tmp_path)
    assert a["summary"]["config"]["validation_look"] == 1 and b["summary"]["config"]["validation_look"] == 2
    assert b["summary"]["config"]["validation_alpha"] == pytest.approx(0.025)


def test_best_ignores_partial_scores_of_pruned_trials(lr_env):
    jid = _run(24, seed=3)
    t = pd.read_csv(LR.LR_DIR / jid / "trials.csv")
    assert t.loc[t["state"] == "PRUNED", "dev_log_loss"].isna().all()
    best = LR.Job(jid).status()["best"]
    for fam, b in best.items():
        complete = t[(t["family"] == fam) & (t["state"] == "COMPLETE")]["dev_log_loss"]
        assert b["dev_log_loss"] == pytest.approx(complete.min(), abs=1e-5)
