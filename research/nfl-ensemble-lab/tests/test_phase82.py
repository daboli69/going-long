import json

import numpy as np
import pandas as pd

from lab import blindspots82 as B


def test_excess_log_loss_is_zero_for_a_calibrated_forecaster():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.5, 0.9, 200_000)
    y = (rng.random(p.size) < p).astype(float)
    assert abs(np.mean(B._ll(y, p) - B._H(p))) < 0.003            # calibrated -> no excess even though it loses ~30% of games
    y_over = (rng.random(p.size) < p - 0.1).astype(float)          # overconfident forecaster -> positive excess
    assert np.mean(B._ll(y_over, p) - B._H(p)) > 0.02


def test_flags_use_only_pregame_columns():
    x = pd.DataFrame({"week": [1, 5], "p_fav": [0.85, 0.6], "p": [0.85, 0.4], "home_rest_days": [4, 7], "away_rest_days": [7, 7],
                      "ctx_div_game": [1, 0], "ctx_neutral": [0, 0], "margin_ensemble": [12.0, -2.0]})
    assert B._flag(x, "early_weeks_1_4").tolist() == [True, False]
    assert B._flag(x, "fav_over_80").tolist() == [True, False]
    assert B._flag(x, "short_rest").tolist() == [True, False]
    assert B._flag(x, "away_favourite").tolist() == [False, True]
    assert B._flag(x, "predicted_margin_10plus").tolist() == [True, False]


def test_registration_is_written_once(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "OUT", tmp_path)
    a = B.register_prospective()
    (tmp_path / "prospective_hypotheses.json").write_text(json.dumps(a | {"tampered": True}))
    b = B.register_prospective()
    assert b.get("tampered") and len(b["hypotheses"]) == 3 and {h["id"] for h in b["hypotheses"]} == {"P1", "P2", "P3"}


def test_prospective_eval_ignores_games_archived_before_registration(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "OUT", tmp_path)
    reg = pd.Timestamp(B.REGISTERED_AT)
    rows = []
    for i, at in enumerate([reg - pd.Timedelta(days=1), reg + pd.Timedelta(days=1)]):
        rows.append({"game_id": f"g{i}", "stage": "final", "predicted_at": at.isoformat(), "version": "v20261016_212540", "p": 0.7,
                     "home_win": 1.0})
    monkeypatch.setattr("lab.compare7.collect", lambda: pd.DataFrame(rows))
    fs = pd.DataFrame({"week": [2, 2], "home_p72_OL_starters_confirmed_out": [0, 0], "away_p72_OL_starters_confirmed_out": [0, 0],
                       "home_team": ["A", "A"], "away_team": ["B", "B"]}, index=["g0", "g1"])
    monkeypatch.setattr("lab.data_pipeline.load_feature_store", lambda: fs.rename_axis("game_id").reset_index())
    monkeypatch.setattr("lab.market81.espn_archive", lambda: pd.DataFrame())
    out = B.prospective_eval().set_index("id")
    assert out.loc["P1", "games"] == 1                              # only the game archived after registration counts
    assert out.loc["P1", "status"].startswith("accumulating")
