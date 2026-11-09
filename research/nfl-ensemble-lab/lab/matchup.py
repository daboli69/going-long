"""Matchup features against the closing line. Rule: docs/MATCHUP_PREREG.md (with Amendment 1)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RAW_DIR
from .ingest import normalize_team

K_EPA = 250.0
K_INT = 300.0
RIDGE = 1.0
FIRST_FIT, FIRST_TEST, LAST_TEST = 2007, 2022, 2025
COLS = ["season", "week", "season_type", "posteam", "defteam", "play_type", "epa", "pass", "interception"]
H1, H2 = ["net_eff", "pass_match"], ["int_prod"]


def _plays(seasons) -> pd.DataFrame:
    parts = [pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=COLS) for s in seasons]
    p = pd.concat(parts, ignore_index=True)
    p = p[(p["season_type"] == "REG") & p["play_type"].isin(["pass", "run"]) & p["epa"].notna() & p["posteam"].notna() & p["defteam"].notna()].copy()
    p["posteam"], p["defteam"] = p["posteam"].map(normalize_team), p["defteam"].map(normalize_team)
    p["pass"] = (p["pass"] == 1).astype(int)
    p["interception"] = ((p["interception"] == 1) & (p["pass"] == 1)).astype(int)
    return p


def _agg(p: pd.DataFrame, team_col: str) -> pd.DataFrame:
    d = p.assign(pe=p["epa"] * p["pass"])
    g = d.groupby(["season", "week", team_col]).agg(n=("epa", "size"), epa=("epa", "sum"), pn=("pass", "sum"), pepa=("pe", "sum"), ints=("interception", "sum"))
    g.index.names = ["season", "week", "team"]
    return g


def team_tables(p: pd.DataFrame):
    return _agg(p, "posteam"), _agg(p, "defteam")


def _cum(tab: pd.DataFrame) -> dict:
    """{(season, team): (weeks, cumulative n, epa, pass n, pass epa, interceptions)} for look-ups before a given week."""
    out = {}
    for (s, t), x in tab.reset_index().sort_values("week").groupby(["season", "team"]):
        out[(s, t)] = (x["week"].to_numpy(), x[["n", "epa", "pn", "pepa", "ints"]].cumsum().to_numpy())
    return out


def _asof(cum: dict, season: int, week: int, team: str, prior: pd.Series, league_int: float) -> dict:
    """Rates for one side before `week`: current-season plays blended with the previous full season."""
    wk, c = cum.get((season, team), (np.array([]), np.zeros((0, 5))))
    k = int(np.searchsorted(wk, week, side="left"))
    n, e, pn, pe, it = (c[k - 1] if k else np.zeros(5))
    pr = prior.get(team)
    pre = 0.0 if pr is None else pr["epa"]
    ppe = 0.0 if pr is None else pr["pepa"]
    wi = pn / (pn + K_INT)
    cur_int = it / pn if pn else league_int
    return {"epa": (e + K_EPA * pre) / (n + K_EPA), "pass_epa": (pe + K_EPA * ppe) / (pn + K_EPA), "int": wi * cur_int + (1 - wi) * league_int}


def _prior(tab: pd.DataFrame, season: int) -> pd.Series:
    try:
        t = tab.xs(season, level="season")
    except KeyError:
        return pd.Series(dtype=object)
    s = t.groupby(level="team").sum()
    return pd.Series({tm: {"epa": r.epa / r.n, "pepa": r.pepa / max(r.pn, 1), "int": r.ints / max(r.pn, 1)} for tm, r in s.iterrows()})


def _games() -> pd.DataFrame:
    g = pd.read_csv(RAW_DIR / "games.csv")
    g = g[(g["game_type"] == "REG") & g["home_score"].notna() & (g["season"] >= FIRST_FIT)].copy()
    n0 = len(g)
    g = g[g["home_moneyline"].notna() & g["away_moneyline"].notna()].copy()
    g["dropped_no_ml"] = n0 - len(g)

    def imp(ml):
        ml = ml.astype(float)
        return np.where(ml < 0, -ml / (-ml + 100.0), 100.0 / (ml + 100.0))
    ih, ia = imp(g["home_moneyline"]), imp(g["away_moneyline"])
    g["p_mkt"] = ih / (ih + ia)
    g["m"] = np.log(g["p_mkt"] / (1 - g["p_mkt"]))
    g["y"] = (g["home_score"] > g["away_score"]).astype(float)
    g = g[g["home_score"] != g["away_score"]].copy()
    g["home"], g["away"] = g["home_team"].map(normalize_team), g["away_team"].map(normalize_team)
    return g.reset_index(drop=True)


def build(last_season: int = LAST_TEST) -> pd.DataFrame:
    """One row per game: closing log-odds m, outcome y and the three features (home minus away), all from earlier weeks only."""
    p = _plays(range(FIRST_FIT - 1, last_season + 1))
    off, de = team_tables(p)
    co, cd = _cum(off), _cum(de)
    g = _games()
    g = g[g["season"] <= last_season].reset_index(drop=True)
    league = {s: float(x["interception"].sum() / max(x["pass"].sum(), 1)) for s, x in p.groupby("season")}
    pri_o = {s: _prior(off, s - 1) for s in g["season"].unique()}
    pri_d = {s: _prior(de, s - 1) for s in g["season"].unique()}
    rows = []
    for r in g.itertuples():
        s, w = int(r.season), int(r.week)
        lg = league[s - 1]
        ho, ao = (_asof(co, s, w, t, pri_o[s], lg) for t in (r.home, r.away))
        hd, ad = (_asof(cd, s, w, t, pri_d[s], lg) for t in (r.home, r.away))
        net_h, net_a = ho["epa"] - hd["epa"], ao["epa"] - ad["epa"]
        pm_h, pm_a = ho["pass_epa"] - ad["pass_epa"], ao["pass_epa"] - hd["pass_epa"]
        ip_h, ip_a = ho["int"] * ad["int"], ao["int"] * hd["int"]
        rows.append((net_h - net_a, pm_h - pm_a, ip_h - ip_a))
    f = pd.DataFrame(rows, columns=H1 + H2)
    out = pd.concat([g[["game_id", "season", "week", "home", "away", "m", "p_mkt", "y"]], f], axis=1)
    return out


def fit(X: np.ndarray, m: np.ndarray, y: np.ndarray, ridge: float = RIDGE) -> np.ndarray:
    """Logistic regression of y on [1, m, X] with a ridge penalty on the X coefficients only. Newton steps."""
    n, k = X.shape
    A = np.column_stack([np.ones(n), m, X])
    beta = np.zeros(k + 2)
    beta[1] = 1.0
    pen = np.diag([0.0, 0.0] + [ridge] * k)
    for _ in range(50):
        z = A @ beta
        p = 1 / (1 + np.exp(-z))
        grad = A.T @ (p - y) + pen @ beta
        H = A.T @ (A * (p * (1 - p))[:, None]) + pen + 1e-9 * np.eye(k + 2)
        step = np.linalg.solve(H, grad)
        beta -= step
        if np.abs(step).max() < 1e-8:
            break
    return beta


def predict(beta: np.ndarray, X: np.ndarray, m: np.ndarray) -> np.ndarray:
    z = beta[0] + beta[1] * m + X @ beta[2:]
    return np.clip(1 / (1 + np.exp(-z)), 1e-6, 1 - 1e-6)


def logloss(p, y):
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def walk(df: pd.DataFrame, cols: list[str], seasons=range(FIRST_TEST, LAST_TEST + 1), y_col: str = "y") -> pd.DataFrame:
    """Out-of-sample probabilities for each test season: fit on 2007 through S-1, features standardised on that training set."""
    out = []
    for s in seasons:
        tr, te = df[df["season"] < s], df[df["season"] == s]
        mu, sd = tr[cols].mean().to_numpy(), tr[cols].std().to_numpy()
        b = fit(((tr[cols].to_numpy() - mu) / sd), tr["m"].to_numpy(), tr[y_col].to_numpy())
        p = predict(b, (te[cols].to_numpy() - mu) / sd, te["m"].to_numpy())
        out.append(pd.DataFrame({"season": s, "week": te["week"].to_numpy(), "p": p, "p_mkt": te["p_mkt"].to_numpy(), "y": te[y_col].to_numpy()}))
    return pd.concat(out, ignore_index=True)


def paired(oos: pd.DataFrame) -> pd.DataFrame:
    """Per game: log-loss and Brier difference, challenger minus champion."""
    return oos.assign(dll=logloss(oos["p"], oos["y"]) - logloss(oos["p_mkt"], oos["y"]), dbr=(oos["p"] - oos["y"]) ** 2 - (oos["p_mkt"] - oos["y"]) ** 2)


def week_se(d: pd.DataFrame, col: str = "dll") -> tuple[float, float]:
    """Mean and a normal standard error clustered by season-week."""
    c = d.groupby(["season", "week"])[col].agg(["sum", "count"])
    mean = float(d[col].mean())
    n = len(d)
    resid = c["sum"] - mean * c["count"]
    return mean, float(np.sqrt((resid ** 2).sum()) / n)


def passes(d: pd.DataFrame, min_gain: float = 0.002) -> bool:
    """The registered rule without the 2026 condition: pooled upper 97.5% bound below zero, gain of at least 0.002, 3 of 4 seasons better, Brier no worse."""
    mean, se = week_se(d)
    seasons_better = int((d.groupby("season")["dll"].mean() < 0).sum())
    return bool(mean + 1.96 * se < 0 and mean <= -min_gain and seasons_better >= 3 and d["dbr"].mean() <= 0)
