"""Coherence Test B (docs/COHERENCE_PREREG.md and Amendment 1): do Kalshi player ladders keep catching up to a game-line move that was already visible?"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from .config import CACHE_DIR

CAND = CACHE_DIR / "props_kalshi" / "candles"
SCOPE = CACHE_DIR / "props_kalshi_scope.parquet"
OUT = CACHE_DIR / "coherence_ladder_points.parquet"
HORIZONS = (24, 12, 3)
SMALLEST = 0.15
MAX_SPREAD = 0.20


def _pick(rows: list, target: int):
    best = None
    for r in rows:
        if r["end_period_ts"] <= target:
            best = r
        else:
            break
    if best is None:
        return None
    try:
        bb, aa = best["yes_bid"], best["yes_ask"]
        b, a = float(bb.get("close", bb.get("close_dollars"))), float(aa.get("close", aa.get("close_dollars")))
    except (TypeError, ValueError, KeyError, AttributeError):
        return None
    if not (b > 0 and a < 1 and a - b <= MAX_SPREAD):
        return None
    return (a + b) / 2, a - b


def points() -> pd.DataFrame:
    """Usable mid price of every greater-type ladder contract at each horizon."""
    if OUT.exists():
        return pd.read_parquet(OUT)
    k = pd.read_parquet(SCOPE)
    k = k[k["strike_type"] == "greater"].copy()
    k["kick_ts"] = pd.to_datetime(k["kickoff"], utc=True).astype("int64") // 10**9
    out = []
    for r in k.itertuples():
        f = CAND / f"{r.ticker}.json"
        if not f.exists():
            continue
        rows = sorted(json.load(open(f)), key=lambda x: x["end_period_ts"])
        for h in HORIZONS:
            p = _pick(rows, r.kick_ts - h * 3600)
            if p:
                out.append((r.ticker, r.gid, r.series, r.team, r.pid, r.player, float(r.strike), h, p[0], p[1]))
    d = pd.DataFrame(out, columns=["ticker", "gid", "series", "team", "pid", "player", "strike", "h", "mid", "spread"])
    d.to_parquet(OUT)
    return d


def crossing(strikes: np.ndarray, p: np.ndarray) -> float | None:
    if len(strikes) < 3:
        return None
    o = np.argsort(strikes)
    s, q = strikes[o], IsotonicRegression(increasing=False).fit_transform(strikes[o], p[o])
    if not (q.max() >= 0.5 >= q.min()) or q.max() == q.min():
        return None
    i = np.where((q[:-1] >= 0.5) & (q[1:] <= 0.5))[0]
    if len(i) == 0:
        return None
    i = i[0]
    if q[i] == q[i + 1]:
        return float(s[i])
    return float(s[i] + (q[i] - 0.5) / (q[i] - q[i + 1]) * (s[i + 1] - s[i]))


def medians(d: pd.DataFrame) -> pd.DataFrame:
    """One row per ladder and horizon: gid, series, team, pid, h, implied median."""
    rows = []
    for (gid, ser, team, pid, h), g in d.groupby(["gid", "series", "team", "pid", "h"], dropna=False):
        m = crossing(g["strike"].to_numpy(), g["mid"].to_numpy())
        if m is not None:
            rows.append((gid, ser, team, pid, h, m))
    return pd.DataFrame(rows, columns=["gid", "series", "team", "pid", "h", "med"])


def team_points(m: pd.DataFrame) -> pd.DataFrame:
    """Implied points per team and horizon: the favorite is the team whose margin ladder crosses 0.5, the other team is the second team in the game id."""
    tot = m[m["series"] == "KXNFLTOTAL"][["gid", "h", "med"]].rename(columns={"med": "total"})
    sp = m[m["series"] == "KXNFLSPREAD"][["gid", "h", "team", "med"]].rename(columns={"med": "margin"})
    both = sp.merge(tot, on=["gid", "h"])
    rows = []
    for r in both.itertuples():
        a, b = r.gid.split("_")[2:4]
        other = b if r.team == a else a
        rows.append((r.gid, r.h, r.team, (r.total + r.margin) / 2))
        rows.append((r.gid, r.h, other, (r.total - r.margin) / 2))
    return pd.DataFrame(rows, columns=["gid", "h", "team", "tp"])


def design(d: pd.DataFrame) -> pd.DataFrame:
    """One row per player ladder with the moves needed by the model."""
    m = medians(d)
    tp = team_points(m).groupby(["gid", "team", "h"], as_index=False)["tp"].mean()
    pl = m[m["series"].isin(["KXNFLPASSYDS", "KXNFLRECYDS"])]
    wide = pl.pivot_table(index=["gid", "series", "team", "pid"], columns="h", values="med").reset_index().dropna(subset=[24, 12, 3])
    t = tp.pivot_table(index=["gid", "team"], columns="h", values="tp").reset_index()
    t = t.rename(columns={24: "T24", 12: "T12", 3: "T3"})[["gid", "team", "T24", "T12"]]
    out = wide.merge(t, on=["gid", "team"], how="inner")
    out["dG"] = out["T12"] - out["T24"]
    out["y_next"] = out[3] - out[12]
    out["y_prev"] = out[12] - out[24]
    return out.dropna(subset=["dG", "y_next", "y_prev"])


def z(x):
    s = np.std(x, ddof=1)
    return (x - np.mean(x)) / s if s > 0 else x * 0


def slope_L(df: pd.DataFrame) -> float:
    x = np.column_stack([z(df["dG"].to_numpy()), z(df["y_prev"].to_numpy())])
    y = z(df["y_next"].to_numpy())
    return float(np.linalg.lstsq(x, y, rcond=None)[0][0])


def boot_se(df: pd.DataFrame, rng: np.random.Generator, b: int = 1000) -> tuple[float, np.ndarray]:
    ug, inv = np.unique(df["gid"].to_numpy(), return_inverse=True)
    idx = [np.where(inv == i)[0] for i in range(len(ug))]
    vals = []
    for _ in range(b):
        k = np.concatenate([idx[i] for i in rng.integers(0, len(ug), len(ug))])
        vals.append(slope_L(df.iloc[k]))
    vals = np.array(vals)
    return float(vals.std(ddof=1)), vals


def counts_and_gate(df: pd.DataFrame, rng: np.random.Generator) -> dict:
    """Counts and minimum detectable L per stage. L itself is not returned."""
    out = {}
    for stage, sel in (("decide_2025", df["gid"].str.startswith("2025")), ("confirm_2026", df["gid"].str.startswith("2026"))):
        s = df[sel]
        if s["gid"].nunique() < 5 or len(s) < 20:
            out[stage] = {"games": int(s["gid"].nunique()), "player_ladders": int(len(s)), "min_detectable_L": None, "informative": False}
            continue
        se, _ = boot_se(s, rng)
        out[stage] = {"games": int(s["gid"].nunique()), "player_ladders": int(len(s)), "se_L": se, "min_detectable_L": 2.8 * se, "informative": bool(2.8 * se <= SMALLEST)}
    return out
