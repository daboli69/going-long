import pandas as pd

from lab.props.ensemble.data import candidates


def test_prior_roster_trade_resolution_and_equal_time_ambiguity():
    games = pd.DataFrame([dict(game_id="g", season=2022, week=3, home_team="SF", away_team="CHI",
        kickoff_utc=pd.Timestamp("2022-10-01", tz="UTC"), ind_margin=0, ind_total=44)])
    roster = pd.DataFrame([dict(season=2022, week=w, team=t, gsis_id="p", status="ACT", position="WR", full_name="P")
                          for w, t in [(1, "SF"), (2, "CHI")]])
    result = candidates(games, roster)
    assert len(result) == 1
    assert result.team.item() == "CHI"
    roster["week"] = 2
    assert candidates(games, roster).empty


def test_mixed_decision_times_and_strict_comparison():
    values = pd.Series(["2026-10-19T20:45:30+00:00", "2026-10-19T20:45:30.664733+00:00"])
    parsed = pd.to_datetime(values, utc=True, format="mixed")
    assert parsed.iloc[0] < parsed.iloc[1]
