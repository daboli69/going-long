"""Phase 8.2: champion error audit and blind-spot screen (EXPLORATORY: every historical season is research-exposed).

Key distinction: losing a game is not a model failure. Calibration-type error is measured as
  excess log loss = LL(p, y) - H(p), where H(p) is the binary entropy (the log loss a perfectly calibrated forecaster
  stating p expects). Excess > 0 means the champion was worse than its own stated confidence implies.
Signed miscalibration is measured from the favourite's side: observed favourite win rate - predicted.
Every condition is a pregame flag from the as-of feature store; outcomes are used only for scoring.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

from . import metrics as M
from .config import ARTIFACTS_DIR
from .ensemble import MODEL_KEYS

OUT = ARTIFACTS_DIR / "phase82"
SEASONS = range(2018, 2026)              # completed out-of-fold seasons (2026 reported separately)


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _H(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(p * np.log(p) + (1 - p) * np.log(1 - p))


def _ll(y, p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def frame() -> pd.DataFrame:
    from .data_pipeline import load_feature_store
    from .specialists.baseline import load_oof
    x = load_oof()
    x = x[x["home_win"].notna()].copy()
    fs = load_feature_store().set_index("game_id")
    x = x.join(fs.drop(columns=[c for c in fs.columns if c in x.columns]), on="game_id")
    try:
        mk = pd.read_parquet(ARTIFACTS_DIR / "phase81" / "analysis_frame.parquet")[["game_id", "p_close", "p_open"]]
        x = x.merge(mk, on="game_id", how="left")
    except Exception:
        x["p_close"], x["p_open"] = np.nan, np.nan
    x["p"] = x["p_weighted_average"]
    x["y"] = x["home_win"]
    x["p_fav"] = np.maximum(x["p"], 1 - x["p"])
    x["y_fav"] = np.where(x["p"] >= 0.5, x["y"], 1 - x["y"])
    x["ll"] = _ll(x["y"], x["p"])
    x["excess"] = x["ll"] - _H(x["p"])
    x["wrong"] = ((x["p"] > 0.5) != (x["y"] == 1)).astype(int)
    P = x[[f"p_{k}" for k in MODEL_KEYS]]
    x["wrong6"] = P.gt(0.5).ne(x["y"].eq(1), axis=0).all(axis=1).astype(int)
    x["right6"] = P.gt(0.5).eq(x["y"].eq(1), axis=0).all(axis=1).astype(int)
    x["disagreement"] = P.std(axis=1)
    x["fav_is_home"] = (x["p"] >= 0.5).astype(int)
    return x


def _flag(x, name):
    f = pd.Series(0, index=x.index, dtype=float)
    g = lambda c: x[c].fillna(0) if c in x else pd.Series(0.0, index=x.index)
    both = lambda s: (g(f"home_{s}") + g(f"away_{s}"))
    if name == "qb_change":
        f = both("qb_change") > 0
    elif name == "qb_projected_out":
        f = both("qb_projected_out") > 0
    elif name == "qb_questionable":
        f = both("qb_questionable") > 0
    elif name == "qb_returning_v2":
        f = both("qb7_returning") > 0
    elif name == "qb_v1_v2_disagree":
        f = (x["home_qb_projected_id"] != x["home_qb7_projected_id"]) | (x["away_qb_projected_id"] != x["away_qb7_projected_id"])
    elif name == "inexperienced_qb":
        f = (x[["home_qb_log_exp", "away_qb_log_exp"]].min(axis=1) < np.log1p(300))
    elif name == "ol_2plus_out":
        f = (x[["home_p72_OL_starters_confirmed_out", "away_p72_OL_starters_confirmed_out"]].max(axis=1) >= 2)
    elif name == "defense_2plus_out":
        f = (x[[f"{s}_p72_{u}_starters_confirmed_out" for s in ("home", "away") for u in ("DL", "LB", "DB")]].fillna(0)
             .groupby(lambda c: c.split("_")[0], axis=1).sum().max(axis=1) >= 2) if "home_p72_DL_starters_confirmed_out" in x else f
    elif name == "concentrated_unit_out":
        cols = [c for c in x.columns if c.endswith("_starters_confirmed_out") and c.startswith(("home_p72_", "away_p72_")) and "_QB_" not in c]
        f = x[cols].fillna(0).max(axis=1) >= 2
    elif name == "high_ol_churn":
        c = x[["home_ol_churn_l4", "away_ol_churn_l4"]].max(axis=1)
        f = c >= c.quantile(0.9)
    elif name == "early_weeks_1_4":
        f = x["week"] <= 4
    elif name == "weeks_1_2":
        f = x["week"] <= 2
    elif name == "new_coach":
        f = (both("coach_new_this_season") + both("coach_changed_midseason")) > 0
    elif name == "high_roster_turnover":
        c = x[["home_p4roster_blend_returning_snap_share", "away_p4roster_blend_returning_snap_share"]].min(axis=1)
        f = c <= c.quantile(0.1)
    elif name == "fav_over_80":
        f = x["p_fav"] > 0.8
    elif name == "fav_70_80":
        f = (x["p_fav"] > 0.7) & (x["p_fav"] <= 0.8)
    elif name == "predicted_margin_10plus":
        f = x["margin_ensemble"].abs() >= 10
    elif name == "recent_form_shift":
        s = (x["home_l3_epa_pp"] - x["home_blend_epa_pp"]).abs().combine((x["away_l3_epa_pp"] - x["away_blend_epa_pp"]).abs(), max)
        f = s >= s.quantile(0.9)
    elif name == "short_rest":
        f = x[["home_rest_days", "away_rest_days"]].min(axis=1) <= 5
    elif name == "rest_diff_3plus":
        f = (x["home_rest_days"] - x["away_rest_days"]).abs() >= 3
    elif name == "tz_shift_2plus":
        f = x[["home_tz_shift", "away_tz_shift"]].abs().max(axis=1) >= 2
    elif name == "divisional":
        f = x["ctx_div_game"] == 1
    elif name == "neutral_site":
        f = x["ctx_neutral"] == 1
    elif name == "away_favourite":
        f = x["p"] < 0.5
    elif name == "no_verified_injury_report":
        f = (x["home_inj_report_available"] != 1) | (x["away_inj_report_available"] != 1)
    elif name == "player_model_stale":
        f = x["home_p5_model_staleness_days"] > 14
    elif name == "qb_unknown":
        f = (x["home_qb_known"] != 1) | (x["away_qb_known"] != 1)
    return pd.Series(np.asarray(f, bool), index=x.index)


CATEGORIES = {
    "A quarterback": ["qb_change", "qb_projected_out", "qb_questionable", "qb_returning_v2", "qb_v1_v2_disagree", "inexperienced_qb"],
    "B personnel": ["ol_2plus_out", "defense_2plus_out", "concentrated_unit_out", "high_ol_churn"],
    "C early season": ["early_weeks_1_4", "weeks_1_2", "new_coach", "high_roster_turnover"],
    "D extremes": ["fav_over_80", "fav_70_80", "predicted_margin_10plus"],
    "E recent change": ["recent_form_shift"],
    "F conditions": ["short_rest", "rest_diff_3plus", "tz_shift_2plus", "divisional", "neutral_site", "away_favourite"],
    "G missing/stale": ["no_verified_injury_report", "player_model_stale", "qb_unknown"],
}
TESTED_BEFORE = {"qb_change": "Phase 8 F, 8.1 H3", "qb_projected_out": "8.1 H3", "qb_questionable": "Phase 8 F, 8.1 H3",
                 "qb_returning_v2": "Phase 7 challenger", "early_weeks_1_4": "Phase 8 F", "weeks_1_2": "8.1 H3 (week<=3)",
                 "new_coach": "Phase 8 C, 8.1 H3", "fav_over_80": "Phase 8 F", "fav_70_80": "Phase 8 F",
                 "concentrated_unit_out": "Phase 7.2 lineups", "ol_2plus_out": "Phase 7.2", "rest_diff_3plus": "Phase 8 D, 8.1 H3",
                 "recent_form_shift": "Phase 8 C"}


def screen(x: pd.DataFrame, n_boot: int = 2000) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    d = x[x["season"].isin(SEASONS)].reset_index(drop=True)
    rows = []
    for cat, names in CATEGORIES.items():
        for nm in names:
            f = _flag(d, nm).to_numpy()
            n = int(f.sum())
            if n < 25 or n > len(d) - 25:
                rows.append({"category": cat, "condition": nm, "games": n, "note": "too few games"})
                continue
            ex_in, ex_out = d.loc[f, "excess"].to_numpy(), d.loc[~f, "excess"].to_numpy()
            bs = [ex_in[rng.integers(0, n, n)].mean() - ex_out[rng.integers(0, len(ex_out), len(ex_out))].mean() for _ in range(n_boot)]
            miscal = float((d.loc[f, "y_fav"] - d.loc[f, "p_fav"]).mean())
            lc = _logit(d["p"])
            X0 = lc.reshape(-1, 1)
            X1 = np.c_[lc, f.astype(float), f * lc]
            m0 = LogisticRegression(C=1e6, max_iter=2000).fit(X0, d["y"])
            m1 = LogisticRegression(C=1e6, max_iter=2000).fit(X1, d["y"])
            lr = 2 * len(d) * (M.log_loss(d["y"], m0.predict_proba(X0)[:, 1]) - M.log_loss(d["y"], m1.predict_proba(X1)[:, 1]))
            # season stability: sign of the condition's mean excess (vs the season's other games), per season
            signs = []
            for s, z in d.groupby("season"):
                ff = _flag(z, nm).to_numpy()
                if ff.sum() >= 5:
                    signs.append(np.sign(z.loc[ff, "excess"].mean() - z.loc[~ff, "excess"].mean()))
            # walk-forward targeted recalibration inside the condition (fitted on earlier seasons' condition games)
            gain_rows = []
            for s in sorted(d["season"].unique()):
                tr = d[(d["season"] < s) & f]
                te_m = (d["season"] == s).to_numpy() & f
                if len(tr) < 40 or te_m.sum() == 0:
                    continue
                mm = LogisticRegression(C=1.0, max_iter=2000).fit(_logit(tr["p"]).reshape(-1, 1), tr["y"])
                pc = mm.predict_proba(_logit(d.loc[te_m, "p"]).reshape(-1, 1))[:, 1]
                gain_rows.append(_ll(d.loc[te_m, "y"].to_numpy(), d.loc[te_m, "p"].to_numpy()) - _ll(d.loc[te_m, "y"].to_numpy(), pc))
            wf = np.concatenate(gain_rows) if gain_rows else np.array([])
            rows.append({"category": cat, "condition": nm, "games": n, "share_of_games": n / len(d),
                         "champion_ll": float(d.loc[f, "ll"].mean()), "other_ll": float(d.loc[~f, "ll"].mean()),
                         "accuracy": float(1 - d.loc[f, "wrong"].mean()),
                         "excess_ll": float(ex_in.mean()), "excess_ll_other": float(ex_out.mean()),
                         "excess_diff": float(ex_in.mean() - ex_out.mean()), "excess_diff_ci_low": float(np.percentile(bs, 2.5)),
                         "excess_diff_ci_high": float(np.percentile(bs, 97.5)),
                         "fav_miscalibration": miscal, "lr_p_given_champion": float(stats.chi2.sf(max(lr, 0), 2)),
                         "seasons_same_sign": f"{int(sum(s_ > 0 for s_ in signs))}+/{int(sum(s_ < 0 for s_ in signs))}-",
                         "walkforward_recal_gain_in_condition": float(wf.mean()) if len(wf) else np.nan,
                         "implied_overall_ll_gain": float(wf.sum() / len(d)) if len(wf) else np.nan,
                         "tested_before": TESTED_BEFORE.get(nm, "")})
    res = pd.DataFrame(rows)
    ok = res["lr_p_given_champion"].notna()
    order = res.loc[ok, "lr_p_given_champion"].sort_values().index
    run, adj = 0.0, {}
    for k, i in enumerate(order):
        run = max(run, min(1.0, (ok.sum() - k) * res.loc[i, "lr_p_given_champion"]))
        adj[i] = run
    res["p_holm"] = pd.Series(adj)
    return res


def audit(x: pd.DataFrame) -> dict:
    d = x[x["season"].isin(SEASONS)]
    out = {}

    def summ(z):
        return pd.Series({"games": len(z), "accuracy": 1 - z["wrong"].mean(), "log_loss": z["ll"].mean(),
                          "brier": float(np.mean((z["p"] - z["y"]) ** 2)), "excess_ll": z["excess"].mean(),
                          "pred_fav": z["p_fav"].mean(), "obs_fav": z["y_fav"].mean(),
                          "margin_mae": (z["margin_ensemble"] - z["margin"]).abs().mean()})
    out["overall"] = summ(d).to_frame().T
    out["by_season"] = d.groupby("season").apply(summ, include_groups=False).reset_index()
    out["by_week_group"] = d.assign(wg=pd.cut(d["week"], [0, 4, 8, 12, 18, 30], labels=["1-4", "5-8", "9-12", "13-18", "playoffs"])).groupby("wg", observed=True).apply(summ, include_groups=False).reset_index()
    out["by_fav_band"] = d.assign(b=pd.cut(d["p_fav"], [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9, 1.0])).groupby("b", observed=True).apply(summ, include_groups=False).reset_index().astype({"b": str})
    out["by_home_away_fav"] = d.groupby("fav_is_home").apply(summ, include_groups=False).reset_index()
    out["by_spread_band"] = d.assign(b=pd.cut(d["margin_ensemble"].abs(), [0, 3, 7, 10, 14, 40])).groupby("b", observed=True).apply(summ, include_groups=False).reset_index().astype({"b": str})
    t = []
    for side in ("home", "away"):
        z = d.assign(team=d[f"{side}_team"])
        t.append(z[["team", "excess", "ll", "wrong", "y_fav", "p_fav"]])
    tt = pd.concat(t)
    out["by_team"] = tt.groupby("team").agg(games=("ll", "size"), log_loss=("ll", "mean"), excess_ll=("excess", "mean")).reset_index().sort_values("excess_ll", ascending=False)
    out["by_completeness"] = d.assign(c=_flag(d, "no_verified_injury_report").map({True: "no verified report", False: "verified report"})).groupby("c").apply(summ, include_groups=False).reset_index()
    return out


def shared_errors(x: pd.DataFrame) -> dict:
    """All-six-wrong games vs comparable games, controlling for the favourite probability (logistic with p-band dummies)."""
    d = x[x["season"].isin(SEASONS)].reset_index(drop=True)
    bands = pd.get_dummies(pd.cut(d["p_fav"], [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 1.0], include_lowest=True), drop_first=True).astype(float).to_numpy()
    rows = []
    for cat, names in CATEGORIES.items():
        for nm in names:
            f = _flag(d, nm).astype(float).to_numpy()
            if f.sum() < 25:
                continue
            X0, X1 = bands, np.c_[bands, f]
            m0 = LogisticRegression(C=1e6, max_iter=2000).fit(X0, d["wrong6"])
            m1 = LogisticRegression(C=1e6, max_iter=2000).fit(X1, d["wrong6"])
            lr = 2 * len(d) * (M.log_loss(d["wrong6"], m0.predict_proba(X0)[:, 1]) - M.log_loss(d["wrong6"], m1.predict_proba(X1)[:, 1]))
            rows.append({"condition": nm, "rate_in_all_six_wrong": float(f[d["wrong6"] == 1].mean()),
                         "rate_in_unanimous_right": float(f[d["right6"] == 1].mean()),
                         "rate_in_split_votes": float(f[(d["wrong6"] == 0) & (d["right6"] == 0)].mean()),
                         "odds_ratio_given_fav_band": float(np.exp(m1.coef_[0][-1])), "p": float(stats.chi2.sf(max(lr, 0), 1))})
    sh = pd.DataFrame(rows)
    order = sh["p"].sort_values().index
    run, adj = 0.0, {}
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(sh) - k) * sh.loc[i, "p"]))
        adj[i] = run
    sh["p_holm"] = pd.Series(adj)
    groups = {"all six wrong": d["wrong6"] == 1, "unanimous right": d["right6"] == 1, "split votes": (d["wrong6"] == 0) & (d["right6"] == 0)}
    if d["p_close"].notna().any():
        mr = ((d["p_close"] > 0.5) == (d["y"] == 1)) & (d["wrong"] == 1)
        cr = ((d["p_close"] > 0.5) != (d["y"] == 1)) & (d["wrong"] == 0)
        groups |= {"market right, champion wrong": mr, "champion right, market wrong": cr}
    comp = pd.DataFrame([{"group": k, "games": int(m.sum()), "mean_fav_prob": float(d.loc[m, "p_fav"].mean()),
                          "mean_disagreement": float(d.loc[m, "disagreement"].mean()), "excess_ll": float(d.loc[m, "excess"].mean())} for k, m in groups.items()])
    # disagreement beyond the ensemble probability: walk-forward recalibration with vs without disagreement
    pr = []
    for s in sorted(d["season"].unique()):
        tr, te = d[d["season"] < s], d[d["season"] == s]
        if len(tr) < 250:
            continue
        mu, sd = tr["disagreement"].mean(), tr["disagreement"].std()
        z = lambda q: (q["disagreement"] - mu) / sd
        X = lambda q: np.c_[_logit(q["p"]), z(q), _logit(q["p"]) * z(q)]
        a = LogisticRegression(C=1.0, max_iter=2000).fit(_logit(tr["p"]).reshape(-1, 1), tr["y"]).predict_proba(_logit(te["p"]).reshape(-1, 1))[:, 1]
        b = LogisticRegression(C=1.0, max_iter=2000).fit(X(tr), tr["y"]).predict_proba(X(te))[:, 1]
        pr.append(pd.DataFrame({"y": te["y"], "recal": a, "with_disagreement": b, "season": s}))
    P = pd.concat(pr)
    dd = _ll(P["y"].to_numpy(), P["recal"].to_numpy()) - _ll(P["y"].to_numpy(), P["with_disagreement"].to_numpy())
    rng = np.random.default_rng(1)
    bs = [dd[rng.integers(0, len(dd), len(dd))].mean() for _ in range(3000)]
    dis = {"games": int(len(P)), "gain": float(dd.mean()), "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
           "by_season": P.assign(g=dd).groupby("season")["g"].mean().round(4).to_dict()}
    return {"conditions": sh, "groups": comp, "disagreement": dis}


def market_disagreement(x: pd.DataFrame) -> pd.DataFrame:
    """Market-informed, kept separate: which pregame conditions co-occur with large champion-market disagreement."""
    d = x[x["season"].isin(SEASONS)].dropna(subset=["p_close"]).reset_index(drop=True)
    dis = np.abs(_logit(d["p_close"]) - _logit(d["p"]))
    top = dis >= np.quantile(dis, 0.9)
    rows = []
    for cat, names in CATEGORIES.items():
        for nm in names:
            f = _flag(d, nm).to_numpy()
            if f.sum() < 25:
                continue
            tab = [[int((f & top).sum()), int((~f & top).sum())], [int((f & ~top).sum()), int((~f & ~top).sum())]]
            odds, p = stats.fisher_exact(tab)
            rows.append({"condition": nm, "rate_in_top_decile_disagreement": float(f[top].mean()), "rate_elsewhere": float(f[~top].mean()),
                         "odds_ratio": float(odds), "p": float(p)})
    return pd.DataFrame(rows).sort_values("p")


def run() -> dict:
    x = frame()
    res = {"audit": audit(x), "screen": screen(x), "shared": shared_errors(x), "market": market_disagreement(x)}
    OUT.mkdir(parents=True, exist_ok=True)
    for k, v in res["audit"].items():
        v.to_csv(OUT / f"audit_{k}.csv", index=False)
    res["screen"].to_csv(OUT / "screen.csv", index=False)
    res["shared"]["conditions"].to_csv(OUT / "shared_conditions.csv", index=False)
    res["shared"]["groups"].to_csv(OUT / "shared_groups.csv", index=False)
    res["market"].to_csv(OUT / "market_disagreement.csv", index=False)
    (OUT / "disagreement.json").write_text(json.dumps(res["shared"]["disagreement"], indent=2))
    return res


def load() -> dict:
    out = {f.stem: pd.read_csv(f) for f in OUT.glob("*.csv")}
    j = OUT / "disagreement.json"
    if j.exists():
        out["disagreement"] = json.loads(j.read_text())
    return out


# --------------------------------------------------------------------------- prospective hypotheses (Phase 8.2)

PROSPECTIVE = [
    {"id": "P1", "name": "early-season overconfidence", "type": "football-only", "min_games": 256,
     "metric": "mean(y_fav - p_fav) in weeks 1-4, final-stage forecast", "support": "95% CI below 0"},
    {"id": "P2", "name": "offensive-line disruption", "type": "football-only (+ market companion)", "min_games": 150,
     "metric": "excess log loss in OL-2+-out games minus other games", "support": "95% CI above 0"},
    {"id": "P3", "name": "market advantage timing", "type": "market-informed", "min_games": 128,
     "metric": "paired LL (market - champion) at final minus at Friday", "support": "difference > 0 with CI excluding 0"},
]
REGISTERED_AT = "2026-10-17T20:15:00+00:00"


def register_prospective():
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "prospective_hypotheses.json"
    if not p.exists():                                   # registration is written once and never edited
        p.write_text(json.dumps({"registered_at": REGISTERED_AT, "doc": "docs/PHASE8_2_PREREGISTRATION.md",
                                 "hypotheses": PROSPECTIVE}, indent=2))
    return json.loads(p.read_text())


def prospective_eval(n_boot: int = 2000) -> pd.DataFrame:
    """Score only games archived after registration; reports progress toward each hypothesis's sample size."""
    from .compare7 import collect
    from .data_pipeline import load_feature_store
    reg = register_prospective()
    t0 = pd.Timestamp(reg["registered_at"])
    df = collect()
    rows = []
    if df.empty:
        return pd.DataFrame([{"id": h["id"], "name": h["name"], "games": 0, "min_games": h["min_games"], "status": "no completed archived games yet"}
                             for h in reg["hypotheses"]])
    df["predicted_at"] = pd.to_datetime(df["predicted_at"], utc=True)
    champ = df[(df["version"] == df["version"].iloc[0]) & (df["predicted_at"] >= t0)]
    fin = champ[champ["stage"] == "final"].drop_duplicates("game_id", keep="last")
    fs = load_feature_store().set_index("game_id")
    rng = np.random.default_rng(0)
    # P1
    z = fin.join(fs[["week"]], on="game_id")
    e = z[z["week"] <= 4]
    pf = np.maximum(e["p"], 1 - e["p"])
    yf = np.where(e["p"] >= 0.5, e["home_win"], 1 - e["home_win"])
    r = {"id": "P1", "name": "early-season overconfidence", "games": int(len(e)), "min_games": 256, "estimate": float(np.mean(yf - pf)) if len(e) else np.nan}
    rows.append(r)
    # P2
    z = fin.join(fs[["home_p72_OL_starters_confirmed_out", "away_p72_OL_starters_confirmed_out"]], on="game_id")
    f = z[["home_p72_OL_starters_confirmed_out", "away_p72_OL_starters_confirmed_out"]].fillna(0).max(axis=1).to_numpy() >= 2
    ex = _ll(z["home_win"].to_numpy(), z["p"].to_numpy()) - _H(z["p"].to_numpy())
    rows.append({"id": "P2", "name": "offensive-line disruption", "games": int(f.sum()), "min_games": 150,
                 "estimate": float(ex[f].mean() - ex[~f].mean()) if f.any() and (~f).any() else np.nan})
    # P3: needs the T1 ESPN archive matched to stage archive times
    from .market81 import american_to_prob, espn_archive, novig
    arc = espn_archive()
    est = np.nan
    n3 = 0
    if len(arc):
        arc["retrieved_at"] = pd.to_datetime(arc["retrieved_at"], utc=True)
        def mkt(gid, at):
            g = fs.loc[gid] if gid in fs.index else None
            if g is None:
                return np.nan
            a = arc[(arc["home"] == g["home_team"]) & (arc["away"] == g["away_team"]) & (arc["retrieved_at"] <= at)]
            if a.empty:
                return np.nan
            last = a.iloc[-1]
            try:
                h, w = float(str(last["home_ml_close"]).replace("+", "")), float(str(last["away_ml_close"]).replace("+", ""))
            except (TypeError, ValueError):
                return np.nan
            return float(novig(american_to_prob([h]), american_to_prob([w]))[0])
        pairs = []
        for gid, d in champ.groupby("game_id"):
            fr, fi = d[d["stage"] == "friday"], d[d["stage"] == "final"]
            if fr.empty or fi.empty:
                continue
            mf, mfi = mkt(gid, fr["predicted_at"].iloc[-1]), mkt(gid, fi["predicted_at"].iloc[-1])
            if np.isnan(mf) or np.isnan(mfi):
                continue
            y = fi["home_win"].iloc[-1]
            adv_f = _ll(y, fr["p"].iloc[-1]) - _ll(y, mf)
            adv_fi = _ll(y, fi["p"].iloc[-1]) - _ll(y, mfi)
            pairs.append(adv_fi - adv_f)
        n3 = len(pairs)
        est = float(np.mean(pairs)) if pairs else np.nan
    rows.append({"id": "P3", "name": "market advantage timing", "games": n3, "min_games": 128, "estimate": est})
    out = pd.DataFrame(rows)
    out["status"] = np.where(out["games"] >= out["min_games"], "ready for its single pre-registered evaluation", "accumulating (no conclusion)")
    out.to_csv(OUT / "prospective_progress.csv", index=False)
    return out
