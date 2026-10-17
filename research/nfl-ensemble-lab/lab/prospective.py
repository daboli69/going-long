"""Phase 3: automated prospective prediction archive and postgame scoring.

Run by the Windows scheduled task (refresh_data.bat -> `python -m lab.cli scheduled`),
independently of the dashboard. Each run:
  1. refreshes public data (on failure it continues with cached data, flagged stale)
  2. snapshots every game kicking off within the next 8 days, per cutoff window:
       early  : 30 h < time to kickoff <= 8 days   (one snapshot per game)
       final  : 5 min < time to kickoff <= 30 h    (a new snapshot whenever inputs changed;
                                                     the latest pre-kickoff one is scored)
  3. scores every completed game against its frozen snapshots
  4. writes a missing-prediction report

Snapshots are write-once JSON files (exclusive create, then read-only) listed in an
append-only ledger. Scoring never edits a snapshot; results live in derived tables.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import metrics as M
from . import sources
from .config import ARTIFACTS_DIR, LAB_ROOT, MODELS_DIR, SNAPSHOTS_DIR

PROSP_DIR = SNAPSHOTS_DIR / "prospective"
PROSP_DIR.mkdir(parents=True, exist_ok=True)
LEDGER = PROSP_DIR / "ledger.jsonl"
RUN_LOG = PROSP_DIR / "scheduled_runs.jsonl"
SCORE_DIR = ARTIFACTS_DIR / "prospective"
SCORE_DIR.mkdir(parents=True, exist_ok=True)
CHALLENGERS = MODELS_DIR / "CHALLENGERS.json"
EARLY_MAX_H, FINAL_MAX_H, MIN_LEAD_MIN = 8 * 24, 30.0, 5.0
STALE_HOURS = 12.0
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def window_for(hours_to_kickoff: float) -> str | None:
    if hours_to_kickoff * 60 <= MIN_LEAD_MIN:
        return None
    if hours_to_kickoff <= FINAL_MAX_H:
        return "final"
    if hours_to_kickoff <= EARLY_MAX_H:
        return "early"
    return None


def _append(path, obj) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, default=str) + "\n")


def _read_jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_ledger() -> pd.DataFrame:
    rows = _read_jsonl(LEDGER)
    df = pd.DataFrame(rows)
    if len(df):
        df["predicted_at"] = pd.to_datetime(df["predicted_at"], utc=True)
        df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    return df


def run_history() -> pd.DataFrame:
    return pd.DataFrame(_read_jsonl(RUN_LOG))


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=LAB_ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "unknown"


def challenger_registry() -> dict:
    if not CHALLENGERS.exists():
        return {"versions": [], "hypotheses": []}
    r = json.loads(CHALLENGERS.read_text())
    r.setdefault("versions", [])
    r.setdefault("hypotheses", [])
    return r


def challenger_versions() -> list[str]:
    """Every model version archived alongside the champion: gate-passing shadow challengers and
    pre-registered prospective hypotheses (judged only on future games)."""
    r = challenger_registry()
    return r["versions"] + [h["version"] for h in r["hypotheses"] if h["version"] not in r["versions"]]


def register_hypothesis(version: str, label: str, rationale: str) -> None:
    """Pre-register a model design for prospective evaluation. It is NOT a validated challenger:
    the plan is fixed now and judged only on games archived after this moment."""
    r = challenger_registry()
    if any(h["version"] == version for h in r["hypotheses"]):
        return
    r["hypotheses"].append({"version": version, "label": label, "rationale": rationale,
                            "registered_at": pd.Timestamp.now(tz="UTC").isoformat(),
                            "plan": "Compare archived final-snapshot log loss vs the champion on games played after "
                                    "registration; decision after >= 128 games: paired bootstrap 95% CI must lie below zero."})
    CHALLENGERS.write_text(json.dumps(r, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- live weather (monitoring only)

def fetch_weather(games: pd.DataFrame) -> dict:
    """Open-Meteo forecast at kickoff for outdoor/retractable sites. Live context only:
    no verified historical pregame forecasts exist, so this is never a model input."""
    from . import geo
    out = {}
    for r in games.itertuples(index=False):
        site = geo.site_key(getattr(r, "stadium_id", ""), getattr(r, "stadium", ""))
        if site not in geo.STADIUMS or getattr(r, "roof_type", "") == "dome":
            out[r.game_id] = {"status": "dome or unknown site; not fetched"}
            continue
        lat, lon, _ = geo.STADIUMS[site]
        try:
            body, _ = sources._fetch(f"{OPEN_METEO}?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m,"
                                     f"precipitation_probability&forecast_days=10&timezone=UTC", timeout=30, retries=1)
            h = json.loads(body)["hourly"]
            times = pd.to_datetime(h["time"]).tz_localize("UTC")
            i = int(np.argmin(np.abs((times - r.kickoff_utc).total_seconds())))
            out[r.game_id] = {"status": "ok", "forecast_retrieved_at": _now().isoformat(), "valid_time": str(times[i]),
                              "temperature_c": h["temperature_2m"][i], "wind_kmh": h["wind_speed_10m"][i],
                              "precip_probability": h["precipitation_probability"][i], "roof_type": getattr(r, "roof_type", "")}
        except Exception as exc:
            out[r.game_id] = {"status": f"unavailable: {exc}"}
    return out


# --------------------------------------------------------------------------- snapshots

AVAIL_COLS = ["qb_projected_id", "qb_known", "qb_change", "qb_projected_out", "qb_questionable", "qb_offseason",
              "inj_report_available", "inj_final_published", "inj_report_time", "inj_source", "inj_out_off", "inj_out_def",
              "inj_q_off", "inj_q_def"] + [f"inj_out_{g}" for g in ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "CB", "S")] + \
             [f"inj_starters_out_{g}" for g in ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "CB", "S")]


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 6)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def build_records(games: pd.DataFrame, now: pd.Timestamp, data_status: dict, stale: bool, stale_reason: str | None) -> list[dict]:
    from .availability import live_monitor
    from .data_pipeline import GAMES_TABLE
    from .training import load_bundle, load_run
    from . import transparency as T
    from .weekly import discovery_overlay, predict_games
    bundle = load_bundle()
    run = load_run(bundle["version"])
    table, _ = predict_games(games, bundle, run, explain=False)
    disc = discovery_overlay(table, games)
    try:
        monitor = live_monitor(games, games, pd.read_parquet(GAMES_TABLE))
    except Exception as exc:
        monitor = [{"error": str(exc)}]
    weather = fetch_weather(games)
    chall = {}
    for v in challenger_versions():
        try:
            cb = load_bundle(v)
            ct, _ = predict_games(games, cb, load_run(v), explain=False, challengers=False)
            gi = games.set_index("game_id")
            chall[v] = {g_: {"p_champion": _clean(r_["p_champion"]),
                             "p_home": {k: _clean(r_[f"p_{k}"]) for k in cb["model_keys"] if f"p_{k}" in r_},
                             "margin_ensemble": _clean(r_.get("margin_ensemble")),
                             "inputs": T.version_inputs(gi.loc[g_], cb["features"])}
                        for g_, (_, r_) in zip(ct["game_id"], ct.iterrows())}
        except Exception as exc:
            chall[v] = {"error": str(exc)}
    manifest = sources.load_manifest()
    provenance = {k: {"sha256": (v.get("sha256") or "")[:16], "downloaded_at": v.get("downloaded_at")}
                  for k, v in manifest.items() if not k.startswith("_") and ("games" in k or str(int(games["season"].max())) in k)}
    disc_rows = {r["game_id"]: r for r in disc.get("rows", [])}
    disc_sig = dict(zip([r["game_id"] for r in disc.get("rows", [])], disc.get("signals", [])))
    records = []
    for (_, g), (_, t) in zip(games.iterrows(), table.iterrows()):
        mon = [m for m in monitor if m.get("game_id") == g["game_id"]]
        rec = {
            "game_id": g["game_id"], "season": int(g["season"]), "week": int(g["week"]),
            "matchup": f"{g['away_team']} @ {g['home_team']}", "home_team": g["home_team"], "away_team": g["away_team"],
            "kickoff_utc": g["kickoff_utc"].isoformat(),
            "hours_to_kickoff": round((g["kickoff_utc"] - now).total_seconds() / 3600, 2),
            "data_cutoff": {"data_refreshed_at": data_status.get("refreshed_at"),
                            "official_injury_file_downloaded_at": (data_status.get("injury") or {}).get("live_injury_file_downloaded_at"),
                            "espn_injuries_retrieved_at": (data_status.get("injury") or {}).get("espn_retrieved_at"),
                            "features_built_at": _clean(g.get("features_built_at")), "feature_rule": "only games with kickoff before this game"},
            "stale_data": stale, "stale_reason": stale_reason,
            "model_version": bundle["version"], "champion_method": bundle["champion"],
            "p_home": {k: _clean(t[f"p_{k}"]) for k in bundle["model_keys"]},
            "p_home_raw": {k: _clean(t[f"raw_{k}"]) for k in bundle["model_keys"]},
            "p_home_ensembles": {k: _clean(t[f"p_{k}"]) for k in ("equal_average", "weighted_average", "stacking")},
            "p_champion": _clean(t["p_champion"]), "vote": t["vote_label"], "majority_winner": t["majority_winner"],
            "margin_home": {k: _clean(t[f"margin_{k}"]) for k in bundle["model_keys"]}, "margin_ensemble": _clean(t["margin_ensemble"]),
            "market_at_snapshot": {"spread_line": _clean(g["spread_line"]), "home_moneyline": _clean(g["home_moneyline"]),
                                   "away_moneyline": _clean(g["away_moneyline"]), "p_home_novig": _clean(g["market_p_home_novig"]),
                                   "note": "line as published in nfldata at data refresh time (timestamp = data_refreshed_at)"},
            "experimental": {"experiment": disc.get("experiment"), **{k: _clean(v) for k, v in disc_rows.get(g["game_id"], {}).items()
                                                                     if k.startswith(("p_home_adj", "adj_", "n_validated", "patterns_verdict", "gbm_verdict"))},
                             "signals": disc_sig.get(g["game_id"], [])},
            "shadow_challengers": {v: (c.get(g["game_id"]) if isinstance(c, dict) and "error" not in c else c) for v, c in chall.items()},
            "availability": {side: {c: _clean(g.get(f"{side}_{c}")) for c in AVAIL_COLS} for side in ("home", "away")},
            "availability_monitor": mon,
            "champion_inputs": T.version_inputs(g, bundle["features"]),
            "live_qb_monitoring_only": _live_qb(T, g),
            "weather_forecast_live_only": weather.get(g["game_id"]),
            "missing": {"features_missing": int(g[bundle["features"]].isna().sum()), "n_features": len(bundle["features"]),
                        "injury_report_final_both": bool(g.get("home_inj_report_available") == 1 and g.get("away_inj_report_available") == 1),
                        "qb_projection_known_both": bool(g.get("home_qb_known") == 1 and g.get("away_qb_known") == 1)},
            "feature_snapshot": {c: _clean(g[c]) for c in bundle["features"]},
            "provenance": provenance, "code_version": _git_sha(),
        }
        records.append(rec)
    return records


def _live_qb(T, g) -> dict:
    """Monitoring-only QB view stored beside (never inside) the forecast; excluded from the content hash."""
    try:
        return {side: T.live_qb(g[f"{side}_team"], int(g["season"]), int(g["week"]), g, side) for side in ("home", "away")}
    except Exception as exc:
        return {"error": repr(exc)[:200]}


def _content_hash(rec: dict) -> str:
    keep = {k: v for k, v in rec.items() if k not in ("hours_to_kickoff", "data_cutoff", "availability_monitor", "live_qb_monitoring_only",
                                                       "weather_forecast_live_only", "provenance", "code_version",
                                                       "live_context_monitoring_only", "scheduled_for", "event_id")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:20]


def write_record(rec: dict, window: str, now: pd.Timestamp, ledger: pd.DataFrame, force_new: bool = False) -> tuple[str, str | None]:
    """Write one snapshot unless a safeguard says otherwise. Returns (action, path).
    force_new: stage snapshots are written once per stage even if inputs did not change."""
    kick = pd.Timestamp(rec["kickoff_utc"])
    if now >= kick - pd.Timedelta(minutes=MIN_LEAD_MIN):
        return "refused: too close to or after kickoff", None
    h = _content_hash(rec)
    prev = ledger[(ledger["game_id"] == rec["game_id"]) & (ledger["window"] == window)] if len(ledger) else ledger
    if window == "early" and len(prev):
        return "skipped: early snapshot already exists", None
    if not force_new and len(prev) and prev.sort_values("predicted_at")["content_hash"].iloc[-1] == h:
        return "skipped: inputs unchanged since last snapshot", None
    rec = {**rec, "window": window, "predicted_at": now.isoformat(), "content_hash": h, "immutable": True}
    d = PROSP_DIR / f"{rec['season']}_w{rec['week']:02d}" / rec["game_id"]
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{window}_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    with open(path, "x", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, default=str)
    path.chmod(0o444)
    _append(LEDGER, {"game_id": rec["game_id"], "season": rec["season"], "week": rec["week"], "window": window,
                     "predicted_at": rec["predicted_at"], "kickoff_utc": rec["kickoff_utc"], "content_hash": h,
                     "path": str(path.relative_to(SNAPSHOTS_DIR)), "model_version": rec["model_version"],
                     "p_champion": rec["p_champion"], "stale_data": rec["stale_data"]})
    return "written", str(path)


def run_scheduled(refresh: bool = True, now: pd.Timestamp | None = None, progress=print, horizon_days: int = 8) -> dict:
    from .data_pipeline import load_feature_store, load_status, refresh_data
    now = now or _now()
    log = {"started_at": now.isoformat(), "refresh_ok": None, "written": 0, "skipped": 0, "refused": 0, "errors": []}
    stale, reason = False, None
    if refresh:
        try:
            refresh_data(progress=progress)
            log["refresh_ok"] = True
        except Exception as exc:
            log["refresh_ok"] = False
            log["errors"].append(f"refresh failed: {exc}")
            stale, reason = True, f"refresh failed, using cached data: {exc}"
    status = load_status()
    if status.get("refreshed_at"):
        age = (now - pd.Timestamp(status["refreshed_at"])).total_seconds() / 3600
        if age > STALE_HOURS:
            stale, reason = True, reason or f"data last refreshed {age:.0f} h ago"
    try:
        fs = load_feature_store()
        up = fs[(fs["kickoff_utc"] > now) & (fs["kickoff_utc"] <= now + pd.Timedelta(days=horizon_days))].copy()
        up["window"] = [window_for((k - now).total_seconds() / 3600) for k in up["kickoff_utc"]]
        up = up[up["window"].notna()]
        log["eligible_games"] = int(len(up))
        if len(up):
            # stadium/roof context for weather lookups
            from .data_pipeline import GAMES_TABLE
            gt = pd.read_parquet(GAMES_TABLE)
            gt = gt[[c for c in ("game_id", "stadium_id", "stadium") if c in gt.columns]]
            up = up.merge(gt, on="game_id", how="left")
            recs = build_records(up.drop(columns=["window"]), now, status, stale, reason)
            ledger = load_ledger()
            actions = []
            for rec, w in zip(recs, up["window"]):
                act, path = write_record(rec, w, now, ledger)
                actions.append({"game_id": rec["game_id"], "window": w, "action": act})
                key = "written" if act == "written" else "refused" if act.startswith("refused") else "skipped"
                log[key] += 1
            log["actions"] = actions
    except Exception as exc:
        log["errors"].append(f"snapshot step failed: {exc!r}")
    try:
        log["scoring"] = score(progress=progress)["overall"]
    except Exception as exc:
        log["errors"].append(f"scoring failed: {exc!r}")
    log["finished_at"] = _now().isoformat()
    log["stale_data"] = stale
    _append(RUN_LOG, log)
    progress(f"Scheduled run: {log['written']} written, {log['skipped']} skipped, {log['refused']} refused, "
             f"{len(log['errors'])} errors.")
    return log


# --------------------------------------------------------------------------- scoring

def _load_snapshot(rel: str) -> dict:
    return json.loads((SNAPSHOTS_DIR / rel).read_text(encoding="utf-8"))


def scored_table() -> pd.DataFrame:
    """One row per (game, window): the latest snapshot made before kickoff, with results attached."""
    from .data_pipeline import load_feature_store
    led = load_ledger()
    if led.empty:
        return pd.DataFrame()
    led = led[led["predicted_at"] < led["kickoff_utc"]].sort_values("predicted_at").groupby(["game_id", "window"]).tail(1)
    fs = load_feature_store().set_index("game_id")
    rows = []
    for r in led.itertuples(index=False):
        if r.game_id not in fs.index or not bool(fs.loc[r.game_id, "completed"]):
            continue
        snap = _load_snapshot(r.path)
        res = fs.loc[r.game_id]
        p = snap["p_champion"]
        row = {"game_id": r.game_id, "season": r.season, "week": r.week, "window": r.window, "predicted_at": r.predicted_at,
               "kickoff_utc": r.kickoff_utc, "lead_hours": (r.kickoff_utc - r.predicted_at).total_seconds() / 3600,
               "model_version": snap["model_version"], "p_home": p, "home_win": res["home_win"], "margin": res["margin"],
               "margin_pred": snap["margin_ensemble"], "spread_at_snapshot": snap["market_at_snapshot"]["spread_line"],
               "p_market_at_snapshot": snap["market_at_snapshot"]["p_home_novig"],
               "p_adj_patterns": snap["experimental"].get("p_home_adj_patterns"), "p_adj_gbm": snap["experimental"].get("p_home_adj_gbm"),
               "injury_complete": snap["missing"]["injury_report_final_both"], "stale_data": snap["stale_data"],
               **{f"p_{k}": v for k, v in snap["p_home"].items()},
               **{f"chall_{k}": (v["p_champion"] if isinstance(v, dict) else v)
                  for k, v in snap.get("shadow_challengers", {}).items()
                  if isinstance(v, (int, float)) or (isinstance(v, dict) and isinstance(v.get("p_champion"), (int, float)))}}
        rows.append(row)
    return pd.DataFrame(rows)


def score(progress=print) -> dict:
    t = scored_table()
    out = {"generated_at": _now().isoformat(), "overall": {"games_scored": 0}}
    if t.empty:
        (SCORE_DIR / "metrics.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        return out
    t.to_parquet(SCORE_DIR / "scored.parquet", index=False)
    lab = t[t["home_win"].notna()]
    out["overall"] = {"games_scored": int(lab["game_id"].nunique()), "snapshots_scored": int(len(lab))}
    by_window = {}
    for w, d in lab.groupby("window"):
        res = {"champion": M.prob_summary(d["home_win"], d["p_home"])}
        for c in [c for c in d.columns if c.startswith(("p_logreg", "p_xgboost", "p_decision_tree", "p_random_forest", "p_mlp", "p_single_layer"))]:
            res[c[2:]] = M.prob_summary(d["home_win"], d[c], ci=False)
        mk = d[d["p_market_at_snapshot"].notna()]
        res["market_at_snapshot"] = M.prob_summary(mk["home_win"], mk["p_market_at_snapshot"], ci=False)
        for adj in ("p_adj_patterns", "p_adj_gbm"):
            a = d[d[adj].notna()]
            if len(a):
                res[adj] = M.prob_summary(a["home_win"], a[adj], ci=False)
        for c in [c for c in d.columns if c.startswith("chall_")]:
            a = d[d[c].notna()]
            res[c] = M.prob_summary(a["home_win"], a[c], ci=False)
        res["margin"] = M.margin_summary(d["margin"], d["margin_pred"])
        res["spread_at_snapshot"] = M.margin_summary(d["margin"], d["spread_at_snapshot"])
        res["calibration"] = M.calibration_table(d["home_win"], d["p_home"]).to_dict("records")
        fav = np.where(d["p_home"] >= 0.5, d["home_win"], 1 - d["home_win"])
        p_fav = np.maximum(d["p_home"], 1 - d["p_home"])
        res["favorite_vs_underdog"] = {"games": int(len(d)), "favorite_win_rate": float(np.mean(fav)),
                                       "expected_favorite_win_rate": float(np.mean(p_fav)),
                                       "underdog_wins": int(len(d) - fav.sum()), "expected_underdog_wins": float(np.sum(1 - p_fav))}
        res["by_injury_completeness"] = {str(k): M.prob_summary(x["home_win"], x["p_home"], ci=False)
                                         for k, x in d.groupby("injury_complete")}
        wk = d.sort_values("kickoff_utc").groupby(["season", "week"]).apply(
            lambda x: pd.Series({"n": len(x), "log_loss": M.log_loss(x["home_win"], x["p_home"]),
                                 "accuracy": M.accuracy(x["home_win"], x["p_home"])}), include_groups=False).reset_index()
        res["by_week"] = wk.to_dict("records")
        by_window[w] = res
    out["by_window"] = by_window
    out["paired"] = paired_comparisons(lab)
    try:
        out["challengers"] = evaluate_challengers().to_dict("records")
    except Exception as exc:
        out["challengers_error"] = repr(exc)[:200]
    try:
        from .discovery import evaluate_prospective_hypotheses
        hyp = evaluate_prospective_hypotheses()
        out["hypotheses"] = hyp.to_dict("records") if len(hyp) else []
    except Exception as exc:
        out["hypotheses_error"] = repr(exc)[:200]
    (SCORE_DIR / "metrics.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


def _paired(y, a, b, n_boot=2000, seed=0):
    """Mean log-loss difference b - a on the same games, with a bootstrap 95% CI."""
    pa, pb = np.clip(a, 1e-6, 1 - 1e-6), np.clip(b, 1e-6, 1 - 1e-6)
    d = -(y * np.log(pb) + (1 - y) * np.log(1 - pb)) + (y * np.log(pa) + (1 - y) * np.log(1 - pa))
    if len(d) == 0:
        return {"n": 0}
    boots = d[np.random.default_rng(seed).integers(0, len(d), (n_boot, len(d)))].mean(axis=1)
    return {"n": int(len(d)), "delta_log_loss": float(d.mean()), "ci": (float(np.quantile(boots, .025)), float(np.quantile(boots, .975)))}


def paired_comparisons(lab: pd.DataFrame) -> list[dict]:
    """Paired log-loss differences on identical games: each model / challenger / market vs the
    champion within a stage, and each stage vs the final pregame stage."""
    rows = []
    for w, d in lab.groupby("window"):
        y = d["home_win"].to_numpy(float)
        for c in [c for c in d.columns if c.startswith(("p_logreg", "p_xgboost", "p_decision_tree", "p_random_forest", "p_mlp",
                                                       "p_single_layer", "chall_", "p_market_at_snapshot", "p_adj_"))]:
            ok = d[c].notna().to_numpy()
            if ok.sum():
                rows.append({"stage": w, "comparison": f"{c} vs champion", **_paired(y[ok], d["p_home"].to_numpy(float)[ok],
                                                                                   d[c].to_numpy(float)[ok])})
    if "final" in set(lab["window"]):
        fin = lab[lab["window"] == "final"].set_index("game_id")
        for w, d in lab[lab["window"] != "final"].groupby("window"):
            d = d.set_index("game_id")
            common = d.index.intersection(fin.index)
            if len(common):
                y = fin.loc[common, "home_win"].to_numpy(float)
                rows.append({"stage": w, "comparison": f"{w} vs final (champion)",
                             **_paired(y, fin.loc[common, "p_home"].to_numpy(float), d.loc[common, "p_home"].to_numpy(float))})
    return rows


def load_metrics() -> dict:
    p = SCORE_DIR / "metrics.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# --------------------------------------------------------------------------- missing predictions

def missing_report(now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Every game whose window opened after tracking started: did it get a pre-kickoff
    early and final snapshot? If not, why (PC off, failed run, etc.)."""
    from .data_pipeline import load_feature_store
    now = now or _now()
    runs = run_history()
    led = load_ledger()
    if runs.empty:
        return pd.DataFrame()
    start = pd.to_datetime(runs["started_at"], utc=True).min()
    run_t = pd.to_datetime(runs["started_at"], utc=True)
    fs = load_feature_store()
    g = fs[(fs["kickoff_utc"] > start) & (fs["kickoff_utc"] <= now + pd.Timedelta(days=EARLY_MAX_H / 24))]
    rows = []
    for r in g.itertuples(index=False):
        for w, lo_h, hi_h in (("early", FINAL_MAX_H, EARLY_MAX_H), ("final", MIN_LEAD_MIN / 60, FINAL_MAX_H)):
            open_t, close_t = r.kickoff_utc - pd.Timedelta(hours=hi_h), r.kickoff_utc - pd.Timedelta(hours=lo_h)
            if open_t < start:
                status = "window opened before tracking started"
            elif now < close_t and now >= open_t:
                status = "window open now"
            elif now < open_t:
                status = "window not open yet"
            else:
                status = None
            have = led[(led["game_id"] == r.game_id) & (led["window"] == w) & (led["predicted_at"] < led["kickoff_utc"])] if len(led) else led
            if len(have):
                status = "archived"
            elif status is None:
                in_win = runs[(run_t >= open_t) & (run_t < close_t)]
                if in_win.empty:
                    status = "MISSED: no scheduled run while the window was open (PC off or asleep?)"
                elif in_win["errors"].map(len).sum() > 0:
                    status = "MISSED: run(s) in window failed: " + "; ".join(sum(in_win["errors"].tolist(), []))[:200]
                else:
                    status = "MISSED: run occurred but did not snapshot (check run log)"
            rows.append({"game_id": r.game_id, "matchup": f"{r.away_team} @ {r.home_team}", "kickoff_utc": r.kickoff_utc,
                         "window": w, "status": status, "snapshots": int(len(have))})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Phase 6 stage snapshots

STAGE_LABELS = {"early_week": "early-week forecast", "friday": "Friday injury-report forecast", "t24h": "24 h before kickoff",
                "t90": "90 min (inactives)", "t60": "60 min", "final": "final pregame (30 min)",
                "early": "early (Phase 3 window)"}


def live_context(game_row: pd.Series) -> dict:
    """Monitoring-only live information for a game (never a model input)."""
    from . import live
    out = {}
    try:
        espn, espn_t = live.espn_full()
        ina = live.espn_inactives(espn)
        tx = live.transactions(since=_now() - pd.Timedelta(days=7))
        for side in ("home", "away"):
            team = game_row[f"{side}_team"]
            out[team] = {
                "espn_reported_inactives_partial": ina[ina["team"] == team][["player", "position"]].to_dict("records") if len(ina) else [],
                "espn_out_or_ir": espn[(espn["team"] == team) & espn["status"].isin(["Out", "Injured Reserve", "Doubtful"])][
                    ["player", "position", "status"]].to_dict("records") if len(espn) else [],
                "transactions_last_7_days": tx[tx["team"] == team][["date", "type", "description"]].astype(str).to_dict("records") if len(tx) else []}
        out["espn_retrieved"] = espn_t
        out["official_inactive_list"] = "not available from free sources; ESPN-reported inactives above are partial"
    except Exception as exc:
        out["error"] = repr(exc)[:200]
    return out


def write_stage_snapshots(due: pd.DataFrame, progress=print, stale_refresh: bool = False, now=None) -> dict:
    """One immutable snapshot per (game, stage) for scheduler stage events that are due."""
    from .data_pipeline import GAMES_TABLE, load_feature_store, load_status
    now = now or _now()
    fs = load_feature_store()
    gt = pd.read_parquet(GAMES_TABLE)
    gt = gt[[c for c in ("game_id", "stadium_id", "stadium") if c in gt.columns]]
    ids = due["game_id"].dropna().unique().tolist()
    games = fs[fs["game_id"].isin(ids)].merge(gt, on="game_id", how="left")
    status = load_status()
    by_event = {}
    if games.empty:
        return {"by_event": {e: {"ok": False, "reason": "game not in feature store"} for e in due["event_id"]}}
    stale = stale_refresh
    reason = "refresh before this snapshot failed; last valid data used" if stale_refresh else None
    recs = {r["game_id"]: r for r in build_records(games, now, status, stale, reason)}
    ledger = load_ledger()
    for ev in due.itertuples(index=False):
        rec = recs.get(ev.game_id)
        if rec is None:
            by_event[ev.event_id] = {"ok": False, "reason": "no record"}
            continue
        kick = pd.Timestamp(ev.kickoff_utc) if getattr(ev, "kickoff_utc", None) is not None and not pd.isna(ev.kickoff_utc) else pd.Timestamp(rec["kickoff_utc"])
        rec = {**rec, "kickoff_utc": kick.isoformat(), "stage": ev.stage, "stage_label": STAGE_LABELS.get(ev.stage, ev.stage),
               "scheduled_for": str(ev.time_utc), "event_id": ev.event_id,
               "live_context_monitoring_only": live_context(games[games["game_id"] == ev.game_id].iloc[0])}
        prev = ledger[(ledger["game_id"] == ev.game_id) & (ledger["window"] == ev.stage)] if len(ledger) else ledger
        if len(prev):
            by_event[ev.event_id] = {"ok": True, "action": "already archived for this stage"}
            continue
        act, path = write_record(rec, ev.stage, now, ledger, force_new=True)
        by_event[ev.event_id] = {"ok": act == "written", "action": act, "path": path}
    progress(f"stage snapshots: {sum(v['ok'] for v in by_event.values())}/{len(by_event)} ok")
    return {"by_event": by_event}



def record_considered(source: str, candidates: list[dict]) -> None:
    """Audit trail: candidates considered for prospective tracking, whether they qualified, why."""
    r = challenger_registry()
    r.setdefault("considered", [])
    r["considered"] = [c for c in r["considered"] if c.get("source") != source]
    for c in candidates:
        r["considered"].append({"source": source, **{k: (float(v) if isinstance(v, (np.floating,)) else v) for k, v in c.items()},
                                "recorded_at": pd.Timestamp.now(tz="UTC").isoformat()})
    CHALLENGERS.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")


MIN_PROSPECTIVE_GAMES = 128


def evaluate_challengers(stage: str = "final") -> pd.DataFrame:
    """Prospective test of every tracked challenger vs the champion on identical archived games
    (after its registration), with Holm correction across all challengers. A challenger is only
    'supported' after >= 128 games AND a Holm-adjusted p < 0.05 with a negative mean difference."""
    from .discovery import holm
    reg = challenger_registry()
    t = scored_table()
    rows = []
    entries = [{"version": v, "label": "shadow (gate passed)", "registered_at": None} for v in reg["versions"]] + \
              [{"version": h["version"], "label": h["label"], "registered_at": h["registered_at"]} for h in reg["hypotheses"]]
    for e in entries:
        col = f"chall_{e['version']}"
        d = t[(t["window"] == stage)] if len(t) else t
        if len(d) and e["registered_at"]:
            d = d[d["predicted_at"] > pd.Timestamp(e["registered_at"])]
        if not len(d) or col not in d or d[col].notna().sum() == 0:
            rows.append({"challenger": e["version"], "label": e["label"], "games": 0, "status": "no scored games yet"})
            continue
        d = d[d[col].notna() & d["home_win"].notna()]
        r = _paired(d["home_win"].to_numpy(float), d["p_home"].to_numpy(float), d[col].to_numpy(float))
        y = d["home_win"].to_numpy(float)
        pa, pb = np.clip(d["p_home"].to_numpy(float), 1e-6, 1 - 1e-6), np.clip(d[col].to_numpy(float), 1e-6, 1 - 1e-6)
        diff = -(y * np.log(pb) + (1 - y) * np.log(1 - pb)) + (y * np.log(pa) + (1 - y) * np.log(1 - pa))
        boots = diff[np.random.default_rng(0).integers(0, len(diff), (4000, len(diff)))].mean(axis=1)
        rows.append({"challenger": e["version"], "label": e["label"], "games": r["n"], "delta_log_loss": r["delta_log_loss"],
                     "ci": r["ci"], "p_one_sided": float((boots >= 0).mean())})
    df = pd.DataFrame(rows)
    if "p_one_sided" in df:
        ok = df["p_one_sided"].notna()
        df.loc[ok, "p_holm"] = holm(df.loc[ok, "p_one_sided"].to_numpy())
        df["status"] = np.where(df["games"] < MIN_PROSPECTIVE_GAMES, df.get("status", "accumulating").fillna(
            "accumulating (" + df["games"].astype(str) + f"/{MIN_PROSPECTIVE_GAMES} games)"),
            np.where((df["p_holm"] < 0.05) & (df["delta_log_loss"] < 0), "supported: eligible for a promotion review (never automatic)",
                     "not supported"))
    return df
