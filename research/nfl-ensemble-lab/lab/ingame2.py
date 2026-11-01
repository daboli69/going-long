"""In-game tracker v2: player baseline from snap counts across teams, share prior fitted by a hierarchical Bayesian model (PyMC), and a game-state win model.

Pre-registered in docs/INGAME_PREREG_V2.md before anything here was fitted. Routes are not available from any free source; the baseline uses snaps (snap_counts)
and targets or carries per game played. For past seasons "inactive" means no offensive snap in the game's snap counts; the live tracker uses the posted list.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import ingame as G

RAW = G.RAW
HISTORY = 8


def snap_table(seasons) -> pd.DataFrame:
    """(gid, team, pid, pos, snaps, pct) for every player with snaps, ids mapped to gsis through the players table."""
    pl = pd.read_parquet(RAW / "players.parquet", columns=["gsis_id", "pfr_id"]).dropna()
    frames = [pd.read_parquet(RAW / f"snap_counts_{s}.parquet") for s in seasons]
    sn = pd.concat(frames, ignore_index=True)
    sn = sn[sn["game_type"] == "REG"].merge(pl, left_on="pfr_player_id", right_on="pfr_id", how="inner")
    sn = sn.rename(columns={"game_id": "gid", "gsis_id": "pid", "position": "pos", "offense_snaps": "snaps", "offense_pct": "pct"})
    return sn[["gid", "team", "pid", "pos", "snaps", "pct", "season", "week"]]


def group_of(fam: str, pos: str, rank: int) -> str:
    r = min(rank, 3)
    if fam == "pass":
        return "QB"
    if fam == "rush":
        return ("RB" if pos == "RB" else "QB" if pos == "QB" else "WR") + str(min(r, 2))
    return {"WR": "WR", "TE": "TE", "RB": "RB"}.get(pos, "WR") + str(r)


def baselines2(e: pd.DataFrame, tv: pd.DataFrame, snaps: pd.DataFrame, pool: dict, pool_catch: dict, m_eff: dict, m_catch: float) -> dict[str, pd.DataFrame]:
    """One row per player-game in which he played: his share of the team's attempts over his last eight games played (any team), efficiency shrunk to the
    pool, and his role group. Rows also carry the game's own opportunities and team attempts, for fitting and scoring only, never as inputs."""
    out = {}
    tvx = tv.set_index(["gid", "team"])
    order = tv[["gid", "season", "week"]].drop_duplicates().sort_values(["season", "week", "gid"]).reset_index(drop=True)
    kidx = dict(zip(order["gid"], range(len(order))))
    played = snaps[snaps["snaps"] > 0][["gid", "team", "pid", "pos", "pct"]]
    for fam in G.FAMILIES:
        kind_col = "n_rush" if fam == "rush" else "n_pass"
        rows = G._fam_rows(e, fam)
        g = rows.groupby(["gid", "team", "pid"]).agg(O=("t", "size"), Y=("yards", "sum"), C=("catch", "sum")).reset_index()
        pg = played.merge(g, on=["gid", "team", "pid"], how="left").fillna({"O": 0, "Y": 0.0, "C": 0.0})
        pg["V"] = [tvx[kind_col].get((a, b), np.nan) for a, b in zip(pg["gid"], pg["team"])]
        pg = pg.dropna(subset=["V"])
        pg["k"] = pg["gid"].map(kidx)
        pg = pg.dropna(subset=["k"])
        po, pc = float(pool[fam].mean()), float(pool_catch[fam])
        recs = []
        for pid, h in pg.groupby("pid"):
            h = h.sort_values("k").reset_index(drop=True)
            O, Y, C, V = (h[c].to_numpy(dtype=float) for c in ("O", "Y", "C", "V"))
            cO, cY, cC, cV = (np.concatenate([[0.0], np.cumsum(x)]) for x in (O, Y, C, V))
            for i in range(4, len(h)):
                lo = max(0, i - HISTORY)
                n = i - lo
                if (cO[i] - cO[lo]) / n < G.THRESH[fam]:
                    continue
                o, y, c, v = cO[i] - cO[lo], cY[i] - cY[lo], cC[i] - cC[lo], cV[i] - cV[lo]
                recs.append((h.at[i, "gid"], h.at[i, "team"], pid, h.at[i, "pos"], o / n, o / max(v, 1.0), (y + m_eff[fam] * po) / (o + m_eff[fam]),
                             (c + m_catch * pc) / (o + m_catch), O[i], V[i], Y[i]))
        b = pd.DataFrame(recs, columns=["gid", "team", "pid", "pos", "mu_O", "share", "ypo", "cr", "O_game", "A_game", "Y_game"])
        b["rank"] = b.groupby(["gid", "team"])["share"].rank(ascending=False, method="first").astype(int)
        b["grp"] = [group_of(fam, p, r) for p, r in zip(b["pos"], b["rank"])]
        out[fam] = b
    return out


def fit_hier(df: pd.DataFrame, seed: int = 0, n: int = 6000, draws: int = 700) -> dict:
    """Partially pooled calibration of the pregame share and its prior strength, per role group: O_game ~ BetaBinomial(A_game, p*kappa, (1-p)*kappa),
    logit p = a_g + b_g * logit(trailing share). Returns posterior means and convergence checks."""
    import arviz as az
    import pymc as pm
    d = df[(df["A_game"] > 0) & (df["O_game"] <= df["A_game"])]
    d = d.sample(min(len(d), n), random_state=seed).reset_index(drop=True)
    gi, groups = pd.factorize(d["grp"])
    s = np.clip(d["share"].to_numpy(), 1e-3, 0.995)
    x = np.log(s / (1 - s))
    ng = len(groups)
    with pm.Model():
        mu_a, sd_a = pm.Normal("mu_a", 0, 0.5), pm.HalfNormal("sd_a", 0.5)
        mu_b, sd_b = pm.Normal("mu_b", 1, 0.3), pm.HalfNormal("sd_b", 0.3)
        mu_k, sd_k = pm.Normal("mu_k", np.log(30), 1.0), pm.HalfNormal("sd_k", 0.7)
        za, zb, zk = pm.Normal("za", 0, 1, shape=ng), pm.Normal("zb", 0, 1, shape=ng), pm.Normal("zk", 0, 1, shape=ng)     # non-centred: group effects as scaled offsets
        a, b, lk = pm.Deterministic("a", mu_a + sd_a * za), pm.Deterministic("b", mu_b + sd_b * zb), pm.Deterministic("lk", mu_k + sd_k * zk)
        p = pm.math.sigmoid(a[gi] + b[gi] * x)
        kap = pm.math.exp(lk[gi])
        pm.BetaBinomial("O", n=d["A_game"].to_numpy().astype(int), alpha=p * kap, beta=(1 - p) * kap, observed=d["O_game"].to_numpy().astype(int))
        idata = pm.sample(draws, tune=1000, chains=2, target_accept=0.95, progressbar=False, random_seed=seed)
    post = idata.posterior
    summ = az.summary(idata, var_names=["a", "b", "lk"])
    return {"groups": {g: {"a": float(post["a"].mean(("chain", "draw")).values[i]), "b": float(post["b"].mean(("chain", "draw")).values[i]),
                           "kappa": float(np.exp(post["lk"].values[:, :, i]).mean())} for i, g in enumerate(groups)},
            "rows": int(len(d)), "max_rhat": float(summ["r_hat"].max()), "min_ess": float(summ["ess_bulk"].min())}


def calibrated_share(h: dict, grp: str, share: float) -> tuple[float, float]:
    """(calibrated pregame share, prior strength) for a role group; the raw share and the median strength for a group never seen in fitting."""
    g = h["groups"].get(grp)
    if g is None:
        return share, float(np.median([v["kappa"] for v in h["groups"].values()]))
    s = float(np.clip(share, 1e-3, 0.995))
    return 1 / (1 + np.exp(-(g["a"] + g["b"] * np.log(s / (1 - s))))), g["kappa"]


# --------------------------------------------------------------------------- win model

WP_FEATURES = ["margin", "secs", "down", "ydstogo", "yl", "poss_home", "to_poss", "to_def", "spread", "margin_z"]


def wp_frame(plays: pd.DataFrame) -> pd.DataFrame:
    p = plays[plays["posteam"].notna() & plays["total_home_score"].notna() & plays["game_seconds_remaining"].notna() & (plays["qtr"] <= 4)].copy()
    margin = p["total_home_score"] - p["total_away_score"]
    secs = p["game_seconds_remaining"].clip(lower=0)
    return pd.DataFrame({"gid": p["game_id"], "season": p["season"], "t": G.GAME - secs, "margin": margin, "secs": secs, "down": p["down"].fillna(0),
                         "ydstogo": p["ydstogo"].fillna(0), "yl": p["yardline_100"].fillna(50), "poss_home": (p["posteam"] == p["home_team"]).astype(int),
                         "to_poss": p["posteam_timeouts_remaining"].fillna(3), "to_def": p["defteam_timeouts_remaining"].fillna(3), "spread": p["spread_line"],
                         "margin_z": margin / np.sqrt(secs + 30.0), "y": (p["result"] > 0).astype(float), "tie": p["result"] == 0, "nfl_wp": p["home_wp"]})


def fit_wp(train: pd.DataFrame, calib: pd.DataFrame):
    """Gradient-boosted game-state model for a home win, then isotonic calibration on a later season."""
    from sklearn.isotonic import IsotonicRegression
    from xgboost import XGBClassifier
    tr = train[~train["tie"]].dropna(subset=WP_FEATURES)
    m = XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.9, min_child_weight=50, eval_metric="logloss", n_jobs=2)
    m.fit(tr[WP_FEATURES], tr["y"])
    ca = calib[~calib["tie"]].dropna(subset=WP_FEATURES)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.001, y_max=0.999).fit(m.predict_proba(ca[WP_FEATURES])[:, 1], ca["y"])
    return m, iso


def wp_predict(model, iso, X: pd.DataFrame, calibrated: bool = True) -> np.ndarray:
    raw = model.predict_proba(X[WP_FEATURES])[:, 1]
    return iso.predict(raw) if calibrated else raw
