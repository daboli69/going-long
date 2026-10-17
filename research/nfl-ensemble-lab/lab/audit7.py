"""Phase 7 live-weekend audit: checks completed scheduler work only (never scores unplayed games)."""
from __future__ import annotations

import hashlib
import json
import os
import stat

import pandas as pd

from .config import ARTIFACTS_DIR, SNAPSHOTS_DIR

SCHED = ARTIFACTS_DIR / "scheduler"
PROS = SNAPSHOTS_DIR / "prospective"


def _jsonl(p) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def run(now=None) -> dict:
    from .prospective import challenger_registry, scored_table
    from .training import current_version
    now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC"))
    out = {"audited_at": now.isoformat(timespec="seconds"), "checks": []}

    def check(name, ok, detail):
        out["checks"].append({"check": name, "ok": bool(ok), "detail": detail})

    ticks = pd.DataFrame(_jsonl(SCHED / "ticks.jsonl"))
    if len(ticks):
        t = pd.to_datetime(ticks["started_at"], utc=True).sort_values()
        gaps = t.diff().dt.total_seconds().div(60)
        n_err = int(ticks["errors"].map(len).sum())
        check("scheduler ticks", n_err == 0, f"{len(ticks)} ticks {t.min():%Y-%m-%d %H:%M} -> {t.max():%Y-%m-%d %H:%M} UTC, "
              f"{n_err} errors, longest gap {gaps.max():.0f} min, gaps > 15 min: {int((gaps > 15).sum())}")
    ev = pd.DataFrame(_jsonl(SCHED / "events.jsonl"))
    if len(ev):
        done = ev[ev["outcome"] == "done"]
        first_tick = pd.to_datetime(ticks["started_at"], utc=True).min() if len(ticks) else now
        miss = ev[ev["outcome"] == "missed"]
        pre = miss[pd.to_datetime(miss["deadline_utc"], utc=True) < first_tick] if "deadline_utc" in miss else miss
        check("missed events explained", len(pre) == len(miss),
              f"{len(miss)} missed, {len(pre)} of them were due before the scheduler's first tick ({first_tick:%Y-%m-%d %H:%M} UTC)")
        late = done[pd.to_datetime(done["completed_at"], utc=True, format="ISO8601") > pd.to_datetime(done["deadline_utc"], utc=True)] \
            if "deadline_utc" in done else done.iloc[:0]
        check("scheduled events", (ev["outcome"] != "failed").all() and late.empty,
              f"{len(ev)} events: " + ", ".join(f"{k} {v}" for k, v in ev["outcome"].value_counts().items()) +
              f"; completed after deadline: {len(late)}")
        st = ev[ev["kind"] == "stage"] if "kind" in ev else ev.iloc[:0]
        check("stage snapshots by stage", True, ", ".join(f"{k}: {v}" for k, v in st.groupby("stage")["outcome"].apply(
            lambda s: int((s == "done").sum())).items()) or "none yet")
    led = pd.DataFrame(_jsonl(PROS / "ledger.jsonl"))
    if len(led):
        led["predicted_at"] = pd.to_datetime(led["predicted_at"], utc=True, format="ISO8601")
        led["kickoff_utc"] = pd.to_datetime(led["kickoff_utc"], utc=True, format="ISO8601")
        after = led[led["predicted_at"] >= led["kickoff_utc"]]
        check("snapshots made before kickoff", after.empty, f"{len(led)} ledger entries; after kickoff: {len(after)}")
        missing, writable, mism = [], [], []
        for r in led.itertuples(index=False):
            p = SNAPSHOTS_DIR / str(r.path).replace("\\", os.sep)
            if not p.exists():
                missing.append(r.path)
                continue
            if os.stat(p).st_mode & stat.S_IWRITE:
                writable.append(r.path)
            h = json.loads(p.read_text(encoding="utf-8")).get("content_hash")
            if h and h != r.content_hash:
                mism.append(r.path)
        check("snapshot files intact (exist, read-only, hash matches ledger)", not (missing or writable or mism),
              f"missing {len(missing)}, writable {len(writable)}, hash mismatch {len(mism)}")
        dup = led.groupby(["game_id", "window", "path"]).size()
        check("no overwrites (one ledger entry per file)", (dup == 1).all(), f"{int((dup > 1).sum())} files with >1 entry")
        versions = sorted(led["model_version"].unique())
        check("champion version in snapshots", versions == [current_version()], f"versions seen: {versions}; current {current_version()}")
        chal = []
        for r in led.tail(20).itertuples(index=False):
            snap = json.loads((SNAPSHOTS_DIR / str(r.path).replace("\\", os.sep)).read_text(encoding="utf-8"))
            chal.append(sorted((snap.get("shadow_challengers") or {}).keys()))
        reg = [h["version"] for h in challenger_registry()["hypotheses"]]
        tracked = sorted(set().union(*map(set, chal))) if chal else []
        last_t = led["predicted_at"].max()
        due = [h["version"] for h in challenger_registry()["hypotheses"] if pd.Timestamp(h["registered_at"]) < last_t - pd.Timedelta(hours=1)]
        check("registered challengers tracked in recent snapshots", all(v in tracked for v in due),
              f"registered {reg}; present in last 20 snapshots: {tracked}")
        kicked = led[led["kickoff_utc"] < now]["game_id"].nunique()
        st_ = scored_table()
        check("scoring (played games only)", True, f"games with archived snapshots that have kicked off: {kicked}; "
              f"scored rows: {0 if st_ is None else len(st_)} (unplayed games are never scored)")
    hp = ARTIFACTS_DIR / "discovery" / "prospective_hypotheses.joblib"
    if hp.exists():
        import joblib
        h = joblib.load(hp)
        n = len(h.get("hypotheses", h)) if isinstance(h, dict) else len(h)
        digest = hashlib.sha256(hp.read_bytes()).hexdigest()[:16]
        ref = ARTIFACTS_DIR / "phase7" / "hypotheses_sha.txt"
        ref.parent.mkdir(parents=True, exist_ok=True)
        if not ref.exists():
            ref.write_text(digest)
        check("10 frozen upset hypotheses unchanged", n == 10 and ref.read_text().strip() == digest,
              f"{n} hypotheses; file hash {digest} (reference {ref.read_text().strip()}); last modified "
              f"{pd.Timestamp(hp.stat().st_mtime, unit='s', tz='UTC'):%Y-%m-%d %H:%M} UTC")
    try:
        stt = stage_table(now)
        arc = stt[stt["archived_at"].notna()] if "archived_at" in stt else stt.iloc[:0]
        if len(arc):
            by = arc.groupby("stage").agg(n=("game_id", "size"), no_final_report=("final_report_both", lambda x: int((~x.astype(bool)).sum())),
                                          max_lag=("lag_min", "max"), challengers_complete=("challengers_saved", lambda x: int(sum(
                                              a_.split("/")[0] == a_.split("/")[1] for a_ in x))))
            check("forecast inputs by stage", True, "; ".join(
                f"{k}: {int(r.n)} archived, {int(r.no_final_report)} without a verified final injury report, max lag {r.max_lag:.0f} min, "
                f"champion+all challengers saved together {int(r.challengers_complete)}/{int(r.n)}" for k, r in by.iterrows()))
            check("all archived stages before kickoff and read-only", bool(arc["before_kickoff"].all() and arc["read_only"].all()),
                  f"{len(arc)} stage snapshots")
        stt.to_csv(ARTIFACTS_DIR / "phase7" / "stage_table.csv", index=False)
    except Exception as exc:
        check("stage table", False, repr(exc)[:200])
    (ARTIFACTS_DIR / "phase7").mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "phase7" / "weekend_audit.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def load() -> dict:
    p = ARTIFACTS_DIR / "phase7" / "weekend_audit.json"
    return json.loads(p.read_text()) if p.exists() else {}


# --------------------------------------------------------------------------- Phase 7.1: per game x stage

def stage_table(now=None) -> pd.DataFrame:
    """Every planned kickoff-relative stage with its outcome, archive time and what the forecast assumed.
    Future stages are shown as 'pending' (never evaluated)."""
    from .availability import player_names
    from .prospective import challenger_registry
    now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC"))
    plan = pd.DataFrame(_jsonl(SCHED / "planned.jsonl"))
    if plan.empty:
        return plan
    plan = plan.drop_duplicates("event_id", keep="last")
    ev = pd.DataFrame(_jsonl(SCHED / "events.jsonl"))
    ev = ev.drop_duplicates("event_id", keep="last").set_index("event_id") if len(ev) else pd.DataFrame()
    names = player_names()
    reg = {h["version"]: pd.Timestamp(h["registered_at"]) for h in challenger_registry()["hypotheses"]}
    rows = []
    for r in plan.itertuples(index=False):
        t = pd.Timestamp(r.time_utc)
        e = ev.loc[r.event_id] if len(ev) and r.event_id in ev.index else None
        row = {"game_id": r.game_id, "stage": r.stage, "scheduled_utc": t, "kickoff_utc": pd.Timestamp(r.kickoff_utc),
               "outcome": (e["outcome"] if e is not None else ("pending" if t > now else "not yet processed"))}
        det = (e.get("detail") if e is not None else None) or {}
        path = det.get("path") if isinstance(det, dict) else None
        if path and os.path.exists(path):
            s = json.loads(open(path, encoding="utf-8").read())
            pa = pd.Timestamp(s["predicted_at"])
            av = s.get("availability", {})
            due = [v for v, at in reg.items() if at < pa]
            ch = s.get("shadow_challengers") or {}
            row |= {"archived_at": pa, "lag_min": round((pa - t).total_seconds() / 60, 1),
                    "before_kickoff": pa < row["kickoff_utc"], "read_only": not (os.stat(path).st_mode & stat.S_IWRITE),
                    "p_home_champion": s.get("p_champion"),
                    "challengers_saved": f"{sum(isinstance(ch.get(v), dict) and ch[v].get('p_champion') is not None for v in due)}/{len(due)}",
                    "home_qb": names.get((av.get("home") or {}).get("qb_projected_id")),
                    "away_qb": names.get((av.get("away") or {}).get("qb_projected_id")),
                    "final_report_both": all((av.get(x) or {}).get("inj_report_available") == 1 for x in ("home", "away")),
                    "stale_data": s.get("stale_data")}
        rows.append(row)
    df = pd.DataFrame(rows).sort_values(["kickoff_utc", "game_id", "scheduled_utc"])
    # QB / injury-report changes between consecutive archived stages of the same game
    df["changed_since_previous_stage"] = None
    for gid, d in df[df.get("archived_at").notna()].groupby("game_id") if "archived_at" in df else []:
        prev = None
        for i, r in d.iterrows():
            if prev is not None:
                ch = [k for k in ("home_qb", "away_qb", "final_report_both") if r[k] != prev[k]]
                if r["p_home_champion"] is not None and prev["p_home_champion"] is not None:
                    ch.append(f"p {prev['p_home_champion']:.3f}->{r['p_home_champion']:.3f}")
                df.at[i, "changed_since_previous_stage"] = ", ".join(ch)
            prev = r
    return df
