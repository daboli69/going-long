import numpy as np
import pandas as pd

from lab.specialists import core as C
from lab.specialists import evaluate as E


def _frame(n_per=60, seasons=range(2016, 2021), seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        for i in range(n_per):
            x = rng.normal()
            rows.append({"game_id": f"{s}_{i:03d}", "season": s, "week": 1 + i % 17, "home_win": float(rng.random() < 1 / (1 + np.exp(-x))),
                         "ctx_home_field": 1.0, "ctx_signal": x, "home_rest_days": 7.0, "away_rest_days": 7.0})
    return pd.DataFrame(rows)


class Recorder(C.Environment):
    key = "D"
    seen = []

    def model(self):
        rec = self.seen

        class M:
            def fit(self, X, y):
                rec.append(len(y))
                return self

            def predict_proba(self, X):
                return np.c_[np.full(len(X), 0.5), np.full(len(X), 0.5)]
        return M()


def test_walk_forward_trains_only_on_earlier_seasons():
    df = _frame()
    spec = Recorder()
    spec.seen.clear()
    out = C.run_specialist(spec, df, targets=[2018, 2019, 2020])
    assert spec.seen == [120, 180, 240]                       # 2 / 3 / 4 earlier seasons x 60 games, never the target season
    assert set(out["season"]) == {2018, 2019, 2020}


def test_forbidden_rating_columns_never_selected():
    df = _frame().assign(diff_rating_margin=1.0, ctx_rating_margin=2.0)
    for spec in (C.Environment(), C.Availability()):
        assert not any(f in c for c in spec.features(df) for f in C.FORBIDDEN)


def test_availability_abstains_without_verified_reports():
    df = pd.DataFrame({"home_p72_report_known": [1, 1, 0, np.nan], "away_p72_report_known": [1, 0, 1, 1]})
    assert C.Availability().abstain(df).tolist() == [False, True, True, True]


def test_drive_simulation_is_deterministic_and_sensible():
    cols = {"home_p8dr_blend_td_rate": 0.30, "away_p8dr_blend_td_rate": 0.18, "home_p8dr_blend_def_td_rate": 0.18,
            "away_p8dr_blend_def_td_rate": 0.28, "home_p8dr_blend_fg_rate": 0.15, "away_p8dr_blend_fg_rate": 0.15,
            "home_p8dr_blend_def_fg_rate": 0.15, "away_p8dr_blend_def_fg_rate": 0.15, "home_p8dr_blend_drives": 11.0, "away_p8dr_blend_drives": 11.0}
    test = pd.DataFrame([{"game_id": "2026_01_A_B", **cols}])
    train = pd.DataFrame([{**{k: 0.22 if "td" in k else (0.15 if "fg" in k else 11.0) for k in cols}, "home_score": 23.0, "away_score": 21.0}] * 50)
    a = C.DriveSim().fit_predict(train, test)
    b = C.DriveSim().fit_predict(train, test)
    assert a.equals(b)
    assert a["raw"].iloc[0] > 0.7 and a["margin"].iloc[0] > 5 and 30 < a["total"].iloc[0] < 70


def test_drive_windows_are_strictly_pregame():
    from lab.advanced import window_features
    games = pd.DataFrame({"game_id": ["g1", "g2", "g3"], "season": 2024, "home_team": "A", "away_team": "B",
                          "kickoff_utc": pd.to_datetime(["2024-09-08", "2024-09-15", "2024-09-22"], utc=True)})
    tg = pd.DataFrame({"game_id": ["g1", "g2", "g3"], "team": "A", "td_rate": [0.2, 0.3, 0.4]})
    a = window_features(games, tg, "x_").set_index(["game_id", "team"])
    tg2 = tg.assign(td_rate=[0.2, 0.3, 0.99])                  # change the LAST game only
    b = window_features(games, tg2, "x_").set_index(["game_id", "team"])
    assert a.loc[("g3", "A"), "x_blend_td_rate"] == b.loc[("g3", "A"), "x_blend_td_rate"]   # g3 never sees its own result
    assert np.isnan(a.loc[("g1", "A"), "x_blend_td_rate"])


def test_combination_uses_only_earlier_seasons():
    rng = np.random.default_rng(1)
    rows = []
    for s in range(2018, 2023):
        for i in range(250):
            p = rng.uniform(0.2, 0.8)
            rows.append({"game_id": f"{s}_{i}", "season": s, "home_win": float(rng.random() < p), "p_weighted_average": p, "p_X": 0.5})
    g = pd.DataFrame(rows)
    a = E.combo_predictions(g, ["X"], 1.0)
    g2 = g.copy()
    g2.loc[g2["season"] == 2022, "home_win"] = 1.0            # future outcomes must not change earlier predictions
    b = E.combo_predictions(g2, ["X"], 1.0)
    early = g["season"] < 2022
    assert np.allclose(a[early].dropna(), b[early].dropna()) and a[g["season"] == 2018].isna().all()
