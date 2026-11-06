"""Closing-line efficiency tests on 20 years of game lines (docs/LINEMOVE_PREREG.md)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats
from sklearn.linear_model import LogisticRegression

from .config import RAW_DIR

FILE = RAW_DIR / "market" / "aussportsbetting_nfl.xlsx"
DECIDE = range(2006, 2016)
CONFIRM = range(2016, 2026)
SIZE = {"T1": 0.06, "T2": 0.06, "T3": 0.10, "T4": 0.06}
TESTS = ("T1", "T2", "T3", "T4")


def load() -> pd.DataFrame:
    d = pd.read_excel(FILE, sheet_name="Data", header=0)
    d["date"] = pd.to_datetime(d["Date"])
    d = d[d["Playoff Game?"].isna()].copy()
    d["season"] = np.where(d["date"].dt.month >= 8, d["date"].dt.year, d["date"].dt.year - 1)
    need = ["Home Score", "Away Score", "Home Line Open", "Home Line Close", "Home Line Min", "Home Line Max", "Total Score Open", "Total Score Close", "Home Odds Close", "Away Odds Close", "Home Line Odds Close", "Away Line Odds Close"]
    d = d.dropna(subset=need).copy()
    d["m_close"], d["m_open"] = -d["Home Line Close"], -d["Home Line Open"]
    d["margin"] = d["Home Score"] - d["Away Score"]
    d["E"] = d["margin"] - d["m_close"]
    d["M"] = d["m_close"] - d["m_open"]
    d["Et"] = d["Home Score"] + d["Away Score"] - d["Total Score Close"]
    d["Mt"] = d["Total Score Close"] - d["Total Score Open"]
    d["R"] = d["Home Line Max"] - d["Home Line Min"]
    ph, pa = 1 / d["Home Odds Close"], 1 / d["Away Odds Close"]
    d["p_ml"] = ph / (ph + pa)
    d["home_win"] = (d["margin"] > 0).astype(float)
    d = d[d["margin"] != 0].reset_index(drop=True)
    return d


def sigma_fit(dec: pd.DataFrame) -> float:
    m, w = dec["m_close"].to_numpy(), dec["home_win"].to_numpy()
    f = lambda s: -np.sum(w * stats.norm.logcdf(m / s) + (1 - w) * stats.norm.logcdf(-m / s))
    return float(optimize.minimize_scalar(f, bounds=(5, 30), method="bounded").x)


def z(x):
    x = np.asarray(x, float)
    s = x.std(ddof=1)
    return (x - x.mean()) / s if s > 0 else x * 0


def design(d: pd.DataFrame, sig: float) -> dict:
    lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
    p_sp = stats.norm.cdf(d["m_close"] / sig)
    dd = lg(d["p_ml"]) - lg(p_sp)
    return {"T1": (z(d["M"]), z(d["E"]), None), "T2": (z(d["Mt"]), z(d["Et"]), None), "T3": (np.column_stack([z(lg(p_sp)), z(dd)]), d["home_win"].to_numpy(), "logit"),
            "T4": (np.column_stack([z(d["R"]), z(d["Total Score Close"])]), z(d["E"].abs()), "multi")}


def coef(test: str, d: pd.DataFrame, sig: float) -> float:
    x, y, kind = design(d, sig)[test]
    if test == "T3":
        return float(LogisticRegression(penalty=None, max_iter=200).fit(x, y).coef_[0][1])
    if test == "T4":
        return float(np.linalg.lstsq(np.column_stack([x, np.ones(len(x))]), y, rcond=None)[0][0])
    return float(np.corrcoef(x, y)[0, 1])


def boot(test: str, d: pd.DataFrame, sig: float, rng: np.random.Generator, b: int = 1000) -> np.ndarray:
    n = len(d)
    return np.array([coef(test, d.iloc[rng.integers(0, n, n)], sig) for _ in range(b)])


def gate(conf: pd.DataFrame, sig: float, rng: np.random.Generator) -> dict:
    out = {}
    for t in TESTS:
        se = float(boot(t, conf, sig, rng, 600).std(ddof=1))
        out[t] = {"se": se, "min_detectable": 2.8 * se, "size_of_interest": SIZE[t], "informative": bool(2.8 * se <= SIZE[t]), "n": int(len(conf))}
    return out
