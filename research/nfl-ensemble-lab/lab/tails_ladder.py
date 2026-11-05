"""Tails Amendment 2: Kalshi spread and total ladders, one Student-t per game, width and tail tests. Rule: docs/TAILS_PREREG.md."""
from __future__ import annotations

import json
from math import lgamma, log, pi, sqrt

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import least_squares
from sklearn.isotonic import IsotonicRegression

from . import props_kalshi as pk
from . import tails
from .tails import ROOT, rule
from .tails_tests import holm

SCOPE = ROOT / "data" / "cache" / "tails_ladder_scope.parquet"
HORIZONS = (24, 3, 1)
LIQ = {"L1": {"spread_max": 0.10, "vol24_min": 0.0}, "L2": {"spread_max": 0.05, "vol24_min": 500.0}}
MAX_AGE = pd.Timedelta(hours=3)
TICK = 0.005
SERIES = {"KXNFLSPREAD": "margin", "KXNFLTOTAL": "total"}


def tmad(df: float) -> float:
    """Mean absolute deviation of a standard Student-t with df > 1."""
    return 2 * sqrt(df) * np.exp(lgamma((df + 1) / 2) - lgamma(df / 2)) / (sqrt(pi) * (df - 1))


def tcdf(x, mu, sigma, df):
    return stats.t.cdf((x - mu) / sigma, df)


def fit_ladder(x: np.ndarray, F: np.ndarray, kind: str = "margin") -> dict | None:
    """Monotone, tick-censored location-scale Student-t fit to a ladder of (x, CDF value). None if too thin."""
    o = np.argsort(x)
    x, F = x[o], F[o]
    ux = np.unique(x)
    Fm = np.array([F[x == v].mean() for v in ux])
    x, F = ux, Fm
    viol = int((np.diff(F) < -0.01).sum())
    Fi = IsotonicRegression(increasing=True, y_min=0.0, y_max=1.0).fit_transform(x, F)
    interior = int(((Fi > 0.03) & (Fi < 0.97)).sum())
    if len(x) < 5 or interior < 3:
        return None
    lo, hi = np.maximum(Fi - TICK, 0), np.minimum(Fi + TICK, 1)
    lo = np.where(Fi >= 0.98, 0.975, lo)
    hi = np.where(Fi >= 0.98, 1.0, hi)
    lo = np.where(Fi <= 0.02, 0.0, lo)
    hi = np.where(Fi <= 0.02, 0.025, hi)
    w = 1 / np.maximum(Fi * (1 - Fi), 0.01)

    def resid(th):
        m = tcdf(x, th[0], np.exp(th[1]), np.exp(th[2]))
        d = np.where(m < lo, lo - m, np.where(m > hi, m - hi, 0.0))
        return np.sqrt(w) * d

    mu0 = float(np.interp(0.5, Fi, x)) if Fi.min() <= 0.5 <= Fi.max() else float(x[np.argmin(np.abs(Fi - 0.5))])
    s0 = 12.0 if kind == "margin" else 10.0
    best = None
    for df0 in (4.0, 12.0, 40.0):
        r = least_squares(resid, [mu0, np.log(s0), np.log(df0)], bounds=([x.min() - 20, np.log(2), np.log(2.5)], [x.max() + 20, np.log(40), np.log(60)]), xtol=1e-10, ftol=1e-10)
        if best is None or r.cost < best.cost:
            best = r
    mu, sigma, df = float(best.x[0]), float(np.exp(best.x[1])), float(np.exp(best.x[2]))
    return {"mu": mu, "sigma": sigma, "df": df, "mad": sigma * tmad(df), "rungs": int(len(x)), "interior": interior, "violations": viol, "cost": float(best.cost)}


def recovery(n_per_cell: int = 300, seed: int = 1) -> dict:
    """Simulate ladders from known t shapes on real strike sets, round to whole cents with noise, refit, and report recovery."""
    rng = np.random.default_rng(seed)
    sc = pd.read_parquet(SCOPE)
    sp = sc[sc["series"] == "KXNFLSPREAD"]
    sets = [g["strike"].astype(float).to_numpy() for _, g in sp.groupby("gid") if g["strike"].notna().sum() >= 8]
    out = {}
    for df_true in (4, 8, 30):
        errs, dfs = [], []
        for sigma in (10.0, 12.5, 15.0):
            for _ in range(n_per_cell):
                mu = rng.uniform(-10, 10)
                st = sets[rng.integers(len(sets))]
                x = np.concatenate([st, -st])
                F = tcdf(x, mu, sigma, df_true)
                F = np.clip(np.round(F + rng.normal(0, 0.01, len(F)), 2), 0.01, 0.99)
                fit = fit_ladder(x, F)
                if fit:
                    errs.append(np.log(fit["sigma"] / sigma))
                    dfs.append(fit["df"])
        out[str(df_true)] = {"ladders_fitted": len(errs), "median_log_scale_error": float(np.median(errs)), "median_abs_log_scale_error": float(np.median(np.abs(errs))),
                             "median_df_hat": float(np.median(dfs)), "share_df_below_10": float(np.mean(np.array(dfs) < 10))}
    out["scale_bar_ok"] = bool(all(abs(out[k]["median_log_scale_error"]) <= 0.05 for k in ("4", "8", "30")))
    out["tail_bar_ok"] = bool(out["4"]["share_df_below_10"] >= 0.8 and (1 - out["30"]["share_df_below_10"]) >= 0.8)
    return out


# ---------------------------------------------------------------------------- prices

def quote(c: pd.DataFrame, P: pd.Timestamp) -> dict | None:
    x = c[c["ts"] <= P]
    if x.empty:
        return None
    r = x.iloc[-1]
    if P - r["ts"] > MAX_AGE:
        return None
    return {"bid": r["bid"], "ask": r["ask"], "last": r["last"], "vol24": float(x["volume"].iloc[-24:].sum())}


def price(q: dict, liq: dict) -> float | None:
    """Mid when the book passes the setting; otherwise the last trade; None if neither."""
    ok = pd.notna(q["bid"]) and pd.notna(q["ask"]) and q["bid"] >= 0.02 and q["ask"] <= 0.98 and (q["ask"] - q["bid"]) <= liq["spread_max"] and q["vol24"] >= liq["vol24_min"]
    if ok:
        return float((q["bid"] + q["ask"]) / 2)
    return None


def load_scope() -> tuple[pd.DataFrame, dict]:
    """Settled spread and total rungs joined to nflverse results; audits Kalshi's settled yes/no against the final score."""
    sc = pd.read_parquet(SCOPE)
    sc = sc[sc["status"] == "finalized"].rename(columns={"result": "k_result"}).copy()
    g = tails.load_games().set_index("game_id")[["result", "total", "spread_line", "total_line"]]
    sc = sc.join(g, on="gid")
    audit = {"settled_rungs": int(len(sc)), "rungs_without_nflverse_game": int(sc["result"].isna().sum())}
    sc = sc[sc["result"].notna()].copy()
    home = (sc["team"] == sc["home"]).to_numpy()
    sp = (sc["series"] == "KXNFLSPREAD").to_numpy()
    sc["x"] = np.where(sp, np.where(home, sc["strike"], -sc["strike"]), sc["strike"])
    truth = np.where(sp, np.where(home, sc["result"] > sc["strike"], sc["result"] < -sc["strike"]), sc["total"] > sc["strike"])
    sc["wrong"] = truth != (sc["k_result"] == "yes").to_numpy()
    bad_games = set(sc.loc[sc["wrong"], "gid"])
    audit["rungs_where_kalshi_settlement_disagrees_with_nflverse"] = int(sc["wrong"].sum())
    audit["games_dropped_for_settlement_mismatch"] = len(bad_games)
    return sc[~sc["gid"].isin(bad_games)].copy(), audit


def ladders(sc: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fit one t per (game, series, horizon, liquidity setting). Uses cached candles only; reports what was dropped and why."""
    rows, drops = [], {"no_candle_price": 0, "too_thin": 0}
    for (gid, series), d in sc.groupby(["gid", "series"]):
        kick = d["kickoff"].iloc[0]
        cs = {m["ticker"]: pk.candles(pd.Series(m)) for m in d.to_dict("records")}
        for h in HORIZONS:
            P = kick - pd.Timedelta(hours=h)
            qs = {t: quote(c, P) for t, c in cs.items()}
            for lname, liq in LIQ.items():
                xs, Fs = [], []
                for m in d.itertuples(index=False):
                    q = qs[m.ticker]
                    p = price(q, liq) if q else None
                    if p is None:
                        continue
                    kind_home = m.team == m.home
                    if series == "KXNFLSPREAD":
                        xs.append(m.x)
                        Fs.append(1 - p if kind_home else p)
                    else:
                        xs.append(m.x)
                        Fs.append(1 - p)
                if len(xs) < 5:
                    drops["no_candle_price"] += 1
                    continue
                f = fit_ladder(np.array(xs, float), np.array(Fs, float), SERIES[series])
                if f is None:
                    drops["too_thin"] += 1
                    continue
                r0 = d.iloc[0]
                y = r0["result"] if series == "KXNFLSPREAD" else r0["total"]
                line = r0["spread_line"] if series == "KXNFLSPREAD" else r0["total_line"]
                rows.append({"gid": gid, "season": int(r0["season"]), "week": int(r0["week"]), "series": series, "horizon": h, "liq": lname, "y": float(y), "line": float(line), **f})
    return pd.DataFrame(rows), drops


def _stats(d: pd.DataFrame) -> dict:
    pit = tcdf(d["y"].to_numpy(), d["mu"].to_numpy(), d["sigma"].to_numpy(), d["df"].to_numpy())
    m = np.abs(d["y"] - d["mu"]).to_numpy()
    return {"width_level": float(m.mean() / d["mad"].mean()), "tail10": float(((pit < 0.05) | (pit > 0.95)).mean()), "tail2": float(((pit < 0.01) | (pit > 0.99)).mean()),
            "center_diff": float((m - np.abs(d["y"] - d["line"]).to_numpy()).mean())}, pit


def _boot(d: pd.DataFrame, rng, B: int) -> dict:
    n = len(d)
    out = {k: np.empty(B) for k in ("width_level", "tail10", "tail2", "center_diff")}
    arrs = {c: d[c].to_numpy() for c in ("y", "mu", "sigma", "df", "mad", "line")}
    for b in range(B):
        i = rng.integers(0, n, n)
        e = {c: v[i] for c, v in arrs.items()}
        pit = tcdf(e["y"], e["mu"], e["sigma"], e["df"])
        m = np.abs(e["y"] - e["mu"])
        out["width_level"][b] = m.mean() / e["mad"].mean()
        out["tail10"][b] = ((pit < 0.05) | (pit > 0.95)).mean()
        out["tail2"][b] = ((pit < 0.01) | (pit > 0.99)).mean()
        out["center_diff"][b] = (m - np.abs(e["y"] - e["line"])).mean()
    return out


def _perm_null(d: pd.DataFrame, rng, P: int) -> dict:
    """Shuffle realized results across games within the week; fits unchanged."""
    out = {k: np.empty(P) for k in ("width_level", "tail10", "tail2")}
    idx = d.groupby("week").indices
    y = d["y"].to_numpy()
    base = {c: d[c].to_numpy() for c in ("mu", "sigma", "df", "mad")}
    for b in range(P):
        yp = y.copy()
        for ix in idx.values():
            yp[ix] = y[rng.permutation(ix)]
        pit = tcdf(yp, base["mu"], base["sigma"], base["df"])
        out["width_level"][b] = np.abs(yp - base["mu"]).mean() / base["mad"].mean()
        out["tail10"][b] = ((pit < 0.05) | (pit > 0.95)).mean()
        out["tail2"][b] = ((pit < 0.01) | (pit > 0.99)).mean()
    return out


def tests(tab: pd.DataFrame, R: dict, rng, B: int = 1000, P: int = 1000) -> dict:
    """Per stage (2025 decides, 2026 confirms) and setting: center, width level, tail shares, KS, permutation percentile, power."""
    out = {}
    for stage, season in (("decide_2025", 2025), ("confirm_2026", 2026)):
        rows, pw, pt10, pt2 = {}, {}, {}, {}
        for (series, h, liq), d in tab[tab["season"] == season].groupby(["series", "horizon", "liq"]):
            key = f"{series}_{h}h_{liq}"
            if len(d) < 20:
                rows[key] = {"games": int(len(d)), "note": "too few games"}
                continue
            st, pit = _stats(d)
            bt = _boot(d, rng, B)
            nul = _perm_null(d, rng, P)
            ks = stats.kstest(pit, "uniform")
            r = {"games": int(len(d)), **st, "ks_p": float(ks.pvalue), "center_ci95": [float(np.percentile(bt["center_diff"], 2.5)), float(np.percentile(bt["center_diff"], 97.5))],
                 "width_ci95": [float(np.percentile(bt["width_level"], 2.5)), float(np.percentile(bt["width_level"], 97.5))],
                 "p_width_two_sided": float(2 * min((bt["width_level"] >= 1).mean(), (bt["width_level"] <= 1).mean())),
                 "p_tail10_excess": float((bt["tail10"] <= 0.10).mean()), "p_tail2_excess": float((bt["tail2"] <= 0.02).mean()),
                 "perm_percentile": {k: float((nul[k] < st[k]).mean()) for k in nul},
                 "power": {"min_detectable_width_error": float(2.8 * bt["width_level"].std()), "min_detectable_tail10_excess": float(2.8 * bt["tail10"].std())},
                 "median_df": float(d["df"].median()), "median_sigma": float(d["sigma"].median()), "median_abs_gap_to_line": float((d["mu"] - d["line"]).abs().median()),
                 "p90_abs_gap_to_line": float((d["mu"] - d["line"]).abs().quantile(0.9))}
            rows[key] = r
            pw[key], pt10[key], pt2[key] = r["p_width_two_sided"], r["p_tail10_excess"], r["p_tail2_excess"]
        for name, pv in (("holm_width", pw), ("holm_tail10", pt10), ("holm_tail2", pt2)):
            adj = holm(pv)
            for k, v in adj.items():
                rows[k][name] = v
        out[stage] = rows
    keys = [k for k in out["decide_2025"] if "holm_width" in out["decide_2025"][k] and k in out["confirm_2026"] and "holm_width" in out["confirm_2026"][k]]
    passed = []
    for k in keys:
        a, b = out["decide_2025"][k], out["confirm_2026"][k]
        if a["holm_width"] < R["alpha"] and b["holm_width"] < R["alpha"] and (a["width_level"] - 1) * (b["width_level"] - 1) > 0 and min(a["perm_percentile"]["width_level"], 1 - a["perm_percentile"]["width_level"]) <= 0.05 and min(b["perm_percentile"]["width_level"], 1 - b["perm_percentile"]["width_level"]) <= 0.05:
            passed.append(k + ":width")
        for t in ("tail10", "tail2"):
            if a["holm_" + t] < R["alpha"] and b["holm_" + t] < R["alpha"] and a["perm_percentile"][t] >= 0.95 and b["perm_percentile"][t] >= 0.95:
                passed.append(f"{k}:{t}")
    out["passed"] = passed
    out["plausible_sizes_detectable_in_confirmation"] = {k: bool(out["confirm_2026"][k].get("power", {}).get("min_detectable_width_error", 9) <= 0.15 and out["confirm_2026"][k].get("power", {}).get("min_detectable_tail10_excess", 9) <= 0.05) for k in keys}
    return out


def counts() -> dict:
    sc = pd.read_parquet(SCOPE)
    sc = sc.assign(settled=sc["status"] == "finalized")
    cd = ROOT / "data" / "cache" / "props_kalshi" / "candles"
    td = ROOT / "data" / "cache" / "props_kalshi" / "trades"
    have_c = {p.stem for p in cd.glob("KXNFLSPREAD*.json")} | {p.stem for p in cd.glob("KXNFLTOTAL*.json")}
    have_t = {p.stem for p in td.glob("KXNFLSPREAD*.json")} | {p.stem for p in td.glob("KXNFLTOTAL*.json")}
    sc["has_candles"] = sc["ticker"].isin(have_c)
    sc["has_tape"] = sc["ticker"].isin(have_t)
    out = {}
    for (s, yr), d in sc.groupby(["series", "season"]):
        out[f"{s}_{yr}"] = {"games": int(d["gid"].nunique()), "events": int(d["event"].nunique()), "rungs": int(len(d)), "settled_rungs": int(d["settled"].sum()), "rungs_with_candles": int(d["has_candles"].sum()),
                            "rungs_with_trade_tape": int(d["has_tape"].sum()), "first_kickoff": str(d["kickoff"].min()), "last_kickoff": str(d["kickoff"].max())}
    snaps = sorted((ROOT / "data" / "raw" / "archive" / "dense_books").glob("*.json"))
    out["order_book_snapshots"] = {"dense_books_files": len(snaps), "props_kalshi_books_files": len(list((ROOT / "data" / "raw" / "archive" / "props_kalshi_books").glob("*.json"))), "first": snaps[0].name[:13] if snaps else None, "last": snaps[-1].name[:13] if snaps else None, "note": "game-winner and prop books; spread and total ladder books are archived from the weekly save forward"}
    return out


def tape_check() -> dict:
    """Last trade at or before kickoff minus 1h against that rung's candle mid, on the center rungs whose tape was pulled."""
    sc = pd.read_parquet(SCOPE)
    td = ROOT / "data" / "cache" / "props_kalshi" / "trades"
    diffs, n_trades, n_markets = [], 0, 0
    for m in sc.to_dict("records"):
        f = td / f"{m['ticker']}.json"
        if not f.exists():
            continue
        tr = json.loads(f.read_text())
        n_markets += 1
        n_trades += len(tr)
        if not tr:
            continue
        P = m["kickoff"] - pd.Timedelta(hours=1)
        pts = []
        for t in tr:
            ts = pd.Timestamp(t.get("created_time") or t.get("ts"), tz="UTC") if (t.get("created_time") or t.get("ts")) else None
            px = t.get("yes_price_dollars")
            if px is None and t.get("yes_price") is not None:
                px = float(t["yes_price"]) / 100
            if ts is not None and px is not None and ts <= P:
                pts.append((ts, float(px)))
        q = quote(pk.candles(pd.Series(m)), P)
        if pts and q and pd.notna(q["bid"]) and pd.notna(q["ask"]):
            diffs.append(max(pts)[1] - (q["bid"] + q["ask"]) / 2)
    return {"markets_with_tape": n_markets, "trade_prints": n_trades, "compared": len(diffs), "median_abs_diff": float(np.median(np.abs(diffs))) if diffs else None, "p90_abs_diff": float(np.percentile(np.abs(diffs), 90)) if diffs else None}


def run_all() -> dict:
    R = rule()
    rng = np.random.default_rng(R["seed"] + 2)
    rec = recovery()
    sc, audit = load_scope()
    tab, drops = ladders(sc)
    res = {"counts": counts(), "recovery": rec, "audit": audit, "dropped_game_horizons": drops, "fitted_ladders": int(len(tab)),
           "ladder_fits_by_setting": {f"{s}_{h}h_{l}": int(len(d)) for (s, h, l), d in tab.groupby(["series", "horizon", "liq"])},
           "violations_share_of_ladders": float((tab["violations"] > 0).mean()), "tape_check": tape_check()}
    if rec["scale_bar_ok"]:
        res["tests"] = tests(tab, R, rng)
        res["tail_test_informative"] = rec["tail_bar_ok"]
    else:
        res["tests"] = None
        res["note"] = "Recovery check failed on scale; nothing downstream is reported as a result."
    tab.to_parquet(ROOT / "data" / "cache" / "tails_ladder_fits.parquet")
    return res


# ---------------------------------------------------------------------------- forward-only record

ARCHIVE = tails.OUT / "ladders"


def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


def archive_ladders(week: int | None = None) -> dict:
    """Write-once: current bid, ask, last, volume and observation time of every open spread and total rung for games not yet started."""
    import hashlib
    from datetime import datetime, timezone
    from . import homewin_deep as h
    if week and (ARCHIVE / f"2026_w{int(week):02d}.json").exists():
        return json.loads((ARCHIVE / f"2026_w{int(week):02d}.json").read_text())
    games, _ = h.load_games()
    live = pk.live_markets(games, series=list(SERIES))
    live = live.join(games.set_index("gid")[["season", "week", "home", "away"]], on="gid")
    now = pd.Timestamp.now(tz="UTC")
    live = live[live["kickoff"] > now]
    week = int(week or live["week"].min())
    live = live[live["week"] == week]
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    path = ARCHIVE / f"2026_w{week:02d}.json"
    if path.exists():
        return json.loads(path.read_text())
    cols = ["gid", "series", "ticker", "team", "strike", "bid", "ask", "last", "vol24", "kickoff", "home", "away", "week"]
    body = {"observed_at": now.isoformat(), "week": week, "rungs": json.loads(live[cols].to_json(orient="records", date_format="iso"))}
    body["sha256"] = hashlib.sha256(_canon(body).encode()).hexdigest()
    path.write_text(json.dumps(body, indent=1))
    with (tails.OUT / "ledger.jsonl").open("a") as f:
        f.write(json.dumps({"file": "ladders/" + path.name, "sha256": body["sha256"], "created": body["observed_at"]}) + "\n")
    return body


def score_archived() -> dict:
    """Fit each archived ladder at its saved prices (after the games) and report width level and tail shares, forward-only."""
    import hashlib
    g = tails.load_games().set_index("game_id")
    rows = []
    files = sorted(ARCHIVE.glob("*.json")) if ARCHIVE.exists() else []
    for f in files:
        b = json.loads(f.read_text())
        ok = hashlib.sha256(_canon({k: v for k, v in b.items() if k != "sha256"}).encode()).hexdigest() == b["sha256"]
        if not ok:
            continue
        d = pd.DataFrame(b["rungs"])
        obs = pd.Timestamp(b["observed_at"])
        for (gid, series), r in d.groupby(["gid", "series"]):
            if gid not in g.index or pd.isna(g.loc[gid, "result"]) or pd.Timestamp(r["kickoff"].iloc[0]) <= obs:
                continue
            xs, Fs = [], []
            for m in r.itertuples(index=False):
                if pd.notna(m.bid) and pd.notna(m.ask) and m.bid >= 0.02 and m.ask <= 0.98 and (m.ask - m.bid) <= LIQ["L1"]["spread_max"]:
                    p = (m.bid + m.ask) / 2
                    if series == "KXNFLSPREAD":
                        xs.append(m.strike if m.team == m.home else -m.strike)
                        Fs.append(1 - p if m.team == m.home else p)
                    else:
                        xs.append(m.strike)
                        Fs.append(1 - p)
            fit = fit_ladder(np.array(xs, float), np.array(Fs, float), SERIES[series]) if len(xs) >= 5 else None
            if fit:
                y = g.loc[gid, "result"] if series == "KXNFLSPREAD" else g.loc[gid, "total"]
                rows.append({"gid": gid, "series": series, "y": float(y), **fit})
    if not rows:
        return {"files": len(files), "games_scored": 0}
    t = pd.DataFrame(rows)
    pit = tcdf(t["y"].to_numpy(), t["mu"].to_numpy(), t["sigma"].to_numpy(), t["df"].to_numpy())
    return {"files": len(files), "games_scored": int(len(t)), "width_level": float(np.abs(t["y"] - t["mu"]).mean() / t["mad"].mean()), "tail10": float(((pit < 0.05) | (pit > 0.95)).mean())}
