"""Phase 7.2: independence analysis and a pre-declared development-only experiment.

DECLARED BEFORE ANY RESULT WAS SEEN (2026-10-17):
  candidates
    A lineup          : champion groups + P72_LINEUP                           vs champion
    B lineup+matchup  : champion groups + P72_LINEUP + P72_MATCHUP             vs champion
    C beyond_player   : champion + P5_PLAYER + P7_SNAP + P72_LINEUP + P72_MATCHUP vs champion + P5_PLAYER + P7_SNAP
  models    : each family's champion hyperparameters (no search); equal-weight six-model ensemble
  seasons   : walk-forward development folds 2019-2022 only (2023-2025 untouched)
  rule      : gain > 0 on 2019-21 AND gain >= 0 on 2022 AND Holm-adjusted one-sided paired bootstrap
              p < 0.05 on pooled 2019-22 game-level log-loss differences (3 comparisons)
  registry  : at most one qualifying candidate (largest pooled gain) may become a frozen shadow challenger
Independence analysis is descriptive and uses development seasons 2016-2022 only.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import metrics as M
from .config import ARTIFACTS_DIR
from .features import DEFAULT_GROUPS, P5_PLAYER, P7_SNAP, P72_LINEUP, P72_MATCHUP
from .longrun import DEV_FOLDS, FAMILIES, _prepare_data, champion_family_config, evaluate_config

OUT = ARTIFACTS_DIR / "phase72"
SEL, CHECK = (2019, 2020, 2021), 2022
CANDIDATES = {
    "A_lineup": ([], [P72_LINEUP]),
    "B_lineup_matchup": ([], [P72_LINEUP, P72_MATCHUP]),
    "C_beyond_player": ([P5_PLAYER, P7_SNAP], [P72_LINEUP, P72_MATCHUP]),
}


# --------------------------------------------------------------------------- independence (descriptive, dev only)

def _resid(y, X):
    X = np.c_[np.ones(len(X)), X]
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ b, 1 - np.var(y - X @ b) / max(np.var(y), 1e-12)


def independence(progress=print) -> pd.DataFrame:
    from .training import current_version, load_bundle
    data, groups = _prepare_data()
    oof = pd.read_parquet(ARTIFACTS_DIR / "runs" / current_version() / "oof_predictions.parquet")[["game_id", "margin_ensemble", "p_weighted_average"]]
    d = data[data["season"].between(2018, 2022)].merge(oof, on="game_id", how="inner")
    base_cols = [c for c in load_bundle()["features"] if c in d]
    Xb = d[base_cols].astype(float).fillna(d[base_cols].astype(float).mean()).to_numpy()
    Xb = (Xb - Xb.mean(0)) / np.where(Xb.std(0) > 0, Xb.std(0), 1)
    margin_res = (d["home_score"] - d["away_score"] - d["margin_ensemble"]).to_numpy()
    rng = np.random.default_rng(0)
    rows = []
    cand = {g: groups.get(g, []) for g in (P72_LINEUP, P72_MATCHUP, P5_PLAYER, P7_SNAP)}
    for g, cols in cand.items():
        for c in cols:
            x = d[c].astype(float)
            ok = x.notna().to_numpy()
            if ok.sum() < 200 or x[ok].std() == 0:
                continue
            r, r2 = _resid(x[ok].to_numpy(), Xb[ok])
            mr = margin_res[ok]
            corr = float(np.corrcoef(r, mr)[0, 1]) if r.std() > 0 else 0.0
            bs = []
            for _ in range(300):
                i = rng.integers(0, len(r), len(r))
                bs.append(np.corrcoef(r[i], mr[i])[0, 1] if r[i].std() > 0 else 0.0)
            rows.append({"group": g, "feature": c, "games": int(ok.sum()), "r2_explained_by_champion_features": float(r2),
                         "residual_corr_with_champion_margin_error": corr, "ci95_low": float(np.percentile(bs, 2.5)),
                         "ci95_high": float(np.percentile(bs, 97.5))})
    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "independence.csv", index=False)
    return out


# --------------------------------------------------------------------------- dev-only experiment

def _ens(preds, name, seasons):
    return {s: np.mean([preds[(f, name)][s]["p"] for f in FAMILIES], axis=0) for s in seasons}


def _eff_models(preds, name):
    L = np.column_stack([np.concatenate([preds[(f, name)][s]["p"] for s in DEV_FOLDS]) for f in FAMILIES])
    L = np.log(np.clip(L, 1e-6, 1 - 1e-6) / (1 - np.clip(L, 1e-6, 1 - 1e-6)))
    ev = np.clip(np.linalg.eigvalsh(np.corrcoef(L.T)), 0, None)
    return float(ev.sum() ** 2 / (ev ** 2).sum())


def experiment(threads: int = 4, n_boot: int = 5000, progress=print) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    data, groups = _prepare_data()
    configs = {"champion": []}
    for name, (base_extra, new) in CANDIDATES.items():
        configs[name] = base_extra + new
        if base_extra:
            configs[f"{name}__baseline"] = base_extra
    preds = {}
    for fam in FAMILIES:
        base = champion_family_config(fam)
        for name, extra in configs.items():
            cfg = base | {"groups": list(DEFAULT_GROUPS) + [g for g in extra if g in groups]}
            preds[(fam, name)] = evaluate_config(data, fam, cfg, groups, DEV_FOLDS, threads)["preds"]
        progress(f"  {fam}: {len(configs)} configurations")
    ref = preds[(FAMILIES[0], "champion")]
    y = {s: ref[s]["y"] for s in DEV_FOLDS}
    E = {n: _ens(preds, n, DEV_FOLDS) for n in configs}
    rng = np.random.default_rng(0)
    rows = []
    for name, (base_extra, _) in CANDIDATES.items():
        bname = f"{name}__baseline" if base_extra else "champion"
        ll = lambda n, s: M.log_loss(y[s], E[n][s])
        g_sel = float(np.mean([ll(bname, s) - ll(name, s) for s in SEL]))
        g_chk = float(ll(bname, CHECK) - ll(name, CHECK))
        yy = np.concatenate([y[s] for s in DEV_FOLDS])
        pb, pc = np.concatenate([E[bname][s] for s in DEV_FOLDS]), np.concatenate([E[name][s] for s in DEV_FOLDS])
        lb = -(yy * np.log(np.clip(pb, 1e-6, 1)) + (1 - yy) * np.log(np.clip(1 - pb, 1e-6, 1)))
        lc = -(yy * np.log(np.clip(pc, 1e-6, 1)) + (1 - yy) * np.log(np.clip(1 - pc, 1e-6, 1)))
        diff = lb - lc                                                   # positive = candidate better
        bs = np.array([diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_boot)])
        rows.append({"candidate": name, "baseline": bname, "gain_2019_21": g_sel, "gain_2022_check": g_chk,
                     "pooled_gain_2019_22": float(diff.mean()), "ci95_low": float(np.percentile(bs, 2.5)),
                     "ci95_high": float(np.percentile(bs, 97.5)), "p_one_sided": float((bs <= 0).mean()),
                     "brier_candidate": float(np.mean((pc - yy) ** 2)), "brier_baseline": float(np.mean((pb - yy) ** 2)),
                     "accuracy_candidate": float(((pc > 0.5) == (yy == 1)).mean()), "accuracy_baseline": float(((pb > 0.5) == (yy == 1)).mean()),
                     "ece_candidate": _ece(yy, pc), "ece_baseline": _ece(yy, pb),
                     "effective_models_candidate": _eff_models(preds, name), "effective_models_baseline": _eff_models(preds, bname)})
    res = pd.DataFrame(rows)
    order = res["p_one_sided"].sort_values().index                    # Holm step-down
    m, adj, running = len(res), {}, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * res.loc[i, "p_one_sided"]))
        adj[i] = running
    res["p_holm"] = pd.Series(adj)
    res["qualifies"] = (res["gain_2019_21"] > 0) & (res["gain_2022_check"] >= 0) & (res["p_holm"] < 0.05)
    fam_rows = []
    for name, (base_extra, _) in CANDIDATES.items():
        bname = f"{name}__baseline" if base_extra else "champion"
        for f in FAMILIES:
            g = {s: M.log_loss(y[s], preds[(f, bname)][s]["p"]) - M.log_loss(y[s], preds[(f, name)][s]["p"]) for s in DEV_FOLDS}
            fam_rows.append({"candidate": name, "family": f, "gain_2019_21": float(np.mean([g[s] for s in SEL])), "gain_2022": g[CHECK]})
    res.to_csv(OUT / "dev_experiment.csv", index=False)
    pd.DataFrame(fam_rows).to_csv(OUT / "dev_experiment_by_family.csv", index=False)
    (OUT / "dev_experiment.json").write_text(json.dumps({"declared": __doc__, "results": res.to_dict("records")}, indent=2, default=str))
    return {"results": res, "by_family": pd.DataFrame(fam_rows)}


def _ece(y, p, bins=10):
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(y[b == k].mean() - p[b == k].mean()) * (b == k).mean() for k in range(bins) if (b == k).any()))


def load() -> dict:
    out = {}
    for k in ("independence", "dev_experiment", "dev_experiment_by_family"):
        f = OUT / f"{k}.csv"
        if f.exists():
            out[k] = pd.read_csv(f)
    return out
