"""Leans: model probability against archived Kalshi prop prices, scored by edge. No staking, no sizing.

The rule (threshold, size cuts, bootstrap, pass rule) is fixed in docs/leans_rule.json and docs/LEANS_PREREG.md.
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
THRESH = ROOT / "data" / "cache" / "props_kalshi" / "scored_thresholds.parquet"
FROZEN = ROOT / "data" / "leans" / "frozen"
LEDGER = ROOT / "data" / "leans" / "ledger.jsonl"
STAT_NAME = {"pass_yds": "Passing yards", "rec": "Receptions", "rec_yds": "Receiving yards", "rush_yds": "Rushing yards"}
NOT_TESTABLE = {"Game total": "the game numbers come from the market, so the model has no independent probability",
                "Spread": "the game numbers come from the market, so the model has no independent probability",
                "Moneyline": "the game numbers come from the market, so the model has no independent probability",
                "Touchdowns": "no archived model probability with outcomes in a usable form"}


def rule() -> dict:
    return json.loads(RULE_PATH.read_text())


def rule_sha() -> str:
    return hashlib.sha256(RULE_PATH.read_bytes()).hexdigest()


def load() -> pd.DataFrame:
    R = rule()
    d = pd.read_parquet(THRESH)
    d = d[(d["point_utc"] < d["kickoff_utc"]) & d["stat"].isin(R["stats"])].dropna(subset=[R["model_col"], R["market_col"], R["close_col"]]).copy()
    d["y"] = d["y_home_win"].astype(int)
    d["key"] = d["season"] * 100 + d["week"]
    return d.sort_values(["key", "gid"]).reset_index(drop=True)


def _logit(p):
    p = np.clip(p, 0.01, 0.99)
    return np.log(p / (1 - p))


def recalibrate(d: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward logistic recalibration of the model probability per stat, trained only on earlier weeks."""
    from sklearn.linear_model import LogisticRegression
    R = rule()
    first = R["recal"]["first_test_season"] * 100 + R["recal"]["first_test_week"]
    d = d.copy()
    d["p_R"] = d[R["model_col"]]
    for key in sorted(k for k in d["key"].unique() if k >= first):
        for stat in R["stats"]:
            tr = d[(d["key"] < key) & (d["stat"] == stat)]
            te = (d["key"] == key) & (d["stat"] == stat)
            if te.any() and len(tr) >= 200 and tr["y"].nunique() == 2:
                m = LogisticRegression(C=1e6, max_iter=500).fit(_logit(tr[R["model_col"]].to_numpy())[:, None], tr["y"])
                d.loc[te, "p_R"] = m.predict_proba(_logit(d.loc[te, R["model_col"]].to_numpy())[:, None])[:, 1]
    d["tested"] = d["key"] >= first
    return d


def _ll(p, y):
    p = np.clip(p, 0.01, 0.99)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _boot_by_game(g: pd.Series, gid: pd.Series, draws: int, seed: int) -> tuple[float, float]:
    s = pd.DataFrame({"v": g.to_numpy(), "gid": gid.to_numpy()}).groupby("gid")["v"].agg(["sum", "count"])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(s), size=(draws, len(s)))
    tot, cnt = s["sum"].to_numpy()[idx].sum(1), s["count"].to_numpy()[idx].sum(1)
    est = tot / cnt
    return float(np.quantile(est, 0.025)), float(np.quantile(est, 0.975))


def recal_test(d: pd.DataFrame) -> dict:
    R = rule()
    t = d[d["tested"]]
    diff = _ll(t[R["model_col"]].to_numpy(), t["y"].to_numpy()) - _ll(t["p_R"].to_numpy(), t["y"].to_numpy())   # positive: recalibrated is better
    lo, hi = _boot_by_game(pd.Series(diff), t["gid"], R["bootstrap"]["draws"], R["bootstrap"]["seed"])
    return {"rows": int(len(t)), "log_loss_raw": float(_ll(t[R["model_col"]], t["y"]).mean()), "log_loss_recal": float(_ll(t["p_R"], t["y"]).mean()),
            "log_loss_market": float(_ll(t[R["market_col"]], t["y"]).mean()), "gain": float(diff.mean()), "ci": [lo, hi], "adopted": bool(lo > 0)}


def make_leans(d: pd.DataFrame, qcol: str) -> pd.DataFrame:
    R = rule()
    cuts = R["size_cuts"]
    x = d.copy()
    x["q"], x["m"], x["c"] = x[qcol], x[R["market_col"]], x[R["close_col"]]
    x["edge"] = x["q"] - x["m"]
    x = x[x["edge"].abs() >= R["edge_threshold"]].copy()
    x["side"] = np.where(x["edge"] > 0, "over", "under")
    x["win"] = np.where(x["side"] == "over", x["y"], 1 - x["y"]).astype(float)
    x["price"] = np.where(x["side"] == "over", x["m"], 1 - x["m"])
    x["real"] = x["win"] - x["price"]
    x["clv"] = np.where(x["side"] == "over", x["c"] - x["m"], x["m"] - x["c"])
    a = x["edge"].abs()
    x["size"] = np.where(a >= cuts[2], "large", np.where(a >= cuts[1], "medium", "small"))
    x["market"] = x["stat"].map(STAT_NAME)
    return x


def benchmarks(d: pd.DataFrame, x: pd.DataFrame) -> dict:
    """Follow the market and a random side, on the same rows as the leans."""
    R = rule()
    rows = d.loc[x.index.intersection(d.index)] if len(x) else d.iloc[0:0]
    m, y = rows[R["market_col"]].to_numpy(), rows["y"].to_numpy()
    over = m >= 0.5
    follow = np.where(over, y - m, (1 - y) - (1 - m))
    rng = np.random.default_rng(R["random_side"]["seed"])
    rnd = np.mean([np.where(rng.random(len(m)) < 0.5, y - m, (1 - y) - (1 - m)).mean() for _ in range(R["random_side"]["draws"])]) if len(m) else None
    return {"follow_market_realized": float(follow.mean()) if len(m) else None, "random_side_realized": None if rnd is None else float(rnd)}


def summarize(x: pd.DataFrame, boot: bool = True) -> dict:
    R = rule()
    n = int(len(x))
    if n == 0:
        return {"n": 0, "note": "No leans in this selection."}
    sd = float(x["real"].std(ddof=1)) if n > 1 else 0.5
    need = int(np.ceil(((1.96 + 0.8416) * sd / R["power"]["target_edge"]) ** 2))
    out = {"n": n, "games": int(x["gid"].nunique()), "win_rate": float(x["win"].mean()), "stated_edge": float(x["edge"].abs().mean()), "realized_edge": float(x["real"].mean()),
           "clv": float(x["clv"].mean()), "need_for_2pt": need}
    if boot and x["gid"].nunique() > 2:
        lo, hi = _boot_by_game(x["real"], x["gid"], R["bootstrap"]["draws"], R["bootstrap"]["seed"])
        out["realized_ci"] = [lo, hi]
        out["finds_edge"] = bool(lo > 0 and out["clv"] > 0 and n >= need)
    out["note"] = (f"Too few leans to mean anything: about {need} are needed to detect a 2 point realized edge, and this selection has {n}." if n < need
                   else "Enough leans to detect a 2 point realized edge.")
    return out


def calibration(d: pd.DataFrame) -> dict:
    R = rule()
    out = {}
    for name, col in (("model", R["model_col"]), ("recalibrated", "p_R"), ("market", R["market_col"])):
        b = pd.cut(d[col], [0, .1, .25, .4, .6, .75, .9, 1.0], include_lowest=True)
        g = d.groupby(b, observed=True).agg(n=("y", "size"), stated=(col, "mean"), realized=("y", "mean"))
        out[name] = [{"bucket": str(k), "n": int(r.n), "stated": float(r.stated), "realized": float(r.realized)} for k, r in g.iterrows()]
    return out


def backtest() -> dict:
    d = recalibrate(load())
    rt = recal_test(d)
    qcol = "p_R" if rt["adopted"] else rule()["model_col"]
    x = make_leans(d, qcol)
    res = {"rule_sha256": rule_sha(), "model_used": qcol, "recal_test": rt, "universe_rows": int(len(d)), "universe_games": int(d["gid"].nunique()),
           "leans": int(len(x)), "no_lean": int(len(d) - len(x)), "all": summarize(x), "benchmarks": benchmarks(d, x), "calibration": calibration(d)}
    res["by_market"] = {m: summarize(g) for m, g in x.groupby("market")}
    res["by_size"] = {s: summarize(g) for s, g in x.groupby("size")}
    res["by_season"] = {str(s): summarize(g) for s, g in x.groupby("season")}
    return res, x


def rows_for_screen(x: pd.DataFrame) -> pd.DataFrame:
    return x[["gid", "season", "week", "market", "pid", "k", "side", "q", "m", "c", "edge", "size", "y", "win", "real", "clv"]]


def select(x: pd.DataFrame, market: str | None, week_from: int | None, week_to: int | None, size: str | None, season: int | None = 2026) -> pd.DataFrame:
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
