"""Kalshi as a market benchmark for the saved home-win walk-forward forecasts (descriptive; no gate, no promotion).

  python scripts/kalshi_benchmark.py            # refresh Kalshi history (settled markets cached), score, write report

Uses only Kalshi prices whose hourly candle ended at or before each model's own decision time, or at or before
kickoff for the close. Writes reports/kalshi/benchmark.json and data/cache/homewin_deep/kalshi_history.parquet.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import homewin_deep as h  # noqa: E402
from lab import homewin_eval as ev  # noqa: E402
from lab import kalshi as k  # noqa: E402
from lab.config import LAB_ROOT  # noqa: E402

OUT = LAB_ROOT / "reports" / "kalshi"


def log(m):
    print(m, flush=True)


def kalshi_at(hist, frame, time_col):
    by = {g: d for g, d in hist.groupby("gid")}
    out = []
    for gid, t, kick in zip(frame["gid"], frame[time_col], frame["kickoff_utc"]):
        d = by.get(gid)
        out.append(k.probability(d, gid, t, kick)["p_home"] if d is not None else np.nan)
    return np.array(out)


def compare_block(df, models, ref):
    y = df["y_home_win"].to_numpy(float)
    res = {"n": int(len(df)), ref: ev.metrics(y, df[ref].to_numpy())["log_loss"]}
    for m in models:
        c = ev.compare(df, m, ref, 0.05)
        res[m] = {"log_loss": float(ev._ll(y, df[m].to_numpy()).mean()), "delta_vs_kalshi": c["ll_delta"], "ci95": c["ll_ci"],
                  "brier_delta": c["brier_delta"]}
    return res


def clv(df, model, at, close):
    d = df[df[at].notna() & df[close].notna()]
    move = (d[close] - d[at]).to_numpy()
    side = np.sign(d[model].to_numpy() - d[at].to_numpy())
    c = move * side
    nz = c[c != 0]
    cl = (d["season"].astype(str) + "_" + d["week"].astype(str)).to_numpy()
    return {"games": int(len(c)), "mean_clv": float(c.mean()) if len(c) else None, "ci95": ev.cluster_boot(c, cl, 0.05) if len(c) else None,
            "toward": int((nz > 0).sum()), "away": int((nz < 0).sum()), "zero_moves": int((move == 0).sum()),
            "sign_p_one_sided": float(binomtest(int((nz > 0).sum()), len(nz), alternative="greater").pvalue) if len(nz) else None}


def main():
    games, _ = h.load_games()
    hist, cov = k.history(games, progress=log)
    hist.to_parquet(h.CACHE / "kalshi_history.parquet")
    log(f"Kalshi coverage: {cov['by_season']}")
    res = {"label": "descriptive benchmark; not a preregistered gate; nothing promoted", "coverage": cov}
    meta = games.set_index("gid")[["week"]]

    v1p = h.CACHE / "walk_forward.parquet"
    if v1p.exists():
        v1 = pd.read_parquet(v1p)
        v1 = v1[v1["season"] >= 2025].copy()
        v1["k_decision"], v1["k_close"] = kalshi_at(hist, v1, "decision_utc"), kalshi_at(hist, v1, "kickoff_utc")
        models = [f"p_{m}" for m in ev.MODELS]
        for col in ("k_decision", "k_close"):
            sub = v1.dropna(subset=[col])
            res[f"v1_weekly_vs_{col}"] = compare_block(sub, models, col)
        res["v1_clv_decision_to_close"] = {m: clv(v1, m, "k_decision", "k_close") for m in models}
        log(f"v1: {len(v1.dropna(subset=['k_close']))} games with Kalshi close")

    v2dir = h.CACHE / "v2"
    pts = {p: pd.read_parquet(v2dir / f"wf_{p}.parquet") for p in ("open", "wed", "fri", "t90") if (v2dir / f"wf_{p}.parquet").exists()}
    if pts:
        res["v2_points"] = {}
        for p, d in pts.items():
            d = d[d["season"] >= 2025].copy()
            d["k_at"], d["k_close"] = kalshi_at(hist, d, "point_utc"), kalshi_at(hist, d, "kickoff_utc")
            sub = d.dropna(subset=["k_at"])
            res["v2_points"][p] = {"accuracy_vs_kalshi_at_point": compare_block(sub, ["p_elo", "p_margin", "p_xgb_deep"], "k_at"),
                                   "clv_to_close": {m: clv(d, m, "k_at", "k_close") for m in ("p_elo", "p_margin", "p_xgb_deep")}}
        log("v2 points scored")

    simp = h.CACHE / "sim" / "games.parquet"
    if simp.exists():
        s = pd.read_parquet(simp)
        s = s[(s["season"] >= 2025) & ~s["tie"]].copy()
        s["y_home_win"] = s["y_home_win"].astype(float)
        s["k_close"] = kalshi_at(hist, s, "kickoff_utc")
        res["simulator_vs_kalshi_close"] = compare_block(s.dropna(subset=["k_close", "p_elo"]), ["p_sim", "p_elo"], "k_close")

    OUT.mkdir(parents=True, exist_ok=True)
    body = json.dumps(res, indent=1, default=str)
    (OUT / "benchmark.json").write_bytes(body.encode("utf-8"))
    log(f"Wrote reports/kalshi/benchmark.json sha256 {hashlib.sha256(body.encode()).hexdigest()}")
    for key in ("v1_weekly_vs_k_close", "v1_weekly_vs_k_decision"):
        if key in res:
            b = res[key]
            log(f"\n{key}: n={b['n']} Kalshi LL {b[key.split('_vs_')[1]]:.4f}")
            for m in ("p_elo", "p_margin_platt", "p_xgb_deep_platt", "p_xgb_v1"):
                x = b[m]
                log(f"  {m:<18} LL {x['log_loss']:.4f} delta {x['delta_vs_kalshi']:+.4f} [{x['ci95'][0]:+.4f},{x['ci95'][1]:+.4f}]")
    if "v2_points" in res:
        log("\nCLV on Kalshi prices (point -> close):")
        for p, b in res["v2_points"].items():
            for m, c in b["clv_to_close"].items():
                if c["games"]:
                    log(f"  {p:<5} {m:<11} n={c['games']} mean {c['mean_clv']:+.4f} [{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
                        f"{c['toward']}/{c['away']} zero={c['zero_moves']} p={c['sign_p_one_sided']:.3f}")


if __name__ == "__main__":
    main()
