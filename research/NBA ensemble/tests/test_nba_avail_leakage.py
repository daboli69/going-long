"""Randomized-outcome leakage test and mutation test for the availability pipeline (real archived data, windowed)."""
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from nba_xgb import availability, data, rapm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_nba_xgb'
needed = [OUT / 'stints.parquet', ROOT / 'data' / 'cache' / 'player_boxes.parquet', ROOT / 'data' / 'cache' / 'injury_reports.parquet']
pytestmark = pytest.mark.skipif(not all(p.exists() for p in needed), reason='archived inputs not present')
FEATS = ['full_value_diff', 'avail_effect_diff', 'missing_min_diff', 'avail_value_diff', 'rapm_refit_day']


@pytest.fixture(scope='module')
def inputs():
    games, pb, inj = availability.load_inputs()
    games = games[games.season <= 2023].copy()
    stints = pd.read_parquet(OUT / 'stints.parquet')
    stints = stints[(stints.season >= 2021) & (stints.season <= 2023)].copy()
    pb = pb[pb.season <= 2023].copy()
    inj = inj[inj.game_id.isin(games.game_id)].copy()
    return games, pb, inj, stints


def refit_day_on_or_after(date):
    d = rapm.day_num('2021-12-01')
    target = rapm.day_num(date)
    while d < target:
        d += rapm.REFIT_DAYS
    return d


def pipeline(games, pb, inj, stints, cut_day, leak_history=False, leak_days=0):
    design = rapm.Design(stints, games)
    ratings = rapm.ratings_table(design, 3000, 730, start='2021-12-01', end=str(np.datetime64(int(cut_day + 40), 'D')),
                                 log=lambda *a: None, leak_days=leak_days)
    cands = availability.candidate_rows(games, pb, inj, leak_history=leak_history)
    return availability.build_game_features(cands, games, ratings, log=lambda *a: None).set_index('game_id')


def scramble(games, pb, stints, cut_date, seed=11):
    rng = np.random.default_rng(seed)
    g = games.copy()
    late_ids = set(g.loc[g.game_date >= cut_date, 'game_id'])
    flip = g.game_id.isin(late_ids) & (rng.random(len(g)) < 0.5)
    g.loc[flip, ['home_score', 'away_score']] = g.loc[flip, ['away_score', 'home_score']].values
    p = pb.copy()
    idx = p.index[p.game_id.isin(late_ids)]
    cols = ['minutes', 'played', 'did_not_play']
    p.loc[idx, cols] = p.loc[rng.permutation(idx), cols].values
    s = stints.copy()
    sidx = s.index[s.game_id.isin(late_ids)]
    pcols = ['home_pts', 'away_pts', 'home_poss', 'away_poss']
    s.loc[sidx, pcols] = s.loc[rng.permutation(sidx), pcols].values
    return g, p, s


def cut_setup(games):
    cut_day = refit_day_on_or_after('2023-01-20')                       # a refit day, so a same-day leak would be visible
    cut_date = str(np.datetime64(int(cut_day), 'D'))
    return cut_day, cut_date


def test_randomizing_later_outcomes_leaves_earlier_features_unchanged(inputs):
    games, pb, inj, stints = inputs
    cut_day, cut_date = cut_setup(games)
    base = pipeline(games, pb, inj, stints, cut_day)
    g2, pb2, st2 = scramble(games, pb, stints, cut_date)
    pert = pipeline(g2, pb2, inj, st2, cut_day)
    early = games[(games.game_date <= cut_date)].game_id
    early = [g for g in early if g in base.index and g in pert.index]
    assert len(early) > 500
    a, b = base.loc[early, FEATS].to_numpy(float), pert.loc[early, FEATS].to_numpy(float)
    assert np.allclose(a, b, atol=1e-9, equal_nan=True)
    # power: features well after the cut must react to the scrambled outcomes
    late = [g for g in games[games.game_date >= str(np.datetime64(int(cut_day + 40), 'D'))].game_id if g in base.index and g in pert.index]
    assert len(late) > 100
    assert not np.allclose(base.loc[late, FEATS[:3]].to_numpy(float), pert.loc[late, FEATS[:3]].to_numpy(float), equal_nan=True)


@pytest.mark.parametrize('leak', ['history', 'rapm_same_day'])
def test_mutation_planted_leaks_are_detected(inputs, leak):
    games, pb, inj, stints = inputs
    cut_day, cut_date = cut_setup(games)
    g2, pb2, st2 = scramble(games, pb, stints, cut_date)
    kw = dict(leak_history=True) if leak == 'history' else dict(leak_days=1)
    base = pipeline(games, pb, inj, stints, cut_day, **kw)
    pert = pipeline(g2, pb2, inj, st2, cut_day, **kw)
    early = [g for g in games[(games.game_date <= cut_date)].game_id if g in base.index and g in pert.index]
    a, b = base.loc[early, FEATS].to_numpy(float), pert.loc[early, FEATS].to_numpy(float)
    assert not np.allclose(a, b, atol=1e-9, equal_nan=True), 'the planted leak was NOT detected'
