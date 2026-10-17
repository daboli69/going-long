"""Phase 9: versioned, read-only lab -> GOING feed (schema going-nfl-lab-feed 1.x).

Built ONLY from existing artifacts: immutable stage snapshots, the challenger registry, the experimental drive-simulator
archive, the ESPN market archive and prospective scoring. Nothing here writes to models, the scheduler or archives.
Sanitised for a public website: no file paths, raw feature vectors, local hashes, research files or credentials.
Contract: docs/GOING_FEED_CONTRACT.md.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR, LAB_ROOT, SNAPSHOTS_DIR

SCHEMA = "going-nfl-lab-feed"
SCHEMA_VERSION = "1.0.0"
STALE_AFTER_HOURS = 36
MODEL_LABELS = {"logreg": "Logistic regression", "xgboost": "XGBoost", "decision_tree": "Decision tree",
                "random_forest": "Random forest", "mlp": "Neural network (MLP)", "single_layer": "Single-layer network"}
NOTICES = {
    "correlation": "The six models read the same 85 inputs and behave like about 1.2 independent models. Agreement among them is "
                   "not six independent confirmations.",
    "experimental": "Drive simulation and lineup analysis are experimental research outputs, not official forecasts.",
    "market": "Sportsbook prices are a benchmark. A model-versus-market difference is not a proven betting edge; historically the "
              "closing market has been more accurate than the champion.",
    "challengers": "Challengers are tracked prospectively and are not promoted until they meet a pre-registered standard over 128+ games.",
}


def _f(x, nd=4):
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return None
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def _snapshots() -> pd.DataFrame:
    from .prospective import load_ledger
    led = load_ledger()
    if led.empty:
        return led
    led = led[led["predicted_at"] < led["kickoff_utc"]]                    # pregame archives only
    return led.sort_values("predicted_at")


def _load(path) -> dict | None:
    try:
        return json.loads((SNAPSHOTS_DIR / str(path).replace("\\", os.sep)).read_text(encoding="utf-8"))
    except Exception:
        return None


def _qb(s: dict, side: str, names: dict) -> dict:
    ci = s.get("champion_inputs") or {}
    av = (s.get("availability") or {}).get(side) or {}
    qid = ci.get(f"{side}_qb_id") or av.get("qb_projected_id")
    live = ((s.get("live_qb_monitoring_only") or {}).get(side) or {})
    return {"champion_assumes": names.get(qid) if qid else None,
            "starter_listed_out": bool(av.get("qb_projected_out")) if av.get("qb_projected_out") is not None else None,
            "starter_questionable": bool(av.get("qb_questionable")) if av.get("qb_questionable") is not None else None,
            "live_projection": live.get("live_qb"), "live_status": live.get("status"),
            "injury_report": "verified pregame report" if av.get("inj_report_available") == 1 else "no verified report",
            "injury_report_retrieved_at": av.get("inj_report_time")}


def _lineup(game_row, team) -> dict:
    """Projected absences from the Phase 7.2 lineup analysis (as of publication; analysis, not a model input)."""
    try:
        from .lineup72 import player_table
        t = player_table(game_row, team)
    except Exception:
        return {"available": False}
    if t is None or t.empty:
        return {"available": False}
    st = t[t["starter"]]
    absences = [{"player": r.player, "unit": r.unit, "status": r.basis, "type": r.status_type, "availability": _f(r.availability, 2)}
                for r in st.itertuples(index=False) if r.availability < 0.95]
    ol = st[st["unit"] == "OL"]
    return {"available": True, "starters_expected_out": _f((1 - st["availability"]).sum(), 1),
            "important_absences": absences[:12],
            "ol_starters_expected": int((ol["availability"] > 0.5).sum()), "ol_regular_starters": int(len(ol))}


def _drive_sim(game_id: str) -> dict | None:
    d = ARTIFACTS_DIR / "phase81" / "drive_sim_archive"
    files = sorted(d.glob(f"{game_id}_*.json"), key=lambda p: p.stat().st_mtime) if d.exists() else []
    if not files:
        return None
    r = json.loads(files[-1].read_text())
    return {"experimental": True, "stage": r.get("stage"), "archived_at": r.get("archived_at"),
            "p_home": _f(r.get("p_home_calibrated")), "margin_home": _f(r.get("margin"), 1), "total": _f(r.get("total"), 1),
            "margin_p10": _f(r.get("margin_p10"), 1), "margin_p90": _f(r.get("margin_p90"), 1),
            "total_p10": _f(r.get("total_p10"), 1), "total_p90": _f(r.get("total_p90"), 1)}


def _market(s: dict, arc: pd.DataFrame) -> dict:
    from .market81 import american_to_prob, novig
    m = s.get("market_at_snapshot") or {}
    at = {"source": "nfldata line at forecast data refresh", "timestamp": (s.get("data_cutoff") or {}).get("data_refreshed_at"),
          "p_home_novig": _f(m.get("p_home_novig")), "spread_home": _f(m.get("spread_line"), 1),
          "home_moneyline": _f(m.get("home_moneyline"), 0), "away_moneyline": _f(m.get("away_moneyline"), 0)}
    latest = None
    if len(arc):
        a = arc[(arc["home"] == s["home_team"]) & (arc["away"] == s["away_team"])]
        if len(a):
            r = a.sort_values("retrieved_at").iloc[-1]

            def nv(h, w):
                try:
                    return _f(novig(american_to_prob([float(str(h).replace("+", ""))]), american_to_prob([float(str(w).replace("+", ""))]))[0])
                except (TypeError, ValueError):
                    return None
            latest = {"source": f"{r.get('provider')} via ESPN", "retrieved_at": r.get("retrieved_at"),
                      "p_home_novig_current": nv(r.get("home_ml_close"), r.get("away_ml_close")),
                      "p_home_novig_open": nv(r.get("home_ml_open"), r.get("away_ml_open")),
                      "spread_home_current": _f(-float(r["spread_current"]) if r.get("spread_current") is not None else None, 1),
                      "total_current": _f(r.get("total_current"), 1),
                      "home_moneyline_current": r.get("home_ml_close"), "away_moneyline_current": r.get("away_ml_close")}
    pc = s.get("p_champion")
    diff = _f(pc - at["p_home_novig"]) if pc is not None and at["p_home_novig"] is not None else None
    return {"at_forecast": at, "latest": latest, "champion_minus_market_at_forecast": diff,
            "comparable": at["p_home_novig"] is not None,
            "warning": "Prices are a benchmark, not a verified edge. The at-forecast price is the line at the forecast's data refresh; "
                       "the latest price may be newer than the forecast and is not directly comparable."}


def _performance() -> dict:
    out = {"historical": None, "prospective": None}
    try:
        from .specialists.baseline import load_oof
        from . import metrics as M
        x = load_oof()
        rows = []
        for label, seasons in (("walk-forward 2018-22 (development)", range(2018, 2023)), ("walk-forward 2023-24 (validation)", (2023, 2024)),
                               ("walk-forward 2025 (diagnostic)", (2025,))):
            d = x[x["season"].isin(seasons) & x["home_win"].notna()]
            if d.empty:
                continue
            y, p = d["home_win"].to_numpy(), d["p_weighted_average"].to_numpy()
            rows.append({"window": label, "games": int(len(d)), "accuracy": _f(((p > 0.5) == (y == 1)).mean()), "log_loss": _f(M.log_loss(y, p)),
                         "brier": _f(np.mean((p - y) ** 2)), "margin_mae": _f((d["margin_ensemble"] - d["margin"]).abs().mean(), 2)})
        out["historical"] = {"model": "champion", "note": "Historical walk-forward results; these seasons were examined during research, so "
                                                          "they are not untouched holdouts.", "windows": rows}
    except Exception:
        pass
    try:
        from .compare7 import collect, compare
        c = compare(collect(), "final")
        if c["games"]:
            out["prospective"] = {"stage": "final", "games": c["games"], "required_games": 128,
                                  "by_version": json.loads(c["by_version"].to_json(orient="records")),
                                  "note": "Genuinely prospective: immutable pregame archives scored after the game."}
        else:
            out["prospective"] = {"stage": "final", "games": 0, "required_games": 128, "by_version": [],
                                  "note": "No archived game has finished yet."}
    except Exception:
        pass
    return out


def build(now=None) -> dict:
    from .availability import player_names
    from .data_pipeline import GAMES_TABLE, load_feature_store
    from .market81 import espn_archive
    from .prospective import challenger_registry
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    led = _snapshots()
    games = pd.read_parquet(GAMES_TABLE).set_index("game_id")
    fs = load_feature_store().set_index("game_id")
    names = player_names()
    arc = espn_archive()
    reg = challenger_registry()
    labels = {h["version"]: h.get("label") for h in reg.get("hypotheses", [])}
    window_lo = now - pd.Timedelta(days=4)
    out_games = []
    latest_fc = None
    for gid, d in (led.groupby("game_id") if len(led) else []):
        kick = pd.Timestamp(d["kickoff_utc"].iloc[0])
        if kick < window_lo or kick > now + pd.Timedelta(days=10):
            continue
        s = _load(d.iloc[-1]["path"])
        if s is None:
            continue
        stages = []
        for r in d.itertuples(index=False):
            ss = _load(r.path)
            if ss:
                stages.append({"stage": ss.get("stage") or ss.get("window"), "archived_at": ss.get("predicted_at"), "p_home": _f(ss.get("p_champion")),
                               "timeliness": (ss.get("timing") or {}).get("timeliness")})
        pc = s.get("p_champion")
        ph = s.get("p_home") or {}
        vals = [v for v in ph.values() if v is not None]
        g = games.loc[gid] if gid in games.index else None
        done = bool(g["completed"]) if g is not None else False
        rec = {"game_id": gid, "season": int(s["season"]), "week": int(s["week"]), "home_team": s["home_team"], "away_team": s["away_team"],
               "kickoff_utc": s["kickoff_utc"], "status": "final" if done else ("in_progress_or_started" if kick <= now else "scheduled"),
               "final_score": ({"home": int(g["home_score"]), "away": int(g["away_score"])} if done else None),
               "forecast": {"stage": s.get("stage") or s.get("window"), "stage_label": s.get("stage_label"), "archived_at": s.get("predicted_at"),
                            "timeliness": (s.get("timing") or {}).get("timeliness"), "stale_inputs": bool(s.get("stale_data")),
                            "data_refreshed_at": (s.get("data_cutoff") or {}).get("data_refreshed_at"),
                            "champion": {"version": s.get("model_version"), "p_home": _f(pc),
                                         "predicted_winner": s["home_team"] if (pc or 0) >= 0.5 else s["away_team"],
                                         "margin_home": _f(s.get("margin_ensemble"), 1)},
                            "models": [{"key": k, "label": MODEL_LABELS.get(k, k), "p_home": _f(v), "margin_home": _f((s.get("margin_home") or {}).get(k), 1)}
                                       for k, v in ph.items()],
                            "disagreement": {"vote": s.get("vote"), "range": _f(max(vals) - min(vals)) if vals else None,
                                             "std": _f(float(np.std(vals))) if vals else None}},
               "stages": stages,
               "challengers": [{"version": v, "label": labels.get(v, v), "p_home": _f((c or {}).get("p_champion"))}
                               for v, c in (s.get("shadow_challengers") or {}).items() if isinstance(c, dict)],
               "player_intel": {"qb": {side: _qb(s, side, names) for side in ("home", "away")},
                                "lineups": ({side: _lineup(fs.loc[gid], s[f"{side}_team"]) for side in ("home", "away")}
                                            if (gid in fs.index and not done) else None),
                                "lineup_note": "Lineup analysis is computed at publication time from verified snap counts, official reports and "
                                               "roster status; it is not an input of the champion."},
               "simulation": _drive_sim(gid),
               "market": _market(s, arc)}
        out_games.append(rec)
        t = pd.Timestamp(s.get("predicted_at"))
        latest_fc = t if latest_fc is None or t > latest_fc else latest_fc
    cv = ARTIFACTS_DIR / "scheduler" / "code_version.json"
    release = json.loads(cv.read_text()) if cv.exists() else {}
    feed = {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "generated_at": now.isoformat(timespec="seconds"),
            "source": {"publisher": "NFL Ensemble Lab (local)", "scheduler_release": release.get("release"),
                       "champion_version": next((g["forecast"]["champion"]["version"] for g in out_games), None),
                       "challengers": [{"version": h["version"], "label": h.get("label"), "registered_at": h.get("registered_at")}
                                       for h in reg.get("hypotheses", [])]},
            "freshness": {"latest_forecast_archived_at": latest_fc.isoformat() if latest_fc is not None else None,
                          "stale_after_hours": STALE_AFTER_HOURS},
            "notices": NOTICES, "performance": _performance(),
            "games": sorted(out_games, key=lambda g: g["kickoff_utc"])}
    return feed


# --------------------------------------------------------------------------- contract validation (mirrors shared/nfl-intel.js)

def validate(feed: dict) -> list[str]:
    errs = []
    if feed.get("schema") != SCHEMA:
        errs.append("schema")
    if not str(feed.get("schema_version", "")).startswith("1."):
        errs.append("schema_version must be 1.x")
    for k in ("generated_at", "games", "freshness", "notices", "source"):
        if k not in feed:
            errs.append(f"missing {k}")
    for i, g in enumerate(feed.get("games") or []):
        for k in ("game_id", "home_team", "away_team", "kickoff_utc", "forecast"):
            if k not in g:
                errs.append(f"games[{i}] missing {k}")
        p = ((g.get("forecast") or {}).get("champion") or {}).get("p_home")
        if p is not None and not (0 <= p <= 1):
            errs.append(f"games[{i}] champion p out of range")
        fa, ko = (g.get("forecast") or {}).get("archived_at"), g.get("kickoff_utc")
        if fa and ko and pd.Timestamp(fa) >= pd.Timestamp(ko):
            errs.append(f"games[{i}] forecast archived after kickoff")
        for m in (g.get("forecast") or {}).get("models") or []:
            if m.get("p_home") is not None and not (0 <= m["p_home"] <= 1):
                errs.append(f"games[{i}] model p out of range")
    text = json.dumps(feed)
    for bad in ("C:\\\\", "/Users/", "OneDrive", "sha256", "feature_snapshot", "api_key", "token", "password"):
        if bad.lower() in text.lower():
            errs.append(f"forbidden content: {bad}")
    return errs
