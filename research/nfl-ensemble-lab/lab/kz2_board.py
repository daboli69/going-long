"""King of the End Zone board for the screen: the v2 model's probabilities for one upcoming game, a crowding estimate, the touchdown bets each pick pairs with,
and write-once hashed forecasts saved before kickoff and scored after the game.

The model is the one tested in docs/KINGZONE_PREREG.md. The only things added here are production inputs the test could not use: players listed Out or on
injured reserve are dropped from the roster, and a Kalshi anytime-touchdown quote is shown when one was archived. Nothing here is a bet recommendation and no
price is invented.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from . import gamesim as S
from . import kz2 as K

ROOT = Path(__file__).resolve().parents[1]
FITS = ROOT / "data" / "cache" / "kz2"
FROZEN = ROOT / "data" / "kingzone" / "frozen"
LEDGER = ROOT / "data" / "kingzone" / "ledger.jsonl"
SNAPS = ROOT / "data" / "cache" / "props_kalshi" / "td_snapshots.jsonl"
WALK = ROOT / "docs" / "kingzone_walkforward.json"
PROD_SIMS = 20000
OUT_STATUS = ("out", "injured reserve", "pup", "suspended", "physically unable to perform", "reserve/pup")
GAMMAS = (0.5, 1.0, 1.5)
_BOARDS: dict = {}


def latest_fit(season: int, week: int) -> tuple[dict, str]:
    """The newest fit made with history before this week: a production fit if one exists, else the tested schedule's."""
    best = None
    for f in FITS.glob(f"*_{season}_*.pkl"):
        w = int(f.stem.split("_")[-1])
        if w <= week and (best is None or (w, f.name.startswith("prod")) > best[0]):
            best = ((w, f.name.startswith("prod")), f)
    if best is None:
        raise FileNotFoundError(f"no tail fit for {season} week {week} or earlier; run scripts/kz2_freeze.py refit")
    return pickle.loads(best[1].read_bytes()), best[1].name


def kalshi_anytime(gid: str) -> dict:
    """Mid of the newest archived Kalshi anytime-touchdown quote per player for the game (name -> mid), or empty."""
    if not SNAPS.exists():
        return {}
    got: dict = {}
    for line in SNAPS.read_text(encoding="utf-8").splitlines():
        try:
            snap = json.loads(line)
        except ValueError:
            continue
        for r in snap.get("rows", []):
            if r.get("gid") == gid and r.get("bid") is not None and r.get("ask") is not None:
                got[r["player"]] = {"mid": (float(r["bid"]) + float(r["ask"])) / 2, "at": snap["t"]}
    return got


def _out_pids(gid: str) -> tuple[set, list[str]]:
    sim = S.simulate(gid, "typical", 0) or {}
    by = S._pid_by_norm()
    pids, names = set(), []
    touchers = set(K.load()["touches"]["pid"])
    for u in sim.get("unavailable") or []:
        if str(u.get("status", "")).lower() in OUT_STATUS:
            pid = by.get(S._norm(u["player"]))
            if pid:
                pids.add(pid)
                if pid in touchers:   # list only players who have carried or been targeted
                    names.append(f"{u['player']} ({u['team']})")
    return pids, names


def walk() -> dict:
    """The walk-forward test summary the screen shows beside the board (empty until the test has been run)."""
    if not WALK.exists():
        return {}
    w = json.loads(WALK.read_text(encoding="utf-8"))
    t = w.get("test_2022_2025", {})
    keep = ("games", "mean_log_model", "mean_log_b1", "mean_log_b2", "diff_vs_b1", "games_needed_80pct_power_for_0.05", "top_pick", "field", "reliability", "flagged_buckets")
    return {"verdict": w.get("verdict", {}), "test": {k: t.get(k) for k in keep}, "holdout": (w.get("holdout_2026_w1_8") or {}).get("diff_vs_b1")}


def verdict() -> dict:
    return walk().get("verdict", {})


def frozen_info(gid: str) -> dict | None:
    p = FROZEN / f"{gid}.json"
    if not p.exists():
        return None
    r = json.loads(p.read_text(encoding="utf-8"))
    return {"frozen_at": r["frozen_at"], "before_kickoff": r["before_kickoff"], "sha256": r["sha256"]}


def _reasons(r: dict, fit: dict, opp: str, team_lam: float) -> list[str]:
    out = []
    for kd, par in sorted(r["params"].items()):
        word = "carries" if kd == 0 else "targets"
        gz = float(np.mean(fit["default"]["zeta"][par["g"]]))
        gs = float(np.mean(fit["default"]["sigma"][par["g"]]))
        z = par["zeta"] / max(r["opp_f"][kd], 1e-6)
        out.append((abs(np.log(max(z / gz, 1e-3))) * (1 if z > gz else -1) * 2, f"Gains 15+ yards on {z:.0%} of {word} that start 15+ yards out (position average {gz:.0%})"))
        if par["sigma"] > 1.12 * gs:
            out.append((np.log(par["sigma"] / gs), f"When he breaks one, the gain runs longer than his position's (tail scale {par['sigma']:.1f} yards, position {gs:.1f})"))
        if par["sigma"] < 0.9 * gs:
            out.append((np.log(par["sigma"] / gs), f"Long gains run shorter than his position's (tail scale {par['sigma']:.1f} yards, position {gs:.1f})"))
        out.append((0.02 * par["share"] * 10, f"{par['share']:.0%} of his team's {word}"))
        if abs(r["opp_f"][kd] - 1) >= 0.08:
            out.append((np.log(r["opp_f"][kd]) * 2, f"{opp} has allowed 15+ yard gains {'more' if r['opp_f'][kd] > 1 else 'less'} often than the league ({r['opp_f'][kd]:.2f} times) on {word}"))
    out.append((0.0, f"His team is expected to score {team_lam:.1f} offensive touchdowns"))
    out.sort(key=lambda t: -t[0])
    return [s for _, s in out][:5]


def _crowd(rows: list[dict], gamma: float) -> np.ndarray:
    w = np.array([max(r["crowd_base"], 1e-3) ** gamma for r in rows])
    return w / w.sum()


def board(gid: str, n: int = PROD_SIMS, force: bool = False) -> dict | None:
    hit = _BOARDS.get(gid)
    if hit and not force and time.time() - hit["built_at"] < 900:
        return hit
    g = D.games_table()
    r = g[g["game_id"] == gid]
    if r.empty:
        return None
    r = r.iloc[0]
    season, week, home, away = int(r["season"]), int(r["week"]), r["home_team"], r["away_team"]
    fit, fit_name = latest_fit(season, week)
    out_pids, out_names = _out_pids(gid)
    res = K.predict(season, week, home, away, fit, n=n, seed=int(hashlib.sha256(gid.encode()).hexdigest()[:8], 16), out_pids=out_pids, extended=True)
    nm, pos = K.names(), K._positions()
    mk = kalshi_anytime(gid)
    mk_by = {S._norm(k): v for k, v in mk.items()}
    team_lam = {t["team"]: t["lam"] for t in res["teams"]}
    rows = []
    for i, x in enumerate(res["rows"][:30], 1):
        name = nm.get(x["pid"], x["pid"])
        opp = away if x["team"] == home else home
        m = mk_by.get(S._norm(name))
        rows.append({"rank": i, "pid": x["pid"], "player": name, "team": x["team"], "opp": opp, "pos": pos.get(x["pid"]), "chance": x["chance"], "anytime": x["anytime"], "two_plus": x["two_plus"],
                     "first": x["first"], "p40": x["p40"], "p60": x["p60"], "market_anytime": None if m is None else m["mid"], "market_at": None if m is None else m["at"],
                     "crowd_base": m["mid"] if m is not None else x["anytime"], "crowd_basis": "market" if m is not None else "model",
                     "given_longest": {"anytime": x["chance"] / x["anytime"] if x["anytime"] > 0 else None, "two_plus": x["win_two_plus"],
                                       "first": x["first_and_longest"] / x["first"] if x["first"] > 0 else None},
                     "why": _reasons(x, fit, opp, team_lam[x["team"]])})
    listed = sum(x["chance"] for x in rows)
    for gm in GAMMAS:
        q = _crowd(rows, gm)
        for row, qi in zip(rows, q):
            row.setdefault("pool_index_by_gamma", {})[str(gm)] = (row["chance"] / listed) / qi
    for row in rows:
        v = row["pool_index_by_gamma"]
        row["pool_index"] = v["1.0"]
        row["pool_index_range"] = [min(v.values()), max(v.values())]
        row["pair"] = {k: val for k, val in row["given_longest"].items()}
        ok = {k: val for k, val in row["pair"].items() if val is not None}
        row["pairs_best_with"] = max(ok, key=ok.get) if ok else None
        del row["crowd_base"]
    v = verdict()
    b = {"gid": gid, "away": away, "home": home, "kickoff_utc": str(r["kickoff_utc"]), "week": week, "rows": rows, "field": res["field"], "no_touchdown": res["none"], "expected_longest": res["expected_longest"],
         "teams": res["teams"], "listed_total": listed, "dropped_out": out_names, "fit": fit_name, "sims": n, "completed": bool(r["completed"]), "verdict": v, "walk": walk(),
         "built_at": time.time(),
         "model": "kz2", "code_sha256": hashlib.sha256((ROOT / "lab" / "kz2.py").read_bytes()).hexdigest()}
    _BOARDS[gid] = b
    return b


# --------------------------------------------------------------------------- frozen forecasts

def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=float)


def freeze(gid: str) -> dict:
    """Write-once pregame forecast with a SHA-256 of its content. A second call returns the stored record after checking the hash."""
    path = FROZEN / f"{gid}.json"
    if path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
        if hashlib.sha256(_canon(rec["forecast"]).encode()).hexdigest() != rec["sha256"]:
            raise RuntimeError(f"frozen forecast for {gid} no longer matches its hash")
        return rec
    b = board(gid, force=True)
    if b is None:
        raise ValueError(f"unknown game {gid}")
    now = pd.Timestamp.now(tz="UTC")
    kick = pd.Timestamp(b["kickoff_utc"])
    fc = {"gid": gid, "week": b["week"], "fit": b["fit"], "code_sha256": b["code_sha256"], "sims": b["sims"], "field": b["field"], "no_touchdown": b["no_touchdown"],
          "players": [{k: x[k] for k in ("pid", "player", "team", "chance", "anytime", "two_plus", "first", "p40", "p60", "market_anytime", "pool_index")} for x in b["rows"]]}
    fc = json.loads(_canon(fc))
    rec = {"gid": gid, "frozen_at": now.isoformat(), "kickoff_utc": kick.isoformat(), "before_kickoff": bool(now < kick), "forecast": fc, "sha256": hashlib.sha256(_canon(fc).encode()).hexdigest()}
    FROZEN.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"gid": gid, "frozen_at": rec["frozen_at"], "before_kickoff": rec["before_kickoff"], "sha256": rec["sha256"]}) + "\n")
    return rec


def score_frozen() -> list[dict]:
    """Score every frozen forecast whose game is final: the probability given to the real longest-touchdown scorer, and the rank of the top pick."""
    from . import results as Rs
    Rs.refresh_pbp()
    K._C.clear()
    out = []
    for f in sorted(FROZEN.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        if hashlib.sha256(_canon(rec["forecast"]).encode()).hexdigest() != rec["sha256"]:
            out.append({"gid": rec["gid"], "error": "hash mismatch"})
            continue
        win = K.actual_winners(rec["gid"])
        if not win:
            continue
        fc = rec["forecast"]
        p = {x["pid"]: x["chance"] for x in fc["players"]}
        pe = float(np.mean([fc["field"] if e == "FIELD" else p.get(e, fc["field"]) for e in win["entities"]]))
        top = fc["players"][0]
        out.append({"gid": rec["gid"], "before_kickoff": rec["before_kickoff"], "winner": [K.names().get(e, e) for e in win["entities"]], "length": win["length"], "p_winner": pe,
                    "log_score": float(np.log(max(pe, K.FLOOR))), "top_pick": top["player"], "top_pick_chance": top["chance"], "top_pick_won": top["pid"] in win["entities"]})
    return out
