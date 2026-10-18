"""Vectorised play-by-play game simulator: N simulated games advance one play per step.

teams: list of two dicts (0 = home, 1 = away) with keys
  pass_off (logit offset), recv_cols / recv_cum, rush_cols / rush_cum, qb_col.
players: dict of arrays over all P player columns: w_recv, dist_recv (P,7), coff, w_rush, dist_rush (P,7).
"""
from __future__ import annotations

import numpy as np

from .models import b_down, b_sd, b_time, b_togo, b_yl, state_index

MAX_STEPS = 400
AIR_G = (np.arange(7) - 3) / 2.0           # ordered-bin tilt weights (gain direction)
YAC_G = (np.arange(6) - 2.5) / 1.7
RUSH_G = (np.arange(7) - 3) / 2.0


def _sig(x):
    return 1 / (1 + np.exp(-x))


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _cat(prob, u):
    c = np.cumsum(prob, axis=1)
    c /= c[:, -1:]
    return np.minimum((u[:, None] > c).sum(1), prob.shape[1] - 1)


def _tilt(prob, e, g):
    w = prob * np.exp(e[:, None] * g[None, :])
    return w / w.sum(1, keepdims=True)


def _vals(rng, vals, b):
    out = np.zeros(len(b))
    for k, v in enumerate(vals):
        m = b == k
        if m.any():
            out[m] = v[rng.integers(0, len(v), m.sum())] if len(v) else 0.0
    return out


def _choose_sim(rng, off, teams, shares, key):
    out = np.zeros(len(off), dtype=int)
    u = rng.random(len(off))
    for s in (0, 1):
        m = off == s
        if m.any():
            cum, cols = shares[(s, key)][m], teams[s][f"{key}_cols"]
            k = np.minimum((u[m][:, None] > cum / cum[:, -1:]).sum(1), len(cols) - 1)
            out[m] = cols[k]
    return out


def simulate(T: dict, teams: list, players: dict, n: int, e, rng, record=True, diag=None) -> dict:
    e = np.asarray(e, float)
    P = len(players["coff"])
    e_sim = e[None, :] + rng.normal(0, T.get("sigma_e", 0.0), (n, 2)) if T.get("sigma_e", 0) > 0 else np.repeat(e[None, :], n, 0)
    shares = {}
    for s_ in (0, 1):
        for key in ("recv", "rush"):
            base = np.diff(np.r_[0.0, teams[s_][f"{key}_cum"]])
            if T.get("kappa", 0) > 0 and len(base) > 1:
                shares[(s_, key)] = np.cumsum(rng.dirichlet(np.maximum(base, 1e-3) * T["kappa"], n), 1)
            else:
                shares[(s_, key)] = np.repeat(teams[s_][f"{key}_cum"][None, :], n, 0)
    poss = rng.integers(0, 2, n)
    first_recv = poss.copy()
    yl = T["kick_start"][rng.integers(0, len(T["kick_start"]), n)]
    down, togo, sec = np.ones(n, int), np.full(n, 10.0), np.full(n, 3600.0)
    score = np.zeros((n, 2))
    rows = np.arange(n)
    st = {k: np.zeros((n, P)) for k in ("rec_yds", "rec", "rush_yds", "pass_yds")} if record else None
    pass_off = np.array([teams[0]["pass_off"], teams[1]["pass_off"]])
    qb_col = np.array([teams[0]["qb_col"], teams[1]["qb_col"]])
    c0, c1 = T["fg_coef"]
    alive = np.ones(n, bool)
    rz = np.zeros(n, bool)
    for _ in range(MAX_STEPS):
        if not alive.any():
            break
        off = poss
        eo = e_sim[rows, off]
        sd = score[rows, off] - score[rows, 1 - off]
        sidx = state_index(down, togo, yl, sd, sec)
        u = rng.random((16, n))
        # 4th down decision
        f4 = ((b_togo(togo) * 7 + b_yl(yl)) * 7 + b_sd(sd)) * 4 + b_time(sec)
        dec = _cat(T["fourth"][f4], u[0])
        is4 = alive & (down == 4)
        punt, fg = is4 & (dec == 1), is4 & (dec == 2)
        play = alive & ~punt & ~fg
        pen = play & (u[14] < T["pen_rate"])
        pj = rng.integers(0, len(T["pen_gain"]), n)
        pg_, pfd = T["pen_gain"][pj], T["pen_fd"][pj]
        pg_ = np.where(pg_ > 0, np.minimum(pg_, np.maximum(yl / 2, 1)), np.maximum(pg_, -(100 - yl) / 2))   # half the distance
        play = play & ~pen
        isp = play & (u[1] < _sig(_logit(T["p_pass"][sidx]) + pass_off[off]))
        isr = play & ~isp
        sack = isp & (u[2] < _sig(_logit(T["p_sack"][sidx]) - eo))
        att = isp & ~sack
        # pass: receiver -> air yards -> outcome -> yac
        rc = _choose_sim(rng, off, teams, shares, "recv")
        wr = players["w_recv"][rc][:, None]
        airp = _tilt((1 - wr) * T["air"][sidx] + wr * players["dist_recv"][rc], eo, AIR_G)
        airb = _cat(airp, u[3])
        airv = _vals(rng, T["air_vals"], airb)
        lo = np.log(np.clip(T["outcome"][(airb * 7 + b_yl(yl)) * 3 + b_down(down)], 1e-9, 1))
        lo[:, 0] += eo + players["coff"][rc]
        lo[:, 2] -= eo
        outc = _cat(np.exp(lo), u[4])
        comp, intc = att & (outc == 0), att & (outc == 2)
        inc = att & (outc == 1)
        yacb = _cat(_tilt(T["yac"][airb * 7 + b_yl(yl)], eo, YAC_G), u[5])
        gp = airv + _vals(rng, T["yac_vals"], yacb)
        # run
        ru = _choose_sim(rng, off, teams, shares, "rush")
        wu = players["w_rush"][ru][:, None]
        rb = _cat(_tilt((1 - wu) * T["rush"][sidx] + wu * players["dist_rush"][ru], eo, RUSH_G), u[6])
        rv = _vals(rng, T["rush_vals"], rb)
        for y_ in np.unique(yl[alive & (yl <= 20)]).astype(int):
            mk = alive & (yl.astype(int) == y_)
            for arr, tgt in ((T["rz_rush"].get(y_), "r"), (T["rz_pass"].get(y_), "p")):
                if arr is not None and len(arr) >= 20:
                    v = arr[rng.integers(0, len(arr), mk.sum())]
                    if T.get("rz_boost", 0) > 0:
                        v2 = arr[rng.integers(0, len(arr), mk.sum())]
                        v = np.where(rng.random(mk.sum()) < T["rz_boost"], np.maximum(v, v2), v)
                    if tgt == "r":
                        rv[mk] = v
                    else:
                        gp[mk] = v
        sv = T["sack_vals"][rng.integers(0, len(T["sack_vals"]), n)]
        gain = np.where(pen, pg_, np.where(comp, gp, np.where(isr, rv, np.where(sack, sv, 0.0))))
        td = (comp | isr) & (gain >= yl)
        gain = np.where(td, yl, gain)
        fum = ~td & ((comp & (u[7] < T["fum_comp"])) | (isr & (u[7] < T["fum_run"])) | (sack & (u[7] < T["fum_sack"])))
        if record:
            m = comp
            np.add.at(st["rec_yds"], (rows[m], rc[m]), gain[m])
            np.add.at(st["rec"], (rows[m], rc[m]), 1.0)
            np.add.at(st["pass_yds"], (rows[m], qb_col[off[m]]), gain[m])
            m = isr
            np.add.at(st["rush_yds"], (rows[m], ru[m]), gain[m])
        score[rows[td], off[td]] += 6 + (u[8][td] < T["pat"])
        fgp = _sig(c0 + c1 * (yl + 17))
        fgm = fg & (u[9] < fgp)
        fgx = fg & ~fgm
        score[rows[fgm], off[fgm]] += 3
        if diag is not None:
            for k, v in (("plays", play | pen), ("pass", isp), ("run", isr), ("comp", comp), ("int", intc), ("fum", fum), ("td", td),
                         ("fga", fg), ("fgm", fgm), ("punt", punt), ("pen", pen), ("sack", sack), ("go4", is4 & play)):
                diag[k] = diag.get(k, 0) + int(v.sum())
            diag["yds"] = diag.get("yds", 0.0) + float(gain[play | pen].sum())
            new_rz = alive & ~rz & (yl <= 20)
            rz |= new_rz
            diag["rz_trips"] = diag.get("rz_trips", 0) + int(new_rz.sum())
            diag["rz_td"] = diag.get("rz_td", 0) + int((td & rz).sum())
        # next state
        nyl = np.clip(yl - gain, 1, 99)
        conv = (togo - gain) <= 0
        ndown = np.where(inc, down + 1, np.where(conv, 1, down + 1))
        ntogo = np.where(inc, togo, np.where(conv, np.minimum(10, nyl), togo - gain))
        pconv = pen & (pfd | conv)
        ndown = np.where(pen, np.where(pconv, 1, down), ndown)
        ntogo = np.where(pen, np.where(pconv, np.minimum(10, nyl), togo - gain), ntogo)
        nyl = np.where(inc, yl, nyl)
        downs = play & ~td & ~intc & ~fum & (ndown > 4)
        kick = td | fgm
        opp_yl = np.where(intc, np.where(yl - airv <= 0, 80, np.clip(100 - (yl - airv), 1, 99)), 100 - nyl)
        opp_yl = np.where(fgx, np.where(yl + 7 < 20, 80, np.clip(100 - (yl + 7), 1, 99)), opp_yl)
        ps = np.zeros(n)
        for k, v in enumerate(T["punt_start"]):
            mk = punt & (b_yl(yl) == k)
            if mk.any() and len(v):
                ps[mk] = v[rng.integers(0, len(v), mk.sum())]
        opp_yl = np.where(punt, ps, opp_yl)
        opp_yl = np.where(kick, T["kick_start"][rng.integers(0, len(T["kick_start"]), n)], opp_yl)
        change = kick | fgx | punt | intc | fum | downs
        yl = np.where(change, opp_yl, nyl)
        down = np.where(change, 1, ndown)
        togo = np.where(change, np.minimum(10, yl), ntogo)
        poss = np.where(change & alive, 1 - poss, poss)
        rz = rz & ~change
        # clock
        klass = np.where(inc | intc | pen, 0, np.where(comp | isr | sack, 1, 2))
        half = np.where(sec > 1800, sec - 1800, sec)
        q = np.clip(1 + (3600 - sec) // 900, 1, 4)
        hurry = np.isin(q, (2, 4)) & (half <= 120)
        dt = np.zeros(n)
        for (k, h), v in T["clock"].items():
            mk = alive & (klass == k) & (hurry == h)
            if mk.any() and len(v):
                dt[mk] = v[rng.integers(0, len(v), mk.sum())]
        dt = dt * T.get("clock_scale", 1.0)
        new_sec = np.where(alive, sec - np.maximum(dt, 1.0), sec)
        if diag is not None:
            for k in range(3):
                for h in (False, True):
                    mk = alive & (klass == k) & (hurry == h)
                    diag[f"t{k}{int(h)}"] = diag.get(f"t{k}{int(h)}", 0.0) + float(np.maximum(dt, 1.0)[mk].sum())
                    diag[f"n{k}{int(h)}"] = diag.get(f"n{k}{int(h)}", 0) + int(mk.sum())
        cross = alive & (sec > 1800) & (new_sec <= 1800)
        if cross.any():
            poss[cross] = 1 - first_recv[cross]
            yl[cross] = T["kick_start"][rng.integers(0, len(T["kick_start"]), cross.sum())]
            down[cross], togo[cross] = 1, 10.0
            new_sec[cross] = 1800.0
        sec = new_sec
        alive = sec > 0
    return {"points": score, "stats": st}


def calibrate_clock(T, n=3000, iters=3, seed=11):
    """Training-data structural calibration at neutral strength (e = 0):
    clock scale -> scrimmage plays per team; red-zone finishing boost -> points per team."""
    P = 4
    pl = {"w_recv": np.zeros(P), "dist_recv": np.full((P, 7), 1 / 7), "coff": np.zeros(P), "w_rush": np.zeros(P), "dist_rush": np.full((P, 7), 1 / 7)}
    tm = [{"pass_off": 0.0, "recv_cols": np.array([0]), "recv_cum": np.array([1.0]), "rush_cols": np.array([1]), "rush_cum": np.array([1.0]), "qb_col": 1},
          {"pass_off": 0.0, "recv_cols": np.array([2]), "recv_cum": np.array([1.0]), "rush_cols": np.array([3]), "rush_cum": np.array([1.0]), "qb_col": 3}]
    for _ in range(iters):
        d = {}
        simulate(T, tm, pl, n, [0, 0], np.random.default_rng(seed), record=False, diag=d)
        sim_plays = (d["pass"] + d["run"]) / n / 2
        T["clock_scale"] *= sim_plays / T["real_scrimmage_per_team"]
    lo, hi = 0.0, 1.0
    for _ in range(7):
        T["rz_boost"] = (lo + hi) / 2
        pts = simulate(T, tm, pl, n, [0, 0], np.random.default_rng(seed), record=False)["points"].mean()
        lo, hi = (T["rz_boost"], hi) if pts < T["real_points_per_team"] else (lo, T["rz_boost"])
    T["rz_boost"] = (lo + hi) / 2
    return T["clock_scale"], T["rz_boost"]


def calibrate(T, teams, players, targets, rng, n=2000, iters=6):
    """Per-offense efficiency scalars so mean simulated points match the market's implied team totals.
    Common random numbers (same seed each pass) keep the secant steps stable."""
    seed = int(rng.integers(0, 2**31))
    e = np.zeros(2)
    slope = np.array([10.0, 10.0])
    prev = None
    for _ in range(iters):
        pts = simulate(T, teams, players, n, e, np.random.default_rng(seed), record=False)["points"].mean(0)
        if prev is not None:
            de, dp = e - prev[0], pts - prev[1]
            ok = np.abs(de) > 1e-3
            slope[ok] = np.clip(dp[ok] / de[ok], 5.0, 30.0)
        prev = (e.copy(), pts)
        e = np.clip(e + (np.asarray(targets) - pts) / slope, -2.0, 2.0)
    return e, pts
