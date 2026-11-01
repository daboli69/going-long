"""Save raw in-game data for every NFL game that is live: read-only public ESPN and Kalshi data, $0, no orders and no account calls.

    .venv\\Scripts\\python.exe scripts\\ingame_capture.py [--interval 120] [--max-hours 8]

Every poll writes one gzip of the raw ESPN `summary` JSON per game (box score, every drive and play, win probability, odds) to
data/raw/ingame/<event id>/<UTC stamp>.json.gz, and one line to data/raw/ingame/index.jsonl (stamp, event, status, clock, score, sha256 of the raw
bytes, and the open Kalshi team-market prices). Files are never overwritten. A poll whose summary is byte-identical to the previous one
is logged in the index but not stored again. The loop ends when no game is live or about to start.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "raw" / "ingame"
BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def kalshi_prices() -> dict:
    """Open KXNFLGAME team markets as {ticker: [team, yes_bid, yes_ask, last]}; an error name when Kalshi cannot be reached."""
    try:
        from lab import kalshi as K
        m = K.game_markets("open")
        return {r.ticker: [r.team, r.yes_bid, r.yes_ask, r.last] for r in m.itertuples()} if m is not None and len(m) else {}
    except Exception as exc:  # public market data being down must not stop the capture
        return {"error": type(exc).__name__}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=120)
    ap.add_argument("--max-hours", type=float, default=8.0)
    ap.add_argument("--no-kalshi", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    last: dict[str, str] = {}
    end = time.time() + a.max_hours * 3600
    quiet = 0
    while time.time() < end:
        try:
            sb = requests.get(BASE + "/scoreboard", timeout=30).json()
        except Exception as exc:
            print(stamp(), "scoreboard failed", type(exc).__name__, flush=True)
            time.sleep(a.interval)
            continue
        live = 0
        soon = 0
        k = None if a.no_kalshi else kalshi_prices()
        for ev in sb.get("events", []):
            st = ev["status"]["type"]["state"]
            eid = ev["id"]
            if st == "pre":
                kick = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
                if (kick - datetime.now(timezone.utc)).total_seconds() < 1800:
                    soon += 1
                else:
                    continue
            elif st == "in":
                live += 1
            else:
                if eid in last and last[eid] != "post":  # one last pull so the final state is on file
                    pass
                else:
                    continue
            try:
                raw = requests.get(BASE + "/summary", params={"event": eid}, timeout=30).content
            except Exception as exc:
                print(stamp(), eid, "summary failed", type(exc).__name__, flush=True)
                continue
            sha = hashlib.sha256(raw).hexdigest()
            s = stamp()
            comp = ev["competitions"][0]["competitors"]
            row = {"stamp": s, "event": eid, "name": ev["shortName"], "state": st, "period": ev["status"]["period"], "clock": ev["status"]["displayClock"],
                   "scores": {c["homeAway"]: c["score"] for c in comp}, "teams": {c["homeAway"]: c["team"]["abbreviation"] for c in comp}, "sha256": sha,
                   "stored": sha != last.get(eid + ":sha")}
            if k:
                row["kalshi"] = k
            if row["stored"]:
                d = OUT / eid
                d.mkdir(exist_ok=True)
                p = d / f"{s}.json.gz"
                if not p.exists():
                    with gzip.open(p, "wb") as f:
                        f.write(raw)
                last[eid + ":sha"] = sha
            last[eid] = st
            with open(OUT / "index.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            if st == "post":
                last[eid] = "post"
        print(stamp(), f"live={live} soon={soon}", flush=True)
        if live == 0 and soon == 0:
            quiet += 1
            if quiet >= 3:
                break
        else:
            quiet = 0
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
