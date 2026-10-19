"""First-offensive-TD categorical scores on 2022 only; no passing/return TD category."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import features as F
from .data import OUT
from .research import clustered_difference
from .combine import first_td_reweight
from ...data_pipeline import FEATURE_STORE


def run():
    # Source columns are the explicit allowed development loader; never eval files.
    plays = F.load_plays([2022])
    p = plays[(plays["season_type"] == "REG") & (plays["qtr"] <= 4) & plays["play_type"].isin(["pass", "run"])
              & plays["two_point_attempt"].fillna(0).eq(0)]
    td = p[p["pass_touchdown"].eq(1) | p["rush_touchdown"].eq(1)].sort_values(["game_id", "play_id"])
    first = td.groupby("game_id").first()
    outcomes = {gid: (r.receiver_player_id if r.pass_touchdown == 1 else r.rusher_player_id) for gid, r in first.iterrows()}
    ensemble = pd.read_parquet(OUT / "dev_predictions.parquet")
    ensemble = ensemble[ensemble["stat"] == "anytime_td"]
    structural_files = sorted((OUT / "structural_dev2022").glob("*.parquet"))
    schedule = pd.read_parquet(FEATURE_STORE, columns=["game_id", "season", "completed"])
    completed_games = set(schedule.loc[(schedule["season"] == 2022) & schedule["completed"], "game_id"])
    rows, concerns = [], []
    for path in structural_files:
        metadata = json.loads(path.with_suffix(".json").read_text())
        if metadata["season"] != 2022:
            raise ValueError("Forbidden TD evaluation season")
        if metadata["game_id"] not in completed_games:
            continue  # Cancelled/unplayed games have no invented no-TD outcome.
        e = ensemble[ensemble["game_id"] == metadata["game_id"]].set_index("pid")
        st = pd.read_parquet(path)
        for game in metadata["games"]:
            if game["member"] != "sim_independent":
                continue
            ids = sorted(game["first_td"])
            probabilities = np.array([game["first_td"][pid] for pid in ids] + [game["no_offensive_td"]])
            if not np.isclose(probabilities.sum(), 1):
                raise ValueError("First-TD probability mass does not sum to one")
            actual = outcomes.get(metadata["game_id"], "no_offensive_td")
            if actual not in ids and actual != "no_offensive_td":
                concerns.append({"game_id": metadata["game_id"], "reason": "actual first scorer absent from prior-roster candidate set"})
                # Keep the game and expose zero assigned probability with EPS
                # log-loss clipping; never drop a bad scorer prediction.
                ids += [actual]
                probabilities = np.r_[probabilities[:-1], 0., probabilities[-1]]
            index = len(ids) if actual == "no_offensive_td" else ids.index(actual)
            onehot = np.zeros(len(ids) + 1)
            onehot[index] = 1
            any_rows = st[(st["stat"] == "anytime_td") & (st["member"] == "sim_independent")].drop_duplicates("pid").set_index("pid")
            structural_any, learned_any = [], []
            for pid in ids:
                sa = float(any_rows.loc[pid, "anytime_td"]) if pid in any_rows.index else 0.
                structural_any.append(sa)
                learned_any.append(float(e.loc[pid, "equal"]) if pid in e.index else sa)
            reweighted = first_td_reweight(probabilities[:-1], structural_any, learned_any, probabilities[-1])
            row = {"game_id": metadata["game_id"], "actual": actual,
                "structural_log_loss": float(-np.log(max(probabilities[index], 1e-6))),
                "ensemble_log_loss": float(-np.log(max(reweighted[index], 1e-6))),
                "structural_brier": float(((probabilities - onehot) ** 2).sum()),
                "ensemble_brier": float(((reweighted - onehot) ** 2).sum())}
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return {"games": 0, "status": "blocked: no structural first-TD files"}
    df.to_parquet(OUT / "first_td_scores2022.parquet", index=False)
    result = {"experiment": "B4 first TD", "games": len(df), "definition": "First offensive rushing/receiving TD in regulation; passing/defensive/special-teams TDs excluded",
        "log_loss": {"structural": float(df["structural_log_loss"].mean()), "reweighted": float(df["ensemble_log_loss"].mean()),
                     "paired_ci": clustered_difference(df["game_id"], df["ensemble_log_loss"] - df["structural_log_loss"])},
        "brier": {"structural": float(df["structural_brier"].mean()), "reweighted": float(df["ensemble_brier"].mean()),
                  "paired_ci": clustered_difference(df["game_id"], df["ensemble_brier"] - df["structural_brier"])},
        "concerns": concerns, "decision": "descriptive development diagnostic only"}
    (OUT / "first_td_research2022.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
