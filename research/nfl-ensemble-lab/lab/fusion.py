"""Sportsbooks as noisy sensors of one hidden line (docs/FUSION_PREREG.md)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats

from . import basket as K

C_FUSION = {"pass_yds": 0.30, "rec_yds": 0.70}
NU = 4.0
DECIDE_WEEKS = range(1, 5)
CONFIRM_WEEKS = range(5, 9)
SHARP = {"pinnacle", "novig", "prophetx"}


def quotes() -> pd.DataFrame:
    """One row per book quote with log odds-adjusted line and age; props with at least three books at a snapshot."""
    d = K.legs()
    c = d["stat"].map(C_FUSION)
    z = stats.norm.ppf(np.clip(d["p_over"], *K.P_CLIP))
    d["y"] = d["line"] + c * d["line"] * z
    d = d[d["y"] > 1].copy()
    d["ly"] = np.log(d["y"])
    d["pid_key"] = d["snap"].astype(str) + "|" + d["game_id"] + "|" + d["gsis_id"] + "|" + d["stat"]
    n = d.groupby("pid_key")["book"].transform("nunique")
    return d[n >= 3].reset_index(drop=True)


class Obs:
    def __init__(self, ly, book, prop, age, nbooks):
        self.ly, self.book, self.prop, self.age, self.B = np.asarray(ly, float), np.asarray(book), np.asarray(prop), np.asarray(age, float), nbooks
        self.P = int(prop.max()) + 1


def _center(o: Obs, beta, sig, q, iters=4):
    s2 = sig[o.book] ** 2 + q * o.age
    m = np.bincount(o.prop, weights=(o.ly - beta[o.book]), minlength=o.P) / np.bincount(o.prop, minlength=o.P)
    for _ in range(iters):
        r = o.ly - m[o.prop] - beta[o.book]
        w = (NU + 1) / (NU + r * r / s2)
        num = np.bincount(o.prop, weights=w * (o.ly - beta[o.book]) / s2, minlength=o.P)
        den = np.bincount(o.prop, weights=w / s2, minlength=o.P)
        m = num / den
    r = o.ly - m[o.prop] - beta[o.book]
    w = (NU + 1) / (NU + r * r / s2)
    return m, r, w, s2


def fit(o: Obs, iters=25) -> dict:
    beta, sig, q = np.zeros(o.B), np.full(o.B, 0.05), 1e-4
    for _ in range(iters):
        m, r, w, s2 = _center(o, beta, sig, q)
        resid_b = o.ly - m[o.prop]
        num = np.bincount(o.book, weights=w * resid_b / s2, minlength=o.B)
        den = np.bincount(o.book, weights=w / s2, minlength=o.B)
        beta = num / np.maximum(den, 1e-12)
        beta -= np.median(beta)
        r = o.ly - m[o.prop] - beta[o.book]

        def nll(th):
            sg, qq = np.exp(th[:-1]), np.exp(th[-1])
            s = sg[o.book] ** 2 + qq * o.age
            return float(np.sum(np.log(s) + w * r * r / s))
        th = optimize.minimize(nll, np.log(np.append(sig, q)), method="L-BFGS-B", bounds=[(-8, 0)] * o.B + [(-14, -3)]).x
        sig, q = np.exp(th[:-1]), float(np.exp(th[-1]))
    return {"beta": beta, "sigma": sig, "q": q}


def fused(o: Obs, par: dict):
    m, r, w, s2 = _center(o, par["beta"], par["sigma"], par["q"])
    return m, r / np.sqrt(s2)


def encode(d: pd.DataFrame, books: list) -> Obs:
    b = d["book"].map({k: i for i, k in enumerate(books)}).to_numpy()
    p = pd.factorize(d["pid_key"])[0]
    return Obs(d["ly"], b, p, d["age"], len(books))


def crps_free_logloss(center: np.ndarray, line: np.ndarray, c: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    p = 1 - stats.norm.cdf((line - center) / (c * center))
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return -(outcome * np.log(p) + (1 - outcome) * np.log(1 - p))
