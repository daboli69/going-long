"""Forward test of the Wentz-over-Murray hunch. Rule: docs/GUT_FORWARD_WENTZ.md.

    .venv/Scripts/python.exe scripts/gut_forward.py freeze   # once, before the first game of the window
    .venv/Scripts/python.exe scripts/gut_forward.py score
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import gut_check as gc  # noqa: E402

LEDGER = ROOT / "reports" / "gut" / "forward_ledger.jsonl"
DOC = ROOT / "docs" / "GUT_FORWARD_WENTZ.md"
H_GUT, H_EQUAL = 0.069, -0.038
MARKS = (150, 300, 600)


def freeze_row() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8").splitlines()[0])


def freeze():
    if LEDGER.exists():
        raise SystemExit("already frozen")
    now = pd.Timestamp.now(tz="UTC")
    d = gc.dropbacks()
    pbp = pd.read_parquet(gc.RAW_DIR / "play_by_play_2026.parquet", columns=["game_id"])
    started = "2026_09_BUF_MIN" in set(pbp["game_id"])
    row = {"frozen_at": now.isoformat(), "doc_sha256": hashlib.sha256(DOC.read_bytes()).hexdigest(), "h_gut": H_GUT, "h_equal": H_EQUAL,
           "first_game": "2026_09_BUF_MIN", "first_game_already_in_data": bool(started), "wentz_2026_dropbacks_so_far": int(((d["season"] == 2026) & d["passer_id"].isin(gc.player_ids("Carson Wentz"))).sum())}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(row) + "\n", encoding="utf-8")
    print(json.dumps(row, indent=1))


def score():
    fr = freeze_row()
    cut = pd.Timestamp(fr["frozen_at"])
    d = gc.dropbacks()
    games = pd.read_parquet(gc.RAW_DIR / "games.csv".replace("csv", "parquet")) if (gc.RAW_DIR / "games.parquet").exists() else pd.read_csv(gc.RAW_DIR / "games.csv")
    games = games[games["season"] == 2026]
    ko = pd.to_datetime(games["gameday"].astype(str) + " " + games.get("gametime", "00:00").astype(str), utc=True, errors="coerce")
    ok = set(games.loc[ko > cut.tz_convert("UTC"), "game_id"]) if "game_id" in games else set()
    w = d[(d["season"] == 2026) & d["passer_id"].isin(gc.player_ids("Carson Wentz")) & (d["posteam"] == "MIN")]
    w = w[w["game_id"].isin(ok) | w["game_id"].eq(fr["first_game"])]
    n = len(w)
    out = {"dropbacks": n, "games": int(w["game_id"].nunique())}
    if n >= 2:
        m, se = float(w["epa_adj"].mean()), float(w["epa_adj"].std(ddof=1) / np.sqrt(n))
        lr = float(np.exp(norm.logpdf(m, H_GUT, se) - norm.logpdf(m, H_EQUAL, se)))
        out |= {"mean_adj_epa": round(m, 4), "se": round(se, 4), "likelihood_ratio_gut_over_equal": round(lr, 3)}
    out["marks_reached"] = [k for k in MARKS if n >= k]
    out["verdict"] = ("supports H_gut" if out.get("likelihood_ratio_gut_over_equal", 1) >= 10 else "supports H_equal" if out.get("likelihood_ratio_gut_over_equal", 1) <= 0.1 else "inconclusive") if n >= 600 else "no verdict before 600 dropbacks"
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"freeze": freeze, "score": score}[sys.argv[1]]()
