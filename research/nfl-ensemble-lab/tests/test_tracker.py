import json

import pandas as pd
import pytest

from lab import tracker as T


def snap(game, p, pn, ml_h, ml_a, at="2026-11-01T12:00:00+00:00", kick="2026-11-01T18:00:00+00:00"):
    return {"game_id": game, "week": 9, "window": "final", "predicted_at": at, "kickoff_utc": kick,
            "_body": {"p_champion": p, "stale_data": False,
                      "market_at_snapshot": {"p_home_novig": pn, "home_moneyline": ml_h, "away_moneyline": ml_a, "spread_line": 3.0}}}


@pytest.fixture
def lab(tmp_path, monkeypatch):
    sdir = tmp_path / "snapshots"
    (sdir / "prospective").mkdir(parents=True)
    raw = tmp_path / "raw"
    raw.mkdir()
    ledger = sdir / "prospective" / "ledger.jsonl"
    entries = [snap("2026_09_A_B", 0.70, 0.55, -120, 100),     # edge 0.15 home, qualifies
               snap("2026_09_C_D", 0.52, 0.50, -110, -110),    # edge 0.02, does not qualify
               snap("2026_09_E_F", 0.30, 0.50, -150, 130),     # edge 0.20 away at +130
               snap("2026_09_G_H", 0.60, 0.40, -150, 130, at="2026-11-01T19:00:00+00:00")]  # after kickoff, ignored
    lines = []
    for e in entries:
        path = f"prospective/{e['game_id']}.json"
        (sdir / path).write_text(json.dumps(e.pop("_body")), encoding="utf-8")
        e["path"] = path
        lines.append(json.dumps(e))
    ledger.write_text("\n".join(lines), encoding="utf-8")
    pd.DataFrame({"game_id": ["2026_09_A_B", "2026_09_C_D", "2026_09_E_F", "2026_09_G_H"], "season": 2026,
                  "home_team": list("ACEG"), "away_team": list("BDFH"), "home_score": [20, 10, 17, 30],
                  "away_score": [10, 10, 24, 3], "gameday": "2026-11-01", "gametime": "13:00"}).to_csv(raw / "games.csv", index=False)
    monkeypatch.setattr(T, "SNAPSHOTS_DIR", sdir)
    monkeypatch.setattr(T, "LEDGER", ledger)
    monkeypatch.setattr(T, "RAW_DIR", raw)
    monkeypatch.setattr(T, "TRACK_DIR", tmp_path / "t")
    monkeypatch.setattr(T, "EVAL_CSV", tmp_path / "t" / "evaluations.csv")
    monkeypatch.setattr(T, "SETTLE_CSV", tmp_path / "t" / "settlements.csv")
    return tmp_path


def test_units():
    assert T.units_for(-120, "win") == pytest.approx(100 / 120)
    assert T.units_for(130, "win") == pytest.approx(1.3)
    assert T.units_for(-120, "loss") == -1.0
    assert T.units_for(150, "push") == 0.0


def test_select_is_idempotent_and_ignores_post_kickoff(lab):
    first = T.select("backfill")
    assert {r["game_id"] for r in first} == {"2026_09_A_B", "2026_09_C_D", "2026_09_E_F"}
    assert T.select() == []
    assert [r["qualified"] for r in first] == ["1", "0", "1"]


def test_settle_and_performance(lab):
    T.select()
    T.settle()
    assert T.settle() == []
    perf = T.performance()
    assert perf["qualified"] == 2 and perf["settled"] == 2
    # A_B home wins at -120 (+0.8333); E_F bets away at +130 and wins (+1.3)
    assert perf["units"] == pytest.approx(100 / 120 + 1.3, abs=1e-3)
    assert perf["wins"] == 2 and perf["max_drawdown_units"] == 0.0


def test_losing_streak_drawdown(lab):
    T.select()
    ev = pd.read_csv(T.EVAL_CSV, dtype=str, keep_default_na=False)
    rows = [{"game_id": g, "rule_id": T.RULE_ID, "settled_at": "x", "home_score": 0, "away_score": 0,
             "outcome": "loss", "units": -1.0} for g in ev.loc[ev.qualified == "1", "game_id"]]
    T._append(T.SETTLE_CSV, T.SETTLE_COLS, rows)
    assert T.performance()["max_drawdown_units"] == pytest.approx(-2.0)


def test_tampering_breaks_the_chain(lab):
    T.select()
    assert not [p for p in T.verify() if "chain" in p]
    text = T.EVAL_CSV.read_text(encoding="utf-8").replace("-120", "-110", 1)
    T.EVAL_CSV.write_text(text, encoding="utf-8")
    assert any("chain" in p for p in T.verify())


def test_performance_counts_live_rows_only_by_default(lab):
    T.select("backfill")
    T.settle()
    assert T.performance()["settled"] == 0 and T.performance()["units"] == 0.0
    assert T.performance(origin="backfill")["settled"] == 2
    assert T.performance(origin=None)["settled"] == 2


def test_bettable_price_needs_a_fresh_named_book_quote():
    import pandas as pd
    k, t = "2026-11-08T18:00:00+00:00", "2026-11-08T17:00:00+00:00"
    q = pd.DataFrame({"market": "h2h", "home": "B", "away": "A", "side": "home", "book": ["x", "y", "z"],
                      "price": [-120, -110, 150], "commence_time": pd.Timestamp(k),
                      "quote_time": pd.to_datetime(["2026-11-08T16:50Z", "2026-11-08T16:45Z", "2026-11-08T16:00Z"])})
    b = T.best_book_price(q, "2026_09_A_B", "home", t, k)
    assert b["book"] == "y" and b["american_odds"] == -110  # z is better but 60 minutes old
    assert T.best_book_price(q, "2026_09_A_B", "away", t, k) is None
    done = pd.DataFrame([{"game_id": "2026_09_A_B", "side": "home", "snapshot_at": t, "kickoff_utc": k, "outcome": "win"},
                         {"game_id": "2026_09_C_D", "side": "home", "snapshot_at": t, "kickoff_utc": k, "outcome": "win"}])
    r = T.bettable(done, q)
    assert r["priced_bets"] == 1 and r["unpriced_bets"] == 1 and r["units"] == pytest.approx(100 / 110)
