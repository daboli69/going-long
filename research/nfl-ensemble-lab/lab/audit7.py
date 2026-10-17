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
    (ARTIFACTS_DIR / "phase7").mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "phase7" / "weekend_audit.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def load() -> dict:
    p = ARTIFACTS_DIR / "phase7" / "weekend_audit.json"
    return json.loads(p.read_text()) if p.exists() else {}
