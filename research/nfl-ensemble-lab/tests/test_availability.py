import numpy as np
import pandas as pd

from lab import availability as A
from lab import ingest

K = pd.Timestamp("2024-09-08 17:00", tz="UTC")


def _games():
    return pd.DataFrame({
        "game_id": ["2024_01_KC_BUF", "2024_01_NYJ_NE", "2024_02_BUF_KC"],
        "source_game_id": ["2024_01_KC_BUF", "2024_01_NYJ_NE", "2024_02_BUF_KC"],
        "season": [2024, 2024, 2024], "week": [1, 1, 2],
        "kickoff_utc": [K, K - pd.Timedelta(days=3), K + pd.Timedelta(days=7)],
        "home_team": ["BUF", "NE", "KC"], "away_team": ["KC", "NYJ", "BUF"],
    })


def _rows(times, statuses=("Out",), season=2024, source="nflverse date_modified"):
    return pd.DataFrame({"season": season, "week": 1, "team": "BUF", "gsis_id": [f"P{i}" for i in range(len(times))],
                         "full_name": "x", "position": "T", "group": "OL", "report_status": list(statuses) * len(times),
                         "practice_status": None, "available_at": times, "source": source})


def _snaps_and_games():
    g = pd.concat([_games(), pd.DataFrame({"game_id": ["2024_00_A", "2024_00_B"], "source_game_id": ["2024_00_A", "2024_00_B"],
                                           "kickoff_utc": [K - pd.Timedelta(days=30), K - pd.Timedelta(days=20)]})])
    snaps = pd.DataFrame({"game_id": ["2024_00_A", "2024_00_B", "2024_02_BUF_KC"], "gsis_id": ["P0", "P0", "P0"],
                          "role": [1.0, 0.5, 0.0]})
    return snaps, g


def test_rows_after_kickoff_are_dropped():
    rows = _rows([K - pd.Timedelta(hours=40), K + pd.Timedelta(minutes=5)])
    v = A.pregame_injuries(rows, _games())
    assert list(v["gsis_id"]) == ["P0"]


def test_latest_snapshot_before_kickoff_wins():
    early = _rows([K - pd.Timedelta(days=3)], ("Questionable",), source="lab archive A")
    late = _rows([K - pd.Timedelta(hours=20)], ("Out",), source="lab archive B")
    after = _rows([K + pd.Timedelta(hours=1)], ("Questionable",), source="lab archive C")
    v = A.pregame_injuries(pd.concat([early, late, after]), _games())
    assert list(v["report_status"]) == ["Out"] and set(v["source"]) == {"lab archive B"}


def test_coverage_decided_per_kickoff():
    rows = _rows([K - pd.Timedelta(days=2)])
    cov = A.report_coverage(_games(), A.pregame_injuries(rows, _games()), rows).set_index(["game_id", "team"])
    assert cov.loc[("2024_01_KC_BUF", "BUF"), "inj_report_available"] == 1
    assert cov.loc[("2024_01_NYJ_NE", "NE"), "inj_report_available"] == 0   # kicked off before the report existed
    assert cov.loc[("2024_02_BUF_KC", "KC"), "inj_report_available"] == 0   # no week-2 report


def test_role_uses_only_prior_games():
    snaps, g = _snaps_and_games()
    tgt = pd.DataFrame({"gsis_id": ["P0"], "kickoff_utc": [K]})
    assert A.role_asof(snaps, g, tgt).iloc[0] == 0.75   # the later 0.0 game is excluded


def test_team_loads_and_missing_semantics():
    snaps, g = _snaps_and_games()
    games = _games()
    rows = _rows([K - pd.Timedelta(days=2)])
    f = A.team_injury_features(g, A.pregame_injuries(rows, games), snaps, rows)
    f = f[f["game_id"].isin(games["game_id"])].set_index(["game_id", "team"])
    assert f.loc[("2024_01_KC_BUF", "BUF"), "inj_out_OL"] == 0.75        # Out player's prior snap share
    assert f.loc[("2024_01_KC_BUF", "BUF"), "inj_starters_out_OL"] == 1
    assert f.loc[("2024_01_KC_BUF", "KC"), "inj_out_OL"] == 0.0           # healthy team in a final 2024 report
    assert np.isnan(f.loc[("2024_02_BUF_KC", "KC"), "inj_out_OL"])         # no report: missing, not zero
    live = _rows([K - pd.Timedelta(days=2)], (None,), season=2026, source="lab archive X")
    g26 = games.assign(season=2026)
    f26 = A.team_injury_features(g26, A.pregame_injuries(live, g26), snaps, live).set_index(["game_id", "team"])
    assert f26.loc[("2024_01_KC_BUF", "BUF"), "inj_report_available"] == 0  # practice-only snapshot is not final
    assert np.isnan(f26.loc[("2024_01_KC_BUF", "BUF"), "inj_out_OL"])


def test_stadium_roof_types():
    g = pd.DataFrame({"stadium_id": ["ATL97", "ATL97", "NOR00", "BUF00", "BUF00"], "roof": ["closed", "", "dome", "outdoors", ""]})
    assert list(ingest.stadium_roof_types(g)) == ["retractable", "retractable", "dome", "outdoors", "outdoors"]
