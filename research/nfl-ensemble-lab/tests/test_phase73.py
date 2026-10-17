import pandas as pd
import pytest

from lab import cache73 as C
from lab import scheduler as S


@pytest.fixture()
def cdir(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "DIR", tmp_path)
    monkeypatch.setattr(C, "DISABLED", False)
    return tmp_path


def _rows(seasons, v=1.0):
    return pd.DataFrame([{"game_id": f"{s}_01_A_B", "team": t, "x": v * s} for s in seasons for t in ("A", "B")])


def test_season_cache_reuses_only_unchanged_seasons(cdir):
    data = {2020: "a", 2021: "b", 2022: "c"}
    calls = []

    def compute(need):
        calls.append(sorted(need))
        return _rows(need)
    run = lambda: C.by_season("t", data, lambda s: data[s], compute)
    first = run()
    assert calls == [[2020, 2021, 2022]]
    again = run()
    assert calls[-1] == [2020, 2021, 2022] and len(calls) == 1 and again.equals(first)      # full reuse
    data[2021] = "changed"                                                                   # a historical season changes
    run()
    assert calls[-1] == [2021, 2022]                                                         # it and every later season
    data[2022] = "live update"
    run()
    assert calls[-1] == [2022]                                                               # only the live season


def test_code_or_params_change_invalidates_everything(cdir, monkeypatch):
    calls = []
    compute = lambda need: (calls.append(sorted(need)), _rows(need))[1]
    C.by_season("t", [2020, 2021], str, compute, params="p1")
    C.by_season("t", [2020, 2021], str, compute, params="p2")
    assert calls[-1] == [2020, 2021]
    monkeypatch.setattr(C, "code_hash", lambda: "different-code")
    C.by_season("t", [2020, 2021], str, compute, params="p2")
    assert calls[-1] == [2020, 2021] and len(calls) == 3


def test_corrupt_cache_is_rebuilt_not_trusted(cdir):
    calls = []
    compute = lambda need: (calls.append(sorted(need)), _rows(need))[1]
    C.by_season("t", [2020], str, compute)
    (cdir / "t.parquet").write_bytes(b"not a parquet file")
    out = C.by_season("t", [2020], str, compute)
    assert calls == [[2020], [2020]] and len(out) == 2
    v = C.memo("m", "k", lambda: 41)
    (cdir / "m.joblib").write_bytes(b"garbage")
    assert v == 41 and C.memo("m", "k", lambda: 42) == 42                                   # unreadable memo recomputed
    assert not list(cdir.glob("*.tmp"))                                                      # atomic writes leave no temp files


def test_disabled_cache_recomputes_and_writes_nothing(cdir):
    with C.disabled():
        C.by_season("t", [2020], str, lambda need: _rows(need))
        assert C.memo("m", "k", lambda: 1) == 1
    assert not list(cdir.iterdir())


def test_timeliness_policy():
    k = pd.Timestamp("2026-10-18 17:00", tz="UTC")
    sched = k - pd.Timedelta(minutes=30)
    assert S.timeliness(sched, sched + pd.Timedelta(seconds=40), k) == "on_time"
    assert S.timeliness(sched, sched + pd.Timedelta(minutes=12), k) == "late_valid"
    assert S.timeliness(sched, k + pd.Timedelta(seconds=1), k) == "invalid_after_kickoff"


def test_snapshot_runs_before_full_refresh_and_failures_are_separate():
    order = []
    now = pd.Timestamp("2026-10-18 12:00", tz="UTC")
    due = pd.DataFrame([{"event_id": "daily", "action": "full"}, {"event_id": "stage:g:t60", "action": "snapshot", "game_id": "g"}])

    def full(p):
        order.append("full")
        raise RuntimeError("download timeout")
    res = S.run_actions(due, now, lambda m: None, actions={
        "full": full, "live": lambda p: order.append("live") or {},
        "snapshot": lambda snaps, p, stale=False: order.append("snapshot") or {"by_event": {"stage:g:t60": {"ok": True}}}})
    assert order == ["live", "snapshot", "full"]                       # the forecast never waits for the full refresh
    assert res.get("full_failed") and not res.get("refresh_failed")    # the failed download does not mark the snapshot stale


def test_no_archive_after_kickoff(monkeypatch):
    from lab import prospective as P
    k = pd.Timestamp("2026-10-18 17:00", tz="UTC")
    due = pd.DataFrame([{"event_id": "stage:g1:final:x", "game_id": "g1", "stage": "final", "time_utc": k - pd.Timedelta(minutes=30),
                         "deadline_utc": k - pd.Timedelta(minutes=5), "kickoff_utc": k}])
    fs = pd.DataFrame({"game_id": ["g1"], "season": [2026], "week": [6]})
    monkeypatch.setattr("lab.data_pipeline.load_feature_store", lambda: fs)
    monkeypatch.setattr("lab.data_pipeline.load_status", lambda: {})
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k_: pd.DataFrame({"game_id": ["g1"]}))
    monkeypatch.setattr(P, "build_records", lambda *a, **k_: [{"game_id": "g1", "kickoff_utc": k.isoformat()}])
    monkeypatch.setattr(P, "load_ledger", lambda: pd.DataFrame())
    monkeypatch.setattr(P, "live_context", lambda g: {})
    written = []
    monkeypatch.setattr(P, "write_record", lambda *a, **k_: written.append(1) or ("written", "x"))
    r = P.write_stage_snapshots(due, progress=lambda m: None, now=k + pd.Timedelta(seconds=10))
    assert not written and not r["by_event"]["stage:g1:final:x"]["ok"]
