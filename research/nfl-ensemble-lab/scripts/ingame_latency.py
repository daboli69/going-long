"""How far behind is the ESPN feed? For every play, the gap between ESPN's own timestamp for it and the first stored snapshot that contained it.

    .venv\Scripts\python.exe scripts\ingame_latency.py

ESPN stamps each play with `wallclock` (UTC, whole seconds). Our snapshots carry the time we fetched them. The gap includes the polling interval, so plays are
also reported separately when the previous snapshot of the game was at most 30 seconds earlier (dense polling), where the gap is mostly ESPN's own delay.
The gap is measured against ESPN's timestamp, not the broadcast; ESPN's `wallclock` is the play's own time and its relation to the television picture is not
known here. Writes docs/ingame_latency.json. Reads local files only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import ingame_feed as F  # noqa: E402


def stamp_time(stamp: str) -> pd.Timestamp:
    return pd.Timestamp(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}Z")


def plays_of(raw: dict):
    drv = raw.get("drives") or {}
    for d in (drv.get("previous") or []) + ([drv["current"]] if drv.get("current") else []):
        for p in d.get("plays") or []:
            if p.get("id") and p.get("wallclock"):
                yield p["id"], pd.Timestamp(p["wallclock"])


def summarize(x: np.ndarray) -> dict:
    if not len(x):
        return {"n": 0}
    q = np.percentile(x, [10, 50, 90])
    return {"n": int(len(x)), "p10": round(float(q[0]), 1), "median": round(float(q[1]), 1), "p90": round(float(q[2]), 1), "max": round(float(x.max()), 1)}


def main():
    all_lag, dense_lag = [], []
    per_game = {}
    for d in sorted(p for p in F.CAPTURE.iterdir() if p.is_dir()):
        seen, prev_t, first = {}, None, True
        g_all, g_dense = [], []
        for stamp, path in F.snapshots(d.name):
            t = stamp_time(stamp)
            gap = None if prev_t is None else (t - prev_t).total_seconds()
            prev_t = t
            was_first, first = first, False
            first_flag = was_first
            for pid, wc in plays_of(F.load(path)):
                if pid in seen:
                    continue
                seen[pid] = 1
                if first_flag:                     # plays already in the game when recording began are backlog, not delay
                    continue
                lag = (t - wc).total_seconds()
                if lag < -5 or lag > 3600:       # a clock problem or a replayed history, not a delay
                    continue
                g_all.append(lag)
                if gap is not None and gap <= 30:
                    g_dense.append(lag)
        per_game[d.name] = {"all": summarize(np.array(g_all)), "dense_polling": summarize(np.array(g_dense))}
        all_lag += g_all
        dense_lag += g_dense
    out = {"all_snapshots": summarize(np.array(all_lag)), "dense_polling_only": summarize(np.array(dense_lag)), "games": per_game,
           "note": "seconds from ESPN's own play timestamp to first appearance in our snapshots; includes polling interval unless dense_polling_only"}
    (ROOT / "docs" / "ingame_latency.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("all_snapshots", "dense_polling_only")}, indent=1))


if __name__ == "__main__":
    main()
