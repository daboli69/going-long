"""Home-win study v2. Frozen protocol: docs/HOMEWIN_V2_PREREGISTRATION.md (commit 18e98172).

Power, walk-forward expected points, per-game decision points, stacking and CLV, built on lab.homewin_deep.
"""
from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

from . import homewin_deep as h
from . import homewin_eval as ev
from .config import LAB_ROOT, RAW_DIR

PREREG_COMMIT = "18e98172"
REPORT_DIR = LAB_ROOT / "reports" / "homewin_v2"
CACHE = h.CACHE / "v2"
SESOI_LL = 0.005
SESOI_CLV = 0.005
POINTS = ["open", "wed", "fri", "t90", "close"]
CLV_POINTS = ["open", "wed", "fri", "t90"]
ET = "America/New_York"


# --------------------------------------------------------------------------- decision points

def decision_points(games: pd.DataFrame) -> pd.DataFrame:
    """Per game: open, Wednesday, Friday, T-90 and close timestamps (UTC), each capped at kickoff - 90 min."""
    k = games["kickoff_utc"]
    local = k.dt.tz_convert(ET)
    day = local.dt.normalize().dt.tz_localize(None)
    dow = day.dt.dayofweek  # Mon=0 ... Sun=6

    def at(d, hour):
        return (d + pd.Timedelta(hours=hour)).dt.tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")

    two_before = day - pd.Timedelta(days=2)
    open_day = two_before - pd.to_timedelta((two_before.dt.dayofweek - 6) % 7, unit="D")
    wed_day = day - pd.to_timedelta(((dow - 2) % 7).replace(0, 7), unit="D")
    fri_day = day - pd.to_timedelta(((dow - 4) % 7).replace(0, 7), unit="D")
    t90 = k - h.DECISION_LEAD
    out = pd.DataFrame({"gid": games["gid"], "kickoff_utc": k,
                        "open": at(open_day, 20), "wed": at(wed_day, 12), "fri": at(fri_day, 17), "t90": t90, "close": k})
    for p in ("open", "wed", "fri"):
        out[p] = out[p].where(out[p] < t90, t90)
    return out


# --------------------------------------------------------------------------- 0. power

def power(data: h.Data) -> dict:
    z_ll = norm.ppf(1 - 0.0125 / 2) + norm.ppf(0.80)
    z_clv = norm.ppf(1 - 0.05 / 2) + norm.ppf(0.80)
    v1 = pd.read_parquet(h.CACHE / "walk_forward.parquet")
    y = v1["y_home_win"].to_numpy(float)
    d = ev._ll(y, v1["p_margin_platt"].to_numpy()) - ev._ll(y, v1["p_elo"].to_numpy())
    wk = pd.Series(d).groupby((v1["season"].astype(str) + "_" + v1["week"].astype(str)).to_numpy()).mean()
    sd_w = float(wk.std(ddof=1))
    n_hist = len(wk)
    n_ll = int(np.ceil((z_ll * sd_w / SESOI_LL) ** 2))
    res = {"prereg_commit": PREREG_COMMIT,
           "log_loss": {"source": "v1 margin_platt - elo, week means (design-stage)", "sd_week_mean": sd_w,
                        "history_weeks": n_hist, "history_mde": z_ll * sd_w / np.sqrt(n_hist), "sesoi": SESOI_LL,
                        "prospective_mde_by_weeks": {n: z_ll * sd_w / np.sqrt(n) for n in (1, 4, 8, 17, 34, 68)},
                        "N_LL_weeks": n_ll}}

    g = data.games[data.games["played"] & ~data.games["tie"]]
    pts = decision_points(g).set_index("gid")
    clv = {}
    for p in CLV_POINTS:
        moves, weeks = [], []
        for r in g.itertuples(index=False):
            a = h.market_probability(data.quotes, r.home, r.away, r.kickoff_utc, pts.at[r.gid, p])["p_home"]
            if np.isnan(a):
                continue
            c = h.market_probability(data.quotes, r.home, r.away, r.kickoff_utc, r.kickoff_utc)["p_home"]
            if np.isnan(c):
                continue
            moves.append(c - a)
            weeks.append(f"{r.season}_{r.week}")
        m = np.asarray(moves)
        n_games, n_weeks = len(m), len(set(weeks))
        rms = float(np.sqrt((m ** 2).mean())) if n_games else np.nan  # SD of CLV under random sides
        per_week = n_games / n_weeks if n_weeks else np.nan
        mde_hist = z_clv * rms / np.sqrt(n_games) if n_games else np.nan
        n_clv = int(np.ceil((z_clv * rms / SESOI_CLV) ** 2 / per_week)) if n_games else None
        clv[p] = {"games": n_games, "weeks": n_weeks, "rms_move": rms, "share_zero_move": float((m == 0).mean()) if n_games else None,
                  "history_mde": mde_hist, "games_per_week": per_week, "N_CLV_weeks": n_clv,
                  "prospective_mde_by_weeks": {n: z_clv * rms / np.sqrt(per_week * n) for n in (1, 4, 8, 17, 34)} if n_games else {}}
    ok = {p: v for p, v in clv.items() if v["games"]}
    primary = min(CLV_POINTS, key=lambda p: (ok[p]["history_mde"] if p in ok else np.inf, CLV_POINTS.index(p)))
    res["clv"] = {"points": clv, "primary_point": primary, "N_CLV_weeks": clv[primary]["N_CLV_weeks"], "sesoi": SESOI_CLV}
    return res
