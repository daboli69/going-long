import numpy as np
import pandas as pd

from lab import features


def _fcols(fs):
    return [c for c in fs.columns if c.startswith(("home_", "away_", "diff_", "mx_", "ctx_"))
            and c not in features.META_COLUMNS and fs[c].dtype.kind == "f"]


def test_one_row_per_game_and_cutoff(feature_store, league):
    g, _, _ = league
    assert len(feature_store) == len(g) and feature_store["game_id"].is_unique
    assert (feature_store["feature_cutoff_utc"] == feature_store["kickoff_utc"]).all()


def test_no_future_information(league, feature_store):
    """Changing a game's result and stats must not change any feature of a game
    that kicked off at or before it, and must change something later."""
    g, t, q = league
    target = g[(g["season"] == 2020) & (g["week"] == 7)].iloc[0]
    g2, t2, q2 = g.copy(), t.copy(), q.copy()
    g2.loc[g2["game_id"] == target["game_id"], ["home_score", "away_score"]] = [70, 0]
    g2["margin"] = g2["home_score"] - g2["away_score"]
    t2.loc[t2["game_id"] == target["game_id"], ["epa_pp", "turnovers", "sr", "pass_yds"]] = [5.0, 9, 0.99, 900]
    q2.loc[q2["game_id"] == target["game_id"], "qb_epa_sum"] = 999.0
    fs2 = features.build_feature_store(g2, t2, q2)
    cols = _fcols(feature_store)
    a = feature_store.set_index("game_id")
    b = fs2.set_index("game_id").loc[a.index]
    before = a["kickoff_utc"] <= target["kickoff_utc"]
    pd.testing.assert_frame_equal(a.loc[before, cols], b.loc[before, cols])
    after = a["kickoff_utc"] > target["kickoff_utc"]
    assert not np.allclose(a.loc[after, cols].fillna(0).to_numpy(), b.loc[after, cols].fillna(0).to_numpy())


def test_rolling_windows_exclude_current_game(league, feature_store):
    g, t, _ = league
    team = "BUF"
    played = g[g["completed"] & ((g["home_team"] == team) | (g["away_team"] == team))].sort_values("kickoff_utc")
    games_team = played.merge(t[t["team"] == team], on="game_id")
    row = feature_store[feature_store["game_id"] == played.iloc[40]["game_id"]].iloc[0]
    side = "home" if row["home_team"] == team else "away"
    prior = games_team.iloc[37:40]["epa_pp"].mean()
    assert abs(row[f"{side}_l3_epa_pp"] - prior) < 1e-12


def test_season_boundary_resets_season_to_date(league, feature_store):
    wk1 = feature_store[(feature_store["season"] == 2019) & (feature_store["week"] == 1)]
    assert (wk1["home_std_games"] == 0).all()
    assert wk1["home_std_epa_pp"].isna().all()
    # blend falls back to the previous season mean in week 1
    assert np.allclose(wk1["home_blend_epa_pp"], wk1["home_prev_epa_pp"])
    g, t, _ = league
    team = wk1.iloc[0]["home_team"]
    prev = g[(g["season"] == 2018)].merge(t[t["team"] == team], on="game_id")["epa_pp"].mean()
    assert abs(wk1.iloc[0]["home_prev_epa_pp"] - prev) < 1e-12


def test_upcoming_games_get_features(feature_store):
    up = feature_store[~feature_store["completed"]]
    assert len(up)
    cols = features.select_features(feature_store.columns)
    assert up[cols].notna().mean().mean() > 0.9


def test_feature_catalog_documents_every_model_feature(feature_store):
    cat = features.feature_catalog(feature_store.columns)
    cols = features.select_features(feature_store.columns)
    assert set(cols) <= set(cat["feature"])
    assert (cat.loc[cat["feature"].isin(cols), "formula"].str.len() > 0).all()
    assert cat["pregame_available"].str.contains("EXCLUDED").any()


def test_actual_starting_qb_never_used(league, feature_store):
    """Rewriting the listed/actual starters must not change any feature."""
    g, t, q = league
    g2 = g.copy()
    g2["home_qb_id"], g2["away_qb_id"] = "SOMEONE_ELSE", "SOMEONE_ELSE"
    fs2 = features.build_feature_store(g2, t, q)
    cols = _fcols(feature_store)
    pd.testing.assert_frame_equal(feature_store[cols], fs2[cols])


def test_projected_qb_switches_only_on_verified_out(league):
    g, t, q = league
    target = g[(g["season"] == 2021) & (g["week"] == 5)].iloc[0]
    team = target["home_team"]
    base = features.project_starters(g, q).set_index(["game_id", "team"])
    assert base.loc[(target["game_id"], team), "qb_projected_id"] == f"QB_{team}"
    status = {(target["game_id"], team, f"QB_{team}"): "Out"}
    proj = features.project_starters(g, q, status).set_index(["game_id", "team"])
    row = proj.loc[(target["game_id"], team)]
    assert row["qb_projected_out"] == 1 and row["qb_projected_id"] == f"QB2_{team}"
    first = proj[proj["season"] == 2021].sort_values("kickoff_utc").groupby(level=1).head(1)
    assert (first["qb_offseason"] == 1).all()
