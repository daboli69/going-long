"""Phase 8 evaluation: standalone specialist metrics and the pre-registered combination experiment.

Exactly the comparisons in docs/PHASE8_PREREGISTRATION.md: R (recalibrated champion) vs S_A..S_F, the selected
combination and the constrained stack; walk-forward, development 2019-22 (decision), 2023-25 (research-exposed check),
2026 completed games (descriptive). Holm m = 8 on one-sided paired bootstrap p-values.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

from .. import metrics as M
from .core import OUT, SPECIALISTS, _logit

DEV, CHECK = (2019, 2020, 2021, 2022), (2023, 2024, 2025)
KEYS = [s.key for s in SPECIALISTS]


def _ece(y, p, bins=10):
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(y[b == k].mean() - p[b == k].mean()) * (b == k).mean() for k in range(bins) if (b == k).any()))


def _window(s):
    return "development 2018-22" if s <= 2022 else "research-exposed 2023-25" if s <= 2025 else "live 2026"


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    sp = pd.read_parquet(OUT / "specialist_oof.parquet")
    g = pd.read_parquet(OUT / "research_games.parquet")
    wide = sp.pivot_table(index="game_id", columns="specialist", values="p_home", dropna=False)
    wide.columns = [f"p_{c}" for c in wide.columns]
    e = sp[sp["specialist"] == "E"].set_index("game_id")[["margin", "total"] + [c for c in ("margin_p10", "margin_p90", "total_p10", "total_p90") if c in sp]]
    g = g.join(wide, on="game_id").join(e.add_prefix("E_"), on="game_id")
    return g, sp


def standalone() -> pd.DataFrame:
    g, _ = load()
    d = g[g["home_win"].notna() & g["p_weighted_average"].notna()].copy()
    d["window"] = d["season"].map(_window)
    rows = []
    for w, x in d.groupby("window"):
        y = x["home_win"].to_numpy()
        lc = _logit(x["p_weighted_average"])
        for k in ["champion"] + KEYS:
            p = x["p_weighted_average"] if k == "champion" else x[f"p_{k}"]
            ok = p.notna().to_numpy()
            if ok.sum() < 30:
                continue
            pp, yy = p.to_numpy()[ok], y[ok]
            r = {"window": w, "model": k, "games": int(ok.sum()), "log_loss": M.log_loss(yy, pp), "brier": float(np.mean((pp - yy) ** 2)),
                 "accuracy": float(((pp > 0.5) == (yy == 1)).mean()), "ece": _ece(yy, pp),
                 "champion_log_loss_same_games": M.log_loss(yy, x["p_weighted_average"].to_numpy()[ok])}
            if k != "champion":
                ls = _logit(pp)
                r["pred_corr_with_champion"] = float(np.corrcoef(ls, lc[ok])[0, 1])
                r["error_corr_with_champion"] = float(np.corrcoef(yy - pp, yy - x["p_weighted_average"].to_numpy()[ok])[0, 1])
                # incremental information: does the specialist logit add to the champion logit? (likelihood ratio)
                X0, X1 = lc[ok].reshape(-1, 1), np.c_[lc[ok], ls]
                m0 = LogisticRegression(C=1e6, max_iter=1000).fit(X0, yy)
                m1 = LogisticRegression(C=1e6, max_iter=1000).fit(X1, yy)
                lr = 2 * len(yy) * (M.log_loss(yy, m0.predict_proba(X0)[:, 1]) - M.log_loss(yy, m1.predict_proba(X1)[:, 1]))
                r["incremental_lr_stat"], r["incremental_p"], r["incremental_coef"] = float(lr), float(stats.chi2.sf(max(lr, 0), 1)), float(m1.coef_[0][1])
            if k == "E":
                r["margin_mae"] = float((x["E_margin"] - (x["home_score"] - x["away_score"])).abs().mean())
                r["champion_margin_mae"] = float((x["margin_ensemble"] - (x["home_score"] - x["away_score"])).abs().mean())
            rows.append(r)
    for w, x in d.groupby("window"):                                   # simple baselines
        y = x["home_win"].to_numpy()
        hp = np.full(len(y), d[d["season"] < x["season"].min()]["home_win"].mean() if (d["season"] < x["season"].min()).any() else 0.56)
        rows.append({"window": w, "model": "baseline: home-win rate", "games": len(y), "log_loss": M.log_loss(y, hp),
                     "brier": float(np.mean((hp - y) ** 2)), "accuracy": float((y == 1).mean())})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "standalone.csv", index=False)
    return out


# --------------------------------------------------------------------------- combination experiment

def _fit_predict(Xtr, ytr, Xte, C):
    m = LogisticRegression(C=C, max_iter=2000).fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1]


def _design(x, keys):
    cols = [_logit(x["p_weighted_average"])]
    for k in keys:
        p = x[f"p_{k}"]
        cols += [np.where(p.notna(), _logit(p.fillna(0.5)), 0.0), p.isna().astype(float).to_numpy()]
    return np.column_stack(cols)


def combo_predictions(g: pd.DataFrame, keys: list[str], C: float) -> pd.Series:
    d = g[g["p_weighted_average"].notna()]
    out = pd.Series(np.nan, index=d.index)
    for s in sorted(d["season"].unique()):
        tr = d[(d["season"] < s) & d["home_win"].notna()]
        if keys:
            tr = tr[tr[[f"p_{k}" for k in keys]].notna().any(axis=1) | True]
        te = d[d["season"] == s]
        if len(tr) < 200:
            continue
        out.loc[te.index] = _fit_predict(_design(tr, keys), tr["home_win"].to_numpy(), _design(te, keys), C)
    return out


def _gain(y, p_base, p_new, rng, n_boot=5000):
    lb = -(y * np.log(np.clip(p_base, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p_base, 1e-6, 1)))
    ln = -(y * np.log(np.clip(p_new, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p_new, 1e-6, 1)))
    d = lb - ln
    bs = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)])
    return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), float((bs <= 0).mean())


def experiment(n_boot: int = 5000) -> dict:
    g, _ = load()
    g = g[g["p_weighted_average"].notna()].copy()
    rng = np.random.default_rng(0)
    preds = {"R": combo_predictions(g, [], 1e6)}
    for k in KEYS:
        preds[f"S_{k}"] = combo_predictions(g, [k], 1.0)
    done = g["home_win"].notna()
    devm = g["season"].isin(DEV) & done & preds["R"].notna()

    def ll(p, m):
        return M.log_loss(g.loc[m, "home_win"].to_numpy(), p[m].to_numpy())
    selected = [k for k in KEYS if ll(preds["R"], devm) - ll(preds[f"S_{k}"], devm) > 0]
    preds["SELECTED"] = combo_predictions(g, selected, 1.0) if selected else preds["R"]
    preds["STACK"] = combo_predictions(g, KEYS, 0.3)
    six = None
    rows = []
    for name in [n for n in preds if n != "R"]:
        r = {"comparison": name, "specialists": ",".join(selected) if name == "SELECTED" else ("all" if name == "STACK" else name[2:])}
        for wname, seasons in (("dev_2019_22", DEV), ("check_2023_25", CHECK), ("live_2026", (2026,))):
            m = g["season"].isin(seasons) & done & preds["R"].notna() & preds[name].notna()
            if m.sum() < 20:
                continue
            y = g.loc[m, "home_win"].to_numpy()
            gain, lo, hi, p = _gain(y, preds["R"][m].to_numpy(), preds[name][m].to_numpy(), rng, n_boot)
            r |= {f"{wname}_games": int(m.sum()), f"{wname}_gain": gain, f"{wname}_ci_low": lo, f"{wname}_ci_high": hi, f"{wname}_p": p,
                  f"{wname}_brier_gain": float(np.mean((preds["R"][m] - y) ** 2) - np.mean((preds[name][m] - y) ** 2))}
        rows.append(r)
    res = pd.DataFrame(rows)
    order = res["dev_2019_22_p"].sort_values().index
    m_, run, adj = len(res), 0.0, {}
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m_ - rank) * res.loc[i, "dev_2019_22_p"]))
        adj[i] = run
    res["dev_p_holm"] = pd.Series(adj)
    res["qualifies"] = (res["dev_2019_22_gain"] > 0) & (res["dev_p_holm"] < 0.05) & (res.get("check_2023_25_gain", 0) >= 0)
    # calibration-only reference: recalibrated champion vs raw champion on the same games
    calib = {}
    for wname, seasons in (("dev_2019_22", DEV), ("check_2023_25", CHECK)):
        m = g["season"].isin(seasons) & done & preds["R"].notna()
        y = g.loc[m, "home_win"].to_numpy()
        calib[wname] = {"raw_champion": M.log_loss(y, g.loc[m, "p_weighted_average"].to_numpy()), "recalibrated": M.log_loss(y, preds["R"][m].to_numpy())}
    # shared-error games: does a combination help where all six original models were wrong?
    from .baseline import load_oof
    oof = load_oof().set_index("game_id")
    from ..ensemble import MODEL_KEYS
    wrong6 = oof[[f"p_{k}" for k in MODEL_KEYS]].gt(0.5).ne(oof["home_win"].eq(1), axis=0).all(axis=1)
    sh = []
    for name in preds:
        if name == "R":
            continue
        for wname, seasons in (("dev_2019_22", DEV), ("check_2023_25", CHECK)):
            m = g["season"].isin(seasons) & done & preds["R"].notna() & preds[name].notna()
            ww = g.loc[m, "game_id"].map(wrong6).fillna(False).to_numpy()
            y = g.loc[m, "home_win"].to_numpy()
            for sub, mask in (("all six wrong", ww), ("others", ~ww)):
                if mask.sum() < 10:
                    continue
                sh.append({"comparison": name, "window": wname, "subset": sub, "games": int(mask.sum()),
                           "gain": M.log_loss(y[mask], preds["R"][m].to_numpy()[mask]) - M.log_loss(y[mask], preds[name][m].to_numpy()[mask])})
    shared = pd.DataFrame(sh)
    # season-by-season stability
    seas = []
    for name in preds:
        if name == "R":
            continue
        for s in sorted(g["season"].unique()):
            m = (g["season"] == s) & done & preds["R"].notna() & preds[name].notna()
            if m.sum() < 20:
                continue
            y = g.loc[m, "home_win"].to_numpy()
            seas.append({"comparison": name, "season": int(s), "games": int(m.sum()),
                         "gain": M.log_loss(y, preds["R"][m].to_numpy()) - M.log_loss(y, preds[name][m].to_numpy())})
    seasons = pd.DataFrame(seas)
    P = pd.DataFrame(preds)
    P["game_id"], P["season"], P["home_win"] = g["game_id"], g["season"], g["home_win"]
    P.to_parquet(OUT / "combination_oof.parquet", index=False)
    res.to_csv(OUT / "experiment.csv", index=False)
    shared.to_csv(OUT / "experiment_shared_errors.csv", index=False)
    seasons.to_csv(OUT / "experiment_by_season.csv", index=False)
    (OUT / "experiment.json").write_text(json.dumps({"selected": selected, "calibration_reference": calib,
                                                     "results": res.to_dict("records")}, indent=2, default=str))
    return {"results": res, "selected": selected, "calibration": calib, "shared": shared, "seasons": seasons}


def load_results() -> dict:
    out = {}
    for k in ("standalone", "experiment", "experiment_shared_errors", "experiment_by_season"):
        f = OUT / f"{k}.csv"
        if f.exists():
            out[k] = pd.read_csv(f)
    j = OUT / "experiment.json"
    if j.exists():
        out |= {k: v for k, v in json.loads(j.read_text()).items() if k != "results"}
    return out
