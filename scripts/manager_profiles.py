#!/usr/bin/env python3
"""
Builds data/managers.json — how each guy in your league actually drafts.

Walks the league's previous_league_id chain back through every season Sleeper
has, pulls every draft pick, and compares each pick to that season's consensus
ADP. Output per manager:

  reach          average picks EARLIER than ADP (positive = reaches, negative = waits)
  reach_sd       how erratic they are
  discipline     share of picks within 6 slots of ADP (high = they draft off a sheet)
  pos_by_round   positional mix in rounds 1-3 / 4-8 / 9+
  early_qb       share of drafts where they took a QB in the first 5 rounds

Run it once before your draft. It does not need to be on a schedule.

  LEAGUE_ID=123456789 python scripts/manager_profiles.py
"""

import json
import os
import re
import statistics
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

LEAGUE_ID = os.environ.get("LEAGUE_ID", "").strip()
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "managers.json"
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "goinglong-etl/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize(name):
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().replace("'", "").replace(".", "").replace("-", " ")
    parts = [p for p in re.split(r"\s+", name) if p and p not in SUFFIXES]
    return re.sub(r"[^a-z0-9]", "", "".join(parts))


def adp_for_season(season, teams, cache={}):
    if season in cache:
        return cache[season]
    try:
        payload = get_json(
            f"https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams={teams}&year={season}"
        )
        table = {}
        for r in payload.get("players", []):
            k = normalize(r.get("name"))
            if k:
                table[k] = r.get("adp")
        cache[season] = table
    except Exception:
        cache[season] = {}
    return cache[season]


def league_chain(league_id, limit=8):
    chain, seen = [], set()
    while league_id and league_id not in seen and len(chain) < limit:
        seen.add(league_id)
        league = get_json(f"https://api.sleeper.app/v1/league/{league_id}")
        chain.append(league)
        league_id = league.get("previous_league_id")
        time.sleep(0.2)
    return chain


def build():
    if not LEAGUE_ID:
        print("Set LEAGUE_ID first. Find it in your Sleeper league URL.", file=sys.stderr)
        sys.exit(1)

    profiles = {}
    display = {}

    for league in league_chain(LEAGUE_ID):
        season = int(league.get("season", 0))
        teams = league.get("total_rosters") or 12
        print(f"season {season} — {league.get('name')}")

        for user in get_json(f"https://api.sleeper.app/v1/league/{league['league_id']}/users"):
            display[user["user_id"]] = user.get("display_name") or user["user_id"]

        adp = adp_for_season(season, teams)

        for draft in get_json(f"https://api.sleeper.app/v1/league/{league['league_id']}/drafts"):
            picks = get_json(f"https://api.sleeper.app/v1/draft/{draft['draft_id']}/picks")
            for pick in picks:
                uid = pick.get("picked_by")
                if not uid:
                    continue
                meta = pick.get("metadata") or {}
                pos = (meta.get("position") or "").upper()
                name = f"{meta.get('first_name','')} {meta.get('last_name','')}".strip()
                rec = profiles.setdefault(
                    uid,
                    {"picks": 0, "deltas": [], "pos_early": {}, "pos_mid": {}, "pos_late": {},
                     "qb_early_drafts": set(), "drafts": set()},
                )
                rec["picks"] += 1
                rec["drafts"].add(draft["draft_id"])

                rnd = pick.get("round") or 1
                bucket = "pos_early" if rnd <= 3 else ("pos_mid" if rnd <= 8 else "pos_late")
                if pos:
                    rec[bucket][pos] = rec[bucket].get(pos, 0) + 1
                if pos == "QB" and rnd <= 5:
                    rec["qb_early_drafts"].add(draft["draft_id"])

                player_adp = adp.get(normalize(name))
                if player_adp:
                    # positive = took him earlier than the market did
                    rec["deltas"].append(player_adp - pick["pick_no"])
            time.sleep(0.2)

    out = {}
    for uid, rec in profiles.items():
        deltas = rec["deltas"]
        n_drafts = max(len(rec["drafts"]), 1)
        out[uid] = {
            "name": display.get(uid, uid),
            "drafts": n_drafts,
            "picks": rec["picks"],
            "reach": round(statistics.mean(deltas), 2) if deltas else None,
            "reach_sd": round(statistics.pstdev(deltas), 2) if len(deltas) > 1 else None,
            "discipline": round(sum(1 for d in deltas if abs(d) <= 6) / len(deltas), 3) if deltas else None,
            "early_qb": round(len(rec["qb_early_drafts"]) / n_drafts, 2),
            "pos_by_round": {
                "1-3": rec["pos_early"],
                "4-8": rec["pos_mid"],
                "9+": rec["pos_late"],
            },
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"league_id": LEAGUE_ID, "managers": out}, indent=1))
    print(f"\nwrote {OUT} — {len(out)} managers")
    for uid, m in sorted(out.items(), key=lambda kv: -(kv[1]["reach"] or 0)):
        print(f"  {m['name']:<18} reach {str(m['reach']):>7}  discipline {m['discipline']}  drafts {m['drafts']}")


if __name__ == "__main__":
    build()
