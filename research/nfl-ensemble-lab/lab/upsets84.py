"""Phase 8.4: high-variance underdogs (V) and early line movement toward the underdog (S).
Exactly as pre-registered in docs/PHASE8_4_PREREGISTRATION.md. Lab-only research; one historical look."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

from . import metrics as Mx
from .config import ARTIFACTS_DIR

OUT = ARTIFACTS_DIR / "phase84"
TRAITS = ["explosive_rate", "d_turnovers", "d_sack_rate", "pass_rate"]


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _test(y, base_logit, z, seasons, n_season_min=40):
    """One-sided LR test of a negative coefficient on z given base_logit; per-season signs; effect at a 65% favourite."""
    X0, X1 = base_logit.reshape(-1, 1), np.c_[base_logit, z]
    m0 = LogisticRegression(C=1e6, max_iter=2000).fit(X0, y)
    m1 = LogisticRegression(C=1e6, max_iter=2000).fit(X1, y)
    lr = 2 * len(y) * (Mx.log_loss(y, m0.predict_proba(X0)[:, 1]) - Mx.log_loss(y, m1.predict_proba(X1)[:, 1]))
    coef = float(m1.coef_[0][1])
    p2 = float(stats.chi2.sf(max(lr, 0), 1))
    p1 = p2 / 2 if coef < 0 else 1 - p2 / 2
    b0, b = m1.intercept_[0], m1.coef_[0]
    L = np.log(0.65 / 0.35)
    signs, n = 0, 0
    for s in np.unique(seasons):
        k = seasons == s
        if k.sum() < n_season_min or np.std(z[k]) == 0:
            continue
        mm = LogisticRegression(C=1e6, max_iter=2000).fit(np.c_[base_logit[k], z[k]], y[k])
        signs += int(mm.coef_[0][1] < 0)
        n += 1
    return {"games": int(len(y)), "coef_per_sd": coef, "p_one_sided": p1, "seasons_with_predeclared_sign": signs, "seasons": n,
            "upset_prob_at_65pct_fav": float(1 - 1 / (1 + np.exp(-(b0 + b[0] * L)))),
            "upset_prob_plus_1sd": float(1 - 1 / (1 + np.exp(-(b0 + b[0] * L + b[1]))))}


def variance_frame() -> pd.DataFrame:
    from .data_pipeline import load_feature_store
    from .specialists.baseline import load_oof
    oof = load_oof()
    oof = oof[oof["season"].between(2018, 2025) & oof["home_win"].notna()]
    fs = load_feature_store().set_index("game_id")
    cols = [f"{s}_blend_{t}" for s in ("home", "away") for t in TRAITS]
    x = oof.join(fs[cols], on="game_id")
    fav_home = (x["p_weighted_average"] >= 0.5).to_numpy()
    for t in TRAITS:
        x[f"dog_{t}"] = np.where(fav_home, x[f"away_blend_{t}"], x[f"home_blend_{t}"])
        x[f"fav_{t}"] = np.where(fav_home, x[f"home_blend_{t}"], x[f"away_blend_{t}"])
    for t in TRAITS:                                              # standardise each trait over all team-games in the window
        both = pd.concat([x[f"dog_{t}"], x[f"fav_{t}"]])
        mu, sd = both.mean(), both.std()
        x[f"z_dog_{t}"], x[f"z_fav_{t}"] = (x[f"dog_{t}"] - mu) / sd, (x[f"fav_{t}"] - mu) / sd
    x["VI_dog"] = x[[f"z_dog_{t}" for t in TRAITS]].mean(axis=1)
    x["VI_fav"] = x[[f"z_fav_{t}" for t in TRAITS]].mean(axis=1)
    x["p_fav"] = np.where(fav_home, x["p_weighted_average"], 1 - x["p_weighted_average"])
    x["fav_won"] = np.where(fav_home, x["home_win"], 1 - x["home_win"])
    return x.dropna(subset=["VI_dog", "VI_fav"])


def movement_frame() -> pd.DataFrame:
    from .data_pipeline import GAMES_TABLE
    from .market81 import MKT_RAW, american_to_prob, novig
    from .specialists.baseline import load_oof
    sb = pd.read_parquet(MKT_RAW / "sbr_lines.parquet")
    g = pd.read_parquet(GAMES_TABLE)[["game_id", "home_score", "away_score", "home_moneyline", "away_moneyline"]]
    x = sb.merge(g, on="game_id").dropna(subset=["home_score", "sbr_home_spread_open", "sbr_home_spread_close"])
    x = x[(x["home_score"] != x["away_score"]) & (x["sbr_home_spread_open"] != 0)]
    fav_home = (x["sbr_home_spread_open"] > 0).to_numpy()
    x["fav_open"] = np.abs(x["sbr_home_spread_open"])
    x["fav_close"] = np.where(fav_home, x["sbr_home_spread_close"], -x["sbr_home_spread_close"])
    x["m"] = x["fav_open"] - x["fav_close"]                      # positive = moved toward the underdog
    x["fav_won"] = np.where(fav_home, x["home_score"] > x["away_score"], x["away_score"] > x["home_score"]).astype(float)
    pc = novig(american_to_prob(x["home_moneyline"]), american_to_prob(x["away_moneyline"]))
    x["p_close_fav"] = np.where(fav_home, pc, 1 - pc)
    oof = load_oof()[["game_id", "p_weighted_average"]]
    x = x.merge(oof, on="game_id", how="left")
    x["p_champ_fav"] = np.where(fav_home, x["p_weighted_average"], 1 - x["p_weighted_average"])
    # opening-line probability: Phi(spread/sigma), sigma fitted walk-forward on earlier seasons' closing spreads
    x["p_open_fav"] = np.nan
    for s in sorted(x["season"].unique()):
        tr, te = x[x["season"] < s], x["season"] == s
        if len(tr) < 200:
            sig = 13.5
        else:
            grid = np.linspace(9, 18, 91)
            sig = grid[int(np.argmin([Mx.log_loss(tr["fav_won"].to_numpy(), np.clip(stats.norm.cdf(tr["fav_close"] / g_), 1e-4, 1 - 1e-4))
                                      for g_ in grid]))]
        x.loc[te, "p_open_fav"] = stats.norm.cdf(x.loc[te, "fav_open"] / sig)
    return x


def run() -> dict:
    res = {}
    v = variance_frame()
    y, lc, seas = v["fav_won"].to_numpy(), _logit(v["p_fav"]), v["season"].to_numpy()
    z = ((v["VI_dog"] - v["VI_dog"].mean()) / v["VI_dog"].std()).to_numpy()
    res["V"] = _test(y, lc, z, seas)
    zd = (v["VI_dog"] - v["VI_fav"])
    res["V_secondary_dog_minus_fav"] = _test(y, lc, ((zd - zd.mean()) / zd.std()).to_numpy(), seas)
    # quintiles of underdog VI (descriptive): observed vs champion-implied upset rate
    q = pd.qcut(v["VI_dog"], 5, labels=["lowest", "low", "mid", "high", "highest"])
    res["V_quintiles"] = v.assign(q=q).groupby("q", observed=True).apply(lambda d: pd.Series({
        "games": len(d), "implied_upset_rate": 1 - d["p_fav"].mean(), "observed_upset_rate": 1 - d["fav_won"].mean()}), include_groups=False).reset_index()
    mv = movement_frame()
    s2 = mv[mv["season"].between(2018, 2021)].dropna(subset=["p_champ_fav"])
    zm = ((s2["m"] - s2["m"].mean()) / s2["m"].std()).to_numpy()
    res["S2"] = _test(s2["fav_won"].to_numpy(), _logit(s2["p_champ_fav"]), zm, s2["season"].to_numpy())
    zm1 = ((mv["m"] - mv["m"].mean()) / mv["m"].std()).to_numpy()
    res["S1_vs_open"] = _test(mv["fav_won"].to_numpy(), _logit(mv["p_open_fav"]), zm1, mv["season"].to_numpy())
    s3 = mv.dropna(subset=["p_close_fav"])
    zm3 = ((s3["m"] - s3["m"].mean()) / s3["m"].std()).to_numpy()
    res["S3_vs_close"] = _test(s3["fav_won"].to_numpy(), _logit(s3["p_close_fav"]), zm3, s3["season"].to_numpy())
    flag = mv[mv["m"] >= 1.5]
    fl = flag.dropna(subset=["p_close_fav"])
    res["flag_table"] = {"games_moved_1p5_toward_dog": int(len(flag)), "share_of_games": float(len(flag) / len(mv)),
                         "dog_win_rate": float(1 - flag["fav_won"].mean()),
                         "implied_by_open": float(1 - flag["p_open_fav"].mean()),
                         "implied_by_champion": float(1 - flag["p_champ_fav"].mean()) if flag["p_champ_fav"].notna().any() else None,
                         "champion_games": int(flag["p_champ_fav"].notna().sum()),
                         "implied_by_close": float(1 - fl["p_close_fav"].mean()),
                         "moved_toward_favourite_dog_win_rate": float(1 - mv[mv["m"] <= -1.5]["fav_won"].mean()),
                         "moved_toward_favourite_implied_by_open": float(1 - mv[mv["m"] <= -1.5]["p_open_fav"].mean()),
                         "moved_toward_favourite_games": int((mv["m"] <= -1.5).sum())}
    # Holm across the two primary tests
    prim = {"V": res["V"]["p_one_sided"], "S2": res["S2"]["p_one_sided"]}
    o = sorted(prim, key=prim.get)
    holm, run_ = {}, 0.0
    for i, k in enumerate(o):
        run_ = max(run_, min(1.0, (len(o) - i) * prim[k]))
        holm[k] = run_
    res["holm"] = holm
    res["passes"] = {"V": bool(holm["V"] < 0.05 and res["V"]["seasons_with_predeclared_sign"] >= 5),
                     "S2": bool(holm["S2"] < 0.05 and res["S2"]["seasons_with_predeclared_sign"] >= 3)}
    res["m_scale_2018_21"] = {"mean": float(s2["m"].mean()), "sd": float(s2["m"].std())}
    OUT.mkdir(parents=True, exist_ok=True)
    res["V_quintiles"].to_csv(OUT / "variance_quintiles.csv", index=False)
    (OUT / "results.json").write_text(json.dumps({k: v_ for k, v_ in res.items() if k != "V_quintiles"}, indent=2, default=str))
    return res


def load() -> dict:
    p = OUT / "results.json"
    if not p.exists():
        return {}
    r = json.loads(p.read_text())
    q = OUT / "variance_quintiles.csv"
    if q.exists():
        r["V_quintiles"] = pd.read_csv(q)
    return r


# --------------------------------------------------------------------------- prospective S2 (registered only because S2 passed)
REGISTERED_AT = "2026-10-18T04:00:00+00:00"
PROSPECTIVE_MIN_GAMES = 128


def register_prospective() -> dict:
    """Written once, never edited. Movement is standardised with the frozen 2018-21 mean/sd from the historical look."""
    p = OUT / "prospective_registration.json"
    if not p.exists():
        r = json.loads((OUT / "results.json").read_text())
        p.write_text(json.dumps({
            "registered_at": REGISTERED_AT, "doc": "docs/PHASE8_4_PREREGISTRATION.md", "id": "S2P",
            "name": "line movement toward the underdog, beyond the champion",
            "data": "archived ESPN/DraftKings odds: opening spread -> latest archived spread retrieved at or before the champion's final-stage forecast",
            "line_favourite": "side favoured by the ESPN opening spread (pick'em openers excluded)",
            "m": "favourite opening spread - favourite latest spread (positive = toward the underdog)",
            "m_scale": r["m_scale_2018_21"],
            "test": "one-sided LR test, negative coefficient on z(m) in logit(P line favourite won) = a + b*logit(champion final p) + c*z(m)",
            "min_games": PROSPECTIVE_MIN_GAMES, "alpha": 0.05,
            "never": "no change to the champion or registered challengers; no variants"}, indent=2))
    return json.loads(p.read_text())


def _espn_spread(v):
    try:
        return float(str(v).replace("+", ""))
    except (TypeError, ValueError):
        return np.nan


def prospective_frame(champ: pd.DataFrame, arc: pd.DataFrame, fs: pd.DataFrame) -> pd.DataFrame:
    """champ: final-stage champion rows (game_id, predicted_at, p, home_win). ESPN home spread is negative when home is favoured."""
    rows = []
    arc = arc.copy()
    arc["retrieved_at"] = pd.to_datetime(arc["retrieved_at"], utc=True)
    for r in champ.itertuples(index=False):
        if r.game_id not in fs.index or pd.isna(r.home_win):
            continue
        g = fs.loc[r.game_id]
        a = arc[(arc["home"] == g["home_team"]) & (arc["away"] == g["away_team"]) & (arc["retrieved_at"] <= r.predicted_at)]
        if a.empty:
            continue
        last = a.iloc[-1]
        o, c = _espn_spread(last.get("home_spread_open")), _espn_spread(last.get("home_spread_close"))
        if np.isnan(o) or np.isnan(c) or o == 0:
            continue
        fav_home = o < 0
        rows.append({"game_id": r.game_id, "m": (abs(o) - (-c if fav_home else c)),
                     "p_champ_fav": r.p if fav_home else 1 - r.p,
                     "fav_won": float(r.home_win if fav_home else 1 - r.home_win)})
    return pd.DataFrame(rows, columns=["game_id", "m", "p_champ_fav", "fav_won"])


def prospective_eval() -> dict:
    from .compare7 import collect
    from .data_pipeline import load_feature_store
    from .market81 import espn_archive
    reg = register_prospective()
    out = {"id": reg["id"], "name": reg["name"], "games": 0, "min_games": reg["min_games"], "status": "accumulating (no conclusion)"}
    df, arc = collect(), espn_archive()
    if df.empty or arc.empty:
        return out
    df["predicted_at"] = pd.to_datetime(df["predicted_at"], utc=True)
    champ = df[(df["version"] == df["version"].iloc[0]) & (df["stage"] == "final") & (df["predicted_at"] >= pd.Timestamp(reg["registered_at"]))]
    champ = champ.drop_duplicates("game_id", keep="last")
    x = prospective_frame(champ, arc, load_feature_store().drop_duplicates("game_id").set_index("game_id"))
    out["games"] = int(len(x))
    flag = x[x["m"] >= 1.5]
    out["flagged_games"] = int(len(flag))
    if len(flag):
        out["flagged_dog_win_rate"] = float(1 - flag["fav_won"].mean())
        out["flagged_champion_implied"] = float(1 - flag["p_champ_fav"].mean())
    if len(x) >= reg["min_games"]:
        z = ((x["m"] - reg["m_scale"]["mean"]) / reg["m_scale"]["sd"]).to_numpy()
        t = _test(x["fav_won"].to_numpy(), _logit(x["p_champ_fav"]), z, np.zeros(len(x)), n_season_min=10**9)
        out |= {"coef_per_sd": t["coef_per_sd"], "p_one_sided": t["p_one_sided"],
                "status": "PASSED prospectively" if t["p_one_sided"] < reg["alpha"] and t["coef_per_sd"] < 0 else "FAILED prospectively"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "prospective_progress.json").write_text(json.dumps(out, indent=2))
    return out
