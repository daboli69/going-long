"""Write-once prospective freeze of quarterback rushing predictions for one week. Rule: docs/QB_RUSH_SPLIT2_PREREG.md.

    .venv/Scripts/python.exe scripts/qb_rush_freeze.py <week>            # dry run, prints
    .venv/Scripts/python.exe scripts/qb_rush_freeze.py <week> --write    # appends to reports/qb_rush/ledger.jsonl (refuses a week already written)

Run before the week's first kickoff. Starter = gamesim.starting_qbs; margin = mu_m of the newest frozen forecast file of the week.
Versions: B0 last-six mean, B1 shrunk 16-game mean, S (first split), S2 (shrinkage x 0.25).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import qb_rush_split as q  # noqa: E402
import qb_rush_split2 as q2  # noqa: E402
from lab import gamesim as gs  # noqa: E402
from lab import homewin_deep as h  # noqa: E402

LEDGER = ROOT / "reports" / "qb_rush" / "ledger.jsonl"
SEASON = 2026


def week_forecast(week: int) -> dict:
    files = sorted((ROOT / "data" / "raw" / "archive" / "forecast_games").glob(f"{SEASON}_w{week:02d}_*.json"))
    if not files:
        raise SystemExit(f"no frozen forecast file for week {week}")
    d = json.loads(files[-1].read_text(encoding="utf-8"))
    c = d["content"]
    c = json.loads(c) if isinstance(c, str) else c
    return {x["gid"]: x for x in c["games"]}, files[-1].name


def main(week: int, write: bool):
    if write and LEDGER.exists() and any(json.loads(l)["week"] == week for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()):
        raise SystemExit(f"week {week} already frozen")
    fc, fname = week_forecast(week)
    base = q2.prepare()
    data, _ = h.load_all(False)
    rows = []
    for gid, x in fc.items():
        for team, sign in ((x["home"], 1), (x["away"], -1)):
            ids = gs.starting_qbs(team, week, SEASON)
            if not ids:
                continue
            rows.append({"gid": gid, "team": team, "qb": ids[0], "m": sign * float(x["model"]["mu_m"])})
    dummy = pd.DataFrame([{**{c: 0 for c in base.columns}, "game_id": r["gid"], "season": SEASON, "week": week, "posteam": r["team"], "qb": r["qb"], "db": 30, "m": r["m"]} for r in rows])
    g = base[~base["game_id"].isin(set(dummy["game_id"]))]
    kick = data.games.set_index("gid")["kickoff_utc"]
    g = pd.concat([g, dummy], ignore_index=True)
    g = q.add_history(g, kick)
    grp = g.groupby("qb")["total"]
    g["h_total"] = grp.transform(lambda s: s.shift(1).rolling(q.WINDOW, min_periods=1).sum())
    g["m"] = g["m"].where(g["game_id"].isin(set(dummy["game_id"])) & (g["season"] == SEASON), g["m"])
    # restore the intended margins (add_history re-sorted the frame)
    mm = {(r["gid"], r["team"]): r["m"] for r in rows}
    cur = g["game_id"].isin(set(dummy["game_id"])) & (g["season"] == SEASON)
    g.loc[cur, "m"] = [mm.get((a, b), np.nan) for a, b in zip(g.loc[cur, "game_id"], g.loc[cur, "posteam"])]
    out = []
    preds = {}
    for name, f in (("S", 1.0), ("S2", 0.25)):
        q2.set_factor(f)
        tr = g[(g["season"] < SEASON) & (g["season"] >= q.FIT_FROM) & g["m"].notna()]
        L = q.league(g[g["season"] < SEASON])
        fit = q.fit_state(q.components(tr, L))
        te = q.predict(q.components(g[cur].copy(), L), fit, L)
        n = te["h_games"].fillna(0)
        te["pred_B1"] = (te["h_total"].fillna(0) + q2.K_B1 * L["total"]) / (n + q2.K_B1)
        preds[name] = te.set_index(["game_id", "posteam"])
    q2.set_factor(1.0)
    for r in rows:
        k = (r["gid"], r["team"])
        s, s2 = preds["S"].loc[k], preds["S2"].loc[k]
        out.append({"gid": r["gid"], "team": r["team"], "qb": r["qb"], "margin_used": round(r["m"], 3), "B0": round(float(s["pred_B0"]), 2), "B1": round(float(s["pred_B1"]), 2),
                    "S": round(float(s["pred_S"]), 2), "S2": round(float(s2["pred_S"]), 2)})
    rec = {"week": week, "season": SEASON, "frozen_at": datetime.now(timezone.utc).isoformat(), "forecast_file": fname, "rows": out}
    print(json.dumps(rec, indent=1)[:2500])
    if write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print("wrote", LEDGER)


if __name__ == "__main__":
    main(int(sys.argv[1]), "--write" in sys.argv)
