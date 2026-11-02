"""Run the referee tests once; saves docs/refs_results.json and data/refs/games_refs.parquet for the screen."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import refs as R  # noqa: E402

if __name__ == "__main__":
    res, f = R.run()
    (ROOT / "docs" / "refs_results.json").write_text(json.dumps(res, indent=1, default=float))
    out = ROOT / "data" / "refs"
    out.mkdir(parents=True, exist_ok=True)
    f[["game_id", "season", "week", "home_team", "away_team", "referee", "spread_line", "result", "home_ats", "home_fav_ats", "over", "pen_home", "pen_away", "pen_gap", "plays"]].to_parquet(out / "games_refs.parquet")
    print(json.dumps({k: res[k] for k in ("games", "referees", "year_to_year", "claims", "any_effect_claimed", "tweet_check", "market", "penalty_dispersion", "discovery_ats_tests")}, indent=1, default=float))
    print("coverage", json.dumps(res["coverage"]["by_season"]), "mismatch", len(res["coverage"]["mismatches"]))
    print("top ATS discovery", json.dumps([{k: r[k] for k in ("measure", "referee", "n", "rate", "league", "p", "p_holm")} for r in res["discovery_ats"][:5]], default=float))
    print("top pen discovery", json.dumps(res["penalty_discovery"][:4], default=float))
