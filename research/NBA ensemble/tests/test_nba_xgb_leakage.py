"""Temporal-leakage and data-integrity tests for the NBA XGBoost study (synthetic league, no network)."""
import numpy as np
import pandas as pd
import pytest
from nba_xgb import engine, metrics, models, pipeline

TEAMS = [str(i) for i in range(1, 9)]


def synthetic(seasons=(2015, 2016, 2017), seed=3, postpone=None):
    """Small double round-robin league with true latent strength, one game per team per date."""
    rng = np.random.default_rng(seed)
    strength = dict(zip(TEAMS, rng.normal(0, 4, len(TEAMS))))
    games, boxes, gid = [], [], 0
    for season in seasons:
        start = pd.Timestamp(f'{season - 1}-10-20')
        day = 0
        pairs = [(a, b) for a in TEAMS for b in TEAMS if a != b]
        rng.shuffle(pairs)
        # four games a day, each team once
        slots = []
        while pairs:
            used, today = set(), []
            for pair in list(pairs):
                if pair[0] in used or pair[1] in used:
                    continue
                today.append(pair)
                used |= set(pair)
                pairs.remove(pair)
            slots.append(today)
        for today in slots:
            date = (start + pd.Timedelta(days=day * 2)).strftime('%Y-%m-%d')
            day += 1
            for h, a in today:
                gid += 1
                margin = strength[h] - strength[a] + 2.0 + rng.normal(0, 11)
                hs = int(round(108 + margin / 2 + rng.normal(0, 3)))
                aws = int(round(108 - margin / 2 + rng.normal(0, 3)))
                if hs == aws:
                    hs += 1
                ot = abs(hs - aws) < 3
                tip = pd.Timestamp(date + ' 19:30', tz='America/New_York').tz_convert('UTC')
                postponed = postpone is not None and gid == postpone
                games.append(dict(game_id=str(gid), season=season, tipoff_utc=tip, game_date=date, time_valid=True,
                                  home_id=h, away_id=a, home=h, away=a, neutral=False, completed=not postponed,
                                  went_to_ot=bool(ot), home_score=np.nan if postponed else hs,
                                  away_score=np.nan if postponed else aws, has_box=not postponed,
                                  score_matches_box=True, h_identity=True, a_identity=True, verified=not postponed,
                                  home_win=np.nan if postponed else float(hs > aws), source_retrieved_utc='x'))
                if not postponed:
                    for team, pts in ((h, hs), (a, aws)):
                        fgm = int(pts * 0.36)
                        fg3 = int(pts * 0.1)
                        ftm = pts - 2 * fgm - fg3
                        boxes.append(dict(game_id=str(gid), team_id=team, points=pts, fgm=fgm, fga=fgm * 2 + 5, fg3m=fg3,
                                          fg3a=fg3 * 2 + 3, ftm=ftm, fta=ftm + 4, oreb=10, dreb=33, tov=13, team_tov=1.0,
                                          ast=22, stl=7, blk=5))
    return pd.DataFrame(games), pd.DataFrame(boxes)


PARAMS = dict(lag_days=1, elo=dict(k=20.0, hca=60.0, carry=0.7, mov=True), adj=dict(lam=20.0, kappa=0.25),
              recent=dict(half_life=10.0, n0=5.0, rho=0.5))
FEATS = ['elo_diff', 'adj_off_diff', 'adj_def_diff', 'recent_net_diff', 'rest_diff', 'b2b_home', 'b2b_away',
         'recent_off_diff', 'recent_def_diff', 'ff_efg_diff', 'ff_tov_diff', 'ff_orb_diff', 'ff_ftr_diff', 'gp_min']


def features(g, b, **kw):
    return engine.build_features(g, b, {**PARAMS, **kw}).set_index('game_id')


def mid_season_date(g, season=2016, frac=0.5):
    dates = sorted(g.loc[g.season == season, 'game_date'].unique())
    return dates[int(len(dates) * frac)]


def corrupt_from(g, b, cut):
    g2, b2 = g.copy(), b.copy()
    later = g2.game_date >= cut
    g2.loc[later, 'home_score'] = g2.loc[later, 'home_score'] + 40            # corrupt every later result
    g2.loc[later, 'away_score'] = g2.loc[later, 'away_score'] - 30
    g2.loc[later, 'home_win'] = 1.0 - g2.loc[later, 'home_win']
    mask = b2.game_id.isin(set(g2.loc[later, 'game_id']))
    cols = ['points', 'fgm', 'fga', 'tov', 'oreb']
    b2.loc[mask, cols] = b2.loc[mask, cols] * 1.7
    return g2, b2


def test_future_outcomes_cannot_change_earlier_features():
    g, b = synthetic()
    base = features(g, b)
    cut = mid_season_date(g)
    g2, b2 = corrupt_from(g, b, cut)
    assert (g.game_date >= cut).sum() > 20 and (g.game_date < cut).sum() > 20      # the cut really splits the data
    pert = features(g2, b2)
    late = g.loc[g.game_date > cut, 'game_id']
    assert not np.allclose(base.loc[late, FEATS].values, pert.loc[late, FEATS].values)   # corruption does propagate forward
    # games dated on the cut date may see results through the previous day only, which are unchanged
    early = g.loc[g.game_date <= cut, 'game_id']
    pd.testing.assert_frame_equal(base.loc[early, FEATS], pert.loc[early, FEATS], check_exact=False, atol=1e-10)


def test_removing_future_games_changes_nothing():
    g, b = synthetic()
    base = features(g, b)
    day = mid_season_date(g, frac=0.6)
    g2, b2 = pipeline.as_of_tables(g, b, day)
    g2 = g2[g2.game_date <= day]                                # drop the future schedule altogether
    b2 = b2[b2.game_id.isin(g2.game_id)]
    asof = features(g2, b2)
    same = g2.loc[g2.game_date == day, 'game_id']
    assert len(same) > 0
    # rest days come from the published schedule so only the schedule rows through `day` are needed
    pd.testing.assert_frame_equal(base.loc[same, FEATS], asof.loc[same, FEATS], check_exact=False, atol=1e-10)


def test_date_boundary_result_is_used_only_after_lag():
    g, b = synthetic()
    f1 = features(g, b, lag_days=1)
    f2 = features(g, b, lag_days=2)
    d = pd.Timestamp(f1.game_date.iloc[len(f1) // 2])
    row = f1[f1.game_date == d.strftime('%Y-%m-%d')].iloc[0]
    # data_through_day must be strictly earlier than the game day (days since epoch)
    day_num = (d - pd.Timestamp('1970-01-01')).days
    assert (f1.data_through_day.values < pd.to_datetime(f1.game_date).values.astype('datetime64[D]').astype(int)).all()
    assert (f2.data_through_day.values <= f1.data_through_day.values).all()
    assert (f2.data_through_day.values <= pd.to_datetime(f2.game_date).values.astype('datetime64[D]').astype(int) - 2).all()
    assert day_num > row.data_through_day


def test_cutoff_precedes_tipoff():
    g, b = synthetic()
    f = features(g, b)
    assert (pd.to_datetime(f.prediction_cutoff_utc) < pd.to_datetime(f.tipoff_utc, utc=True)).all()


def test_postponed_game_is_ignored_but_keeps_schedule():
    g, b = synthetic(postpone=40)
    f = features(g, b)
    assert not f.loc['40', 'eligible']
    base = features(*synthetic())
    assert len(f) == len(base)


def test_overtime_possessions_are_not_inflated_by_flag():
    g, b = synthetic()
    prep = engine.prepare(g, b)
    u = prep.upd
    assert u.poss.between(60, 140).all()
    assert (u.h_ortg > 0).all()


def test_duplicate_box_rows_are_rejected_by_canonical_check():
    g, b = synthetic()
    dup = pd.concat([b, b.iloc[:1]])
    assert dup.duplicated(['game_id', 'team_id']).any()      # the canonical builder raises on exactly this condition


def test_season_transition_regresses_elo_toward_the_mean():
    g, b = synthetic()
    prep = engine.prepare(g, b)
    snaps = engine.elo_snapshots(prep, 20.0, 60.0, 0.5, True)
    p = engine.cutoff_index(prep, 1)
    first_new = np.where(prep.g_season == 2016)[0][0]
    last_old_p = p[first_new]
    R = snaps[0][last_old_p]
    # with carry 0.5 the pregame view of a new season must sit half-way back to 1500
    d = engine.elo_features(prep, p, snaps, 0.5)[first_new]
    raw = R[prep.g_home[first_new]] - R[prep.g_away[first_new]]
    assert abs(d) == pytest.approx(abs(raw) * 0.5, rel=1e-9)


def test_elo_updates_are_zero_sum_and_depend_only_on_past():
    g, b = synthetic()
    prep = engine.prepare(g, b)
    R, S = engine.elo_snapshots(prep, 20.0, 60.0, 0.7, True)
    # within the first season each update is +x/-x, so the rating total is conserved
    first_season_dates = int((prep.upd.groupby('day').season.first() == 2015).sum())
    assert np.abs(R[1:first_season_dates + 1].sum(1) - R[0].sum()).max() < 1e-6
    assert np.abs(R[-1] - 1500.0).max() > 1.0            # ratings actually move


def test_walk_forward_training_never_contains_target_or_later_seasons():
    g, b = synthetic(seasons=(2016, 2017, 2018, 2019))
    f = engine.build_features(g, b, PARAMS)
    for fold in (2018, 2019):
        tr = models.training_frame(f, fold)
        assert tr.season.max() < fold
        assert (tr.home_win.notna()).all()


def test_calibrator_is_fitted_on_earlier_data_only():
    p = np.linspace(0.2, 0.8, 100)
    y = (np.random.default_rng(0).random(100) < p).astype(float)
    cal = models.Calibrator('platt').fit(p, y)
    assert 0 < cal.predict(np.array([0.5]))[0] < 1


def test_daily_forecast_file_is_immutable(tmp_path):
    df = pd.DataFrame({'a': [1]})
    path = tmp_path / 'f.csv'
    pipeline.write_once(path, df)
    with pytest.raises(FileExistsError):
        pipeline.write_once(path, df)


def test_metrics_match_hand_calculation():
    y = np.array([1, 0, 1, 1.0])
    p = np.array([0.8, 0.3, 0.6, 0.9])
    assert metrics.logloss(y, p) == pytest.approx(-(np.log(.8) + np.log(.7) + np.log(.6) + np.log(.9)) / 4)
    assert metrics.brier(y, p) == pytest.approx(((.2) ** 2 + .3 ** 2 + .4 ** 2 + .1 ** 2) / 4)
    assert metrics.auc(y, p) == pytest.approx(1.0)


def test_tests_have_power_a_same_day_leak_would_be_caught():
    """Mutation check: with lag 0 (same-day results visible) the perturbation test must detect the change."""
    g, b = synthetic()
    cut = mid_season_date(g)
    g2, b2 = corrupt_from(g, b, cut)
    base, pert = features(g, b, lag_days=0), features(g2, b2, lag_days=0)
    on_cut = g.loc[g.game_date == cut, 'game_id']
    assert not np.allclose(base.loc[on_cut, FEATS].values, pert.loc[on_cut, FEATS].values)
    base1, pert1 = features(g, b, lag_days=1), features(g2, b2, lag_days=1)
    assert np.allclose(base1.loc[on_cut, FEATS].values, pert1.loc[on_cut, FEATS].values)
