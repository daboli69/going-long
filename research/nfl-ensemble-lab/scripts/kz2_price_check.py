"""Model anytime-touchdown chance against archived Kalshi anytime-touchdown prices, for finished 2026 games (the only archived player prices that exist for free).

Uses the newest quote taken before kickoff for each player (mid of bid and ask) and the 2026 holdout predictions in data/cache/kz2/results_2026.json.
Scores log loss and Brier for the model and for the quote on the same players, with a bootstrap over players. It is a check of the model's touchdown chances, not of the
longest-touchdown ranking: no longest-play or King of the End Zone prices were archived. Output: docs/kingzone_price_check.json.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import gamecenter_data as D  # noqa: E402
from lab import gamesim as S  # noqa: E402
from lab import kz2 as K  # noqa: E402

SNAPS = ROOT / "data" / "cache" / "props_kalshi" / "td_snapshots.jsonl"


def main() -> None:
    res = {r["gid"]: r for r in json.loads((ROOT / "data" / "cache" / "kz2" / "results_2026.json").read_text())}
    g = D.games_table().set_index("game_id")
    t = K.load()["touches"]
    scored = t[(t["season"] == D.SEASON) & (t["td"] == 1)].groupby(["game_id", "pid"]).size()
    quotes: dict = {}
    for line in SNAPS.read_text(encoding="utf-8").splitlines():
        s = json.loads(line)
        for r in s["rows"]:
            gid = r["gid"]
            if gid not in g.index or r.get("bid") is None or r.get("ask") is None:
                continue
            if pd.Timestamp(s["t"]) < pd.Timestamp(g.loc[gid, "kickoff_utc"]):
                quotes[(gid, r["player"])] = (float(r["bid"]) + float(r["ask"])) / 2
    by = S._pid_by_norm()
    rows = []
    for (gid, player), mid in quotes.items():
        if gid not in res or not bool(g.loc[gid, "completed"]):
            continue
        pid = by.get(S._norm(player))
        mine = {p: a for p, _, a in res[gid]["rows"]}
        if pid is None or pid not in mine:
            continue
        rows.append({"gid": gid, "player": player, "model": mine[pid], "market": mid, "y": int((gid, pid) in scored.index)})
    d = pd.DataFrame(rows)
    d = d[(d["market"] > 0.01) & (d["market"] < 0.99)]
    ll = lambda p, y: -(y * np.log(np.clip(p, 1e-3, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-3, 1)))
    d["ll_model"], d["ll_market"] = ll(d["model"], d["y"]), ll(d["market"], d["y"])
    d["br_model"], d["br_market"] = (d["model"] - d["y"]) ** 2, (d["market"] - d["y"]) ** 2
    diff = (d["ll_model"] - d["ll_market"]).to_numpy()
    rng = np.random.default_rng(1)
    boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(5000)]
    out = {"players": int(len(d)), "games": int(d["gid"].nunique()), "touchdown_rate": float(d["y"].mean()), "mean_model": float(d["model"].mean()), "mean_market": float(d["market"].mean()),
           "log_loss_model": float(d["ll_model"].mean()), "log_loss_market": float(d["ll_market"].mean()), "brier_model": float(d["br_model"].mean()), "brier_market": float(d["br_market"].mean()),
           "log_loss_diff_model_minus_market": {"mean": float(diff.mean()), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]},
           "note": "Lower is better. A positive difference means the model was worse than the quote. Anytime touchdowns only; no longest-play prices exist in the free archive."}
    (ROOT / "docs" / "kingzone_price_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
