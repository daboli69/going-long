"""Over and under calls come from the frozen arm's projection against the consensus line."""
import pandas as pd

from lab import ou_calls


def test_calls_follow_projection_versus_line(tmp_path, monkeypatch):
    d = tmp_path / "2026_w09_r001_x" / "presentations" / "p1"
    d.mkdir(parents=True)
    base = {"week": 9, "training_last_completed_week": 8, "forecast_created_at": "t", "home_team": "SEA", "away_team": "ARI", "game_id": "g", "kickoff_utc": "k", "position": "WR",
            "line_status": "current", "confidence_tier": "C", "mean": 50.0, "q10": 20.0, "q90": 90.0, "p_over": 0.6, "p_under": 0.4}
    rows = [
        {**base, "arm": "frozen", "stat": "rec_yds", "name": "A", "team": "ARI", "median": 60.0, "consensus_line": 48.5},
        {**base, "arm": "frozen", "stat": "rec_yds", "name": "B", "team": "SEA", "median": 40.0, "consensus_line": 48.5, "p_over": 0.3, "p_under": 0.7},
        {**base, "arm": "control", "stat": "rec_yds", "name": "C", "team": "SEA", "median": 40.0, "consensus_line": 48.5},      # other arm, ignored
        {**base, "arm": "frozen", "stat": "anytime_td", "name": "D", "team": "SEA", "median": 0.4, "consensus_line": 0.5},   # not a numeric line
        {**base, "arm": "frozen", "stat": "rec", "name": "E", "team": "SEA", "median": 5.0, "consensus_line": float("nan")},  # no line
    ]
    pd.DataFrame(rows).to_csv(d / "leans.csv", index=False)
    monkeypatch.setattr(ou_calls, "ROOT", tmp_path)
    ou_calls._CACHE.clear()
    out = ou_calls.calls()
    got = {r["player"]: r for r in out["rows"]}
    assert set(got) == {"A", "B"}
    assert got["A"]["call"] == "Over" and got["A"]["chance"] == 0.6 and got["A"]["opp"] == "SEA"
    assert got["B"]["call"] == "Under" and got["B"]["chance"] == 0.7 and got["B"]["opp"] == "ARI"
    assert out["week"] == 9 and out["through_week"] == 8
