"""Probability and margin metrics with game-level bootstrap confidence intervals."""
from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-6


def log_loss(y, p) -> float:
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y, p) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def accuracy(y, p) -> float:
    return float(np.mean((np.asarray(p, float) > 0.5) == (np.asarray(y, float) == 1)))


def ece(y, p, bins: int = 10) -> float:
    t = calibration_table(y, p, bins)
    return float((t["n"] * (t["mean_pred"] - t["observed"]).abs()).sum() / max(t["n"].sum(), 1))


def calibration_table(y, p, bins: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"y": np.asarray(y, float), "p": np.asarray(p, float)})
    df["bucket"] = np.minimum((df["p"] * bins).astype(int), bins - 1)
    t = df.groupby("bucket").agg(n=("y", "size"), mean_pred=("p", "mean"), observed=("y", "mean")).reset_index()
    t["range"] = [f"{b / bins:.0%}-{(b + 1) / bins:.0%}" for b in t["bucket"]]
    return t[["range", "n", "mean_pred", "observed"]]


def bootstrap_ci(fn, *arrays, n_boot: int = 1000, seed: int = 0, alpha: float = 0.05):
    rng = np.random.default_rng(seed)
    arrays = [np.asarray(a) for a in arrays]
    n = len(arrays[0])
    if n == 0:
        return (np.nan, np.nan)
    stats = [fn(*(a[idx] for a in arrays)) for idx in (rng.integers(0, n, n) for _ in range(n_boot))]
    return (float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2)))


def prob_summary(y, p, ci: bool = True) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = ~np.isnan(p) & ~np.isnan(y)
    y, p = y[ok], p[ok]
    out = {"n": int(len(y))}
    if not len(y):
        return out | {"accuracy": np.nan, "brier": np.nan, "log_loss": np.nan, "ece": np.nan}
    out |= {"accuracy": accuracy(y, p), "brier": brier(y, p), "log_loss": log_loss(y, p), "ece": ece(y, p)}
    if ci:
        out["accuracy_ci"] = bootstrap_ci(accuracy, y, p)
        out["brier_ci"] = bootstrap_ci(brier, y, p)
        out["log_loss_ci"] = bootstrap_ci(log_loss, y, p)
    return out


def margin_summary(actual, pred) -> dict:
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    ok = ~np.isnan(a) & ~np.isnan(p)
    a, p = a[ok], p[ok]
    if not len(a):
        return {"n": 0, "mae": np.nan, "rmse": np.nan, "winner_acc": np.nan}
    mae = lambda x, y: float(np.mean(np.abs(x - y)))
    nz = a != 0
    return {"n": int(len(a)), "mae": mae(a, p), "rmse": float(np.sqrt(np.mean((a - p) ** 2))),
            "mae_ci": bootstrap_ci(mae, a, p),
            "winner_acc": float(np.mean(np.sign(p[nz]) == np.sign(a[nz]))) if nz.any() else np.nan}
