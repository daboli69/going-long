import json
import os

import numpy as np
import pandas as pd
import pytest

from lab import live
from lab import scheduler as S

ET = "America/New_York"


def et_ts(s):
    return pd.Timestamp(s).tz_localize(ET).tz_convert("UTC")


@pytest.fixture(autouse=True)
def clean_scheduler_state():
    for f in (S.EVENTS, S.TICKS, S.PLAN, S.LOCK, S.SCHED_DIR / "planned.jsonl"):
        f.unlink(missing_ok=True)
    yield


def sched(*games):
    return pd.DataFrame([{"game_id": g, "kickoff_utc": k, "completed": False} for g, k in games])


MOCK = {"full": lambda p: {"mode": "full"}, "live": lambda p: {"mode": "live"},
        "snapshot": lambda snaps, p, stale=False: {"by_event": {e: {"ok": True} for e in snaps["event_id"]}}}


def test_six_daily_times_in_eastern_across_dst():
    for day, utc_hours in (("2026-10-31", [10, 13, 16, 19, 22, 1]), ("2026-11-02", [11, 14, 17, 20, 23, 2]),
                           ("2026-03-09", [10, 13, 16, 19, 22, 1])):
        start = et_ts(f"{day} 00:30")
        p = S.build_plan(sched(), start, start + pd.Timedelta(hours=23))
        d = p[(p["kind"] == "daily") & p["event_id"].str.contains(day)]
        assert list(d["time_utc"].dt.tz_convert(ET).dt.hour) == [6, 9, 12, 15, 18, 21]
        assert list(d["time_utc"].dt.hour) == utc_hours


def test_gameday_half_hour_refreshes():
    k1, k2 = et_ts("2026-11-08 13:00"), et_ts("2026-11-08 20:20")
    p = S.build_plan(sched(("g1", k1), ("g2", k2)), et_ts("2026-11-08 00:00"), et_ts("2026-11-09 00:00"))
    gd = p[p["kind"] == "gameday"]["time_utc"].dt.tz_convert(ET)
    assert gd.min().strftime("%H:%M") == "10:00" and gd.max().strftime("%H:%M") == "20:00"
    assert (gd.diff().dropna() == pd.Timedelta(minutes=30)).all() and len(gd) == 21


@pytest.mark.parametrize("kick,expect", [
    ("2026-11-12 20:15", {"early_week": "Tue 12:00", "friday": None}),          # Thursday night
    ("2026-11-15 09:30", {"early_week": "Tue 12:00", "friday": "Fri 18:00"}),   # London, Sunday morning ET
    ("2026-11-15 13:00", {"early_week": "Tue 12:00", "friday": "Fri 18:00"}),   # Sunday
    ("2026-11-16 20:15", {"early_week": "Tue 12:00", "friday": "Fri 18:00"}),   # Monday night
    ("2026-12-19 16:30", {"early_week": "Tue 12:00", "friday": "Fri 18:00"}),   # Saturday
])
def test_kickoff_relative_stages(kick, expect):
    k = et_ts(kick)
    st = S.stage_times(k)
    fmt = lambda t: t.tz_convert(ET).strftime("%a %H:%M")
    for s, v in expect.items():
        assert (fmt(st[s]) if s in st else None) == v
    assert st["t24h"] == k - pd.Timedelta(hours=24) and st["t3h"] == k - pd.Timedelta(hours=3)
    assert st["t90"] == k - pd.Timedelta(minutes=90) and st["t60"] == k - pd.Timedelta(minutes=60)
    assert st["final"] == k - pd.Timedelta(minutes=30)
    assert all(t < k for t in st.values())
    p = S.build_plan(sched(("gx", k)), k - pd.Timedelta(days=8), k)
    stages = p[p["game_id"] == "gx"].sort_values("time_utc")
    assert (stages["deadline_utc"] <= k - S.KICKOFF_MARGIN).all()
    assert set(stages[stages["action"] == "snapshot"]["stage"]) == set(S.SNAPSHOT_STAGES) & set(st)


def test_tick_runs_due_events_once_and_marks_missed_after_sleep():
    k = et_ts("2026-11-15 13:00")
    s = sched(("g1", k))
    t0 = k - pd.Timedelta(hours=24, minutes=-2)            # just after the t24h stage
    log = S.tick(now=t0, progress=lambda m: None, actions=MOCK, schedule=s)
    assert any("g1:t24h" in e for e in log["due"])
    again = S.tick(now=t0 + pd.Timedelta(minutes=5), progress=lambda m: None, actions=MOCK, schedule=s)
    assert not any("g1:t24h" in e for e in again["due"])           # never runs twice
    wake = k - pd.Timedelta(minutes=40)                           # PC asleep until 40 min before kickoff
    S.tick(now=wake, progress=lambda m: None, actions=MOCK, schedule=s)
    st = S.event_status()
    t90 = [v for e, v in st.items() if e.startswith("stage:g1:t90:")][0]
    assert t90["outcome"] == "missed" and "PC off or asleep" in t90["reason"]
    t60 = [v for e, v in st.items() if e.startswith("stage:g1:t60:")][0]
    assert t60["outcome"] == "done"                               # still inside its window (until the final stage)
    fin = k - pd.Timedelta(minutes=29)
    S.tick(now=fin, progress=lambda m: None, actions=MOCK, schedule=s)
    assert [v for e, v in S.event_status().items() if e.startswith("stage:g1:final:")][0]["outcome"] == "done"
    after = S.tick(now=k + pd.Timedelta(minutes=1), progress=lambda m: None, actions=MOCK, schedule=s)
    assert after["due"] == [] or not any(e.startswith("stage:g1") for e in after["due"])


def test_rescheduled_kickoff_supersedes_old_events():
    k1 = et_ts("2026-11-15 13:00")
    now = k1 - pd.Timedelta(days=3)
    S.tick(now=now, progress=lambda m: None, actions=MOCK, schedule=sched(("g1", k1)))
    k2 = k1 + pd.Timedelta(days=1, hours=7)                       # moved to Monday night
    log = S.tick(now=now + pd.Timedelta(minutes=5), progress=lambda m: None, actions=MOCK, schedule=sched(("g1", k2)))
    assert log["superseded"] >= 5
    sup = [v for v in S.event_status().values() if v["outcome"] == "superseded"]
    assert all(k1.strftime("%Y%m%dT%H%MZ") in v["event_id"] for v in sup)
    plan = json.loads(S.PLAN.read_text())
    assert all(k2.strftime("%Y%m%dT%H%MZ") in e["event_id"] for e in plan if e["kind"] == "stage")


def test_duplicate_runs_are_prevented():
    S.LOCK.write_text(json.dumps({"pid": os.getpid(), "since": pd.Timestamp.now(tz="UTC").isoformat()}))
    assert S.tick(now=pd.Timestamp.now(tz="UTC"), actions=MOCK, schedule=sched()) == {"skipped": "another scheduler run is active"}
    S.LOCK.write_text(json.dumps({"pid": 99999999, "since": pd.Timestamp.now(tz="UTC").isoformat()}))   # dead process
    assert "skipped" not in S.tick(now=pd.Timestamp.now(tz="UTC"), actions=MOCK, schedule=sched())


def test_failed_refresh_marks_events_failed_not_done():
    k = et_ts("2026-11-15 13:00")
    bad = dict(MOCK, live=lambda p: (_ for _ in ()).throw(ConnectionError("offline")))
    # complete the daily refresh first (a successful full refresh would also cover the live sources)
    S.tick(now=k - pd.Timedelta(hours=3, minutes=2), progress=lambda m: None, actions=MOCK, schedule=sched(("g1", k)))
    S.tick(now=k - pd.Timedelta(hours=3) + pd.Timedelta(minutes=1), progress=lambda m: None, actions=bad, schedule=sched(("g1", k)))
    t3 = [v for e, v in S.event_status().items() if e.startswith("stage:g1:t3h:")][0]
    assert t3["outcome"] == "failed"


def test_inactives_and_transactions_parsing():
    assert live.espn_inactives(pd.DataFrame()).empty
    e = pd.DataFrame({"team": ["KC", "KC", "BUF"], "player": ["A", "B", "C"], "position": ["WR", "QB", "CB"],
                      "status": ["Out", "Questionable", "Out"], "updated": [None] * 3,
                      "fantasy": ["INACTIVE", "QUESTIONABLE", None], "detail_type": [None, None, "Coach's Decision"]})
    assert set(live.espn_inactives(e)["player"]) == {"A", "C"}
    assert live.classify_transaction("Activated RB X from injured reserve.") == "activated / returned"
    assert live.classify_transaction("Placed LB Y on injured reserve.") == "IR placement"
    assert live.classify_transaction("Elevated QB Z from the practice squad.") == "practice-squad elevation"


def test_qb_certainty_never_confirms_from_missing_data():
    row = pd.Series({"home_team": "KC", "home_qb_projected_id": None})
    assert live._qb_certainty(row, "home", {}, pd.DataFrame(), {})[0] == "unavailable"
    row = pd.Series({"home_team": "KC", "home_qb_projected_id": "Q1", "home_qb_projected_out": 0, "home_qb_questionable": 0,
                     "home_qb_name": "Pat"})
    lab_, note = live._qb_certainty(row, "home", {"KC": ("Pat", "x")}, pd.DataFrame(), {"Q1": "Pat"})
    assert lab_ == "consistent" and "not a confirmation" in note
    assert live._qb_certainty(row, "home", {"KC": ("Other", "x")}, pd.DataFrame(), {"Q1": "Pat"})[0] == "uncertain"


def test_stage_snapshots_immutable_and_scored_by_stage(trained):
    from lab import prospective as P
    from lab.data_pipeline import load_feature_store
    P.fetch_weather = lambda games: {g: {"status": "test"} for g in games["game_id"]}
    fs = load_feature_store()
    games = fs[(fs["season"] == 2026) & (fs["week"] == 2)]         # completed in the synthetic league
    k = games["kickoff_utc"].min()
    for stage, lead in (("t24h", pd.Timedelta(hours=24)), ("final", pd.Timedelta(minutes=30))):
        due = pd.DataFrame([{"event_id": f"stage:{g}:{stage}:x", "game_id": g, "stage": stage, "time_utc": kk - lead,
                             "kickoff_utc": kk} for g, kk in zip(games["game_id"], games["kickoff_utc"])])
        r = P.write_stage_snapshots(due, progress=lambda m: None, now=k - lead - pd.Timedelta(minutes=1))
        assert all(v["ok"] for v in r["by_event"].values())
        again = P.write_stage_snapshots(due, progress=lambda m: None, now=k - lead)
        assert all(v.get("action") == "already archived for this stage" for v in again["by_event"].values())
    late = pd.DataFrame([{"event_id": "stage:x:t60:x", "game_id": games["game_id"].iloc[0], "stage": "t60",
                          "time_utc": k, "kickoff_utc": k}])
    r = P.write_stage_snapshots(late, progress=lambda m: None, now=k + pd.Timedelta(minutes=1))
    assert not r["by_event"]["stage:x:t60:x"]["ok"]                 # never written after kickoff
    led = P.load_ledger()
    for rel in led["path"]:
        assert not os.access(P.SNAPSHOTS_DIR / rel, os.W_OK)
    out = P.score(progress=lambda m: None)
    assert {"t24h", "final"} <= set(out["by_window"])
    comps = {p["comparison"] for p in out["paired"]}
    assert "t24h vs final (champion)" in comps and any(c.startswith("p_logreg") for c in comps)
