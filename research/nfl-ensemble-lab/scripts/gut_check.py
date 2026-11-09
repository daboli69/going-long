"""Check a hunch of the form "A is better than B" on EPA per dropback. Rule: docs/GUT_PROTOCOL.md.

    .venv/Scripts/python.exe scripts/gut_check.py --a "Carson Wentz" --b "Kyler Murray" --team MIN

Read-only except one appended line in reports/gut/claims_ledger.jsonl. No network.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab.config import RAW_DIR  # noqa: E402

K = 250.0
BOOT, SEED = 5000, 20261109
SEASONS = range(2022, 2027)
LEDGER = ROOT / "reports" / "gut" / "claims_ledger.jsonl"


def dropbacks() -> pd.DataFrame:
    frames = []
    for s in SEASONS:
        p = pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=["season", "week", "game_id", "posteam", "defteam", "passer_id", "qb_dropback", "epa"])
        frames.append(p[(p["qb_dropback"] == 1) & p["passer_id"].notna() & p["epa"].notna()])
    d = pd.concat(frames, ignore_index=True)
    key = ["season", "defteam"]
    tot, cnt = d.groupby(key)["epa"].transform("sum"), d.groupby(key)["epa"].transform("size")
    gs, gc = d.groupby(key + ["game_id"])["epa"].transform("sum"), d.groupby(key + ["game_id"])["epa"].transform("size")
    opp = (tot - gs) / (cnt - gc).replace(0, np.nan)
    d["epa_adj"] = d["epa"] - (opp.fillna(d["epa"].mean()) - d["epa"].mean())
    return d


def player_ids(name: str) -> list[str]:
    pl = pd.read_parquet(RAW_DIR / "players.parquet").drop_duplicates("gsis_id")
    ids = pl.loc[pl["display_name"] == name, "gsis_id"].tolist()
    if not ids:
        raise SystemExit(f"no player named {name!r}")
    return ids


def games(x: pd.DataFrame, col: str) -> np.ndarray:
    g = x.groupby("game_id")[col].agg(["sum", "size"])
    return g.to_numpy(float)


def shrunk(g: np.ndarray, league: float) -> float:
    return float((g[:, 0].sum() + K * league) / (g[:, 1].sum() + K)) if len(g) else float("nan")


def compare(a: np.ndarray, b: np.ndarray, league: float, rng) -> dict:
    out = {"n_a": int(a[:, 1].sum()), "games_a": len(a), "n_b": int(b[:, 1].sum()), "games_b": len(b),
           "est_a": round(shrunk(a, league), 4), "est_b": round(shrunk(b, league), 4)}
    if len(a) == 0 or len(b) == 0:
        return out | {"diff": None}
    diffs = []
    for _ in range(BOOT):
        ra, rb = a[rng.integers(0, len(a), len(a))], b[rng.integers(0, len(b), len(b))]
        diffs.append(shrunk(ra, league) - shrunk(rb, league))
    diffs = np.array(diffs)
    return out | {"diff": round(out["est_a"] - out["est_b"], 4), "lo80": round(float(np.quantile(diffs, 0.1)), 4), "hi80": round(float(np.quantile(diffs, 0.9)), 4),
                  "p_a_better": round(float((diffs > 0).mean()), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True), ap.add_argument("--b", required=True), ap.add_argument("--team", required=True)
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()
    d = dropbacks()
    ia, ib = player_ids(args.a), player_ids(args.b)
    rng = np.random.default_rng(SEED)
    res = {}
    for wname, mask in (("last3seasons", d["season"] >= 2024), ("same_offense", (d["season"] >= 2025) & (d["posteam"] == args.team))):
        w = d[mask]
        league = {c: float(d[d["season"] >= 2024][c].mean()) for c in ("epa", "epa_adj")}
        for col in ("epa", "epa_adj"):
            res[f"{wname}/{col}"] = compare(games(w[w["passer_id"].isin(ia)], col), games(w[w["passer_id"].isin(ib)], col), league[col], rng)
    p = [res[f"{w}/epa_adj"].get("p_a_better") for w in ("last3seasons", "same_offense")]
    if None in p:
        verdict = "not distinguishable"
    elif min(p) >= 0.90:
        verdict = "supported (retrospective)"
    elif max(p) <= 0.10:
        verdict = "contradicted"
    else:
        verdict = "not distinguishable"
    rec = {"date": str(date.today()), "claim": f"{args.a} better than {args.b} on EPA per dropback", "team": args.team, "results": res, "verdict": verdict}
    print(json.dumps(rec, indent=1))
    if not args.no_log:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
