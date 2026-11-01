"""Fantasy points allowed, converted to stats: lagged, shrunk toward the league, neutral without history. Synthetic inputs only."""
import pandas as pd
import pytest

from lab import allowed_usage as A


def _table():
    rows = []
    for w in (1, 2, 3):
        rows += [(2026, w, "AAA", "WR", 300.0, 80.0), (2026, w, "BBB", "WR", 200.0, 60.0)]
    return pd.DataFrame(rows, columns=["season", "week", "team", "pos", "receiving__yds", "fp__fp"])


def test_gap_is_relative_to_the_league_and_pulled_toward_it_for_short_records():
    g = A.Allowed(_table()).gaps(2026, 4)
    full = 250.0 / 250.0
    assert g.loc[("AAA", "WR"), "receiving__yds"] == pytest.approx((300 / 250 - 1) * 3 / (3 + A.K_SHRINK))
    assert g.loc[("BBB", "WR"), "receiving__yds"] < 0 < g.loc[("AAA", "WR"), "receiving__yds"] and full == 1.0


def test_only_earlier_weeks_count_and_two_are_needed():
    a = A.Allowed(_table())
    assert a.gaps(2026, 2).empty          # one earlier week
    assert len(a.gaps(2026, 3)) == 2      # weeks 1 and 2


def test_unknown_opponent_position_or_column_gives_no_adjustment():
    a, opp = A.Allowed(_table()), {(2026, 4, "XXX"): "AAA"}
    assert A.gap(a, opp, 2026, 4, "XXX", "WR", "receiving__yds") > 0
    assert A.gap(a, opp, 2026, 4, "XXX", "TE", "receiving__yds") == 0.0
    assert A.gap(a, opp, 2026, 4, "YYY", "WR", "receiving__yds") == 0.0
    assert A.gap(a, opp, 2026, 4, "XXX", "WR", "nope") == 0.0
