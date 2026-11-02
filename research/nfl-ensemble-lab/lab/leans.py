"""Leans: model probability against archived Kalshi prop prices, scored by edge. No staking, no sizing.

The rule is fixed in docs/leans_rule.json (original) and docs/leans_rule_v2.json (Amendment 1 in docs/LEANS_PREREG.md).
Prices come from the stored Kalshi quotes: mid prices, or executable prices (ask for an over, 1 minus bid for an under, plus a fee).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RULE_PATH = ROOT / "docs" / "leans_rule.json"
RULE2_PATH = ROOT / "docs" / "leans_rule_v2.json"
THRESH = ROOT / "data" / "cache" / "props_kalshi" / "scored_thresholds.parquet"
QUOTES = ROOT / "data" / "cache" / "props_kalshi" / "quotes.parquet"
FROZEN = ROOT / "data" / "leans" / "frozen"
LEDGER = ROOT / "data" / "leans" / "ledger.jsonl"
STAT_NAME = {"pass_yds": "Passing yards", "rec": "Receptions", "rec_yds": "Receiving yards", "rush_yds": "Rushing yards"}
NOT_TESTABLE = {"Game total": "the game numbers come from the market, so the model has no independent probability",
                "Spread": "the game numbers come from the market, so the model has no independent probability",
                "Moneyline": "the game numbers come from the market, so the model has no independent probability",
                "Touchdowns": "no archived model probability with outcomes in a usable form"}
FEE_RATE = 0.07


def rule() -> dict:
    return json.loads(RULE_PATH.read_text())


def rule_sha() -> str:
    return hashlib.sha256(RULE2_PATH.read_bytes()).hexdigest()


def load() -> pd.DataFrame:
    R = rule()
    d = pd.read_parquet(THRESH)
    d = d[(d["point_utc"] < d["kickoff_utc"]) & d["stat"].isin(R["stats"])].dropna(subset=[R["model_col"], R["market_col"], R["close_col"]]).copy()
    q = pd.read_parquet(QUOTES, columns=["gid", "pid", "stat", "threshold", "bid90", "ask90", "vol2490", "liquid90", "bidC", "askC"]).drop_duplicates(["gid", "pid", "stat", "threshold"])
    d = d.merge(q, left_on=["gid", "pid", "stat", "k"], right_on=["gid", "pid", "stat", "threshold"], how="left").drop(columns="threshold")
    d["y"] = d["y_home_win"].astype(int)
    d["key"] = d["season"] * 100 + d["week"]
    d["executable"] = d["liquid90"].fillna(False).astype(bool) & d[["bid90", "ask90", "bidC", "askC"]].notna().all(axis=1) & (d["ask90"] > d["bid90"])
    return d.sort_values(["key", "gid"]).reset_index(drop=True)


def _logit(p):
    p = np.clip(p, 0.01, 0.99)
    return np.log(p / (1 - p))


def recalibrate(d: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward recalibration per stat, trained only on earlier weeks: logistic (p_L) and isotonic (p_I)."""
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    R = rule()
    mc = R["model_col"]
    first = R["recal"]["first_test_season"] * 100 + R["recal"]["first_test_week"]
    d = d.copy()
    d["p_L"], d["p_I"] = d[mc], d[mc]
    for key in sorted(k for k in d["key"].unique() if k >= first):
        for stat in R["stats"]:
            tr = d[(d["key"] < key) & (d["stat"] == stat)]
            te = (d["key"] == key) & (d["stat"] == stat)
            if te.any() and len(tr) >= 200 and tr["y"].nunique() == 2:
                x = d.loc[te, mc].to_numpy()
                d.loc[te, "p_L"] = LogisticRegression(C=1e6, max_iter=500).fit(_logit(tr[mc].to_numpy())[:, None], tr["y"]).predict_proba(_logit(x)[:, None])[:, 1]
                d.loc[te, "p_I"] = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99).fit(tr[mc].to_numpy(), tr["y"]).predict(x)
    d["tested"] = d["key"] >= first
    return d


def _ll(p, y):
    p = np.clip(p, 0.01, 0.99)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _boot(v: np.ndarray, gid: np.ndarray, draws: int, seed: int) -> np.ndarray:
    s = pd.DataFrame({"v": v, "gid": gid}).groupby("gid")["v"].agg(["sum", "count"])
    idx = np.random.default_rng(seed).integers(0, len(s), size=(draws, len(s)))
    return s["sum"].to_numpy()[idx].sum(1) / s["count"].to_numpy()[idx].sum(1)


def recal_compare(d: pd.DataFrame) -> dict:
    R = rule()
    t = d[d["tested"]]
    y = t["y"].to_numpy()
    ll = {"raw": _ll(t[R["model_col"]].to_numpy(), y), "logistic": _ll(t["p_L"].to_numpy(), y), "isotonic": _ll(t["p_I"].to_numpy(), y), "market": _ll(t[R["market_col"]].to_numpy(), y)}
    chosen = "isotonic" if ll["isotonic"].mean() < ll["logistic"].mean() else "logistic"
    out = {"rows": int(len(t)), "log_loss": {k: float(v.mean()) for k, v in ll.items()}, "chosen": chosen, "adopted_by": "owner choice, not by the original test"}
    for name in ("logistic", "isotonic"):
        b = _boot(ll["raw"] - ll[name], t["gid"].to_numpy(), R["bootstrap"]["draws"], R["bootstrap"]["seed"])
        out[f"gain_{name}"] = {"gain": float((ll["raw"] - ll[name]).mean()), "ci": [float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))]}
    return out


def make_leans(d: pd.DataFrame, q, mode: str = "exec") -> pd.DataFrame:
    """One lean per (game, player, stat): the strike with the largest edge at or over the threshold. mode is 'mid' or 'exec'."""
    R = rule()
    cuts = R["size_cuts"]
    x = d.copy()
    x["q"] = x[q] if isinstance(q, str) else np.asarray(q)
    x["m"], x["c"] = x[R["market_col"]], x[R["close_col"]]
    x["edge"] = x["q"] - x["m"]
    x = x[x["edge"].abs() >= R["edge_threshold"]].copy()
    if mode == "exec":
        x = x[x["executable"]].copy()
    x = x.assign(a=x["edge"].abs()).sort_values("a", ascending=False).drop_duplicates(["gid", "pid", "stat"]).sort_values(["key", "gid"])
    x["side"] = np.where(x["edge"] > 0, "over", "under")
    x["win"] = np.where(x["side"] == "over", x["y"], 1 - x["y"]).astype(float)
    if mode == "exec":
        x["price"] = np.where(x["side"] == "over", x["ask90"], 1 - x["bid90"])
        x["fee"] = FEE_RATE * x["price"] * (1 - x["price"])
        x["real_pre"] = x["win"] - x["price"]
        x["real"] = x["real_pre"] - x["fee"]
        x["clv"] = np.where(x["side"] == "over", x["bidC"] - x["ask90"], x["bid90"] - x["askC"])
    else:
        x["price"] = np.where(x["side"] == "over", x["m"], 1 - x["m"])
        x["fee"] = 0.0
        x["real_pre"] = x["real"] = x["win"] - x["price"]
        x["clv"] = np.where(x["side"] == "over", x["c"] - x["m"], x["m"] - x["c"])
    x["size"] = np.where(x["a"] >= cuts[2], "large", np.where(x["a"] >= cuts[1], "medium", "small"))
    x["market"] = x["stat"].map(STAT_NAME)
    return x


def dropped_share(d: pd.DataFrame, q) -> dict:
    R = rule()
    e = np.abs((d[q].to_numpy() if isinstance(q, str) else np.asarray(q)) - d[R["market_col"]].to_numpy())
    over = e >= R["edge_threshold"]
    ok = over & d["executable"].to_numpy()
    return {"rows_over_threshold": int(over.sum()), "executable": int(ok.sum()), "dropped_thin": float(1 - ok.sum() / max(over.sum(), 1))}


def _icc(v: np.ndarray, gid: np.ndarray) -> float:
    df = pd.DataFrame({"v": v, "g": gid})
    n, G = len(df), df["g"].nunique()
    if G < 2 or n <= G:
        return 0.0
    grp = df.groupby("g")["v"]
    ng, mg = grp.size().to_numpy(), grp.mean().to_numpy()
    msb = (ng * (mg - df["v"].mean()) ** 2).sum() / (G - 1)
    msw = ((df["v"] - grp.transform("mean")) ** 2).sum() / (n - G)
    m0 = (n - (ng ** 2).sum() / n) / (G - 1)
    den = msb + (m0 - 1) * msw
    return float(max(0.0, (msb - msw) / den)) if den > 0 else 0.0


def summarize(x: pd.DataFrame, boot: bool = True) -> dict:
    R = rule()
    n = int(len(x))
    if n == 0:
        return {"n": 0, "note": "No leans in this selection."}
    games = int(x["gid"].nunique())
    sd = float(x["real"].std(ddof=1)) if n > 1 else 0.5
    base = float(((1.96 + 0.8416) * sd / R["power"]["target_edge"]) ** 2)
    icc = _icc(x["real"].to_numpy(), x["gid"].to_numpy())
    de = 1 + (n / games - 1) * icc
    need = int(np.ceil(base * de))
    out = {"n": n, "games": games, "effective_n": float(n / de), "design_effect": float(de), "icc": icc, "win_rate": float(x["win"].mean()), "stated_edge": float(x["edge"].abs().mean()),
           "realized_edge": float(x["real"].mean()), "realized_before_fees": float(x["real_pre"].mean()), "fee": float(x["fee"].mean()), "clv": float(x["clv"].mean()), "need_for_2pt": need, "need_base": int(np.ceil(base))}
    if boot and games > 2:
        b = _boot(x["real"].to_numpy(), x["gid"].to_numpy(), R["bootstrap"]["draws"], R["bootstrap"]["seed"])
        out["realized_ci"] = [float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))]
        out["p_one_sided"] = float((b <= 0).mean())
    out["note"] = (f"Too few leans to mean anything: about {need} are needed to detect a 2 point realized edge once leans from the same game are treated as one source of noise, and this selection has {n} ({out['effective_n']:.0f} effective)."
                   if n < need else "Enough leans to detect a 2 point realized edge.")
    return out


def benchmarks(d: pd.DataFrame, x: pd.DataFrame, mode: str) -> dict:
    """Follow the market and a random side on the same ladders, at the same prices and fees."""
    R = rule()
    r = d.loc[d.index.intersection(x.index)]
    if not len(r):
        return {"follow_market_realized": None, "random_side_realized": None}
    y, m = r["y"].to_numpy(), r[R["market_col"]].to_numpy()

    def real(over):
        if mode == "exec":
            p = np.where(over, r["ask90"], 1 - r["bid90"])
            return np.where(over, y, 1 - y) - p - FEE_RATE * p * (1 - p)
        return np.where(over, y - m, (1 - y) - (1 - m))
    rng = np.random.default_rng(R["random_side"]["seed"])
    return {"follow_market_realized": float(real(m >= 0.5).mean()), "random_side_realized": float(np.mean([real(rng.random(len(m)) < 0.5).mean() for _ in range(R["random_side"]["draws"])]))}


def placebo(d: pd.DataFrame, qcol: str) -> dict:
    R2 = json.loads(RULE2_PATH.read_text())["placebo"]
    R = rule()
    s = d.assign(code=d.groupby(["gid", "stat"]).ngroup()).sort_values("code").reset_index(drop=True)
    rng = np.random.default_rng(R2["seed"])
    diff = (s[qcol] - s[R["market_col"]]).to_numpy()
    code = s["code"].to_numpy()
    vals = []
    for _ in range(R2["draws"]):
        order = np.lexsort((rng.random(len(s)), code))
        q = np.clip(s[R["market_col"]].to_numpy() + diff[order], 0.01, 0.99)
        x = make_leans(s, q, "exec")
        vals.append(float(x["real"].mean()) if len(x) else np.nan)
    v = np.array(vals)
    return {"draws": int(len(v)), "mean_edge": float(np.nanmean(v)), "range": [float(np.nanquantile(v, 0.025)), float(np.nanquantile(v, 0.975))], "abs_mean_le_1pt": bool(abs(np.nanmean(v)) <= 0.01)}


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def backtest():
    d = recalibrate(load())
    rc = recal_compare(d)
    chosen = "p_L" if rc["chosen"] == "logistic" else "p_I"
    models = {"raw": rule()["model_col"], "recal": chosen}
    res = {"rule_sha256": rule_sha(), "recal_compare": rc, "universe_rows": int(len(d)), "universe_games": int(d["gid"].nunique()), "executable_rows": int(d["executable"].sum()), "models": {}}
    frames = []
    for mname, col in models.items():
        res["models"][mname] = {}
        for mode in ("exec", "mid"):
            x = make_leans(d, col, mode)
            res["models"][mname][mode] = {"summary": summarize(x), "benchmarks": benchmarks(d, x, mode), "dropped": dropped_share(d, col)}
            frames.append(x.assign(model=mname, mode=mode))
    hx = make_leans(d, models["recal"], "exec")
    h = res["models"]["recal"]["exec"]["summary"]
    res["placebo"] = placebo(d, models["recal"])
    fam = {}
    for fname in ("market", "size", "season"):
        for g, gx in hx.groupby(fname):
            fam[f"{fname}:{g}"] = gx
    subs = {k: summarize(g) for k, g in fam.items()}
    hp = holm({k: v["p_one_sided"] for k, v in subs.items() if "p_one_sided" in v})
    for k, v in subs.items():
        v["p_holm"] = hp.get(k)
        v["claim"] = bool(hp.get(k, 1) < 0.05)
    res["subgroups"] = subs
    res["pass"] = {"realized_after_costs_ci_lower_gt_0": bool(h.get("realized_ci", [-1])[0] > 0), "clv_exec_gt_0": bool(h["clv"] > 0), "leans_at_least_need_corrected": bool(h["n"] >= h["need_for_2pt"]),
                   "placebo_abs_mean_le_1pt": res["placebo"]["abs_mean_le_1pt"]}
    res["pass"]["edge_found"] = all(res["pass"].values())
    cal = {}
    for name, col in (("raw", rule()["model_col"]), ("logistic", "p_L"), ("isotonic", "p_I"), ("market", rule()["market_col"])):
        b = pd.cut(d[col], [0, .1, .25, .4, .6, .75, .9, 1.0], include_lowest=True)
        g = d.groupby(b, observed=True).agg(n=("y", "size"), stated=(col, "mean"), realized=("y", "mean"))
        cal[name] = [{"bucket": str(k), "n": int(r.n), "stated": float(r.stated), "realized": float(r.realized)} for k, r in g.iterrows()]
    res["calibration"] = cal
    return res, pd.concat(frames)


def rows_for_screen(x: pd.DataFrame) -> pd.DataFrame:
    return x[["model", "mode", "gid", "season", "week", "market", "pid", "k", "side", "q", "m", "c", "price", "fee", "edge", "size", "y", "win", "real_pre", "real", "clv"]]


def select(x: pd.DataFrame, market: str | None, week_from: int | None, week_to: int | None, size: str | None, season: int | None = None) -> pd.DataFrame:
    s = x
    if season:
        s = s[s["season"] == season]
    if market and market != "All":
        s = s[s["market"] == market]
    if week_from:
        s = s[s["week"] >= week_from]
    if week_to:
        s = s[s["week"] <= week_to]
    if size and size != "All":
        s = s[s["size"] == size]
    return s


def live_leans(week: int, now: dt.datetime | None = None) -> dict:
    """Leans for games that have not kicked off, from the app's own prop numbers. Written once per week to a hashed file."""
    from . import gamecenter_data as G
    R = rule()
    now = now or dt.datetime.now(dt.timezone.utc)
    games = G.games_table()
    g = games[(games["season"] == G.SEASON) & (games["week"] == week) & (games["game_type"] == "REG")]
    out, none = [], 0
    for r in g.itertuples():
        ko = pd.Timestamp(r.kickoff_utc)
        ko = ko.tz_localize("UTC") if ko.tzinfo is None else ko
        if ko <= now:
            continue
        d = G.game_detail(r.game_id)
        for p in (d or {}).get("props") or []:
            if p.get("market_chance") is None or p.get("our_chance") is None or p.get("market_line") is None:
                continue
            e = float(p["our_chance"]) - float(p["market_chance"])
            if abs(e) < R["edge_threshold"]:
                none += 1
                continue
            out.append({"gid": r.game_id, "kickoff_utc": ko.isoformat(), "market": p["stat"], "player": p["player"], "team": p["team"], "side": "over" if e > 0 else "under",
                        "line": p["market_line"], "source": "Kalshi", "model_p": float(p["our_chance"]), "market_p": float(p["market_chance"]), "edge": e})
    return {"week": week, "created": now.isoformat(), "rule_sha256": rule_sha(), "leans": out, "no_lean": none}


def freeze_week(week: int) -> dict:
    """Write-once: a second call returns the saved file and never rebuilds it."""
    path = FROZEN / f"{week}.json"
    if path.exists():
        rec = json.loads(path.read_text())
        body = json.dumps(rec["forecast"], sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(body.encode()).hexdigest() != rec["sha256"]:
            raise RuntimeError(f"saved leans for week {week} do not match their hash")
        return rec
    f = live_leans(week)
    body = json.dumps(f, sort_keys=True, separators=(",", ":"))
    rec = {"sha256": hashlib.sha256(body.encode()).hexdigest(), "forecast": f}
    FROZEN.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec))
    with LEDGER.open("a") as fh:
        fh.write(json.dumps({"week": week, "sha256": rec["sha256"], "created": f["created"], "leans": len(f["leans"])}) + "\n")
    return rec
