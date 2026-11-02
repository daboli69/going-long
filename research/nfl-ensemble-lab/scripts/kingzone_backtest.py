"""Check the King of the End Zone model against finished games of the current season: python scripts/kingzone_backtest.py

For each completed regular-season game it builds the board as the app would before kickoff (league and player history strictly before that week),
finds the real longest touchdown in play-by-play, and scores the model's chance for that scorer against a plain baseline that splits the
game's touchdown chance in proportion to each player's expected touchdowns (the number the touchdown rankings already use).
It is a small sample (one event per game); it reports log score, how often the winner was in the model's top 1, 3 and 5, and the average
chance given to the winner. It is not a betting return: no prices are used.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import gamecenter_data as D, gamesim as S, kingzone as K, rankings as R  # noqa: E402


def main() -> None:
    g = D.games_table()
    g = g[(g["season"] == D.SEASON) & (g["game_type"] == "REG") & g["completed"].astype(bool)].sort_values(["week", "kickoff_utc"])
    names = {v: k for k, v in S._pid_by_norm().items()}
    out = []
    for r in g.itertuples():
        act = K.actual_longest(r.game_id)
        sim = S.simulate(r.game_id, "typical", 0)
        if not act or not sim or not sim.get("ok"):
            continue
        res = K.probabilities(sim, int(r.week))
        pid_of = {(x["player"], x["team"]): S._pid_by_norm().get(S._norm(x["player"])) for x in res["rows"]}
        model = {k: x["chance"] for k, x in zip(pid_of, res["rows"])}
        # baseline: share of the game's touchdown chance in proportion to expected touchdowns, with the same field share as the model
        tdc = R.td_chances(sim)
        tot = sum(v["exp_td"] for v in tdc.values()) or 1.0
        base = {k: v["exp_td"] / tot * sum(x["chance"] for x in res["rows"]) for k, v in tdc.items()}
        if act["by"] == "player":
            hit = [k for k, p in pid_of.items() if p in act["pids"]]
            pm = sum(model[k] for k in hit) / max(len(act["pids"]), 1) if hit else None
            pb = sum(base.get(k, 0.0) for k in hit) / max(len(act["pids"]), 1) if hit else None
            ranked = sorted(res["rows"], key=lambda x: -x["chance"])
            rank = next((i for i, x in enumerate(ranked, 1) if (x["player"], x["team"]) in hit), None)
            field_m = sum(res["field"].values()) + sum(res["unlisted"].values())
        else:
            hit, pm, pb, rank = [], None, None, None
            field_m = sum(res["field"].values())
        out.append({"gid": r.game_id, "week": int(r.week), "winner": act, "model_chance": pm, "baseline_chance": pb, "rank": rank, "listed": bool(hit),
                    "field_chance": field_m})
        print(r.game_id, act.get("scorers"), act["length"], None if pm is None else round(pm, 3), rank, flush=True)
    listed = [o for o in out if o["listed"] and o["baseline_chance"]]
    floor = 0.002
    summary = {"games": len(out), "winner_listed": len(listed), "winner_not_listed_or_defense": len(out) - len(listed),
               "mean_log_score_model": float(np.mean([np.log(max(o["model_chance"], floor)) for o in listed])) if listed else None,
               "mean_log_score_baseline": float(np.mean([np.log(max(o["baseline_chance"], floor)) for o in listed])) if listed else None,
               "mean_chance_model": float(np.mean([o["model_chance"] for o in listed])) if listed else None,
               "mean_chance_baseline": float(np.mean([o["baseline_chance"] for o in listed])) if listed else None,
               "top1": float(np.mean([o["rank"] == 1 for o in listed])) if listed else None, "top3": float(np.mean([o["rank"] <= 3 for o in listed])) if listed else None,
               "top5": float(np.mean([o["rank"] <= 5 for o in listed])) if listed else None,
               "mean_field_chance": float(np.mean([o["field_chance"] for o in out])) if out else None,
               "field_share_actual": float(np.mean([1 - o["listed"] for o in out])) if out else None}
    (ROOT / "docs" / "kingzone_backtest.json").write_text(json.dumps({"summary": summary, "games": out}, indent=1, default=str))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
