"""Quarterback passing-yards line against the receiver basket (docs/BASKET_PREREG.md)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats

from . import coherence_book as CB
from .config import CACHE_DIR, RAW_DIR
from .props import lines as L

DECIDE_WEEKS = range(1, 5)
CONFIRM_WEEKS = range(5, 9)
P_CLIP = (0.25, 0.75)
RHO = 0.25
GATE_LEVEL = 0.05 / 2
KAPPA_SIZE = 0.15
MIN_RECEIVERS = 2


def american_p(o):
    o = np.asarray(o, float)
    return np.where(o < 0, -o / (-o + 100), 100 / (o + 100))


def power_fair(po: float, pu: float) -> float:
    f = lambda k: po ** k + pu ** k - 1
    try:
        k = optimize.brentq(f, 0.2, 5.0)
    except ValueError:
        return po / (po + pu)
    return po ** k


def games() -> pd.DataFrame:
    g = pd.read_parquet(CACHE_DIR / "games.parquet")
    g = g[(g["season"] == 2026) & (g["game_type"] == "REG")]
    return g[["game_id", "week", "home_team", "away_team", "kickoff_utc"]].rename(columns={"home_team": "home", "away_team": "away"})


def legs() -> pd.DataFrame:
    d = L.archived_lines()
    d = d[(d["period"] == "FULL") & d["stat"].isin(["pass_yds", "rec_yds"]) & d["line"].notna() & d["gsis_id"].notna() & d["over_odds"].notna() & d["under_odds"].notna()
          & (~d["in_play"].fillna(False).astype(bool)) & (~d["dfs"].fillna(False).astype(bool))].copy()
    d["snap"], d["kick"], d["qt"] = CB._t(d["available_at"]), CB._t(d["kickoff"]), CB._t(d["quote_time"])
    d = d[(d["qt"] <= d["snap"]) & (d["snap"] - d["qt"] <= pd.Timedelta(hours=CB.MAX_AGE_H)) & (d["snap"] < d["kick"])]
    d = d.sort_values("qt").drop_duplicates(["snap", "home", "away", "book", "gsis_id", "stat"], keep="last")
    po, pu = american_p(d["over_odds"]), american_p(d["under_odds"])
    d["p_over"] = [power_fair(a, b) for a, b in zip(po, pu)]
    d["hold"] = po + pu - 1
    d["over_odds"], d["under_odds"] = d["over_odds"].astype(float), d["under_odds"].astype(float)
    rt = CB.roster_teams()
    def team_of(r):
        s = rt.get(r.gsis_id, set())
        h, a = r.home in s, r.away in s
        return r.home if h and not a else r.away if a and not h else None
    d["team"] = [team_of(r) for r in d.itertuples()]
    d = d[d["team"].notna()]
    g = games()
    d = d.merge(g, on=["home", "away"], how="inner")
    d = d[(d["kick"] - d["kickoff_utc"]).abs() <= pd.Timedelta(days=1)]
    return d[["snap", "kick", "book", "game_id", "week", "home", "away", "team", "gsis_id", "stat", "line", "over_odds", "under_odds", "p_over", "hold"]].reset_index(drop=True)


def actuals() -> pd.DataFrame:
    p = pd.read_parquet(RAW_DIR / "play_by_play_2026.parquet", columns=["game_id", "posteam", "pass_attempt", "sack", "passer_player_id", "receiver_player_id", "passing_yards", "receiving_yards", "game_seconds_remaining"])
    q = p[(p["pass_attempt"] == 1) & (p["sack"] == 0)]
    done = p.groupby("game_id")["game_seconds_remaining"].min()
    done = set(done[done <= 0].index)
    r = q.groupby(["game_id", "receiver_player_id"])["receiving_yards"].sum().rename("rec").reset_index().rename(columns={"receiver_player_id": "gsis_id"})
    s = q.groupby(["game_id", "passer_player_id"])["passing_yards"].sum().rename("pas").reset_index().rename(columns={"passer_player_id": "gsis_id"})
    return r, s, done


def adjusted(df: pd.DataFrame, cQ: float, cR: float) -> pd.DataFrame:
    z = stats.norm.ppf(np.clip(df["p_over"], *P_CLIP))
    c = np.where(df["stat"] == "pass_yds", cQ, cR)
    return df.assign(adj=df["line"] + c * df["line"] * z)


def fit_decide(lg: pd.DataFrame, rec: pd.DataFrame, pas: pd.DataFrame, done: set) -> dict:
    """c factors and remainder shares from the decide-stage weeks, outcomes included."""
    d = lg[lg["week"].isin(DECIDE_WEEKS) & lg["game_id"].isin(done)]
    d = d.merge(rec, on=["game_id", "gsis_id"], how="left").merge(pas, on=["game_id", "gsis_id"], how="left")
    cQ = cR = 0.3
    for _ in range(4):
        a = adjusted(d, cQ, cR)
        q, r = a[a["stat"] == "pass_yds"], a[a["stat"] == "rec_yds"]
        cQ = float(np.sqrt((((q["pas"].fillna(0) - q["adj"]) / q["line"]) ** 2).mean()))
        cR = float(np.sqrt((((r["rec"].fillna(0) - r["adj"]) / r["line"].clip(lower=5)) ** 2).mean()))
    tg = team_games(lg[lg["week"].isin(DECIDE_WEEKS) & lg["game_id"].isin(done)], rec, pas, cQ, cR, {}, need_share=True)
    shares = {}
    for k in (2, 3, 4, 5):
        s = tg[(tg["k"].clip(upper=5) == k)]
        shares[k] = float(((s["qb_act"] - s["listed_act"]) / s["qb_act"].clip(lower=1)).mean()) if len(s) >= 10 else None
    pooled = float(((tg["qb_act"] - tg["listed_act"]) / tg["qb_act"].clip(lower=1)).mean())
    return {"cQ": cQ, "cR": cR, "share": {k: (v if v is not None else pooled) for k, v in shares.items()}, "pooled_share": pooled, "decide_team_games": int(len(tg))}


def team_games(lg: pd.DataFrame, rec: pd.DataFrame, pas: pd.DataFrame, cQ: float, cR: float, share: dict, need_share: bool = False) -> pd.DataFrame:
    a = adjusted(lg, cQ, cR)
    a = a.merge(rec, on=["game_id", "gsis_id"], how="left").merge(pas, on=["game_id", "gsis_id"], how="left")
    rows = []
    for (snap, book, gid, team), g in a.groupby(["snap", "book", "game_id", "team"]):
        q, r = g[g["stat"] == "pass_yds"], g[g["stat"] == "rec_yds"]
        if len(q) < 1 or len(r) < MIN_RECEIVERS:
            continue
        q = q.sort_values("line", ascending=False).iloc[0]
        k = len(r)
        B = float(r["adj"].sum())
        rem = share.get(min(k, 5), share.get("pooled", 0.2)) if share else 0.0
        Qstar = B / (1 - rem)
        rows.append({"snap": snap, "book": book, "game_id": gid, "team": team, "week": int(q["week"]), "k": k, "Q": float(q["adj"]), "Q_line": float(q["line"]), "B": B, "Qstar": Qstar,
                     "G": float(q["adj"]) - Qstar, "g": (float(q["adj"]) - Qstar) / float(q["adj"]), "qb_act": q["pas"], "listed_act": float(r["rec"].fillna(0).sum()),
                     "qb_over": float(q["over_odds"]), "qb_under": float(q["under_odds"]), "holds": float(g["hold"].sum()), "legs": int(len(g))})
    return pd.DataFrame(rows)


def clv_bets(lg: pd.DataFrame, tg: pd.DataFrame, par: dict) -> pd.DataFrame:
    """Amendment 2: one bet per listed receiver at the early snapshot, valued against the closing consensus."""
    g = games().set_index("game_id")["kickoff_utc"]
    tg = tg.assign(kick=tg["game_id"].map(g))
    tg["hrs"] = (tg["kick"] - tg["snap"]).dt.total_seconds() / 3600
    early = tg[(tg["hrs"] <= 48) & (tg["hrs"] >= 18)].sort_values("snap").groupby(["book", "game_id", "team"]).head(1)
    thr = float(early.loc[early["week"].isin(DECIDE_WEEKS), "g"].abs().median())
    big = early[early["g"].abs() >= thr]
    a = adjusted(lg, par["cQ"], par["cR"])
    r = a[a["stat"] == "rec_yds"]
    fin = r.sort_values("snap").groupby(["book", "game_id", "gsis_id"]).tail(1)
    cons = fin.groupby(["game_id", "gsis_id"]).agg(M=("adj", "median"), nb=("book", "nunique")).reset_index()
    cons = cons[cons["nb"] >= CB.MIN_BOOKS]
    b = big[["book", "game_id", "team", "snap", "g", "week"]].merge(r, on=["book", "game_id", "team", "snap"], suffixes=("", "_r"))
    b = b.merge(cons, on=["game_id", "gsis_id"])
    over = b["g"] < 0
    odds = np.where(over, b["over_odds"], b["under_odds"])
    be = american_p(odds)
    sig = par["cR"] * b["M"].clip(lower=5)
    z = (b["M"] - b["line"]) / sig
    prob = np.where(over, stats.norm.cdf(z), stats.norm.cdf(-z))
    return b.assign(side=np.where(over, "over", "under"), be=be, prob=prob, net=prob - be, gross=prob - 0.5)[["book", "game_id", "team", "week", "gsis_id", "side", "line", "M", "g", "be", "prob", "net", "gross"]]
