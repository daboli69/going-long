"""Test the independent drive simulation against the betting market, and save how much (if at all) it may move the simulated game.

    .venv\\Scripts\\python.exe scripts\\drivesim_check.py

Fits the home edge and scoring scale on 2022-2024 completed games, fits blend weights with the market on the same games, then scores
2025 and 2026 games the fit never saw. A blend weight stays zero unless the blend beats the market on both years with the whole 90%
interval below zero. Writes docs/DRIVE_SIM_CHECK.md, docs/drivesim_check.json and data/cache/drivesim_rule.json. Local files only.
"""
from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import drivesim as DS  # noqa: E402
from lab import gamecenter_data as D  # noqa: E402

N_FIT, N_EVAL = 1500, 4000


def frame() -> pd.DataFrame:
    G = D.games_table()
    G = G[(G["game_type"] == "REG") & G["completed"] & (G["season"] >= 2022)].dropna(subset=["spread_line", "total_line", "market_p_home_novig"])
    return G[["season", "week", "game_id", "home_team", "away_team", "home_score", "away_score", "spread_line", "total_line", "market_p_home_novig"]].reset_index(drop=True)


def sim_all(G: pd.DataFrame, edge: float, scale: float, n: int) -> pd.DataFrame:
    r = DS.rates()
    lg = DS.league_means(r)
    rows = []
    for x in G.itertuples():
        m = DS.matchup(r, x.game_id, x.home_team, x.away_team, lg)
        if m is None:
            rows.append((np.nan, np.nan, np.nan))
            continue
        s = DS.summarize(*DS.simulate(m, n, zlib.crc32(x.game_id.encode()), edge, scale))
        rows.append((s["margin"], s["total"], s["p_home"]))
    return pd.DataFrame(rows, columns=["sm", "st", "sp"], index=G.index)


def paired(err_new, err_old, season, draws=2000, seed=11):
    """Mean of (new - old) per-game loss and a 90% interval, resampling games."""
    d = np.asarray(err_new) - np.asarray(err_old)
    idx = np.random.default_rng(seed).integers(0, len(d), (draws, len(d)))
    m = d[idx].mean(1)
    return {"games": int(len(d)), "loss_new": float(np.mean(err_new)), "loss_old": float(np.mean(err_old)), "diff": float(d.mean()), "lo": float(np.percentile(m, 5)), "hi": float(np.percentile(m, 95))}


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def main():
    G = frame()
    train = G["season"] <= 2024
    # 1) scoring scale: make the simulated total average match the real total on the training games
    best_scale, best_gap = 1.0, 1e9
    for scale in np.arange(0.94, 1.081, 0.02):
        S = sim_all(G[train].iloc[::3], 0.04, scale, N_FIT)
        gap = abs(S["st"].mean() - G.loc[S.index, "home_score"].add(G.loc[S.index, "away_score"]).mean())
        if gap < best_gap:
            best_scale, best_gap = round(float(scale), 2), gap
    # 2) home edge: smallest squared margin error on the training games
    best_edge, best_mse = 0.04, 1e9
    for edge in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10):
        S = sim_all(G[train].iloc[::3], edge, best_scale, N_FIT)
        mse = float(((S["sm"] - (G.loc[S.index, "home_score"] - G.loc[S.index, "away_score"])) ** 2).mean())
        if mse < best_mse:
            best_edge, best_mse = edge, mse
    S = sim_all(G, best_edge, best_scale, N_EVAL)
    G = G.join(S).dropna(subset=["sm"])
    G["am"] = G["home_score"] - G["away_score"]
    G["at"] = G["home_score"] + G["away_score"]
    G["won"] = (G["am"] > 0).astype(float) + 0.5 * (G["am"] == 0)
    train = G["season"] <= 2024

    out = {"edge": best_edge, "scale": best_scale, "fit_games": int(train.sum()), "tests": {}}
    weights = {}
    for name, mkt, sim, act, kind in (("margin", "spread_line", "sm", "am", "sq"), ("total", "total_line", "st", "at", "sq"), ("win", "market_p_home_novig", "sp", "won", "ll")):
        grid = np.round(np.arange(0, 1.001, 0.05), 2)

        def blend(w, d):
            if kind == "sq":
                return (1 - w) * d[mkt] + w * d[sim]
            z = (1 - w) * logit(d[mkt]) + w * logit(d[sim])
            return 1 / (1 + np.exp(-z))

        def loss(w, d):
            b = blend(w, d)
            if kind == "sq":
                return ((b - d[act]) ** 2).to_numpy()
            b = np.clip(b, 1e-4, 1 - 1e-4)
            return (-(d[act] * np.log(b) + (1 - d[act]) * np.log(1 - b))).to_numpy()
        tr = G[train]
        w_best = float(grid[int(np.argmin([loss(w, tr).mean() for w in grid]))])
        res = {"weight_fitted": w_best, "tests": {}}
        for label, sub in (("2025", G[G["season"] == 2025]), ("2026", G[G["season"] == 2026])):
            res["tests"][label] = {"blend_vs_market": paired(loss(w_best, sub), loss(0.0, sub), label),
                                   "drive_sim_alone_vs_market": paired(loss(1.0, sub), loss(0.0, sub), label)}
        passes = w_best > 0 and all(t["blend_vs_market"]["hi"] < 0 for t in res["tests"].values())
        res["used"] = bool(passes)
        weights[f"w_{name}"] = w_best if passes else 0.0
        out["tests"][name] = res

    # agreement: how often the independent sim picks the same winner as the market
    t = G[G["season"] >= 2025]
    out["same_pick"] = float(((t["sm"] > 0) == (t["spread_line"] > 0)).mean())
    out["pick_accuracy"] = {"market": float(((t["spread_line"] > 0) == (t["am"] > 0)).mean()), "drive_sim": float(((t["sm"] > 0) == (t["am"] > 0)).mean())}
    rule = {"edge": best_edge, "scale": best_scale, **weights, "created_at": pd.Timestamp.now(tz="UTC").isoformat()}
    DS.PARAMS_PATH.write_text(json.dumps(rule, indent=1), encoding="utf-8")
    (ROOT / "docs" / "drivesim_check.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")

    L = ["# Independent drive simulation against the betting market", "",
         "Generated by `scripts/drivesim_check.py`. The drive simulation uses no betting line: each team's drives per game and touchdown and field-goal "
         f"rates per drive (and what its opponent allows), as known before the game. Scoring scale {best_scale} and home edge {best_edge:.0%} were fitted on "
         f"{out['fit_games']} completed games from 2022 to 2024. Everything below is scored on 2025 and 2026 games the fit never saw.", "",
         "Loss is the average squared miss (margin and total) or log loss (win chance); lower is better. The interval is 90%, from resampling games.", "",
         "| What | Year | Games | Market | Drive simulation alone | Market and simulation blended | Blend minus market (interval) | Used |", "|---|---|---|---|---|---|---|---|"]
    for name, res in out["tests"].items():
        for label, t in res["tests"].items():
            b, a = t["blend_vs_market"], t["drive_sim_alone_vs_market"]
            L.append(f"| {name.capitalize()} | {label} | {b['games']} | {b['loss_old']:.3f} | {a['loss_new']:.3f} | {b['loss_new']:.3f} | {b['diff']:+.3f} ({b['lo']:+.3f} to {b['hi']:+.3f}) | {'yes' if res['used'] else 'no'} |")
    L += ["", "Blend weight on the drive simulation, fitted on 2022 to 2024 (zero unless it beat the market in both years):", ""]
    for name, res in out["tests"].items():
        L.append(f"- {name.capitalize()}: fitted {res['weight_fitted']:.2f}; " + ("used." if res["used"] else "not used, so the betting market alone sets this number."))
    L += ["", f"On 2025 and 2026 games the market's side won {out['pick_accuracy']['market']:.1%} of the time and the drive simulation's side {out['pick_accuracy']['drive_sim']:.1%}; "
          f"they picked the same side in {out['same_pick']:.1%} of games.", ""]
    (ROOT / "docs" / "DRIVE_SIM_CHECK.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print("\nRULE", json.dumps(rule))


if __name__ == "__main__":
    main()
