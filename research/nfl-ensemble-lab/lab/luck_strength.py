"""Luck-adjusted, play-level team strength (docs/LUCK_ADJUSTED_PREREGISTRATION.md and its Amendment 1).

Pipeline, all from raw play rows and the schedule, every number as of the decision time:
  1. play table: pass and rush plays, garbage time out;
  2. team-game table: per game and offense, counts and EPA sums split into normal, red-zone, interception and fumble plays;
  3. luck removal: interceptions, fumbles and red-zone results replaced by shrunk, as-of expectations (shrink constant k);
  4. weekly opponent-adjusted ridge (strength lambda, half-life H) on EPA per play;
  5. a Kalman filter per team and unit (process variance q, between-season regression rho) fed by the ridge-adjusted games;
  6. weekly weighted least squares from strength to margin and total, with predictive spreads.
Nothing here reads a result of a game that has not ended at least 12 hours before the target kickoff; `check_asof` enforces and reports it.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import luck_elo as LE
from .ingest import normalize_team

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("LUCK_DATA", ROOT / "data"))   # a clean checkout points this at the shared data folder
RAW = DATA / "raw"
FIRST, LAST = 2002, 2026
GARBAGE = (0.05, 0.95)
HIST_SEASONS = 2          # a team's history for luck shrinkage: this season to date and the two before
OFFSEASON_AGE = 4         # weeks of age added per season boundary when decaying old games
MAP_FROM = 2003           # strength-to-score fits use games from this season on (2002 states are still warming up)
GAME_HOURS, GAP_HOURS = 4, 12
UNITS = ("pass_off", "rush_off", "pass_def", "rush_def")
PLAY_COLS = ["game_id", "season_type", "posteam", "play_type", "qb_dropback", "epa", "wp", "interception", "fumble", "fumble_lost", "yardline_100"]
DEFAULTS = {"int_rate": 0.03, "e_int": -4.7, "p_fl": 0.5, "e_fl": -3.4, "e_fk": -0.6, "rz_pass": 0.1, "rz_rush": 0.0, "s2": 2.0}
SD_FLOOR = 3.0

# --------------------------------------------------------------------------- 1 and 2: plays and team-games


def load_plays(raw: Path = RAW, last_season: int = LAST) -> pd.DataFrame:
    """Regular-season pass and rush plays with an EPA, outside garbage time. unit: 0 pass (dropbacks, scrambles and sacks included), 1 rush.
    cat: 0 normal, 1 interception, 2 fumble. Kneels, spikes, kicks and penalty-only plays are not in the table."""
    parts = [pd.read_parquet(raw / f"play_by_play_{s}.parquet", columns=PLAY_COLS) for s in range(FIRST, last_season + 1)]
    p = pd.concat(parts, ignore_index=True)
    p = p[(p["season_type"] == "REG") & p["play_type"].isin(["pass", "run"]) & p["epa"].notna() & p["wp"].notna() & p["posteam"].notna()]
    p = p[(p["wp"] >= GARBAGE[0]) & (p["wp"] <= GARBAGE[1])].copy()
    p["team"] = p["posteam"].map(normalize_team)
    p["unit"] = np.where((p["qb_dropback"] == 1) | (p["play_type"] == "pass"), 0, 1)
    p["cat"] = np.where((p["interception"] == 1) & (p["unit"] == 0), 1, np.where(p["fumble"] == 1, 2, 0))
    p["rz"] = p["yardline_100"] <= 20
    return p[["game_id", "team", "unit", "cat", "rz", "epa", "fumble_lost"]]


STAT = ["n", "s_all", "s_base", "n_rz", "s_rz", "n_int", "s_int", "n_fum", "n_fl", "s_fl", "s_fk"]


def team_game_stats(plays: pd.DataFrame) -> pd.DataFrame:
    """One row per game, offense and unit group, as wide columns <stat>_p and <stat>_r."""
    p = plays
    normal = p["cat"] == 0
    fl = p["fumble_lost"].fillna(0) == 1
    v = pd.DataFrame({"game_id": p["game_id"], "team": p["team"], "unit": p["unit"],
                      "n": 1.0, "s_all": p["epa"],
                      "s_base": p["epa"] * (normal & ~p["rz"]), "n_rz": (normal & p["rz"]) * 1.0, "s_rz": p["epa"] * (normal & p["rz"]),
                      "n_int": (p["cat"] == 1) * 1.0, "s_int": p["epa"] * (p["cat"] == 1),
                      "n_fum": (p["cat"] == 2) * 1.0, "n_fl": ((p["cat"] == 2) & fl) * 1.0,
                      "s_fl": p["epa"] * ((p["cat"] == 2) & fl), "s_fk": p["epa"] * ((p["cat"] == 2) & ~fl)})
    g = v.groupby(["game_id", "team", "unit"], sort=False)[STAT].sum().unstack("unit", fill_value=0.0)
    g.columns = [f"{s}_{'pr'[u]}" for s, u in g.columns]
    return g.reset_index()


class Panel:
    """Rows are team-games (offense view) in week order; two rows per game. Everything a pass over time needs, as plain arrays."""

    def __init__(self, raw: Path = RAW, plays: pd.DataFrame | None = None, last_season: int = LAST):
        games = LE.load_games(regular_only=True, since=FIRST, neutral_rule="stadium_id")
        games = games[games["season"] <= last_season]
        tg = team_game_stats(load_plays(raw, last_season) if plays is None else plays)
        games = games[games["played"] & games["game_id"].isin(tg["game_id"].unique())].copy()
        games = games.sort_values(["season", "week", "kickoff", "game_id"]).reset_index(drop=True)
        self.teams = sorted(set(games["home"]) | set(games["away"]))
        self.tix = {t: i for i, t in enumerate(self.teams)}
        batches = games[["season", "week"]].drop_duplicates().sort_values(["season", "week"]).reset_index(drop=True)
        bmap = {(s, w): i for i, (s, w) in enumerate(zip(batches["season"], batches["week"]))}
        self.batch_season = batches["season"].to_numpy()
        self.batch_week = batches["week"].to_numpy()
        self.nb, self.T = len(batches), len(self.teams)
        # game arrays
        self.games = games
        G = len(games)
        self.G = G
        self.g_batch = np.array([bmap[(s, w)] for s, w in zip(games["season"], games["week"])])
        self.g_season = games["season"].to_numpy()
        self.g_kick = games["kickoff"].to_numpy("datetime64[ns]")
        self.y_m = (games["home_score"] - games["away_score"]).to_numpy(float)
        self.y_t = (games["home_score"] + games["away_score"]).to_numpy(float)
        self.g_neutral = games["neutral"].to_numpy(bool)
        self.g_home = games["home"].map(self.tix).to_numpy()
        self.g_away = games["away"].map(self.tix).to_numpy()
        # row arrays: row 2g is the home offense, row 2g+1 the away offense
        rows = []
        for r, side in ((0, "home"), (1, "away")):
            opp = "away" if side == "home" else "home"
            d = games[["game_id"]].copy()
            d["team"], d["opp"] = games[side].to_numpy(), games[opp].to_numpy()
            d["row"] = 2 * np.arange(G) + r
            d["is_home"] = float(side == "home")
            rows.append(d)
        rw = pd.concat(rows).sort_values("row").reset_index(drop=True).merge(tg, on=["game_id", "team"], how="left").fillna(0.0)
        rw = rw.sort_values("row").reset_index(drop=True)
        self.N = len(rw)
        self.team = rw["team"].map(self.tix).to_numpy()
        self.opp = rw["opp"].map(self.tix).to_numpy()
        gi = np.repeat(np.arange(G), 2)
        self.row_game = gi
        self.batch, self.season = self.g_batch[gi], self.g_season[gi]
        self.home = (rw["is_home"].to_numpy() * (~self.g_neutral[gi])).astype(float)
        self.stats = {u: {s: rw[f"{s}_{'pr'[u]}"].to_numpy(float) for s in STAT} for u in (0, 1)}
        self.n = np.vstack([self.stats[0]["n"], self.stats[1]["n"]])
        self.y_real = np.vstack([self.stats[u]["s_all"] / np.maximum(self.stats[u]["n"], 1) for u in (0, 1)])
        # first row of each batch
        self.b_start = np.searchsorted(self.batch, np.arange(self.nb + 1))
        self.g_start = np.searchsorted(self.g_batch, np.arange(self.nb + 1))

    # ---- luck removal -------------------------------------------------

    def _hist(self, key: np.ndarray, vals: np.ndarray) -> np.ndarray:
        """For every row, the sum of `vals` over earlier rows with the same key in this season and the HIST_SEASONS before."""
        out = np.zeros_like(vals)
        order = np.argsort(key, kind="stable")
        ks = key[order]
        cuts = np.flatnonzero(np.r_[True, ks[1:] != ks[:-1], True])
        for a, b in zip(cuts[:-1], cuts[1:]):
            idx = order[a:b]
            cs = np.vstack([np.zeros((1, vals.shape[1])), np.cumsum(vals[idx], axis=0)])
            se = self.season[idx]
            first = np.searchsorted(se, se - HIST_SEASONS, side="left")
            out[idx] = cs[np.arange(len(idx))] - cs[first]
        return out

    def _league(self, vals: np.ndarray) -> np.ndarray:
        """For every row, the league-wide sum of `vals` over all rows in earlier weeks."""
        per_batch = np.add.reduceat(vals, self.b_start[:-1], axis=0)
        ex = np.vstack([np.zeros((1, vals.shape[1])), np.cumsum(per_batch, axis=0)])[:-1]
        return ex[self.batch]

    def adjusted(self, k: float, luck: bool = True) -> dict:
        """Luck-adjusted EPA per play for the offense view (y_off) and the defense view (y_def) of every row, per unit, plus plays n.
        With luck=False both are the realized EPA per play."""
        if not luck:
            return {"y_off": self.y_real.copy(), "y_def": self.y_real.copy(), "n": self.n}
        y_off, y_def = np.zeros((2, self.N)), np.zeros((2, self.N))
        for u in (0, 1):
            S = self.stats[u]
            M = np.column_stack([S[s] for s in STAT])
            lg = self._league(M)
            li = {s: lg[:, i] for i, s in enumerate(STAT)}
            with np.errstate(divide="ignore", invalid="ignore"):
                d = DEFAULTS
                lg_int = np.where(li["n"] > 2000, li["n_int"] / li["n"], d["int_rate"]) if u == 0 else np.zeros(self.N)
                e_int = np.where(li["n_int"] > 50, li["s_int"] / li["n_int"], d["e_int"])
                p_fl = np.where(li["n_fum"] > 50, li["n_fl"] / li["n_fum"], d["p_fl"])
                e_fl = np.where(li["n_fl"] > 20, li["s_fl"] / li["n_fl"], d["e_fl"])
                e_fk = np.where(li["n_fum"] - li["n_fl"] > 20, li["s_fk"] / (li["n_fum"] - li["n_fl"]), d["e_fk"])
                lg_rz = np.where(li["n_rz"] > 200, li["s_rz"] / li["n_rz"], d["rz_pass" if u == 0 else "rz_rush"])
            fum = S["n_fum"] * (p_fl * e_fl + (1 - p_fl) * e_fk)
            for side, key in (("off", self.team), ("def", self.opp)):
                # defense view: the history of the plays this team's defense faced, i.e. rows where it was the opponent
                H = self._hist(key, M)
                hi = {s: H[:, i] for i, s in enumerate(STAT)}
                r_hat = (hi["n_int"] + k * lg_int) / (hi["n"] + k) if u == 0 else np.zeros(self.N)
                m_hat = (hi["s_rz"] + k * lg_rz) / (hi["n_rz"] + k)
                total = S["s_base"] + S["n_rz"] * m_hat + fum + S["n"] * r_hat * e_int
                count = S["n"] - S["n_int"] + S["n"] * r_hat
                y = np.where(count > 0, total / np.maximum(count, 1e-9), 0.0)
                (y_off if side == "off" else y_def)[u] = y
        return {"y_off": y_off, "y_def": y_def, "n": self.n}

    # ---- league plays per game, as of each batch --------------------------------

    def plays_per_game(self) -> np.ndarray:
        """(nb, 2): league-average plays per team-game for pass and rush, using games before each batch (a default before any)."""
        out = np.zeros((self.nb, 2))
        tot, cnt = np.zeros(2), 0
        for b in range(self.nb):
            out[b] = tot / cnt if cnt else np.array([33.0, 24.0])
            lo, hi = self.b_start[b], self.b_start[b + 1]
            tot += self.n[:, lo:hi].sum(axis=1)
            cnt += hi - lo
        return out


# --------------------------------------------------------------------------- 4: weekly ridge


def _age(P: Panel, b: int, rows: np.ndarray) -> np.ndarray:
    return (b - P.batch[rows]) + OFFSEASON_AGE * (P.batch_season[b] - P.season[rows])


def ridge_weekly(P: Panel, adj: dict, lams: list[float], half_life: float, first_batch: int = 1) -> dict:
    """For every batch b, ridge fits on the rows of earlier batches (this season and two before), one per unit and lambda.

    Returns {lam: dict(mu (nb,2), beta (nb,2), o (nb,2,T), d (nb,2,T), s2 (nb,2))}. Row r is explained by
    y = mu + beta x home + o[team] + d[opp]; weights are plays x 0.5^(age / half_life)."""
    T, nb = P.T, P.nb
    out = {lam: dict(mu=np.zeros((nb, 2)), beta=np.zeros((nb, 2)), o=np.zeros((nb, 2, T)), d=np.zeros((nb, 2, T)),
                     s2=np.full((nb, 2), DEFAULTS["s2"])) for lam in lams}
    idx_all = np.arange(P.N)
    pen_mask = np.r_[0.0, 0.0, np.ones(2 * T)]
    for b in range(first_batch, nb):
        sel = idx_all[(P.batch < b) & (P.season >= P.batch_season[b] - HIST_SEASONS)]
        if len(sel) < 40:
            continue
        X = np.zeros((len(sel), 2 + 2 * T))
        X[:, 0] = 1.0
        X[:, 1] = P.home[sel]
        X[np.arange(len(sel)), 2 + P.team[sel]] = 1.0
        X[np.arange(len(sel)), 2 + T + P.opp[sel]] = 1.0
        dec = np.ones(len(sel)) if np.isinf(half_life) else 0.5 ** (_age(P, b, sel) / half_life)
        for u in (0, 1):
            w = adj["n"][u, sel] * dec
            y = adj["y_off"][u, sel]
            XtW = X.T * w
            A = XtW @ X
            rhs = XtW @ y
            for lam in lams:
                theta = np.linalg.solve(A + np.diag(lam * pen_mask + 1e-8), rhs)
                r = y - X @ theta
                res = out[lam]
                res["mu"][b, u], res["beta"][b, u] = theta[0], theta[1]
                res["o"][b, u], res["d"][b, u] = theta[2:2 + T], theta[2 + T:]
                res["s2"][b, u] = float((dec * adj["n"][u, sel] * r * r).sum() / dec.sum())
    return out


# --------------------------------------------------------------------------- 5: Kalman strength


def kalman_strength(P: Panel, adj: dict, ridge: dict, lam: float, q: float, rho: float, nbar: np.ndarray) -> dict:
    """Per-game pre-game strengths. Units: pass offense, rush offense, pass defense, rush defense (defense = EPA allowed above average).

    Returns xm, xt (G,): points-scale strength differences used by the score maps, and the state history `m` at each batch start (nb, 4, T)."""
    T = P.T
    m, v = np.zeros((4, T)), np.zeros((4, T))
    xm, xt = np.full(P.G, np.nan), np.full(P.G, np.nan)
    states = np.zeros((P.nb, 4, T))
    unit_of = np.array([0, 1, 0, 1])
    last_season = None
    for b in range(P.nb):
        s2 = ridge["s2"][b]
        v0 = np.array([s2[0], s2[1], s2[0], s2[1]]) / lam
        if last_season is None:
            v[:] = v0[:, None]
        elif P.batch_season[b] != last_season:
            m *= rho
            v = rho ** 2 * v + (1 - rho ** 2) * v0[:, None]
        last_season = P.batch_season[b]
        states[b] = m
        g0, g1 = P.g_start[b], P.g_start[b + 1]
        h, a = P.g_home[g0:g1], P.g_away[g0:g1]
        net = m[:2] - m[2:]                # offense minus allowed, per team, pass and rush
        tot = m[:2] + m[2:]
        npl = nbar[b]
        xm[g0:g1] = ((net[:, h] - net[:, a]) * npl[:, None]).sum(axis=0)
        xt[g0:g1] = ((tot[:, h] + tot[:, a]) * npl[:, None]).sum(axis=0)
        r0, r1 = P.b_start[b], P.b_start[b + 1]
        if r1 == r0 or b == 0:
            continue
        rows = np.arange(r0, r1)
        tm, op, hm = P.team[rows], P.opp[rows], P.home[rows]
        for u in (0, 1):
            nn = np.maximum(P.n[u, rows], 1.0)
            R = ridge["s2"][b, u] / nn
            qg = q * ridge["s2"][b, u] / max(nbar[b, u], 1.0)
            base = ridge["mu"][b, u] + ridge["beta"][b, u] * hm
            # offense state of the row's team, defense state of its opponent
            for unit, who, z in ((u, tm, adj["y_off"][u, rows] - base - ridge["d"][b, u][op]),
                                 (2 + u, op, adj["y_def"][u, rows] - base - ridge["o"][b, u][tm])):
                vv = v[unit, who] + qg
                K = vv / (vv + R)
                m[unit, who] += K * (z - m[unit, who])
                v[unit, who] = (1 - K) * vv
    return {"xm": xm, "xt": xt, "states": states}


# --------------------------------------------------------------------------- 6: strength to scores


def _decay(P: Panel, b: int, gidx: np.ndarray, half_life: float) -> np.ndarray:
    if np.isinf(half_life):
        return np.ones(len(gidx))
    age = (b - P.g_batch[gidx]) + OFFSEASON_AGE * (P.batch_season[b] - P.g_season[gidx])
    return 0.5 ** (age / half_life)


def _wls(X: np.ndarray, y: np.ndarray, w: np.ndarray):
    A = (X.T * w) @ X + 1e-9 * np.eye(X.shape[1])
    Ainv = np.linalg.inv(A)
    beta = Ainv @ (X.T * w) @ y
    r = y - X @ beta
    sig2 = float((w * r * r).sum() / max(w.sum() - X.shape[1], 1.0))
    return beta, Ainv, sig2


def score_maps(P: Panel, xm: np.ndarray, xt: np.ndarray, half_life: float, first_batch: int, canary: np.ndarray | None = None) -> dict:
    """Weekly weighted least squares from strength to scores. Margin = h x (not neutral) + b x xm; total = c + d x xt.
    Games in batches before `b`, from season MAP_FROM on and within three seasons, with weight 0.5^(age/half_life).
    `canary`, if given, is added to the margin design as an extra column (the leak test)."""
    mu_m, sd_m = np.full(P.G, np.nan), np.full(P.G, np.nan)
    mu_t, sd_t = np.full(P.G, np.nan), np.full(P.G, np.nan)
    gall = np.arange(P.G)
    for b in range(first_batch, P.nb):
        tgt = gall[P.g_start[b]:P.g_start[b + 1]]
        if len(tgt) == 0:
            continue
        sel = gall[(P.g_batch < b) & (P.g_season >= max(MAP_FROM, P.batch_season[b] - HIST_SEASONS)) & np.isfinite(xm)]
        if len(sel) < 60:
            continue
        w = _decay(P, b, sel, half_life)
        cols = [xm, (~P.g_neutral).astype(float)] + ([canary] if canary is not None else [])
        Xm = np.column_stack([c[sel] for c in cols])
        Xmt = np.column_stack([c[tgt] for c in cols])
        beta, Ainv, sig2 = _wls(Xm, P.y_m[sel], w)
        mu_m[tgt] = Xmt @ beta
        sd_m[tgt] = np.sqrt(sig2 * (1 + np.einsum("ij,jk,ik->i", Xmt, Ainv, Xmt)))
        Xt = np.column_stack([np.ones(len(sel)), xt[sel]])
        Xtt = np.column_stack([np.ones(len(tgt)), xt[tgt]])
        beta, Ainv, sig2 = _wls(Xt, P.y_t[sel], w)
        mu_t[tgt] = Xtt @ beta
        sd_t[tgt] = np.sqrt(sig2 * (1 + np.einsum("ij,jk,ik->i", Xtt, Ainv, Xtt)))
    return {"mu_m": mu_m, "sd_m": np.maximum(sd_m, SD_FLOOR), "mu_t": mu_t, "sd_t": np.maximum(sd_t, SD_FLOOR)}


# --------------------------------------------------------------------------- scores and the as-of check


def crps_normal(y, mu, sd):
    z = (np.asarray(y) - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def check_asof(P: Panel, source_batches_for: np.ndarray | None = None) -> dict:
    """The decision-time rule: every game feeding a target game ended (kickoff + 4h) at least 12h before the target's kickoff.

    By construction a target in batch b uses games of batches < b. This measures, for every target game, the latest kickoff among all games
    of earlier batches and counts the targets for which the gap is too small. `source_batches_for` (per game) overrides the batch a
    target's sources are drawn from; passing a game's own batch (the leak canary) must produce violations."""
    sb = P.g_batch - 1 if source_batches_for is None else source_batches_for
    latest = np.full(P.G, np.datetime64("NaT"), dtype="datetime64[ns]")
    batch_latest = np.array([P.g_kick[P.g_start[b]:P.g_start[b + 1]].max() if P.g_start[b + 1] > P.g_start[b] else np.datetime64("NaT")
                             for b in range(P.nb)])
    ok = sb >= 0
    latest[ok] = batch_latest[sb[ok]]
    need = np.timedelta64(GAME_HOURS + GAP_HOURS, "h")
    viol = ok & (latest + need > P.g_kick)
    return {"targets": int(ok.sum()), "violations": int(viol.sum()), "violating_games": [P.games["game_id"].iloc[i] for i in np.flatnonzero(viol)[:10]]}
