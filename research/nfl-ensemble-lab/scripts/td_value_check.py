"""Did the Market value tab's anytime-touchdown picks work? Scores the saved Kalshi snapshots against what happened.

    .venv\\Scripts\\python.exe scripts\\td_value_check.py

Reads data/cache/props_kalshi/td_snapshots.jsonl (written each time the Market value tab prices a week, at most every ten minutes). For every player in a
game that has finished, takes the LAST snapshot before kickoff, then compares:
  - our chance and the Kalshi mid price against whether he scored (log loss; lower is better),
  - buying one YES contract at the ask for the flagged picks (our number above the price after fees) against all other priced players: hit rate, average ask,
    and average profit per contract after Kalshi's fee.
Aggregate numbers only; writes docs/td_value_check.json. Descriptive until there are many weeks: a few dozen picks cannot separate skill from luck, and the
report says how many it has. Local files only (no network).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import fpds_usage as X  # noqa: E402
from lab import gamecenter_data as D  # noqa: E402
from lab import gamesim as S  # noqa: E402
from lab import tdmarket as M  # noqa: E402


def logloss(p, y):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def main():
    if not M.SNAP.exists():
        print("No snapshots yet: open the Market value tab on a week with games still to play.")
        return
    G = D.games_table().set_index("game_id")
    snaps = [json.loads(line) for line in M.SNAP.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    for s in snaps:
        for r in s["rows"]:
            rows.append({**r, "t": pd.Timestamp(s["t"]), "week": s["week"]})
    d = pd.DataFrame(rows)
    if d.empty:
        print("Snapshots hold no priced players yet.")
        return
    d["kickoff"] = d["gid"].map(lambda g: G.loc[g, "kickoff_utc"] if g in G.index else pd.NaT)
    d["done"] = d["gid"].map(lambda g: bool(G.loc[g, "completed"]) if g in G.index else False)
    d = d[d["done"] & (d["t"] < d["kickoff"])]
    if d.empty:
        print("No snapshot belongs to a finished game yet. Run this after the games.")
        return
    d = d.sort_values("t").groupby("ticker").tail(1)       # last look before kickoff
    td = X._td_table(D.SEASON)
    pid_by = S._pid_by_norm()
    hit = []
    for r in d.itertuples():
        pid = pid_by.get(S._norm(r.player))
        wk = int(G.loc[r.gid, "week"])
        x = td[(td["week"] == wk) & (td["pid"] == pid)]
        hit.append(float((x["rec_td"].sum() + x["rush_td"].sum()) > 0))
    d["hit"] = hit
    d["mid"] = (d["bid"] + d["ask"]) / 2
    d["fee"] = M.FEE * d["ask"] * (1 - d["ask"])
    d["net"] = d["ours"] - d["ask"] - d["fee"]
    d["flag"] = (d["net"] >= M.VALUE_EDGE) & (d["ours"] >= M.MIN_CHANCE)
    d["profit"] = d["hit"] - d["ask"] - d["fee"]
    out = {"players_scored": int(len(d)), "weeks": sorted(int(w) for w in d["week"].unique()),
           "logloss_ours": logloss(d["ours"].to_numpy(), d["hit"].to_numpy()), "logloss_kalshi_mid": logloss(d["mid"].to_numpy(), d["hit"].to_numpy()),
           "mean_ours": float(d["ours"].mean()), "mean_mid": float(d["mid"].mean()), "actual_rate": float(d["hit"].mean())}
    for name, m in (("flagged", d["flag"]), ("not_flagged", ~d["flag"])):
        x = d[m]
        out[name] = {"n": int(len(x)), "mean_ours": float(x["ours"].mean()) if len(x) else None, "mean_ask": float(x["ask"].mean()) if len(x) else None,
                     "hit_rate": float(x["hit"].mean()) if len(x) else None, "profit_per_contract_after_fees": float(x["profit"].mean()) if len(x) else None}
    out["note"] = "A few dozen picks cannot tell skill from luck; this becomes informative over many weeks."
    (ROOT / "docs" / "td_value_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
