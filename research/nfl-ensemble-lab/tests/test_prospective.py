import json
import os

import numpy as np
import pandas as pd
import pytest

from lab import features, geo
from lab import prospective as P


def test_cutoff_windows():
    assert P.window_for(0.05) is None            # 3 minutes before kickoff: too late
    assert P.window_for(2) == "final"
    assert P.window_for(30) == "final"
    assert P.window_for(31) == "early"
    assert P.window_for(8 * 24) == "early"
    assert P.window_for(8 * 24 + 1) is None
    assert P.window_for(-1) is None


@pytest.fixture(scope="module")
def sched(trained):
    """Simulated scheduled runs on the synthetic league (no network)."""
    from lab.data_pipeline import load_feature_store
    P.fetch_weather = lambda games: {g: {"status": "test"} for g in games["game_id"]}
    fs = load_feature_store()
    wk3 = fs[(fs["season"] == 2026) & (fs["week"] == 3)]
    now = wk3["kickoff_utc"].min() - pd.Timedelta(hours=20)       # week 3 in final window, week 4 early
    first = P.run_scheduled(refresh=False, now=now, progress=lambda m: None)
    second = P.run_scheduled(refresh=False, now=now + pd.Timedelta(hours=1), progress=lambda m: None)
    return {"now": now, "first": first, "second": second, "fs": fs}


def test_snapshots_written_once_and_read_only(sched):
    assert sched["first"]["written"] > 0 and not sched["first"]["errors"]
    assert sched["second"]["written"] == 0 and sched["second"]["skipped"] == sched["first"]["written"]
    led = P.load_ledger()
    assert set(led["window"]) == {"early", "final"}
    assert (led["predicted_at"] < led["kickoff_utc"]).all()
    for rel in led["path"]:
        f = P.SNAPSHOTS_DIR / rel
        assert not os.access(f, os.W_OK)
    snap = json.loads((P.SNAPSHOTS_DIR / led["path"].iloc[0]).read_text())
    for k in ("p_home", "p_champion", "margin_ensemble", "experimental", "availability", "missing", "feature_snapshot",
              "data_cutoff", "provenance", "model_version", "market_at_snapshot", "kickoff_utc", "predicted_at"):
        assert k in snap
    assert len(snap["p_home"]) == 6


def test_refuses_after_kickoff(sched):
    led = P.load_ledger()
    rel = led["path"].iloc[0]
    rec = json.loads((P.SNAPSHOTS_DIR / rel).read_text())
    late = pd.Timestamp(rec["kickoff_utc"]) + pd.Timedelta(minutes=1)
    action, path = P.write_record({**rec, "p_champion": 0.123}, "final", late, led)
    assert action.startswith("refused") and path is None


def test_scoring_attaches_results_without_editing_snapshots(sched):
    led = P.load_ledger()
    before = {rel: (P.SNAPSHOTS_DIR / rel).read_bytes() for rel in led["path"]}
    out = P.score(progress=lambda m: None)
    assert out["overall"]["games_scored"] > 0          # synthetic week-3/4 games are already completed
    t = P.scored_table()
    assert (t["predicted_at"] < t["kickoff_utc"]).all()
    assert {"final", "early"} <= set(out["by_window"])
    for rel, b in before.items():
        assert (P.SNAPSHOTS_DIR / rel).read_bytes() == b


def test_missing_report_explains_gaps(sched):
    later = sched["now"] + pd.Timedelta(days=12)
    mr = P.missing_report(now=later)
    assert (mr["status"] == "archived").any()
    assert mr["status"].str.startswith("MISSED: no scheduled run").any()   # PC 'off' after the simulated runs


def test_geo_distance_and_timezones():
    assert abs(geo.km("SEA00", "NYC01") - 3855) < 20
    assert geo.km("XXX", "NYC01") != geo.km("XXX", "NYC01")                  # NaN for unknown sites
    t = pd.Timestamp("2026-10-18 17:00", tz="UTC")
    assert geo.local_hour("SEA00", t) == 10.0 and geo.utc_offset_hours("NYC01", t) == -4.0
    assert geo.site_key("JAX00", "Tottenham Hotspur Stadium") == "LON02"


def test_coach_and_travel_context_use_only_prior_games():
    k = pd.Timestamp("2024-09-08 17:00", tz="UTC")
    g = pd.DataFrame({"game_id": ["a", "b", "c", "d"], "season": [2023, 2024, 2024, 2024], "week": [18, 1, 2, 3],
                      "kickoff_utc": [k - pd.Timedelta(days=240), k, k + pd.Timedelta(days=7), k + pd.Timedelta(days=14)],
                      "home_team": ["SEA", "SEA", "NYG", "SEA"], "away_team": ["NYG", "NYG", "SEA", "NYG"],
                      "neutral_site": 0, "stadium_id": ["SEA00", "SEA00", "NYC01", "SEA00"], "stadium": "",
                      "home_coach": ["Old", "New", "B", "New"], "away_coach": ["B", "B", "New", "B"]})
    t = features.travel_coach_context(g).set_index(["game_id", "team"])
    assert t.loc[("b", "SEA"), "coach_new_this_season"] == 1
    assert t.loc[("b", "SEA"), "coach_log_tenure"] == 0                    # first game for the new coach
    assert t.loc[("d", "SEA"), "coach_log_tenure"] == np.log1p(2)
    assert abs(t.loc[("c", "SEA"), "travel_km"] - 3855) < 20 and t.loc[("b", "SEA"), "travel_km"] < 0.01
    assert t.loc[("c", "SEA"), "tz_shift"] == 3.0
