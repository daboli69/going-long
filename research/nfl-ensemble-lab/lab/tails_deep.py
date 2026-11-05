"""Tails Amendment 1: same-season control, placebo, positive controls, dose-response, raw-source checks. See docs/TAILS_PREREG.md."""
from __future__ import annotations

import re
from io import StringIO

import numpy as np
import pandas as pd

from . import tails
from .tails import RAW, rule
from .tails_tests import holm

RUNGS = (7, 10, 14, 21)
FLAGS = ("u_qb", "u_gap", "u_any")


def _strata(d: pd.DataFrame, flag: np.ndarray, H: np.ndarray):
    """Per season: flagged games, unflagged games, flagged hits and unflagged hits by rung. Seasons without both are dropped."""
    out = []
    for s, ix in d.groupby("season").indices.items():
        f = flag[ix]
        nf, nu = int(f.sum()), int((~f).sum())
        if nf and nu:
            out.append((nf, nu, H[ix][f].sum(0), H[ix][~f].sum(0), H[ix].sum(0), len(ix)))
    return out


def control_stat(st) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nf = sum(x[0] for x in st)
    obs = sum(x[2] for x in st)
    exp = sum(x[0] * x[3] / x[1] for x in st)
    return (obs - exp) / nf, obs / exp, obs / nf


def boot_p(st, rng, draws: int) -> np.ndarray:
    """One-sided bootstrap by game within each season (binomial form: a game's hit is 0 or 1), p = share of draws with statistic at or below zero."""
    nf_tot = sum(x[0] for x in st)
    tot = 0.0
    for nf, nu, hf, hu, _, _ in st:
        bf = rng.binomial(nf, hf / nf, (draws, len(hf)))
        bu = rng.binomial(nu, hu / nu, (draws, len(hu)))
        tot = tot + (bf - nf * bu / nu)
    return ((tot / nf_tot) <= 0).mean(0)


def placebo(d: pd.DataFrame, flag: np.ndarray, H: np.ndarray, rng, draws: int) -> np.ndarray:
    """Statistic under random flags with the same count in each season."""
    nf_tot, acc = 0, np.zeros((draws, H.shape[1]))
    for s, ix in d.groupby("season").indices.items():
        nf = int(flag[ix].sum())
        if not nf or nf == len(ix):
            continue
        Hs = H[ix]
        pick = np.argsort(rng.random((draws, len(ix))), axis=1)[:, :nf]
        hf = Hs[pick].sum(1)
        acc += hf - nf * (Hs.sum(0) - hf) / (len(ix) - nf)
        nf_tot += nf
    return acc / nf_tot


def _hits(d: pd.DataFrame, rungs=RUNGS) -> np.ndarray:
    a = d["e"].abs().to_numpy()
    return np.column_stack([(a >= r).astype(float) for r in rungs])


def stage_tests(g: pd.DataFrame, R: dict, rng, flags=FLAGS, flag_override: dict | None = None, rungs=RUNGS, placebo_draws=10000) -> dict:
    out = {}
    for stage in ("discovery", "confirmation"):
        a, b = R[stage]
        d = g[g["season"].between(a, b) & g["result"].notna()].reset_index(drop=True)
        H = _hits(d, rungs)
        rows, pv = {}, {}
        for f in flags:
            fl = (flag_override[f](d) if flag_override else d[f]).to_numpy().astype(bool)
            st = _strata(d, fl, H)
            diff, ratio, obs = control_stat(st)
            p = boot_p(st, rng, R["bootstrap_draws"])
            pl = placebo(d, fl, H, rng, placebo_draws) if placebo_draws else None
            for j, r in enumerate(rungs):
                key = f"{f}_{r}"
                pv[key] = float(p[j])
                rows[key] = {"flagged_games": int(fl.sum()), "observed_rate": float(obs[j]), "ratio": float(ratio[j]), "diff": float(diff[j]), "p_one_sided": float(p[j])}
                if pl is not None:
                    rows[key]["placebo_percentile"] = float((pl[:, j] < diff[j]).mean())
                    rows[key]["placebo_5_95"] = [float(np.percentile(pl[:, j], 5)), float(np.percentile(pl[:, j], 95))]
        adj = holm(pv)
        for k in rows:
            rows[k]["p_holm"] = adj[k]
        out[stage] = rows
    out["passed"] = [k for k in out["discovery"] if all(out[s][k]["p_holm"] < R["alpha"] and out[s][k]["ratio"] >= R["min_ratio"] and out[s][k].get("placebo_percentile", 0) >= 0.95 for s in ("discovery", "confirmation"))]
    return out


def rate3(g: pd.DataFrame, R: dict) -> dict:
    """Rung 3 is reported, not tested: base rate of 3 or more points from the line, flagged against same-season unflagged."""
    out = {}
    for stage in ("discovery", "confirmation"):
        d = g[g["season"].between(*R[stage]) & g["result"].notna()].reset_index(drop=True)
        H = _hits(d, (3,))
        for f in FLAGS:
            diff, ratio, obs = control_stat(_strata(d, d[f].to_numpy().astype(bool), H))
            out[f"{stage}_{f}"] = {"observed_rate": float(obs[0]), "ratio": float(ratio[0])}
    return out


def positive_controls(g: pd.DataFrame, R: dict, rng) -> dict:
    out = {"natural_total_line_top_fifth": {}, "injected": {}}
    g = g.copy()
    g["hi_total"] = g.groupby("season")["total_line"].transform(lambda s: s >= s.quantile(0.8))
    res = stage_tests(g, R, rng, flags=("hi_total",), placebo_draws=0)
    out["natural_total_line_top_fifth"] = {s: {k: v for k, v in res[s].items()} for s in ("discovery", "confirmation")}
    out["natural_detected"] = bool(any(res[s][k]["p_holm"] < R["alpha"] for s in ("discovery", "confirmation") for k in res[s]) and all(any(v["p_holm"] < R["alpha"] for v in res[s].values()) for s in ("discovery", "confirmation")))
    conf = g[g["season"].between(*R["confirmation"]) & g["result"].notna()].reset_index(drop=True)
    for scale in (1.10, 1.20, 1.30):
        hits = 0
        for i in range(200):
            d = conf.iloc[rng.integers(0, len(conf), len(conf))].reset_index(drop=True)
            fl = d["u_any"].to_numpy().astype(bool)
            d.loc[fl, "e"] = d.loc[fl, "e"] * scale
            H = _hits(d)
            st = _strata(d, fl, H)
            p = boot_p(st, rng, 300)
            _, ratio, _ = control_stat(st)
            adj = holm({str(j): float(p[j]) for j in range(len(RUNGS))})
            hits += int(any(adj[str(j)] < R["alpha"] and ratio[j] >= R["min_ratio"] for j in range(len(RUNGS))))
        out["injected"][str(scale)] = hits / 200
    out["method_has_power_at_1_20"] = out["injected"]["1.2"] >= 0.8
    return out


def dose_response(g: pd.DataFrame, R: dict, rng) -> dict:
    from sklearn.linear_model import LogisticRegression
    out = {}
    for stage in ("discovery", "confirmation"):
        d = g[g["season"].between(*R[stage]) & g["result"].notna() & g["total_line"].notna()].reset_index(drop=True)
        dum = pd.get_dummies(d["season"], drop_first=True).to_numpy().astype(float)
        score = ((d["score"] - d["score"].mean()) / d["score"].std()).to_numpy()
        X = np.column_stack([score, dum])
        targets = {"margin_14": (d["e"].abs() >= 14).to_numpy(), "total_10": (d["tot_e"].abs() >= 10).to_numpy()}
        rows, pv = {}, {}
        for name, y in targets.items():
            fit = lambda ix: LogisticRegression(C=1e4, max_iter=300).fit(X[ix], y[ix]).coef_[0][0]
            full = float(fit(np.arange(len(d))))
            boot = np.array([fit(rng.integers(0, len(d), len(d))) for _ in range(400)])
            pv[name] = float((boot <= 0).mean())
            rows[name] = {"games": int(len(d)), "coef_per_sd_of_score": full, "odds_ratio_per_sd": float(np.exp(full)), "p_one_sided": pv[name], "ci95_coef": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}
        adj = holm(pv)
        for k in rows:
            rows[k]["p_holm"] = adj[k]
        out[stage] = rows
    out["passed"] = [k for k in out["discovery"] if all(out[s][k]["p_holm"] < R["alpha"] and out[s][k]["coef_per_sd_of_score"] > 0 for s in ("discovery", "confirmation"))]
    return out


def sbr_check() -> dict:
    """Re-derive closing spread and total from the six raw sbr HTML pages and match to games.csv by date and final score."""
    g = tails.load_games()
    g = g[g["result"].notna()].copy()
    g["md"] = g["date"].dt.month * 100 + g["date"].dt.day
    key = {(int(r.season), r.md, int(r.away_score), int(r.home_score)): (r.spread_line, r.total_line) for r in g.itertuples()}
    num = lambda v: 0.0 if str(v).strip().lower() in ("pk", "pick") else pd.to_numeric(v, errors="coerce")
    tot = match = spread_ok = total_ok = 0
    ds, dt = [], []
    for yr in range(2016, 2022):
        t = pd.read_html(StringIO((RAW / "market" / f"sbr_{yr}.html").read_text(encoding="utf8", errors="ignore")))[0]
        t = t.iloc[1:].reset_index(drop=True)
        for i in range(0, len(t) - 1, 2):
            v, h = t.iloc[i], t.iloc[i + 1]
            if str(v[2]).strip() != "V" or str(h[2]).strip() != "H":
                continue
            c1, c2 = num(v[10]), num(h[10])
            if np.isnan(c1) or np.isnan(c2):
                continue
            tot += 1
            md = int(v[0])
            season = yr if md > 300 else yr + 1
            k = (season, md, int(v[8]), int(h[8]))
            if k not in key:
                continue
            match += 1
            spread_line = abs(min(c1, c2)) * (1 if c2 <= c1 else -1)
            sl, tl = key[k]
            ds.append(abs(spread_line - sl))
            dt.append(abs(max(c1, c2) - tl))
            spread_ok += int(abs(spread_line - sl) < 0.01)
            total_ok += int(abs(max(c1, c2) - tl) < 0.01)
    return {"html_games_parsed": tot, "matched_to_games_csv_by_date_and_score": match, "closing_spread_equal": spread_ok, "closing_total_equal": total_ok,
            "spread_within_1_point": int((np.array(ds) <= 1.0).sum()), "total_within_1_point": int((np.array(dt) <= 1.0).sum()), "median_abs_spread_diff": float(np.median(ds)), "median_abs_total_diff": float(np.median(dt))}


def starter_agreement(g_before: pd.DataFrame) -> dict:
    st = tails.pbp_starters(g_before)
    parts = g_before["game_id"].str.split("_")
    h = [st.get((gid, p[3])) for gid, p in zip(g_before["game_id"], parts)]
    a = [st.get((gid, p[2])) for gid, p in zip(g_before["game_id"], parts)]
    n = ok = 0
    for x, y, hh, aa in zip(g_before["home_qb_id"], g_before["away_qb_id"], h, a):
        for u, w in ((x, hh), (y, aa)):
            if w is not None:
                n += 1
                ok += int(u == w)
    return {"team_games_compared": n, "same_starter_in_games_csv_and_pbp": ok, "share": ok / n}


def kalshi_history() -> dict:
    """Count settled Kalshi spread and total markets visible through the public read-only endpoints. Not used to fill gaps."""
    from . import kalshi as K
    out = {}
    for series in ("KXNFLSPREAD", "KXNFLTOTAL"):
        n = {}
        for path in ("/markets", "/historical/markets"):
            cnt, cur, events, settled, closes = 0, "", set(), 0, []
            try:
                while True:
                    d = K._get(f"{path}?series_ticker={series}&limit=1000" + (f"&cursor={cur}" if cur else ""))
                    ms = d.get("markets", [])
                    cnt += len(ms)
                    events |= {m.get("event_ticker") for m in ms}
                    settled += sum(1 for m in ms if m.get("result") in ("yes", "no"))
                    closes += [m.get("close_time") for m in ms if m.get("close_time")]
                    cur = d.get("cursor")
                    if not cur or not ms:
                        break
                n[path] = {"markets": cnt, "events": len(events), "settled_yes_or_no": settled, "first_close": min(closes, default=None), "last_close": max(closes, default=None)}
            except Exception as e:  # network or endpoint shape; recorded, not hidden
                n[path] = {"error": str(e)[:120]}
        out[series] = n
    return out


def run_all() -> dict:
    R = rule()
    rng = np.random.default_rng(R["seed"] + 1)
    g0, f0 = tails.build()
    agree = starter_agreement(g0[g0["result"].notna()])
    g, fitted = tails.build(use_pbp_starters=True)
    res = {"starter_agreement": agree, "sbr_rederive": sbr_check(), "kalshi_history": kalshi_history(), "fitted_pbp_starters": fitted}
    res["same_season_control"] = stage_tests(g, R, rng)
    res["rung3_reported_only"] = rate3(g, R)
    res["positive_controls"] = positive_controls(g, R, rng)
    res["dose_response"] = dose_response(g, R, rng)
    old = __import__("json").loads((tails.ROOT / "docs" / "tails_results.json").read_text())["tail_tests"]
    res["original_ratios"] = {s: {k: v["ratio"] for k, v in old[s].items()} for s in ("discovery", "confirmation")}
    return res
