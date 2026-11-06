"""Tails Amendment 3: counts, aligned prices and the power gate first. python scripts/leadlag_run.py"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import leadlag  # noqa: E402

if __name__ == "__main__":
    t, rep = leadlag.aligned()
    G = leadlag.games_frame()
    Q = leadlag.book_quotes(G)
    from lab import kalshi as K
    hist, _ = K.history(G, progress=lambda *_: None)
    t.to_parquet(ROOT / "data" / "cache" / "leadlag_aligned.parquet")
    rng = np.random.default_rng(20261106)
    res = {"counts": leadlag.counts(t, rep), "power": leadlag.power_table(t, rng)}
    res["qb_events"] = leadlag.qb_events(G, Q, hist)
    res["any_informative"] = bool(any(v.get("informative") for v in res["power"].values()))
    (ROOT / "docs" / "leadlag_results.json").write_text(json.dumps(res, indent=1, default=str))
    c = res["counts"]
    print("games", c["games_2026_weeks_1_to_8_played"], "both sides", c["games_with_both_sides_and_closes"])
    print("book quote rows", c["sportsbook"]["book_quote_rows"], c["sportsbook"]["book_quote_games"], "games; range", c["sportsbook"]["book_quote_range"])
    print("age", json.dumps(c["book_quote_age_at_horizon"]))
    for k, v in res["power"].items():
        a, b = v.get("a_B_kalshi_leads"), v.get("a_K_book_leads")
        print(k, v["games"], "informative", v["informative"], "" if not a else ("min detectable", round(a["min_detectable"], 3), round(b["min_detectable"], 3)))
    print("qb events", {k: v for k, v in res["qb_events"].items() if k != "events"})
    print("any informative:", res["any_informative"])
