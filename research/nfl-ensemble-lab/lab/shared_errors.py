"""Phase 7.1: why the six models make the same mistakes (DESCRIPTIVE; nothing is fitted or selected here).

Uses the champion's walk-forward out-of-sample predictions. The closing market line (from nfldata) is
used only as a post-hoc proxy for "information available before kickoff"; it is never a model input.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR
from .ensemble import MODEL_KEYS

OUT = ARTIFACTS_DIR / "phase7"


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _r2(y, X) -> float:
    X = np.c_[np.ones(len(X)), X]
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(1 - np.var(y - X @ b) / np.var(y))


def build(version: str | None = None) -> dict:
    from .data_pipeline import load_feature_store
    from .training import current_version, load_bundle
    version = version or current_version()
    b = load_bundle(version)
    oof = pd.read_parquet(ARTIFACTS_DIR / "runs" / version / "oof_predictions.parquet")
    oof = oof[oof["home_win"].notna()].reset_index(drop=True)
    fs = load_feature_store().set_index("game_id")
    x = oof.join(fs[[c for c in ("diff_rating_margin", "diff_qb_eff", "home_qb_change", "away_qb_change", "home_qb_projected_id",
                                 "away_qb_projected_id") if c in fs]], on="game_id")
    from .data_pipeline import GAMES_TABLE
    g = pd.read_parquet(GAMES_TABLE).set_index("game_id")[["home_qb_id", "away_qb_id"]]
    x = x.join(g, on="game_id")
    res = {"version": version, "games": int(len(x))}

    # 1. shared inputs
    per_model = b.get("features_by_model") or {}
    res["inputs"] = ("All six models receive the identical feature list" if not per_model else "Models use per-model feature lists") + \
        f" ({len(b['features'])} features from {len(b['groups'])} groups: {', '.join(b['groups'])})."

    # 2. how much of each model is one shared signal
    L = pd.DataFrame({k: _logit(x[f"p_{k}"]) for k in MODEL_KEYS})
    rows = []
    for k in MODEL_KEYS:
        rows.append({"model": k,
                     "r2_on_rating_margin_diff_alone": _r2(L[k].to_numpy(), x[["diff_rating_margin"]].fillna(0).to_numpy()),
                     "r2_on_rating_and_qb": _r2(L[k].to_numpy(), x[["diff_rating_margin", "diff_qb_eff"]].fillna(0).to_numpy()),
                     "r2_on_market_logit": _r2(L[k].to_numpy(), _logit(x["p_market"].fillna(0.5)).reshape(-1, 1)),
                     "r2_on_other_five_mean": _r2(L[k].to_numpy(), L.drop(columns=[k]).mean(axis=1).to_numpy().reshape(-1, 1))})
    res["shared_signal"] = pd.DataFrame(rows)
    ev = np.clip(np.linalg.eigvalsh(np.corrcoef(L.T.to_numpy())), 0, None)
    res["first_component_share_of_prediction_variance"] = float(ev.max() / ev.sum())

    # 3. is agreement presented as confidence? accuracy by vote split vs what the probability already implied
    votes = (pd.DataFrame({k: x[f"p_{k}"] > 0.5 for k in MODEL_KEYS}).sum(axis=1))
    split = votes.map(lambda v: f"{max(v, 6 - v)}-{min(v, 6 - v)}")
    fav_p = np.where(x["p_weighted_average"] > 0.5, x["p_weighted_average"], 1 - x["p_weighted_average"])
    fav_won = np.where(x["p_weighted_average"] > 0.5, x["home_win"], 1 - x["home_win"])
    vs = pd.DataFrame({"split": split, "fav_p": fav_p, "fav_won": fav_won})
    res["vote_split"] = vs.groupby("split").agg(games=("fav_p", "size"), ensemble_predicted=("fav_p", "mean"),
                                                observed=("fav_won", "mean")).reset_index()
    # within similar probability bands, does unanimity add accuracy?
    band = pd.cut(vs["fav_p"], [0.5, 0.6, 0.7, 1.0], labels=["50-60%", "60-70%", ">70%"])
    res["unanimity_within_band"] = vs.assign(band=band, unanimous=split.eq("6-0")).groupby(["band", "unanimous"], observed=True).agg(
        games=("fav_p", "size"), predicted=("fav_p", "mean"), observed=("fav_won", "mean")).reset_index()

    # 4. common misses: what was knowable before kickoff?
    wrong = pd.DataFrame({k: (x[f"p_{k}"] > 0.5) != (x["home_win"] == 1) for k in MODEL_KEYS}).all(axis=1)
    mk = x["p_market"]
    market_right = ((mk > 0.5) == (x["home_win"] == 1)) & mk.notna()
    qb_wrong = ~((x["home_qb_projected_id"] == x["home_qb_id"]) & (x["away_qb_projected_id"] == x["away_qb_id"]))
    aw = x[wrong]
    res["all_six_wrong"] = {
        "games": int(wrong.sum()), "share": float(wrong.mean()),
        "market_also_wrong": float((~market_right[wrong]).mean()),
        "market_right_models_wrong": float(market_right[wrong].mean()),
        "qb_projection_wrong_in_these": float(qb_wrong[wrong].mean()), "qb_projection_wrong_overall": float(qb_wrong.mean()),
        "mean_abs_model_vs_market_gap": float((aw["p_weighted_average"] - aw["p_market"]).abs().mean()),
        "mean_abs_model_vs_market_gap_overall": float((x["p_weighted_average"] - x["p_market"]).abs().mean())}
    by = []
    for nm, m in (("QB projection wrong (post-hoc)", qb_wrong), ("QB projection right", ~qb_wrong)):
        by.append({"group": nm, "games": int(m.sum()), "all_six_wrong": float(wrong[m].mean()),
                   "market_right_when_all_six_wrong": float(market_right[m & wrong].mean()) if (m & wrong).any() else np.nan})
    res["by_qb"] = pd.DataFrame(by)
    _save(res)
    return res


def _save(res):
    OUT.mkdir(parents=True, exist_ok=True)
    flat = {}
    for k, v in res.items():
        if isinstance(v, pd.DataFrame):
            v.to_csv(OUT / f"shared_{k}.csv", index=False)
        else:
            flat[k] = v
    (OUT / "shared_summary.json").write_text(json.dumps(flat, indent=2, default=str))


def load() -> dict:
    p = OUT / "shared_summary.json"
    if not p.exists():
        return {}
    res = json.loads(p.read_text())
    for k in ("shared_signal", "vote_split", "unanimity_within_band", "by_qb"):
        f = OUT / f"shared_{k}.csv"
        if f.exists():
            res[k] = pd.read_csv(f)
    return res
