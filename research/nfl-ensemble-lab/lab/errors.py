"""Phase 7 error analysis (DESCRIPTIVE ONLY: nothing here selects features, models or thresholds).

Source: the champion run's walk-forward out-of-sample predictions (each season predicted by models
trained on earlier seasons). Seasons are labelled by role: development 2018-22, validation 2023-24
(already inspected), 2025 diagnostic, 2026 retrospective walk-forward (not timestamped; the
timestamped prospective record is the snapshot archive, summarised separately).
Post-hoc facts (who actually started at QB) are used only to describe errors, never as inputs.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import metrics as M
from .config import ARTIFACTS_DIR
from .ensemble import MODEL_KEYS

OUT = ARTIFACTS_DIR / "phase7"


def _role(s: int) -> str:
    return "development 2018-22" if s <= 2022 else "validation 2023-24 (inspected)" if s <= 2024 else \
        "diagnostic 2025" if s == 2025 else "2026 walk-forward"


def _summ(d: pd.DataFrame, p="p", label=None) -> dict:
    y = d["home_win"].to_numpy()
    out = {"games": int(len(d)), "log_loss": M.log_loss(y, d[p].to_numpy()) if len(d) else np.nan,
           "accuracy": float(((d[p] > 0.5) == (y == 1)).mean()) if len(d) else np.nan}
    if "p_market" in d and d["p_market"].notna().all() and len(d):
        out["market_log_loss"] = M.log_loss(y, d["p_market"].to_numpy())
    return out | ({"bucket": label} if label is not None else {})


def build(version: str | None = None) -> dict:
    from .data_pipeline import GAMES_TABLE, load_feature_store
    from .training import current_version
    from .config import ARTIFACTS_DIR as A
    version = version or current_version()
    oof = pd.read_parquet(A / "runs" / version / "oof_predictions.parquet")
    oof = oof[oof["home_win"].notna()].copy()
    oof["p"] = oof["p_weighted_average"]
    oof["role"] = oof["season"].map(_role)
    fs = load_feature_store().set_index("game_id")
    g = pd.read_parquet(GAMES_TABLE).set_index("game_id")
    x = oof.set_index("game_id")
    cols = [c for c in fs.columns if c.endswith(("qb_projected_id", "qb_change", "qb_known", "inj_report_available",
                                                 "p5_off_loss", "p5_def_loss", "p5_model_staleness_days", "qb7_projected_id"))
            and c.startswith(("home_", "away_"))]
    x = x.join(fs[cols]).join(g[["home_qb_id", "away_qb_id"]])
    x = x.reset_index()
    res = {"version": version, "games": int(len(x))}

    # 1. do the six models make the same mistakes?
    P = x[[f"p_{k}" for k in MODEL_KEYS]]
    R = P.rsub(x["home_win"], axis=0)
    res["residual_correlation"] = R.corr().round(3)
    ev = np.clip(np.linalg.eigvalsh(np.nan_to_num(R.corr().to_numpy())), 0, None)
    res["effective_models"] = float(ev.sum() ** 2 / (ev ** 2).sum())
    wrong = (P.gt(0.5)).ne(x["home_win"].eq(1), axis=0)
    x["n_models_wrong"] = wrong.sum(axis=1)
    res["wrong_count_distribution"] = x["n_models_wrong"].value_counts().sort_index().rename("games").reset_index()
    res["all_six_wrong_share"] = float((x["n_models_wrong"] == 6).mean())
    res["ensemble_wrong_share"] = float(((x["p"] > 0.5) != (x["home_win"] == 1)).mean())

    # 2. buckets (each row: one bucket within one season role)
    x["qb_proj_correct"] = np.where(x["home_qb_id"].isna() | x["away_qb_id"].isna(), np.nan,
                                    ((x["home_qb_projected_id"] == x["home_qb_id"]) & (x["away_qb_projected_id"] == x["away_qb_id"])).astype(float))
    x["qb7_proj_correct"] = np.where(x["home_qb_id"].isna() | x["away_qb_id"].isna(), np.nan,
                                     ((x["home_qb7_projected_id"] == x["home_qb_id"]) & (x["away_qb7_projected_id"] == x["away_qb_id"])).astype(float))
    x["disagreement"] = P.std(axis=1)
    x["inj_loss"] = (x["home_p5_off_loss"].abs() + x["home_p5_def_loss"].abs() + x["away_p5_off_loss"].abs() + x["away_p5_def_loss"].abs())
    x["conf"] = (x["p"] - 0.5).abs()
    defs = {
        "QB projection (post-hoc: both projected starters started?)": x["qb_proj_correct"].map({1.0: "both correct", 0.0: "at least one wrong"}),
        "QB change flagged pregame": np.where((x["home_qb_change"] + x["away_qb_change"]) > 0, "QB change projected", "no projected change"),
        "Model disagreement (std of six probabilities)": pd.qcut(x["disagreement"], 3, labels=["low", "medium", "high"]).astype(str),
        "Projected injury loss (Phase 5 player model)": pd.qcut(x["inj_loss"].rank(method="first"), 3, labels=["low", "medium", "high"]).astype(str),
        "Verified injury report": np.where((x["home_inj_report_available"] + x["away_inj_report_available"]) == 2, "both teams", "missing for a team"),
        "Player model staleness": np.where(x["home_p5_model_staleness_days"] > 14, "stale (>14 days)", "current"),
        "Ensemble confidence": pd.cut(x["conf"], [-0.01, 0.1, 0.2, 0.3, 0.5], labels=["<60%", "60-70%", "70-80%", ">80%"]).astype(str),
    }
    rows = []
    for name, b in defs.items():
        for (role, val), d in x.assign(_b=b).groupby(["role", "_b"]):
            if val in ("nan", "None") or pd.isna(val):
                continue
            rows.append({"factor": name, "seasons": role} | _summ(d, label=val))
    res["buckets"] = pd.DataFrame(rows)

    # 3. overconfidence: predicted vs observed by confidence band (pooled, then per role)
    cal = []
    for (role, band), d in x.assign(band=defs["Ensemble confidence"]).groupby(["role", "band"]):
        fav = np.where(d["p"] > 0.5, d["p"], 1 - d["p"])
        won = np.where(d["p"] > 0.5, d["home_win"], 1 - d["home_win"])
        cal.append({"seasons": role, "confidence": band, "games": len(d), "predicted_favourite_win": float(fav.mean()),
                    "observed_favourite_win": float(won.mean()), "gap": float(won.mean() - fav.mean())})
    res["calibration"] = pd.DataFrame(cal)

    # 4. QB projection agreement (diagnostic): old rule vs v2
    agree = []
    for role, d in x.groupby("role"):
        agree.append({"seasons": role, "games": len(d), "old_rule_both_correct": float(d["qb_proj_correct"].mean()),
                      "v2_both_correct": float(d["qb7_proj_correct"].mean())})
    res["qb_agreement"] = pd.DataFrame(agree)

    # 5. hardest misses: all six wrong with high confidence (descriptive list)
    worst = x[(x["n_models_wrong"] == 6)].assign(miss=lambda d: (d["p"] - d["home_win"]).abs()).sort_values("miss", ascending=False)
    res["worst_misses"] = worst[["game_id", "season", "home_team", "away_team", "p", "home_win", "margin", "p_market",
                                 "qb_proj_correct", "disagreement"]].head(25)
    res["prospective"] = _prospective()
    _save(res)
    return res


def _prospective() -> dict:
    from .prospective import scored_table
    t = scored_table()
    if t is None or not len(t):
        return {"note": "no prospective game has been played and scored yet"}
    rows = [{"window": w, **_summ(d.assign(p=d["p_home"]))} for w, d in t.groupby("window")]
    return {"by_window": rows, "note": "descriptive only; too few games for any conclusion"}


def _save(res: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    flat = {}
    for k, v in res.items():
        if isinstance(v, pd.DataFrame):
            v.to_csv(OUT / f"errors_{k}.csv", index=k == "residual_correlation")
        else:
            flat[k] = v
    (OUT / "errors_summary.json").write_text(json.dumps(flat, indent=2, default=str))


def load() -> dict:
    p = OUT / "errors_summary.json"
    if not p.exists():
        return {}
    res = json.loads(p.read_text())
    for k in ("buckets", "calibration", "qb_agreement", "worst_misses", "wrong_count_distribution"):
        f = OUT / f"errors_{k}.csv"
        if f.exists():
            res[k] = pd.read_csv(f)
    f = OUT / "errors_residual_correlation.csv"
    if f.exists():
        res["residual_correlation"] = pd.read_csv(f, index_col=0)
    return res
