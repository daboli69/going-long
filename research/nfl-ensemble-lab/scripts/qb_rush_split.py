"""Quarterback rushing split (designed, scramble, kneel) against the recent-average baseline. Rule: docs/QB_RUSH_SPLIT_PREREG.md.

    .venv/Scripts/python.exe scripts/qb_rush_split.py

Writes docs/qb_rush_split_results.json. Research challenger; changes no freeze and no display.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import homewin_deep as h  # noqa: E402
from lab.config import RAW_DIR  # noqa: E402

TEST = (2022, 2025)
FIT_FROM = 2012
BOOT, SEED = 2000, 20261110
K_RATE_D, K_YPA_D, K_RATE_S, K_YPA_S, WINDOW = 6.0, 30.0, 150.0, 15.0, 16
CLIP_M = 14.0
LEAGUE_DB = 37.5


def load_plays(seasons) -> pd.DataFrame:
    cols = ["game_id", "season", "week", "posteam", "qb_dropback", "qb_scramble", "qb_kneel", "rush_attempt", "rusher_player_id", "passer_id", "yards_gained"]
    return pd.concat([pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=cols) for s in seasons], ignore_index=True)


def starter_games(p: pd.DataFrame) -> pd.DataFrame:
    db = p[(p["qb_dropback"] == 1) & p["passer_id"].notna()].groupby(["game_id", "season", "week", "posteam", "passer_id"]).size().rename("db").reset_index()
    db = db.sort_values("db", ascending=False).drop_duplicates(["game_id", "posteam"])
    db = db[db["db"] >= 15].rename(columns={"passer_id": "qb"})
    r = p[(p["rush_attempt"] == 1) & p["rusher_player_id"].notna()].copy()
    r["kind"] = np.where(r["qb_kneel"] == 1, "k", np.where(r["qb_scramble"] == 1, "s", "d"))
    a = r.groupby(["game_id", "posteam", "rusher_player_id", "kind"]).agg(att=("yards_gained", "size"), yds=("yards_gained", "sum")).reset_index()
    out = db.copy()
    for k in "dsk":
        x = a[a["kind"] == k].rename(columns={"rusher_player_id": "qb", "att": f"att_{k}", "yds": f"yds_{k}"})[["game_id", "posteam", "qb", f"att_{k}", f"yds_{k}"]]
        out = out.merge(x, on=["game_id", "posteam", "qb"], how="left")
    out = out.fillna({c: 0 for c in out.columns if c.startswith(("att_", "yds_"))})
    out["total"] = out["yds_d"] + out["yds_s"] + out["yds_k"]
    ko = h.pd.read_parquet(h.CACHE / "walk_forward.parquet")[["gid", "kickoff_utc", "pred_margin"]] if False else None
    return out


def add_history(g: pd.DataFrame, kick: pd.Series) -> pd.DataFrame:
    g = g.assign(kick=g["game_id"].map(kick)).sort_values(["qb", "kick"]).reset_index(drop=True)
    grp = g.groupby("qb")
    def prior(col, n=WINDOW):
        return grp[col].transform(lambda s: s.shift(1).rolling(n, min_periods=1).sum())
    g["h_games"] = grp["db"].transform(lambda s: s.shift(1).rolling(WINDOW, min_periods=1).count())
    for c in ("db", "att_d", "yds_d", "att_s", "yds_s"):
        g[f"h_{c}"] = prior(c)
    g["b0_mean"] = grp["total"].transform(lambda s: s.shift(1).rolling(6, min_periods=3).mean())
    return g


def fit_poisson(x, y, off_rate):
    """exp(a + b*m) multiplier on a known rate: Poisson with offset via the weighted-ratio form."""
    ok = off_rate > 0
    m = PoissonRegressor(alpha=0.0, max_iter=500).fit(x[ok][:, None], (y[ok] / off_rate[ok]), sample_weight=off_rate[ok])
    return float(m.intercept_), float(m.coef_[0])


def league(tr: pd.DataFrame) -> dict:
    return {"att_d": tr["att_d"].mean(), "ypa_d": tr["yds_d"].sum() / max(tr["att_d"].sum(), 1), "rate_s": tr["att_s"].sum() / tr["db"].sum(),
            "ypa_s": tr["yds_s"].sum() / max(tr["att_s"].sum(), 1), "ypk": tr["yds_k"].sum() / max(tr["att_k"].sum(), 1), "total": tr["total"].mean()}


def components(d: pd.DataFrame, L: dict) -> pd.DataFrame:
    d = d.copy()
    n = d["h_games"].fillna(0)
    d["rate_d"] = (d["h_att_d"].fillna(0) + K_RATE_D * L["att_d"]) / (n + K_RATE_D)
    d["ypa_d"] = (d["h_yds_d"].fillna(0) + K_YPA_D * L["ypa_d"]) / (d["h_att_d"].fillna(0) + K_YPA_D)
    d["rate_s"] = (d["h_att_s"].fillna(0) + K_RATE_S * L["rate_s"]) / (d["h_db"].fillna(0) + K_RATE_S)
    d["ypa_s"] = (d["h_yds_s"].fillna(0) + K_YPA_S * L["ypa_s"]) / (d["h_att_s"].fillna(0) + K_YPA_S)
    return d


def fit_state(tr: pd.DataFrame):
    m = tr["m"].clip(-CLIP_M, CLIP_M).to_numpy()
    aD = PoissonRegressor(alpha=0.0, max_iter=500).fit(m[:, None], tr["db"].to_numpy(float))
    D_fit = aD.predict(m[:, None])
    pd_ = fit_poisson(m, tr["att_d"].to_numpy(float), tr["rate_d"].to_numpy())
    ps_ = fit_poisson(m, tr["att_s"].to_numpy(float), (tr["rate_s"] * D_fit).to_numpy())
    ak = PoissonRegressor(alpha=0.0, max_iter=500).fit(m[:, None], tr["att_k"].to_numpy(float))
    return {"D": aD, "d": pd_, "s": ps_, "k": ak}


def predict(d: pd.DataFrame, fit: dict, L: dict) -> pd.DataFrame:
    d = d.copy()
    m = d["m"].clip(-CLIP_M, CLIP_M).to_numpy()
    D = fit["D"].predict(m[:, None])
    d["mu_d"] = d["rate_d"] * np.exp(fit["d"][0] + fit["d"][1] * m)
    d["mu_s"] = d["rate_s"] * D * np.exp(fit["s"][0] + fit["s"][1] * m)
    d["mu_k"] = fit["k"].predict(m[:, None])
    d["pred_S"] = d["mu_d"] * d["ypa_d"] + d["mu_s"] * d["ypa_s"] + d["mu_k"] * L["ypk"]
    d["pred_S_nok"] = d["pred_S"] - d["mu_k"] * L["ypk"]
    d["pred_B0"] = d["b0_mean"].fillna(L["total"])
    return d


def main():
    seasons = range(2004, 2026)
    p = load_plays(seasons)
    wf = pd.read_parquet(h.CACHE / "walk_forward.parquet")[["gid", "kickoff_utc", "pred_margin"]]
    kick = wf.set_index("gid")["kickoff_utc"]
    g = starter_games(p)
    # kickoff for all seasons from the lab's games table
    data, _ = h.load_all(False)
    kick = data.games.set_index("gid")["kickoff_utc"]
    g = add_history(g, kick)
    gm = data.games.set_index("gid")[["home"]]
    pm = wf.set_index("gid")["pred_margin"]
    g["home"] = g["game_id"].map(gm["home"])
    g["m"] = np.where(g["posteam"] == g["home"], g["game_id"].map(pm), -g["game_id"].map(pm))
    rng = np.random.default_rng(SEED)
    outs = []
    for s in range(TEST[0], TEST[1] + 1):
        tr = g[(g["season"] < s) & (g["season"] >= FIT_FROM) & g["m"].notna()]
        L = league(g[g["season"] < s])
        trc = components(tr, L)
        fit = fit_state(trc)
        te = predict(components(g[(g["season"] == s) & g["m"].notna()], L), fit, L)
        outs.append(te)
    t = pd.concat(outs, ignore_index=True)
    y = t["total"].to_numpy(float)
    res = {"games": int(len(t)), "seasons": list(TEST)}
    def metrics(pred):
        e = pred - y
        return {"rmse": float(np.sqrt((e ** 2).mean())), "mae": float(np.abs(e).mean()), "bias": float(e.mean())}
    for k in ("pred_B0", "pred_S", "pred_S_nok"):
        res[k] = metrics(t[k].to_numpy(float))
    idx = [rng.integers(0, len(t), len(t)) for _ in range(BOOT)]
    def delta(a, b, mask=None):
        ea, eb = (t[a].to_numpy(float) - y), (t[b].to_numpy(float) - y)
        mk = np.ones(len(t), bool) if mask is None else mask
        da, db_ = ea[mk], eb[mk]
        ix = [rng.integers(0, mk.sum(), mk.sum()) for _ in range(BOOT)]
        r = np.array([np.sqrt((da[i] ** 2).mean()) - np.sqrt((db_[i] ** 2).mean()) for i in ix])
        return {"n": int(mk.sum()), "rmse_delta": float(np.sqrt((da ** 2).mean()) - np.sqrt((db_ ** 2).mean())), "ci95": [float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))],
                "mae_delta": float(np.abs(da).mean() - np.abs(db_).mean())}
    res["S_vs_B0"] = delta("pred_S", "pred_B0")
    res["S_vs_S_nokneels"] = delta("pred_S", "pred_S_nok")
    rushy = ((t["h_att_d"].fillna(0) + t["h_att_s"].fillna(0)) / t["h_games"].replace(0, np.nan)).fillna(0)
    res["S_vs_B0_top_quartile_rushers"] = delta("pred_S", "pred_B0", (rushy >= rushy.quantile(0.75)).to_numpy())
    res["S_vs_B0_margin_over_7"] = delta("pred_S", "pred_B0", (t["m"] > 7).to_numpy())
    res["passes"] = bool(res["pred_S"]["rmse"] < res["pred_B0"]["rmse"] and res["pred_S"]["mae"] < res["pred_B0"]["mae"] and res["S_vs_B0"]["ci95"][1] < 0)
    res["mean_actual"] = float(y.mean())
    res["mean_kneels_per_game_margin_over_7"] = float(t.loc[t["m"] > 7, "att_k"].mean())
    (ROOT / "docs" / "qb_rush_split_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    t.to_pickle(ROOT / "data" / "cache" / "qb_rush_split_test.pkl")


if __name__ == "__main__":
    main()
