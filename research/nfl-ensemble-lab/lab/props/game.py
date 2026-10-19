"""Per-game simulator inputs, baseline B and quantile scoring, shared by the v2 tuning run and the 2026 weekly archive.
Mirrors the per-game construction in evaluate.run_season (v1's frozen 2023-25 look), which is left untouched."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import players as PL

LEVELS = np.arange(1, 100) / 100.0
QCOLS = [f"q{k:02d}" for k in range(1, 100)]
STATS = ("pass_yds", "rush_yds", "rec_yds", "rec")


def build(a, avail: dict, team_hist: dict, week: int, qbs: dict, sides):
    """avail[team] = DataFrame(pid, position); team_hist[team] = (current-season panel rows, previous-season rows)."""
    cols, info = {}, []
    for t in sides:
        qb = qbs.get(t)
        cur, prev = team_hist[t]
        ti = PL.team_inputs(a, avail[t], t, cur, prev, week, qb)
        for pid in list(ti["recv"].index) + list(ti["rush"].index) + ([qb] if qb else []):
            cols.setdefault(pid, len(cols))
        info.append((t, qb, ti))
    P = len(cols)
    pl = {"w_recv": np.zeros(P), "dist_recv": np.full((P, 7), 1 / 7), "coff": np.zeros(P), "w_rush": np.zeros(P),
          "dist_rush": np.full((P, 7), 1 / 7)}
    for pid, c in cols.items():
        wr, dr, co, wu, du = PL.efficiency(a, pid)
        pl["w_recv"][c], pl["dist_recv"][c], pl["coff"][c], pl["w_rush"][c], pl["dist_rush"][c] = wr, dr, co, wu, du
    teams = [{"pass_off": ti["pass_off"], "qb_col": cols.get(qb, 0),
              "recv_cols": np.array([cols[x] for x in ti["recv"].index]), "recv_cum": np.cumsum(ti["recv"]["share"].to_numpy()),
              "rush_cols": np.array([cols[x] for x in ti["rush"].index]), "rush_cum": np.cumsum(ti["rush"]["share"].to_numpy())}
             for t, qb, ti in info]
    return teams, pl, cols, info


def eligible(info, a):
    """v1 eligibility (as-of shares only): starting QB; target share >= 10%; carry share >= 20%; history required for baseline B."""
    out = []
    for t, qb, ti in info:
        el = [(qb, "pass_yds")] if qb else []
        el += [(pid, k) for pid in ti["recv"].index[ti["recv"]["share"] >= 0.10] for k in ("rec_yds", "rec")]
        el += [(pid, "rush_yds") for pid in ti["rush"].index[ti["rush"]["share"] >= 0.20]]
        out += [(t, pid, k) for pid, k in el if pid in a.index]
    return out


def baseline(a, pid, k, ratio, possd):
    """Baseline B parameters as in evaluate.run_season: ('poisson', lam) or ('normal', mu, sd); None when no history."""
    ar = a.loc[pid]
    if k == "pass_yds":
        mu, sd0, n0 = ar.get("qb_mean"), ar.get("qb_std"), ar.get("qb_size")
    else:
        mu, sd0, n0 = ar.get(k), ar.get(f"{k}_sd"), ar.get("games_total")
    if mu is None or np.isnan(mu):
        return None
    mu = float(mu) * ratio
    n0 = float(np.nan_to_num(n0))
    if k == "rec":
        return ("poisson", max(mu, 0.05))
    sd = (n0 * float(np.nan_to_num(sd0, nan=possd[k])) + PL.K_BLEND * possd[k]) / (n0 + PL.K_BLEND)
    return ("normal", mu, max(sd, 1.0))


def baseline_quantiles(b):
    if b[0] == "poisson":
        return float(b[1]), stats.poisson.ppf(LEVELS, b[1]).astype(float)
    return float(b[1]), stats.norm.ppf(LEVELS, b[1], b[2])


def qcrps(q: np.ndarray, y) -> np.ndarray:
    """CRPS estimated from quantiles at LEVELS: 2 x mean pinball loss. q has shape (..., 99); y broadcasts."""
    y = np.asarray(y, float)[..., None]
    return 2 * np.mean(((y < q).astype(float) - LEVELS) * (q - y), axis=-1)


def coverage(q: np.ndarray, y, lo: int, hi: int) -> np.ndarray:
    """Interval [q_lo, q_hi] (percent levels) contains y."""
    y = np.asarray(y, float)
    return ((q[..., lo - 1] <= y) & (y <= q[..., hi - 1])).astype(float)
