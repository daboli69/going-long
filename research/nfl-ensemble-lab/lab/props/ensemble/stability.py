"""B5: fixed first eight 2022 games, fixed seeds and simulation counts."""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from ...data_pipeline import FEATURE_STORE
from .. import game as G, models as M, players as PL, sim as S
from ..independent import IndependentAnchor
from .data import OUT
from .structural import build_inputs, tables


def run(log=print):
    table = tables(log)
    frame = pd.read_parquet(OUT / "features.parquet")
    games = pd.read_parquet(FEATURE_STORE)
    target = games[(games["season"] == 2022) & games["game_type"].eq("REG")].sort_values(["week", "game_id"]).head(8)
    panel = PL.panel(M.load_pbp([2021, 2022]), table)
    anchor = IndependentAnchor().fit(games)
    rows, errors = [], []
    for g in target.itertuples(index=False):
        try:
            teams, players, cols, info, _ = build_inputs(frame, panel, 2022, g)
            pred = anchor.predict(games[games["game_id"] == g.game_id]).iloc[0]
            e, _ = S.calibrate_v2(table, teams, players, [pred.home_points, pred.away_points], np.random.default_rng(20261019))
            actual = frame[frame["game_id"] == g.game_id].set_index("pid")
            eligible = G.eligible(info, actual)
            for sims in (250, 1000, 2000):
                for seed in (20261019, 20261020):
                    started = time.perf_counter()
                    result = S.simulate(table, teams, players, sims, e, np.random.default_rng(seed))
                    seconds = time.perf_counter() - started
                    for team, pid, stat in eligible:
                        if pid not in actual.index or pd.isna(actual.loc[pid, stat]):
                            continue
                        samples = result["stats"][stat][:, cols[pid]]
                        y = actual.loc[pid, stat]
                        q = np.quantile(samples, [.1, .5, .9])
                        rows.append({"game_id": g.game_id, "pid": pid, "stat": stat, "sims": sims, "seed": seed,
                            "q10": q[0], "q50": q[1], "q90": q[2], "seconds": seconds,
                            "coverage80": float(q[0] <= y <= q[2]), "pit": float((samples < y).mean() + .5 * (samples == y).mean())})
            log(f"stability {g.game_id}")
        except Exception as exc:
            errors.append({"game_id": g.game_id, "error": repr(exc)})
            log(f"FAILED stability {g.game_id}: {exc}; skipped")
    data = pd.DataFrame(rows)
    data.to_parquet(OUT / "stability2022.parquet", index=False)
    reference = data[data["sims"] == 2000][["game_id", "pid", "stat", "seed", "q10", "q50", "q90"]]
    merged = data.merge(reference, on=["game_id", "pid", "stat", "seed"], suffixes=("", "_ref"))
    for q in (10, 50, 90):
        merged[f"change{q}"] = abs(merged[f"q{q}"] - merged[f"q{q}_ref"])
    summaries, passing = [], []
    for sims, d in merged.groupby("sims"):
        by = []
        for stat, z in d.groupby("stat"):
            med = float(np.median(z[["change10", "change50", "change90"]].to_numpy()))
            threshold = .5 if stat == "rec" else 2.
            by.append({"stat": stat, "n": len(z), "median_absolute_quantile_change": med,
                       "threshold": threshold, "passes": med <= threshold,
                       "coverage80": float(z["coverage80"].mean()), "pit_histogram": np.histogram(z["pit"], bins=np.linspace(0, 1, 11))[0].tolist()})
        summaries.append({"sims": int(sims), "seconds_per_game": float(d.groupby(["game_id", "seed"])["seconds"].first().mean()), "by_stat": by})
        if all(z["passes"] for z in by):
            passing.append(int(sims))
    result = {"experiment": "B5", "games": data["game_id"].nunique(), "results": summaries,
              "recommended_sims": min(passing) if passing and not errors and data["game_id"].nunique() == 8 else None,
              "errors": errors, "note": "Eight-game development runtime diagnostic; no selection on 2023–25 or 2026"}
    (OUT / "stability2022.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
