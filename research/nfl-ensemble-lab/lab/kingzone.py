"""King of the End Zone: each player's chance of scoring the longest touchdown of one game.

The promotion pays a share of a prize pool to the player who scores the longest touchdown (passing touchdowns count for the receiver, not the
passer; a return or defensive touchdown can be the longest, in which case the defense or special teams side wins).

Model, all from local play-by-play and the simulated game's own inputs (no new data source, nothing fitted to this game's result):
  1. League shape. For each kind of touch (carry, target) and position, the rate of touchdowns of each length per touch, 2022 to the week before.
     A touchdown's length is the yard line the play started from, so a 60-yard score is a play that began 60 yards out and went all the way.
  2. Player propensity. How often he gains 20+ and 40+ yards per touch, against his position (shrunk toward the position so a few plays do not
     decide it). Receivers add deep-target rate (20+ air yards) and yards after the catch against the position and yards per route run;
     runners add broken tackles per carry (Pro Football Reference). These lift only the long lengths (a ramp from 10 yards, full by 25 for the
     20+ rate and from 25 to 50 for the 40+ rate).
  3. Opponent. The defense's rate of allowed 20+ and 40+ gains per carry and per target over its last seven games, shrunk the same way.
  4. Volume and environment. Expected carries and targets from the simulated game, and each team's expected touchdowns from its expected points
     (the same figure the touchdown rankings use): a team's touchdown total is held to that figure, so a high-scoring game gives more chances.
  5. Everyone else. Touchdowns by players not listed, and defense and special-teams touchdowns (rate and length from the league record), compete
     for the title too, so a player's chance is not overstated.
Touchdowns are Poisson by length; ties are split evenly. Importance weights in the blend below are judgment, not fitted (the brief's
"very high", "high", "medium" ordering); `backtest` checks the whole thing against the earlier weeks. Local files only, read-only, deterministic.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from . import gamesim as S
from . import rankings as R
from . import usage as U
from .config import RAW_DIR
from .ingest import normalize_team

LEAGUE_FROM = 2022
LENGTHS = np.arange(1, 100)
PBP_COLS = ["game_id", "season", "week", "season_type", "posteam", "defteam", "play_type", "yardline_100", "rusher_player_id", "receiver_player_id",
            "rush_touchdown", "pass_touchdown", "touchdown", "td_team", "two_point_attempt", "qb_kneel", "rushing_yards", "receiving_yards", "complete_pass",
            "air_yards", "yards_after_catch", "return_yards", "fumble_recovery_1_yards", "td_player_id", "td_player_name"]
# Exponents of each player ratio in his multiplier (judgment, from the brief's "very high / high / medium" order).
W_REC = {"explosive": 0.55, "deep": 0.25, "yac": 0.15, "yprr": 0.15}
W_RUSH = {"explosive": 0.70, "broken": 0.30}
PRIOR20, PRIOR40 = 8.0, 5.0   # pseudo-events pulling a player or defense toward its group
CLIP = (0.4, 2.5)
DEF_WINDOW = 7
_CACHE: dict = {}


def _stamp() -> tuple:
    p = RAW_DIR / f"play_by_play_{D.SEASON}.parquet"
    return (p.stat().st_mtime_ns,) if p.exists() else ()


def _smooth(x: np.ndarray, width: int = 9) -> np.ndarray:
    k = np.ones(width) / width
    pad = width // 2
    return np.convolve(np.pad(x, pad, mode="edge"), k, mode="valid")


def _ramps() -> tuple[np.ndarray, np.ndarray]:
    w20 = np.clip((LENGTHS - 10) / 15.0, 0, 1)
    w40 = np.clip((LENGTHS - 25) / 25.0, 0, 1)
    return w20, w40


def _mult(m20: float, m40: float) -> np.ndarray:
    """Multiplier by touchdown length: 1 up to 10 yards, rising to m20 by 25, then to m40 by 50 and flat beyond."""
    w20, w40 = _ramps()
    return np.exp(np.log(m20) * w20 * (1 - w40) + np.log(m40) * w40)


def _pbp() -> pd.DataFrame:
    parts = []
    for s in range(LEAGUE_FROM, D.SEASON + 1):
        f = RAW_DIR / f"play_by_play_{s}.parquet"
        if f.exists():
            parts.append(pd.read_parquet(f, columns=PBP_COLS))
    p = pd.concat(parts, ignore_index=True)
    return p[p["season_type"] == "REG"].copy()


def _touches(p: pd.DataFrame) -> pd.DataFrame:
    pos = U.positions()
    no2 = p["two_point_attempt"].fillna(0) != 1
    rush = p[(p["play_type"] == "run") & p["rusher_player_id"].notna() & no2 & (p["qb_kneel"].fillna(0) != 1)]
    tgt = p[(p["play_type"] == "pass") & p["receiver_player_id"].notna() & no2]
    r = pd.DataFrame({"season": rush["season"], "week": rush["week"], "game_id": rush["game_id"], "opp": rush["defteam"], "pid": rush["rusher_player_id"], "kind": 0,
                      "yl": rush["yardline_100"], "td": (rush["rush_touchdown"] == 1).astype(int), "gain": rush["rushing_yards"].fillna(0), "air": np.nan,
                      "yac": np.nan, "complete": 1})
    t = pd.DataFrame({"season": tgt["season"], "week": tgt["week"], "game_id": tgt["game_id"], "opp": tgt["defteam"], "pid": tgt["receiver_player_id"], "kind": 1,
                      "yl": tgt["yardline_100"], "td": (tgt["pass_touchdown"] == 1).astype(int),
                      "gain": np.where(tgt["complete_pass"] == 1, tgt["receiving_yards"].fillna(0), 0.0), "air": tgt["air_yards"], "yac": tgt["yards_after_catch"],
                      "complete": tgt["complete_pass"].fillna(0).astype(int)})
    x = pd.concat([r, t], ignore_index=True)
    x["opp"] = x["opp"].map(lambda v: normalize_team(v) if isinstance(v, str) else v)
    pg = x["pid"].map(pos).fillna("OTHER")
    x["pg"] = np.where(x["kind"] == 0, np.where(pg.isin(["QB", "RB", "WR", "TE"]), pg, "RB"), np.where(pg.isin(["RB", "WR", "TE"]), pg, "WR"))
    x["g20"] = (x["gain"] >= 20).astype(int)
    x["g40"] = (x["gain"] >= 40).astype(int)
    x["deep"] = (x["air"] >= 20).astype(int)
    return x


def _returns(p: pd.DataFrame) -> pd.DataFrame:
    """Touchdowns by the defense or special teams: one row per score with its length in yards."""
    d = p[(p["touchdown"] == 1) & p["td_team"].notna() & (p["td_team"] != p["posteam"]) & p["play_type"].isin(["kickoff", "punt", "pass", "run", "field_goal", "no_play"])]
    # An interception or fumble return reads as a play by the offense whose opponent scored; kickoff and punt returns have posteam as the kicking team.
    ln = d["return_yards"].where(d["return_yards"] > 0, d["fumble_recovery_1_yards"]).fillna(d["return_yards"]).abs()
    return pd.DataFrame({"season": d["season"], "week": d["week"], "game_id": d["game_id"], "team": d["td_team"], "len": ln.clip(1, 99)}).dropna()


def _league(week: int) -> dict:
    """Everything built from history strictly before (season, week); cached per week and file stamp."""
    key = (week, _stamp())
    if key in _CACHE:
        return _CACHE[key]
    p = _pbp()
    before = (p["season"] < D.SEASON) | ((p["season"] == D.SEASON) & (p["week"] < week))
    p = p[before]
    t = _touches(p)
    lg = {}
    for (kind, pg), g in t.groupby(["kind", "pg"]):
        n = len(g)
        tdl = np.bincount(g.loc[g["td"] == 1, "yl"].clip(1, 99).astype(int), minlength=100)[1:100].astype(float)
        dens = _smooth(tdl / max(n, 1))
        c = g[g["complete"] == 1]
        lg[(kind, pg)] = {"n": n, "p20": g["g20"].mean(), "p40": max(g["g40"].mean(), 1e-4), "deep": g["deep"].mean() if kind == 1 else None,
                          "yac": c["yac"].mean() if kind == 1 and len(c) else None, "catch": g["complete"].mean() if kind == 1 else None, "dens": dens, "tds": float(tdl.sum())}
    # sparse groups borrow the pooled shape for their kind
    for kind in (0, 1):
        pool = t[t["kind"] == kind]
        tdl = np.bincount(pool.loc[pool["td"] == 1, "yl"].clip(1, 99).astype(int), minlength=100)[1:100].astype(float)
        lg[(kind, "ALL")] = {"n": len(pool), "p20": pool["g20"].mean(), "p40": max(pool["g40"].mean(), 1e-4), "dens": _smooth(tdl / len(pool)), "tds": float(tdl.sum())}
    for (kind, pg), v in list(lg.items()):
        if pg != "ALL" and v["n"] < 800:
            lg[(kind, pg)] = {**lg[(kind, "ALL")], "deep": v["deep"], "yac": v["yac"], "catch": v["catch"]}
    player = t[t["season"] >= D.SEASON - 2].groupby(["pid", "kind"]).agg(n=("g20", "size"), c20=("g20", "sum"), c40=("g40", "sum"), deep=("deep", "sum"), comp=("complete", "sum"),
                                                                       yac=("yac", "sum"), air=("air", "sum")).reset_index()
    # a defense: its last seven games this season, topped up by last season when fewer are available
    t["order"] = t["season"] * 100 + t["week"]
    dgames = t[["opp", "game_id", "order"]].drop_duplicates().sort_values("order")
    last = dgames.groupby("opp").tail(DEF_WINDOW)
    dt = t.merge(last[["opp", "game_id"]], on=["opp", "game_id"])
    defense = dt.groupby(["opp", "kind"]).agg(n=("g20", "size"), c20=("g20", "sum"), c40=("g40", "sum"), games=("game_id", "nunique")).reset_index()
    ret = _returns(p)
    team_games = len(p[["game_id"]].drop_duplicates()) * 2
    rdens = _smooth(np.bincount(ret["len"].astype(int), minlength=100)[1:100].astype(float) / max(len(ret), 1))
    out = {"lg": lg, "player": player.set_index(["pid", "kind"]), "defense": defense.set_index(["opp", "kind"]), "ret_rate": len(ret) / max(team_games, 1), "ret_dens": rdens,
           "ret_n": len(ret), "pool_dens": {k: lg[(k, "ALL")]["dens"] for k in (0, 1)}}
    out["broken"] = _broken()
    _CACHE.clear()
    _CACHE[key] = out
    return out


def _broken() -> dict:
    """Broken tackles per carry by player (Pro Football Reference, last three seasons), plus the league rate."""
    frames = []
    for s in range(D.SEASON - 2, D.SEASON + 1):
        f = RAW_DIR / f"pfradv_rush_{s}.parquet"
        if f.exists():
            frames.append(pd.read_parquet(f, columns=["pfr_player_name", "carries", "rushing_broken_tackles"]))
    if not frames:
        return {"rate": None, "by": {}}
    d = pd.concat(frames).dropna()
    d = d[d["carries"] > 0]
    rate = d["rushing_broken_tackles"].sum() / d["carries"].sum()
    d["k"] = d["pfr_player_name"].map(S._norm)
    g = d.groupby("k").agg(bt=("rushing_broken_tackles", "sum"), n=("carries", "sum"))
    return {"rate": float(rate), "by": {k: (float(r.bt), float(r.n)) for k, r in g.iterrows()}}


def _ratio(events: float, n: float, rate: float, prior: float) -> float:
    """Shrunk rate over the group rate: `prior` pseudo-events at the group rate are added to his own."""
    return float(np.clip((events + prior) / (n * rate + prior), *CLIP))


def _propensity(L: dict, pid: str | None, name: str, pg: str, kind: int, yprr: float | None) -> dict:
    """The player's 20+ and 40+ multipliers and the facts behind them."""
    base = L["lg"].get((kind, pg)) or L["lg"][(kind, "ALL")]
    row = L["player"].loc[(pid, kind)] if pid is not None and (pid, kind) in L["player"].index else None
    n = float(row["n"]) if row is not None else 0.0
    c20 = float(row["c20"]) if row is not None else 0.0
    c40 = float(row["c40"]) if row is not None else 0.0
    r20, r40 = _ratio(c20, n, base["p20"], PRIOR20), _ratio(c40, n, base["p40"], PRIOR40)
    info = {"touches": n, "p20": c20 / n if n else None, "p40": c40 / n if n else None, "league20": base["p20"], "league40": base["p40"], "r20": r20, "r40": r40}
    if kind == 1:
        deep = _ratio(float(row["deep"]) if row is not None else 0.0, n, base["deep"] or 0.1, PRIOR20)
        comp = float(row["comp"]) if row is not None else 0.0
        yac_avg = float(row["yac"]) / comp if comp else None
        yac = float(np.clip(((float(row["yac"]) if row is not None else 0.0) + 25 * base["yac"]) / ((comp + 25) * base["yac"]), *CLIP)) if base.get("yac") else 1.0
        yp = float(np.clip(yprr / 1.6, *CLIP)) if yprr else 1.0
        if yprr and row is not None:   # YPRR is a noisy 4 to 6 game figure: half weight toward 1
            yp = float(np.sqrt(yp))
        m20 = r20 ** W_REC["explosive"] * deep ** W_REC["deep"] * yac ** W_REC["yac"] * yp ** W_REC["yprr"]
        m40 = r40 ** W_REC["explosive"] * deep ** W_REC["deep"] * yac ** W_REC["yac"] * yp ** W_REC["yprr"]
        info.update(adot=float(row["air"]) / n if row is not None and n else None, deep_rate=float(row["deep"]) / n if row is not None and n else None,
                    league_deep=base["deep"], yac_avg=yac_avg, league_yac=base["yac"], deep_ratio=deep, yac_ratio=yac, yprr=yprr)
    else:
        bt_rate = L["broken"]["rate"]
        bt, bn = L["broken"]["by"].get(S._norm(name), (0.0, 0.0))
        br = _ratio(bt, bn, bt_rate, 4.0) if bt_rate else 1.0
        m20 = r20 ** W_RUSH["explosive"] * br ** W_RUSH["broken"]
        m40 = r40 ** W_RUSH["explosive"] * br ** W_RUSH["broken"]
        info.update(broken_per_carry=bt / bn if bn else None, league_broken=bt_rate, broken_ratio=br)
    info["m20"], info["m40"] = float(np.clip(m20, *CLIP)), float(np.clip(m40, *CLIP))
    return info


def _defense_mult(L: dict, opp: str, kind: int) -> tuple[float, float, dict]:
    try:
        d = L["defense"].loc[(opp, kind)]
    except KeyError:
        return 1.0, 1.0, {}
    base = L["lg"][(kind, "ALL")]
    r20, r40 = _ratio(float(d["c20"]), float(d["n"]), base["p20"], PRIOR20), _ratio(float(d["c40"]), float(d["n"]), base["p40"], PRIOR40)
    return r20, r40, {"allowed20": float(d["c20"]) / float(d["n"]), "league20": base["p20"], "allowed40": float(d["c40"]) / float(d["n"]), "league40": base["p40"], "games": int(d["games"])}


def _entries(sim: dict, L: dict, week: int) -> tuple[list[dict], dict]:
    """One entry per player and kind of touch with his length curve, plus the pooled 'not listed' curves per team."""
    rows = sim["players"]
    by: dict = {}
    for r in rows:
        by.setdefault((r["player"], r["team"]), {})[r["stat"]] = r
    out, extra = [], {}
    for team, m in (sim.get("td_model") or {}).items():
        exp_td = max(R.TD_FLOOR, R.TD_PER_POINT * m["exp_points"] + R.TD_INTERCEPT)
        opp = sim["home"] if team == sim["away"] else sim["away"]
        team_entries = []
        for (name, tm), rs in by.items():
            if tm != team:
                continue
            pid = S._pid_by_norm().get(S._norm(name))
            pos = next(iter(rs.values())).get("pos")
            fp = next((r["fpds"] for r in rs.values() if r.get("fpds")), {})
            for kind in (0, 1):
                if kind == 0:
                    r = rs.get("Rushing yards")
                    touches = float(r.get("carries") or 0) if r else 0.0
                    pg = pos if pos in ("QB", "RB", "WR", "TE") else "RB"
                else:
                    r = rs.get("Receptions")
                    pg = pos if pos in ("RB", "WR", "TE") else "WR"
                    touches = float(r["expected"]) / max(L["lg"].get((1, pg), L["lg"][(1, "ALL")]).get("catch") or 0.65, 0.3) if r else 0.0
                if not r or touches < (1.0 if kind == 0 and pos in ("WR", "TE") else 0.4):
                    continue
                base = L["lg"].get((kind, pg)) or L["lg"][(kind, "ALL")]
                prop = _propensity(L, pid, name, pg, kind, fp.get("yprr"))
                d20, d40, dinfo = _defense_mult(L, opp, kind)
                curve = touches * base["dens"] * _mult(prop["m20"] * d20, prop["m40"] * d40)
                team_entries.append({"player": name, "team": team, "opp": opp, "pos": pos, "kind": kind, "touches": touches, "curve": curve, "prop": prop, "defense": dinfo,
                                     "d20": d20, "d40": d40, "yprr": fp.get("yprr"), "ay_share": fp.get("ay_share")})
        listed_share = 0.0
        rs_ = float(m["rush_share"])
        rush = {r["player"]: max(r["typical"], 0.0) for r in rows if r["team"] == team and r["stat"] == "Rushing yards"}
        tot = sum(rush.values())
        for n in set(m["rec_weights"]) | set(rush):
            listed_share += (1 - rs_) * m["rec_weights"].get(n, 0.0) + (rs_ * rush.get(n, 0.0) / tot if tot > 0 else 0.0)
        listed_share = float(min(listed_share, 0.97))
        raw = sum(float(e["curve"].sum()) for e in team_entries)
        scale = exp_td * listed_share / raw if raw > 0 else 0.0
        for e in team_entries:
            e["curve"] = e["curve"] * scale
            e["exp_td_here"] = float(e["curve"].sum())
        pool = 0.5 * (L["pool_dens"][0] + L["pool_dens"][1])
        extra[team] = {"unlisted": exp_td * (1 - listed_share) * pool / pool.sum(), "exp_td": exp_td, "scale": scale}
        out.extend(team_entries)
    return out, extra


def probabilities(sim: dict, week: int) -> dict:
    """The board for one simulated game: chance of the longest touchdown for every player, plus the field."""
    L = _league(week)
    ents, extra = _entries(sim, L, week)
    ret = L["ret_rate"] * L["ret_dens"] / L["ret_dens"].sum()
    field = {t: ret for t in extra}
    total = sum((e["curve"] for e in ents), np.zeros(99))
    for t, x in extra.items():
        total = total + x["unlisted"] + field[t]
    longer = np.concatenate([np.cumsum(total[::-1])[::-1][1:], [0.0]])   # rate of touchdowns strictly longer than L
    p_none_longer = np.exp(-longer)
    share_scale = (1 - np.exp(-total)) / np.where(total > 0, total, 1.0)   # chance there is at least one at L, over its rate (ties split evenly)

    def win(curve: np.ndarray) -> float:
        return float(np.sum(curve * share_scale * p_none_longer))

    per: dict = {}
    for e in ents:
        k = (e["player"], e["team"])
        per.setdefault(k, {"player": e["player"], "team": e["team"], "opp": e["opp"], "pos": e["pos"], "curve": np.zeros(99), "parts": {}})
        per[k]["curve"] = per[k]["curve"] + e["curve"]
        per[k]["parts"]["rush" if e["kind"] == 0 else "rec"] = e
    rows = []
    for (name, team), v in per.items():
        c = v["curve"]
        rows.append({"player": name, "team": team, "opp": v["opp"], "pos": v["pos"], "chance": win(c), "exp_td": float(c.sum()),
                     "p_40": float(1 - np.exp(-c[39:].sum())), "p_60": float(1 - np.exp(-c[59:].sum())), "parts": v["parts"]})
    rows.sort(key=lambda r: -r["chance"])
    unl = {t: win(x["unlisted"]) for t, x in extra.items()}
    fld = {t: win(field[t]) for t in extra}
    none = float(np.exp(-total.sum()))
    return {"rows": rows, "unlisted": unl, "field": fld, "no_td": none, "expected_longest": float(np.sum(LENGTHS * total * share_scale * p_none_longer)),
            "total_exp_td": float(total.sum()), "extra": {t: x["exp_td"] for t, x in extra.items()}}


def _fmt_pct(x: float | None, d: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


def _why(row: dict) -> list[str]:
    """Plain-English reasons, the ones that raise his chance first and the ones that lower it last, built from the numbers the model used."""
    out = []
    rec, rush = row["parts"].get("rec"), row["parts"].get("rush")
    for e, kind in ((rec, "targets"), (rush, "carries")):
        if not e:
            continue
        p = e["prop"]
        if p["touches"] >= 20 and p["p20"] is not None:
            what = "of his targets" if kind == "targets" else "of his carries"
            line = f"20+ yard gains on {_fmt_pct(p['p20'])} {what} (position average {_fmt_pct(p['league20'])})"
            if p["p40"]:
                line += f", 40+ on {_fmt_pct(p['p40'])} ({_fmt_pct(p['league40'])})"
            out.append((np.log(max(p["r20"], 1e-3)), line))
        if kind == "targets" and p.get("adot") is not None and p["touches"] >= 20:
            out.append((np.log(max(p["deep_ratio"], 1e-3)), f"Average depth of target {p['adot']:.1f} yards; {_fmt_pct(p['deep_rate'])} of targets go 20+ in the air (position {_fmt_pct(p['league_deep'])})"))
            if p.get("yac_avg") is not None:
                out.append((np.log(max(p["yac_ratio"], 1e-3)), f"{p['yac_avg']:.1f} yards after the catch per reception (position {p['league_yac']:.1f})"))
            if p.get("yprr"):
                out.append((0.1, f"{p['yprr']:.2f} yards per route run"))
        if kind == "carries" and p.get("broken_per_carry") is not None:
            out.append((np.log(max(p["broken_ratio"], 1e-3)), f"Breaks a tackle on {_fmt_pct(p['broken_per_carry'])} of carries (league {_fmt_pct(p['league_broken'])})"))
        d = e["defense"]
        if d:
            tag = "pass defense" if kind == "targets" else "run defense"
            out.append((np.log(max(e["d20"], 1e-3)), f"{row['opp']} {tag} has allowed 20+ yard gains on {_fmt_pct(d['allowed20'])} of {'targets' if kind == 'targets' else 'carries'} (league {_fmt_pct(d['league20'])}), last {d['games']} games"))
        out.append((0.05, f"Expected {e['touches']:.1f} {'targets' if kind == 'targets' else 'carries'} in this game"))
    out.sort(key=lambda t: -t[0])
    seen, lines = set(), []
    for _, s in out:
        if s not in seen:
            seen.add(s)
            lines.append(s)
    return lines[:5]


def board(gid: str) -> dict | None:
    """King of the End Zone board for a game id, ready for the screen."""
    g = D.games_table()
    r = g[g["game_id"] == gid]
    if r.empty:
        return None
    r = r.iloc[0]
    week = int(r["week"])
    sim = S.simulate(gid, "typical", 0)
    if not sim or not sim.get("ok"):
        return None
    res = probabilities(sim, week)
    rows = []
    for i, x in enumerate(res["rows"][:25], 1):
        rows.append({"rank": i, "player": x["player"], "team": x["team"], "opp": x["opp"], "pos": x["pos"], "chance": x["chance"], "exp_td": x["exp_td"], "p_40": x["p_40"], "p_60": x["p_60"],
                     "why": _why(x), "kinds": sorted(x["parts"])})
    listed = sum(x["chance"] for x in res["rows"])
    return {"gid": gid, "away": r["away_team"], "home": r["home_team"], "kickoff_utc": str(r["kickoff_utc"]), "week": week, "rows": rows,
            "players_scored": len(res["rows"]), "listed_total": listed, "field": {"defense_special_teams": res["field"], "other_players": res["unlisted"]},
            "no_touchdown": res["no_td"], "expected_longest": res["expected_longest"], "expected_td": res["extra"], "completed": bool(r["completed"]),
            "built_at": time.time()}


_BOARDS: dict = {}


def cached_board(gid: str, ttl: float = 900.0) -> dict | None:
    hit = _BOARDS.get(gid)
    if hit and time.time() - hit["built_at"] < ttl:
        return hit
    b = board(gid)
    if b:
        _BOARDS[gid] = b
    return b


def week_games(week: int) -> dict:
    """The week's games for the picker, with the Monday-night game (the promotion's usual target) preselected."""
    g = D.games_table()
    g = g[(g["season"] == D.SEASON) & (g["week"] == week) & (g["game_type"] == "REG")].sort_values("kickoff_utc")
    ko = pd.to_datetime(g["kickoff_utc"], utc=True).dt.tz_convert("America/New_York")
    mon = g[ko.dt.dayofweek == 0]
    pick = None
    open_ = g[~g["completed"].astype(bool)]
    pool = mon[~mon["completed"].astype(bool)] if len(mon) else mon
    if len(pool):
        pick = pool.iloc[-1]["game_id"]
    elif len(mon):
        pick = mon.iloc[-1]["game_id"]
    elif len(open_):
        pick = open_.iloc[-1]["game_id"]
    elif len(g):
        pick = g.iloc[-1]["game_id"]
    games = [{"gid": x.game_id, "away": x.away_team, "home": x.home_team, "kickoff_utc": str(x.kickoff_utc), "completed": bool(x.completed), "monday": bool(i in mon.index)}
             for i, x in zip(g.index, g.itertuples())]
    return {"week": week, "default_gid": pick, "games": games}


def actual_longest(gid: str) -> dict | None:
    """The real longest touchdown of a finished game from play-by-play: scorer, length, and whether a player (not a defense or return) scored it."""
    p = pd.read_parquet(RAW_DIR / f"play_by_play_{D.SEASON}.parquet", columns=PBP_COLS)
    p = p[(p["game_id"] == gid) & (p["touchdown"] == 1)]
    if p.empty:
        return None
    off = p[(p["td_team"] == p["posteam"]) & p["play_type"].isin(["run", "pass"])].copy()
    off["len"] = off["yardline_100"]
    off["scorer"] = off["td_player_name"]
    off["pid"] = off["td_player_id"]
    best = off["len"].max() if len(off) else 0
    dfn = _returns(p)
    dbest = dfn["len"].max() if len(dfn) else 0
    if dbest > best:
        r = dfn.sort_values("len").iloc[-1]
        return {"scorer": None, "team": r["team"], "length": float(r["len"]), "by": "defense or special teams"}
    top = off[off["len"] == best]
    return {"scorers": [str(x) for x in top["scorer"]], "pids": [str(x) for x in top["pid"]], "team": str(top.iloc[0]["td_team"]), "length": float(best), "by": "player"}
