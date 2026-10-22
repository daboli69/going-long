"""Phase 6 live football intelligence: timestamped, archived, change-tracked.

Sources (free, no authentication):
  * nflverse injuries (official NFL injury report, practice participation)  -> MODEL INPUT
    (the only availability source the models were trained on)
  * nflverse depth_charts (daily ESPN snapshots, `dt` timestamp)             -> monitoring
  * ESPN injuries feed (statuses incl. IR; 'inactive' / coach's-decision
    designations appear once teams announce inactives)                       -> monitoring
  * ESPN transactions feed (IR placements/activations, practice-squad
    elevations, signings, releases, trades)                                    -> monitoring
  * ESPN scoreboard (live kickoff times, postponements, game status)         -> scheduling
Monitoring-only sources never change model features (no untrained distributions);
they drive warnings, readiness and the debate. No complete official game-day
inactive list is freely available: ESPN-reported inactives are partial.
Missing information is never treated as 'healthy'.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import sources
from .availability import ARCHIVE_DIR, _team, espn_latest
from .config import CACHE_DIR

ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
LIVE_DIR = ARCHIVE_DIR / "live"
LIVE_DIR.mkdir(parents=True, exist_ok=True)
CHANGES = LIVE_DIR / "changes.jsonl"          # append-only change log
TRANSACTIONS = LIVE_DIR / "transactions.jsonl"  # append-only, de-duplicated
SCOREBOARD = CACHE_DIR / "espn_scoreboard.json"
ET = "America/New_York"


def _now():
    return datetime.now(timezone.utc)


def _append(path, rows):
    if not rows:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")


def _read(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


# --------------------------------------------------------------------------- scoreboard / kickoff times

def fetch_scoreboard(dates: list[str] | None = None) -> dict:
    """ESPN scoreboard for the current week (and optional YYYYMMDD dates). Kept on disk; on
    failure the last valid copy stays in place."""
    events = {}
    urls = [f"{ESPN}/scoreboard"] + [f"{ESPN}/scoreboard?dates={d}" for d in (dates or [])]
    for u in urls:
        body, _ = sources._fetch(u, timeout=30, retries=2)
        for e in json.loads(body).get("events", []):
            comp = e["competitions"][0]
            teams = {c["homeAway"]: _team(c["team"]["abbreviation"]) for c in comp["competitors"]}
            events[e["id"]] = {"espn_id": e["id"], "home": teams.get("home"), "away": teams.get("away"),
                               "kickoff_utc": e["date"], "status": e["status"]["type"]["name"],
                               "neutral": comp.get("neutralSite", False)}
    payload = {"retrieved_at": _now().isoformat(timespec="seconds"), "events": list(events.values())}
    SCOREBOARD.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def kickoff_overrides(games: pd.DataFrame) -> pd.DataFrame:
    """Latest ESPN kickoff time/status for scheduled games (rescheduled games move here)."""
    if not SCOREBOARD.exists():
        return pd.DataFrame(columns=["game_id", "espn_kickoff_utc", "espn_status", "scoreboard_retrieved_at"])
    sb = json.loads(SCOREBOARD.read_text(encoding="utf-8"))
    ev = pd.DataFrame(sb["events"])
    if ev.empty:
        return pd.DataFrame(columns=["game_id", "espn_kickoff_utc", "espn_status", "scoreboard_retrieved_at"])
    up = games[~games["completed"]][["game_id", "home_team", "away_team", "kickoff_utc"]]
    m = up.merge(ev, left_on=["home_team", "away_team"], right_on=["home", "away"], how="inner")
    m["espn_kickoff_utc"] = pd.to_datetime(m["kickoff_utc_y"], utc=True)
    # same matchup within 10 days of the scheduled kickoff (guards against rematches)
    m = m[(m["espn_kickoff_utc"] - pd.to_datetime(m["kickoff_utc_x"], utc=True)).abs() < pd.Timedelta(days=10)]
    return m.rename(columns={"status": "espn_status"}).assign(scoreboard_retrieved_at=sb["retrieved_at"])[
        ["game_id", "espn_kickoff_utc", "espn_status", "scoreboard_retrieved_at"]]


# --------------------------------------------------------------------------- transactions

TX_TYPES = [("activated", "activated / returned"), ("injured reserve", "IR placement"), ("elevated", "practice-squad elevation"),
            ("practice squad", "practice-squad move"), ("waived", "waived / released"), ("released", "waived / released"),
            ("signed", "signed"), ("traded", "trade"), ("suspend", "suspension"), ("reserve", "reserve list move")]


def classify_transaction(desc: str) -> str:
    d = desc.lower()
    for k, v in TX_TYPES:
        if k in d:
            return v
    return "other"


def fetch_transactions(pages: int = 2) -> int:
    """Append new ESPN transactions (de-duplicated by date+team+description). Returns # new."""
    seen = {(r["date"], r["team"], r["description"]) for r in _read(TRANSACTIONS)}
    new = []
    for page in range(1, pages + 1):
        body, _ = sources._fetch(f"{ESPN}/transactions?page={page}", timeout=30, retries=2)
        for t in json.loads(body).get("transactions", []):
            team = _team((t.get("team") or {}).get("abbreviation", ""))
            row = {"date": t.get("date"), "team": team, "description": t.get("description", ""),
                   "type": classify_transaction(t.get("description", "")), "retrieved_at": _now().isoformat(timespec="seconds")}
            key = (row["date"], row["team"], row["description"])
            if key not in seen:
                seen.add(key)
                new.append(row)
    _append(TRANSACTIONS, new)
    return len(new)


def transactions(team: str | None = None, since=None) -> pd.DataFrame:
    df = pd.DataFrame(_read(TRANSACTIONS))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], utc=True)
    if team:
        df = df[df["team"] == team]
    if since is not None:
        df = df[df["date"] >= since]
    return df.sort_values("date", ascending=False)


# --------------------------------------------------------------------------- change tracking

def _state_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


STATE = LIVE_DIR / "last_state.json"


def track_changes(official: pd.DataFrame, espn: pd.DataFrame, qb1: dict) -> int:
    """Compare the newest official report statuses, ESPN statuses and depth-chart QB1 with the
    previous refresh; append every change (with both timestamps) to the change log."""
    prev = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    cur = {"official": {f"{r.team}|{r.full_name}": [r.report_status, r.practice_status] for r in official.itertuples()} if len(official) else {},
           "espn": {f"{r.team}|{r.player}": r.status for r in espn.itertuples()} if len(espn) else {},
           "qb1": {t: v[0] for t, v in qb1.items()}}
    now = _now().isoformat(timespec="seconds")
    rows = []
    for src in ("official", "espn", "qb1"):
        a, b = prev.get(src, {}), cur[src]
        if not a:      # first observation: nothing to compare against
            continue
        for k in set(a) | set(b):
            if a.get(k) != b.get(k):
                team, who = (k.split("|", 1) + [""])[:2] if src != "qb1" else (k, "QB1")
                rows.append({"detected_at": now, "source": src, "team": team, "player": who, "before": a.get(k), "after": b.get(k)})
    _append(CHANGES, rows)
    STATE.write_text(json.dumps(cur, default=str), encoding="utf-8")
    return len(rows)


def changes(team: str | None = None, since=None) -> pd.DataFrame:
    df = pd.DataFrame(_read(CHANGES))
    if df.empty:
        return df
    df["detected_at"] = pd.to_datetime(df["detected_at"], utc=True)
    if team:
        df = df[df["team"] == team]
    if since is not None:
        df = df[df["detected_at"] >= since]
    return df.sort_values("detected_at", ascending=False)


def espn_inactives(espn: pd.DataFrame) -> pd.DataFrame:
    """Players ESPN marks inactive / coach's decision (partial; not the official list)."""
    if espn.empty or "fantasy" not in espn.columns:
        return pd.DataFrame(columns=["team", "player", "position", "status", "updated"])
    m = espn["fantasy"].fillna("").str.lower().eq("inactive") | espn["detail_type"].fillna("").str.lower().str.contains("coach")
    return espn[m][["team", "player", "position", "status", "updated"]]


def espn_full() -> tuple[pd.DataFrame, str | None]:
    """ESPN injuries with fantasy-status/detail fields (for inactive detection)."""
    files = sorted(ARCHIVE_DIR.glob("espn_injuries_*.json"))
    if not files:
        return pd.DataFrame(), None
    payload = json.loads(files[-1].read_text(encoding="utf-8"))
    rows = []
    for t in payload.get("injuries", []):
        for i in t.get("injuries", []):
            a = i.get("athlete", {})
            det = i.get("details") or {}
            rows.append({"team": _team(a.get("team", {}).get("abbreviation", "")), "player": a.get("displayName"),
                         "position": (a.get("position") or {}).get("abbreviation"), "status": i.get("status"),
                         "updated": i.get("date"), "fantasy": ((det.get("fantasyStatus") or {}).get("description")),
                         "detail_type": det.get("type"), "return_date": det.get("returnDate"), "note": i.get("shortComment")})
    return pd.DataFrame(rows), files[-1].stem.split("_")[-1]


# --------------------------------------------------------------------------- refresh (light)

def _ok(h: dict) -> dict:
    if not h.get("ok"):
        raise RuntimeError(h.get("error") or "failed")
    return h


def refresh_live(progress=print) -> dict:
    """Live sources only (seconds, small downloads). Each source fails independently and keeps
    its last valid copy; failures are reported, never silently treated as 'no news'."""
    from .availability import depth_chart_qb1, load_injury_rows
    from .data_pipeline import current_season
    out = {"at": _now().isoformat(timespec="seconds"), "ok": [], "failed": {}}
    season = current_season()
    from . import availability
    from . import extra_sources as X
    for name, fn in (("schedule (nfldata games.csv)", lambda: sources.download("nfldata_games", sources.GAMES_URL, sources.RAW_DIR / "games.csv",
                                                                               max_age_hours=0.33, validate=sources._validate_games_csv,
                                                                               progress=lambda m: None)),
                     ("espn_scoreboard", lambda: fetch_scoreboard()),
                     ("espn_transactions", lambda: fetch_transactions()),
                     ("official_injuries+depth+espn_injuries", lambda: availability.refresh_sources([season], season, progress=lambda m: None, live_only=True)),
                     ("nflcom_injury_report", lambda: _ok(X.fetch_nflcom())),
                     ("nflverse_weekly_rosters", lambda: _ok(X.fetch_weekly_rosters(season))),
                     ("sleeper_players (monitoring)", lambda: _ok(X.fetch_sleeper()))):
        try:
            r = fn()
            if isinstance(r, dict) and r.get("errors"):
                raise RuntimeError("; ".join(r["errors"]))
            out["ok"].append(name)
        except Exception as exc:
            out["failed"][name] = repr(exc)[:300]
    try:
        rows = load_injury_rows([season])
        latest = rows[rows["source"].str.startswith("lab archive")] if len(rows) else rows
        if len(latest):
            latest = latest[latest["available_at"] == latest["available_at"].max()]
        espn, _ = espn_full()
        qb1, _ = depth_chart_qb1(season)
        out["changes_detected"] = track_changes(latest, espn, qb1)
    except Exception as exc:
        out["failed"]["change_tracking"] = repr(exc)[:300]
    try:
        from .fpds_injury_confirmation import update_imported_weeks
        out['fpds_injury_confirmation']=update_imported_weeks()
    except Exception as exc:
        # Subscription error details stay private; original refreshes remain independent.
        from .fpds_research.common import private_error
        private_error('fpds_injury_confirmation')
        out['fpds_injury_confirmation_error']=type(exc).__name__
    return out


def source_freshness() -> pd.DataFrame:
    """Age of every live source's last successful retrieval (nothing is invented)."""
    man = sources.load_manifest()
    now = _now()
    rows = []
    def age(ts):
        return round((now - pd.Timestamp(ts).to_pydatetime()).total_seconds() / 3600, 2) if ts else None
    season = max([int(k.rsplit("_", 1)[1]) for k in man if k.startswith("nflverse_injuries_") and k.rsplit("_", 1)[1].isdigit()] or [0])
    for key, label in (("nfldata_games", "schedule & lines (nfldata)"), (f"nflverse_injuries_{season}", "official injury report (nflverse)"),
                       (f"nflverse_depth_{season}", "depth charts (nflverse/ESPN)")):
        ts = man.get(key, {}).get("downloaded_at")
        rows.append({"source": label, "last_success": ts, "age_hours": age(ts)})
    _, espn_t = espn_latest()
    rows.append({"source": "ESPN injuries", "last_success": pd.Timestamp(datetime.strptime(espn_t, "%Y%m%dT%H%M%SZ"), tz="UTC").isoformat()
                 if espn_t else None, "age_hours": age(pd.Timestamp(datetime.strptime(espn_t, "%Y%m%dT%H%M%SZ"), tz="UTC")) if espn_t else None})
    sb = json.loads(SCOREBOARD.read_text(encoding="utf-8"))["retrieved_at"] if SCOREBOARD.exists() else None
    rows.append({"source": "ESPN scoreboard (kickoff times)", "last_success": sb, "age_hours": age(sb)})
    tx = _read(TRANSACTIONS)
    last_tx = max((r["retrieved_at"] for r in tx), default=None)
    rows.append({"source": "ESPN transactions", "last_success": last_tx, "age_hours": age(last_tx)})
    from . import extra_sources as X
    _, nf_t = X.nflcom_latest()
    h = X.source_health().set_index("source") if X.HEALTH.exists() else pd.DataFrame()
    # NFL.com archives only on content change, so the last successful check is the freshness signal
    nf_ok = h.loc["NFL.com injury report", "last_ok"] if "NFL.com injury report" in h.index else nf_t
    rows.append({"source": "NFL.com official injury report", "last_success": None if pd.isna(nf_ok) else pd.Timestamp(nf_ok).isoformat(),
                 "age_hours": None if pd.isna(nf_ok) else age(nf_ok)})
    ts = man.get(f"nflverse_roster_weekly_{season}", {}).get("downloaded_at")
    rows.append({"source": "weekly rosters (nflverse)", "last_success": ts, "age_hours": age(ts)})
    _, sl_t = X.sleeper_latest()
    rows.append({"source": "Sleeper players (monitoring, daily)", "last_success": sl_t.isoformat() if sl_t is not None else None,
                 "age_hours": age(sl_t) if sl_t is not None else None, "limit_hours": 30})
    df = pd.DataFrame(rows)
    lim = df["limit_hours"].fillna(12) if "limit_hours" in df else 12
    df["state"] = np.where(df["age_hours"].isna(), "unavailable", np.where(df["age_hours"] > lim, "stale", "fresh"))
    return df.drop(columns=["limit_hours"], errors="ignore")


# --------------------------------------------------------------------------- readiness

LIVE_STATUS = LIVE_DIR / "last_live_refresh.json"


def record_live_refresh(result: dict) -> None:
    LIVE_STATUS.write_text(json.dumps(result, default=str), encoding="utf-8")


def last_live_refresh() -> dict:
    return json.loads(LIVE_STATUS.read_text(encoding="utf-8")) if LIVE_STATUS.exists() else {}


def official_qb_status(season: int) -> dict:
    """(team, player name) -> latest official pregame game status (nflverse/NFL.com rows, newest week)."""
    try:
        from .availability import load_injury_rows
        r = load_injury_rows([season])
    except Exception:
        return {}
    if not len(r):
        return {}
    wk = int(r["week"].max())
    r = r[r["week"] == wk].sort_values("available_at")
    out = {(t, n): s for t, n, s in zip(r["team"], r["full_name"], r["report_status"]) if isinstance(s, str)}
    nv_t = pd.to_datetime(r["available_at"], utc=True, errors="coerce").max()
    out["_week"], out["_source"], out["_retrieved"] = wk, "nflverse official report", str(nv_t)
    # Phase 7.3: prefer the NFL.com copy of the same league report when it is newer (monitoring only)
    try:
        from . import extra_sources as X
        nf, nf_t = X.nflcom_latest()
        if len(nf) and nf_t is not None and int(nf["season"].max()) == season:
            nwk = int(nf["week"].max())
            if nwk > wk or (nwk == wk and (pd.isna(nv_t) or nf_t > nv_t)):
                n = nf[nf["week"] == nwk]
                out = {(t, nm): st for t, nm, st in zip(n["team"], n["full_name"], n["report_status"]) if isinstance(st, str)}
                out["_week"], out["_source"], out["_retrieved"] = nwk, "NFL.com official report", str(nf_t)
    except Exception:
        pass
    return out                               # a report covers only its own week's games (_week)


def _qb_certainty(row: pd.Series, side: str, qb1: dict, espn: pd.DataFrame, names: dict,
                  official: dict | None = None) -> tuple[str, str]:
    """An alternative QB named by a static source (depth chart, nfldata listing) does NOT create a conflict
    when the official report lists him Out/Doubtful: the projection already accounts for that."""
    official = official or {}
    if official.get("_week") != row.get("week"):
        official = {}
    proj = names.get(row.get(f"{side}_qb_projected_id"), row.get(f"{side}_qb_projected_id"))
    team = row[f"{side}_team"]
    if not isinstance(proj, str):
        return "unavailable", "no projected starter"
    if row.get(f"{side}_qb_projected_out", 0) == 1:
        return "changed", f"official report lists the usual starter Out/Doubtful; replacement projected: {proj}"
    notes = []
    if row.get(f"{side}_qb_questionable", 0) == 1:
        notes.append("projected starter Questionable")
    st = espn[(espn["team"] == team) & (espn["player"] == proj)]["status"].tolist() if len(espn) else []
    if st and st[0] not in ("Active",):
        notes.append(f"ESPN lists {proj} as {st[0]}")
    v2 = names.get(row.get(f"{side}_qb7_projected_id"), row.get(f"{side}_qb7_projected_id"))
    if isinstance(v2, str) and v2 != proj:
        notes.append(f"QB projection v2 (Phase 7) expects {v2} to return" if row.get(f"{side}_qb7_returning", 0) == 1
                     else f"QB projection v2 (Phase 7) projects {v2}")
    explained = []
    for src, alt_ in (("ESPN depth chart QB1", qb1.get(team, (None,))[0]), ("nfldata listing", row.get(f"{side}_qb_name"))):
        if not isinstance(alt_, str) or alt_ == proj:
            continue
        if official.get((team, alt_)) in ("Out", "Doubtful"):
            explained.append(f"{src} names {alt_}, but the official report lists him {official[(team, alt_)]}")
        else:
            notes.append(f"{src} is {alt_}")
    if notes:
        return "uncertain", "; ".join(notes + explained)
    tail = f" ({'; '.join(explained)})" if explained else ""
    return "consistent", f"{proj}: projection agrees with the official report and listings (not a confirmation){tail}"


def game_readiness(games: pd.DataFrame, now=None) -> pd.DataFrame:
    """Per upcoming game: freshness and completeness labels. Nothing here is a confidence score."""
    from .availability import depth_chart_qb1, player_names
    from .data_pipeline import current_season, load_status
    from .scheduler import et, next_for_game
    now = pd.Timestamp(now or _now())
    status = load_status()
    lr = last_live_refresh()
    fresh = source_freshness()
    missing = fresh[fresh["state"] != "fresh"]["source"].tolist()
    espn, _ = espn_full()
    ina = espn_inactives(espn)
    qb1, _ = depth_chart_qb1(current_season())
    names = player_names()
    official = official_qb_status(current_season())
    snaps_latest = {}
    try:
        from .players import snap_shares
        from .data_pipeline import GAMES_TABLE
        gt = pd.read_parquet(GAMES_TABLE)
        sn = snap_shares(gt, [current_season()])
        snaps_latest = sn.groupby("team")["kickoff_utc"].max().to_dict()
        last_played = pd.concat([gt[gt["completed"]][["home_team", "kickoff_utc"]].rename(columns={"home_team": "team"}),
                                 gt[gt["completed"]][["away_team", "kickoff_utc"]].rename(columns={"away_team": "team"})]).groupby("team")["kickoff_utc"].max()
    except Exception:
        last_played = pd.Series(dtype="datetime64[ns, UTC]")
    rows = []
    for _, g in games.iterrows():
        k = pd.Timestamp(g["kickoff_utc"])
        hrs = (k - now).total_seconds() / 3600
        r = {"game": f"{g['away_team']} @ {g['home_team']}", "game_id": g["game_id"], "kickoff_et": et(k),
             "time_to_kickoff": f"{int(hrs // 24)}d {int(hrs % 24)}h" if hrs >= 24 else f"{hrs:.1f} h",
             "latest_full_refresh": (status.get("refreshed_at") or "never"), "latest_live_refresh": lr.get("at", "never"),
             "missing_or_stale_sources": ", ".join(missing) or "none"}
        both = g.get("home_inj_report_available") == 1 and g.get("away_inj_report_available") == 1
        one = (g.get("home_inj_report_available") == 1) or (g.get("away_inj_report_available") == 1)
        r["injury_report"] = "complete (final designations, both teams)" if both else ("incomplete (one team / practice only)" if one
                                                                                      else "incomplete (no final designations yet)")
        for side in ("home", "away"):
            lab_, note = _qb_certainty(g, side, qb1, espn, names, official)
            r[f"{side}_qb"] = f"{lab_}: {note}"
            t = g[f"{side}_team"]
            latest_snap, latest_game = snaps_latest.get(t), last_played.get(t)
            r[f"{side}_lineup"] = ("unavailable" if latest_snap is None else
                                   "current (snap counts include last game)" if latest_game is None or latest_snap >= latest_game
                                   else f"stale (snap counts end {et(latest_snap)})")
        if hrs > 2:
            r["inactives"] = "not yet expected (teams announce ~90 min before kickoff)"
        else:
            n = int(ina["team"].isin([g["home_team"], g["away_team"]]).sum()) if len(ina) else 0
            r["inactives"] = (f"ESPN-reported inactives seen: {n} (partial; official list not freely available)" if n
                              else "unavailable (no ESPN-reported inactives yet)")
        st = g.get("home_p5_model_staleness_days")
        r["player_model"] = "unavailable" if pd.isna(st) else (f"stale ({int(st)} days since newest play)" if st > 14 else "current")
        r |= next_for_game(g["game_id"], now)
        rows.append(r)
    return pd.DataFrame(rows)
