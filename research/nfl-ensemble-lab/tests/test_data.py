import hashlib

import numpy as np
import pandas as pd
import pytest

from lab import ingest, sources


def test_team_normalization_and_aliases():
    assert ingest.normalize_team("oak") == "LV"
    assert ingest.normalize_team("SD") == "LAC"
    assert ingest.normalize_team("STL") == "LA"
    assert ingest.normalize_team("LAR") == "LA"
    with pytest.raises(ValueError):
        ingest.normalize_team("XYZ")


def test_canonical_game_id():
    assert ingest.canonical_game_id(2016, 1, "OAK", "NO") == "2016_01_LV_NO"
    assert ingest.canonical_game_id(2025, 12, "KC", "BUF") == "2025_12_KC_BUF"


def test_no_vig_conversion():
    assert ingest.american_to_prob(-150) == pytest.approx(0.6)
    assert ingest.american_to_prob(150) == pytest.approx(0.4)
    p = ingest.no_vig_home_prob(-150, 130)
    q = ingest.no_vig_home_prob(130, -150)
    assert p + q == pytest.approx(1.0)
    assert 0.5 < p < 0.6
    assert ingest.no_vig_home_prob(-110, -110) == pytest.approx(0.5)
    assert np.isnan(ingest.no_vig_home_prob(np.nan, 120))


def _games_csv(tmp_path, extra_rows=()):
    cols = ("game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,location,"
            "result,total,overtime,old_game_id,gsis,nfl_detail_id,pfr,pff,espn,ftn,away_rest,home_rest,away_moneyline,"
            "home_moneyline,spread_line,away_spread_odds,home_spread_odds,total_line,under_odds,over_odds,div_game,roof,"
            "surface,temp,wind,away_qb_id,home_qb_id,away_qb_name,home_qb_name,away_coach,home_coach,referee,stadium_id,stadium")
    rows = [
        "2016_01_OAK_NO,2016,REG,1,2016-09-11,Sunday,13:00,OAK,35,NO,34,Home,-1,69,0,,,,,,,,7,7,110,-130,2.5,,,50.5,,,0,dome,,,,A,B,QA,QB,,,,,",
        "2016_01_LA_SF,2016,REG,1,2016-09-12,Monday,22:20,LA,0,SF,28,Home,28,28,0,,,,,,,,7,7,-120,100,-2.5,,,44,,,1,outdoors,,,,C,D,QC,QD,,,,,",
        "2016_02_SF_CAR,2016,REG,2,2016-09-18,Sunday,13:00,SF,27,CAR,27,Neutral,0,54,1,,,,,,,,6,7,,,,,,,,,0,outdoors,,,,D,E,QD,QE,,,,,",
        "2016_03_NO_SF,2016,REG,3,2016-09-25,Sunday,16:25,NO,,SF,,Home,,,,,,,,,,,7,7,,,,,,,,,0,outdoors,,,,,,,,,,,,",
        *extra_rows,
    ]
    p = tmp_path / "games.csv"
    p.write_text(cols + "\n" + "\n".join(rows) + "\n")
    return p


def test_load_games_schema_ids_outcomes(tmp_path):
    g, warnings = ingest.load_games(_games_csv(tmp_path), 2016)
    assert set(g["game_id"]) == {"2016_01_LV_NO", "2016_01_LA_SF", "2016_02_SF_CAR", "2016_03_NO_SF"}
    assert any("differ from canonical" in w for w in warnings)  # OAK -> LV
    r = g.set_index("game_id")
    assert r.loc["2016_01_LV_NO", "home_win"] == 0.0
    assert r.loc["2016_01_LA_SF", "home_win"] == 1.0
    assert np.isnan(r.loc["2016_02_SF_CAR", "home_win"]) and r.loc["2016_02_SF_CAR", "tie"]
    assert r.loc["2016_02_SF_CAR", "neutral_site"] == 1
    assert not r.loc["2016_03_NO_SF", "completed"]
    # 13:00 US/Eastern in September is 17:00 UTC
    assert r.loc["2016_01_LV_NO", "kickoff_utc"] == pd.Timestamp("2016-09-11 17:00", tz="UTC")
    assert 0.5 < r.loc["2016_01_LV_NO", "market_p_home_novig"] < 0.6
    assert g["kickoff_utc"].is_monotonic_increasing


def test_duplicate_detection(tmp_path):
    dup = "2016_01_OAK_NO,2016,REG,1,2016-09-11,Sunday,13:00,OAK,35,NO,34,Home,-1,69,0,,,,,,,,7,7,110,-130,2.5,,,50.5,,,0,dome,,,,A,B,QA,QB,,,,,"
    g, warnings = ingest.load_games(_games_csv(tmp_path, [dup]), 2016)
    assert g["game_id"].is_unique
    assert any("duplicate" in w for w in warnings)
    assert len(ingest.find_duplicates(g)) == 0


def _pbp():
    base = dict(game_id="2020_01_KC_BUF", season=2020, week=1, defteam="KC", down=1, third_down_converted=0, third_down_failed=0,
                yardline_100=50, fixed_drive=1, fixed_drive_result="Punt", score_differential=0, qtr=1, passer_player_id=None,
                qb_epa=None, two_point_attempt=0, sack=0, interception=0, fumble_lost=0, pass_touchdown=0, rush_touchdown=0)
    rows = [
        base | dict(play_id=1, posteam="BUF", play_type="pass", epa=0.5, success=1, qb_dropback=1, rush=0, pass_=1, yards_gained=25, game_seconds_remaining=3600, passer_player_id="Q1", qb_epa=0.5),
        base | dict(play_id=2, posteam="BUF", play_type="run", epa=-0.2, success=0, qb_dropback=0, rush=1, pass_=0, yards_gained=2, game_seconds_remaining=3570),
        base | dict(play_id=3, posteam="BUF", play_type="pass", epa=-2.0, success=0, qb_dropback=1, rush=0, pass_=1, yards_gained=0, interception=1, game_seconds_remaining=3540, passer_player_id="Q1", qb_epa=-2.0),
        base | dict(play_id=4, posteam="BUF", play_type="punt", epa=0.1, success=0, qb_dropback=0, rush=0, pass_=0, yards_gained=0, game_seconds_remaining=3530),
        base | dict(play_id=5, posteam="KC", defteam="BUF", play_type="run", epa=0.3, success=1, qb_dropback=0, rush=1, pass_=0, yards_gained=12, game_seconds_remaining=3500, fixed_drive=2, yardline_100=15, fixed_drive_result="Touchdown", rush_touchdown=1),
    ]
    df = pd.DataFrame(rows).rename(columns={"pass_": "pass"})
    return df


def test_team_game_stats_aggregation():
    t = ingest.team_game_stats(_pbp()).set_index("team")
    buf, kc = t.loc["BUF"], t.loc["KC"]
    assert buf["plays"] == 3  # punt excluded
    assert buf["turnovers"] == 1
    assert buf["pass_yds"] == 25 and buf["rush_yds"] == 2
    assert buf["explosive_rate"] == pytest.approx(1 / 3)
    assert buf["sec_per_play"] == pytest.approx(30)
    assert kc["rz_td_rate"] == 1.0 and kc["rush_td"] == 1
    q = ingest.qb_game_stats(_pbp())
    assert q.iloc[0]["qb_dropbacks"] == 2 and q.iloc[0]["qb_epa_sum"] == pytest.approx(-1.5)


def test_download_cache_and_provenance(tmp_path, monkeypatch):
    calls = []
    body = b"PAR1" + b"x" * 100 + b"PAR1"

    def fake_fetch(url, timeout=120, retries=3):
        calls.append(url)
        return body, {"etag": "abc"}
    monkeypatch.setattr(sources, "_fetch", fake_fetch)
    monkeypatch.setattr(sources, "MANIFEST", tmp_path / "manifest.json")
    dest = tmp_path / "pbp.parquet"
    e1 = sources.download("k", "http://x", dest, max_age_hours=None, validate=sources._validate_parquet, progress=lambda m: None)
    e2 = sources.download("k", "http://x", dest, max_age_hours=None, validate=sources._validate_parquet, progress=lambda m: None)
    assert len(calls) == 1 and e2["cached"] and not e1["cached"]
    assert e1["sha256"] == hashlib.sha256(body).hexdigest()
    sources.download("k", "http://x", dest, max_age_hours=None, force=True, progress=lambda m: None)
    assert len(calls) == 2


def test_download_rejects_bad_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "_fetch", lambda url, **k: (b"<html>error</html>", {}))
    monkeypatch.setattr(sources, "MANIFEST", tmp_path / "manifest.json")
    with pytest.raises(ValueError):
        sources.download("k", "http://x", tmp_path / "f.parquet", max_age_hours=None, validate=sources._validate_parquet, progress=lambda m: None)
    assert not (tmp_path / "f.parquet").exists()
