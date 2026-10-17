"""Phase 6 scheduler: one lightweight 'tick' (Windows Task Scheduler, every 5 minutes,
pythonw, no console) manages every refresh and pregame snapshot.

Event plan (all times America/New_York, DST-aware; executed in UTC):
  daily     06:00 09:00 12:00 15:00 18:00 21:00 ET  -> full incremental refresh
  gameday   every :00/:30 from 3 h before the first kickoff of an ET date to its last kickoff
                                                    -> live refresh
  per game (relative to the CURRENT kickoff; a moved kickoff supersedes old events)
    early_week  Tuesday 12:00 ET of game week (if before kickoff)  -> refresh + snapshot
    friday      Friday 18:00 ET before kickoff (if before kickoff) -> refresh + snapshot
    t24h  kickoff-24h   -> refresh + snapshot
    t3h   kickoff-3h    -> live refresh (personnel / injuries)
    t90   kickoff-90min -> live refresh (inactives) + snapshot
    t60   kickoff-60min -> live refresh + snapshot
    final kickoff-30min -> live refresh + final snapshot
Each event may run from its time until the next stage of the same game (or kickoff-5min);
after that it is MISSED (never back-filled). One process at a time (lock file); the
Windows task also has MultipleInstances=IgnoreNew.
"""
from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime, timezone

import pandas as pd

from .config import ARTIFACTS_DIR

ET = "America/New_York"
SCHED_DIR = ARTIFACTS_DIR / "scheduler"
SCHED_DIR.mkdir(parents=True, exist_ok=True)
LOCK = SCHED_DIR / "tick.lock"
EVENTS = SCHED_DIR / "events.jsonl"     # append-only event outcomes
TICKS = SCHED_DIR / "ticks.jsonl"       # append-only tick log
PLAN = SCHED_DIR / "plan.json"
DAILY_HOURS = (6, 9, 12, 15, 18, 21)
SNAPSHOT_STAGES = ("early_week", "friday", "t24h", "t90", "t60", "final")
STAGE_ORDER = ("early_week", "friday", "t24h", "t3h", "t90", "t60", "final")
DAILY_GRACE = pd.Timedelta(hours=3)
GAMEDAY_GRACE = pd.Timedelta(minutes=30)
KICKOFF_MARGIN = pd.Timedelta(minutes=5)
LOCK_STALE = pd.Timedelta(minutes=40)


def _utc(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def et(ts) -> str:
    return _utc(ts).tz_convert(ET).strftime("%a %b %d %I:%M %p ET")


def _et_at(day, hour, minute=0) -> pd.Timestamp:
    """A wall-clock time in New York on a given date -> UTC (DST-aware)."""
    return pd.Timestamp(year=day.year, month=day.month, day=day.day, hour=hour, minute=minute).tz_localize(ET).tz_convert("UTC")


# --------------------------------------------------------------------------- plan

def stage_times(kickoff) -> dict:
    k = _utc(kickoff)
    kl = k.tz_convert(ET)
    out = {}
    tue = (kl - pd.Timedelta(days=(kl.weekday() - 1) % 7)).normalize()          # Tuesday on/before kickoff (ET)
    if kl.weekday() <= 1:                                                        # Mon/Tue games: previous Tuesday
        tue = tue - pd.Timedelta(days=7) if kl.weekday() == 1 else tue
    early = _et_at(tue, 12)
    if early < k - pd.Timedelta(hours=30):
        out["early_week"] = early
    fri = (kl - pd.Timedelta(days=(kl.weekday() - 4) % 7)).normalize()
    friday = _et_at(fri, 18)
    if friday < k - pd.Timedelta(hours=1) and (k - friday) < pd.Timedelta(days=5):
        out["friday"] = friday
    out |= {"t24h": k - pd.Timedelta(hours=24), "t3h": k - pd.Timedelta(hours=3), "t90": k - pd.Timedelta(minutes=90),
            "t60": k - pd.Timedelta(minutes=60), "final": k - pd.Timedelta(minutes=30)}
    return out


def build_plan(games: pd.DataFrame, start, end) -> pd.DataFrame:
    """games: game_id, kickoff_utc (current/authoritative), completed. Events in [start, end]."""
    start, end = _utc(start), _utc(end)
    rows = []
    d0 = start.tz_convert(ET).normalize()
    for i in range((end - start).days + 2):
        day = d0 + pd.Timedelta(days=i)
        for h in DAILY_HOURS:
            t = _et_at(day, h)
            if start - DAILY_GRACE <= t <= end:
                rows.append({"event_id": f"daily:{day.date()}:{h:02d}", "kind": "daily", "game_id": None, "stage": None,
                             "time_utc": t, "deadline_utc": t + DAILY_GRACE, "action": "full"})
    if games is None or games.empty or "kickoff_utc" not in games:
        games = pd.DataFrame(columns=["game_id", "kickoff_utc", "completed"])
    up = games[(~games["completed"].astype(bool)) & (pd.to_datetime(games["kickoff_utc"], utc=True) > start - pd.Timedelta(days=1))]
    up = up.assign(kick=pd.to_datetime(up["kickoff_utc"], utc=True))
    up = up[up["kick"] <= end + pd.Timedelta(days=9)]
    for day, g in up.groupby(up["kick"].dt.tz_convert(ET).dt.date):
        first, last = g["kick"].min() - pd.Timedelta(hours=3), g["kick"].max()
        t = first.ceil("30min")
        while t <= last:
            if start - GAMEDAY_GRACE <= t <= end:
                rows.append({"event_id": f"gameday:{t.tz_convert(ET):%Y-%m-%d:%H%M}", "kind": "gameday", "game_id": None, "stage": None,
                             "time_utc": t, "deadline_utc": t + GAMEDAY_GRACE, "action": "live"})
            t += pd.Timedelta(minutes=30)
    for r in up.itertuples(index=False):
        st = stage_times(r.kick)
        ordered = [s for s in STAGE_ORDER if s in st]
        for i, s in enumerate(ordered):
            t = st[s]
            nxt = st[ordered[i + 1]] if i + 1 < len(ordered) else r.kick - KICKOFF_MARGIN
            deadline = min(max(nxt, t + pd.Timedelta(minutes=10)), r.kick - KICKOFF_MARGIN)
            if t > end or deadline < start - pd.Timedelta(days=2):
                continue
            rows.append({"event_id": f"stage:{r.game_id}:{s}:{r.kick:%Y%m%dT%H%MZ}", "kind": "stage", "game_id": r.game_id, "stage": s,
                         "time_utc": t, "deadline_utc": deadline, "kickoff_utc": r.kick,
                         "action": "snapshot" if s in SNAPSHOT_STAGES else "live"})
    plan = pd.DataFrame(rows)
    return plan.sort_values("time_utc").reset_index(drop=True) if len(plan) else plan


def current_schedule() -> pd.DataFrame:
    """Scheduled games with ESPN's live kickoff time where available (handles moved games)."""
    from .data_pipeline import GAMES_TABLE
    from .live import kickoff_overrides
    g = pd.read_parquet(GAMES_TABLE)[["game_id", "season", "week", "home_team", "away_team", "kickoff_utc", "completed"]]
    o = kickoff_overrides(g)
    g = g.merge(o, on="game_id", how="left")
    moved = g["espn_kickoff_utc"].notna() & (g["espn_kickoff_utc"] != g["kickoff_utc"])
    g["kickoff_source"] = g["espn_kickoff_utc"].notna().map({True: "ESPN scoreboard", False: "nfldata schedule"})
    g.loc[moved, "kickoff_utc"] = g.loc[moved, "espn_kickoff_utc"]
    g["kickoff_moved"] = moved
    g["postponed"] = g["espn_status"].fillna("").str.contains("POSTPONED|CANCELED|SUSPENDED")
    return g[~g["postponed"]]


# --------------------------------------------------------------------------- ledger

def _read(path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _append(path, row: dict):
    for i in range(10):
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, default=str) + "\n")
            return
        except PermissionError:      # OneDrive / antivirus briefly holding the file
            time.sleep(0.3 * (i + 1))


def event_status() -> dict[str, dict]:
    """Final outcome per event id (last record wins)."""
    st = {}
    for r in _read(EVENTS):
        st[r["event_id"]] = r
    return st


# --------------------------------------------------------------------------- lock

def acquire_lock() -> bool:
    import psutil
    if LOCK.exists():
        try:
            info = json.loads(LOCK.read_text())
            alive = psutil.pid_exists(info["pid"])
            age = pd.Timestamp.now(tz="UTC") - pd.Timestamp(info["since"])
            if alive and age < LOCK_STALE:
                return False
        except Exception:
            pass
    LOCK.write_text(json.dumps({"pid": os.getpid(), "since": pd.Timestamp.now(tz="UTC").isoformat()}))
    return True


def release_lock():
    LOCK.unlink(missing_ok=True)


# --------------------------------------------------------------------------- tick

def classify(plan: pd.DataFrame, status: dict, now, ticks: list[dict], tracking_start) -> tuple[pd.DataFrame, list[dict]]:
    """Return (due events, newly missed records)."""
    now = _utc(now)
    due, missed = [], []
    tick_times = sorted(_utc(t["started_at"]) for t in ticks)
    for r in plan.itertuples(index=False):
        if r.event_id in status:
            continue
        if r.time_utc <= now < r.deadline_utc:
            due.append(r._asdict())
        elif r.deadline_utc <= now:
            if r.time_utc < tracking_start:
                reason = "before scheduler tracking started"
            elif not any(r.time_utc <= t < r.deadline_utc for t in tick_times):
                reason = "no scheduler run while the event window was open (PC off or asleep?)"
            else:
                reason = "scheduler ran but the event did not complete (see tick log errors)"
            missed.append(r._asdict() | {"outcome": "missed", "reason": reason, "recorded_at": now.isoformat()})
    return pd.DataFrame(due), missed


ON_TIME_GRACE = pd.Timedelta(minutes=5)     # one scheduler interval


def timeliness(scheduled, archived, kickoff, grace=ON_TIME_GRACE) -> str:
    """Policy (Phase 7.3). on_time: archived within one scheduler interval of the scheduled stage time;
    late_valid: later than that but still before kickoff; invalid_after_kickoff never happens (refused).
    'missed' (no archive before the stage deadline) and 'unavailable' (game/model/data could not produce a
    forecast) are recorded by the scheduler, never back-filled."""
    scheduled, archived, kickoff = _utc(scheduled), _utc(archived), _utc(kickoff)
    if archived >= kickoff:
        return "invalid_after_kickoff"
    return "on_time" if archived <= scheduled + grace else "late_valid"


def run_actions(due: pd.DataFrame, now, progress=print, actions=None) -> dict:
    """Execute merged actions once. Time-critical stage snapshots come first: when a snapshot and the daily
    full refresh are due in the same tick, the snapshot runs after a light refresh and the full refresh runs
    afterwards (Phase 7.3), so a multi-minute download never delays a pregame forecast."""
    actions = actions or {}
    full = actions.get("full", _do_full)
    live = actions.get("live", _do_live)
    snap = actions.get("snapshot", _do_snapshots)
    result = {"errors": []}
    kinds = set(due["action"])
    snaps = due[due["action"] == "snapshot"]
    # stored in lab.prospective: the scheduler runs as __main__, so a global here would be a different module object
    from . import prospective as _P
    _P.TICK_STARTED_AT = _utc(now)
    if len(snaps):
        try:
            result["refresh"] = live(progress)
        except Exception as exc:
            result["errors"].append(f"refresh failed: {exc!r}")
            result["refresh_failed"] = True
        try:
            result["snapshots"] = snap(snaps, progress, stale=result.get("refresh_failed", False))
        except Exception as exc:
            result["errors"].append(f"snapshot failed: {exc!r}")
        if "full" in kinds:
            try:
                result["refresh_full"] = full(progress)
            except Exception as exc:
                result["errors"].append(f"full refresh failed: {exc!r}")
                result["full_failed"] = True
        return result
    try:
        if "full" in kinds:
            result["refresh"] = full(progress)
        elif kinds & {"live", "snapshot"}:
            result["refresh"] = live(progress)
    except Exception as exc:
        result["errors"].append(f"refresh failed: {exc!r}")
        result["refresh_failed"] = True
        result["full_failed"] = "full" in kinds
    return result


def _after_refresh():
    """Cheap bookkeeping after any refresh: score finished games (snapshots are never edited)."""
    try:
        from .prospective import score
        score(progress=lambda m: None)
    except Exception:
        pass


def _do_full(progress):
    from .data_pipeline import refresh_data
    from .live import record_live_refresh, refresh_live
    lv = refresh_live(progress)
    record_live_refresh(lv)
    refresh_data(progress=progress)
    _after_refresh()
    if lv.get("failed"):
        raise RuntimeError(f"live sources failed: {lv['failed']}")
    return {"mode": "full", "live": lv}


def _do_live(progress):
    from .data_pipeline import rebuild_features
    from .live import record_live_refresh, refresh_live
    lv = refresh_live(progress)
    record_live_refresh(lv)
    rb = rebuild_features(progress)
    _after_refresh()
    if lv.get("failed") and not lv.get("ok"):
        raise RuntimeError(f"all live sources failed: {lv['failed']}")
    return {"mode": "live", "live": lv, "rebuild": rb}


def _do_snapshots(snaps: pd.DataFrame, progress, stale: bool = False) -> dict:
    from .prospective import write_stage_snapshots
    return write_stage_snapshots(snaps, progress=progress, stale_refresh=stale)


def tick(now=None, progress=print, actions=None, schedule: pd.DataFrame | None = None, horizon_days: int = 9) -> dict:
    now = _utc(now or pd.Timestamp.now(tz="UTC"))
    if not acquire_lock():
        return {"skipped": "another scheduler run is active"}
    log = {"started_at": now.isoformat(), "due": [], "missed": 0, "errors": []}
    try:
        try:
            import psutil
            p = psutil.Process()
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10)
        except Exception:
            pass
        ticks = _read(TICKS)
        tracking_start = _utc(ticks[0]["started_at"]) if ticks else now
        sched = schedule if schedule is not None else current_schedule()
        plan = build_plan(sched, now - pd.Timedelta(days=2), now + pd.Timedelta(days=horizon_days))
        PLAN.write_text(plan.to_json(orient="records", date_format="iso"), encoding="utf-8")
        status = event_status()
        superseded = _supersede(plan, status, now)
        due, missed = classify(plan, status, now, ticks, tracking_start)
        for m in missed + superseded:
            _append(EVENTS, m)
        log["missed"] = len(missed)
        log["superseded"] = len(superseded)
        if len(due):
            log["due"] = due["event_id"].tolist()
            res = run_actions(due, now, progress, actions)
            log["errors"] += res.get("errors", [])
            written = (res.get("snapshots") or {}).get("by_event", {})
            done_at = pd.Timestamp.now(tz="UTC") if actions is None else now
            for r in due.itertuples(index=False):
                ok = (bool(written.get(r.event_id, {}).get("ok")) if r.action == "snapshot"
                      else not res.get("full_failed") if r.action == "full" else not res.get("refresh_failed"))
                _append(EVENTS, r._asdict() | {"outcome": "done" if ok else "failed", "completed_at": done_at.isoformat(),
                                               "detail": written.get(r.event_id), "recorded_at": done_at.isoformat()})
            if actions is None:                       # research archives run strictly AFTER official forecasts are saved
                log["research"] = _post_forecast_research(due, written)
    except Exception:
        log["errors"].append(traceback.format_exc()[-1500:])
    finally:
        log["finished_at"] = pd.Timestamp.now(tz="UTC").isoformat()
        _append(TICKS, log)
        release_lock()
    return log


def _post_forecast_research(due: pd.DataFrame, written: dict) -> dict:
    """Phase 8.1: market odds archive + experimental drive-simulator distributions. Never raises, never affects
    official snapshots (they are already written when this runs)."""
    out = {}
    try:
        from .market81 import archive_espn_odds
        out["market"] = archive_espn_odds()
    except Exception as exc:
        out["market"] = {"ok": False, "reason": repr(exc)[:200]}
    try:
        ok = due[(due["action"] == "snapshot") & due["event_id"].map(lambda e: bool((written.get(e) or {}).get("ok")))]
        if len(ok):
            from .scoring81 import archive
            out["drive_sim"] = archive(ok)
    except Exception as exc:
        out["drive_sim"] = {"ok": False, "reason": repr(exc)[:200]}
    return out


def _supersede(plan: pd.DataFrame, status: dict, now) -> list[dict]:
    """Stage events planned for an OLD kickoff time that are no longer in the plan."""
    out = []
    current = set(plan["event_id"]) if len(plan) else set()
    prev = _read(SCHED_DIR / "planned.jsonl")
    seen = {p["event_id"] for p in prev}
    new_rows = [r for r in plan.to_dict("records") if r["event_id"] not in seen and r["kind"] == "stage"]
    for r in new_rows:
        _append(SCHED_DIR / "planned.jsonl", {"event_id": r["event_id"], "game_id": r["game_id"], "stage": r["stage"],
                                             "time_utc": str(r["time_utc"]), "kickoff_utc": str(r["kickoff_utc"])})
    for p in prev:
        if p["event_id"] not in current and p["event_id"] not in status and _utc(p["time_utc"]) > now - pd.Timedelta(days=2):
            same_game_current = any(e.startswith(f"stage:{p['game_id']}:{p['stage']}:") for e in current)
            if same_game_current:
                out.append({"event_id": p["event_id"], "kind": "stage", "game_id": p["game_id"], "stage": p["stage"],
                            "time_utc": p["time_utc"], "outcome": "superseded", "reason": "kickoff time changed",
                            "recorded_at": _utc(now).isoformat()})
    return out


# --------------------------------------------------------------------------- views

def upcoming_events(hours: int = 48, now=None) -> pd.DataFrame:
    now = _utc(now or pd.Timestamp.now(tz="UTC"))
    if not PLAN.exists():
        return pd.DataFrame()
    plan = pd.DataFrame(json.loads(PLAN.read_text(encoding="utf-8")))
    if plan.empty:
        return plan
    for c in ("time_utc", "deadline_utc"):
        plan[c] = pd.to_datetime(plan[c], utc=True)
    st = event_status()
    plan["status"] = plan["event_id"].map(lambda e: st.get(e, {}).get("outcome", "pending"))
    plan["time_et"] = plan["time_utc"].map(et)
    return plan[(plan["time_utc"] <= now + pd.Timedelta(hours=hours)) & (plan["deadline_utc"] >= now - pd.Timedelta(hours=hours))]


def event_history() -> pd.DataFrame:
    df = pd.DataFrame(_read(EVENTS))
    if len(df):
        df["time_et"] = df["time_utc"].map(et)
    return df


def tick_history() -> pd.DataFrame:
    return pd.DataFrame(_read(TICKS))


def next_for_game(game_id: str, now=None) -> dict:
    up = upcoming_events(24 * 9, now)
    if up.empty:
        return {}
    pend = up[up["status"] == "pending"]
    nxt_refresh = pend[pend["action"].isin(["full", "live"]) | ((pend["game_id"] == game_id) & (pend["action"] == "live"))]
    nxt_snap = pend[(pend["game_id"] == game_id) & (pend["action"] == "snapshot")]
    return {"next_refresh_et": nxt_refresh["time_et"].iloc[0] if len(nxt_refresh) else None,
            "next_snapshot_et": (nxt_snap["time_et"].iloc[0] + f" ({nxt_snap['stage'].iloc[0]})") if len(nxt_snap) else None}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="lab.scheduler")
    ap.add_argument("cmd", choices=["tick", "plan"])
    a = ap.parse_args(argv)
    if a.cmd == "tick":
        print(json.dumps(tick(), indent=2, default=str))
    else:
        tick_free = build_plan(current_schedule(), pd.Timestamp.now(tz="UTC"), pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=3))
        print(tick_free.assign(time_et=tick_free["time_utc"].map(et))[["event_id", "time_et", "action"]].to_string())


if __name__ == "__main__":
    main()
