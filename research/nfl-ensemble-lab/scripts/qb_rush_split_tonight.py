"""Rushing split projection for one quarterback's next game (research challenger; see docs/QB_RUSH_SPLIT_PREREG.md).

    .venv/Scripts/python.exe scripts/qb_rush_split_tonight.py <qb gsis id> <game_id> <team> <margin> [<margin> ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import qb_rush_split as q  # noqa: E402
from lab import homewin_deep as h  # noqa: E402


def main(qb, gid, team, margins):
    p = q.load_plays(range(2004, 2027))
    data, _ = h.load_all(False)
    kick = data.games.set_index("gid")["kickoff_utc"]
    g = q.starter_games(p)
    season = int(gid.split("_")[0])
    dummy = {c: 0 for c in g.columns}
    dummy.update({"game_id": gid, "season": season, "week": int(gid.split("_")[1]), "posteam": team, "qb": qb, "db": 30})
    g = pd.concat([g, pd.DataFrame([dummy])], ignore_index=True)
    g = q.add_history(g, kick)
    wf = pd.read_parquet(h.CACHE / "walk_forward.parquet")[["gid", "pred_margin"]].set_index("gid")["pred_margin"]
    home = data.games.set_index("gid")["home"]
    g["m"] = np.where(g["posteam"] == g["game_id"].map(home), g["game_id"].map(wf), -g["game_id"].map(wf))
    tr = g[(g["season"] < season) & (g["season"] >= q.FIT_FROM) & g["m"].notna()]
    L = q.league(g[g["season"] < season])
    fit = q.fit_state(q.components(tr, L))
    row = g[(g["game_id"] == gid) & (g["qb"] == qb)].copy()
    out = {"qb": qb, "game": gid, "history_games": float(row["h_games"].iloc[0]), "baseline_last6_mean": None if pd.isna(row["b0_mean"].iloc[0]) else round(float(row["b0_mean"].iloc[0]), 1), "by_margin": {}}
    for m in margins:
        r = row.copy()
        r["m"] = m
        r = q.predict(q.components(r, L), fit, L).iloc[0]
        out["by_margin"][str(m)] = {"designed_att": round(r["mu_d"], 2), "designed_yds": round(r["mu_d"] * r["ypa_d"], 1), "scramble_att": round(r["mu_s"], 2),
                                    "scramble_yds": round(r["mu_s"] * r["ypa_s"], 1), "kneels": round(r["mu_k"], 2), "kneel_yds": round(r["mu_k"] * L["ypk"], 1), "total_yds": round(r["pred_S"], 1)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], [float(x) for x in sys.argv[4:]])
