"""Within-game dependence between player outcomes (docs/DEPENDENCE_PREREG.md).

Works in normal-score space: the stored PIT of each independent marginal forecast is mapped through the fit-season
empirical distribution and then through the normal quantile function. Copulas (Gaussian, t, Clayton) are fitted on the
fit seasons only and scored against the independence model on the held-out season.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.special import gammaln

from .config import ARTIFACTS_DIR

PROPS = ARTIFACTS_DIR / "props"
FIT_SEASONS = (2022, 2023, 2024)
TEST_SEASON = 2025
CLASSES = {"A_qb_wr": ("pass_yds", "rec_yds", "WR"), "B_qb_te": ("pass_yds", "rec_yds", "TE"), "C_qb_rb_rush": ("pass_yds", "rush_yds", "RB")}
T_NU = (4, 8, 16)
PLANTED_RHO = 0.15
GATE_LEVEL = 0.05 / 3
GATE_POWER = 0.80
M_DRAWS = 400
N_BOOT = 2000


def load_marginals() -> pd.DataFrame:
    a = pd.concat([pd.read_parquet(PROPS / "dev" / "player_games.parquet"), pd.read_parquet(PROPS / "eval" / "player_games.parquet")], ignore_index=True)
    return a[["game_id", "season", "team", "pid", "stat", "pit_base"]]


def positions() -> pd.Series:
    f = pd.concat([pd.read_parquet(PROPS / "phase10" / n, columns=["pid", "position"]) for n in ("features.parquet", "features_production.parquet")])
    return f.dropna().groupby("pid")["position"].agg(lambda s: s.value_counts().index[0])


def load_pairs() -> tuple[pd.DataFrame, dict]:
    a = load_marginals()
    pos = positions()
    a["position"] = a["pid"].map(pos)
    info = {"rows": int(len(a)), "rows_missing_position": int(a.loc[a["stat"] != "pass_yds", "position"].isna().sum()), "rows_non_qb_stats": int((a["stat"] != "pass_yds").sum())}
    qb = a[a["stat"] == "pass_yds"]
    one = qb.groupby(["game_id", "team"]).size()
    info["qb_team_games_dropped_not_one_row"] = int((one != 1).sum())
    qb = qb.merge(one[one == 1].rename("n").reset_index()[["game_id", "team"]], on=["game_id", "team"])[["game_id", "season", "team", "pit_base"]].rename(columns={"pit_base": "p1"})
    out = []
    for cls, (_, stat, p) in CLASSES.items():
        o = a[(a["stat"] == stat) & (a["position"] == p)][["game_id", "team", "pid", "pit_base"]].rename(columns={"pit_base": "p2"})
        m = qb.merge(o, on=["game_id", "team"])
        m["cls"] = cls
        out.append(m)
    return pd.concat(out, ignore_index=True), info


def ecdf_ref(a: pd.DataFrame, stat: str) -> np.ndarray:
    return np.sort(a.loc[(a["stat"] == stat) & a["season"].isin(FIT_SEASONS), "pit_base"].to_numpy())


def to_u(x, ref: np.ndarray) -> np.ndarray:
    n = len(ref)
    return np.clip(np.searchsorted(ref, np.asarray(x), side="right") / (n + 1), 1 / (n + 1), n / (n + 1))


def z_of(u):
    return stats.norm.ppf(u)


def logpdf(fam: str, par: tuple, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    if fam == "gaussian":
        r = par[0]
        x, y = z_of(u), z_of(v)
        return -0.5 * np.log1p(-r * r) - (r * r * (x * x + y * y) - 2 * r * x * y) / (2 * (1 - r * r))
    if fam == "t":
        r, nu = par
        x, y = stats.t.ppf(u, nu), stats.t.ppf(v, nu)
        q = (x * x + y * y - 2 * r * x * y) / (nu * (1 - r * r))
        return (gammaln((nu + 2) / 2) + gammaln(nu / 2) - 2 * gammaln((nu + 1) / 2) - 0.5 * np.log1p(-r * r) - (nu + 2) / 2 * np.log1p(q)
                + (nu + 1) / 2 * (np.log1p(x * x / nu) + np.log1p(y * y / nu)))
    th = par[0]
    return np.log1p(th) - (1 + th) * (np.log(u) + np.log(v)) - (2 + 1 / th) * np.log(u ** -th + v ** -th - 1)


def fit_all(u: np.ndarray, v: np.ndarray) -> dict:
    n = len(u)
    res = {}
    f = optimize.minimize_scalar(lambda r: -logpdf("gaussian", (r,), u, v).sum(), bounds=(-0.95, 0.95), method="bounded")
    res["gaussian"] = {"par": (float(f.x),), "ll": float(-f.fun), "k": 1}
    best = None
    for nu in T_NU:
        f = optimize.minimize_scalar(lambda r: -logpdf("t", (r, nu), u, v).sum(), bounds=(-0.95, 0.95), method="bounded")
        if best is None or -f.fun > best["ll"]:
            best = {"par": (float(f.x), nu), "ll": float(-f.fun), "k": 2}
    res["t"] = best
    f = optimize.minimize_scalar(lambda t: -logpdf("clayton", (t,), u, v).sum(), bounds=(0.01, 10), method="bounded")
    res["clayton"] = {"par": (float(f.x),), "ll": float(-f.fun), "k": 1}
    for r in res.values():
        r["bic"] = r["k"] * np.log(n) - 2 * r["ll"]
    res["chosen"] = min(("gaussian", "t", "clayton"), key=lambda k: res[k]["bic"])
    return res


def sample(fam: str, par: tuple, n: int, m: int, rng: np.random.Generator) -> np.ndarray:
    """Normal-score draws, shape (n, m, 2)."""
    if fam == "independence":
        return np.stack(rng.standard_normal((2, n, m)), -1)
    if fam == "gaussian":
        r = par[0]
        a, b = rng.standard_normal((2, n, m))
        return np.stack([a, r * a + np.sqrt(1 - r * r) * b], -1)
    if fam == "t":
        r, nu = par
        a, b = rng.standard_normal((2, n, m))
        w = np.sqrt(rng.chisquare(nu, (n, m)) / nu)
        return z_of(np.clip(stats.t.cdf(np.stack([a, r * a + np.sqrt(1 - r * r) * b], -1) / w[..., None], nu), 1e-9, 1 - 1e-9))
    th = par[0]
    u, w = rng.uniform(1e-9, 1 - 1e-9, (2, n, m))
    v = ((w ** (-th / (1 + th)) - 1) * u ** -th + 1) ** (-1 / th)
    return z_of(np.clip(np.stack([u, v], -1), 1e-9, 1 - 1e-9))


def scores(draws: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Energy score and variogram score (p = 0.5) per observation; lower is better."""
    m = draws.shape[1] // 2
    a, b = draws[:, :m], draws[:, m:2 * m]
    term1 = np.linalg.norm(draws - y[:, None, :], axis=-1).mean(1)
    term2 = np.linalg.norm(a - b, axis=-1).mean(1)
    vs = (np.sqrt(np.abs(y[:, 0] - y[:, 1])) - np.sqrt(np.abs(draws[..., 0] - draws[..., 1])).mean(1)) ** 2
    return term1 - 0.5 * term2, vs


def game_means(d: np.ndarray, games: np.ndarray) -> np.ndarray:
    s = pd.Series(d).groupby(games).mean()
    return s.to_numpy()


def dm_p(g: np.ndarray) -> tuple[float, float]:
    """One-sided Diebold-Mariano p that the mean game-level loss difference is above zero."""
    se = g.std(ddof=1) / np.sqrt(len(g))
    t = g.mean() / se if se > 0 else 0.0
    return float(t), float(1 - stats.norm.cdf(t))


def boot_p(g: np.ndarray, rng: np.random.Generator, b: int = N_BOOT) -> tuple[float, tuple[float, float]]:
    idx = rng.integers(0, len(g), (b, len(g)))
    mu = g[idx].mean(1)
    return float((np.sum(mu <= 0) + 1) / (b + 1)), (float(np.quantile(mu, 0.025)), float(np.quantile(mu, 0.975)))


def evaluate(fit_u: np.ndarray, fit_v: np.ndarray, test_z: np.ndarray, test_games: np.ndarray, rng: np.random.Generator, m: int = M_DRAWS) -> dict:
    """Fit on (u, v), choose by BIC, score on held-out normal scores. Returns per-game loss differences."""
    fits = fit_all(fit_u, fit_v)
    fam = fits["chosen"]
    n = len(test_z)
    seed = int(rng.integers(2 ** 31))
    es_c, vs_c = scores(sample(fam, fits[fam]["par"], n, m, np.random.default_rng(seed)), test_z)
    es_i, vs_i = scores(sample("independence", (), n, m, np.random.default_rng(seed)), test_z)
    return {"fits": fits, "family": fam, "g_es": game_means(es_i - es_c, test_games), "g_vs": game_means(vs_i - vs_c, test_games)}


def planted_z(struct: pd.DataFrame, rho: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """struct: one row per team-game with game_id and n (number of receivers). One quarterback score per team-game."""
    n = struct["n"].to_numpy()
    z1 = np.repeat(rng.standard_normal(len(n)), n)
    z2 = rho * z1 + np.sqrt(1 - rho * rho) * rng.standard_normal(len(z1))
    return np.stack([z1, z2], 1), np.repeat(struct["game_id"].to_numpy(), n)


def sim_once(s_fit: pd.DataFrame, s_test: pd.DataFrame, rho: float, rng: np.random.Generator, m: int = M_DRAWS) -> dict:
    zf, _ = planted_z(s_fit, rho, rng)
    zt, gt = planted_z(s_test, rho, rng)
    ev = evaluate(stats.norm.cdf(zf[:, 0]), stats.norm.cdf(zf[:, 1]), zt, gt, rng, m)
    return {"p_es": dm_p(ev["g_es"])[1], "p_vs": dm_p(ev["g_vs"])[1], "rho_hat": ev["fits"]["gaussian"]["par"][0], "family": ev["family"]}


def structure(pairs: pd.DataFrame, cls: str, seasons) -> pd.DataFrame:
    p = pairs[(pairs["cls"] == cls) & pairs["season"].isin(seasons)]
    return p.groupby(["game_id", "team"]).size().rename("n").reset_index()


def scale_structure(s: pd.DataFrame, k: int) -> pd.DataFrame:
    return pd.concat([s.assign(game_id=s["game_id"] + f"#{i}") for i in range(k)], ignore_index=True)


def gate(pairs: pd.DataFrame, cls: str, rng: np.random.Generator, reps: int = 400, rec_reps: int = 100, scan_reps: int = 100, multipliers=(2, 3, 5, 8)) -> dict:
    """Recovery and power from the count structure only; no outcome is read."""
    out = {}
    for cls in (cls,):
        sf, st = structure(pairs, cls, FIT_SEASONS), structure(pairs, cls, [TEST_SEASON])
        rec = {}
        for rho in (0.0, 0.10, 0.20, 0.30, 0.50):
            r = [sim_once(sf, st, rho, rng) for _ in range(rec_reps)]
            rec[str(rho)] = {"mean_rho_hat": float(np.mean([x["rho_hat"] for x in r])), "reject_es": float(np.mean([x["p_es"] < GATE_LEVEL for x in r])), "reject_both": float(np.mean([(x["p_es"] < GATE_LEVEL) and (x["p_vs"] < GATE_LEVEL) for x in r]))}
        r = [sim_once(sf, st, PLANTED_RHO, rng) for _ in range(reps)]
        power = float(np.mean([(x["p_es"] < GATE_LEVEL) and (x["p_vs"] < GATE_LEVEL) for x in r]))
        scan = {}
        for k in multipliers:
            rr = [sim_once(sf, scale_structure(st, k), PLANTED_RHO, rng) for _ in range(scan_reps)]
            scan[str(k)] = {"games": int(st["game_id"].nunique() * k), "power_both": float(np.mean([(x["p_es"] < GATE_LEVEL) and (x["p_vs"] < GATE_LEVEL) for x in rr]))}
        need = next((v["games"] for v in scan.values() if v["power_both"] >= GATE_POWER), None)
        rec_ok = abs(rec["0.2"]["mean_rho_hat"] - 0.20) <= 0.03 and rec["0.0"]["reject_both"] <= 0.07
        out[cls] = {"fit_team_games": int(len(sf)), "fit_pairs": int(sf["n"].sum()), "test_team_games": int(len(st)), "test_pairs": int(st["n"].sum()), "test_games": int(st["game_id"].nunique()),
                    "recovery": rec, "recovery_ok": bool(rec_ok), "power_at_0.15_both_scores": power, "power_ok": bool(power >= GATE_POWER),
                    "informative": bool(rec_ok and power >= GATE_POWER), "scan": scan, "games_for_80pct_power": need}
    return out
