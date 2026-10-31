"""Simulated game for the Game Center: score ranges from 10,000 draws and a play-by-play replay of one typical game.

The score ranges come from the same saved forecast the Game tab shows (market spread and total, with their spreads).
The replay is an illustration. Its final score is the median simulated score, rounded to a reachable football score, and
its player totals are built from each player's median projection. The individual plays are invented to connect those
totals and say nothing the forecast does not. Local files only, read-only, deterministic per game.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from .config import CACHE_DIR

N_SIMS = 10_000
DRIVES_PER_TEAM = 11
TEAM_STATS = CACHE_DIR / "team_game_stats.parquet"
SECONDS = {"pass": 30, "incomplete": 6, "rush": 36, "sack": 34}


def _rng(gid: str, salt: str = "") -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256((gid + salt).encode()).hexdigest()[:12], 16))


# --------------------------------------------------------------------------- score ranges

def score_ranges(gid: str, mu_m: float, sd_m: float, mu_t: float, sd_t: float) -> dict:
    r = _rng(gid, "ranges")
    m, t = r.normal(mu_m, sd_m, N_SIMS), r.normal(mu_t, sd_t, N_SIMS)
    home, away = np.clip((t + m) / 2, 0, None), np.clip((t - m) / 2, 0, None)
    def band(x):
        lo, med, hi = np.percentile(x, [10, 50, 90])
        return {"low": int(round(lo)), "median": int(round(med)), "high": int(round(hi))}
    return {"sims": N_SIMS, "home": band(home), "away": band(away), "total": band(home + away)}


def reachable_score(target: int) -> tuple[int, int]:
    """Touchdowns and field goals whose points land closest to `target` (ties go to fewer field goals)."""
    best = min(((t, f) for t in range(9) for f in range(5)), key=lambda c: (abs(7 * c[0] + 3 * c[1] - target), c[1]))
    return best


# --------------------------------------------------------------------------- team context

def team_context(season: int = D.SEASON) -> pd.DataFrame:
    """Per-game offense averages and what each defense allowed, with ranks (1 = most allowed)."""
    if not TEAM_STATS.exists():
        return pd.DataFrame()
    s = pd.read_parquet(TEAM_STATS)
    s = s[s["season"] == season]
    if s.empty:
        return pd.DataFrame()
    opp = s[["game_id", "team", "pass_yds", "rush_yds", "turnovers", "sack_rate", "dropbacks"]].rename(columns=lambda c: c if c in ("game_id",) else f"opp_{c}")
    j = s.merge(opp, on="game_id")
    j = j[j["team"] != j["opp_team"]]
    j["sacks"] = j["opp_sack_rate"] * j["opp_dropbacks"]
    g = j.groupby("team").agg(games=("game_id", "nunique"), plays=("plays", "mean"), rushes=("rushes", "mean"), dropbacks=("dropbacks", "mean"),
                              pass_yds=("pass_yds", "mean"), rush_yds=("rush_yds", "mean"), turnovers=("turnovers", "mean"),
                              pass_allowed=("opp_pass_yds", "mean"), rush_allowed=("opp_rush_yds", "mean"),
                              takeaways=("opp_turnovers", "mean"), sacks=("sacks", "mean"))
    for c in ("pass_allowed", "rush_allowed"):
        g[f"{c}_rank"] = g[c].rank(ascending=False, method="min").astype(int)
    for c in ("takeaways", "sacks"):
        g[f"{c}_rank"] = g[c].rank(ascending=False, method="min").astype(int)
    return g


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def defense_matchups(ctx: pd.DataFrame, away: str, home: str) -> list[dict]:
    out = []
    for team, opp in ((away, home), (home, away)):
        if team not in ctx.index:
            continue
        c = ctx.loc[team]
        n = len(ctx)
        out.append({"team": team, "faces": opp, "games": int(c["games"]), "rows": [
            {"label": "Passing yards allowed per game", "value": round(float(c["pass_allowed"])), "rank": f"{_ordinal(int(c['pass_allowed_rank']))} most of {n}"},
            {"label": "Rushing yards allowed per game", "value": round(float(c["rush_allowed"])), "rank": f"{_ordinal(int(c['rush_allowed_rank']))} most of {n}"},
            {"label": "Sacks per game", "value": round(float(c["sacks"]), 1), "rank": f"{_ordinal(int(c['sacks_rank']))} most of {n}"},
            {"label": "Takeaways per game", "value": round(float(c["takeaways"]), 1), "rank": f"{_ordinal(int(c['takeaways_rank']))} most of {n}"}]})
    return out


# --------------------------------------------------------------------------- the replay

def _split(total: float, n: int, r: np.random.Generator) -> list[int]:
    if n <= 0:
        return []
    w = r.gamma(1.3, 1.0, n)
    parts = np.floor(total * w / w.sum()).astype(int)
    parts[np.argmax(w)] += int(round(total)) - int(parts.sum())
    return [int(p) for p in parts]


def _pool(team: str, props: list[dict], ctx_row, r: np.random.Generator) -> tuple[list[dict], str]:
    """Every snap this team runs in the typical game, built from player median projections (team averages fill gaps)."""
    mine = [p for p in props if p["team"] == team]
    by = {}
    for p in mine:
        by.setdefault(p["player"], {})[p["stat"]] = p["typical"]
    qbs = [(n, s["Passing yards"]) for n, s in by.items() if "Passing yards" in s]
    qb, pass_yds = max(qbs, key=lambda x: x[1]) if qbs else (f"{team} quarterback", float(ctx_row["pass_yds"]) if ctx_row is not None else 210.0)
    team_rushes = float(ctx_row["rushes"]) if ctx_row is not None else 26.0
    plays: list[dict] = []

    recv = []
    for n, s in by.items():
        yds, rec = s.get("Receiving yards"), s.get("Receptions")
        if yds is None and rec is None:
            continue
        yds = yds if yds is not None else rec * 9.5
        rec = rec if rec is not None else yds / 11
        recv.append((n, max(1, int(round(rec))), yds))
    rest = pass_yds - sum(y for _, _, y in recv)
    if rest > 12:
        recv.append((f"another {team} receiver", max(1, int(round(rest / 10))), rest))
    elif rest < 0 and recv:
        scale = pass_yds / sum(y for _, _, y in recv)
        recv = [(n, c, y * scale) for n, c, y in recv]
    catches = 0
    for n, c, y in recv:
        catches += c
        plays += [{"kind": "pass", "player": n, "yards": v} for v in _split(y, c, r)]
    plays += [{"kind": "incomplete", "player": None, "yards": 0} for _ in range(int(round(catches * 0.52)))]
    plays += [{"kind": "sack", "player": None, "yards": -int(r.integers(4, 9))} for _ in range(2)]

    carries, named_yds = 0, 0.0
    for n, s in by.items():
        yds = s.get("Rushing yards")
        if yds is None or n == qb:
            continue
        c = max(1, int(round(yds / 4.3)))
        carries, named_yds = carries + c, named_yds + yds
        plays += [{"kind": "rush", "player": n, "yards": v} for v in _split(yds, c, r)]
    # Carries the named backs don't account for get the team's usual remaining rushing yards (at least 3 a carry).
    extra = max(0, int(round(team_rushes)) - carries)
    team_rush = float(ctx_row["rush_yds"]) if ctx_row is not None else 110.0
    who = f"{team} running back" if carries == 0 else f"another {team} runner"
    plays += [{"kind": "rush", "player": who, "yards": v} for v in _split(max(team_rush - named_yds, 3.0 * extra), extra, r)]
    for p in plays:
        p["passer"] = qb if p["kind"] != "rush" else None
    # Named players' snaps come first, so the snaps a short game leaves unused are the generic ones.
    shuffled = [plays[i] for i in r.permutation(len(plays))]
    generic = lambda p: p["kind"] in ("rush", "pass") and str(p["player"]).startswith(("another ", f"{team} "))
    return sorted(shuffled, key=generic), qb


def _outcomes(n_td: int, n_fg: int, turnovers: int, r: np.random.Generator) -> list[str]:
    k = min(turnovers, max(0, DRIVES_PER_TEAM - n_td - n_fg))
    out = ["TD"] * n_td + ["FG"] * n_fg + ["TO"] * k
    out += ["PUNT"] * (DRIVES_PER_TEAM - len(out))
    return [out[i] for i in r.permutation(len(out))]


def _caption(p: dict, team: str) -> str:
    if p["kind"] == "pass":
        return f"{p['passer']} completes to {p['player']} for {p['yards']} yard{'s' if abs(p['yards']) != 1 else ''}."
    if p["kind"] == "incomplete":
        return f"{p['passer']} pass incomplete."
    if p["kind"] == "sack":
        return f"{p['passer']} sacked for a loss of {-p['yards']}."
    return f"{p['player']} rushes for {p['yards']} yard{'s' if abs(p['yards']) != 1 else ''}."


def replay(gid: str, away: str, home: str, targets: dict, props: list[dict], ctx: pd.DataFrame) -> dict:
    r = _rng(gid, "replay")
    teams = {}
    for t in (away, home):
        td, fg = reachable_score(targets[t])
        row = ctx.loc[t] if t in ctx.index else None
        to = int(round(float(row["turnovers"]))) if row is not None else 1
        pool, qb = _pool(t, props, row, r)
        teams[t] = {"pool": pool, "qb": qb, "outcomes": _outcomes(td, fg, to, r)}

    score = {away: 0, home: 0}
    plays: list[dict] = []
    start = 30  # own 30 after a kickoff
    for i in range(2 * DRIVES_PER_TEAM):
        off = away if i % 2 == 0 else home
        de = home if off == away else away
        if i == DRIVES_PER_TEAM:  # second half: kickoff to the home team
            start = 30
        T = teams[off]
        goal = T["outcomes"][i // 2]
        pool = T["pool"]
        pos, down, togo, n = start, 1, 10, 0
        drive: list[dict] = []
        ended = None

        def take(kind_filter=None, small=False, big=False):
            cands = [j for j, p in enumerate(pool) if kind_filter is None or p["kind"] in kind_filter]
            if not cands:
                kind = "rush"
                return {"kind": kind, "player": f"another {off} runner", "yards": int(r.integers(2, 7)), "passer": None}
            if small:
                j = min(cands, key=lambda j: pool[j]["yards"])
            elif big:
                j = max(cands, key=lambda j: pool[j]["yards"])
            else:
                j = cands[0]
            return pool.pop(j)

        while ended is None:
            n += 1
            if goal == "PUNT":
                p = take(small=n > 1 or pos > 45)
                p["yards"] = min(p["yards"], max(0, 60 - pos))
            elif goal == "TO" and n >= int(r.integers(1, 5)):
                p = take({"pass", "incomplete"} if r.random() < 0.6 else {"rush"})
                p = dict(p, yards=min(max(p["yards"], 0), 99 - pos))
                ended = "INT" if p["kind"] != "rush" else "FUMBLE"
            elif goal in ("TD", "FG") and (down >= 3 or n > 10):
                p = take({"pass", "rush"}, big=True)
                p["yards"] = max(p["yards"], togo)
            elif goal == "TO":
                p = take()
                p["yards"] = min(p["yards"], max(0, 75 - pos))
            else:
                p = take()
            if goal == "FG":
                p["yards"] = min(p["yards"], 92 - pos)
            if pos + p["yards"] >= 100:
                p["yards"] = 100 - pos
            p = dict(p, team=off, down=down, togo=togo, start=pos)
            pos = max(1, pos + p["yards"])
            p["end"] = pos
            p["text"] = _caption(p, off)
            if ended in ("INT", "FUMBLE"):
                p["text"] = (f"{p['passer']} pass intercepted by {de}." if ended == "INT" else f"{p['player']} fumbles; {de} recovers.")
                if p["kind"] != "rush":
                    p["kind"], p["player"], p["yards"], p["end"] = "incomplete", None, 0, p["start"]
                    pos = p["start"]
                p["event"] = ended
            elif pos >= 100:
                score[off] += 7
                p["event"], ended = "TD", "TD"
                p["text"] += " TOUCHDOWN. Extra point good."
            p["score"] = dict(score)
            drive.append(p)
            if ended:
                break
            gained = pos - p["start"]
            if gained >= togo:
                down, togo = 1, min(10, 100 - pos)
            else:
                down, togo = down + 1, togo - gained
            if goal == "FG" and pos >= 65 and (down >= 3 or n >= 6):
                dist = 100 - pos + 17
                score[off] += 3
                drive.append({"score": dict(score), "team": off, "kind": "fg", "player": None, "passer": None, "yards": 0, "down": 4 if down >= 4 else down, "togo": togo,
                              "start": pos, "end": 100, "event": "FG", "text": f"Field goal good from {dist} yards."})
                ended = "FG"
            elif goal == "PUNT" and down == 4:
                land = min(pos + 44, 90)
                drive.append({"score": dict(score), "team": off, "kind": "punt", "player": None, "passer": None, "yards": 0, "down": 4, "togo": togo, "start": pos,
                              "end": land, "event": "PUNT", "text": f"{off} punts. {de} takes over at their own {max(100 - land, 10)}."})
                ended = "PUNT"
            elif down > 4:
                ended = "DOWNS"
                drive[-1]["event"] = "DOWNS"
                drive[-1]["text"] += f" Turnover on downs."
        plays += drive
        if ended in ("TD", "FG"):
            start = 30
        elif ended == "PUNT":
            start = max(100 - drive[-1]["end"], 10)
        else:
            start = max(min(100 - drive[-1]["end"], 95), 5)

    _clock(plays)
    return {"plays": [_public(p, away) for p in plays], "final": score, "qbs": {t: teams[t]["qb"] for t in (away, home)},
            "targets": targets}


def _clock(plays: list[dict]) -> None:
    """Spread each half's plays over 30 minutes in proportion to how long each kind of snap takes."""
    half = DRIVES_PER_TEAM
    idx = [0]
    drives = 0
    for i in range(1, len(plays)):
        if plays[i]["team"] != plays[i - 1]["team"]:
            drives += 1
            if drives == half:
                idx.append(i)
    idx.append(len(plays))
    for h, (a, b) in enumerate(zip(idx[:-1], idx[1:])):
        secs = np.array([SECONDS.get(p["kind"], 8) for p in plays[a:b]], dtype=float)
        if not len(secs):
            continue
        ends = 1800 * np.cumsum(secs) / secs.sum()
        begins = np.concatenate([[0.0], ends[:-1]])
        for p, t0 in zip(plays[a:b], begins):
            el = h * 1800 + t0
            q = int(el // 900) + 1
            left = 900 - (el - (q - 1) * 900)
            p["qtr"], p["clock"] = q, f"{int(left // 60):02d}:{int(left % 60):02d}"


def _public(p: dict, away: str) -> dict:
    """Field x runs 0 (away team's goal line, left) to 100 (home goal line, right)."""
    flip = p["team"] != away
    fx = (lambda y: 100 - y) if flip else (lambda y: y)
    to_go = p["start"] + p["togo"]
    return {"team": p["team"], "kind": p["kind"], "player": p["player"], "passer": p["passer"], "yards": p["yards"], "qtr": p["qtr"], "clock": p["clock"],
            "down": p["down"], "togo": p["togo"], "x_start": fx(p["start"]), "x_end": fx(min(p["end"], 100)), "x_first": fx(min(to_go, 100)),
            "spot": _spot(p["start"], p["team"]), "event": p.get("event"), "text": p["text"], "score": p["score"]}


def _spot(pos: int, team: str) -> str:
    if pos == 50:
        return "50"
    return f"own {pos}" if pos < 50 else f"opp {100 - pos}"


# --------------------------------------------------------------------------- public API

def simulate(gid: str) -> dict | None:
    d = D.game_detail(gid)
    if d is None:
        return None
    away, home = d["away"], d["home"]
    out = {"gid": gid, "away": away, "home": home, "ok": False}
    e = d.get("expected") or {}
    if e.get("margin") is None or e.get("total") is None:
        out["reason"] = "No saved spread and total for this game yet, so it cannot be simulated."
        return out
    rng = score_ranges(gid, e["margin"], e["sd_m"], e["total"], e["sd_t"])
    ctx = team_context()
    props = d.get("props") or []
    out_now = {r["player"] for rows in (d.get("injuries") or {}).get("teams", {}).values() for r in rows if r["status"].startswith("Out")}
    props = [p for p in props if p["player"] not in out_now]
    targets = {away: rng["away"]["median"], home: rng["home"]["median"]}
    out.update({"ok": True, "ranges": rng, "replay": replay(gid, away, home, targets, props, ctx),
                "defense": defense_matchups(ctx, away, home) if not ctx.empty else [],
                "source": {"margin": e.get("margin_label"), "total": e.get("total_label")}, "has_players": bool(props),
                "left_out": sorted(out_now & {p["player"] for p in d.get("props") or []})})
    return D.clean(out)
