"""Run the snap simulator for a game: players, venue and rest adjustments, percentages, leans, write-once saved record (docs/SNAPSIM_PREREG.md)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import snapfit
from .snapsim import simulate

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "snapsim"
CACHE = ROOT / "data" / "cache" / "snapsim_venue.json"
N_SIMS = 10_000
STAT_ROWS = {"Passing yards": "pass_yds", "Receptions": "rec", "Receiving yards": "rec_yds", "Rushing yards": "rush_yds", "Completions": "comp", "Rushing attempts": "car"}
SCENARIO = {"share": (0.40, 0.65), "price_of_rest": 0.55, "mult_mean": 0.95, "mult_sd": 0.07, "low": (0.40, 0.88), "high": (0.65, 1.02)}


# ---------------------------------------------------------------- venue and rest
def venue_effects(team: str = "SEA", rest_pair: tuple[int, int] = (11, 8)) -> dict:
    """False-start multiplier for visiting offenses at `team`, rest effect, home margin. 2015 to 2025."""
    key = f"{team}"
    if CACHE.exists():
        c = json.loads(CACHE.read_text())
        if c.get("key") == key:
            return c
    cols = ["game_id", "home_team", "posteam", "play_type", "penalty_type", "penalty_team", "down", "season_type"]
    fr = []
    for s in range(2015, 2026):
        p = pd.read_parquet(RAW / f"play_by_play_{s}.parquet", columns=cols)
        p = p[(p["season_type"] == "REG") & p["play_type"].isin(["pass", "run", "no_play"]) & p["down"].notna() & (p["posteam"] != p["home_team"])]
        fs = ((p["penalty_type"] == "False Start") & (p["penalty_team"] == p["posteam"])).astype(int)
        fr.append(pd.DataFrame({"home": p["home_team"], "fs": fs}))
    d = pd.concat(fr).groupby("home").agg(n=("fs", "size"), x=("fs", "sum"))
    d["rate"] = d["x"] / d["n"]
    base = d["x"].sum() / d["n"].sum()
    vb = max(float(d["rate"].var(ddof=1)) - float((base * (1 - base) / d["n"]).mean()), 1e-12)
    k = base * (1 - base) / vb
    d["shrunk"] = (d["x"] + k * base) / (d["n"] + k)
    d["rank_raw"] = d["rate"].rank(ascending=False).astype(int)
    d["rank_shrunk"] = d["shrunk"].rank(ascending=False).astype(int)
    r = d.loc[team]
    g = pd.read_csv(RAW / "games.csv")
    g = g[(g["game_type"] == "REG") & g["season"].between(2015, 2025) & g["result"].notna() & g["spread_line"].notna()]
    dr = (g["home_rest"].clip(upper=14) - g["away_rest"].clip(upper=14)).to_numpy(float)
    y = (g["result"] - g["spread_line"]).to_numpy(float)
    X = np.column_stack([np.ones(len(dr)), dr])
    beta, res, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    se = float(np.sqrt(resid.var(ddof=2) / ((dr - dr.mean()) ** 2).sum()))
    shrink = beta[1] ** 2 / (beta[1] ** 2 + se ** 2)
    diff = rest_pair[1] - rest_pair[0]
    out = {"key": key, "team": team, "false_start_raw_rate": float(r["rate"]), "false_start_shrunk_rate": float(r["shrunk"]), "league_rate": float(base), "multiplier": float(r["shrunk"] / base),
           "multiplier_raw": float(r["rate"] / base), "rank_raw": int(r["rank_raw"]), "rank_shrunk": int(r["rank_shrunk"]), "stadiums": int(len(d)), "visiting_snaps": int(r["n"]), "visiting_false_starts": int(r["x"]),
           "rest_beta_per_day": float(beta[1]), "rest_se": se, "rest_applied_per_day": float(beta[1] * shrink), "rest_diff_home_minus_away": diff, "rest_points_to_home": float(beta[1] * shrink * diff),
           "home_margin": float(g["result"].mean()), "seasons": "2015-2025"}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out))
    return out


# ---------------------------------------------------------------- players
def _roster_info():
    pl = pd.read_parquet(RAW / "players.parquet", columns=["gsis_id", "display_name", "position"]).drop_duplicates("gsis_id").set_index("gsis_id")
    dc = pd.read_parquet(RAW / "depth_charts_2026.parquet")
    dc = dc.sort_values("dt").drop_duplicates(["team", "gsis_id"], keep="last")
    return pl, dc


def _history_rush(gsis: str, seasons=(2023, 2024, 2025)) -> tuple[float, float]:
    n, yds = 0.0, 0.0
    for s in seasons:
        p = pd.read_parquet(RAW / f"play_by_play_{s}.parquet", columns=["season_type", "rusher_player_id", "rush_attempt", "yards_gained", "qb_scramble", "penalty"])
        p = p[(p["season_type"] == "REG") & (p["rusher_player_id"] == gsis) & (p["rush_attempt"] == 1) & (p["qb_scramble"] != 1) & (p["penalty"] != 1)]
        n += len(p)
        yds += float(p["yards_gained"].sum())
    return n, yds


def build_pool(P: snapfit.Params, p: pd.DataFrame, team: str, week: int, scenario: dict | None, S: int, rng, injuries: pd.DataFrame, fixed=None) -> dict:
    pl, dc = _roster_info()
    t = p[p["posteam"] == team]
    t26 = t[t["yr"] == snapfit.SEASON]
    out_ids = set(injuries[(injuries["team"] == team) & injuries["report_status"].isin(["Out", "Doubtful"])]["gsis_id"].dropna())
    ro = pd.read_parquet(RAW / "roster_weekly_2026.parquet", columns=["team", "week", "gsis_id", "status", "full_name"])
    ro = ro[(ro["team"] == team) & (ro["week"] == min(week, ro["week"].max()))]
    out_ids |= set(ro.loc[ro["status"] != "ACT", "gsis_id"].dropna())     # reserve lists, suspensions and game-day inactives do not play
    elig = set(dc[dc["team"] == team]["gsis_id"]) | set(t26["receiver_player_id"].dropna()) | set(t26["rusher_player_id"].dropna())
    if scenario:
        elig |= {scenario["star"], scenario["rookie"]}
    elig -= out_ids
    rookie_on = bool(scenario) and scenario["rookie"] in elig
    rec = t[(t["pass_attempt"] == 1) & (t["penalty"] != 1) & t["receiver_player_id"].isin(elig)]
    car = t[(t["rush_attempt"] == 1) & (t["qb_scramble"] != 1) & (t["penalty"] != 1) & t["rusher_player_id"].isin(elig)]
    dbk = t26[(t26["qb_dropback"] == 1)].groupby("passer_player_id")["w"].sum().sort_values(ascending=False)
    qb = next((q for q in dbk.index if q not in out_ids), None) or dc[(dc["team"] == team) & (dc["pos_abb"] == "QB")].sort_values("pos_rank")["gsis_id"].iloc[0]
    ids = sorted(i for i in ((set(rec["receiver_player_id"]) | set(car["rusher_player_id"]) | {qb} | ({scenario["star"]} | ({scenario["rookie"]} if rookie_on else set()) if scenario else set())) & (elig | {qb})) if isinstance(i, str))
    pos = {i: (pl["position"].get(i) or "") for i in ids}
    nm = {i: (pl["display_name"].get(i) or i) for i in ids}
    idx = {i: k for k, i in enumerate(ids)}
    Pn = len(ids)

    def shares(df, col, flag_rz):
        a = np.zeros((2, Pn))
        for z in (0, 1):
            d = df[(df["yardline_100"] <= 10) == bool(z)] if flag_rz else df
            c = d.groupby(col)["w"].sum()
            for i, v in c.items():
                a[z, idx[i]] = v
        base = a.sum(0)
        base = base / max(base.sum(), 1e-9)
        z1 = (a[1] + 15 * base) / (a[1].sum() + 15)
        z0 = a[0] / max(a[0].sum(), 1e-9)
        return np.vstack([z0, z1 / max(z1.sum(), 1e-9)])

    ts = shares(rec, "receiver_player_id", True)
    for i in ids:
        if pos[i] == "QB":
            ts[:, idx[i]] = 0
    ts = ts / np.maximum(ts.sum(1, keepdims=True), 1e-9)
    cs = shares(car, "rusher_player_id", True)
    qbs = max(idx[qb], 0)
    # catch rate, yards per reception, yards per carry deltas, shrunk to the team
    ff = rec[rec["complete_pass"].notna()]
    tc = float(np.average(ff["complete_pass"], weights=ff["w"])) if len(ff) else 0.65
    tyr = float(np.average(ff.loc[ff["complete_pass"] == 1, "yards_gained"], weights=ff.loc[ff["complete_pass"] == 1, "w"])) if (ff["complete_pass"] == 1).any() else 10.0
    catch, ypr, ypc = np.zeros(Pn), np.zeros(Pn), np.zeros(Pn)
    for i in ids:
        d = ff[ff["receiver_player_id"] == i]
        if len(d):
            w = d["w"].to_numpy()
            c = d["complete_pass"].to_numpy()
            catch[idx[i]] = (w * (c - tc)).sum() / ((w * tc * (1 - tc)).sum() + 30.0)
            dc_ = d[d["complete_pass"] == 1]
            if len(dc_):
                ypr[idx[i]] = (np.average(dc_["yards_gained"], weights=dc_["w"]) - tyr) * dc_["w"].sum() / (dc_["w"].sum() + 15.0)
    tr = float(np.average(car["yards_gained"], weights=car["w"])) if len(car) else 4.2
    for i in ids:
        d = car[car["rusher_player_id"] == i]
        nn, yy = d["w"].sum(), (d["w"] * d["yards_gained"]).sum()
        if scenario and i == scenario["star"] and nn < 30:
            hn, hy = _history_rush(i)
            nn, yy = nn + hn, yy + hy
        if nn > 0:
            ypc[idx[i]] = (yy / nn - tr) * nn / (nn + 40.0)
    mult = np.ones((S, Pn))
    meta = {}
    cshare, tshare = np.broadcast_to(cs, (S, 2, Pn)).copy(), np.broadcast_to(ts, (S, 2, Pn)).copy()
    if scenario:
        si = idx[scenario["star"]]
        ri = idx[scenario["rookie"]] if rookie_on else None
        rbs = [k for k, i in enumerate(ids) if pos[i] in ("RB", "FB")]
        others = [k for k in rbs if k not in (si, ri)]
        share_rookie = SCENARIO["price_of_rest"] if rookie_on else 0.0
        if fixed is None:
            u = rng.uniform(*SCENARIO["share"], S)
            m = np.clip(rng.normal(SCENARIO["mult_mean"], SCENARIO["mult_sd"], S), 0.7, 1.2)
        else:
            u, m = np.full(S, fixed[0]), np.full(S, fixed[1])
        for arr in (cshare, tshare):
            R = arr[:, :, rbs].sum(2)
            ob = arr[:, :, others] / np.maximum(arr[:, :, others].sum(2, keepdims=True), 1e-9) if others else None
            arr[:, :, si] = u[:, None] * R
            if rookie_on:
                arr[:, :, ri] = share_rookie * (1 - u)[:, None] * R
            if others:
                arr[:, :, others] = (1 - share_rookie) * (1 - u)[:, None, None] * R[:, :, None] * ob
        mult[:, si] = m
        meta = {"star": nm[scenario["star"]], "rookie": nm[scenario["rookie"]] if rookie_on else None, "rookie_name": pl["display_name"].get(scenario["rookie"]), "rookie_unavailable": not rookie_on}
    return {"names": [nm[i] for i in ids], "pos": [pos[i] for i in ids], "ids": ids, "qb": qbs, "tcum": np.cumsum(tshare, axis=2), "ccum": np.cumsum(cshare, axis=2), "catch": catch, "ypr": ypr, "ypc": ypc, "rush_mult": mult,
            "out": [pl["display_name"].get(i, i) for i in out_ids if i in (set(t["receiver_player_id"].dropna()) | set(t["rusher_player_id"].dropna()) | set(t["passer_player_id"].dropna()))], "scenario": meta}


# ---------------------------------------------------------------- run
def _dist(a: np.ndarray) -> dict:
    return {"mean": float(a.mean()), "p10": float(np.quantile(a, 0.1)), "median": float(np.quantile(a, 0.5)), "p90": float(np.quantile(a, 0.9))}


def run_game(gid: str, n: int = N_SIMS, scenario_on: bool = True, fixed=None, seed: int | None = None, kickoff_week: int | None = None) -> dict:
    g = pd.read_csv(RAW / "games.csv")
    r = g[g["game_id"] == gid].iloc[0]
    away, home, week = r["away_team"], r["home_team"], int(r["week"])
    P = snapfit.fit(week)
    p = snapfit.load(week)
    inj = pd.read_parquet(RAW / "injuries_2026.parquet")
    inj = inj[inj["week"] == inj["week"].max()] if "week" in inj else inj
    inj = inj.rename(columns={"gsis_id": "gsis_id"})
    rng = np.random.default_rng(int(hashlib.sha256(gid.encode()).hexdigest()[:8], 16) if seed is None else seed)
    ven = venue_effects(home, (int(r["away_rest"]), int(r["home_rest"])))
    sc = None
    if scenario_on and home == "SEA":
        pl, dc = _roster_info()
        look = lambda nm_: pl.index[pl["display_name"] == nm_][0]
        sc = {"star": look("Zach Charbonnet"), "rookie": look("Jadarian Price")}
    crowd = ven["multiplier"] if (home == ven["team"]) else 1.0
    pools = [build_pool(P, p, away, week, None, n, rng, inj), build_pool(P, p, home, week, sc if home == "SEA" else None, n, rng, inj, fixed)]
    sim = simulate(P, away, home, pools, n=n, seed=int(hashlib.sha256((gid + "s").encode()).hexdigest()[:8], 16) if seed is None else seed + 1, crowd_mult=crowd)
    return summarize(sim, pools, r, ven, crowd, n, week)


def summarize(sim: dict, pools: list, r, ven: dict, crowd: float, n: int, week: int) -> dict:
    sc = sim["score"]
    away, home = sim["teams"]
    margin = (sc[:, 1] - sc[:, 0]).astype(float)
    adj = margin + ven["home_margin"] * 0 + 0.0
    hfa = ven["home_margin"] if r["home_team"] == ven["team"] else ven["home_margin"]
    shift = hfa + ven["rest_points_to_home"]
    madj = margin + shift
    spread, total = float(r["spread_line"]), float(r["total_line"])
    tot = (sc[:, 0] + sc[:, 1]).astype(float)
    vf = ROOT / "docs" / "snapsim_validation.json"
    gap = 0.0
    if vf.exists():
        pt = json.loads(vf.read_text())["v1"]["points_per_team"]
        gap = float(pt["actual"] - pt["sim"])
    res = {"gid": r["game_id"], "away": away, "home": home, "week": week, "sims": n, "spread_home": spread, "total": total,
           "win": {home: float((madj > 0).mean()), away: float((madj < 0).mean())},
           "raw_win": {home: float((margin > 0).mean() + 0.5 * (margin == 0).mean()), away: float((margin < 0).mean() + 0.5 * (margin == 0).mean())},
           "cover": {home: float((madj > spread).mean()), away: float((madj < spread).mean())},
           "cover_raw": {home: float((margin > spread).mean()), away: float((margin < spread).mean()), "push": float((margin == spread).mean())},
           "ladder": {"spreads": [{"line": x, "home": float((madj > x).mean()), "away": float((madj < x).mean())} for x in sorted({spread - 1, spread - 0.5, spread, spread + 0.5, spread + 1})],
                      "totals": [{"line": x, "over": float((tot > x).mean()), "over_adjusted": float((tot + 2 * gap > x).mean())} for x in sorted({total - 1, total - 0.5, total, total + 0.5, total + 1})]},
           "scoring_gap_per_team": gap, "over_scoring_adjusted": float((tot + 2 * gap > total).mean()),
           "over": float((tot > total).mean()), "under": float((tot < total).mean()), "over_raw_push": float((tot == total).mean()),
           "score": {"home": _dist(sc[:, 1].astype(float)), "away": _dist(sc[:, 0].astype(float)), "margin": _dist(margin), "total": _dist(tot)},
           "adjustments": {"home_field_points": hfa, "rest_points_to_home": ven["rest_points_to_home"], "rest_beta_per_day": ven["rest_beta_per_day"], "rest_se": ven["rest_se"], "false_start_multiplier": crowd,
                           "false_start_rank": ven["rank_shrunk"], "false_start_rank_raw": ven["rank_raw"], "stadiums": ven["stadiums"], "visiting_false_start_rate": ven["false_start_raw_rate"], "league_rate": ven["league_rate"]},
           "team_stats": {}}
    for k, t in enumerate((away, home)):
        st = sim["stats"]
        res["team_stats"][t] = {m: float(st[m][:, k].mean()) for m in ("snaps", "dropbacks", "sacks", "penalties", "false_starts", "fourth_go", "tds", "fgs", "ints", "pass_att", "rush_att")}
    players = []
    for k, t in enumerate((away, home)):
        pool, a, q = pools[k], sim["acc"][k], sim["qb"][k]
        for j, nm in enumerate(pool["names"]):
            isqb = j == pool["qb"]
            row = {"team": t, "name": nm, "pos": pool["pos"][j]}
            dist = {"rec": a["rec"][:, j], "rec_yds": a["recyd"][:, j], "car": a["car"][:, j], "rush_yds": a["rushyd"][:, j], "tgt": a["tgt"][:, j]}
            if isqb:
                dist.update({"pass_yds": q["yds"], "comp": q["comp"], "att": q["att"], "pass_td": q["td"], "int": q["int"]})
            tdc = a["rectd"][:, j] + a["rushtd"][:, j] + (0 if not isqb else 0)
            row["anytime_td"] = float((tdc > 0).mean())
            row["stats"] = {k2: _dist(v) for k2, v in dist.items() if v.mean() > 0.01}
            row["_d"] = dist
            players.append(row)
    res["_players"] = players
    res["scenario"] = pools[1]["scenario"]
    res["out"] = {away: pools[0]["out"], home: pools[1]["out"]}
    return res


def scenarios(gid: str, n: int = 4000) -> dict:
    out = {}
    for name, fx in (("low", SCENARIO["low"]), ("high", SCENARIO["high"])):
        s = run_game(gid, n=n, fixed=fx, seed=7)
        if not s["scenario"].get("star"):
            return {}                      # no returning-starter question in this game
        out[name] = {"win": s["win"], "cover": s["cover"], "over": s["over"], "star": next((pl["stats"].get("rush_yds") for pl in s["_players"] if pl["name"] == s["scenario"].get("star")), None)}
    return out


# ---------------------------------------------------------------- leans: sim, matchup and game must agree
def matchup_ratios(p: pd.DataFrame, week: int) -> dict:
    """Opponent allowed per game to a position and stat, against the league, shrunk with 4 games of league average. Plus each team's 2026 pass and rush attempts per game."""
    pl = pd.read_parquet(RAW / "players.parquet", columns=["gsis_id", "position"]).drop_duplicates("gsis_id").set_index("gsis_id")["position"]
    q = p[(p["penalty"] != 1) & (p["qb_kneel"] != 1) & (p["qb_spike"] != 1)].copy()
    q["g"] = q["yr"].astype(str) + q["game_id"]
    games = q.groupby("defteam")["w"].apply(lambda s: s.groupby(q.loc[s.index, "g"]).first().sum())
    out = {}

    def add(key, df, val):
        tot = (df["w"] * val).groupby(df["defteam"]).sum()
        lg = tot.sum() / games.sum()
        for t in games.index:
            pg = tot.get(t, 0.0) / games[t]
            out[(t, key)] = float((pg * games[t] + lg * 4) / (games[t] + 4) / lg) if lg else 1.0
    att = q[(q["pass_attempt"] == 1)]
    add("pass_yds", att, att["yards_gained"].where(att["complete_pass"] == 1, 0))
    for grp, nm in (("WR", "WR"), ("TE", "TE"), ("RB", "RB")):
        a = att[att["receiver_player_id"].map(pl).map(lambda x: "RB" if x == "FB" else x) == grp]
        add(f"rec_yds_{nm}", a, a["yards_gained"].where(a["complete_pass"] == 1, 0))
        add(f"rec_{nm}", a, a["complete_pass"].fillna(0))
    rn = q[(q["rush_attempt"] == 1) & (q["qb_scramble"] != 1)]
    add("rush_yds", rn, rn["yards_gained"])
    vol = {}
    t26 = q[q["yr"] == snapfit.SEASON]
    ng = t26.groupby("posteam")["game_id"].nunique()
    for t in ng.index:
        d = t26[t26["posteam"] == t]
        vol[t] = {"pass": float((d["pass_attempt"] == 1).sum() / ng[t]), "rush": float(((d["rush_attempt"] == 1) & (d["qb_scramble"] != 1)).sum() / ng[t])}
    return {"allowed": out, "volume": vol}


def leans(res: dict, props: list[dict], mr: dict) -> dict:
    away, home = res["away"], res["home"]
    by = {(pl["team"], pl["name"]): pl for pl in res["_players"]}
    pos_of = {(pl["team"], pl["name"]): pl["pos"] for pl in res["_players"]}
    out, near = [], 0
    for pr in props:
        stat = STAT_ROWS.get(pr["stat"])
        if stat not in ("pass_yds", "rec", "rec_yds", "rush_yds") or pr.get("market_line") is None or pr.get("market_chance") is None:
            continue
        pl = by.get((pr["team"], pr["player"]))
        if pl is None or stat not in pl["_d"]:
            continue
        line = float(pr["market_line"])
        v = pl["_d"][stat]
        sim_p = float((v > line).mean() if line % 1 else (v >= line).mean())
        opp = away if pr["team"] == home else home
        pos = pos_of[(pr["team"], pr["player"])]
        key = stat if stat in ("pass_yds", "rush_yds") else f"{stat}_{'RB' if pos == 'FB' else pos}"
        m = mr["allowed"].get((opp, key))
        vol_key = "pass" if stat != "rush_yds" else "rush"
        base = mr["volume"].get(pr["team"], {}).get(vol_key)
        sv = res["team_stats"][pr["team"]]["pass_att" if vol_key == "pass" else "rush_att"]
        sig = lambda x, hi, lo: "over" if x >= hi else ("under" if x <= lo else None)
        s_sim = sig(sim_p - float(pr["market_chance"]), 0.05, -0.05)
        s_mat = sig(m, 1.05, 0.95) if m is not None else None
        s_game = sig(sv / base, 1.03, 0.97) if base else None
        row = {"player": pr["player"], "team": pr["team"], "stat": pr["stat"], "line": line, "market_chance": float(pr["market_chance"]), "sim_chance": sim_p, "edge": sim_p - float(pr["market_chance"]),
               "matchup_ratio": m, "volume_ratio": (sv / base) if base else None, "signals": {"sim": s_sim, "matchup": s_mat, "game": s_game}}
        if s_sim and s_sim == s_mat == s_game:
            row["side"] = s_sim
            out.append(row)
        elif s_sim:
            near += 1
            row["side"] = None
            out.append({**row, "lean": False})
    leans_ = [r for r in out if r.get("side")]
    others = [r for r in out if not r.get("side")]
    return {"leans": sorted(leans_, key=lambda r: -abs(r["edge"])), "sim_only": sorted(others, key=lambda r: -abs(r["edge"]))[:8], "props_checked": len(props)}


def full_run(gid: str) -> dict:
    from . import gamecenter_data as G
    g = pd.read_csv(RAW / "games.csv")
    r = g[g["game_id"] == gid].iloc[0]
    res = run_game(gid)
    res["scenario_runs"] = scenarios(gid)
    p = snapfit.load(int(r["week"]))
    detail = G.game_detail(gid) or {}
    res["leans"] = leans(res, detail.get("props") or [], matchup_ratios(p, int(r["week"])))
    res["players"] = [{k: v for k, v in pl.items() if k != "_d"} for pl in res.pop("_players") if pl["stats"]]
    res["created"] = dt.datetime.now(dt.timezone.utc).isoformat()
    res["rule_sha256"] = hashlib.sha256((ROOT / "docs" / "SNAPSIM_PREREG.md").read_bytes()).hexdigest()
    res["kickoff"] = f"{r['gameday']} {r['gametime']} ET"
    res["rest"] = {"away": int(r["away_rest"]), "home": int(r["home_rest"])}
    return res


def get(gid: str, refresh: bool = False) -> dict:
    """The write-once pre-kickoff record if one exists, else the cached run, else a fresh run."""
    froz = OUT / "frozen" / f"{gid}.json"
    if froz.exists():
        rec = json.loads(froz.read_text())
        ok = hashlib.sha256(json.dumps(rec["forecast"], sort_keys=True, separators=(",", ":")).encode()).hexdigest() == rec["sha256"]
        return {**rec["forecast"], "frozen": True, "frozen_ok": ok, "sha256": rec["sha256"]}
    path = OUT / f"{gid}.json"
    if path.exists() and not refresh:
        return {**json.loads(path.read_text()), "frozen": False}
    res = full_run(gid)
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, default=float))
    return {**res, "frozen": False}


def freeze(gid: str) -> dict:
    """Write-once, before kickoff. A second call returns the saved file and never rebuilds it."""
    path = OUT / "frozen" / f"{gid}.json"
    if path.exists():
        return get(gid)
    res = full_run(gid)
    body = json.dumps(res, sort_keys=True, separators=(",", ":"), default=float)
    body = json.dumps(json.loads(body), sort_keys=True, separators=(",", ":"))
    rec = {"sha256": hashlib.sha256(body.encode()).hexdigest(), "forecast": json.loads(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec))
    with (OUT / "ledger.jsonl").open("a") as fh:
        fh.write(json.dumps({"gid": gid, "sha256": rec["sha256"], "created": res["created"]}) + "\n")
    return get(gid)
