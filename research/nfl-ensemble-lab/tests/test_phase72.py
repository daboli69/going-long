import pandas as pd

from lab import extra_sources as X
from lab import lineup72 as L
from lab import recover72 as R


def _valid(season, n_played, n, status="Questionable", practice="Limited Participation in Practice"):
    return pd.DataFrame({"season": season, "game_id": [f"{season}_g{i}" for i in range(n)], "team": "AAA",
                         "gsis_id": [f"p{i}" for i in range(n)], "report_status": status, "practice_status": practice}), \
        pd.DataFrame({"game_id": [f"{season}_g{i}" for i in range(n)], "gsis_id": [f"p{i}" for i in range(n)],
                      "played": [i < n_played for i in range(n)]})


def test_availability_rates_are_as_of():
    v17, p17 = _valid(2017, 80, 100)
    v18, p18 = _valid(2018, 0, 100)                     # 2018 outcomes must not affect 2018's own rates
    valid, played = pd.concat([v17, v18]), pd.concat([p17, p18])
    r18 = L.availability_rates(valid, played, 2018)
    r19 = L.availability_rates(valid, played, 2019)
    assert abs(r18["Questionable|limited"] - (80 + 2.5) / 105) < 1e-9
    assert r19["Questionable|limited"] < r18["Questionable|limited"]
    assert L.availability_rates(valid, played, 2017) == {}          # no history -> deterministic rule is used
    assert L._deterministic("Out|dnp") == 0 and L._deterministic("Doubtful|limited") == 0 and L._deterministic("Questionable|full") == 1


def test_status_key_practice_parsing():
    assert L._status_key("Out", "Did Not Participate In Practice") == "Out|dnp"
    assert L._status_key(None, "Full Participation in Practice") == "listed_no_status|full"
    assert L._status_key("Questionable", None) == "Questionable|none"


def test_recovered_coverage_requires_capture_before_kickoff():
    games = pd.DataFrame({"game_id": ["2025_03_A_B", "2025_04_C_D"], "season": 2025, "week": [3, 4],
                          "kickoff_utc": pd.to_datetime(["2025-09-21 17:00", "2025-09-28 17:00"], utc=True)})
    rec = pd.DataFrame({"season": 2025, "week": [3, 4], "team": "A", "full_name": "x", "report_status": ["Out", "Out"],
                        "available_at": pd.to_datetime(["2025-09-19 23:45", "2025-09-28 18:00"], utc=True), "source": ["cap1", "cap2"]})
    c = R.coverage(rec, games).set_index("game_id")
    assert c.loc["2025_03_A_B", "recovered_before_kickoff"] and c.loc["2025_03_A_B", "hours_before_kickoff"] > 0
    assert not c.loc["2025_04_C_D", "recovered_before_kickoff"]                # captured after kickoff: never used


def test_parse_nflcom_tolerates_2025_whitespace():
    html_ = ('<h1>Week 3 of the 2025 Season</h1><div class="d3-o-section-sub-title"> <span>Dolphins</span> </div>'
             '<table><thead> <tr> <th>Player</th> </tr> </thead><tbody> <tr> <td scope="row"> <a> Ethan Bonner </a> </td> '
             '<td> CB </td> <td> Knee </td> <td> Limited Participation in Practice </td> <td> Questionable </td> </tr></tbody></table>')
    rep, season, week = X.parse_nflcom(html_)
    assert (season, week) == (2025, 3) and rep.iloc[0][["team", "full_name", "report_status"]].tolist() == ["MIA", "Ethan Bonner", "Questionable"]


def test_status_changes_and_source_lag(tmp_path, monkeypatch):
    monkeypatch.setattr(X, "ARCHIVE", tmp_path)
    import lab.availability as A
    monkeypatch.setattr(A, "ARCHIVE_DIR", tmp_path / "none")
    for ts, st in (("20261016T200000Z", None), ("20261017T140000Z", "Out")):
        pd.DataFrame({"season": [2026], "week": [6], "team": ["PHI"], "full_name": ["Jalen Hurts"], "position": ["QB"],
                      "report_status": [st], "practice_status": ["Did Not Participate In Practice"]}).to_parquet(
            tmp_path / f"nflcom_injuries_{ts}_abc{ts[-3:]}.parquet")
    ch = X.status_changes(2026, 6)
    assert len(ch) == 1 and ch.iloc[0]["to"].startswith("Out")
    lag = X.source_lag(2026, 6, min_statuses=1)
    assert lag["first_with_statuses"].iloc[0] == pd.Timestamp("2026-10-17 14:00", tz="UTC")
