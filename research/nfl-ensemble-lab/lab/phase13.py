"""Phase 13: error budget, information-timing audit, Kalman market-anchored challenger, simulator coherence.
Exactly as pre-registered in docs/PHASE13_PREREGISTRATION.md (commit 294685aa). Lab-only.

  python -m lab.phase13 budget      A + B + E (descriptive)
  python -m lab.phase13 ablation    C development seasons 2018-20 -> ablation.json
  python -m lab.phase13 evaluate    C single look 2021-24 (refuses without ablation.json, refuses to rerun)
  python -m lab.phase13 coherence   D
  python -m lab.phase13 freeze      2026 prospective challenger forecasts
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd
from scipy import optimize, stats

from .config import ARTIFACTS_DIR, RAW_DIR
from .ingest import normalize_team

OUT = ARTIFACTS_DIR / "phase13"
PUB = RAW_DIR / "public"
NAMES = None


# --------------------------------------------------------------------------- shared data
def _ll(y, p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def games() -> pd.DataFrame:
    """2014-2025 completed REG/POST games with nflverse close, ASB open/close, champion OOF, nfelo."""
    from .market81 import american_to_prob, novig
    from .specialists.baseline import load_oof
    from .upsets85 import load_asb, match_asb
    g = pd.read_csv(RAW_DIR / "games.csv")
    g = g[g["season"].between(2014, 2026) & g["home_score"].notna()].copy()
    for c in ("home_team", "away_team"):
        g[c] = g[c].map(normalize_team)
    g = g[g["home_score"] != g["away_score"]].sort_values(["gameday", "gametime", "game_id"]).reset_index(drop=True)
    g["y"] = (g["home_score"] > g["away_score"]).astype(float)
    g["margin"] = g["home_score"] - g["away_score"]
    pc = np.asarray(novig(american_to_prob(pd.to_numeric(g["home_moneyline"], errors="coerce")),
                          american_to_prob(pd.to_numeric(g["away_moneyline"], errors="coerce"))), float)
    g["p_close"] = np.where(np.isnan(pc), stats.norm.cdf(g["spread_line"] / 13.5), pc)
    a = match_asb(load_asb(), g)[["game_id", "asb_home_line_open", "asb_home_line_close", "asb_home_odds_open", "asb_away_odds_open"]]
    g = g.merge(a, on="game_id", how="left")
    ho, ao = 1 / g["asb_home_odds_open"], 1 / g["asb_away_odds_open"]
    g["p_open"] = ho / (ho + ao)
    g["open_margin"] = -g["asb_home_line_open"]                      # + = home favoured
    g["close_margin_asb"] = -g["asb_home_line_close"]
    g["asb_ok"] = g["asb_home_line_open"].notna() & g["asb_home_line_close"].notna() & g["p_open"].notna()
    o = load_oof()[["game_id", "p_weighted_average"]].rename(columns={"p_weighted_average": "p_champ"})
    g = g.merge(o, on="game_id", how="left")
    f = PUB / "nfelo_nfelo_games.csv"
    if f.exists():
        n = pd.read_csv(f)[["game_id", "nfelo_home_probability_open", "nfelo_home_probability_close"]]
        g = g.merge(n.rename(columns={"nfelo_home_probability_open": "p_nfelo_open", "nfelo_home_probability_close": "p_nfelo_close"}),
                    on="game_id", how="left")
    return g


def murphy(y, p, bins=10) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    b = np.minimum((p * bins).astype(int), bins - 1)
    ybar = y.mean()
    rel = res = 0.0
    for k in range(bins):
        m = b == k
        if m.any():
            rel += m.sum() * (p[m].mean() - y[m].mean()) ** 2
            res += m.sum() * (y[m].mean() - ybar) ** 2
    n = len(y)
    return {"brier": float(np.mean((p - y) ** 2)), "reliability": rel / n, "resolution": res / n, "uncertainty": float(ybar * (1 - ybar))}


def _boot_ci(d, n=2000, seed=13):
    d = np.asarray(d, float)
    idx = np.random.default_rng(seed).integers(0, len(d), (n, len(d)))
    m = d[idx].mean(1)
    return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def _platt_walkforward(df) -> np.ndarray:
    out = df["p_champ"].to_numpy(float).copy()
    from sklearn.linear_model import LogisticRegression
    for s in sorted(df["season"].unique()):
        tr = df[df["season"] < s]
        if len(tr) < 200:
            continue
        m = LogisticRegression(C=1e6).fit(_logit(tr["p_champ"]).reshape(-1, 1), tr["y"])
        k = (df["season"] == s).to_numpy()
        out[k] = m.predict_proba(_logit(df.loc[k, "p_champ"]).reshape(-1, 1))[:, 1]
    return out


# --------------------------------------------------------------------------- A, E, 2026 stages
def budget(g: pd.DataFrame) -> dict:
    d = g[g["season"].between(2018, 2024) & g["asb_ok"] & g["p_champ"].notna()].copy()
    y = d["y"].to_numpy()
    d["p_champ_cal"] = _platt_walkforward(d)
    L = {k: _ll(y, d[c]) for k, c in (("champion", "p_champ"), ("champion_recal", "p_champ_cal"), ("open", "p_open"), ("close", "p_close"))}
    ent = -(d["p_close"] * np.log(d["p_close"]) + (1 - d["p_close"]) * np.log(1 - d["p_close"]))
    r = {"games": int(len(d)), "log_loss": {k: float(v.mean()) for k, v in L.items()},
         "noise_floor": {"close_entropy": float(ent.mean()), "margin_sd_vs_close": float(np.std(d["margin"] - d["spread_line"])),
                         "margin_sd_vs_open": float(np.std(d["margin"] - d["open_margin"]))},
         "murphy": {k: murphy(y, d[c]) for k, c in (("champion", "p_champ"), ("open", "p_open"), ("close", "p_close"))}}
    gap = L["champion"] - L["close"]
    parts = {"total_champion_minus_close": gap, "calibration": L["champion"] - L["champion_recal"],
             "modelling_vs_opener": L["champion_recal"] - L["open"], "market_after_open": L["open"] - L["close"]}
    r["gap_attribution"] = {k: {"mean": float(v.mean()), "ci95": _boot_ci(v)} for k, v in parts.items()}
    sd = float(np.std(gap, ddof=1))
    z = 1.645 + 0.842
    r["power"] = {"sd_paired_ll_diff": sd, "games_needed": {str(dl): int(np.ceil((z * sd / dl) ** 2)) for dl in (0.002, 0.005, 0.01, 0.02)},
                  "games_needed_line_move_corr_0.1": int(np.ceil((z / np.arctanh(0.1)) ** 2 + 3)),
                  "regular_season_games_per_year": 272}
    # E: line-move prediction and nfelo
    mv = _logit(d["p_close"]) - _logit(d["p_open"])
    r["line_move_prediction"] = {"champion": float(np.corrcoef(_logit(d["p_champ"]) - _logit(d["p_open"]), mv)[0, 1])}
    if "p_nfelo_open" in d:
        k = d["p_nfelo_open"].notna() & d["p_nfelo_close"].notna()
        r["line_move_prediction"]["nfelo_open"] = float(np.corrcoef(_logit(d.loc[k, "p_nfelo_open"]) - _logit(d.loc[k, "p_open"]), mv[k])[0, 1])
        r["nfelo"] = {"games": int(k.sum()), "ll_nfelo_open": float(_ll(y[k], d.loc[k, "p_nfelo_open"]).mean()),
                      "ll_nfelo_close": float(_ll(y[k], d.loc[k, "p_nfelo_close"]).mean()),
                      "ll_champion_same_games": float(L["champion"][k].mean()), "ll_open_same_games": float(L["open"][k].mean()),
                      "ll_close_same_games": float(L["close"][k].mean())}
    d[["game_id", "season", "week", "y", "p_champ", "p_champ_cal", "p_open", "p_close"]].to_parquet(OUT / "budget_games.parquet", index=False)
    return r


def stages_2026() -> dict:
    """Champion vs the archived DraftKings line at each stage's snapshot time (descriptive, small n)."""
    from .compare7 import collect
    from .data_pipeline import load_feature_store
    from .market81 import american_to_prob, espn_archive, novig
    df, arc = collect(), espn_archive()
    if df.empty or arc.empty:
        return {"games": 0}
    df["predicted_at"] = pd.to_datetime(df["predicted_at"], utc=True)
    df = df[df["version"] == df["version"].iloc[0]]
    arc["retrieved_at"] = pd.to_datetime(arc["retrieved_at"], utc=True)
    fs = load_feature_store().drop_duplicates("game_id").set_index("game_id")
    rows = []
    for r in df.itertuples(index=False):
        if r.game_id not in fs.index:
            continue
        h, a = fs.loc[r.game_id, "home_team"], fs.loc[r.game_id, "away_team"]
        q = arc[(arc["home"] == h) & (arc["away"] == a) & (arc["retrieved_at"] <= r.predicted_at)]
        if q.empty:
            continue
        last = q.iloc[-1]
        try:
            pm = float(novig(american_to_prob([float(str(last["home_ml_close"]).replace("+", ""))]),
                             american_to_prob([float(str(last["away_ml_close"]).replace("+", ""))]))[0])
        except (TypeError, ValueError):
            continue
        rows.append({"game_id": r.game_id, "stage": r.stage, "y": r.home_win, "p": r.p, "p_mkt": pm})
    t = pd.DataFrame(rows)
    if t.empty:
        return {"games": 0}
    t["ll_champ"], t["ll_mkt"] = _ll(t["y"], t["p"]), _ll(t["y"], t["p_mkt"])
    return {"by_stage": t.groupby("stage").agg(n=("y", "size"), ll_champion=("ll_champ", "mean"), ll_market_at_time=("ll_mkt", "mean")).round(4).to_dict("index")}


# --------------------------------------------------------------------------- B audit
def _starters(season):
    """Per (team, week): set of top-11 offense + top-11 defense gsis ids by season-to-date mean snap share before that week."""
    s = pd.read_parquet(RAW_DIR / f"snap_counts_{season}.parquet")
    s = s[s["game_type"] == "REG"]
    pl = pd.read_parquet(RAW_DIR / "players.parquet", columns=["gsis_id", "pfr_id"]).dropna().drop_duplicates("pfr_id").set_index("pfr_id")["gsis_id"]
    s["gsis_id"] = s["pfr_player_id"].map(pl)
    s["team"] = s["team"].map(normalize_team)
    out = {}
    for w in range(1, 19):
        prior = s[s["week"] < w]
        if prior.empty:
            continue
        for t, d in prior.groupby("team"):
            o = d.groupby("gsis_id")["offense_pct"].mean().nlargest(11).index
            de = d.groupby("gsis_id")["defense_pct"].mean().nlargest(11).index
            out[(t, w)] = set(o) | set(de)
    return out


def audit(g: pd.DataFrame) -> dict:
    d = g[g["season"].between(2018, 2024) & g["asb_ok"] & g["p_champ"].notna()].copy()
    # QB change vs the team's previous game in the same season
    long = pd.concat([d[["game_id", "season", "gameday", "home_team", "home_qb_id"]].rename(columns={"home_team": "team", "home_qb_id": "qb"}),
                      d[["game_id", "season", "gameday", "away_team", "away_qb_id"]].rename(columns={"away_team": "team", "away_qb_id": "qb"})])
    allg = pd.read_csv(RAW_DIR / "games.csv")
    for c in ("home_team", "away_team"):
        allg[c] = allg[c].map(normalize_team)
    al = pd.concat([allg[["game_id", "season", "gameday", "home_team", "home_qb_id"]].rename(columns={"home_team": "team", "home_qb_id": "qb"}),
                    allg[["game_id", "season", "gameday", "away_team", "away_qb_id"]].rename(columns={"away_team": "team", "away_qb_id": "qb"})])
    al = al.sort_values(["season", "team", "gameday"])
    al["prev_qb"] = al.groupby(["season", "team"])["qb"].shift(1)
    al["qb_change"] = al["prev_qb"].notna() & (al["qb"] != al["prev_qb"])
    qc = al.groupby("game_id")["qb_change"].any()
    d["qb_change"] = d["game_id"].map(qc).fillna(False)
    # starters Out on a pre-kickoff report, and starters INA
    d["kickoff"] = pd.to_datetime(d["gameday"] + " " + d["gametime"]).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
    out_flag, ina_flag = {}, {}
    for s in range(2018, 2025):
        st = _starters(s)
        inj = pd.read_parquet(RAW_DIR / f"injuries_{s}.parquet")
        inj = inj[inj["report_status"] == "Out"].copy()
        inj["team"] = inj["team"].map(normalize_team)
        inj["dm"] = pd.to_datetime(inj["date_modified"], utc=True, errors="coerce")
        ros = pd.read_parquet(RAW_DIR / f"roster_weekly_{s}.parquet", columns=["week", "team", "gsis_id", "status"])
        ros = ros[ros["status"] == "INA"]
        ros["team"] = ros["team"].map(normalize_team)
        for r in d[d["season"] == s].itertuples(index=False):
            for t in (r.home_team, r.away_team):
                S = st.get((t, r.week), set())
                if not S:
                    continue
                o = inj[(inj["team"] == t) & (inj["week"] == r.week) & (inj["dm"] < r.kickoff)]
                if o["gsis_id"].isin(S).any():
                    out_flag[r.game_id] = True
                if ros[(ros["team"] == t) & (ros["week"] == r.week)]["gsis_id"].isin(S).any():
                    ina_flag[r.game_id] = True
    d["starter_out"] = d["game_id"].map(out_flag).fillna(False)
    d["starter_ina"] = d["game_id"].map(ina_flag).fillna(False)
    d["wind15"] = d["game_id"].map(_wind_forecasts(d))
    y = d["y"].to_numpy()
    d["gap"] = _ll(y, d["p_champ"]) - _ll(y, d["p_close"])
    d["move"] = (d["open_margin"] - d["close_margin_asb"]).abs()
    d["dis"] = _logit(d["p_champ"]) - _logit(d["p_open"])
    d["mv"] = _logit(d["p_close"]) - _logit(d["p_open"])
    res = {}
    for tag in ("qb_change", "starter_out", "starter_ina", "wind15"):
        k = d[tag].astype("boolean")
        sub = d[k.notna()]
        kk = sub[tag].astype(bool)
        res[tag] = {"games": int(len(sub)), "tagged": int(kk.sum()), "share": float(kk.mean()),
                    "mean_abs_move_tagged": float(sub.loc[kk, "move"].mean()) if kk.any() else None,
                    "mean_abs_move_untagged": float(sub.loc[~kk, "move"].mean()),
                    "champion_gap_to_close_tagged": float(sub.loc[kk, "gap"].mean()) if kk.any() else None,
                    "champion_gap_to_close_untagged": float(sub.loc[~kk, "gap"].mean()),
                    "gap_diff_ci95": _boot_ci(sub.loc[kk, "gap"].to_numpy()) if kk.sum() > 10 else None,
                    "champion_predicts_move_corr_tagged": float(np.corrcoef(sub.loc[kk, "dis"], sub.loc[kk, "mv"])[0, 1]) if kk.sum() > 10 else None}
    return res


def _wind_forecasts(d) -> dict:
    """Open-Meteo historical forecast (2022-24) wind at kickoff for outdoor/open games; one request per stadium per season."""
    import requests
    from . import geo
    cache = OUT / "wind_cache.json"
    store = json.loads(cache.read_text()) if cache.exists() else {}
    res = {}
    sub = d[d["season"].between(2022, 2024) & d["roof"].isin(["outdoors", "open"])]
    for (sid, s), grp in sub.groupby(["stadium_id", "season"]):
        if sid not in geo.STADIUMS:
            continue
        key = f"{sid}_{s}"
        if key not in store:
            lat, lon, _ = geo.STADIUMS[sid]
            start, end = grp["gameday"].min(), grp["gameday"].max()
            url = ("https://historical-forecast-api.open-meteo.com/v1/forecast"
                   f"?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}&hourly=wind_speed_10m&wind_speed_unit=mph&timezone=UTC")
            try:
                j = requests.get(url, timeout=30).json()
                store[key] = dict(zip(j["hourly"]["time"], j["hourly"]["wind_speed_10m"]))
            except Exception:  # noqa: BLE001
                store[key] = {}
            time.sleep(0.5)
        for r in grp.itertuples(index=False):
            hk = r.kickoff.strftime("%Y-%m-%dT%H:00")
            v = store[key].get(hk)
            if v is not None:
                res[r.game_id] = bool(v >= 15)
    OUT.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(store))
    return res


# --------------------------------------------------------------------------- C Kalman challenger
def win_totals() -> pd.DataFrame:
    rows = []
    from .upsets85 import _team
    for f in sorted((PUB / "sportsoddshistory").glob("win_*.html")):
        s = int(f.stem.split("_")[1])
        t = pd.read_html(f)[0]
        for r in t.itertuples(index=False):
            team = _team(r[0])
            if team:
                rows.append({"season": s, "team": team, "wt": float(r[1])})
    w = pd.DataFrame(rows).drop_duplicates(["season", "team"])
    return w


def kalman_run(g: pd.DataFrame, q: float, h: float, R: float, prior: dict | None, use_dynamic=True, P0=36.0, shrink=0.5):
    """Online predictions (made before each game) of home margin and its variance. prior[(season, team)] = prior mean."""
    th, P, last_season = {}, {}, None
    pred, var = np.zeros(len(g)), np.zeros(len(g))
    season_end = {}
    for i, r in enumerate(g.itertuples(index=False)):
        if r.season != last_season:
            if last_season is not None:
                season_end[last_season] = dict(th)
            for t in set(th) | {r.home_team, r.away_team}:
                pm = prior.get((r.season, t)) if prior else None
                th[t] = pm if pm is not None else shrink * th.get(t, 0.0)
                P[t] = P0
            last_season = r.season
        for t in (r.home_team, r.away_team):
            th.setdefault(t, 0.0)
            P.setdefault(t, P0)
            if use_dynamic:
                P[t] += q
        m = th[r.home_team] - th[r.away_team] + h
        S = P[r.home_team] + P[r.away_team] + R
        pred[i], var[i] = m, S
        e = r.margin - m
        kh, ka = P[r.home_team] / S, P[r.away_team] / S
        th[r.home_team] += kh * e
        th[r.away_team] -= ka * e
        P[r.home_team] *= (1 - kh)
        P[r.away_team] *= (1 - ka)
    season_end[last_season] = dict(th)
    return pred, var, season_end


def _priors(g, wt, beta):
    if wt is None or beta is None:
        return None
    mu = wt.groupby("season")["wt"].transform("mean")
    return {(s, t): beta * (v - m) for s, t, v, m in zip(wt["season"], wt["team"], wt["wt"], mu)}


def fit_and_predict(g: pd.DataFrame, eval_season: int, comp: dict, wt: pd.DataFrame | None) -> pd.DataFrame:
    """Fit q, h, R (margin likelihood), beta (win-total slope), kappa, sigma on seasons < eval_season; predict eval_season online."""
    hist = g[g["season"] < eval_season]
    beta = None
    if comp["win_total_prior"] and wt is not None:
        # beta: end-of-season ratings (from a default-parameter run) regressed on win-total deviation, seasons < eval_season
        _, _, ends = kalman_run(hist, 1.0, 1.8, 13.5 ** 2, None)
        xs, ys = [], []
        for (s, t), v in wt.set_index(["season", "team"])["wt"].items():
            if s < eval_season and s in ends and t in ends[s]:
                xs.append(v - wt.loc[wt["season"] == s, "wt"].mean())
                ys.append(ends[s][t])
        beta = float(np.dot(xs, ys) / np.dot(xs, xs)) if len(xs) >= 32 else None
    prior = _priors(g, wt, beta) if comp["win_total_prior"] else None
    fit_rows = (hist["season"] >= 2015).to_numpy()

    def nll(x):
        q, h, R = np.exp(x[0]), x[1], np.exp(x[2])
        p, v, _ = kalman_run(hist, q, h, R, prior, comp["dynamic"])
        e = hist["margin"].to_numpy() - p
        return float(np.sum((0.5 * np.log(v) + 0.5 * e ** 2 / v)[fit_rows]))
    x0 = [np.log(1.0), 1.8, np.log(13.5 ** 2)]
    if comp["dynamic"]:
        sol = optimize.minimize(nll, x0, method="Nelder-Mead", options={"maxiter": 200, "xatol": 1e-3, "fatol": 1e-2})
        q, h, R = np.exp(sol.x[0]), sol.x[1], np.exp(sol.x[2])
    else:
        sol = optimize.minimize(lambda z: nll([np.log(1e-9), z[0], z[1]]), x0[1:], method="Nelder-Mead", options={"maxiter": 200})
        q, h, R = 0.0, sol.x[0], np.exp(sol.x[1])
    upto = g[g["season"] <= eval_season]
    pred, var, _ = kalman_run(upto, q, h, R, prior, comp["dynamic"])
    upto = upto.assign(model_margin=pred)
    tr = upto[(upto["season"] < eval_season) & (upto["season"] >= 2015) & upto["asb_ok"]]
    if comp["anchor"]:
        def bll(z):
            k, sg = z[0], np.exp(z[1])
            f = tr["open_margin"] + k * (tr["model_margin"] - tr["open_margin"])
            return float(_ll(tr["y"].to_numpy(), stats.norm.cdf(f / sg)).sum())
        z = optimize.minimize(bll, [0.3, np.log(13.0)], method="Nelder-Mead").x
        kappa, sigma = float(z[0]), float(np.exp(z[1]))
    else:
        kappa = 1.0
        sigma = float(np.exp(optimize.minimize_scalar(lambda ls: float(_ll(tr["y"].to_numpy(), stats.norm.cdf(tr["model_margin"] / np.exp(ls))).sum()),
                                                       bounds=(1.5, 3.5), method="bounded").x))
    ev = upto[(upto["season"] == eval_season)].copy()
    ev["p_chal"] = stats.norm.cdf((ev["open_margin"] + kappa * (ev["model_margin"] - ev["open_margin"])) / sigma) if comp["anchor"] \
        else stats.norm.cdf(ev["model_margin"] / sigma)
    ev.attrs["params"] = {"q": q, "h": h, "R": R, "beta": beta, "kappa": kappa, "sigma": sigma}
    return ev


FULL = {"win_total_prior": True, "dynamic": True, "anchor": True}


def _season_ll(g, seasons, comp, wt):
    rows, params = [], {}
    for s in seasons:
        ev = fit_and_predict(g, s, comp, wt)
        params[s] = ev.attrs["params"]
        rows.append(ev[ev["asb_ok"] & ev["p_champ"].notna()])
    d = pd.concat(rows)
    return d, params


def ablation(g, wt) -> dict:
    p = OUT / "ablation.json"
    if p.exists():
        return json.loads(p.read_text())
    dev = (2018, 2019, 2020)
    base, _ = _season_ll(g, dev, FULL, wt)
    full_ll = float(_ll(base["y"], base["p_chal"]).mean())
    res = {"full_ll": full_ll, "components": {}}
    kept = dict(FULL)
    for c in FULL:
        comp = dict(FULL, **{c: False})
        d, _ = _season_ll(g, dev, comp, wt)
        ll = float(_ll(d["y"], d["p_chal"]).mean())
        res["components"][c] = {"ll_without": ll, "keep": bool(ll > full_ll)}
        kept[c] = bool(ll > full_ll)
    res["kept"] = kept
    res["written_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, indent=2))
    return res


def _paired(a, b, n=5000, seed=17):
    d = np.asarray(a) - np.asarray(b)
    obs = d.mean()
    idx = np.random.default_rng(seed).integers(0, len(d), (n, len(d)))
    bm = d[idx].mean(1)
    p = float((np.sum((bm - obs) <= obs) + 1) / (n + 1))
    dm = stats.ttest_1samp(d, 0, alternative="less")
    return {"mean_diff": float(obs), "ci95": [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))], "p_bootstrap": p,
            "p_dm": float(dm.pvalue)}


def evaluate(g, wt) -> dict:
    a = OUT / "ablation.json"
    if not a.exists():
        raise FileNotFoundError("ablation.json must exist before the evaluation seasons are scored")
    if (OUT / "evaluation.json").exists():
        raise FileExistsError("Phase 13 evaluation look already taken")
    kept = json.loads(a.read_text())["kept"]
    d, params = _season_ll(g, (2021, 2022, 2023, 2024), kept, wt)
    y = d["y"].to_numpy()
    L = {k: _ll(y, d[c]) for k, c in (("challenger", "p_chal"), ("champion", "p_champ"), ("open", "p_open"), ("close", "p_close"))}
    h1, h2 = _paired(L["challenger"], L["champion"]), _paired(L["challenger"], L["open"])
    ps = sorted([("H1", h1["p_bootstrap"]), ("H2", h2["p_bootstrap"])], key=lambda x: x[1])
    holm, run = {}, 0.0
    for i, (k, pv) in enumerate(ps):
        run = max(run, min(1.0, (2 - i) * pv))
        holm[k] = run
    res = {"games": int(len(d)), "kept_components": kept, "params": params,
           "log_loss": {k: float(v.mean()) for k, v in L.items()},
           "H1_challenger_vs_champion": h1 | {"holm": holm["H1"], "passes": bool(holm["H1"] < 0.05 and h1["mean_diff"] < 0)},
           "H2_challenger_vs_open": h2 | {"holm": holm["H2"], "passes": bool(holm["H2"] < 0.05 and h2["mean_diff"] < 0)},
           "vs_close": _paired(L["challenger"], L["close"]),
           "murphy": {k: murphy(y, d[c]) for k, c in (("challenger", "p_chal"), ("champion", "p_champ"))},
           "line_move_prediction_challenger": float(np.corrcoef(_logit(d["p_chal"]) - _logit(d["p_open"]),
                                                                _logit(d["p_close"]) - _logit(d["p_open"]))[0, 1])}
    blend = _phase11_blend(d)
    if blend is not None:
        res["phase11_blend_ll"] = float(_ll(y, blend).mean())
    if "p_nfelo_open" in d:
        k = d["p_nfelo_open"].notna()
        res["nfelo_open_ll_same_games"] = float(_ll(y[k], d.loc[k, "p_nfelo_open"]).mean())
        res["challenger_ll_same_games"] = float(L["challenger"][k].mean())
    d[["game_id", "season", "week", "y", "p_chal", "p_champ", "p_open", "p_close", "model_margin", "open_margin"]].to_parquet(OUT / "evaluation_games.parquet", index=False)
    (OUT / "evaluation.json").write_text(json.dumps(res, indent=2, default=str))
    return res


def _phase11_blend(d):
    try:
        from . import market_blend11 as MB
        a, b, c = MB.WEIGHTS["intercept"], MB.WEIGHTS["champion"], MB.WEIGHTS["open"]
    except Exception:  # noqa: BLE001
        a, b, c = -0.1319, 0.2569, 0.8165            # frozen in docs/PHASE11_MARKET_BLEND_PREREGISTRATION.md
    return 1 / (1 + np.exp(-(a + b * _logit(d["p_champ"]) + c * _logit(d["p_open"]))))


# --------------------------------------------------------------------------- D simulator coherence
def coherence(limit=60, n_sims=2000) -> dict:
    from .props import evaluate as PE
    from .props import models as M
    from .props import sim as S
    res = {}
    T = M.fit(range(2016, 2024))
    S.calibrate_clock(T)
    P = 8
    pl = {"w_recv": np.zeros(P), "dist_recv": np.full((P, 7), 1 / 7), "coff": np.zeros(P), "w_rush": np.zeros(P), "dist_rush": np.full((P, 7), 1 / 7)}
    tm = [{"pass_off": 0.0, "recv_cols": np.array([0, 1]), "recv_cum": np.array([.6, 1.]), "rush_cols": np.array([2, 3]), "rush_cum": np.array([.8, 1.]), "qb_col": 3},
          {"pass_off": 0.0, "recv_cols": np.array([4, 5]), "recv_cum": np.array([.6, 1.]), "rush_cols": np.array([6, 7]), "rush_cum": np.array([.8, 1.]), "qb_col": 7}]
    dg = {}
    r = S.simulate(T, tm, pl, 4000, [0, 0], np.random.default_rng(3), record=False, diag=dg)
    p24 = M.load_pbp([2024])
    p24 = p24[p24["qtr"] <= 4]
    ng = p24["game_id"].nunique() * 2
    sc = p24[p24["play_type"].isin(["pass", "run"]) & (p24["two_point_attempt"] == 0)]
    g24 = pd.read_csv(RAW_DIR / "games.csv")
    g24 = g24[(g24["season"] == 2024) & (g24["game_type"] == "REG")]
    pts = np.r_[g24["home_score"], g24["away_score"]]
    res["neutral_vs_2024"] = {"sim": {"plays": (dg["pass"] + dg["run"]) / 8000, "yards": dg["yds"] / 8000, "td": dg["td"] / 8000,
                                      "rz_td_rate": dg["rz_td"] / max(dg["rz_trips"], 1), "points_mean": float(r["points"].mean()),
                                      "points_sd": float(r["points"].std())},
                              "real_2024": {"plays": len(sc) / ng, "yards": float(sc["yards_gained"].sum() / ng), "points_mean": float(pts.mean()),
                                            "points_sd": float(pts.std())}}
    tp = PE.OUT / "eval" / "team_points.parquet"
    if tp.exists():
        t = pd.read_parquet(tp)
        sim, imp, act = t[["sim_home", "sim_away"]].to_numpy().ravel(), t[["imp_home", "imp_away"]].to_numpy().ravel(), t[["act_home", "act_away"]].to_numpy().ravel()
        res["eval_2023_25_team_points"] = {"games": int(len(t)), "sim_mean": float(sim.mean()), "implied_mean": float(imp.mean()), "actual_mean": float(act.mean()),
                                           "mae_sim_vs_actual": float(np.abs(sim - act).mean()), "mae_implied_vs_actual": float(np.abs(imp - act).mean()),
                                           "share_gap_over_2": float((np.abs(sim - imp) > 2).mean())}
    pg, cr, tm2 = PE.run_season(2025, n_sims=n_sims, log=lambda m: None, limit=limit)
    if "sim_p_home" in tm2:
        gg = games().set_index("game_id")
        tm2 = tm2.join(gg[["p_champ", "p_close", "y"]], on="game_id").dropna(subset=["p_champ", "p_close"])
        y = tm2["y"].to_numpy()
        res["win_prob_2025_sample"] = {"games": int(len(tm2)), "ll_sim": float(_ll(y, tm2["sim_p_home"]).mean()), "ll_champion": float(_ll(y, tm2["p_champ"]).mean()),
                                       "ll_close": float(_ll(y, tm2["p_close"]).mean()), "corr_sim_close": float(np.corrcoef(tm2["sim_p_home"], tm2["p_close"])[0, 1]),
                                       "corr_sim_champion": float(np.corrcoef(tm2["sim_p_home"], tm2["p_champ"])[0, 1]),
                                       "mean_abs_sim_minus_close": float(np.abs(tm2["sim_p_home"] - tm2["p_close"]).mean())}
    return res


# --------------------------------------------------------------------------- prospective freeze
def freeze(g, wt) -> dict:
    """Frozen challenger forecasts for unplayed 2026 games with an archived DraftKings opener."""
    from .market81 import espn_archive
    kept = json.loads((OUT / "ablation.json").read_text())["kept"]
    allg = pd.read_csv(RAW_DIR / "games.csv")
    allg = allg[allg["season"] == 2026].copy()
    for c in ("home_team", "away_team"):
        allg[c] = allg[c].map(normalize_team)
    upcoming = allg[allg["home_score"].isna()]
    arc = espn_archive()
    arc["retrieved_at"] = pd.to_datetime(arc["retrieved_at"], utc=True)
    hist = g[g["season"] <= 2026]
    ev = fit_and_predict(hist, 2026, kept, wt)
    params = ev.attrs["params"]
    # ratings after the last completed game: re-run and read end state
    _, _, ends = kalman_run(hist, params["q"], params["h"], params["R"], _priors(hist, wt, params["beta"]) if kept["win_total_prior"] else None, kept["dynamic"])
    th = ends.get(2026, {})
    rows = []
    for r in upcoming.itertuples(index=False):
        a = arc[(arc["home"] == r.home_team) & (arc["away"] == r.away_team)]
        if a.empty:
            continue
        try:
            op = -float(str(a.iloc[0]["home_spread_open"]).replace("+", ""))    # ESPN: home negative = favoured
        except (TypeError, ValueError):
            continue
        mm = th.get(r.home_team, 0.0) - th.get(r.away_team, 0.0) + params["h"]
        f = op + params["kappa"] * (mm - op) if kept["anchor"] else mm
        rows.append({"game_id": r.game_id, "week": r.week, "open_margin": op, "model_margin": mm, "p_chal": float(stats.norm.cdf(f / params["sigma"]))})
    out = OUT / "prospective"
    out.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%SZ")
    f = out / f"forecasts_{stamp}.parquet"
    pd.DataFrame(rows).assign(created_at=stamp).to_parquet(f, index=False)
    return {"file": f.name, "games": len(rows), "params": params}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "budget"
    OUT.mkdir(parents=True, exist_ok=True)
    if cmd == "coherence":
        r = coherence()
    else:
        g = games()
        wt = win_totals()
        if cmd == "budget":
            r = {"A_E": budget(g), "stages_2026": stages_2026(), "B_audit": audit(g)}
        elif cmd == "ablation":
            r = ablation(g, wt)
        elif cmd == "evaluate":
            r = evaluate(g, wt)
        elif cmd == "freeze":
            r = freeze(g, wt)
    (OUT / f"{cmd}.json").write_text(json.dumps(r, indent=2, default=str)) if cmd not in ("evaluate",) else None
    print(json.dumps(r, indent=2, default=str)[:6000])
