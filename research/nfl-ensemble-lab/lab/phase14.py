"""Phase 14: QB value model, information-arrival event study, sequential monitors, research ledger.
Exactly as pre-registered in docs/PHASE14_PREREGISTRATION.md (commit 0d0795db). Lab-only.

  python -m lab.phase14 evaluate    QB model: single historical look (2021-24) + validation (refuses to rerun)
  python -m lab.phase14 events      2026 information-arrival event study (repeatable, descriptive)
  python -m lab.phase14 monitor     sequential e-process monitors M1-M6 (repeatable)
  python -m lab.phase14 freeze      frozen pregame QB values for upcoming 2026 games
  python -m lab.phase14 ledger      regenerate docs/LEDGER.md from research_ledger.json
"""
from __future__ import annotations

import glob
import json
import sys

import numpy as np
import pandas as pd
from scipy import optimize, stats

from pathlib import Path

from .config import ARTIFACTS_DIR, RAW_DIR

ROOT = Path(__file__).resolve().parents[1]
from .ingest import normalize_team
from .sequential import e_process, monitor_summary

OUT = ARTIFACTS_DIR / "phase14"
LEDGER = ROOT / "research_ledger.json"
REGISTERED_AT = pd.Timestamp("2026-10-26T21:34:01Z")
SIGMA2_DEFAULT = 2.4


def _ll(y, p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


# --------------------------------------------------------------------------- QB data
def qb_games(seasons) -> pd.DataFrame:
    rows = []
    for s in seasons:
        f = (RAW_DIR / "history" if s <= 2014 else RAW_DIR) / f"play_by_play_{s}.parquet"
        p = pd.read_parquet(f, columns=["game_id", "season", "week", "season_type", "posteam", "qb_dropback", "id", "qb_epa", "cpoe"])
        p = p[(p["qb_dropback"] == 1) & p["id"].notna() & p["qb_epa"].notna()]
        g = p.groupby(["game_id", "season", "week", "season_type", "posteam", "id"]).agg(
            n=("qb_epa", "size"), epa=("qb_epa", "sum"), cpoe_sum=("cpoe", "sum"), cpoe_n=("cpoe", "count")).reset_index()
        rows.append(g)
    q = pd.concat(rows, ignore_index=True).rename(columns={"id": "qb"})
    q["wk"] = q["week"] + np.where(q["season_type"] == "POST", 100, 0)       # postseason after week 18
    return q


def _players():
    pl = pd.read_parquet(RAW_DIR / "players.parquet", columns=["gsis_id", "draft_pick", "rookie_season", "draft_year"])
    pl = pl.drop_duplicates("gsis_id").set_index("gsis_id")
    pl["log_pick"] = np.log(pl["draft_pick"].fillna(260).clip(1, 260))
    pl["rookie"] = pl["rookie_season"].fillna(pl["draft_year"])
    return pl


def asof_table(q: pd.DataFrame, season: int, wk: int) -> pd.DataFrame:
    """Per QB: weighted dropbacks n_eff, weighted mean EPA, career CPOE (attempts) - all strictly before (season, wk)."""
    cur = q[(q["season"] == season) & (q["wk"] < wk)]
    prev = q[q["season"].between(season - 3, season - 1)]
    w = np.r_[np.ones(len(cur)), 0.5 ** (season - prev["season"].to_numpy())]
    both = pd.concat([cur, prev], ignore_index=True)
    both["w"] = w
    both["wn"], both["wepa"] = both["w"] * both["n"], both["w"] * both["epa"]
    a = both.groupby("qb").agg(n_eff=("wn", "sum"), wepa=("wepa", "sum"))
    a["ebar"] = a["wepa"] / a["n_eff"]
    car = q[(q["season"] < season) | ((q["season"] == season) & (q["wk"] < wk))].groupby("qb").agg(cs=("cpoe_sum", "sum"), cn=("cpoe_n", "sum"))
    a = a.join(car, how="outer")
    return a


def _prior_X(qbs, season, pl, car):
    """Design matrix: 1, log pick, experience bucket dummies (1, 2, 3+), shrunk career CPOE (k = 200 attempts)."""
    p = pl.reindex(qbs)
    exp = (season - p["rookie"]).fillna(0).clip(0, 3).to_numpy()
    cs = car.reindex(qbs)
    cp = (cs["cs"].fillna(0) / (cs["cn"].fillna(0) + 200)).to_numpy()
    lp = p["log_pick"].fillna(np.log(260)).to_numpy()
    return np.c_[np.ones(len(qbs)), lp, exp == 1, exp == 2, exp >= 3, cp].astype(float)


def fit_hyper(q: pd.DataFrame, seasons, pl) -> dict:
    """Marginal ML on QB-season observations: ebar ~ N(X b, tau^2 + sigma^2 / n)."""
    sub = q[q["season"].isin(list(seasons))]
    sigma2 = SIGMA2_DEFAULT
    xs, ys, ns = [], [], []
    for s, d in sub.groupby("season"):
        a = d.groupby("qb").agg(n=("n", "sum"), epa=("epa", "sum"))
        car = q[q["season"] < s].groupby("qb").agg(cs=("cpoe_sum", "sum"), cn=("cpoe_n", "sum"))
        xs.append(_prior_X(a.index, s, pl, car))
        ys.append((a["epa"] / a["n"]).to_numpy())
        ns.append(a["n"].to_numpy(float))
    X, y, n = np.vstack(xs), np.concatenate(ys), np.concatenate(ns)

    def nll(z):
        b, tau2 = z[:-1], np.exp(z[-1])
        v = tau2 + sigma2 / n
        return float(np.sum(0.5 * np.log(v) + 0.5 * (y - X @ b) ** 2 / v))
    z = optimize.minimize(nll, np.r_[np.zeros(X.shape[1]), np.log(0.01)], method="L-BFGS-B").x
    return {"b": z[:-1].tolist(), "tau2": float(np.exp(z[-1])), "sigma2": sigma2, "n_obs": int(len(y))}


def posterior(a: pd.DataFrame, qbs, season, pl, hyper) -> pd.Series:
    X = _prior_X(qbs, season, pl, a[["cs", "cn"]])
    mu = X @ np.asarray(hyper["b"])
    r = a.reindex(qbs)
    n = r["n_eff"].fillna(0).to_numpy()
    eb = r["ebar"].fillna(0).to_numpy()
    prec = 1 / hyper["tau2"] + n / hyper["sigma2"]
    return pd.Series((mu / hyper["tau2"] + n * eb / hyper["sigma2"]) / prec, index=list(qbs))


# --------------------------------------------------------------------------- games, QB changes, market adjustment
def game_frame(q) -> pd.DataFrame:
    from .phase13 import games as p13_games
    g = p13_games()
    g = g[g["season"].between(2014, 2026)].copy()
    allg = pd.read_csv(RAW_DIR / "games.csv")
    for c in ("home_team", "away_team"):
        allg[c] = allg[c].map(normalize_team)
    al = pd.concat([allg[["game_id", "season", "gameday", "home_team", "home_qb_id"]].rename(columns={"home_team": "team", "home_qb_id": "qb"}),
                    allg[["game_id", "season", "gameday", "away_team", "away_qb_id"]].rename(columns={"away_team": "team", "away_qb_id": "qb"})])
    al = al.sort_values(["season", "team", "gameday"])
    al["prev_qb"] = al.groupby(["season", "team"])["qb"].shift(1)
    prev = al.set_index(["game_id", "team"])["prev_qb"]
    g["home_prev_qb"] = prev.reindex(pd.MultiIndex.from_arrays([g["game_id"], g["home_team"]])).to_numpy()
    g["away_prev_qb"] = prev.reindex(pd.MultiIndex.from_arrays([g["game_id"], g["away_team"]])).to_numpy()
    g["home_change"] = g["home_prev_qb"].notna() & (g["home_qb_id"] != g["home_prev_qb"])
    g["away_change"] = g["away_prev_qb"].notna() & (g["away_qb_id"] != g["away_prev_qb"])
    g["qb_change"] = g["home_change"] | g["away_change"]
    g["wk"] = g["week"] + np.where(g["game_type"] != "REG", 100, 0)
    # market power ratings: ridge of closing margins on team indicators over each team's previous 6 games (union)
    teams = sorted(set(g["home_team"]) | set(g["away_team"]))
    ti = {t: i for i, t in enumerate(teams)}
    Xall = np.zeros((len(g), len(teams) + 1))
    for i, (h, a) in enumerate(zip(g["home_team"], g["away_team"])):
        Xall[i, ti[h]], Xall[i, ti[a]], Xall[i, -1] = 1, -1, 1
    yall = g["spread_line"].to_numpy(float)
    exp = np.full(len(g), np.nan)
    hist = {t: [] for t in teams}
    for i, (h, a) in enumerate(zip(g["home_team"], g["away_team"])):
        rows_ = sorted(set(j for t in teams for j in hist[t][-6:]))
        if len(rows_) >= 60:
            X, y = Xall[rows_], yall[rows_]
            A = X.T @ X + np.eye(X.shape[1]) * 1.0
            A[-1, -1] -= 1.0 - 1e-6                      # do not shrink home field
            beta = np.linalg.solve(A, X.T @ y)
            exp[i] = Xall[i] @ beta
        hist[h].append(i)
        hist[a].append(i)
    g["market_expected"] = exp
    g["market_qb_adj"] = g["open_margin"] - g["market_expected"]
    return g


def deltas(g, q, pl, hyper_by_season, D_by_season) -> pd.DataFrame:
    """Delta_home for QB-change games: (theta_new - theta_old) * D, home team minus away team, all as of the game."""
    out = []
    pk = None
    for r in g[g["qb_change"]].itertuples(index=False):
        key = (r.season, r.wk)
        if key != pk:
            a = asof_table(q, r.season, r.wk)
            pk = key
        hyper, D = hyper_by_season[r.season], D_by_season[r.season]
        d = {}
        for side in ("home", "away"):
            if getattr(r, f"{side}_change"):
                new, old = getattr(r, f"{side}_qb_id"), getattr(r, f"{side}_prev_qb")
                th = posterior(a, [new, old], r.season, pl, hyper)
                d[side] = float((th.iloc[0] - th.iloc[1]) * D)
            else:
                d[side] = 0.0
        out.append({"game_id": r.game_id, "delta_home": d["home"] - d["away"], "delta_home_team": d["home"], "delta_away_team": d["away"]})
    return pd.DataFrame(out)


def _models(q, pl, seasons):
    hyper, D = {}, {}
    for s in seasons:
        hyper[s] = fit_hyper(q, range(max(2006, s - 10), s), pl)
        tr = q[q["season"].between(s - 5, s - 1)]
        D[s] = float(tr.groupby(["game_id", "posteam"])["n"].sum().mean())
    return hyper, D


def _paired(a, b, n=5000, seed=19):
    d = np.asarray(a) - np.asarray(b)
    obs = d.mean()
    idx = np.random.default_rng(seed).integers(0, len(d), (n, len(d)))
    bm = d[idx].mean(1)
    return {"mean_diff": float(obs), "ci95": [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))],
            "p_one_sided": float((np.sum((bm - obs) <= obs) + 1) / (n + 1))}


def evaluate() -> dict:
    if (OUT / "evaluation.json").exists():
        raise FileExistsError("Phase 14 historical look already taken")
    q = qb_games(range(2006, 2026))
    pl = _players()
    g = game_frame(q)
    seasons = range(2018, 2025)
    hyper, D = _models(q, pl, seasons)
    d = deltas(g[g["season"].isin(list(seasons))], q, pl, hyper, D)
    x = g.merge(d, on="game_id")
    x = x[x["p_champ"].notna() & x["asb_ok"] & x["market_qb_adj"].notna()]
    dev, ev = x[x["season"].between(2018, 2020)], x[x["season"].between(2021, 2024)]
    # gamma on development QB-change games: logistic with offset logit(p_champ), no intercept
    def nll(gm):
        return float(_ll(dev["y"].to_numpy(), 1 / (1 + np.exp(-(_logit(dev["p_champ"]) + gm * dev["delta_home"])))).sum())
    gamma = float(optimize.minimize_scalar(nll, bounds=(-1, 1), method="bounded").x)
    ev = ev.assign(p_adj=1 / (1 + np.exp(-(_logit(ev["p_champ"]) + gamma * ev["delta_home"]))))
    r1 = stats.pearsonr(ev["delta_home"], ev["market_qb_adj"], alternative="greater")
    q2 = _paired(_ll(ev["y"], ev["p_adj"]), _ll(ev["y"], ev["p_champ"]))
    ps = sorted([("Q1", float(r1.pvalue)), ("Q2", q2["p_one_sided"])], key=lambda t: t[1])
    holm, run = {}, 0.0
    for i, (k, pv) in enumerate(ps):
        run = max(run, min(1.0, (2 - i) * pv))
        holm[k] = run
    mv = _logit(ev["p_close"]) - _logit(ev["p_open"])
    res = {"qb_change_games_eval": int(len(ev)), "qb_change_games_dev": int(len(dev)), "gamma": gamma,
           "D": D, "hyper_2021": hyper[2021],
           "Q1_corr_delta_market_adj": {"r": float(r1.statistic), "p_one_sided": float(r1.pvalue), "holm": holm["Q1"],
                                        "passes": bool(holm["Q1"] < 0.05 and r1.statistic > 0)},
           "Q2_logloss_adj_vs_champion": q2 | {"holm": holm["Q2"], "passes": bool(holm["Q2"] < 0.05 and q2["mean_diff"] < 0),
                                               "ll_adj": float(_ll(ev["y"], ev["p_adj"]).mean()), "ll_champion": float(_ll(ev["y"], ev["p_champ"]).mean()),
                                               "ll_open": float(_ll(ev["y"], ev["p_open"]).mean()), "ll_close": float(_ll(ev["y"], ev["p_close"]).mean())},
           "reported": {"corr_delta_open_to_close_move": float(np.corrcoef(ev["delta_home"], ev["close_margin_asb"] - ev["open_margin"])[0, 1]),
                        "clv_corr_adj": float(np.corrcoef(_logit(ev["p_adj"]) - _logit(ev["p_open"]), mv)[0, 1]),
                        "clv_corr_champion": float(np.corrcoef(_logit(ev["p_champ"]) - _logit(ev["p_open"]), mv)[0, 1]),
                        "mean_abs_delta": float(ev["delta_home"].abs().mean()), "mean_abs_market_adj": float(ev["market_qb_adj"].abs().mean()),
                        "slope_market_adj_on_delta": float(np.polyfit(ev["delta_home"], ev["market_qb_adj"], 1)[0])}}
    q1p, q2p = res["Q1_corr_delta_market_adj"]["passes"], res["Q2_logloss_adj_vs_champion"]["passes"]
    res["kill_rule"] = ("killed for fixed-sample work" if (not q1p or r1.statistic < 0.2)
                        else ("continue prospectively as a monitor only" if not q2p else "continue to a frozen prospective challenger"))
    res["validation_538"] = _validate_538(x)
    OUT.mkdir(parents=True, exist_ok=True)
    x.to_parquet(OUT / "qb_change_games.parquet", index=False)
    (OUT / "evaluation.json").write_text(json.dumps(res, indent=2, default=str))
    (OUT / "model.json").write_text(json.dumps({"gamma": gamma, "hyper": {int(k): v for k, v in hyper.items()}, "D": D}, indent=2))
    return res


def _validate_538(x) -> dict:
    f = RAW_DIR / "public" / "nfelo_nfelo_games.csv"
    if not f.exists():
        return {"available": False}
    n = pd.read_csv(f)[["game_id", "home_538_qb_adj", "away_538_qb_adj"]]
    v = x.merge(n, on="game_id").dropna(subset=["home_538_qb_adj", "away_538_qb_adj"])
    a538 = (v["home_538_qb_adj"] - v["away_538_qb_adj"]) / 25.0
    return {"available": True, "games": int(len(v)), "corr_delta_vs_538_net_qb_adj": float(np.corrcoef(v["delta_home"], a538)[0, 1]),
            "corr_market_adj_vs_538": float(np.corrcoef(v["market_qb_adj"], a538)[0, 1]),
            "mean_abs_538_points": float(a538.abs().mean())}


# --------------------------------------------------------------------------- 2026 information-arrival events
def _espn_qb_out(f):
    d = json.load(open(f, encoding="utf-8"))
    ts = pd.Timestamp(d.get("timestamp") or f.split("_")[-1].replace(".json", ""), tz="UTC") if d.get("timestamp") else None
    out = []
    for t in d.get("injuries", []):
        for it in t.get("injuries", []):
            ath = it.get("athlete", {})
            pos = ((ath.get("position") or {}).get("abbreviation"))
            if pos == "QB" and str(it.get("status", "")).lower() in ("out", "doubtful", "injured reserve"):
                out.append({"t": ts, "team_name": t.get("displayName"), "player": ath.get("displayName")})
    return out


def events() -> dict:
    from .market81 import espn_archive
    from .upsets85 import _team
    dc = pd.read_parquet(RAW_DIR / "depth_charts_2026.parquet")
    dc = dc[(dc["pos_abb"] == "QB") & (dc["pos_rank"] == 1)].copy()
    dc["t"] = pd.to_datetime(dc["dt"], utc=True)
    dc["team"] = dc["team"].map(normalize_team)
    dc = dc.sort_values(["team", "t"])
    dc["prev"] = dc.groupby("team")["player_name"].shift(1)
    ev = dc[dc["prev"].notna() & (dc["player_name"] != dc["prev"]) & (dc["t"] >= pd.Timestamp("2026-09-01", tz="UTC"))]
    E = [{"t": r.t, "team": r.team, "kind": "depth_chart_qb1_change", "detail": f"{r.prev} -> {r.player_name}"} for r in ev.itertuples()]
    q1 = dc.drop_duplicates(["team", "t"], keep="last")
    seen = set()
    for f in sorted(glob.glob(str(RAW_DIR / "archive" / "espn_injuries_*.json"))):
        for o in _espn_qb_out(f):
            team = _team(o["team_name"])
            if not team or o["t"] is None:
                continue
            starters = q1[(q1["team"] == team) & (q1["t"] <= o["t"])]
            if starters.empty or starters.iloc[-1]["player_name"].split(" ")[-1] not in str(o["player"]):
                continue
            k = (team, o["player"])
            if k not in seen:
                seen.add(k)
                E.append({"t": o["t"], "team": team, "kind": "qb1_out_or_doubtful_espn", "detail": o["player"]})
    E = pd.DataFrame(E)
    arc = espn_archive()
    if E.empty or arc.empty:
        return {"events": 0}
    arc["retrieved_at"] = pd.to_datetime(arc["retrieved_at"], utc=True)
    arc["ko"] = pd.to_datetime(arc["kickoff"], utc=True, errors="coerce")
    arc["spread"] = pd.to_numeric(arc["home_spread_close"].astype(str).str.replace("+", "", regex=False), errors="coerce")
    rng = np.random.default_rng(14)
    rows = []
    for e in E.itertuples(index=False):
        g = arc[((arc["home"] == e.team) | (arc["away"] == e.team)) & (arc["ko"] > e.t)]
        if g.empty:
            continue
        ko = g["ko"].min()
        g = g[g["ko"] == ko].sort_values("retrieved_at")
        before = g[g["retrieved_at"] <= e.t]
        if before.empty:
            continue
        b = before.iloc[-1]["spread"]
        rec = {"t": e.t, "team": e.team, "kind": e.kind, "detail": e.detail, "kickoff": ko, "spread_before": b}
        for lbl, dt in (("1h", 1), ("6h", 6), ("24h", 24)):
            a = g[g["retrieved_at"] >= e.t + pd.Timedelta(hours=dt)]
            rec[f"move_{lbl}"] = float(a.iloc[0]["spread"] - b) if len(a) and a.iloc[0]["retrieved_at"] < ko else np.nan
        rec["move_close"] = float(g[g["retrieved_at"] < ko].iloc[-1]["spread"] - b)
        # random-time comparison for the same game
        span = g[g["retrieved_at"] < ko]
        if len(span) > 2:
            rt = span["retrieved_at"].iloc[rng.integers(0, len(span) - 1)]
            rb = span[span["retrieved_at"] <= rt].iloc[-1]["spread"]
            ra = span[span["retrieved_at"] >= rt + pd.Timedelta(hours=24)]
            rec["random_move_24h"] = float(ra.iloc[0]["spread"] - rb) if len(ra) else np.nan
        rows.append(rec)
    t = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT / "events_2026.csv", index=False)
    res = {"events_with_lines": int(len(t)), "by_kind": t.groupby("kind").size().to_dict() if len(t) else {},
           "mean_abs_move": {c: float(t[c].abs().mean()) for c in ("move_1h", "move_6h", "move_24h", "move_close", "random_move_24h") if c in t and t[c].notna().any()}}
    return res


# --------------------------------------------------------------------------- sequential monitors
def monitor() -> dict:
    from .compare7 import collect
    df = collect()
    res = {"registered_at": str(REGISTERED_AT)}
    if df.empty:
        return res
    df["predicted_at"] = pd.to_datetime(df["predicted_at"], utc=True)
    fin = df[(df["stage"] == "final") & (df["predicted_at"] >= REGISTERED_AT)].sort_values("predicted_at")
    vers = sorted(fin["version"].unique())
    piv = fin.pivot_table(index=["game_id", "home_win"], columns="version", values="p", aggfunc="last").reset_index()
    champ = next((v for v in vers if v.startswith("v20261016")), None)
    y = piv["home_win"].to_numpy(float) if len(piv) else np.array([])
    if champ and len(piv):
        lc = _ll(y, piv[champ])
        for name, v in (("M2_p5_vs_champion", next((v for v in vers if "p5" in v), None)), ("M3_p7_vs_champion", next((v for v in vers if "p7" in v), None))):
            if v:
                res[name] = monitor_summary(lc - _ll(y, piv[v]), 0.005)
        g = pd.read_csv(RAW_DIR / "games.csv").set_index("game_id")
        from .market81 import american_to_prob, novig
        gg = g.reindex(piv["game_id"])
        pc = np.asarray(novig(american_to_prob(pd.to_numeric(gg["home_moneyline"], errors="coerce").to_numpy()),
                              american_to_prob(pd.to_numeric(gg["away_moneyline"], errors="coerce").to_numpy())), float)
        k = ~np.isnan(pc)
        res["M4_close_vs_champion"] = monitor_summary((lc - _ll(y, pc))[k], 0.005)
        try:
            from . import market_blend11 as MB
            sc = MB.score() if hasattr(MB, "score") else None
            if isinstance(sc, pd.DataFrame) and {"game_id", "p_blend"}.issubset(sc.columns):
                m = piv.merge(sc[["game_id", "p_blend"]], on="game_id")
                res["M1_blend_vs_champion"] = monitor_summary(_ll(m["home_win"], m[champ]) - _ll(m["home_win"], m["p_blend"]), 0.005)
        except Exception as e:  # noqa: BLE001
            res["M1_blend_vs_champion"] = {"error": repr(e)}
    try:
        from .upsets84 import prospective_frame  # noqa: F401
        res["M5_S2P"] = {"note": "evaluated from the S2P archive once flagged games accrue after registration"}
    except Exception:  # noqa: BLE001
        pass
    fz = sorted((OUT / "prospective").glob("qb_values_*.parquet")) if (OUT / "prospective").exists() else []
    res["M6_qb_adjustment"] = {"frozen_files": len(fz), "note": "scored once 2026 QB-change games with frozen values complete"}
    res["program_stopping_rule"] = ("Phase 15: if no monitor reaches e >= 20 by the end of the 2026 regular season (week 18), "
                                    "the QB and late-news program is paused in the ledger and effort moves to the next ranked item")
    res["any_crossed"] = any(isinstance(v, dict) and v.get("crossed") for v in res.values())
    res["futile"] = [k for k, v in res.items() if isinstance(v, dict) and v.get("futile")]
    (OUT / "monitor.json").write_text(json.dumps(res, indent=2, default=str))
    return res


# --------------------------------------------------------------------------- freeze
def freeze() -> dict:
    m = json.loads((OUT / "model.json").read_text())
    q = qb_games(range(2023, 2027))
    pl = _players()
    hyper = fit_hyper(qb_games(range(2016, 2026)), range(2016, 2026), pl)
    dc = pd.read_parquet(RAW_DIR / "depth_charts_2026.parquet")
    dc = dc[dc["pos_abb"] == "QB"]
    dc = dc[dc["dt"] == dc["dt"].max()]
    dc = dc[dc["pos_rank"] <= 2]
    a = asof_table(q, 2026, 999)
    th = posterior(a, list(dc["gsis_id"]), 2026, pl, hyper)
    D = float(q[q["season"].between(2021, 2025)].groupby(["game_id", "posteam"])["n"].sum().mean())
    out = dc[["team", "player_name", "gsis_id", "pos_rank"]].assign(theta=th.to_numpy(), value_points=th.to_numpy() * D,
                                                                     depth_chart_dt=dc["dt"].iloc[0], gamma=m["gamma"])
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%SZ")
    (OUT / "prospective").mkdir(parents=True, exist_ok=True)
    f = OUT / "prospective" / f"qb_values_{stamp}.parquet"
    out.to_parquet(f, index=False)
    piv = out.pivot_table(index="team", columns="pos_rank", values="value_points")
    piv["drop_if_starter_out"] = piv[2] - piv[1]
    return {"file": f.name, "teams": int(len(piv)), "largest_drops": piv["drop_if_starter_out"].nsmallest(5).round(2).to_dict()}


# --------------------------------------------------------------------------- ledger
def ledger_md() -> str:
    L = json.loads(LEDGER.read_text())
    items = sorted(L["items"], key=lambda r: (not r.get("pinned", False), -(r.get("score") or 0)))
    lines = ["# Research ledger and backlog", "", f"Generated from `research_ledger.json`. Score = {L['score_formula']}.", "",
             (f"Program stopping rule: {L['program_stopping_rule']['rule']}" if L.get("program_stopping_rule") else ""), "",
             L.get("note", ""), "",
             "| Rank | ID | Hypothesis | Status | Score | Gap targeted | Games to detect | Cost (h) | Kill rule |", "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(items, 1):
        lines.append(f"| {i} | {r['id']} | {r['title']} | {r['status']} | {r.get('score', '')} | {r.get('gap', '')} | {r.get('games_needed', '')} | "
                     f"{r.get('cost_h', '')} | {r.get('kill_rule', '')} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "evaluate"
    OUT.mkdir(parents=True, exist_ok=True)
    if cmd == "ledger":
        (ROOT / "docs" / "LEDGER.md").write_text(ledger_md(), encoding="utf-8")
        print("docs/LEDGER.md written")
    else:
        r = {"evaluate": evaluate, "events": events, "monitor": monitor, "freeze": freeze}[cmd]()
        if cmd in ("events", "freeze"):
            (OUT / f"{cmd}.json").write_text(json.dumps(r, indent=2, default=str))
        print(json.dumps(r, indent=2, default=str)[:5000])
