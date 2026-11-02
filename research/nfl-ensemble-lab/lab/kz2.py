"""King of the End Zone v2: chance of owning the longest touchdown of a game, from play-by-play history only (no simulated-game inputs).

Pieces (all fixed in docs/KINGZONE_PREREG.md before any test season was scored):
  fit       Generalized Pareto tail of each player's gains beyond U yards, with partial pooling position group > role > player, in PyMC. A touchdown is a
            censored gain (the play stopped at the goal line), so the tail is fit with censoring. Exposure is touches that start more than U yards out.
  environ   Each team's expected offensive touchdowns from its own and its opponent's recent touchdown record, shrunk to the league.
  drives    A play-by-play drive simulation (field position, downs, carries and targets by trailing share, body of gains from league history, tail from
            the fit, turnovers), with the number of drives scaled so the team's simulated touchdowns match its expected touchdowns.
  winner    Longest touchdown among all touchdowns in the game, offense and defense or special teams; ties split evenly.
Everything is as of the start of the game's week (history strictly before it). Local files only, read-only, deterministic given the seed.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from .config import RAW_DIR
from .ingest import normalize_team

ROOT = Path(__file__).resolve().parents[1]
U = 15                      # explosive threshold, yards
FIRST_PBP = 2016
WINDOW_SEASONS = 3          # seasons of history behind a tail fit
ROSTER_GAMES = 6            # team games behind a player's touch share
ACTIVE_GAMES = 3            # a player must have touched the ball in one of the last 3 team games to be on the roster
OTHER_SHARE = 0.05          # touches by players not on the roster
BASE_DRIVES = 11.0
P_GO = 0.15                 # chance a fourth down is played on rather than ending the drive
ENV_PRIOR = 6.0             # games of league-average touchdowns added to a team's record
PASS_PRIOR = 100.0          # plays of league pass rate added to a team's record
DEF_PRIOR = 6.0             # pseudo-events behind the opponent explosive-play ratio
DEF_GAMES = 7
DEF_CLIP = (0.7, 1.4)
FLOOR = 0.002
GROUPS = ["R-QB", "R-RB", "R-WR", "T-RB", "T-WR", "T-TE"]
G_IDX = {g: i for i, g in enumerate(GROUPS)}
COLS = ["game_id", "season", "week", "season_type", "home_team", "away_team", "posteam", "defteam", "play_type", "yardline_100", "rusher_player_id", "receiver_player_id",
        "rush_touchdown", "pass_touchdown", "touchdown", "td_team", "td_player_id", "two_point_attempt", "qb_kneel", "rushing_yards", "receiving_yards", "complete_pass",
        "return_yards", "fumble_recovery_1_yards", "fixed_drive", "interception", "fumble_lost"]
_C: dict = {}


# --------------------------------------------------------------------------- data

def _stamp() -> tuple:
    p = RAW_DIR / f"play_by_play_{D.SEASON}.parquet"
    return (p.stat().st_mtime_ns,) if p.exists() else ()


def load() -> dict:
    """All regular-season plays since 2016 and the touch table (one row per carry or target)."""
    key = _stamp()
    if _C.get("key") == key:
        return _C
    parts = [pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=COLS) for s in range(FIRST_PBP, D.SEASON + 1) if (RAW_DIR / f"play_by_play_{s}.parquet").exists()]
    p = pd.concat(parts, ignore_index=True)
    p = p[p["season_type"] == "REG"].copy()
    for c in ("posteam", "defteam", "td_team", "home_team", "away_team"):
        p[c] = p[c].map(lambda v: normalize_team(v) if isinstance(v, str) else v)
    p["order"] = p["season"] * 100 + p["week"]
    pos = _positions()
    no2 = p["two_point_attempt"].fillna(0) != 1
    rush = p[(p["play_type"] == "run") & p["rusher_player_id"].notna() & no2 & (p["qb_kneel"].fillna(0) != 1) & p["yardline_100"].notna()]
    tgt = p[(p["play_type"] == "pass") & p["receiver_player_id"].notna() & no2 & p["yardline_100"].notna()]
    r = pd.DataFrame({"order": rush["order"], "season": rush["season"], "week": rush["week"], "game_id": rush["game_id"], "team": rush["posteam"], "opp": rush["defteam"],
                      "pid": rush["rusher_player_id"], "kind": 0, "yl": rush["yardline_100"], "td": (rush["rush_touchdown"] == 1).astype(int),
                      "gain": rush["rushing_yards"].fillna(0.0)})
    t = pd.DataFrame({"order": tgt["order"], "season": tgt["season"], "week": tgt["week"], "game_id": tgt["game_id"], "team": tgt["posteam"], "opp": tgt["defteam"],
                      "pid": tgt["receiver_player_id"], "kind": 1, "yl": tgt["yardline_100"], "td": (tgt["pass_touchdown"] == 1).astype(int),
                      "gain": np.where(tgt["complete_pass"] == 1, tgt["receiving_yards"].fillna(0.0), 0.0)})
    x = pd.concat([r, t], ignore_index=True)
    x["gain"] = np.minimum(x["gain"], x["yl"])
    pp = x["pid"].map(pos).fillna("OTHER")
    x["pg"] = np.where(x["kind"] == 0, np.where(pp.isin(["QB", "RB", "WR", "TE"]), pp, "RB"), np.where(pp.isin(["RB", "WR", "TE"]), pp, "WR"))
    x["pg"] = np.where((x["kind"] == 0) & (x["pg"] == "TE"), "WR", x["pg"])
    x["g"] = [G_IDX[("R-" if k == 0 else "T-") + g] for k, g in zip(x["kind"], x["pg"])]
    x["risk"] = x["yl"] > U
    x["exc"] = x["risk"] & (x["gain"] > U)
    _C.clear()
    _C.update(key=key, plays=p, touches=x.sort_values("order", kind="stable").reset_index(drop=True))
    return _C


def _positions() -> dict:
    from . import usage as Us
    return Us.positions()


def names() -> dict:
    if "names" not in _C:
        n = pd.read_parquet(RAW_DIR / "players.parquet", columns=["gsis_id", "display_name"]).dropna()
        _C["names"] = dict(zip(n["gsis_id"], n["display_name"]))
    return _C["names"]


def _cut(season: int, week: int) -> int:
    return season * 100 + week


# --------------------------------------------------------------------------- roles and tail fit

def _roles(t: pd.DataFrame) -> pd.DataFrame:
    """Role of each (player, kind) in the window: his average rank by touches within his team and position group in the games he played, capped at 3."""
    g = t.groupby(["game_id", "team", "kind", "g", "pid"]).size().rename("c").reset_index()
    g["rk"] = g.groupby(["game_id", "team", "kind", "g"])["c"].rank(ascending=False, method="first")
    m = g.groupby(["pid", "kind"]).agg(g=("g", lambda s: s.mode().iloc[0]), rk=("rk", "mean")).reset_index()
    m["r"] = np.clip(np.rint(m["rk"]), 1, 3).astype(int) - 1
    return m[["pid", "kind", "g", "r"]]


def window(season: int, week: int) -> pd.DataFrame:
    t = load()["touches"]
    lo, hi = _cut(season - WINDOW_SEASONS + 1, 1), _cut(season, week)
    return t[(t["order"] >= lo) & (t["order"] < hi)]


def fit_tail(season: int, week: int, draws: int = 400, tune: int = 600, seed: int = 11, min_risk: int = 10) -> dict:
    """PyMC fit of the explosive-play rate and Pareto tail for every player with at least `min_risk` at-risk touches, plus defaults for each group and role."""
    import pymc as pm
    import pytensor.tensor as pt

    w = window(season, week)
    roles = _roles(w)
    rk = w[w["risk"]].groupby(["pid", "kind"]).agg(n=("exc", "size"), k=("exc", "sum")).reset_index().merge(roles, on=["pid", "kind"])
    rk = rk[rk["n"] >= min_risk].reset_index(drop=True)
    rk["ui"] = np.arange(len(rk))
    ex = w[w["exc"]].merge(rk[["pid", "kind", "ui"]], on=["pid", "kind"])
    x = (ex["gain"] - U).to_numpy(float).clip(0.05, None)
    cens = (ex["td"] == 1).to_numpy()
    ui = ex["ui"].to_numpy()
    g, r, n, k = rk["g"].to_numpy(), rk["r"].to_numpy(), rk["n"].to_numpy(), rk["k"].to_numpy()
    nU, G, R = len(rk), len(GROUPS), 3
    with pm.Model():
        mu_g = pm.Normal("mu_g", -2.3, 1.0, shape=G)
        sd_r, sd_p = pm.HalfNormal("sd_r", 0.5), pm.HalfNormal("sd_p", 0.5)
        zr, zp = pm.Normal("zr", 0, 1, shape=(G, R)), pm.Normal("zp", 0, 1, shape=nU)
        eta = mu_g[g] + sd_r * zr[g, r] + sd_p * zp
        pm.Binomial("k", n=n, p=pm.math.sigmoid(eta), observed=k)
        ls_g = pm.Normal("ls_g", np.log(10.0), 0.5, shape=G)
        sdsr, sdsp = pm.HalfNormal("sdsr", 0.3), pm.HalfNormal("sdsp", 0.3)
        zsr, zsp = pm.Normal("zsr", 0, 1, shape=(G, R)), pm.Normal("zsp", 0, 1, shape=nU)
        logsig = ls_g[g] + sdsr * zsr[g, r] + sdsp * zsp
        xi_g = pm.Normal("xi_g", 0.1, 0.2, shape=G)
        sdx = pm.HalfNormal("sdx", 0.1)
        zxr = pm.Normal("zxr", 0, 1, shape=(G, R))
        xi_gr = xi_g[:, None] + sdx * zxr
        xs = pt.switch(pt.abs(xi_gr[g, r][ui]) < 1e-3, 1e-3, xi_gr[g, r][ui])
        su = pt.exp(logsig[ui])
        arg = 1 + xs * x / su
        logS = -(1 / xs) * pt.log(pt.maximum(arg, 1e-9))
        logf = -pt.log(su) - (1 + 1 / xs) * pt.log(pt.maximum(arg, 1e-9))
        ll = pt.switch(cens, logS, logf)
        pm.Potential("tail", pt.switch(arg > 0, ll, -1e6).sum())
        pm.Deterministic("zeta", pm.math.sigmoid(eta))
        pm.Deterministic("sigma", pt.exp(logsig))
        pm.Deterministic("zeta_gr", pm.math.sigmoid(mu_g[:, None] + sd_r * zr))
        pm.Deterministic("sigma_gr", pt.exp(ls_g[:, None] + sdsr * zsr))
        pm.Deterministic("xi_gr_d", xi_gr)
        t0 = time.time()
        idata = pm.sample(draws=draws, tune=tune, chains=2, cores=2, target_accept=0.9, random_seed=seed, progressbar=False, compute_convergence_checks=False)
        secs = time.time() - t0
    post = idata.posterior
    mean = lambda v: post[v].mean(("chain", "draw")).to_numpy()
    try:
        import arviz as az
        rh = az.rhat(idata, var_names=["mu_g", "ls_g", "xi_g", "sd_r", "sd_p", "sdsr", "sdsp", "sdx"])
        rh = rh.to_dataset() if hasattr(rh, "to_dataset") else rh
        rhat = float(max(float(rh[v].max()) for v in rh.data_vars))
    except Exception:
        rhat = None
    xi_unit = mean("xi_gr_d")[g, r]
    units = {(p, int(kd)): (float(a), float(b), float(c)) for p, kd, a, b, c in zip(rk["pid"], rk["kind"], mean("zeta"), mean("sigma"), xi_unit)}
    return {"season": season, "week": week, "units": units, "default": {"zeta": mean("zeta_gr"), "sigma": mean("sigma_gr"), "xi": mean("xi_gr_d")},
            "n_units": nU, "n_exceed": int(len(ex)), "seconds": secs, "rhat_max": rhat, "draws": draws, "tune": tune,
            "league_zeta": float(rk["k"].sum() / rk["n"].sum())}


# --------------------------------------------------------------------------- league pieces for the simulation

def league(season: int, week: int) -> dict:
    """Bodies of gains, drive starts, turnover rate and return touchdowns from the window before (season, week)."""
    key = ("league", season, week)
    if key in _C:
        return _C[key]
    w = window(season, week)
    p = load()["plays"]
    pw = p[(p["order"] >= _cut(season - WINDOW_SEASONS + 1, 1)) & (p["order"] < _cut(season, week))]
    bodies: dict = {}
    far = w[w["yl"] > U]
    for (kd, g), d in far[~far["exc"]].groupby(["kind", "g"]):
        bodies[(kd, g, "far")] = d["gain"].to_numpy(float)
    near = w[w["yl"] <= U]
    for (kd, g, y), d in near.groupby(["kind", "g", "yl"]):
        if len(d) >= 30:
            bodies[(kd, g, int(y))] = d["gain"].to_numpy(float)
    for (kd, y), d in near.groupby(["kind", "yl"]):
        bodies[(kd, -1, int(y))] = d["gain"].to_numpy(float)
    for kd, d in far[~far["exc"]].groupby("kind"):
        bodies[(kd, -1, "far")] = d["gain"].to_numpy(float)
    first = pw[pw["play_type"].isin(["run", "pass"]) & pw["fixed_drive"].notna()].groupby(["game_id", "posteam", "fixed_drive"])["yardline_100"].first().to_numpy(float)
    plays = pw[pw["play_type"].isin(["run", "pass"])]
    turn = float(((plays["interception"] == 1) | (plays["fumble_lost"] == 1)).mean())
    d = pw[(pw["touchdown"] == 1) & pw["td_team"].notna() & (pw["td_team"] != pw["posteam"])]
    ln = d["return_yards"].where(d["return_yards"] > 0, d["fumble_recovery_1_yards"]).fillna(d["return_yards"]).abs().clip(1, 99).dropna().to_numpy(float)
    ngames = max(len(pw[["game_id"]].drop_duplicates()) * 2, 1)
    off = w.groupby(["game_id", "team"])["td"].sum()
    tdg = pw[(pw["play_type"].isin(["run", "pass"]))].assign(td=lambda z: ((z["rush_touchdown"] == 1) | (z["pass_touchdown"] == 1)).astype(int)).groupby(["game_id", "posteam"])["td"].sum()
    out = {"bodies": bodies, "starts": first[~np.isnan(first)], "turn": turn, "ret_rate": len(ln) / ngames, "ret_len": ln if len(ln) else np.array([30.0]),
           "mu_td": float(tdg.mean()) if len(tdg) else 2.2, "pass_rate": float((plays["play_type"] == "pass").mean()), "td_by_gt": tdg}
    _C[key] = out
    return out


def _body(L: dict, kind: int, g: int, y: np.ndarray, rng) -> np.ndarray:
    """Gains for plays that do not go past U yards: from the exact yard line when near the goal, else from the far-field body."""
    out = np.zeros(len(y))
    far = y > U
    if far.any():
        arr = L["bodies"].get((kind, g, "far"))
        arr = arr if arr is not None and len(arr) > 50 else L["bodies"][(kind, -1, "far")]
        out[far] = arr[rng.integers(0, len(arr), int(far.sum()))]
    for yy in np.unique(y[~far]):
        m = (y == yy) & ~far
        arr = L["bodies"].get((kind, g, int(yy)))
        arr = arr if arr is not None else L["bodies"].get((kind, -1, int(yy)), np.array([0.0]))
        out[m] = arr[rng.integers(0, len(arr), int(m.sum()))]
    return out


# --------------------------------------------------------------------------- team inputs

def team_inputs(season: int, week: int, team: str, opp: str, fit: dict, L: dict, out_pids: set | None = None) -> dict:
    """Roster, shares, pass rate and expected touchdowns for one team as of the start of the week."""
    t = load()["touches"]
    cut = _cut(season, week)
    past = t[(t["order"] < cut) & (t["order"] >= _cut(season - 1, 1))]
    tg = past[past["team"] == team]
    games = tg[["order", "game_id"]].drop_duplicates().sort_values("order")["game_id"].tolist()
    last = tg[tg["game_id"].isin(games[-ROSTER_GAMES:])]
    recent = set(tg[tg["game_id"].isin(games[-ACTIVE_GAMES:])]["pid"])
    if out_pids:
        recent -= out_pids
    w = window(season, week)
    roles = _roles(w[w["team"] == team]).set_index(["pid", "kind"]) if len(w[w["team"] == team]) else pd.DataFrame()
    pg_of = tg.drop_duplicates(["pid", "kind"]).set_index(["pid", "kind"])["g"]
    units = []
    share = {0: {}, 1: {}}
    for kd in (0, 1):
        c = last[(last["kind"] == kd) & last["pid"].isin(recent)].groupby("pid").size()
        tot = float(c.sum())
        if tot <= 0:
            continue
        for pid, v in c.items():
            share[kd][pid] = (1 - OTHER_SHARE) * v / tot
    pids = sorted(set(share[0]) | set(share[1]))
    opp_f = {kd: _opp_factor(season, week, opp, kd) for kd in (0, 1)}
    for pid in pids:
        row = {"pid": pid}
        for kd in (0, 1):
            if pid not in share[kd]:
                continue
            key = (pid, kd)
            g = int(pg_of.get(key, G_IDX["R-RB"] if kd == 0 else G_IDX["T-WR"])) if key in pg_of.index else (G_IDX["R-RB"] if kd == 0 else G_IDX["T-WR"])
            r = int(roles.loc[key, "r"]) if len(roles) and key in roles.index else 2
            if key in fit["units"]:
                z, s, xi = fit["units"][key]
            else:
                z, s, xi = float(fit["default"]["zeta"][g, r]), float(fit["default"]["sigma"][g, r]), float(fit["default"]["xi"][g, r])
            row[kd] = {"share": share[kd][pid], "g": g, "zeta": min(0.6, z * opp_f[kd]), "sigma": s, "xi": xi}
        units.append(row)
    # the unlisted pool: league-average receiver and back
    oth = {kd: {"share": OTHER_SHARE, "g": G_IDX["R-RB" if kd == 0 else "T-WR"], "zeta": float(fit["league_zeta"]), "sigma": float(np.exp(np.log(10.0))), "xi": 0.1} for kd in (0, 1)}
    units.append({"pid": f"OTHER:{team}", 0: oth[0], 1: oth[1]})
    gm = t[(t["team"] == team) & (t["order"] < cut) & (t["order"] >= _cut(season - 1, 1))]
    gids = gm[["order", "game_id"]].drop_duplicates().sort_values("order")["game_id"].tolist()[-8:]
    tds = float(gm[gm["game_id"].isin(gids)]["td"].sum())
    allowed = t[(t["opp"] == team) & (t["order"] < cut) & (t["order"] >= _cut(season - 1, 1))]
    agids = allowed[["order", "game_id"]].drop_duplicates().sort_values("order")["game_id"].tolist()[-8:]
    atds = float(allowed[allowed["game_id"].isin(agids)]["td"].sum())
    mu = L["mu_td"]
    gm_o = t[(t["team"] == opp) & (t["order"] < cut) & (t["order"] >= _cut(season - 1, 1))]
    ogids = gm_o[["order", "game_id"]].drop_duplicates().sort_values("order")["game_id"].tolist()[-8:]
    oall = t[(t["opp"] == opp) & (t["order"] < cut) & (t["order"] >= _cut(season - 1, 1))]
    oagids = oall[["order", "game_id"]].drop_duplicates().sort_values("order")["game_id"].tolist()[-8:]
    r_off = (tds + ENV_PRIOR * mu) / ((len(gids) + ENV_PRIOR) * mu)
    r_def = (float(oall[oall["game_id"].isin(oagids)]["td"].sum()) + ENV_PRIOR * mu) / ((len(oagids) + ENV_PRIOR) * mu)
    lam = mu * r_off * r_def
    nt = (last["kind"] == 1).sum()
    nr = (last["kind"] == 0).sum()
    pr = (nt + PASS_PRIOR * L["pass_rate"]) / (nt + nr + PASS_PRIOR)
    return {"team": team, "units": units, "pass_rate": float(pr), "lam": float(lam), "games_seen": len(games)}


def _opp_factor(season: int, week: int, opp: str, kind: int) -> float:
    """The defense's explosive-play rate allowed per at-risk touch over its last games, over the league's, shrunk."""
    t = load()["touches"]
    cut = _cut(season, week)
    d = t[(t["opp"] == opp) & (t["order"] < cut) & (t["order"] >= _cut(season - 1, 1)) & (t["kind"] == kind) & t["risk"]]
    gids = d[["order", "game_id"]].drop_duplicates().sort_values("order")["game_id"].tolist()[-DEF_GAMES:]
    d = d[d["game_id"].isin(gids)]
    key = ("lg_exc", season, week, kind)
    if key not in _C:
        w = window(season, week)
        w = w[(w["kind"] == kind) & w["risk"]]
        _C[key] = float(w["exc"].mean())
    p = _C[key]
    return float(np.clip((d["exc"].sum() + DEF_PRIOR) / (len(d) * p + DEF_PRIOR), *DEF_CLIP))


# --------------------------------------------------------------------------- the drive simulation

def _gpd(u: np.ndarray, sigma: float, xi: float) -> np.ndarray:
    return sigma * ((1 - u) ** (-xi) - 1) / xi if abs(xi) > 1e-6 else -sigma * np.log(1 - u)


def sim_team(rng, N: int, team: dict, L: dict, n_drives: float) -> tuple[np.ndarray, np.ndarray]:
    """best[N, P]: the longest touchdown by each unit in each simulated game (0 if none); cnt[N, P]: touchdowns by each unit."""
    units = team["units"]
    P = len(units)
    best = np.zeros((N, P), np.int16)
    cnt = np.zeros((N, P), np.int8)
    lists = {}
    for kd in (0, 1):
        ids = [i for i, u in enumerate(units) if kd in u]
        sh = np.array([units[i][kd]["share"] for i in ids], float)
        lists[kd] = (ids, np.cumsum(sh / sh.sum()))
    nd = int(np.floor(n_drives)) + (rng.random(N) < (n_drives - np.floor(n_drives))).astype(int)
    for d in range(int(nd.max())):
        alive = nd > d
        y = rng.choice(L["starts"], N).clip(1, 99)
        down = np.ones(N, int)
        togo = np.minimum(10.0, y)
        for _ in range(30):
            idx = np.flatnonzero(alive)
            if idx.size == 0:
                break
            fourth = down[idx] == 4
            if fourth.any():
                stop = fourth & (rng.random(idx.size) > P_GO)
                alive[idx[stop]] = False
                idx = np.flatnonzero(alive)
                if idx.size == 0:
                    break
            m = idx.size
            kind = (rng.random(m) < team["pass_rate"]).astype(int)
            yy = y[idx]
            gain = np.zeros(m)
            who = np.zeros(m, int)
            for kd in (0, 1):
                sel = np.flatnonzero(kind == kd)
                if sel.size == 0:
                    continue
                ids, cum = lists[kd]
                j = np.minimum(np.searchsorted(cum, rng.random(sel.size)), len(ids) - 1)
                who[sel] = np.array(ids)[j]
                for jj in np.unique(j):
                    mm = sel[j == jj]
                    par = units[ids[jj]][kd]
                    ys = yy[mm]
                    gg = _body(L, kd, par["g"], ys, rng)
                    farm = ys > U
                    if farm.any():
                        boom = farm & (rng.random(mm.size) < par["zeta"])
                        if boom.any():
                            gg[boom] = U + _gpd(rng.random(int(boom.sum())), par["sigma"], par["xi"])
                    gain[mm] = gg
            td = gain >= yy
            if td.any():
                ti = idx[td]
                np.maximum.at(best, (ti, who[td]), yy[td].astype(np.int16))
                np.add.at(cnt, (ti, who[td]), 1)
                alive[ti] = False
            keep = ~td
            turn = keep & (rng.random(m) < L["turn"])
            alive[idx[turn]] = False
            go = keep & ~turn
            gi = idx[go]
            newy = np.clip(yy[go] - gain[go], 1, 99)
            first = gain[go] >= togo[gi]
            y[gi] = newy
            togo[gi] = np.where(first, np.minimum(10.0, newy), togo[gi] - gain[go])
            down[gi] = np.where(first, 1, down[gi] + 1)
    return best, cnt


def predict(season: int, week: int, home: str, away: str, fit: dict, n: int = 6000, seed: int = 7, out_pids: set | None = None) -> dict:
    """Probabilities for one game as of the start of its week: per roster player the chance of the longest touchdown, any touchdown, 2+ and the field."""
    L = league(season, week)
    rng = np.random.default_rng(seed)
    teams = [team_inputs(season, week, home, away, fit, L, out_pids), team_inputs(season, week, away, home, fit, L, out_pids)]
    sims = []
    for tm in teams:
        pil_b, pil_c = sim_team(rng, 1200, tm, L, BASE_DRIVES)
        mean = max(pil_c.sum(axis=1).mean(), 0.2)
        n_eff = float(np.clip(BASE_DRIVES * tm["lam"] / mean, 4.0, 22.0))
        b, c = sim_team(rng, n, tm, L, n_eff)
        sims.append((b, c, n_eff, mean))
    # defense and special-teams touchdowns, per team
    rets = []
    for _ in teams:
        k = rng.poisson(L["ret_rate"], n)
        lens = np.where(k > 0, np.max(rng.choice(L["ret_len"], (n, 3)) * (np.arange(3)[None, :] < k[:, None]), axis=1), 0)
        rets.append(lens.astype(np.int16))
    allbest = np.concatenate([s[0] for s in sims] + [r[:, None] for r in rets], axis=1)
    top = allbest.max(axis=1)
    eq = (allbest == top[:, None]) & (top[:, None] > 0)
    w = eq / np.maximum(eq.sum(axis=1, keepdims=True), 1)
    rows, col = [], 0
    for tm, (b, c, n_eff, mean) in zip(teams, sims):
        for i, u in enumerate(tm["units"]):
            rows.append({"pid": u["pid"], "team": tm["team"], "chance": float(w[:, col + i].mean()), "anytime": float((c[:, i] >= 1).mean()), "two_plus": float((c[:, i] >= 2).mean()),
                         "exp_td": float(c[:, i].mean()), "win_two_plus": float((w[:, col + i] * (c[:, i] >= 2)).sum() / max((c[:, i] >= 2).sum(), 1)),
                         "p40": float((b[:, i] >= 40).mean()), "p60": float((b[:, i] >= 60).mean()), "share": {kd: u[kd]["share"] for kd in (0, 1) if kd in u}})
        col += len(tm["units"])
    field = float(w[:, col:].sum(axis=1).mean()) + sum(r["chance"] for r in rows if str(r["pid"]).startswith("OTHER:"))
    rows = [r for r in rows if not str(r["pid"]).startswith("OTHER:")]
    rows.sort(key=lambda r: -r["chance"])
    return {"rows": rows, "field": field, "none": float((top == 0).mean()), "teams": [{"team": tm["team"], "lam": tm["lam"], "pass_rate": tm["pass_rate"], "drives": s[2]} for tm, s in zip(teams, sims)],
            "expected_longest": float(top.mean())}


# --------------------------------------------------------------------------- truth and baselines

def _all_winners() -> dict:
    if "win" in _C:
        return _C["win"]
    p = load()["plays"]
    g = p[p["touchdown"] == 1]
    off = g[(g["td_team"] == g["posteam"]) & g["play_type"].isin(["run", "pass"]) & g["td_player_id"].notna()]
    dfn = g[(g["td_team"] != g["posteam"]) & g["td_team"].notna()]
    dl = dfn["return_yards"].where(dfn["return_yards"] > 0, dfn["fumble_recovery_1_yards"]).fillna(dfn["return_yards"]).abs()
    best_d = dl.groupby(dfn["game_id"]).max().to_dict()
    out = {}
    for gid, d in off.groupby("game_id"):
        top = float(d["yardline_100"].max())
        out[gid] = (top, list(dict.fromkeys(str(x) for x in d.loc[d["yardline_100"] == top, "td_player_id"])))
    for gid in set(best_d) | set(out):
        bo, ids = out.get(gid, (0.0, []))
        bd = float(best_d.get(gid, 0.0))
        top = max(bo, bd)
        out[gid] = (top, (ids if bo == top else []) + (["FIELD"] if bd == top and bd > 0 else []))
    _C["win"] = out
    return out


def actual_winners(gid: str) -> dict | None:
    """Real longest touchdown(s) of a finished game: scorers' ids (offense) or 'FIELD' (defense or special teams), and the length."""
    w = _all_winners().get(gid)
    return None if not w or w[0] <= 0 else {"entities": w[1], "length": w[0]}


def score_entity(rows: list[dict], field: float, ents: list[str]) -> float:
    """Probability the model gave the real winner (average over tied winners); winners not on the roster, and defense or special teams, score as the field."""
    byp = {r["pid"]: r["chance"] for r in rows}
    return float(np.mean([byp.get(e, field) if e != "FIELD" else field for e in ents]))


def baseline_split(season: int, week: int, teams: list[str], field0: float) -> dict:
    """Plain expected-touchdown split: each roster player's weight is his touchdown rate over the last 8 team games (shrunk), shares scaled to 1 - field0."""
    t = load()["touches"]
    cut = _cut(season, week)
    w, tot = {}, 0.0
    for tm in teams:
        d = t[(t["team"] == tm) & (t["order"] < cut) & (t["order"] >= _cut(season - 1, 1))]
        gids = d[["order", "game_id"]].drop_duplicates().sort_values("order")["game_id"].tolist()
        recent = set(d[d["game_id"].isin(gids[-ACTIVE_GAMES:])]["pid"])
        d8 = d[d["game_id"].isin(gids[-8:])]
        for pid, v in d8[d8["pid"].isin(recent)].groupby("pid")["td"].sum().items():
            w[pid] = (v + 0.3) / (8 + 6)
            tot += w[pid]
    return {p: (1 - field0) * v / tot for p, v in w.items()}, field0


def baseline_touch(season: int, week: int, teams: list[str], field0: float) -> dict:
    t = load()["touches"]
    cut = _cut(season, week)
    w, tot = {}, 0.0
    for tm in teams:
        d = t[(t["team"] == tm) & (t["order"] < cut) & (t["order"] >= _cut(season - 1, 1))]
        gids = d[["order", "game_id"]].drop_duplicates().sort_values("order")["game_id"].tolist()
        recent = set(d[d["game_id"].isin(gids[-ACTIVE_GAMES:])]["pid"])
        d6 = d[d["game_id"].isin(gids[-6:])]
        for pid, v in d6[d6["pid"].isin(recent)].groupby("pid").size().items():
            w[pid] = float(v)
            tot += float(v)
    return {p: (1 - field0) * v / tot for p, v in w.items()}, field0


def field_rate(season: int, week: int) -> float:
    """Share of games before this week whose longest touchdown was by defense, special teams or a player the roster would not hold (history, 3 seasons)."""
    key = ("field0", season, week)
    if key in _C:
        return _C[key]
    p = load()["plays"]
    gids = p[(p["order"] >= _cut(season - WINDOW_SEASONS + 1, 1)) & (p["order"] < _cut(season, week))]["game_id"].unique()
    hits = [actual_winners(g) for g in gids]
    v = float(np.mean([("FIELD" in h["entities"]) for h in hits if h])) if hits else 0.15
    _C[key] = max(v, 0.05)
    return _C[key]
