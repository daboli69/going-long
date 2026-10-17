"""Weekly predictions, the five-round model debate, and immutable snapshots."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import ensemble as ens
from . import explain as X
from . import models, sources
from .config import SNAPSHOTS_DIR
from .availability import live_monitor
from .data_pipeline import GAMES_TABLE, current_season, load_feature_store, load_status, refresh_data
from .training import load_bundle, load_run


def default_week(fs: pd.DataFrame, season: int | None = None) -> tuple[int, int]:
    """The earliest week of the season with a game that has not kicked off."""
    season = season or current_season()
    now = pd.Timestamp.now(tz="UTC")
    upcoming = fs[(fs["season"] == season) & (fs["kickoff_utc"] > now)]
    if len(upcoming):
        return season, int(upcoming["week"].min())
    return season, int(fs[fs["season"] == season]["week"].max())


def _hist_metrics(run: dict) -> dict:
    lb = run.get("leaderboard", pd.DataFrame())
    out = {}
    for key in ens.MODEL_KEYS + ("equal_average", "weighted_average", "stacking"):
        row = lb[(lb["split"] == "validation") & (lb["method"] == key)] if len(lb) else lb
        out[key] = {"val_accuracy": float(row["accuracy"].iloc[0]), "val_log_loss": float(row["log_loss"].iloc[0]),
                    "val_ece": float(row["ece"].iloc[0])} if len(row) else {}
    return out


def predict_games(games: pd.DataFrame, bundle: dict, run: dict | None = None, explain: bool = True,
                  challengers: bool = True) -> tuple[pd.DataFrame, list[dict]]:
    """Run all six models + ensembles + margins on feature-store rows.
    Returns a flat table and one debate record per game."""
    run = run or {}
    cols, keys = bundle["features"], bundle["model_keys"]
    Xall = games[cols].astype(float).to_numpy()
    hist = _hist_metrics(run) if run else {}
    agree = run.get("agreement", pd.DataFrame())
    out = games[["game_id", "season", "week", "kickoff_utc", "home_team", "away_team", "home_qb_name", "away_qb_name",
                 "spread_line", "home_moneyline", "away_moneyline", "market_p_home_novig", "completed", "home_score", "away_score"]].copy()
    fbm = bundle.get("features_by_model") or {}
    for k in keys:
        ck = fbm.get(k, cols)
        raw = bundle["clf"][k].predict_proba(games[ck].astype(float).to_numpy())[:, 1]
        out[f"raw_{k}"] = raw
        out[f"p_{k}"] = bundle["calibrators"][k].transform(raw)
        out[f"margin_{k}"] = bundle["reg"][k].predict(Xall)
    P = out[[f"p_{k}" for k in keys]].to_numpy()
    out["p_equal_average"] = ens.equal_average(P)
    out["p_weighted_average"] = ens.weighted_average(P, np.array([bundle["weights"][k] for k in keys]))
    out["p_stacking"] = ens.stack_predict(bundle["stacker"], P)
    champ = bundle["champion"]
    out["champion_method"] = champ
    out["p_champion"] = out[f"p_{champ}"]
    out["margin_ensemble"] = out[[f"margin_{k}" for k in keys]].mean(axis=1)
    chall = {}
    if challengers:
        from .prospective import challenger_versions
        from .training import load_bundle as _lb, load_run as _lr
        for cv in challenger_versions():
            try:
                ct, _ = predict_games(games, _lb(cv), _lr(cv), explain=False, challengers=False)
                out[f"challenger_{cv}"] = ct["p_champion"].values
                chall[cv] = ct
            except Exception as exc:  # a broken challenger never blocks the champion
                out[f"challenger_{cv}"] = np.nan
    warn_cols = []
    debates = []
    for i, (_, g) in enumerate(out.iterrows()):
        probs = {k: g[f"p_{k}"] for k in keys}
        v = ens.vote(probs)
        out.loc[g.name, ["home_votes", "away_votes", "vote_label", "vote_tie", "unanimous"]] = [v["home_votes"], v["away_votes"], v["label"], v["tie"], v["unanimous"]]
        team = {"home": g["home_team"], "away": g["away_team"], "none": "none"}
        out.loc[g.name, "majority_winner"] = team[v["winner"]]
        ens_winner = g["home_team"] if g["p_champion"] > 0.5 else g["away_team"]
        out.loc[g.name, "ensemble_winner"] = ens_winner
        out.loc[g.name, "vote_vs_ensemble_disagree"] = team[v["winner"]] != ens_winner
        out.loc[g.name, "prob_spread"] = float(np.max(P[i]) - np.min(P[i]))
        warns = _quality_warnings(games.iloc[i], cols)
        warn_cols.append("; ".join(warns))
        if not explain:
            continue
        exps = {k: X.explain(k, bundle["clf"][k], games.iloc[[i]][fbm.get(k, cols)].astype(float).to_numpy(), fbm.get(k, cols))
                for k in keys}
        debates.append(_debate(g, keys, probs, v, exps, hist, agree, ens_winner, warns))
    out["data_warnings"] = warn_cols
    return out, debates


def _quality_warnings(row: pd.Series, cols: list[str]) -> list[str]:
    w = []
    missing = int(row[cols].isna().sum())
    if missing:
        w.append(f"{missing} of {len(cols)} features missing (imputed with training medians)")
    for side in ("home", "away"):
        if row.get(f"{side}_qb_known", 1) == 0:
            w.append(f"{side}: no previous starter found; QB features use the replacement prior")
        if row.get(f"{side}_qb_projected_out", 0) == 1:
            w.append(f"{side}: projected starter listed Out/Doubtful, replacement QB projected")
        if row.get(f"{side}_qb_questionable", 0) == 1:
            w.append(f"{side}: projected starting QB is Questionable")
        if row.get(f"{side}_inj_report_available", 1) != 1:
            w.append(f"{side}: no final official injury report before kickoff (injury context unavailable; "
                     "the default models do not use injury features)")
        if row.get(f"{side}_std_games", 1) == 0 and row["week"] > 1:
            w.append(f"{side} team has no completed games this season in the data")
    if row["kickoff_utc"] <= pd.Timestamp.now(tz="UTC"):
        w.append("kickoff already passed: this is a retrospective prediction, not a pregame forecast")
    return w


def _debate(g, keys, probs, v, exps, hist, agree, ens_winner, warns) -> dict:
    home, away = g["home_team"], g["away_team"]
    r1 = [{"model": k, "name": ens.MODEL_NAMES[k], "family": ens.FAMILIES[k], "winner": home if probs[k] > 0.5 else away,
           "p_home": float(probs[k]), "p_away": float(1 - probs[k]), "vote": "home" if probs[k] > 0.5 else "away",
           **hist.get(k, {})} for k in keys]
    # Round 3: which features separate the two voting blocs (normalized attribution shares)
    shares = {k: X.normalized_shares(exps[k]) for k in keys}
    home_bloc = [k for k in keys if probs[k] > 0.5]
    away_bloc = [k for k in keys if probs[k] < 0.5]
    split_feats = []
    if home_bloc and away_bloc:
        feats = set().union(*[shares[k].keys() for k in keys])
        diff = {f: np.mean([shares[k].get(f, 0.0) for k in home_bloc]) - np.mean([shares[k].get(f, 0.0) for k in away_bloc]) for f in feats}
        split_feats = [{"feature": f, "home_bloc_minus_away_bloc_share": float(d)}
                       for f, d in sorted(diff.items(), key=lambda kv: -abs(kv[1]))[:6]]
    fam = {}
    for k in keys:
        fam.setdefault(ens.FAMILIES[k], []).append(r1[keys.index(k)]["vote"])
    pv = np.array([probs[k] for k in keys])
    hist_agree = []
    if len(agree):
        a = agree[agree["model_a"] < agree["model_b"]].sort_values("vote_agreement")
        hist_agree = a.to_dict("records")
    fshares = {k: X.factor_shares(exps[k]) for k in keys}
    factors = sorted({f for k in keys for f in fshares[k]})
    factor_rows = [{"model": ens.MODEL_NAMES[k], "vote": "home" if probs[k] > 0.5 else "away",
                    **{f: round(fshares[k].get(f, {}).get("net", 0.0), 4) for f in factors}} for k in keys]
    factor_split = []
    if home_bloc and away_bloc:
        for f in factors:
            h = np.mean([fshares[k].get(f, {}).get("net", 0.0) for k in home_bloc])
            a = np.mean([fshares[k].get(f, {}).get("net", 0.0) for k in away_bloc])
            factor_split.append({"factor": f, "home_bloc_net": round(float(h), 4), "away_bloc_net": round(float(a), 4),
                                 "difference": round(float(h - a), 4)})
        factor_split.sort(key=lambda r: -abs(r["difference"]))
    pv_range = float(max(probs.values()) - min(probs.values()))
    agreement = ("All six models agree on the winner and their probabilities are within "
                 f"{pv_range:.1%} of each other; there is no meaningful disagreement to explain."
                 if v["unanimous"] and pv_range < 0.10 else None)
    r3 = {"factor_net_by_model": factor_rows, "factors_separating_blocs_by_factor": factor_split, "agreement_note": agreement,
          "dissenters": [ens.MODEL_NAMES[k] for k in (away_bloc if v["winner"] == "home" else home_bloc)],
          "prob_range": float(pv.max() - pv.min()), "prob_std": float(pv.std()),
          "features_separating_blocs": split_feats,
          "family_votes": {f: {"votes": vs, "consistent": len(set(vs)) == 1} for f, vs in fam.items()},
          "historical_pairwise_agreement": hist_agree,
          "calibration_ece_validation": {k: hist.get(k, {}).get("val_ece") for k in keys},
          "note": "Logistic Regression and the Single-Layer NN are the same model family; their agreement is expected."}
    r4 = v | {"winner_team": {"home": home, "away": away, "none": "none"}[v["winner"]],
              "note": "Votes count model agreement. A unanimous vote is not a 100% probability."}
    r5 = {"equal_average": float(g["p_equal_average"]), "weighted_average": float(g["p_weighted_average"]),
          "stacking": float(g["p_stacking"]), "champion_method": g["champion_method"], "champion_p_home": float(g["p_champion"]),
          "ensemble_winner": ens_winner, "majority_winner": r4["winner_team"],
          "vote_vs_ensemble_disagree": r4["winner_team"] != ens_winner,
          "margin_models": {models.MARGIN_NAMES[k]: float(g[f"margin_{k}"]) for k in keys},
          "margin_ensemble": float(g["margin_ensemble"]),
          "challengers": {c[len("challenger_"):]: (None if pd.isna(g[c]) else float(g[c])) for c in g.index if str(c).startswith("challenger_")},
          "market_p_home_novig": None if pd.isna(g["market_p_home_novig"]) else float(g["market_p_home_novig"]),
          "spread_line": None if pd.isna(g["spread_line"]) else float(g["spread_line"]),
          **{f"{k}_val": hist.get(k, {}) for k in ("equal_average", "weighted_average", "stacking")}}
    return {"game_id": g["game_id"], "matchup": f"{away} @ {home}", "kickoff_utc": str(g["kickoff_utc"]),
            "warnings": warns, "round1": r1, "round2": {k: exps[k] for k in keys}, "round3": r3, "round4": r4, "round5": r5}


def discovery_overlay(table: pd.DataFrame, games: pd.DataFrame) -> dict:
    """Phase 2 experimental adjustments (if a discovery experiment exists). The original
    ensemble probability stays the primary forecast unless an adjustment passed its
    pre-declared out-of-sample test."""
    from . import discovery
    exp = discovery.current_experiment()
    if not exp:
        return {"experiment": None, "rows": [], "signals": [], "note": "no discovery experiment has been run"}
    try:
        adj, signals = discovery.upcoming_adjustments(table, games, exp)
    except Exception as exc:  # never block weekly predictions on the research layer
        return {"experiment": exp, "rows": [], "signals": [], "note": f"discovery overlay failed: {exc}"}
    for c in ("p_home_adj_patterns", "p_home_adj_gbm", "adj_patterns", "adj_gbm", "n_validated_signals"):
        table[c] = adj[c].values
    return {"experiment": exp, "rows": json.loads(adj.to_json(orient="records")), "signals": signals,
            "note": "experimental; original ensemble remains primary unless verdict says demonstrated"}


def write_snapshot(season: int, week: int, table: pd.DataFrame, debates: list[dict], bundle: dict, extra: dict | None = None) -> dict:
    """Write a new, never-overwritten snapshot. Returns its paths."""
    created = datetime.now(timezone.utc)
    d = SNAPSHOTS_DIR / f"{season}_w{week:02d}"
    d.mkdir(parents=True, exist_ok=True)
    stem = f"{created.strftime('%Y%m%dT%H%M%S%fZ')}_{bundle['version']}"
    manifest = sources.load_manifest()
    meta = {"created_at": created.isoformat(), "season": season, "week": week, "model_version": bundle["version"],
            "models_trained_through": bundle["trained_through"], "champion": bundle["champion"],
            "source_files": {k: {"sha256": v.get("sha256"), "downloaded_at": v.get("downloaded_at")}
                             for k, v in manifest.items() if k == "nfldata_games" or k.endswith(str(season))},
            "immutable": True}
    payload = {"meta": meta, "predictions": json.loads(table.to_json(orient="records", date_format="iso")), "debates": debates, **(extra or {})}
    jpath = d / f"{stem}.json"
    with open(jpath, "x", encoding="utf-8") as fh:  # 'x' refuses to overwrite
        json.dump(payload, fh, indent=1, default=str)
    ppath = d / f"{stem}.parquet"
    with open(ppath, "xb") as fh:
        table.to_parquet(fh, index=False)
    for p in (jpath, ppath):
        p.chmod(0o444)
    return {"snapshot_json": jpath, "snapshot_parquet": ppath}


def list_snapshots() -> list:
    return sorted(SNAPSHOTS_DIR.glob("*/*.json"), reverse=True)


def run_weekly(season: int | None = None, week: int | None = None, refresh: bool = True, progress=print) -> dict:
    if refresh:
        progress("Refreshing completed-game data and schedule ...")
        refresh_data(progress=progress)
    fs = load_feature_store()
    if week is None:
        season, week = default_week(fs, season)
    season = season or current_season()
    games = fs[(fs["season"] == season) & (fs["week"] == week)]
    if games.empty:
        raise ValueError(f"No scheduled games found for {season} week {week}.")
    progress(f"Predicting {len(games)} games for {season} week {week} ...")
    bundle = load_bundle()
    run = load_run(bundle["version"])
    table, debates = predict_games(games, bundle, run)
    now = pd.Timestamp.now(tz="UTC")
    table["predicted_at"] = now.isoformat()
    table["model_version"] = bundle["version"]
    table["predicted_before_kickoff"] = table["kickoff_utc"] > now
    table["feature_cutoff_utc"] = games["feature_cutoff_utc"]  # same index; keeps UTC tz
    monitor = live_monitor(games, games, pd.read_parquet(GAMES_TABLE))
    for side in ("home", "away"):
        m = {x["game_id"]: x for x in monitor if x["side"] == side}
        table[f"{side}_projected_qb"] = table["game_id"].map(lambda g: m.get(g, {}).get("projected_qb"))
        table[f"{side}_qb_uncertain"] = table["game_id"].map(lambda g: m.get(g, {}).get("qb_uncertain", True))
        table[f"{side}_injury_report_final"] = table["game_id"].map(lambda g: m.get(g, {}).get("official_report_final", False))
    status = load_status()
    freshness = {"data_refreshed_at": status.get("refreshed_at"), **(status.get("injury") or {})}
    disc = discovery_overlay(table, games)
    paths = write_snapshot(season, week, table, debates, bundle,
                           extra={"availability_monitor": monitor, "freshness": freshness, "discovery": disc})
    from .reports import weekly_workbook
    paths |= weekly_workbook(season, week, table, debates, bundle, run, monitor, freshness, disc)
    progress(f"Saved snapshot and reports for {season} week {week}.")
    return {"season": season, "week": week, "table": table, "debates": debates, "paths": paths,
            "monitor": monitor, "freshness": freshness, "discovery": disc}
