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


# --------------------------------------------------------------------------- the Inbox drop and the adjustments
import numpy as np


def _csv(tmp_path, name, pos, rows):
    head1 = "TEAM DETAILS,TEAM DETAILS,TEAM DETAILS,TEAM DETAILS,Splits,Splits,Splits,RECEIVING,RECEIVING,RECEIVING,RUSHING,RUSHING,FP"
    head2 = "Rank,Name,POS,G,WEEK,OPP,FP %,TGT,REC,YDS,ATT,YDS,FP"
    lines = [head1, head2, ",,,,,,,5,4,50,1,3,20"]
    lines += [f"{i + 1},{t},vs. {pos},1,{w},XXX,10,{tg},{rc},{yd},1,{ry},{fp}" for i, (t, w, tg, rc, yd, ry, fp) in enumerate(rows)]
    lines.append("Exported from Data Suite 2.0 by someone on 2026-11-01,,,,,,,,,,,,")
    (tmp_path / name).write_text("\n".join(lines), encoding="utf-8")


def test_inbox_file_is_read_with_its_two_header_rows_and_footer(tmp_path):
    _csv(tmp_path, "fantasy-points-allowed-wr.csv", "WR", [("BLT", 3, 20, 12, 150, 4, 40.0), ("KC", 3, 18, 10, 120, 0, 30.0)])
    df = A._parse_inbox_file(tmp_path / "fantasy-points-allowed-wr.csv")
    assert list(df["team"]) == ["BAL", "KC"] and set(df["pos"]) == {"WR"} and set(df["week"]) == {3}
    assert df.loc[df["team"] == "BAL", "receiving__yds"].item() == 150 and df.loc[df["team"] == "BAL", "rushing__yds"].item() == 4


def test_the_fullest_wide_receiver_export_wins_and_the_newest_week_folder_is_used(tmp_path, monkeypatch):
    for n in (6, 7):
        (tmp_path / "Inbox" / f"Week {n}").mkdir(parents=True)
    _csv(tmp_path / "Inbox" / "Week 7", "fantasy-points-allowed-wr.csv", "WR", [("KC", 5, 20, 12, 150, 0, 60.0)])
    _csv(tmp_path / "Inbox" / "Week 7", "fantasy-points-allowed-wr (1).csv", "WR", [("KC", 5, 9, 5, 60, 0, 25.0)])
    _csv(tmp_path / "Inbox" / "Week 6", "fantasy-points-allowed-wr.csv", "WR", [("KC", 4, 20, 12, 999, 0, 99.0)])
    monkeypatch.setenv("GOING_FP_ROOT", str(tmp_path))
    df = A.inbox_weekly()
    assert len(df) == 1 and df["receiving__yds"].item() == 150 and df["week"].item() == 5   # not the slice, not the older folder


def _mults():
    return {"rec_yds": {"WR": {"factor": 1.10, "gap": 0.2}, "TE": {"factor": 0.90, "gap": -0.2}}, "rec": {"WR": {"factor": 1.05, "gap": 0.1}}}


def test_multipliers_use_the_rule_weights_stay_in_range_and_need_the_rule_to_be_applied():
    a = A.Allowed(_table())
    rule = {"applied": True, "weights": {"rec_yds": {"WR": 5.0}}}
    m = A.multipliers("AAA", 2026, 4, rule, a)
    assert m["rec_yds"]["WR"]["factor"] == A.MULT_CLIP[1]            # a huge weight is held at the cap
    assert A.multipliers("AAA", 2026, 4, {**rule, "applied": False}, a) == {}
    assert A.multipliers("AAA", 2026, 4, {"applied": True, "weights": {}}, a) == {}
    assert A.multipliers("ZZZ", 2026, 4, rule, a) == {}               # unknown defense


def test_rows_are_scaled_by_position_and_the_quarterback_follows_the_receiving_yards_factor():
    rows = [{"player": "W", "stat": "Receiving yards", "typical": 100.0, "expected": 100.0, "range_low": 80.0, "range_high": 130.0},
            {"player": "T", "stat": "Receiving yards", "typical": 50.0, "expected": 50.0},
            {"player": "Q", "stat": "Passing yards", "typical": 250.0}]
    f = A.apply_to_rows(rows, {"W": "WR", "T": "TE"}, _mults())
    assert rows[0]["typical"] == pytest.approx(110.0) and rows[0]["range_high"] == pytest.approx(143.0) and rows[1]["typical"] == pytest.approx(45.0)
    assert f["rec_yds"] == pytest.approx((110 + 45) / 150) and rows[2]["typical"] == 250.0   # the caller moves the quarterback
    assert A.apply_to_rows([{"player": "W", "stat": "Receiving yards", "typical": 10.0}], {"W": "WR"}, {})["rec_yds"] == 1.0


def test_sampled_games_scale_yards_and_catches_without_breaking_targets():
    rng = np.random.default_rng(4)
    p = {"group": "WR", "tgt": 12, "rec": 6, "yards": [10, 12, 8, 20, 5, 15]}
    A.apply_to_sampled([p], {"rec_yds": {"WR": {"factor": 1.1}}, "rec": {"WR": {"factor": 1.0}}}, rng)
    assert p["yards"] == [11, 13, 9, 22, 6, 16] and p["rec"] == 6
    more = {"group": "WR", "tgt": 12, "rec": 6, "yards": [10] * 6}
    A.apply_to_sampled([more], {"rec": {"WR": {"factor": 1.25}}}, np.random.default_rng(1))
    assert 6 <= more["rec"] <= 12 and more["rec"] == len(more["yards"])
    fewer = {"group": "WR", "tgt": 12, "rec": 6, "yards": [10] * 6}
    A.apply_to_sampled([fewer], {"rec": {"WR": {"factor": 0.8}}}, np.random.default_rng(1))
    assert 0 <= fewer["rec"] <= 6 and fewer["rec"] == len(fewer["yards"])
