"""Analysis of a completed long-run research job (no re-optimisation).

  python -m lab.analyze_longrun JOB

Every selection decision uses DEVELOPMENT seasons only (2019-2022, walk-forward):
  * selection-noise check: pick each family's best trial on folds 2019-2021 (mean of the
    first three fold losses recorded during the search) and check that pick on the 2022
    fold, which played no role in this ranking but was used by the adaptive search;
  * ensemble replacement study: out-of-fold dev predictions (train on seasons < s) for each
    family's champion version and overnight best; all 64 replace/keep combinations are ranked
    on 2019-2021 and checked on 2022 (equal-weight and walk-forward skill-weighted averages).
2023-2025 numbers are the job's own one-time validation look (already recorded) or are
labelled EXPLORATORY; they never select anything.

The 2022 check is development evidence, not an untouched holdout: the adaptive
optimizer used all DEV_FOLDS, including 2022, to propose configurations.
"""
from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

from . import ensemble as ens
from . import metrics as M
from .longrun import DEV_FOLDS, FAMILIES, LR_DIR, Job, _prepare_data, champion_family_config, evaluate_config

SEL_FOLDS, CHECK_FOLD = (2019, 2020, 2021), 2022


def _fold_losses(t) -> list[float]:
    """Recover per-fold losses from the running means reported during the search."""
    iv = t.intermediate_values
    means = [iv[k] for k in sorted(iv)]
    return [means[0]] + [(k + 1) * means[k] - k * means[k - 1] for k in range(1, len(means))]


def _params(t, groups) -> dict:
    p = {k: v for k, v in t.params.items() if not k.startswith("g::")}
    p["groups"] = sorted({g for g in groups if g == "Opponent-adjusted ratings" or t.params.get(f"g::{g}", False)})
    if "C" in p:
        p.setdefault("penalty", "l2")
    return p


def analyze(job_id: str, top_k: int = 25, progress=print, record=True, max_candidates=None) -> dict:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    job = Job(job_id)
    out_dir = job.dir / "analysis"
    out_dir.mkdir(exist_ok=True)
    data, groups = _prepare_data()
    storage = f"sqlite:///{(job.dir / 'optuna.db').as_posix()}"
    threads = job.meta.get("threads", 4)
    final = json.loads((job.dir / "final.json").read_text()) if (job.dir / "final.json").exists() else {}
    top_rows, freq_rows, hp_rows, check_rows, curve_rows = [], [], [], [], []
    best_cfg, sel_cfg = {}, {}
    for fam in FAMILIES:
        st = optuna.load_study(study_name=fam, storage=storage)
        comp = [t for t in st.trials if t.state.name == "COMPLETE" and len(t.intermediate_values) == len(DEV_FOLDS)]
        comp.sort(key=lambda t: t.value)
        # improvement curve (best-so-far by trial order)
        best = np.inf
        for t in sorted(comp, key=lambda t: t.number):
            best = min(best, t.value)
            curve_rows.append({"family": fam, "trial": t.number, "best_so_far": best})
        top = comp[:top_k]
        for rank, t in enumerate(top[:10], 1):
            p = _params(t, groups)
            top_rows.append({"family": fam, "rank": rank, "trial": t.number, "dev_log_loss": t.value,
                             **{f"fold_{s}": v for s, v in zip(DEV_FOLDS, _fold_losses(t))},
                             "n_groups": len(p["groups"]), "groups": "; ".join(p["groups"]), "max_features": p["max_features"],
                             "calibration": p["calibration"],
                             "hyperparameters": json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in p.items()
                                                            if k not in ("groups", "max_features", "calibration")})})
        for g in sorted(groups):
            in_top = np.mean([g in _params(t, groups)["groups"] for t in top]) if top else np.nan
            in_all = np.mean([g in _params(t, groups)["groups"] for t in comp]) if comp else np.nan
            freq_rows.append({"family": fam, "group": g, "share_in_top": in_top, "share_in_all_complete": in_all,
                              "enrichment": in_top - in_all})
        for k in [k for k in (top[0].params if top else {}) if not k.startswith("g::")]:
            vals = [t.params.get(k) for t in top]
            hp_rows.append({"family": fam, "parameter": k, "top_values": json.dumps(vals[:10], default=str)})
        best_cfg[fam] = _params(top[0], groups) if top else None
        # selection-noise check inside development: select on 2019-2021, check 2022
        if comp:
            sel = min(comp, key=lambda t: np.mean(_fold_losses(t)[:3]))
            sel_cfg[fam] = _params(sel, groups)
            ch = champion_family_config(fam)
            ch_eval = evaluate_config(data, fam, ch, groups, DEV_FOLDS, threads)
            sel_folds = _fold_losses(sel)
            check_rows.append({"family": fam, "selected_trial": sel.number,
                               "selected_mean_2019_21": float(np.mean(sel_folds[:3])),
                               "champion_mean_2019_21": float(np.mean([ch_eval["per_season"][s] for s in SEL_FOLDS])),
                               "selected_2022": sel_folds[3], "champion_2022": ch_eval["per_season"][CHECK_FOLD],
                               "gain_2019_21": float(np.mean([ch_eval["per_season"][s] for s in SEL_FOLDS]) - np.mean(sel_folds[:3])),
                               "gain_2022_holdout": ch_eval["per_season"][CHECK_FOLD] - sel_folds[3]})
        progress(f"  analysed {fam}: {len(comp)} complete trials")
    pd.DataFrame(top_rows).to_csv(out_dir / "top_trials.csv", index=False)
    pd.DataFrame(freq_rows).to_csv(out_dir / "group_frequency.csv", index=False)
    pd.DataFrame(hp_rows).to_csv(out_dir / "hyperparameters.csv", index=False)
    chk = pd.DataFrame(check_rows)
    chk["retention"] = chk["gain_2022_holdout"] / chk["gain_2019_21"].where(chk["gain_2019_21"].abs() > 1e-9)
    chk.to_csv(out_dir / "selection_noise_check.csv", index=False)
    pd.DataFrame(curve_rows).to_csv(out_dir / "improvement_curves.csv", index=False)

    # ---- dev-only out-of-fold predictions for the ensemble replacement study
    progress("  building development out-of-fold predictions (champion versions and overnight bests)")
    preds = {}
    for fam in FAMILIES:
        for tag, cfg in (("champion", champion_family_config(fam)), ("overnight", sel_cfg.get(fam))):
            if cfg is None:
                continue
            r = evaluate_config(data, fam, cfg, groups, DEV_FOLDS, threads)
            preds[(fam, tag)] = r["preds"]
    base = preds[(FAMILIES[0], "champion")]
    gid = np.concatenate([base[s]["game_id"] for s in DEV_FOLDS])
    y = np.concatenate([base[s]["y"] for s in DEV_FOLDS])
    season = np.concatenate([[s] * len(base[s]["y"]) for s in DEV_FOLDS])
    P = {k: np.concatenate([v[s]["p"] for s in DEV_FOLDS]) for k, v in preds.items()}
    oof = pd.DataFrame({"game_id": gid, "season": season, "home_win": y, **{f"{f}|{t}": p for (f, t), p in P.items()}})
    oof.to_parquet(out_dir / "dev_oof.parquet", index=False)
    L = np.log(np.clip(oof[[c for c in oof.columns if "|" in c]], 1e-6, 1 - 1e-6) /
               (1 - np.clip(oof[[c for c in oof.columns if "|" in c]], 1e-6, 1 - 1e-6)))
    corr = L.corr()
    corr.to_csv(out_dir / "prediction_correlations.csv")
    E = (oof[[c for c in oof.columns if "|" in c]].sub(oof["home_win"], axis=0)).corr()
    E.to_csv(out_dir / "error_correlations.csv")
    vm = []
    for c in [c for c in oof.columns if "|" in c]:
        fam, tag = c.split("|")
        p_ = oof[c].to_numpy()
        vm.append({"family": fam, "version": tag, "log_loss_dev": float(np.mean([M.log_loss(oof["home_win"][oof["season"] == s],
                                                                                           p_[oof["season"].to_numpy() == s]) for s in DEV_FOLDS])),
                   "brier_dev": M.brier(oof["home_win"], p_), "accuracy_dev": M.accuracy(oof["home_win"], p_), "ece_dev": M.ece(oof["home_win"], p_),
                   **{f"ll_{s}": M.log_loss(oof["home_win"][oof["season"] == s], p_[oof["season"].to_numpy() == s]) for s in DEV_FOLDS}})
    pd.DataFrame(vm).to_csv(out_dir / "version_metrics.csv", index=False)

    def eff(cols):
        C = np.nan_to_num(L[cols].corr().to_numpy(), nan=0.0)   # a constant-prediction model has undefined correlation
        np.fill_diagonal(C, 1.0)
        ev = np.linalg.eigvalsh(C)
        return float(ev.sum() ** 2 / (ev ** 2).sum())

    def ens_pred(cols, weighted):
        Pm = oof[cols].to_numpy()
        if not weighted:
            return Pm.mean(axis=1)
        out = np.full(len(oof), np.nan)
        for s in DEV_FOLDS:
            m = oof["season"].to_numpy() == s
            h = oof["season"].to_numpy() < s
            w = ens.skill_weights(Pm[h], y[h]) if h.sum() > 100 else np.full(len(cols), 1 / len(cols))
            out[m] = Pm[m] @ w
        return out

    def season_ll(p, seasons):
        return float(np.mean([M.log_loss(y[season == s], p[season == s]) for s in seasons]))

    rows = []
    for r_ in range(0, 7):
        for rep in itertools.combinations(FAMILIES, r_):
            if any((f, "overnight") not in preds for f in rep):
                continue
            cols = [f"{f}|{'overnight' if f in rep else 'champion'}" for f in FAMILIES]
            for weighted in (False, True):
                p = ens_pred(cols, weighted)
                rows.append({"replaced": "+".join(rep) or "(none: champion versions)", "n_replaced": len(rep),
                             "weighting": "skill-weighted (walk-forward)" if weighted else "equal",
                             "ll_2019_21": season_ll(p, SEL_FOLDS), "ll_2022_check": season_ll(p, (CHECK_FOLD,)),
                             "ll_dev_all": season_ll(p, DEV_FOLDS), "brier_dev": M.brier(y, p), "accuracy_dev": M.accuracy(y, p),
                             "ece_dev": M.ece(y, p), "effective_models": eff(cols)})
    combos = pd.DataFrame(rows)
    for w in combos["weighting"].unique():
        m = combos["weighting"] == w
        ref = combos[m & (combos["n_replaced"] == 0)].iloc[0]
        combos.loc[m, "gain_2019_21"] = ref["ll_2019_21"] - combos.loc[m, "ll_2019_21"]
        combos.loc[m, "gain_2022_check"] = ref["ll_2022_check"] - combos.loc[m, "ll_2022_check"]
    combos = combos.sort_values("ll_2019_21").reset_index(drop=True)
    combos.to_csv(out_dir / "ensemble_combinations.csv", index=False)

    # pre-declared candidate rule (dev only): distinct designs that improve 2019-21 AND do not get
    # worse on the untouched-by-selection 2022 fold; at most 3, chosen as:
    #   A) best single-family replacement, B) best combination, C) all six replaced.
    # 2022 was excluded from this ranking, but not from the adaptive search.
    cands = []
    for label, sub in (("best single replacement", combos[combos["n_replaced"] == 1]),
                       ("best combination", combos[combos["n_replaced"] >= 2]),
                       ("all six overnight versions", combos[combos["n_replaced"] == 6])):
        if len(sub):
            r = sub.sort_values("ll_2019_21").iloc[0]
            ok = r["gain_2019_21"] > 0 and r["gain_2022_check"] >= 0
            cands.append({"label": label, "replaced": r["replaced"], "weighting": r["weighting"],
                          "gain_2019_21": r["gain_2019_21"], "gain_2022_check": r["gain_2022_check"],
                          "qualifies_for_prospective_tracking": bool(ok),
                          "reason": "improves 2019-21 and holds on the 2022 check fold" if ok else
                          ("does not improve 2019-21" if r["gain_2019_21"] <= 0 else "gain disappears on the 2022 check fold")})
    cands = pd.DataFrame(cands).drop_duplicates("replaced")
    if max_candidates is not None and len(cands) > max_candidates:
        cands = cands.sort_values(["gain_2019_21", "gain_2022_check"], ascending=False).head(max_candidates)
    cands.to_csv(out_dir / "candidates.csv", index=False)
    summary = {"job": job_id, "prospective_registry_updated": bool(record), "candidate_limit": max_candidates,
               "complete_trials": {f: int(len([t for t in optuna.load_study(study_name=f, storage=storage).trials
                                                                if t.state.name == "COMPLETE"])) for f in FAMILIES},
               "final_validation_look": final.get("validation_look"), "selection_configs": sel_cfg, "best_configs": best_cfg,
               "selection_limitation": "2022 is a development check, not untouched: adaptive search used all DEV_FOLDS. No promotion from these results.",
               "effective_models_champion_versions": eff([f"{f}|champion" for f in FAMILIES]),
               "effective_models_overnight_versions": eff([f"{f}|overnight" for f in FAMILIES if (f, "overnight") in preds]),
               "candidates": cands.to_dict("records"), "protocol": __doc__.split("Every selection decision")[1].strip()}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    progress("analysis written to " + str(out_dir))
    if record:
        try:
            from .prospective import record_considered
            record_considered(job_id, cands.to_dict("records"))
        except Exception:
            pass
    return summary


def load(job_id: str) -> dict:
    d = LR_DIR / job_id / "analysis"
    if not (d / "summary.json").exists():
        return {}
    out = {"summary": json.loads((d / "summary.json").read_text(encoding="utf-8"))}
    for n in ("top_trials", "group_frequency", "hyperparameters", "selection_noise_check", "improvement_curves", "version_metrics",
              "ensemble_combinations", "candidates", "prediction_correlations", "error_correlations"):
        f = d / f"{n}.csv"
        if f.exists():
            out[n] = pd.read_csv(f, index_col=0 if "correlations" in n else None)
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("job")
    parser.add_argument("--no-record", action="store_true", help="Write dev analysis only; do not register considered prospective configurations")
    parser.add_argument("--max-candidates", type=int)
    args = parser.parse_args()
    analyze(args.job, record=not args.no_record, max_candidates=args.max_candidates)
