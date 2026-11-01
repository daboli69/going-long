"""Replay captured games as if live, then check them against the record that exists outside this tool.

    .venv\\Scripts\\python.exe scripts\\ingame_replay.py [--event 401873030 ...] [--final-check] [--freeze]

Per captured game: parse every stored ESPN snapshot in time order, update the tracked players and the win chance, and write the timeline to
data/cache/ingame_replay_<event>.jsonl. Frozen pregame projections come from ingame/frozen/<gid>.json (written once by --freeze; a game frozen after kickoff is
marked and left out of the pregame-versus-live scores).
--final-check compares the last stored box score with the nflverse play-by-play for the same game, player by player (targets, carries, attempts, yards).
Scoring of the live win chance uses the final score; ESPN's own win probability and the Kalshi mid price are shown beside it when the capture has them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import gamecenter_data as D  # noqa: E402
from lab import gamesim as S  # noqa: E402
from lab import ingame as G  # noqa: E402
from lab import ingame_feed as F  # noqa: E402


_GT = []


def lab_gid(snap) -> str:
    if not _GT:
        _GT.append(D.games_table())
    g = _GT[0]
    m = g[(g["season"] == D.SEASON) & (g["home_team"] == snap["home"]) & (g["away_team"] == snap["away"]) & (g["game_type"] == "REG")]
    return m["game_id"].iloc[0] if len(m) else f"{snap['away']}_{snap['home']}"


def kalshi_home(index_row, home: str, away: str):
    """Home win probability from the Kalshi team markets stored with a poll: mid of each side, normalised."""
    k = (index_row or {}).get("kalshi") or {}
    mid = {}
    for tkr, v in k.items():
        if not isinstance(v, list) or len(v) < 4:
            continue
        team, bid, ask, last = v
        if team in (home, away) and f"{away}{home}" in tkr.replace("-", ""):
            m = (bid + ask) / 2 if bid and ask else last
            if m is not None:
                mid[team] = float(m)
    if home in mid and away in mid and mid[home] + mid[away] > 0:
        return mid[home] / (mid[home] + mid[away])
    return None


def index_rows(eid):
    p = F.CAPTURE / "index.jsonl"
    rows = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["event"] == eid:
                rows[r["stamp"]] = r
    return rows


def replay(eid: str, ctx, every: int = 1):
    snaps = F.snapshots(eid)
    idx = index_rows(eid)
    out, first = [], None
    for n, (stamp, path) in enumerate(snaps):
        raw = F.load(path)
        snap = F.parse(raw)
        if first is None:
            first = snap
        gid = lab_gid(snap)
        try:
            fr = F.freeze(gid) if (F.FROZEN / f"{gid}.json").exists() else None
        except Exception:
            fr = None
        pre_margin = float(fr["projection"]["expected"]["margin"]) if fr and fr["projection"].get("expected") and fr["projection"]["expected"].get("margin") is not None else None
        wp = F.win_probability(snap, pre_margin, ctx["params"]) if pre_margin is not None else None
        espn = (raw.get("winprobability") or [{}])[-1].get("homeWinPercentage")
        rec = {"stamp": stamp, "event": eid, "gid": gid, "elapsed": snap["elapsed"], "state": snap["state"], "score": snap["score"], "possession": snap["possession"],
               "p_home_updated": None if wp is None else wp["p_home"], "p_home_frozen_margin": pre_margin, "p_home_espn": espn,
               "p_home_kalshi": kalshi_home(idx.get(stamp), snap["home"], snap["away"]), "frozen_before_kickoff": None if fr is None else fr["before_kickoff"]}
        if n % every == 0 and snap["elapsed"] is not None:
            rows = F.tracked_states(snap, ctx)
            rec["warnings"] = [{k: r[k] for k in ("team", "name", "stat", "kind", "share_pre", "share_post", "team_attempts", "targets_or_carries")} for r in F.warnings(rows)]
            rec["players"] = [{k: (round(float(r[k]), 2) if isinstance(r[k], (float, np.floating)) else r[k]) for k in
                               ("team", "name", "stat", "yards", "frozen", "updated", "low", "high", "share_pre", "share_post")} for r in rows if r["seen"]]
        out.append(rec)
    return out, (F.parse(F.load(snaps[-1][1])) if snaps else None)


def brier(p, y):
    return (p - y) ** 2


def final_check(snap) -> list[dict]:
    """Last box score against nflverse play-by-play for the same game. Returns the mismatches (empty means every compared number matches)."""
    gid = f"2026_{{week:02d}}_{snap['away']}_{snap['home']}"
    plays = pd.read_parquet(F.ROOT / "data" / "raw" / "play_by_play_2026.parquet", columns=G.PBP_COLS + ["fumble_lost"])
    g = plays[(plays["home_team"] == snap["home"]) & (plays["away_team"] == snap["away"])]
    if g.empty:
        return [{"problem": "game not in nflverse play-by-play yet"}]
    ev = G.events(g)
    names = pd.read_parquet(F.ROOT / "data" / "raw" / "players.parquet")
    pidcol = "gsis_id" if "gsis_id" in names.columns else names.columns[0]
    by_norm = S._pid_by_norm()
    bad = []
    for fam, col_o, col_y in (("rec", "targets", "rec_yds"), ("rush", "rush_att", "rush_yds"), ("pass", "pass_att", "pass_yds")):
        rows = G._fam_rows(ev, fam)
        tot = rows.groupby(["team", "pid"]).agg(O=("t", "size"), Y=("yards", "sum")).reset_index()
        for (team, name), pl in snap["players"].items():
            if pl.get(col_o) is None:
                continue
            pid = by_norm.get(S._norm(name))
            m = tot[(tot["team"] == team) & (tot["pid"] == pid)] if pid else tot.iloc[0:0]
            o, y = (int(m["O"].iloc[0]), float(m["Y"].iloc[0])) if len(m) else (0, 0.0)
            if pid is None:
                bad.append({"player": name, "team": team, "stat": fam, "problem": "no player id for this name"})
            elif abs(o - pl[col_o]) > 0 or abs(y - (pl.get(col_y) or 0.0)) > 0:
                bad.append({"player": name, "team": team, "stat": fam, "box": [pl[col_o], pl.get(col_y)], "pbp": [o, y]})
    return bad


STAT_KEY = {"Receiving yards": "rec_yds", "Rushing yards": "rush_yds", "Passing yards": "pass_yds"}


def feed_consistency(raw: dict, snap: dict) -> list[dict]:
    """Not an outside check (same feed): do the play list and the box score agree on each team's pass attempts and rushes?"""
    drv = raw.get("drives") or {}
    plays = [p for d in (drv.get("previous") or []) + ([drv["current"]] if drv.get("current") else []) for p in d.get("plays") or []]
    team_by_id = {c["team"]["id"]: F.normalize_team(c["team"]["abbreviation"]) for c in raw["header"]["competitions"][0]["competitors"]}
    cnt = {t: {"pass": 0, "rush": 0} for t in team_by_id.values()}
    for p in plays:
        ty = (p.get("type") or {}).get("text", "")
        tid = ((p.get("start") or {}).get("team") or {}).get("id")
        t = team_by_id.get(tid)
        if t is None or p.get("isPenalty") or "Penalty" in ty:
            continue
        txt = p.get("text", "")
        if ty in ("Pass Reception", "Pass Incompletion", "Passing Touchdown", "Pass Interception Return", "Interception Return Touchdown") or (ty.startswith("Pass") and "sacked" not in txt):
            cnt[t]["pass"] += 1
        elif ty in ("Rush", "Rushing Touchdown") and "kneel" not in txt.lower():
            cnt[t]["rush"] += 1
    return [{"team": t, "box": snap["team_attempts"].get(t), "plays": c} for t, c in cnt.items() if snap["team_attempts"].get(t) != c]


def score_props(gid: str, tl: list[dict], last: dict) -> dict:
    """The app's frozen projection against the finished box score, and the same projection shifted by the live update at 30 and 40 minutes."""
    fr = json.loads((F.FROZEN / f"{gid}.json").read_text(encoding="utf-8"))["projection"]["props"]
    final = {(S._norm(n), t): v for (t, n), v in last["players"].items()}
    out = {}
    for el in (1800, 2400):
        snapx = min((r for r in tl if r.get("players") and r["elapsed"] is not None and r["elapsed"] <= el), key=lambda r: abs(r["elapsed"] - el), default=None)
        if snapx is None:
            continue
        upd = {(S._norm(p["name"]), p["team"], p["stat"]): p for p in snapx["players"]}
        rows = []
        for r in fr:
            key = STAT_KEY.get(r["stat"])
            f = final.get((S._norm(r["player"]), r["team"]))
            m = upd.get((S._norm(r["player"]), r["team"], r["stat"]))
            if key is None or f is None or m is None or f.get(key) is None or not r.get("typical") or not m["frozen"]:
                continue
            app = float(r["typical"])
            rows.append((abs(app - f[key]), abs(app * m["updated"] / m["frozen"] - f[key]), abs(m["updated"] - f[key])))
        if rows:
            a = np.array(rows)
            out[f"{el // 60}min"] = {"n": len(a), "mae_app_frozen": round(float(a[:, 0].mean()), 2), "mae_app_shifted_by_update": round(float(a[:, 1].mean()), 2), "mae_model_updated": round(float(a[:, 2].mean()), 2)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", nargs="*")
    ap.add_argument("--final-check", action="store_true")
    ap.add_argument("--freeze", action="store_true", help="freeze pregame projections for every game on the current week's slate that has none")
    ap.add_argument("--every", type=int, default=3)
    a = ap.parse_args()
    if a.freeze:
        G_ = D.games_table()
        wk = S.current_week()
        g = G_[(G_["season"] == D.SEASON) & (G_["week"] == wk) & (G_["game_type"] == "REG")]
        for r in g.itertuples():
            gid = r.game_id
            try:
                rec = F.freeze(gid)
                print(gid, "frozen", rec["sha256"][:12], "before kickoff" if rec["before_kickoff"] else "AFTER kickoff")
            except Exception as exc:
                print(gid, "not frozen:", type(exc).__name__, exc)
    events = a.event or sorted(p.name for p in F.CAPTURE.iterdir() if p.is_dir())
    if not events:
        return
    ctx = F.live_context()
    report = {}
    for eid in events:
        tl, last = replay(eid, ctx, a.every)
        if not tl:
            continue
        (ROOT / "data" / "cache" / f"ingame_replay_{eid}.jsonl").write_text("\n".join(json.dumps(r, default=float) for r in tl), encoding="utf-8")
        done = last["completed"] or last["state"] == "post"
        row = {"gid": tl[-1]["gid"], "snapshots": len(tl), "final": last["score"], "completed": done}
        if done:
            res = 1.0 if last["score"]["home"] > last["score"]["away"] else 0.0 if last["score"]["home"] < last["score"]["away"] else 0.5
            sc = {}
            for k in ("p_home_updated", "p_home_espn", "p_home_kalshi"):
                v = [(r[k] / (100.0 if k == "p_home_espn" and r[k] and r[k] > 1 else 1.0), r["elapsed"]) for r in tl if r.get(k) is not None and r["elapsed"] is not None and r["elapsed"] <= G.GAME]
                sc[k] = {"n": len(v), "brier": round(float(np.mean([brier(p, res) for p, _ in v])), 4)} if v else {"n": 0}
            row["win_chance_brier"] = sc
            row["frozen_before_kickoff"] = tl[0].get("frozen_before_kickoff")
            if a.final_check:
                row["final_check"] = final_check(last)
            row["feed_consistency_mismatches"] = feed_consistency(F.load(F.snapshots(eid)[-1][1]), last)
            try:
                row["prop_scores"] = score_props(tl[-1]["gid"], tl, last)
            except FileNotFoundError:
                row["prop_scores"] = "no frozen projection"
        report[eid] = row
        print(eid, json.dumps(row, default=float))
    (ROOT / "docs" / "ingame_replay.json").write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
