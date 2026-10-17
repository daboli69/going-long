"""Phase 8.1 analyses, exactly as pre-registered in docs/PHASE8_1_PREREGISTRATION.md (H1-H5 + drive simulator)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

from . import metrics as M
from .market81 import OUT, american_to_prob, novig


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _ece(y, p, bins=10):
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(y[b == k].mean() - p[b == k].mean()) * (b == k).mean() for k in range(bins) if (b == k).any()))


def _lr_test(y, X0, X1):
    m0 = LogisticRegression(C=1e6, max_iter=2000).fit(X0, y)
    m1 = LogisticRegression(C=1e6, max_iter=2000).fit(X1, y)
    stat = 2 * len(y) * (M.log_loss(y, m0.predict_proba(X0)[:, 1]) - M.log_loss(y, m1.predict_proba(X1)[:, 1]))
    df = X1.shape[1] - X0.shape[1]
    return {"lr_stat": float(stat), "p": float(stats.chi2.sf(max(stat, 0), df)), "coef_added": [float(c) for c in m1.coef_[0][X0.shape[1]:]],
            "games": int(len(y))}


def frame() -> pd.DataFrame:
    from .data_pipeline import GAMES_TABLE, load_feature_store
    from .specialists.baseline import load_oof
    oof = load_oof()
    g = pd.read_parquet(GAMES_TABLE)[["game_id", "home_moneyline", "away_moneyline", "spread_line", "total_line", "home_score", "away_score"]]
    x = oof.merge(g, on="game_id", how="left", suffixes=("", "_g"))
    ph, pa = american_to_prob(x["home_moneyline"]), american_to_prob(x["away_moneyline"])
    for mth in ("multiplicative", "additive", "power"):
        x[f"p_close_{mth}"] = novig(ph, pa, mth)
    x["p_close"] = x["p_close_multiplicative"]
    sb = pd.read_parquet(__import__("lab.market81", fromlist=["MKT_RAW"]).MKT_RAW / "sbr_lines.parquet")
    x = x.merge(sb.drop(columns=["season"]), on="game_id", how="left")
    fs = load_feature_store().set_index("game_id")
    flags = pd.DataFrame(index=fs.index)
    flags["qb_change"] = ((fs["home_qb_change"] + fs["away_qb_change"]) > 0).astype(int)
    flags["qb_out_or_q"] = ((fs[["home_qb_projected_out", "away_qb_projected_out", "home_qb_questionable", "away_qb_questionable"]].fillna(0).sum(axis=1)) > 0).astype(int)
    st = [c for c in fs.columns if c.endswith("_starters_confirmed_out") and c.startswith(("home_p72_", "away_p72_")) and "_QB_" not in c]
    flags["nonqb_starters_out2"] = (fs[st].fillna(0).sum(axis=1) >= 2).astype(int)
    flags["coach_change"] = (fs[["home_coach_new_this_season", "away_coach_new_this_season", "home_coach_changed_midseason",
                                 "away_coach_changed_midseason"]].fillna(0).sum(axis=1) > 0).astype(int)
    flags["early_season"] = (fs["week"] <= 3).astype(int)
    flags["rest_diff3"] = ((fs["home_rest_days"] - fs["away_rest_days"]).abs() >= 3).astype(int)
    x = x.join(flags, on="game_id")
    return x


def _window(x, seasons):
    return x[x["season"].isin(seasons) & x["home_win"].notna()]


def comparison(x: pd.DataFrame) -> dict:
    """Champion vs market on identical games (closing = unequal information; opening = approximately equal)."""
    out = {}
    rows = []
    for label, col, seasons, info in (("closing moneyline (T3)", "p_close", range(2018, 2026), "unequal: market knows late news"),
                                      ("opening spread (T2)", "p_open", range(2018, 2022), "approximately equal (opening time unrecorded)")):
        d = _window(x, seasons)
        d = d[d[col].notna()] if col in d else d.iloc[:0]
        if d.empty:
            continue
        y = d["home_win"].to_numpy()
        for who, p in (("champion", d["p_weighted_average"]), ("market", d[col])):
            p = p.to_numpy()
            rows.append({"benchmark": label, "information": info, "who": who, "games": len(d), "accuracy": float(((p > 0.5) == (y == 1)).mean()),
                         "log_loss": M.log_loss(y, p), "brier": float(np.mean((p - y) ** 2)), "ece": _ece(y, p)})
    out["overall"] = pd.DataFrame(rows)
    d = _window(x, range(2018, 2026)).dropna(subset=["p_close"])
    y = d["home_win"].to_numpy()
    seas = []
    for s, z in d.groupby("season"):
        yy = z["home_win"].to_numpy()
        seas.append({"season": int(s), "games": len(z), "champion_ll": M.log_loss(yy, z["p_weighted_average"].to_numpy()),
                     "market_ll": M.log_loss(yy, z["p_close"].to_numpy()),
                     "champion_margin_mae": float((z["margin_ensemble"] - z["margin"]).abs().mean()),
                     "spread_margin_mae": float((z["spread_line"] - z["margin"]).abs().mean())})
    out["by_season"] = pd.DataFrame(seas)
    fav = np.maximum(d["p_close"], 1 - d["p_close"])
    d = d.assign(band=pd.cut(fav, [0.5, 0.6, 0.7, 0.8, 1.0], labels=["50-60%", "60-70%", "70-80%", ">80%"], include_lowest=True).astype(str))
    out["by_band"] = d.groupby("band").apply(lambda z: pd.Series({"games": len(z), "champion_ll": M.log_loss(z["home_win"].to_numpy(), z["p_weighted_average"].to_numpy()),
                                                                  "market_ll": M.log_loss(z["home_win"].to_numpy(), z["p_close"].to_numpy())}), include_groups=False).reset_index()
    cr = (d["p_weighted_average"] > 0.5) == (d["home_win"] == 1)
    mr = (d["p_close"] > 0.5) == (d["home_win"] == 1)
    out["agreement"] = pd.DataFrame([{"case": k, "games": int(v.sum()), "share": float(v.mean())} for k, v in (
        ("both right", cr & mr), ("both wrong", ~cr & ~mr), ("champion right, market wrong", cr & ~mr), ("market right, champion wrong", ~cr & mr))])
    out["novig_methods"] = pd.DataFrame([{"method": m, "market_ll": M.log_loss(y, d[f"p_close_{m}"].to_numpy())} for m in ("multiplicative", "additive", "power")])
    return out


def hypotheses(x: pd.DataFrame, n_boot: int = 5000) -> dict:
    rng = np.random.default_rng(0)
    res = {}
    # H1: disagreement predicts champion error (opening = primary; closing = reported, unequal information)
    d = _window(x, range(2018, 2022)).dropna(subset=["p_open"])
    lc = _logit(d["p_weighted_average"])
    res["H1_open"] = _lr_test(d["home_win"].to_numpy(), lc.reshape(-1, 1), np.c_[lc, _logit(d["p_open"]) - lc])
    d2 = _window(x, range(2018, 2023)).dropna(subset=["p_close"])
    lc2 = _logit(d2["p_weighted_average"])
    res["H1_close_unequal"] = _lr_test(d2["home_win"].to_numpy(), lc2.reshape(-1, 1), np.c_[lc2, _logit(d2["p_close"]) - lc2])
    # H2: movement beyond the closing line (SBR 2016-21; spreads as features, no sigma needed)
    sb = x.dropna(subset=["sbr_home_spread_open", "sbr_home_spread_close"])
    sb = sb[sb["season"].between(2018, 2021)]
    allsb = _sbr_all()
    y = allsb["home_win"].to_numpy()
    c, mv = allsb["sbr_home_spread_close"].to_numpy(), (allsb["sbr_home_spread_close"] - allsb["sbr_home_spread_open"]).to_numpy()
    res["H2_movement_given_close"] = _lr_test(y, c.reshape(-1, 1), np.c_[c, mv])
    o = allsb["sbr_home_spread_open"].to_numpy()
    res["H2b_movement_given_open"] = _lr_test(y, o.reshape(-1, 1), np.c_[o, mv])
    # H4: margins (2018-21): opening spread vs champion margin; blend walk-forward
    dm = _window(x, range(2018, 2022)).dropna(subset=["sbr_home_spread_open", "margin_ensemble"])
    res["H4_margin_mae"] = {"games": int(len(dm)), "champion": float((dm["margin_ensemble"] - dm["margin"]).abs().mean()),
                            "opening_spread": float((dm["sbr_home_spread_open"] - dm["margin"]).abs().mean()),
                            "closing_spread_unequal": float((dm["sbr_home_spread_close"] - dm["margin"]).abs().mean())}
    e1 = (dm["margin_ensemble"] - dm["margin"]).abs().to_numpy()
    e2 = (dm["sbr_home_spread_open"] - dm["margin"]).abs().to_numpy()
    bs = np.array([np.mean((e1 - e2)[i]) for i in [rng.integers(0, len(e1), len(e1)) for _ in range(n_boot)]])
    res["H4_margin_mae"] |= {"diff_champion_minus_open": float(np.mean(e1 - e2)), "p_open_better": float((bs <= 0).mean())}
    blend = []
    for s in sorted(dm["season"].unique()):
        tr, te = dm[dm["season"] < s], dm[dm["season"] == s]
        if len(tr) < 200:
            continue
        X = np.c_[np.ones(len(tr)), tr["margin_ensemble"], tr["sbr_home_spread_open"]]
        b = np.linalg.lstsq(X, tr["margin"].to_numpy(), rcond=None)[0]
        pred = np.c_[np.ones(len(te)), te["margin_ensemble"], te["sbr_home_spread_open"]] @ b
        blend.append(pd.DataFrame({"e_blend": np.abs(pred - te["margin"]), "e_open": np.abs(te["sbr_home_spread_open"] - te["margin"])}))
    if blend:
        bl = pd.concat(blend)
        res["H4_blend_vs_open"] = {"games": int(len(bl)), "blend_mae": float(bl["e_blend"].mean()), "open_mae": float(bl["e_open"].mean())}
    # H5: combination vs market alone (walk-forward)
    for name, col, seasons in (("H5_close", "p_close", range(2018, 2023)), ("H5_open", "p_open", range(2018, 2022))):
        d = x[x["season"].isin(seasons)].dropna(subset=[col, "p_weighted_average", "home_win"])
        preds = []
        for s in sorted(d["season"].unique()):
            tr, te = d[d["season"] < s], d[d["season"] == s]
            if len(tr) < 200:
                continue
            Xtr, Xte = np.c_[_logit(tr["p_weighted_average"]), _logit(tr[col])], np.c_[_logit(te["p_weighted_average"]), _logit(te[col])]
            pc = LogisticRegression(C=1e6, max_iter=2000).fit(Xtr, tr["home_win"]).predict_proba(Xte)[:, 1]
            pm = LogisticRegression(C=1e6, max_iter=2000).fit(Xtr[:, 1:], tr["home_win"]).predict_proba(Xte[:, 1:])[:, 1]
            pr = LogisticRegression(C=1e6, max_iter=2000).fit(Xtr[:, :1], tr["home_win"]).predict_proba(Xte[:, :1])[:, 1]
            preds.append(pd.DataFrame({"season": s, "y": te["home_win"], "C": pc, "M_raw": te[col], "M_recal": pm, "R": pr,
                                       "champion": te["p_weighted_average"]}))
        P = pd.concat(preds)
        yy = P["y"].to_numpy()
        ll = lambda c_: -(yy * np.log(np.clip(P[c_], 1e-6, 1)) + (1 - yy) * np.log(np.clip(1 - P[c_], 1e-6, 1))).to_numpy()
        r = {"games": int(len(P)), "seasons": sorted(int(s) for s in P["season"].unique())}
        for c_ in ("C", "M_raw", "M_recal", "R", "champion"):
            r[f"ll_{c_}"] = float(ll(c_).mean())
        for base in ("M_raw", "M_recal"):
            dd = ll(base) - ll("C")
            bs = np.array([dd[rng.integers(0, len(dd), len(dd))].mean() for _ in range(n_boot)])
            r[f"gain_C_vs_{base}"], r[f"ci_C_vs_{base}"], r[f"p_C_vs_{base}"] = float(dd.mean()), [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], float((bs <= 0).mean())
        res[name] = r
    return res


def _sbr_all() -> pd.DataFrame:
    from .data_pipeline import GAMES_TABLE
    from .market81 import MKT_RAW
    g = pd.read_parquet(GAMES_TABLE)[["game_id", "home_score", "away_score"]]
    sb = pd.read_parquet(MKT_RAW / "sbr_lines.parquet").merge(g, on="game_id").dropna(subset=["home_score"])
    return sb.assign(home_win=(sb["home_score"] > sb["away_score"]).astype(float) + 0.5 * (sb["home_score"] == sb["away_score"])).query("home_win != 0.5")


def h3(x: pd.DataFrame) -> dict:
    """Stale-input flags in large-disagreement games: discover on 2018-21 (open), reproduce on 2022-25 (close)."""
    flags = ["qb_change", "qb_out_or_q", "nonqb_starters_out2", "coach_change", "early_season", "rest_diff3"]
    out = {}
    for name, col, seasons in (("discover_2018_21_open", "p_open", range(2018, 2022)), ("reproduce_2022_25_close", "p_close", range(2022, 2026))):
        d = _window(x, seasons).dropna(subset=[col])
        dis = pd.Series(np.abs(_logit(d[col]) - _logit(d["p_weighted_average"])), index=d.index)
        top = d[dis >= dis.quantile(0.9)]
        mr = ((top[col] > 0.5) == (top["home_win"] == 1)) & ((top["p_weighted_average"] > 0.5) != (top["home_win"] == 1))
        rows = []
        for f in flags:
            a, b = top.loc[mr, f].fillna(0), top.loc[~mr, f].fillna(0)
            tab = [[int(a.sum()), int(len(a) - a.sum())], [int(b.sum()), int(len(b) - b.sum())]]
            odds, p = stats.fisher_exact(tab, alternative="greater")
            rows.append({"flag": f, "rate_market_right_champ_wrong": float(a.mean()) if len(a) else np.nan,
                         "rate_other_top_decile": float(b.mean()) if len(b) else np.nan, "rate_all_games": float(d[f].fillna(0).mean()),
                         "odds_ratio": float(odds), "p_one_sided": float(p), "n_market_right": int(len(a)), "n_other": int(len(b))})
        out[name] = pd.DataFrame(rows)
        out[f"{name}_top_decile_games"] = int(len(top))
    disc, rep = out["discover_2018_21_open"], out["reproduce_2022_25_close"]
    # Holm across the 6 flags within the discovery set; a flag survives only if it also reproduces (p < 0.05) on 2022-25
    order = disc["p_one_sided"].sort_values().index
    run, adj = 0.0, {}
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(disc) - k) * disc.loc[i, "p_one_sided"]))
        adj[i] = run
    disc["p_holm"] = pd.Series(adj)
    surv = [f for f in disc.loc[disc["p_holm"] < 0.05, "flag"] if float(rep.set_index("flag").loc[f, "p_one_sided"]) < 0.05]
    out["surviving_flags"] = surv
    return out


def drive_sim(x: pd.DataFrame) -> dict:
    from .specialists.core import OUT as P8
    sp = pd.read_parquet(P8 / "specialist_oof.parquet")
    e = sp[sp["specialist"] == "E"][["game_id", "margin", "total", "margin_p10", "margin_p90", "total_p10", "total_p90"]].rename(columns=lambda c: c if c == "game_id" else f"E_{c}")
    d = x.merge(e, on="game_id").dropna(subset=["E_margin", "home_score"])
    d["total_actual"] = d["home_score"] + d["away_score"]
    rows = []
    for w, seasons in (("development 2018-22", range(2018, 2023)), ("research-exposed 2023-25", range(2023, 2026)), ("live 2026", (2026,))):
        z = d[d["season"].isin(seasons)]
        if z.empty:
            continue
        lm = np.array([d[d["season"] < s]["total_actual"].mean() for s in z["season"]])
        r = {"window": w, "games": len(z),
             "margin_mae_drive_sim": float((z["E_margin"] - z["margin"]).abs().mean()),
             "margin_mae_champion": float((z["margin_ensemble"] - z["margin"]).abs().mean()),
             "margin_mae_zero": float(z["margin"].abs().mean()),
             "margin_mae_closing_spread_unequal": float((z["spread_line"] - z["margin"]).abs().mean()),
             "total_mae_drive_sim": float((z["E_total"] - z["total_actual"]).abs().mean()),
             "total_mae_league_mean": float(np.nanmean(np.abs(lm - z["total_actual"]))),
             "total_mae_closing_total_unequal": float((z["total_line"] - z["total_actual"]).abs().mean()),
             "margin_80pct_coverage": float(((z["margin"] >= z["E_margin_p10"]) & (z["margin"] <= z["E_margin_p90"])).mean()),
             "total_80pct_coverage": float(((z["total_actual"] >= z["E_total_p10"]) & (z["total_actual"] <= z["E_total_p90"])).mean()),
             "margin_interval_width": float((z["E_margin_p90"] - z["E_margin_p10"]).mean())}
        sd = (z["E_margin_p90"] - z["E_margin_p10"]) / 2.5631
        pit = stats.norm.cdf((z["margin"] - z["E_margin"]) / sd)
        r["margin_pit_decile_counts_approx_normal"] = np.histogram(pit, bins=10, range=(0, 1))[0].tolist()
        rows.append(r)
    return {"table": pd.DataFrame(rows)}


def run() -> dict:
    x = frame()
    # T2 opening spread -> probability: sigma fitted walk-forward on earlier seasons (Phi(spread / sigma))
    x["p_open"] = np.nan
    for s in sorted(x["season"].unique()):
        tr = x[(x["season"] < s) & x["sbr_home_spread_close"].notna() & x["home_win"].notna()]
        te = (x["season"] == s) & x["sbr_home_spread_open"].notna()
        if len(tr) < 200 or not te.any():
            sig = 13.5 if te.any() else None
        else:
            grid = np.linspace(9, 18, 91)
            sig = grid[int(np.argmin([M.log_loss(tr["home_win"].to_numpy(), np.clip(stats.norm.cdf(tr["sbr_home_spread_close"] / g_), 1e-4, 1 - 1e-4)) for g_ in grid]))]
        if sig:
            x.loc[te, "p_open"] = stats.norm.cdf(x.loc[te, "sbr_home_spread_open"] / sig)
    cmp_ = comparison(x)
    hyp = hypotheses(x)
    h3r = h3(x)
    ds = drive_sim(x)
    prim = {"H1": hyp["H1_open"]["p"], "H2": hyp["H2_movement_given_close"]["p"], "H3": min(h3r["discover_2018_21_open"]["p_holm"].min(), 1.0),
            "H4": hyp["H4_margin_mae"]["p_open_better"], "H5": hyp["H5_close"]["p_C_vs_M_raw"]}
    order = sorted(prim, key=prim.get)
    run_, holm = 0.0, {}
    for k, h in enumerate(order):
        run_ = max(run_, min(1.0, (len(prim) - k) * prim[h]))
        holm[h] = run_
    OUT.mkdir(parents=True, exist_ok=True)
    for k, v in cmp_.items():
        v.to_csv(OUT / f"compare_{k}.csv", index=False)
    for k in ("discover_2018_21_open", "reproduce_2022_25_close"):
        h3r[k].to_csv(OUT / f"h3_{k}.csv", index=False)
    ds["table"].to_csv(OUT / "drive_sim.csv", index=False)
    summary = {"hypotheses": hyp, "primary_p": prim, "holm": holm, "h3_surviving_flags": h3r["surviving_flags"],
               "h3_top_decile_games": {k: v for k, v in h3r.items() if k.endswith("_games")}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    x.to_parquet(OUT / "analysis_frame.parquet", index=False)
    return {"compare": cmp_, "summary": summary, "h3": h3r, "drive": ds}


def load() -> dict:
    out = {}
    for f in OUT.glob("*.csv"):
        out[f.stem] = pd.read_csv(f)
    j = OUT / "summary.json"
    if j.exists():
        out["summary"] = json.loads(j.read_text())
    return out


def timestamped_2026() -> dict:
    """Equal-information check on completed 2026 games: champion walk-forward probability vs the multi-book no-vig
    consensus as quoted 24 h before kickoff (T1) and at the last pregame quote, from GOING's committed history."""
    from .data_pipeline import GAMES_TABLE
    from .market81 import MKT_RAW
    c = pd.read_parquet(MKT_RAW / "going_consensus.parquet")
    g = pd.read_parquet(GAMES_TABLE)[["game_id", "kickoff_utc", "home_score", "away_score", "completed"]]
    x = pd.read_parquet(OUT / "analysis_frame.parquet")[["game_id", "season", "p_weighted_average", "home_win"]]
    c = c.merge(g, on="game_id")
    rows = []
    for gid, d in c.groupby("game_id"):
        k = d["kickoff_utc"].iloc[0]
        d = d[d["quote_time"] < k].sort_values("quote_time")
        if d.empty:
            continue
        t24 = d[d["quote_time"] <= k - pd.Timedelta(hours=24)]
        rows.append({"game_id": gid, "p_first": d["p_home_consensus"].iloc[0], "first_quote_hours_before": (k - d["quote_time"].iloc[0]).total_seconds() / 3600,
                     "p_24h": t24["p_home_consensus"].iloc[-1] if len(t24) else np.nan, "p_last": d["p_home_consensus"].iloc[-1],
                     "last_quote_minutes_before": (k - d["quote_time"].iloc[-1]).total_seconds() / 60, "books_last": int(d["books"].iloc[-1])})
    m = pd.DataFrame(rows).merge(x, on="game_id").dropna(subset=["home_win", "p_weighted_average", "p_24h"])
    y = m["home_win"].to_numpy()
    res = {"games": int(len(m)), "median_first_quote_hours_before": float(m["first_quote_hours_before"].median()),
           "median_last_quote_minutes_before": float(m["last_quote_minutes_before"].median()), "median_books": float(m["books_last"].median())}
    for col in ("p_weighted_average", "p_first", "p_24h", "p_last"):
        res[f"ll_{col}"] = M.log_loss(y, m[col].to_numpy())
        res[f"acc_{col}"] = float(((m[col] > 0.5) == (y == 1)).mean())
    mv = (_logit(m["p_last"]) - _logit(m["p_first"]))
    res["mean_abs_move_logit"] = float(np.abs(mv).mean())
    res["note"] = "2026 champion probabilities are walk-forward (models trained through 2025, features as of kickoff); about 80 games, descriptive"
    m.to_csv(OUT / "timestamped_2026_games.csv", index=False)
    (OUT / "timestamped_2026.json").write_text(json.dumps(res, indent=2))
    return res
