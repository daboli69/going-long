import numpy as np
import pandas as pd

from lab import compare7 as C
from lab import transparency as T

NAMES = {"B": "Tyson Bagent", "W": "Caleb Williams", "P": "Michael Penix Jr."}


def _row():
    return pd.Series({"game_id": "2026_06_CHI_ATL", "season": 2026, "week": 6, "home_team": "ATL", "away_team": "CHI",
                      "home_qb_projected_id": "P", "away_qb_projected_id": "B", "home_qb7_projected_id": "P", "away_qb7_projected_id": "W",
                      "away_qb7_returning": 1, "home_inj_report_available": 1, "away_inj_report_available": 0,
                      "home_inj_report_time": pd.Timestamp("2026-10-17 13:00", tz="UTC"), "f1": 1.0, "f2": np.nan})


def test_version_inputs_reports_each_versions_own_qb():
    r = _row()
    champ = T.version_inputs(r, ["f1", "f2", "diff_qb_eff"])
    chal = T.version_inputs(r, ["f1", "diff_qb7_eff"])
    assert champ["away_qb_id"] == "B" and champ["qb_rule"].startswith("v1")
    assert chal["away_qb_id"] == "W" and chal["away_qb_returning"] == 1 and chal["qb_rule"].startswith("v2")
    assert champ["features_missing"] == 2 and "f2" in champ["features_missing_names"]      # f2 NaN, diff_qb_eff absent
    assert champ["away_injury_report"].startswith("none verified") and champ["home_injury_report"] == "verified pregame report"


def _sleeper(qb1):
    return pd.DataFrame({"team": ["CHI", "CHI"], "position": "QB", "full_name": [qb1, "Other"], "depth_chart_order": [1, 2]})


def test_live_qb_agreement_ignores_champion_rule_and_name_suffixes():
    r = _row()
    lv = T.live_qb("CHI", 2026, 6, r, "away", NAMES, {"_week": 6}, _sleeper("Caleb Williams"), pd.DataFrame())
    assert lv["live_qb"] == "Caleb Williams" and lv["status"] == "projected (sources agree)"
    assert "QB conflict" not in (T.conflict_warning(r, "away", lv, NAMES) or "QB conflict") and "assumes Tyson Bagent" in T.conflict_warning(r, "away", lv, NAMES)
    lh = T.live_qb("ATL", 2026, 6, r, "home", NAMES, {"_week": 6},
                   pd.DataFrame({"team": ["ATL"], "position": "QB", "full_name": ["Michael Penix"], "depth_chart_order": [1]}), pd.DataFrame())
    assert lh["status"] == "projected (sources agree)" and T.conflict_warning(r, "home", lh, NAMES) is None


def test_live_qb_official_out_and_week_scope():
    r = _row()
    off = {("CHI", "Caleb Williams"): "Out", ("CHI", "Somebody Else"): "Out", "_week": 6}
    lv = T.live_qb("CHI", 2026, 6, r, "away", NAMES, off, _sleeper("Caleb Williams"), pd.DataFrame())
    assert lv["status"] == "unavailable" and lv["official_out_or_doubtful"] == ["Caleb Williams"]      # non-QBs not listed
    lv7 = T.live_qb("CHI", 2026, 7, r, "away", NAMES, off, _sleeper("Caleb Williams"), pd.DataFrame())
    assert lv7["live_qb"] == "Caleb Williams"                                                            # week-6 report not applied to week 7
    lc = T.live_qb("CHI", 2026, 6, r, "away", NAMES, {"_week": 6}, _sleeper("Tyson Bagent"), pd.DataFrame())
    assert lc["status"] == "conflicting"                                                                 # Sleeper vs v2 disagree


def _df(n_games, stage="final"):
    rng = np.random.default_rng(0)
    rows = []
    for i in range(n_games):
        y = float(rng.random() < 0.55)
        for v, shift in (("v20261016_212540", 0.0), ("v20261017_142546_p7_qb_snap", 0.05)):
            for st, t in (("friday", "2026-10-16"), (stage, "2026-10-18")):
                p = float(np.clip(0.55 + (shift if st == stage else 0) * (1 if y else -1), 0.05, 0.95))
                rows.append({"game_id": f"g{i}", "stage": st, "predicted_at": t, "version": v, "p": p, "pred_margin": 3.0,
                             "margin": 7.0 if y else -3.0, "home_win": y, "home_qb": "A", "away_qb": "B",
                             "actual_home_qb": "A", "actual_away_qb": "B" if i % 2 else "X", "injury_complete": i % 4 != 0})
    return pd.DataFrame(rows)


def test_compare_identical_games_and_no_conclusion_below_128():
    d = _df(20)
    d = d[~((d["game_id"] == "g0") & (d["version"] == "v20261017_142546_p7_qb_snap"))]      # challenger missing one game
    c = C.compare(d, "final", n_boot=200)
    assert c["games"] == 19                                                                 # identical games only
    by = c["by_version"].set_index("label")
    assert by.loc["Phase 7 QB + snap", "log_loss"] < by.loc["Champion", "log_loss"]
    assert np.isclose(by.loc["Champion", "margin_mae"], d[d.game_id != "g0"].groupby("game_id").margin.first().sub(3).abs().mean())
    assert 0 < by.loc["Champion", "qb_projection_correct"] < 1
    pr = c["paired"].iloc[0]
    assert pr["games"] == 19 and pr["status"] == "accumulating evidence" and pr["ci95_low"] <= pr["delta_log_loss_vs_champion"] <= pr["ci95_high"]
    sc = C.stage_changes(d).set_index("version")
    assert sc.loc["v20261017_142546_p7_qb_snap", "log_loss_last"] < sc.loc["v20261017_142546_p7_qb_snap", "log_loss_first"]


def test_compare_empty():
    assert C.compare(pd.DataFrame())["games"] == 0
