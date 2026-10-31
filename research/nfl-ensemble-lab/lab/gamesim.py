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
from . import gameweather
from . import fpds_usage as X
from . import usage as U
from .config import CACHE_DIR, RAW_DIR
from .ingest import normalize_team

N_SIMS = 10_000
DRIVES_PER_TEAM = 11
TEAM_STATS = CACHE_DIR / "team_game_stats.parquet"
SECONDS = {"pass": 30, "incomplete": 6, "rush": 36, "sack": 34}
NOT_PLAYING = {"Out", "Doubtful", "Injured Reserve", "Suspension", "Physically Unable to Perform"}
LONG_TERM = {"Injured Reserve", "Suspension", "Physically Unable to Perform"}
HOME_EDGE = 1.5  # points of margin for the home team when no betting line exists yet


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

def team_context(season: int = D.SEASON, before_week: int = 99) -> pd.DataFrame:
    """Per-game offense averages and what each defense allowed before `before_week`, with ranks (1 = most allowed)."""
    if not TEAM_STATS.exists():
        return pd.DataFrame()
    s = pd.read_parquet(TEAM_STATS)
    s = s[(s["season"] == season) & (s["game_id"].str[5:7].astype(int) < before_week)]
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


def _pool(team: str, props: list[dict], ctx_row, r: np.random.Generator) -> tuple[list[dict], str, str]:
    """Every snap this team runs in the typical game, built from each named player's projection."""
    mine = [p for p in props if p["team"] == team]
    by, carries_of = {}, {}
    for p in mine:
        by.setdefault(p["player"], {})[p["stat"]] = p["typical"]
        if p.get("carries"):
            carries_of[p["player"]] = p["carries"]
    qbs = [(n, s["Passing yards"]) for n, s in by.items() if "Passing yards" in s]
    qb, pass_yds = max(qbs, key=lambda x: x[1]) if qbs else (f"{team} quarterback", float(ctx_row["pass_yds"]) if ctx_row is not None else 210.0)
    team_rushes = float(ctx_row["rushes"]) if ctx_row is not None else 26.0
    plays: list[dict] = []

    # Catches: every receiver is a named player. Their yards are scaled so they add up to the quarterback's passing yards.
    recv = []
    for n, s in by.items():
        yds, rec = s.get("Receiving yards"), s.get("Receptions")
        if yds is None and rec is None:
            continue
        yds = yds if yds is not None else rec * 9.5
        rec = rec if rec is not None else yds / 11
        recv.append([n, rec, yds])
    total = sum(y for _, _, y in recv)
    if total > 0:
        for x in recv:
            x[2] *= pass_yds / total
    catches = 0
    for n, rec, y in recv:
        c = int(round(rec))
        if c == 0 and y >= 6:
            c = 1
        catches += c
        plays += [{"kind": "pass", "player": n, "yards": v} for v in _split(y, c, r)]
    plays += [{"kind": "incomplete", "player": None, "yards": 0} for _ in range(int(round(catches * 0.52)))]
    plays += [{"kind": "sack", "player": None, "yards": -int(r.integers(4, 9))} for _ in range(2)]

    # Carries: every runner is a named player, quarterback runs included; carries come from each player's projection.
    rushers = []
    for n, s in by.items():
        yds = s.get("Rushing yards")
        if yds is None:
            continue
        car = carries_of.get(n) or yds / 4.3
        c = int(round(car))
        if c == 0 and yds >= 3:
            c = 1
        if c:
            rushers.append((n, yds))
            plays += [{"kind": "rush", "player": n, "yards": v} for v in _split(yds, c, r)]
    if not rushers:  # no player data at all for this team
        yds = float(ctx_row["rush_yds"]) if ctx_row is not None else 110.0
        plays += [{"kind": "rush", "player": f"{team} running back", "yards": v} for v in _split(yds, int(round(team_rushes)), r)]
    for p in plays:
        p["passer"] = qb if p["kind"] != "rush" else None
    lead = max(rushers, key=lambda x: x[1])[0] if rushers else f"{team} running back"
    return [plays[i] for i in r.permutation(len(plays))], qb, lead


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


def replay(gid: str, away: str, home: str, targets: dict, props: list[dict], ctx: pd.DataFrame, td_weights: dict | None = None) -> dict:
    r = _rng(gid, "replay")
    teams = {}
    for t in (away, home):
        td, fg = reachable_score(targets[t])
        row = ctx.loc[t] if t in ctx.index else None
        to = int(round(float(row["turnovers"]))) if row is not None else 1
        pool, qb, lead = _pool(t, props, row, r)
        rotation = [p["player"] for p in pool if p["kind"] == "rush"] or [lead]
        teams[t] = {"pool": pool, "qb": qb, "rotation": rotation, "outcomes": _outcomes(td, fg, to, r)}

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
            if not cands:  # the pool is used up: an incompletion or a short run by someone in the rotation
                if (kind_filter is None or "incomplete" in kind_filter) and r.random() < 0.5:
                    return {"kind": "incomplete", "player": None, "yards": 0, "passer": T["qb"]}
                return {"kind": "rush", "player": T["rotation"][int(r.integers(len(T["rotation"])))], "yards": int(r.integers(0, 4)), "passer": None}
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

    swaps = _assign_scorers(plays, td_weights or {}, r)
    _clock(plays)
    return {"plays": [_public(p, away) for p in plays], "final": score, "qbs": {t: teams[t]["qb"] for t in (away, home)},
            "targets": targets}


def _assign_scorers(plays: list[dict], td_weights: dict, r: np.random.Generator) -> int:
    """Choose who catches each touchdown by the tested weights (yardage share, touchdown history, red-zone targets).

    The chosen player swaps catches with the scorer when he has a catch within four yards, so each player's total changes by at
    most four yards; with no such catch the play is left as it was."""
    swaps = 0
    for p in plays:
        if p.get("event") != "TD" or p["kind"] != "pass":
            continue
        w = td_weights.get(p["team"]) or {}
        names = [n for n in w if any(q["kind"] == "pass" and q["team"] == p["team"] and q["player"] == n for q in plays)]
        if not names:
            continue
        pr = np.clip(np.array([w[n] for n in names], float), 0, None)
        if pr.sum() <= 0:
            continue
        pick = names[int(r.choice(len(names), p=pr / pr.sum()))]
        if pick == p["player"]:
            continue
        cands = [q for q in plays if q is not p and q["kind"] == "pass" and q["team"] == p["team"] and q["player"] == pick
                 and q.get("event") is None and abs(q["yards"] - p["yards"]) <= 4]
        if not cands:
            continue
        q = min(cands, key=lambda c: abs(c["yards"] - p["yards"]))
        p["player"], q["player"] = pick, p["player"]
        for x in (p, q):
            x["text"] = _caption(x, x["team"]) + (" TOUCHDOWN. Extra point good." if x.get("event") == "TD" else "")
        swaps += 1
    return swaps


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

# --------------------------------------------------------------------------- inputs for weeks without saved numbers

def _norm(name: str) -> str:
    parts = "".join(ch for ch in str(name).lower().replace("-", " ") if ch.isalpha() or ch == " ").split()
    return " ".join(w for w in parts if w not in {"jr", "sr", "ii", "iii", "iv", "v"})


def _names() -> dict:
    path = RAW_DIR / "players.parquet"
    if not path.exists():
        return {}
    return D._cached(("player_names",), D._mt(path), lambda: dict(pd.read_parquet(path, columns=["gsis_id", "display_name"]).dropna().values))


def player_games(season: int) -> pd.DataFrame:
    """Per player per game: passing, rushing and receiving yards and catches, from local play-by-play."""
    path = RAW_DIR / f"play_by_play_{season}.parquet"
    if not path.exists():
        return pd.DataFrame()

    def build():
        cols = ["game_id", "week", "posteam", "play_type", "two_point_attempt", "qb_kneel", "qb_spike", "sack", "passer_player_id",
                "receiver_player_id", "rusher_player_id", "passing_yards", "receiving_yards", "rushing_yards", "complete_pass"]
        p = pd.read_parquet(path, columns=cols)
        p = p[p["play_type"].isin(["pass", "run"]) & (p["two_point_attempt"] != 1) & (p["qb_kneel"] != 1) & (p["qb_spike"] != 1)]
        p = p.assign(dropback=(p["sack"] != 1).astype(int))
        k = ["game_id", "week", "posteam"]
        pas = (p[(p["play_type"] == "pass") & p["passer_player_id"].notna()].groupby(k + ["passer_player_id"])
               .agg(pass_yds=("passing_yards", "sum"), att=("dropback", "sum")).rename_axis(k + ["pid"]))
        rec = (p[(p["play_type"] == "pass") & (p["sack"] != 1) & p["receiver_player_id"].notna()].groupby(k + ["receiver_player_id"])
               .agg(rec_yds=("receiving_yards", "sum"), rec=("complete_pass", "sum")).rename_axis(k + ["pid"]))
        rus = (p[(p["play_type"] == "run") & p["rusher_player_id"].notna()].groupby(k + ["rusher_player_id"])
               .agg(rush_yds=("rushing_yards", "sum"), carries=("rushing_yards", "size")).rename_axis(k + ["pid"]))
        out = pas.join(rec, how="outer").join(rus, how="outer").fillna(0).reset_index()
        out["posteam"] = out["posteam"].map(lambda t: normalize_team(t) if isinstance(t, str) else t)
        return out
    return D._cached(("player_games", season), D._mt(path), build)


STAT_NAME = {"rec_yds": "Receiving yards", "rec": "Receptions", "rush_yds": "Rushing yards"}
STAT_CODE = {v: k for k, v in STAT_NAME.items()}


def _row(name: str, team: str, stat: str, value: float, lo=None, hi=None, **extra) -> dict:
    return {"player": name, "team": team, "stat": stat, "typical": float(value), "range_low": lo, "range_high": hi,
            "market_line": None, "market_chance": None, "our_chance": None, **extra}


def _replacement(team: str, pos: str, week: int, season: int, taken: set, u, names: dict) -> str | None:
    """The player who steps in at `pos`: an active roster player outside the regular rotation (most recent snaps first, then
    most production last season); if there is none, a practice-squad player, who would be called up."""
    path = RAW_DIR / f"roster_weekly_{season}.parquet"
    cands = []
    if path.exists():
        r = D._cached(("roster", season), D._mt(path), lambda: pd.read_parquet(path, columns=["team", "week", "position", "status", "gsis_id", "full_name"]))
        r = r[(r["team"].map(lambda t: normalize_team(t) if isinstance(t, str) else t) == team) & r["status"].isin(["ACT", "DEV"])]
        if len(r):
            wk = r[r["week"] <= week]["week"].max() if (r["week"] <= week).any() else r["week"].max()
            r = r[(r["week"] == wk) & (r["position"].map(lambda p: U.POS_GROUP.get(p, "OTHER")) == pos)]
            for status, suffix in (("ACT", ""), ("DEV", " (practice squad)")):
                cands = [(gid, nm + suffix) for gid, nm, st in zip(r["gsis_id"], r["full_name"], r["status"]) if st == status and _norm(nm) not in taken]
                if cands:
                    break
    if not cands:
        return None
    seen = u.players.set_index("pid")["n"].to_dict() if u is not None else {}
    last = player_games(season - 1)
    prod = last.groupby("pid")[["rec_yds", "rush_yds"]].sum().sum(axis=1).to_dict() if len(last) else {}
    return max(cands, key=lambda c: (seen.get(c[0], 0), prod.get(c[0], 0.0)))[1]


def team_players(team: str, week: int, out: dict, saved: list[dict], expected_points: float | None = None, season: int = D.SEASON):
    """Every player expected to touch the ball, with per-game projections after injuries.

    Volume and shares come from lab.usage (last six games before `week`; last season's for week 1). Saved projections,
    where they exist, replace the usage numbers for the players they cover. Players ruled out are removed and their
    production moves by the measured rule in lab.usage (see docs/REDISTRIBUTION_CHECK.md), including a named replacement.
    Returns (rows, moves, source label).
    """
    rule, _ = U.current_rule()
    fp_rule = X.load_rule()
    g = U.player_games((season - 1, season))
    u = U.usage(g, season, team, week)
    label = f"usage before week {week}"
    su, wk_used = season, week
    if u is None:
        u = U.usage(g, season - 1, team, 99)
        label, su, wk_used = f"{season - 1} usage", season - 1, 99
    names = _names()
    saved_t = [r for r in saved if r["team"] == team]
    if u is None:
        return (saved_t, [], "saved projections" if saved_t else "no player data", {"fpds": {"used": False}, "td_weights": {}})
    keys0 = u.players["pid"].map(lambda x: _norm(names.get(x, x)))
    out0 = set(u.players.loc[keys0.isin(out) & u.players["active"], "pid"])
    u, fp_info = X.blend_shares(u, team, su, wk_used, out0, fp_rule)
    p = u.players.copy()
    p["name"] = p["pid"].map(lambda x: names.get(x, x))
    p["key"] = p["name"].map(_norm)
    out_ids = set(p.loc[p["key"].isin(out) & p["active"], "pid"])
    base = rule.project(u, set()).set_index("pid")
    adj = rule.project(u, out_ids).set_index("pid")
    by_saved = {(_norm(r["player"]), STAT_CODE.get(r["stat"])): r for r in saved_t}

    # QB: the regular starter (most dropbacks), else the next healthy passer, else the team's usual passing volume.
    qbs = p[p["att"] > 0].assign(tot=lambda x: x["att"] * x["n"]).sort_values(["tot", "last"], ascending=False)
    healthy = qbs[~qbs["key"].isin(out)]
    starter = qbs.iloc[0] if len(qbs) else None
    qb = healthy.iloc[0] if len(healthy) else None
    rows, moves = [], []
    if qb is not None:
        sv = next((r for r in saved_t if r["stat"] == "Passing yards" and _norm(r["player"]) == qb["key"]), None)
        yds = sv["typical"] if sv else (qb["pass_yds"] if starter is not None and qb["pid"] == starter["pid"] else u.totals["pass_yds"])
        rows.append(sv or _row(qb["name"], team, "Passing yards", yds))
        if starter is not None and starter["key"] in out:
            moves.append({"player": starter["name"], "status": out[starter["key"]][1],
                          "text": f"{qb['name']} starts at quarterback, projected for the team's usual {u.totals['pass_yds']:.0f} passing yards a game."})

    # Everyone else: saved projection or usage, plus this game's injury shift (scaled to the saved numbers when those exist).
    shift = {}
    for s in U.STATS:
        lost_usage = float(base.loc[base.index.isin(out_ids), s].sum())
        lost_saved = sum(by_saved[(k, s)]["typical"] if (k, s) in by_saved else float(base.at[pid, s])
                         for pid, k in p.loc[p["pid"].isin(out_ids), ["pid", "key"]].itertuples(index=False) if pid in base.index)
        scale = lost_saved / lost_usage if lost_usage > 0 else 1.0
        for pid in adj.index:
            before = float(base.at[pid, s]) if pid in base.index else 0.0
            shift[(pid, s)] = (float(adj.at[pid, s]) - before) * scale
    taken = set(out) | set(p.loc[p["active"], "key"])
    new_names = {}
    for pid in [i for i in adj.index if str(i).startswith("NEW:")]:
        pos = pid.split(":")[1]
        nm = _replacement(team, pos, week, season, taken, u, names)
        new_names[pid] = nm
        if nm:
            taken.add(_norm(nm))
    for pid in adj.index:
        is_new = str(pid).startswith("NEW:")
        if is_new:
            name = new_names.get(pid)
            if not name:  # nobody on the roster to name: give it to the top healthy regular at that position
                pos = pid.split(":")[1]
                regs = adj[(adj["pos"] == pos) & ~adj.index.str.startswith("NEW:")]
                if regs.empty:
                    continue
                tgt = regs["rec_yds"].add(regs["rush_yds"]).idxmax()
                for s in U.STATS:
                    shift[(tgt, s)] = shift.get((tgt, s), 0.0) + shift[(pid, s)]
                continue
            key = _norm(name)
        else:
            if pid not in p.set_index("pid").index:
                continue
            info = p.set_index("pid").loc[pid]
            name, key = info["name"], info["key"]
            if key in out:
                continue
        carries_pg = None
        for s in U.STATS:
            sv = by_saved.get((key, s))
            val = (sv["typical"] if sv else (0.0 if is_new else float(base.at[pid, s]))) + shift.get((pid, s), 0.0)
            if val < 0.5 and not (s == "rush_yds" and val > 0):
                continue
            lo = hi = None
            if sv and sv.get("range_low") is not None and sv["typical"] > 0:
                f = val / sv["typical"]
                lo, hi = sv["range_low"] * f, (sv["range_high"] or 0) * f
            if s == "rush_yds" and not is_new:
                info = p.set_index("pid").loc[pid]
                ypc = info["rush_pg"] / info["carries"] if info["carries"] > 0 else 4.3
                carries_pg = val / float(np.clip(ypc, 2.5, 7.0))
            elif s == "rush_yds":
                carries_pg = val / 4.3
            extra = {"carries": carries_pg} if s == "rush_yds" else {}
            if is_new:
                extra["replacement"] = True
            rows.append(_row(name, team, STAT_NAME[s], val, lo, hi, **extra))

    # Where each missing player's production went, one player at a time.
    for pid in out_ids:
        if starter is not None and pid == starter["pid"]:
            continue
        info = p.set_index("pid").loc[pid]
        others_out = out_ids - {pid}
        alone = rule.project(u, others_out).set_index("pid")  # everyone else already out, then remove this player too
        solo = rule.project(u, out_ids).set_index("pid")
        gains = {}
        for s in ("rec_yds", "rush_yds"):
            for j in solo.index:
                if j in out_ids:
                    continue
                d = float(solo.at[j, s]) - (float(alone.at[j, s]) if j in alone.index else 0.0)
                if d >= 1:
                    nm = new_names.get(j) if str(j).startswith("NEW:") else names.get(j, j)
                    if nm:
                        gains[nm] = gains.get(nm, 0.0) + d
        lost = {s: float(base.at[pid, s]) for s in U.STATS if pid in base.index}
        if not lost or (lost.get("rec_yds", 0) + lost.get("rush_yds", 0)) < 3:
            continue
        yds = {x: lost.get(x, 0.0) for x in ("rec_yds", "rush_yds")}
        kept = sum(rule.k_for(team, x) * v for x, v in yds.items()) / max(sum(yds.values()), 1)
        top = sorted(gains.items(), key=lambda x: -x[1])[:5]
        repl = {nm for j, nm in new_names.items() if nm}
        parts = ", ".join(f"{n} +{v:.0f}{' (steps in)' if n in repl else ''}" for n, v in top)
        what = " and ".join(f"{lost[s]:.0f} {STAT_NAME[s].lower()}" for s in ("rec_yds", "rush_yds") if lost.get(s, 0) >= 1)
        moves.append({"player": info["name"], "status": out[info["key"]][1],
                      "text": f"Usually {what} a game. The team keeps about {kept:.0%} of it: {parts}."})
    # Usage numbers are per-game averages; scale them to this game's expected points, as lab/props/weekly.py does.
    ratio = _volume_ratio(team, week, season, expected_points)
    if ratio != 1.0:
        saved_keys = {(_norm(r["player"]), r["stat"]) for r in saved_t}
        for r in rows:
            if (_norm(r["player"]), r["stat"]) not in saved_keys:
                r["typical"] *= ratio
                if r.get("carries"):
                    r["carries"] *= ratio
        label += f", scaled x{ratio:.2f} to the expected score"
    name_pid = dict(zip(p["name"], p["pid"]))
    prof = X.profile(team, su, wk_used, [name_pid[n] for n in {r["player"] for r in rows} if n in name_pid])
    seen = set()
    for r in rows:
        pid = name_pid.get(r["player"])
        if pid in prof and r["player"] not in seen:
            r["fpds"] = prof[pid]
            seen.add(r["player"])
    td_w = {names.get(pid, pid): w for pid, w in X.rec_td_weights(u, team, su, wk_used, out_ids, fp_rule).items()}
    extra = {"fpds": {**fp_info, "players": len(prof)}, "td_weights": td_w}
    return rows, moves, ("saved projections, " if saved_t else "") + label, extra


def _fpds_summary(teams: dict) -> dict:
    rule = X.load_rule()
    td = rule.get("td", {}).get("rec_td", {})
    return {"through_week": X.through().get("weekly_through"), "tested": bool(rule), "catches_for_thin_history": "rec" in rule.get("weights", {}),
            "receiving_yards_blend": "rec_yds" in rule.get("weights", {}), "td_red_zone": bool(td.get("uses_fpds")),
            "thin_players": {t: v.get("thin_players", 0) for t, v in teams.items()}}


def _rule_summary() -> dict:
    rule, meta = U.current_rule()
    return {"kept_rec": rule.k.get("rec_yds", 1.0), "kept_rush": rule.k.get("rush_yds", 1.0), "to_new_rec": rule.to_new.get("rec_yds", 0.0),
            "to_new_rush": rule.to_new.get("rush_yds", 0.0), "fitted_on": meta.get("fitted_on")}


VOLUME_CLIP = (0.75, 1.35)


def _volume_ratio(team: str, week: int, season: int, expected_points: float | None) -> float:
    """Expected points over the team's points per game in the same window the usage comes from."""
    if expected_points is None:
        return 1.0
    G = D.games_table()
    G = G[(G["game_type"] == "REG") & G["completed"] & ((G["home_team"] == team) | (G["away_team"] == team))]
    g = G[(G["season"] == season) & (G["week"] < week)]
    if g.empty:
        g = G[G["season"] == season - 1]
    g = g.sort_values("kickoff_utc").tail(U.WINDOW)
    if g.empty:
        return 1.0
    ppg = np.where(g["home_team"] == team, g["home_score"], g["away_score"]).astype(float).mean()
    return float(np.clip(expected_points / max(ppg, 1.0), *VOLUME_CLIP))


def current_week() -> int:
    G = D.games_table()
    G = G[(G["season"] == D.SEASON) & (G["game_type"] == "REG")]
    up = G[G["kickoff_utc"] > pd.Timestamp.now(tz="UTC")]
    return int(up["week"].min()) if len(up) else int(G["week"].max())


def unavailable(team: str, week: int, season: int = D.SEASON) -> tuple[dict, str | None]:
    """{normalized name: (name, status)} for players not expected to play, and where that came from.

    Past weeks use that week's official report; this week adds the latest ESPN report; later weeks keep only
    long-term absences (injured reserve, suspension), since weekly statuses are not known yet.
    """
    cur = current_week()
    out, source = {}, None
    path = RAW_DIR / f"injuries_{season}.parquet"
    if path.exists() and week <= cur:
        rep = pd.read_parquet(path, columns=["team", "week", "full_name", "report_status"])
        rep = rep[(rep["week"] == week) & rep["report_status"].isin(["Out", "Doubtful"])]
        rep = rep[rep["team"].map(lambda t: normalize_team(t) if isinstance(t, str) else t) == team]
        for r in rep.itertuples(index=False):
            out[_norm(r.full_name)] = (r.full_name, r.report_status)
        if len(rep):
            source = f"the official injury report for week {week}"
    if week >= cur:
        inj, stamp = D.injuries_now()
        if not inj.empty:
            keep = NOT_PLAYING if week == cur else LONG_TERM
            for r in inj[(inj["team"] == team) & inj["status"].isin(keep)].itertuples(index=False):
                out.setdefault(_norm(r.player), (r.player, r.status))
            source = "the latest injury report" + ("" if week == cur else " (long-term absences only; weekly statuses come out game week)")
    return out, source


def fallback_lines(away: str, home: str, week: int) -> dict | None:
    """Expected margin and total from this season's points scored and allowed before `week`, when no betting line exists."""
    G = D.games_table()
    G = G[(G["season"] == D.SEASON) & (G["game_type"] == "REG") & G["completed"] & (G["week"] < week)]
    pf, pa = {}, {}
    for t in (away, home):
        s = D.team_summary(G, t)
        if not s["games"]:
            return None
        pf[t], pa[t] = s["pf"], s["pa"]
    hp = (pf[home] + pa[away]) / 2 + HOME_EDGE / 2
    ap = (pf[away] + pa[home]) / 2 - HOME_EDGE / 2
    label = "this season's scoring averages (no betting line yet)"
    return {"margin": hp - ap, "total": hp + ap, "sd_m": D.DEFAULT_SD["margin"], "sd_t": D.DEFAULT_SD["total"], "margin_label": label, "total_label": label}


# --------------------------------------------------------------------------- public API

def simulate(gid: str) -> dict | None:
    d = D.game_detail(gid)
    if d is None:
        return None
    away, home, week = d["away"], d["home"], d["week"]
    out = {"gid": gid, "away": away, "home": home, "ok": False}
    e = d.get("expected") or {}
    if e.get("margin") is None or e.get("total") is None:
        e = fallback_lines(away, home, week) or {}
    if e.get("margin") is None:
        out["reason"] = "No betting line and no games played yet this season, so there is nothing to simulate from."
        return out
    rng = score_ranges(gid, e["margin"], e["sd_m"], e["total"], e["sd_t"])
    ctx = team_context(before_week=week)

    saved = d.get("props") or []
    players, moves, gone, sources, inj_source = [], [], [], {}, None
    td_weights, fp_teams = {}, {}
    for t in (away, home):
        out_t, src = unavailable(t, week)
        inj_source = inj_source or src
        rows, mv, sources[t], extra = team_players(t, week, out_t, saved, (rng["home"] if t == home else rng["away"])["median"])
        td_weights[t], fp_teams[t] = extra["td_weights"], extra["fpds"]
        players += rows
        moves += [m | {"team": t} for m in mv]
        gone += [{"team": t, "player": n, "status": st} for n, st in out_t.values()]

    targets = {away: rng["away"]["median"], home: rng["home"]["median"]}
    row = D.games_table().set_index("game_id").loc[gid]
    out.update({"ok": True, "ranges": rng, "replay": replay(gid, away, home, targets, players, ctx, td_weights),
                "defense": defense_matchups(ctx, away, home) if not ctx.empty else [],
                "source": {"margin": e.get("margin_label"), "total": e.get("total_label")}, "has_players": bool(players),
                "players": players, "player_source": sources, "injury_moves": moves, "unavailable": gone, "injury_source": inj_source,
                "redistribution": _rule_summary(), "fpds": _fpds_summary(fp_teams),
                "weather": gameweather.kickoff_weather(gid, row.get("stadium") or "", row.get("roof"), row["kickoff_utc"], bool(row["completed"]))})
    return D.clean(out)
