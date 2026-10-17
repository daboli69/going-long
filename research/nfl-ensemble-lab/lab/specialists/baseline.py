"""Phase 8 step 2: diversity baseline of the original six models (frozen walk-forward OOF predictions).

Descriptive. Seasons are labelled by exposure: 2018-22 development, 2023-25 research-exposed, 2026 live season.
Only pregame columns are used to slice games; outcomes are used only to score.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import metrics as M
from ..config import ARTIFACTS_DIR
from ..ensemble import MODEL_KEYS

OUT = ARTIFACTS_DIR / "phase8"


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _ece(y, p, bins=10):
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(y[b == k].mean() - p[b == k].mean()) * (b == k).mean() for k in range(bins) if (b == k).any()))


def eff_models(L: np.ndarray) -> float:
    ev = np.clip(np.linalg.eigvalsh(np.nan_to_num(np.corrcoef(L.T))), 0, None)
    return float(ev.sum() ** 2 / (ev ** 2).sum())


def load_oof(version: str | None = None) -> pd.DataFrame:
    from ..data_pipeline import load_feature_store
    from ..training import current_version
    version = version or current_version()
    oof = pd.read_parquet(ARTIFACTS_DIR / "runs" / version / "oof_predictions.parquet")
    oof = oof[oof["home_win"].notna()].copy()
    fs = load_feature_store().set_index("game_id")
    keep = [c for c in ("diff_rating_margin", "ctx_div_game", "ctx_playoff", "ctx_neutral", "week") if c in fs]
    x = oof.join(fs[keep].rename(columns={"week": "fs_week"}), on="game_id")
    x["exposure"] = np.where(x["season"] <= 2022, "development 2018-22", np.where(x["season"] <= 2025, "research-exposed 2023-25", "live 2026"))
    return x


def build() -> dict:
    x = load_oof()
    y = x["home_win"].to_numpy()
    P = x[[f"p_{k}" for k in MODEL_KEYS]]
    L = pd.DataFrame({k: _logit(P[f"p_{k}"]) for k in MODEL_KEYS})
    res = {}
    res["prediction_correlation"] = L.corr().round(3)
    R = P.rsub(x["home_win"], axis=0).set_axis(MODEL_KEYS, axis=1)
    res["error_correlation"] = R.corr().round(3)
    # partial correlation after removing team strength (rating-margin difference) from each logit
    rm = x["diff_rating_margin"].fillna(0).to_numpy()
    X = np.c_[np.ones(len(rm)), rm]
    Lr = L.apply(lambda c: c - X @ np.linalg.lstsq(X, c.to_numpy(), rcond=None)[0])
    res["partial_correlation_given_rating"] = Lr.corr().round(3)
    res["effective_models"] = {"predictions": eff_models(L.to_numpy()), "errors": eff_models(R.to_numpy()),
                               "after_removing_rating": eff_models(Lr.to_numpy())}
    wrong = P.gt(0.5).ne(x["home_win"].eq(1), axis=0)
    res["simultaneous_failures"] = wrong.sum(axis=1).value_counts().sort_index().rename("games").reset_index().rename(columns={"index": "models_wrong"})
    # per-model metrics by exposure window
    rows = []
    for ex, d in x.groupby("exposure"):
        yy = d["home_win"].to_numpy()
        for k in list(MODEL_KEYS) + ["equal_average", "weighted_average"]:
            p = d[f"p_{k}"].to_numpy()
            mcol = f"margin_{k}" if f"margin_{k}" in d else ("margin_ensemble" if k == "weighted_average" else None)
            rows.append({"window": ex, "model": k, "games": len(d), "log_loss": M.log_loss(yy, p), "brier": float(np.mean((p - yy) ** 2)),
                         "accuracy": float(((p > 0.5) == (yy == 1)).mean()), "ece": _ece(yy, p),
                         "margin_mae": float((d[mcol] - d["margin"]).abs().mean()) if mcol else np.nan})
    res["metrics"] = pd.DataFrame(rows)
    # disagreement by favourite band and game type
    x["disagreement"] = P.std(axis=1)
    fav = np.where(x["p_weighted_average"] > 0.5, x["p_weighted_average"], 1 - x["p_weighted_average"])
    x["fav_band"] = pd.cut(fav, [0.5, 0.6, 0.7, 0.8, 1.0], labels=["50-60%", "60-70%", "70-80%", ">80%"], include_lowest=True).astype(str)
    x["game_type"] = np.where(x["ctx_playoff"] == 1, "playoff", np.where(x["ctx_div_game"] == 1, "division", "other"))
    res["disagreement_by_band"] = x.groupby(["fav_band"]).agg(games=("disagreement", "size"), mean_std=("disagreement", "mean")).reset_index()
    res["disagreement_by_type"] = x.groupby(["game_type"]).agg(games=("disagreement", "size"), mean_std=("disagreement", "mean")).reset_index()
    # does disagreement carry information beyond the ensemble probability? (development seasons only, likelihood-ratio test)
    from scipy import stats
    from sklearn.linear_model import LogisticRegression
    dev = x[x["season"] <= 2022]
    le = _logit(dev["p_weighted_average"])
    dz = (dev["disagreement"] - dev["disagreement"].mean()) / dev["disagreement"].std()
    X0 = le.reshape(-1, 1)
    X1 = np.c_[le, dz, le * dz]
    m0 = LogisticRegression(C=1e6, max_iter=1000).fit(X0, dev["home_win"])
    m1 = LogisticRegression(C=1e6, max_iter=1000).fit(X1, dev["home_win"])
    ll0 = -M.log_loss(dev["home_win"], m0.predict_proba(X0)[:, 1]) * len(dev)
    ll1 = -M.log_loss(dev["home_win"], m1.predict_proba(X1)[:, 1]) * len(dev)
    res["disagreement_information"] = {"games": int(len(dev)), "lr_stat": float(2 * (ll1 - ll0)), "p_value": float(stats.chi2.sf(2 * (ll1 - ll0), 2)),
                                       "coef_disagreement": float(m1.coef_[0][1]), "coef_interaction": float(m1.coef_[0][2])}
    # confident unanimous misses
    conf = (P.min(axis=1) > 0.7) | (P.max(axis=1) < 0.3)
    cw = conf & wrong.all(axis=1)
    res["confident_unanimous"] = {"games": int(conf.sum()), "wrong": int(cw.sum()), "wrong_rate": float(cw.sum() / max(conf.sum(), 1)),
                                  "mean_predicted_favourite": float(np.where(x.loc[conf, "p_weighted_average"] > 0.5, x.loc[conf, "p_weighted_average"],
                                                                             1 - x.loc[conf, "p_weighted_average"]).mean())}
    res["confident_unanimous_misses"] = x.loc[cw, ["game_id", "season", "home_team", "away_team", "p_weighted_average", "margin", "p_market"]]
    _save(res)
    return res


def _save(res):
    import json
    OUT.mkdir(parents=True, exist_ok=True)
    flat = {}
    for k, v in res.items():
        if isinstance(v, pd.DataFrame):
            v.to_csv(OUT / f"baseline_{k}.csv", index=k.endswith("correlation") or k == "partial_correlation_given_rating")
        else:
            flat[k] = v
    (OUT / "baseline_summary.json").write_text(json.dumps(flat, indent=2, default=str))


def load() -> dict:
    import json
    p = OUT / "baseline_summary.json"
    if not p.exists():
        return {}
    r = json.loads(p.read_text())
    for f in OUT.glob("baseline_*.csv"):
        k = f.stem[len("baseline_"):]
        r[k] = pd.read_csv(f, index_col=0 if "correlation" in k else None)
    return r
