"""First touchdown allowed by position: the first-given-up rule, the game-first option, week filtering and percentage arithmetic. Synthetic rows."""
import pandas as pd
import pytest

from lab import first_td_allowed as F


@pytest.fixture
def tables(tmp_path, monkeypatch):
    # game g1 (wk1): CHI at GB. GB scores first (TE), then CHI (WR). game g2 (wk2): CHI at DET. DET scores first (RB), CHI never scores.
    td = pd.DataFrame([
        {"game_id": "g1", "week": 1, "scoring_team": "GB", "def_team": "CHI", "scorer": "a", "pos": "TE", "game_first": True, "qtr": 1, "season": 2026},
        {"game_id": "g1", "week": 1, "scoring_team": "CHI", "def_team": "GB", "scorer": "b", "pos": "WR", "game_first": False, "qtr": 2, "season": 2026},
        {"game_id": "g2", "week": 2, "scoring_team": "DET", "def_team": "CHI", "scorer": "c", "pos": "RB", "game_first": True, "qtr": 3, "season": 2026}])
    games = pd.DataFrame([{"game_id": "g1", "week": 1, "team": "CHI", "season": 2026}, {"game_id": "g1", "week": 1, "team": "GB", "season": 2026},
                          {"game_id": "g2", "week": 2, "team": "CHI", "season": 2026}, {"game_id": "g2", "week": 2, "team": "DET", "season": 2026}])
    monkeypatch.setattr(F, "CACHE", tmp_path)
    games.to_parquet(tmp_path / "2026_games.parquet")
    monkeypatch.setattr(F, "build_season", lambda s: td)


def row(t, team):
    return next(r for r in t["rows"] if r["team"] == team)


def test_every_game_charges_the_first_touchdown_to_the_defense_that_gave_it_up(tables):
    t = F.table(2026, None, False)
    chi = row(t, "CHI")
    assert chi["games"] == 2 and chi["tds"] == 2 and chi["counts"]["TE"] == 1 and chi["counts"]["RB"] == 1
    assert chi["pct"]["TE"] == pytest.approx(0.5) and chi["pct"]["WR"] == pytest.approx(0.0)
    assert row(t, "GB")["counts"]["WR"] == 1 and row(t, "GB")["tds"] == 1


def test_the_game_first_option_keeps_one_touchdown_per_game(tables):
    t = F.table(2026, None, True)
    assert t["league"]["tds"] == 2 and row(t, "GB")["tds"] == 0 and row(t, "GB")["pct"]["WR"] is None      # no touchdown counted, so no share
    assert row(t, "CHI")["counts"]["TE"] == 1


def test_selecting_weeks_recomputes_counts_and_shares(tables):
    t = F.table(2026, [2], False)
    assert t["weeks"] == [2] and row(t, "CHI")["games"] == 1 and row(t, "CHI")["pct"]["RB"] == pytest.approx(1.0)
    both = F.table(2026, [1, 2], False)
    assert both["league"]["tds"] == 3 and sum(both["league"]["counts"].values()) == 3
