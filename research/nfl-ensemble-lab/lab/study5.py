"""Phase 5 evaluation: player-level features, per-family specialized challengers, model
specialization by game context, and an adaptive (context-weighted) ensemble.

  python -m lab.study5

Nested chronological tuning throughout (each season tuned only on earlier seasons).
2019-2022 development; 2023-2024 and 2025 were inspected before -> reported, never used to
pick anything new. Pre-declared gate (same as Phases 3-4): a challenger must improve the
2019-2022 mean season log loss AND 2023-2024, with Holm-adjusted paired-bootstrap p < 0.05.
Gate-passing challengers become SHADOW challengers. Promising but non-passing designs may be
pre-registered as PROSPECTIVE HYPOTHESES: archived with every prediction and judged only on
future games (>= 128 scored final snapshots, paired improvement CI below zero). Nothing here
changes the champion.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from . import ensemble as ens
from . import metrics as M
from .config import ARTIFACTS_DIR
from .data_pipeline import load_feature_store
from .discovery import holm
from .features import DEFAULT_GROUPS, P5_CONTINUITY, P5_FTN, P5_PLAYER
from .training import load_run, run_training

OUT = ARTIFACTS_DIR / "study_phase5"
DEV, VAL, DIAG = (2019, 2022), (2023, 2024), (2025, 2025)
CONFIGS = {
    "champion_nested": DEFAULT_GROUPS,
    "plus_player_model": DEFAULT_GROUPS + (P5_PLAYER,),
    "plus_player_continuity": DEFAULT_GROUPS + (P5_PLAYER, P5_CONTINUITY),
    "plus_all_phase5": DEFAULT_GROUPS + (P5_PLAYER, P5_CONTINUITY, P5_FTN),
}
CONTEXT_C_GRID = (0.01, 0.03, 0.1, 0.3)


def _ll(y, p):
    p = np.clip(np.asarray(p, float), M.EPS, 1 - M.EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _season_ll(df, col, lo, hi):
    d = df[(df["season"] >= lo) & (df["season"] <= hi) & df["home_win"].notna() & df[col].notna()]
    return float(np.mean([M.log_loss(x["home_win"], x[col]) for _, x in d.groupby("season")])) if len(d) else np.nan


def _gate_row(name, base, p, bcol, rng):
    y, season = base["home_win"].to_numpy(), base["season"].to_numpy()
    ok = (season >= DEV[0]) & (season <= VAL[1]) & ~np.isnan(y) & ~np.isnan(p)
    d = _ll(y[ok], p[ok]) - _ll(y[ok], bcol[ok])
    boots = d[rng.integers(0, ok.sum(), (4000, ok.sum()))].mean(axis=1)
    t = base.assign(_c=p, _b=bcol)
    return {"candidate": name, "dev_delta": _season_ll(t, "_c", *DEV) - _season_ll(t, "_b", *DEV),
            "val_delta": _season_ll(t, "_c", *VAL) - _season_ll(t, "_b", *VAL),
            "diag_2025_delta": _season_ll(t, "_c", *DIAG) - _season_ll(t, "_b", *DIAG),
            "pooled_delta": float(d.mean()), "pooled_ci_low": float(np.quantile(boots, .025)),
            "pooled_ci_high": float(np.quantile(boots, .975)), "p_one_sided": float((boots >= 0).mean()),
            "brier_delta_pooled": float(np.mean((p[ok] - y[ok]) ** 2) - np.mean((bcol[ok] - y[ok]) ** 2)),
            "accuracy_delta_pooled": float(np.mean((p[ok] > .5) == (y[ok] == 1)) - np.mean((bcol[ok] > .5) == (y[ok] == 1)))}


# --------------------------------------------------------------------------- context

def context_frame(oof: pd.DataFrame, fs: pd.DataFrame, medians: dict | None = None) -> pd.DataFrame:
    """Objective, pregame game-context variables (all from the feature store or OOF probabilities)."""
    f = fs.drop_duplicates("game_id").set_index("game_id").loc[oof["game_id"]]
    P = oof[[f"p_{k}" for k in ens.MODEL_KEYS]].to_numpy()
    L = np.log(np.clip(P, 1e-6, 1 - 1e-6) / (1 - np.clip(P, 1e-6, 1 - 1e-6)))
    ctx = pd.DataFrame({
        "qb_uncertain": ((f[["home_qb_projected_out", "away_qb_projected_out", "home_qb_questionable", "away_qb_questionable",
                             "home_qb_offseason", "away_qb_offseason"]].fillna(0).sum(axis=1)) > 0).astype(float).to_numpy(),
        "injury_info_missing": (1 - f["inj_available"].fillna(0)).to_numpy(float),
        "strength_gap": np.abs(f["diff_rating_margin"].to_numpy(float)),
        "recent_change": np.abs(f["mx_form_vs_season"].to_numpy(float)),
        "low_information_lineups": (f["home_p5_off_lowexp"].fillna(0) + f["away_p5_off_lowexp"].fillna(0)
                                    + f["home_p5_def_lowexp"].fillna(0) + f["away_p5_def_lowexp"].fillna(0)).to_numpy(float) / 4
        if "home_p5_off_lowexp" in f else np.zeros(len(f)),
        "trench_mismatch": np.abs(f["p5mx_net_trenches"].to_numpy(float)) if "p5mx_net_trenches" in f else np.zeros(len(f)),
        "model_disagreement": L.std(axis=1),
    }, index=oof.index)
    return ctx.fillna(medians if medians is not None else ctx.median())


def specialization(oof: pd.DataFrame, ctx: pd.DataFrame, champ: str, rng) -> pd.DataFrame:
    """Per model and context bucket: log-loss difference vs the champion ensemble (2019-2024,
    previously inspected seasons; descriptive), with bootstrap CI and Holm across all tests."""
    d = oof[oof["season"].between(2019, 2024) & oof["home_win"].notna()]
    c = ctx.loc[d.index]
    rows = []
    for var in c.columns:
        v = c[var]
        if set(v.unique()) <= {0.0, 1.0}:
            buckets = {f"{var}=yes": v == 1, f"{var}=no": v == 0}
        else:
            q1, q2 = v.quantile([1 / 3, 2 / 3])
            buckets = {f"{var}: low": v <= q1, f"{var}: mid": (v > q1) & (v <= q2), f"{var}: high": v > q2}
        for bname, m in buckets.items():
            x = d[m.to_numpy()]
            if len(x) < 80:
                continue
            y = x["home_win"].to_numpy()
            base = _ll(y, x[f"p_{champ}"].to_numpy())
            for k in ens.MODEL_KEYS:
                diff = _ll(y, x[f"p_{k}"].to_numpy()) - base
                boots = diff[rng.integers(0, len(diff), (2000, len(diff)))].mean(axis=1)
                p2 = float(2 * min((boots >= 0).mean(), (boots <= 0).mean()))
                rows.append({"context": var, "bucket": bname, "model": k, "n": len(x), "delta_vs_champion": float(diff.mean()),
                             "ci_low": float(np.quantile(boots, .025)), "ci_high": float(np.quantile(boots, .975)), "p_two_sided": p2})
    out = pd.DataFrame(rows)
    out["p_holm"] = holm(out["p_two_sided"].to_numpy())
    out["supported"] = out["p_holm"] < 0.05
    return out


class AdaptiveEnsemble:
    """Logistic stacking on model logits plus context and (context x mean-logit) interactions."""

    def __init__(self, C):
        self.C = C

    def _X(self, P, ctx):
        L = np.log(np.clip(P, 1e-6, 1 - 1e-6) / (1 - np.clip(P, 1e-6, 1 - 1e-6)))
        Z = ctx.to_numpy(float)
        mean_l = L.mean(axis=1, keepdims=True)
        return np.hstack([L, Z, Z * mean_l])

    def fit(self, P, ctx, y):
        X = self._X(P, ctx)
        self.sc = StandardScaler().fit(X)
        self.m = LogisticRegression(C=self.C, max_iter=2000).fit(self.sc.transform(X), y)
        return self

    def predict(self, P, ctx):
        return self.m.predict_proba(self.sc.transform(self._X(P, ctx)))[:, 1]


def adaptive_walk_forward(oof: pd.DataFrame, ctx: pd.DataFrame) -> tuple[np.ndarray, list]:
    """Season s predicted by an adaptive ensemble fit on OOF seasons < s; its C is chosen by an
    inner chronological split inside those earlier seasons only."""
    pcols = [f"p_{k}" for k in ens.MODEL_KEYS]
    out = np.full(len(oof), np.nan)
    log = []
    lab = oof["home_win"].notna().to_numpy()
    for s in sorted(oof["season"].unique()):
        hist = ((oof["season"] < s).to_numpy()) & lab
        if oof.loc[hist, "season"].nunique() < 2:
            continue
        inner_last = oof.loc[hist, "season"].max()
        tr = hist & (oof["season"] < inner_last).to_numpy()
        va = hist & (oof["season"] == inner_last).to_numpy()
        scores = {}
        for C in CONTEXT_C_GRID:
            m = AdaptiveEnsemble(C).fit(oof.loc[tr, pcols].to_numpy(), ctx[tr], oof.loc[tr, "home_win"].to_numpy())
            scores[C] = M.log_loss(oof.loc[va, "home_win"], m.predict(oof.loc[va, pcols].to_numpy(), ctx[va]))
        C = min(scores, key=scores.get)
        m = AdaptiveEnsemble(C).fit(oof.loc[hist, pcols].to_numpy(), ctx[hist], oof.loc[hist, "home_win"].to_numpy())
        te = (oof["season"] == s).to_numpy()
        out[te] = m.predict(oof.loc[te, pcols].to_numpy(), ctx[te])
        log.append({"season": int(s), "C": C, "inner_scores": scores})
    return out, log


def main(progress=print) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    runs = {}
    for name, groups in CONFIGS.items():
        progress(f"== {name} (nested tuning, winner + margin models)")
        runs[name] = run_training(groups=groups, production=False, tag=f"p5_{name}", nested_tuning=True, fit_margins=True,
                                  progress=lambda m: None)
    champ = load_run()["selection"]["champion"]
    base = runs["champion_nested"]["oof"].reset_index(drop=True)
    bcol = base[f"p_{champ}"].to_numpy()
    rng = np.random.default_rng(0)
    rows = []
    for name, r in runs.items():
        o = r["oof"].set_index("game_id").loc[base["game_id"]].reset_index()
        for m in list(ens.MODEL_KEYS) + ["equal_average", "weighted_average", "stacking"]:
            if name == "champion_nested" and m == champ:
                continue
            row = _gate_row(f"{name}:{m}", base, o[f"p_{m}"].to_numpy(), bcol, rng)
            if m in ens.MODEL_KEYS and name != "champion_nested":   # specialized challenger vs its own family
                own = _gate_row("x", base, o[f"p_{m}"].to_numpy(), base[f"p_{m}"].to_numpy(), rng)
                row |= {"vs_own_family_pooled_delta": own["pooled_delta"], "vs_own_family_val_delta": own["val_delta"],
                        "vs_own_family_dev_delta": own["dev_delta"], "vs_own_family_p": own["p_one_sided"]}
            rows.append(row)
    fs = load_feature_store()
    ctx = context_frame(base, fs)
    adapt, adapt_log = adaptive_walk_forward(base, ctx)
    rows.append(_gate_row("adaptive_context_ensemble (champion models)", base, adapt, bcol, rng))
    pm = runs["plus_player_model"]["oof"].set_index("game_id").loc[base["game_id"]].reset_index()
    ctx_pm = context_frame(pm, fs)
    adapt_pm, _ = adaptive_walk_forward(pm, ctx_pm)
    rows.append(_gate_row("adaptive_context_ensemble (player-model models)", base, adapt_pm, bcol, rng))
    gate = pd.DataFrame(rows)
    gate["p_holm"] = holm(gate["p_one_sided"].to_numpy())
    gate["passes_gate"] = (gate["dev_delta"] < 0) & (gate["val_delta"] < 0) & (gate["p_holm"] < 0.05)
    gate = gate.sort_values("pooled_delta").reset_index(drop=True)
    gate.to_csv(OUT / "gate_results.csv", index=False)
    # per-family specialized challengers (Holm across the 6 families of each config)
    fam = gate[gate["vs_own_family_p"].notna()].copy() if "vs_own_family_p" in gate else pd.DataFrame()
    if len(fam):
        fam["config"] = fam["candidate"].str.split(":").str[0]
        fam["family"] = fam["candidate"].str.split(":").str[1]
        fam["p_holm_family"] = fam.groupby("config")["vs_own_family_p"].transform(lambda p: holm(p.to_numpy()))
        fam["family_improves"] = (fam["vs_own_family_dev_delta"] < 0) & (fam["vs_own_family_val_delta"] < 0) & (fam["p_holm_family"] < 0.05)
        fam.to_csv(OUT / "specialized_challengers.csv", index=False)
    spec = specialization(base, ctx, champ, rng)
    spec.to_csv(OUT / "specialization.csv", index=False)
    # margins: original vs enhanced
    mrows = []
    for name, r in runs.items():
        o = r["oof"]
        for split_name, (lo, hi) in (("dev 2019-22", DEV), ("val 2023-24", VAL), ("diag 2025", DIAG)):
            x = o[o["season"].between(lo, hi)]
            for k in list(ens.MODEL_KEYS) + ["ensemble"]:
                s_ = M.margin_summary(x["margin"], x[f"margin_{k}"])
                mrows.append({"config": name, "period": split_name, "model": k, "mae": s_["mae"], "rmse": s_["rmse"],
                              "winner_acc": s_.get("winner_acc")})
            s_ = M.margin_summary(x["margin"], x["spread_line"])
            mrows.append({"config": name, "period": split_name, "model": "closing spread", "mae": s_["mae"], "rmse": s_["rmse"],
                          "winner_acc": s_.get("winner_acc")})
    pd.DataFrame(mrows).to_csv(OUT / "margins.csv", index=False)
    per = []
    for name, r in runs.items():
        o = r["oof"].set_index("game_id").loc[base["game_id"]].reset_index()
        for s_, g in base.assign(_c=o[f"p_{champ}"].to_numpy(), _b=bcol).groupby("season"):
            g = g[g["home_win"].notna()]
            per.append({"config": name, "season": int(s_), "log_loss": M.log_loss(g["home_win"], g["_c"]),
                        "brier": M.brier(g["home_win"], g["_c"]), "accuracy": M.accuracy(g["home_win"], g["_c"]),
                        "ece": M.ece(g["home_win"], g["_c"])})
    for s_, g in base.assign(_c=adapt).groupby("season"):
        g = g[g["home_win"].notna() & g["_c"].notna()]
        if len(g):
            per.append({"config": "adaptive_context_ensemble", "season": int(s_), "log_loss": M.log_loss(g["home_win"], g["_c"]),
                        "brier": M.brier(g["home_win"], g["_c"]), "accuracy": M.accuracy(g["home_win"], g["_c"]), "ece": M.ece(g["home_win"], g["_c"])})
    pd.DataFrame(per).to_csv(OUT / "per_season.csv", index=False)
    summary = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "champion_method": champ, "runs": {k: str(v["run_dir"]) for k, v in runs.items()},
               "n_candidates": int(len(gate)), "n_passed": int(gate["passes_gate"].sum()),
               "passed": gate[gate["passes_gate"]]["candidate"].tolist(),
               "families_improved": fam[fam["family_improves"]]["candidate"].tolist() if len(fam) else [],
               "supported_specializations": int(spec["supported"].sum()), "specialization_tests": int(len(spec)),
               "adaptive_C_by_season": adapt_log}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    progress(f"{summary['n_candidates']} candidates; {summary['n_passed']} passed; "
             f"{summary['supported_specializations']}/{summary['specialization_tests']} specialization effects supported.")
    return summary


def load_study() -> dict:
    if not (OUT / "summary.json").exists():
        return {}
    r = {"summary": json.loads((OUT / "summary.json").read_text(encoding="utf-8"))}
    for n in ("gate_results", "specialized_challengers", "specialization", "margins", "per_season"):
        f = OUT / f"{n}.csv"
        r[n] = pd.read_csv(f) if f.exists() else pd.DataFrame()
    return r


if __name__ == "__main__":
    main()



def build_adaptive_bundle(progress=print) -> str:
    """Production adaptive-ensemble bundle: the champion's six models, combined by a context-
    weighted stacker fit on all out-of-sample seasons. Saved without becoming current."""
    import joblib
    from .config import MODELS_DIR
    from .training import load_bundle
    b = dict(load_bundle())
    run = load_run(b["version"])
    oof = run["oof"].reset_index(drop=True)
    oof = oof[oof["home_win"].notna()].reset_index(drop=True)
    ctx = context_frame(oof, load_feature_store())
    pcols = [f"p_{k}" for k in ens.MODEL_KEYS]
    last = oof["season"].max()
    tr, va = (oof["season"] < last).to_numpy(), (oof["season"] == last).to_numpy()
    scores = {C: M.log_loss(oof.loc[va, "home_win"], AdaptiveEnsemble(C).fit(oof.loc[tr, pcols].to_numpy(), ctx[tr],
              oof.loc[tr, "home_win"].to_numpy()).predict(oof.loc[va, pcols].to_numpy(), ctx[va])) for C in CONTEXT_C_GRID}
    C = min(scores, key=scores.get)
    model = AdaptiveEnsemble(C).fit(oof[pcols].to_numpy(), ctx, oof["home_win"].to_numpy())
    version = b["version"] + "_adaptive"
    b.update({"version": version, "champion": "adaptive",
              "adaptive": {"model": model, "C": C, "medians": ctx.median().to_dict(), "base_version": b["version"]}})
    (MODELS_DIR / version).mkdir(parents=True, exist_ok=True)
    joblib.dump(b, MODELS_DIR / version / "bundle.joblib")
    progress(f"adaptive bundle {version} (C={C})")
    return version



def context_thresholds() -> dict:
    """Bucket edges used by the specialization study (from the study's champion run)."""
    s = load_study()
    if not s:
        return {}
    oof = pd.read_parquet(Path(s["summary"]["runs"]["champion_nested"]) / "oof_predictions.parquet").reset_index(drop=True)
    ctx = context_frame(oof, load_feature_store())
    d = ctx[oof["season"].between(2019, 2024).to_numpy() & oof["home_win"].notna().to_numpy()]
    return {c: (None if set(d[c].unique()) <= {0.0, 1.0} else (float(d[c].quantile(1 / 3)), float(d[c].quantile(2 / 3))))
            for c in d.columns}


def game_specialization_evidence(ctx_row: pd.Series, thresholds: dict, spec: pd.DataFrame) -> list[dict]:
    """Supported (Holm-significant) model differences for the buckets this game falls in."""
    if spec is None or spec.empty or not thresholds:
        return []
    out = []
    for var, edges in thresholds.items():
        v = ctx_row.get(var)
        if v is None or pd.isna(v):
            continue
        b = (f"{var}={'yes' if v == 1 else 'no'}" if edges is None else
             f"{var}: {'low' if v <= edges[0] else 'mid' if v <= edges[1] else 'high'}")
        hit = spec[(spec["bucket"] == b) & spec["supported"]]
        for r in hit.itertuples(index=False):
            out.append({"situation": b, "model": r.model, "delta_log_loss_vs_champion": r.delta_vs_champion,
                        "ci": (r.ci_low, r.ci_high), "n_games": r.n})
    return out
