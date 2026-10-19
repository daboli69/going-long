import numpy as np
import pandas as pd
import pytest

from lab.props.projections10 import probability_summary, price_gap, matching_lines


def test_real_line_probability_pushes_are_separate():
    p = probability_summary([0, 1, 2, 3], 1)
    assert p == {"p_over": .5, "p_under": .25, "p_push": .25, "p_over_no_push": 2/3}
    with pytest.raises(ValueError):
        probability_summary([], 1)


def test_binary_gap_uses_actual_price_and_vig_label():
    a = price_gap(.6, -110, -110)
    assert a["gap"] == pytest.approx(.1)
    assert "no-vig" in a["gap_units"]
    assert "vig remains" in price_gap(.6, -110, None)["gap_units"]
    assert price_gap(.6, None, None)["gap"] is None


def test_prop_line_join_rejects_period_wrong_game_and_unverified_quotes():
    from types import SimpleNamespace
    game = SimpleNamespace(home_team="SF", away_team="CHI", kickoff_utc=pd.Timestamp("2026-10-20T00:00Z"))
    base = {"home": "SF", "away": "CHI", "gsis_id": "p", "stat": "rec", "pregame_verified": True, "period": "FULL",
            "kickoff": "2026-10-20T00:00Z", "quote_time": "2026-10-19T12:00Z", "available_at": "2026-10-19T12:01Z", "book": "a"}
    frame = pd.DataFrame([base, base | {"book": "half", "period": "1H"}, base | {"book": "wrong", "kickoff": "2026-10-27T00:00Z"},
                          base | {"book": "future", "pregame_verified": False}])
    assert matching_lines(frame, game, "p", "rec")["book"].tolist() == ["a"]


def test_forecast_fixture_roundtrip_is_pregame_and_immutable(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from lab.props import projections10 as P
    output = tmp_path / "shadow"
    reports = tmp_path / "reports"
    structural_dir = output / "structural_prospective2026_recent"
    structural_dir.mkdir(parents=True)
    reports.mkdir()
    monkeypatch.setattr(P, "OUT", output)
    monkeypatch.setattr(P, "REPORTS_DIR", reports)
    monkeypatch.setattr(P, "frozen_config", lambda: {"config_sha256": "fixture"})
    monkeypatch.delenv("NFL_LAB_ARTIFACT_NODE", raising=False)
    monkeypatch.delenv("NFL_LAB_ARTIFACT_WORKSPACE", raising=False)
    gid = "2026_06_CHI_SF"
    kick = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
    games = pd.DataFrame([{"game_id": gid, "season": 2026, "week": 6, "completed": False,
                           "kickoff_utc": kick, "home_team": "SF", "away_team": "CHI"}])
    game_path = tmp_path / "games.parquet"
    games.to_parquet(game_path)
    monkeypatch.setattr(P, "FEATURE_STORE", game_path)
    (output / "production_fit.json").write_text(json.dumps({"frozen_config_sha256": "fixture", "directory": "unused",
        "training_last_completed_week": 5, "training_cutoff_date": "2026-10-12"}))
    pd.DataFrame([{"game_id": gid, "pid": pid, "team": team, "name": name}
                  for pid, team, name in [("p1", "SF", "Fixture QB"), ("p2", "CHI", "Fixture WR")]]).to_parquet(output / "features_production.parquet")
    wide = pd.DataFrame([{ "game_id": gid, "season": 2026, "week": 6, "pid": pid, "team": team,
        "name": name, "stat": stat, "actual": np.nan, "logreg": mean, "random_forest": mean,
        "xgboost": mean, "mlp": mean} for pid, team, name, stat, mean in [
            ("p1", "SF", "Fixture QB", "anytime_td", .2), ("p2", "CHI", "Fixture WR", "anytime_td", .3),
            ("p2", "CHI", "Fixture WR", "rec", 3.)]])
    monkeypatch.setattr(P, "learned_predictions", lambda *a: wide)
    dev = wide.copy()
    dev["season"], dev["week"], dev["actual"] = 2022, 1, 0.
    dev.to_parquet(output / "dev_predictions.parquet")
    st = pd.DataFrame([{ "game_id": gid, "pid": pid, "stat": stat, "member": "sim_independent", "mean": mean,
        "samples": samples, "anytime_td": .25} for pid, stat, mean, samples in [
            ("p1", "anytime_td", .25, [0., 0., 1., 0.]), ("p2", "anytime_td", .25, [0., 0., 1., 0.]),
            ("p2", "rec", 2.5, [1., 2., 3., 4.])]])
    st.to_parquet(structural_dir / f"{gid}.parquet")
    (structural_dir / f"{gid}.json").write_text(json.dumps({"games": [{"member": "sim_independent",
        "margin_samples": [-7, 0, 3, 7], "total_samples": [35, 42, 45, 49], "margin_mean": .75, "total_mean": 42.75,
        "margin_q10_50_90": [-4.9, 1.5, 5.8], "total_q10_50_90": [37.1, 43.5, 47.8],
        "first_td": {"p1": .4, "p2": .5}, "no_offensive_td": .1}]}))
    class Anchor:
        def fit(self, *a):
            return self
        def predict(self, f):
            return pd.DataFrame([{ "margin": 2., "total": 44., "margin_q10": -10., "margin_q50": 2.,
                "margin_q90": 14., "total_q10": 30., "total_q50": 44., "total_q90": 58.}])
    monkeypatch.setattr(P, "IndependentAnchor", Anchor)
    monkeypatch.setattr(P, "archived_lines", lambda **kw: pd.DataFrame())
    monkeypatch.setattr(P, "local_game_lines", lambda *a: {gid: {"margin": 1., "total": 42., "quote_time": pd.Timestamp.now(tz="UTC").isoformat()}})
    monkeypatch.setattr(P.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="fixture-revision"))
    result = P.forecast(log=lambda m: None)
    assert result["errors"] == []
    assert result["archived"] == [gid]
    archived = output / "forecasts2026" / f"{gid}.json"
    before = archived.read_bytes()
    payload = json.loads(before)
    assert pd.Timestamp(payload["generated_at"]) < pd.Timestamp(payload["kickoff"])
    assert payload["training_cutoff_date"] == "2026-10-12"
    td = [r["projection"] for r in payload["rows"] if r["row_type"] == "first_td"]
    assert sum(td) == pytest.approx(1)
    assert all("simulator_v1" not in (r.get("members") or "") for r in payload["rows"])
    P.forecast(log=lambda m: None)
    assert archived.read_bytes() == before
    assert (reports / "projections_2026_w6.csv").exists()
    assert "SF -2.0" in (reports / "projections_2026_w6.md").read_text(encoding="utf-8")
