"""How well do the Game Center's player rankings and touchdown chances match what happened? Played weeks of 2026 only.

    .venv\\Scripts\\python.exe scripts\\rankings_check.py

For each played week from 3 on, builds the rankings the way the screen does (lab/rankings.py: every number is as of before that week) and compares with
the real box scores. Aggregate numbers only; writes docs/RANKINGS_CHECK.md and docs/rankings_check.json. Descriptive, not a betting test: it says
nothing about prices. Local files only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import fpds_usage as X  # noqa: E402
from lab import gamecenter_data as D  # noqa: E402
from lab import gamesim as S  # noqa: E402
from lab import rankings as R  # noqa: E402
from lab import usage as U  # noqa: E402

FIRST_WEEK = 3
ACTUAL = {"rec_yds": "rec_yds", "rec": "rec", "rush_yds": "rush_yds", "pass_yds": "pass_yds"}


def rows_for(week: int) -> dict:
    """All candidate rows per stat for a week, before the top-60 cut (the same code path as the screen, with a large cut)."""
    old = R.TOP
    R.TOP = 10_000
    try:
        return R.build_week(week)["stats"]
    finally:
        R.TOP = old


def main():
    pg = U.player_games((D.SEASON,))
    tdt = X._td_table(D.SEASON)
    pid_by = S._pid_by_norm()
    played = sorted(int(w) for w in D.games_table().query("season == @D.SEASON and completed and game_type == 'REG'")["week"].unique() if w >= FIRST_WEEK)
    recs = []
    for wk in played:
        stats = rows_for(wk)
        act = pg[pg["week"] == wk].set_index(["pid"])
        tdw = tdt[tdt["week"] == wk].groupby("pid")[["rec_td", "rush_td"]].sum()
        for key, v in stats.items():
            for r in v["rows"]:
                pid = pid_by.get(S._norm(r["player"]))
                if pid is None:
                    continue
                if key == "td":
                    hit = float(((tdw.reindex([pid])["rec_td"].fillna(0) + tdw.reindex([pid])["rush_td"].fillna(0)).iloc[0]) > 0)
                    played_flag = pid in act.index
                    recs.append({"week": wk, "stat": key, "pid": pid, "score": r["score"], "proj": r["projection"], "actual": hit, "played": played_flag})
                else:
                    a = float(act.loc[pid, ACTUAL[key]]) if pid in act.index else np.nan
                    recs.append({"week": wk, "stat": key, "pid": pid, "score": r["score"], "proj": r["projection"], "actual": a, "played": pid in act.index})
    df = pd.DataFrame(recs)
    out = {"weeks": played, "rows": int(len(df)), "stats": {}}
    for key in R.STATS:
        d = df[(df["stat"] == key) & df["played"]].dropna(subset=["actual"])
        res = {"player_games": int(len(d))}
        if key != "td":
            per_week = []
            for wk, g in d.groupby("week"):
                if len(g) > 10:
                    per_week.append((spearmanr(g["score"], g["actual"])[0], spearmanr(g["proj"], g["actual"])[0]))
            res["spearman_score"] = float(np.nanmean([a for a, _ in per_week]))
            res["spearman_projection_only"] = float(np.nanmean([b for _, b in per_week]))
            top = d.groupby("week", group_keys=False).apply(lambda g: g.nlargest(10, "score"))
            res["top10_mean_actual"] = float(top["actual"].mean())
            res["all_mean_actual"] = float(d["actual"].mean())
            res["top10_projection_mean"] = float(top["proj"].mean())
        else:
            p = d["proj"].to_numpy()
            y = d["actual"].to_numpy()
            dec = pd.qcut(pd.Series(p), 5, duplicates="drop")
            rel = d.assign(bin=dec.values).groupby("bin", observed=True).agg(predicted=("proj", "mean"), actual=("actual", "mean"), n=("actual", "size"))
            res["reliability_quintiles"] = [{"predicted": float(r.predicted), "actual": float(r.actual), "n": int(r.n)} for r in rel.itertuples()]
            res["mean_predicted"], res["mean_actual"] = float(p.mean()), float(y.mean())
            # one scale c on the expected touchdowns (chance = 1 - exp(-c x lambda)), fitted by log likelihood on these weeks
            lam = -np.log1p(-np.clip(p, 1e-6, 1 - 1e-6))
            grid = np.arange(0.4, 1.41, 0.02)
            ll = [float(np.mean(y * np.log(1 - np.exp(-c * lam) + 1e-12) + (1 - y) * (-c * lam))) for c in grid]
            res["best_scale"] = float(grid[int(np.argmax(ll))])
            res["logloss_now"] = float(-ll[int(np.argmin(abs(grid - 1.0)))])
            res["logloss_best_scale"] = float(-max(ll))
            res["logloss_constant"] = float(-(y.mean() * np.log(y.mean()) + (1 - y.mean()) * np.log(1 - y.mean())))
            half = d["week"] <= sorted(d["week"].unique())[len(d["week"].unique()) // 2]
            res["mean_predicted_early_late"] = [float(p[half.to_numpy()].mean()), float(p[~half.to_numpy()].mean())]
            res["mean_actual_early_late"] = [float(y[half.to_numpy()].mean()), float(y[~half.to_numpy()].mean())]
        out["stats"][key] = res
    (ROOT / "docs" / "rankings_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
