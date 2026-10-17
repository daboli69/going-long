import json

import numpy as np
import pandas as pd
import pytest

from lab import longrun as LR
from lab import prospective as P


@pytest.fixture(scope="module")
def analysed_job(trained):
    from lab import analyze_longrun as AL
    jid = LR.create_job(max_trials=30, threads=2, seed=5, finalize_after=False)
    LR.run_job(jid, progress=lambda m: None)
    LR.finalize(jid, progress=lambda m: None)
    AL.analyze(jid, top_k=5, progress=lambda m: None)
    return jid, AL.load(jid)


def test_fold_losses_match_stored_trial_values(analysed_job):
    import optuna
    from lab.analyze_longrun import _fold_losses
    jid, _ = analysed_job
    st = optuna.load_study(study_name="logreg", storage=f"sqlite:///{(LR.LR_DIR / jid / 'optuna.db').as_posix()}")
    for t in [t for t in st.trials if t.state.name == "COMPLETE"]:
        assert np.mean(_fold_losses(t)) == pytest.approx(t.value, abs=1e-9)


def test_analysis_outputs_and_candidate_rule(analysed_job):
    jid, a = analysed_job
    for k in ("top_trials", "group_frequency", "selection_noise_check", "ensemble_combinations", "candidates", "version_metrics"):
        assert k in a and len(a[k])
    g = a["group_frequency"]
    assert g["share_in_top"].between(0, 1).all()
    combos = a["ensemble_combinations"]
    assert len(combos) == 2 * 64 and (combos[combos["n_replaced"] == 0]["gain_2019_21"] == 0).all()
    c = a["candidates"]
    assert (c["qualifies_for_prospective_tracking"] == ((c["gain_2019_21"] > 0) & (c["gain_2022_check"] >= 0))).all()
    reg = P.challenger_registry()
    assert any(x["source"] == jid for x in reg.get("considered", []))


def test_challenger_evaluation_with_holm(monkeypatch):
    rng = np.random.default_rng(0)
    n = 200
    y = (rng.random(n) < 0.55).astype(float)
    p_champ = np.clip(0.55 + rng.normal(0, 0.1, n), 0.05, 0.95)
    good = np.clip(np.where(y == 1, p_champ + 0.08, p_champ - 0.08), 0.02, 0.98)      # clearly better challenger
    t = pd.DataFrame({"window": "final", "predicted_at": pd.Timestamp("2026-11-01", tz="UTC"), "home_win": y, "p_home": p_champ,
                      "chall_vGOOD": good, "chall_vSAME": p_champ})
    monkeypatch.setattr(P, "scored_table", lambda: t)
    monkeypatch.setattr(P, "challenger_registry", lambda: {"versions": [], "hypotheses": [
        {"version": "vGOOD", "label": "good", "registered_at": "2026-10-01T00:00:00+00:00"},
        {"version": "vSAME", "label": "same", "registered_at": "2026-10-01T00:00:00+00:00"},
        {"version": "vNONE", "label": "no games", "registered_at": "2026-10-01T00:00:00+00:00"}]})
    df = P.evaluate_challengers().set_index("challenger")
    assert df.loc["vGOOD", "status"].startswith("supported") and df.loc["vGOOD", "delta_log_loss"] < 0
    assert df.loc["vSAME", "status"] == "not supported"
    assert df.loc["vNONE", "status"] == "no scored games yet"
    small = t.iloc[:60]
    monkeypatch.setattr(P, "scored_table", lambda: small)
    df2 = P.evaluate_challengers().set_index("challenger")
    assert df2.loc["vGOOD", "status"].startswith("accumulating")       # never supported before 128 games
