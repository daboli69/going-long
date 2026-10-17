"""Phase 7 snap-based player model (SAPM): a labelled SUBSTITUTE for the play-level RAPM.

Why: nflverse has not published 2026 play participation, so the Phase 5 RAPM cannot see any 2026
play and its player values stop at 2025. PFR snap counts ARE published for 2026.

Model (per team-game offense, weighted by plays):
    epa_per_play(team t, game g) = a + h*home + sum_i share_off(i, g) * off_i + sum_j share_def(j, g) * def_j
  share = snap share of each player in that game (verified PFR snap counts, never inferred);
  off_i = EPA/play added on offense, def_j = EPA/play allowed on defense (negative is good).
This is coarser than RAPM: it sees who played how much in each game, not who was on the field
for each play, so values are shrunk harder and players who always share the field are not separable.
Fits are as-of: each week's fit uses only games before that week's first kickoff (current season
plus prior seasons at weights 0.6 / 0.35). The penalty is chosen once on 2016-17 -> 2018.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import cg

from .config import CACHE_DIR
from .players import SEASON_WEIGHTS, UNITS, _positions, snap_shares

META = CACHE_DIR / "snap_model.json"
LAMBDA_GRID = (1.0, 3.0, 10.0, 30.0, 100.0)
LOW_GAMES = 3.0
PLAY_SCALE = 63.0               # fixed penalty scale (typical plays per team-game). Must NOT be computed from the
                                # data: a data mean would include future games (caught by the readiness leakage gate)                 # summed snap share below this = low-information player


def team_rows(games: pd.DataFrame, tstats: pd.DataFrame, shares: pd.DataFrame) -> pd.DataFrame:
    g = games[["game_id", "home_team", "away_team", "kickoff_utc", "season"]]
    t = tstats[["game_id", "team", "epa_pp", "plays"]].merge(g, on="game_id")
    t["opp"] = np.where(t["team"] == t["home_team"], t["away_team"], t["home_team"])
    t["home"] = (t["team"] == t["home_team"]).astype(float)
    have = set(zip(shares["game_id"], shares["team"]))
    t = t[[(a, b) in have and (a, c) in have for a, b, c in zip(t["game_id"], t["team"], t["opp"])]]
    return t.dropna(subset=["epa_pp"]).sort_values("kickoff_utc").reset_index(drop=True)


class SAPM:
    def __init__(self, rows: pd.DataFrame, shares: pd.DataFrame, lam: float):
        self.rows, self.lam = rows, lam
        ids = sorted(shares["gsis_id"].unique())
        self.pid = {p: i for i, p in enumerate(ids)}
        self.P = len(ids)
        off = shares[shares["offense_pct"] > 0]
        de = shares[shares["defense_pct"] > 0]
        ri = {(g, t): i for i, (g, t, o) in enumerate(zip(rows["game_id"], rows["team"], rows["opp"]))}
        ro = {(g, o): i for i, (g, t, o) in enumerate(zip(rows["game_id"], rows["team"], rows["opp"]))}
        r1 = [ri.get((g, t)) for g, t in zip(off["game_id"], off["team"])]
        r2 = [ro.get((g, t)) for g, t in zip(de["game_id"], de["team"])]
        m1 = np.array([x is not None for x in r1])
        m2 = np.array([x is not None for x in r2])
        rr = np.r_[np.array(r1, dtype=object)[m1].astype(int), np.array(r2, dtype=object)[m2].astype(int)]
        cc = np.r_[off["gsis_id"].map(self.pid).to_numpy()[m1], self.P + de["gsis_id"].map(self.pid).to_numpy()[m2]]
        vv = np.r_[off["offense_pct"].to_numpy()[m1], de["defense_pct"].to_numpy()[m2]]
        n = len(rows)
        Xp = sp.csr_matrix((vv, (rr, cc)), shape=(n, 2 * self.P))
        self.X = sp.hstack([Xp, sp.csr_matrix(np.c_[np.ones(n), rows["home"].to_numpy()])]).tocsr()
        self.K = self.X.shape[1]
        self.y = rows["epa_pp"].to_numpy(float)
        self.w = rows["plays"].to_numpy(float)
        self.pen = np.r_[np.full(2 * self.P, lam), [1e-6, 1e-6]]

    def _block(self, mask):
        Xb = self.X[mask]
        W = sp.diags(self.w[mask])
        return (Xb.T @ W @ Xb).tocsr(), Xb.T @ (self.w[mask] * self.y[mask])

    def solve(self, A, b, x0=None):
        A = A + sp.diags(self.pen * PLAY_SCALE)
        beta, _ = cg(A, b, x0=x0, M=sp.diags(1.0 / A.diagonal()), maxiter=500, rtol=1e-7)
        return beta

    def fit_schedule(self, cutoffs: pd.DataFrame, progress=print) -> dict:
        kick = self.rows["kickoff_utc"].to_numpy()
        seas = self.rows["season"].to_numpy()
        out, beta, tot = {}, None, {}
        for season, grp in cutoffs.groupby("season", sort=True):
            for lag in (1, 2):
                if season - lag not in tot and (seas == season - lag).any():
                    tot[season - lag] = self._block(seas == season - lag)
            for r in grp.sort_values("cutoff_utc").itertuples(index=False):
                cur = (seas == season) & (kick < r.cutoff_utc)
                A, b = self._block(cur) if cur.any() else (sp.csr_matrix((self.K, self.K)), np.zeros(self.K))
                for lag in (1, 2):
                    if season - lag in tot:
                        A = A + SEASON_WEIGHTS[lag] * tot[season - lag][0]
                        b = b + SEASON_WEIGHTS[lag] * tot[season - lag][1]
                if not b.any():
                    continue
                beta = self.solve(A, b, beta)
                hist = (kick < r.cutoff_utc) & (seas >= season - 2)
                ex = np.asarray(abs(self.X[hist][:, : 2 * self.P]).sum(axis=0)).ravel()
                out[(int(season), int(r.week))] = {"off": beta[: self.P].copy(), "def": beta[self.P: 2 * self.P].copy(),
                                                   "exp_off": ex[: self.P], "exp_def": ex[self.P:], "cutoff": r.cutoff_utc}
            progress(f"  snap model fits for {season}: {len(grp)} weeks")
        return out


def choose_lambda(rows, shares, progress=print) -> tuple[float, dict]:
    """Development-only: fit 2016-17, predict 2018 team-game EPA/play (play-weighted MSE)."""
    sub = rows[rows["season"].between(2016, 2018)].reset_index(drop=True)
    tr = (sub["season"] < 2018).to_numpy()
    scores = {}
    for lam in LAMBDA_GRID:
        m = SAPM(sub, shares, lam)
        beta = m.solve(*m._block(tr))
        pred = m.X[~tr] @ beta
        scores[lam] = float(np.average((m.y[~tr] - pred) ** 2, weights=m.w[~tr]))
    best = min(scores, key=scores.get)
    progress(f"  snap model penalty chosen on 2016-17 -> 2018: {best} ({scores})")
    return best, scores


def build_features(games: pd.DataFrame, tstats: pd.DataFrame, valid_inj: pd.DataFrame, inj_team: pd.DataFrame,
                   seasons: list, progress=print) -> pd.DataFrame:
    """One row per (game_id, team) with p7s_* columns, pregame only (same lineup and injury rules as Phase 5)."""
    shares = snap_shares(games, seasons)
    rows = team_rows(games[games["season"] >= 2016], tstats, shares)
    lam, scores = choose_lambda(rows, shares, progress)
    model = SAPM(rows, shares, lam)
    cut = games[games["season"] >= 2016].groupby(["season", "week"])["kickoff_utc"].min().reset_index(name="cutoff_utc")
    fits = model.fit_schedule(cut, progress)
    pos = _positions()
    by_team = {t: d.sort_values("kickoff_utc") for t, d in shares.groupby("team")}
    vi = valid_inj if len(valid_inj) else pd.DataFrame(columns=["game_id", "team", "gsis_id", "report_status"])
    status = {(g, t, p): s for g, t, p, s in zip(vi["game_id"], vi["team"], vi["gsis_id"], vi["report_status"])}
    avail = {(g, t): a for g, t, a in zip(inj_team["game_id"], inj_team["team"], inj_team["inj_report_available"])}
    last_row = rows["kickoff_utc"].max()
    out = []
    for g in games[games["season"] >= 2016].itertuples(index=False):
        fit = fits.get((g.season, g.week))
        for team in (g.home_team, g.away_team):
            r = {"game_id": g.game_id, "team": team}
            d = by_team.get(team)
            prior = d[d["kickoff_utc"] < g.kickoff_utc] if d is not None else None
            if fit is None or prior is None or prior.empty:
                out.append(r)
                continue
            last = prior["game_id"].drop_duplicates().iloc[-4:]
            sh = prior[prior["game_id"].isin(last)].groupby("gsis_id")[["offense_pct", "defense_pct"]].sum() / len(last)
            known = avail.get((g.game_id, team), 0) == 1
            outs = {p for p in sh.index if status.get((g.game_id, team, p)) in ("Out", "Doubtful")} if known else set()
            for side, col in (("off", "offense_pct"), ("def", "defense_pct")):
                s = sh[col][sh[col] > 0]
                if s.empty:
                    continue
                idx = [model.pid.get(p) for p in s.index]
                v = np.array([fit[side][i] if i is not None else 0.0 for i in idx])
                e = np.array([fit[f"exp_{side}"][i] if i is not None else 0.0 for i in idx])
                grp = [pos.get(p, "OTH") for p in s.index]
                a = s.to_numpy()
                pv = v.copy()
                for j, p in enumerate(s.index):
                    if p in outs:
                        bench = [(a[k], v[k]) for k in range(len(a)) if grp[k] == grp[j] and a[k] < 0.5 and s.index[k] not in outs]
                        pv[j] = np.average([b[1] for b in bench], weights=[b[0] for b in bench]) if bench else 0.0
                r[f"p7s_{side}_full"] = float(a @ v)
                r[f"p7s_{side}_proj"] = float(a @ pv)
                r[f"p7s_{side}_loss"] = r[f"p7s_{side}_full"] - r[f"p7s_{side}_proj"]
                r[f"p7s_{side}_lowinfo"] = float(a[e < LOW_GAMES].sum() / a.sum())
                for u, gs in UNITS.items():
                    if (side == "off") == (u in ("QB", "OL", "SKILL")):
                        m = np.array([x in gs for x in grp])
                        r[f"p7s_unit_{u}"] = float(a[m] @ pv[m]) if m.any() else np.nan
            r["p7s_staleness_days"] = float(max((g.kickoff_utc - last_row).days, 0))
            out.append(r)
    META.write_text(json.dumps({"lambda": lam, "lambda_scores": {str(k): v for k, v in scores.items()},
                                "team_games": int(len(rows)), "players": model.P, "fits": len(fits),
                                "last_game": str(last_row), "label": "snap-share approximation (not play participation)"}, indent=2))
    return pd.DataFrame(out)
