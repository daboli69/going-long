"""Strict as-of replay of the availability features.

Information boundaries replayed separately, each from truncated inputs:
  * ratings: for every weekly refit day R in the test seasons, rebuild the design from stints dated <= R-1 only and refit;
  * candidates + features: for every game date D in the test seasons, hide every outcome dated on or after D (results, player boxes)
    and rebuild candidates for the previous and current season; the play model for season T is fitted on the batch candidate table of
    seasons < T (which cannot depend on dates inside season T); then build the features of the games on D.
Results must equal the batch run (avail_features.parquet, rapm_ratings.parquet).
"""
import json
import numpy as np
import pandas as pd
from . import availability, rapm, avail_study as S

_G = {}


def init():
    games, pb, inj = availability.load_inputs()
    _G['games'], _G['pb'], _G['inj'] = games, pb, inj
    _G['batch_cands'] = pd.read_parquet(S.OUT / 'avail_candidates.parquet')


def feature_day(D, ratings):
    games, pb, inj = _G['games'], _G['pb'], _G['inj']
    season = int(games.loc[games.game_date == D, 'season'].iloc[0])
    g = games[(games.game_date <= D) & (games.season >= season - 1)].copy()
    hide = g.game_date >= D
    g.loc[hide, ['completed', 'verified']] = False
    g.loc[hide, ['home_score', 'away_score', 'home_win']] = np.nan
    pb_t = pb[pb.game_id.isin(g.loc[~hide, 'game_id'])]
    inj_t = inj[inj.game_id.isin(g.game_id)]
    day_ids = set(g.loc[g.game_date == D, 'game_id'])
    first_tip = pd.to_datetime(g.loc[g.game_date == D, 'tipoff_utc'], utc=True).min()
    chk = inj_t[inj_t.game_id.isin(day_ids)]
    assert (pd.to_datetime(chk.available_at, utc=True) <= first_tip).all(), 'injury row published after first tipoff'
    cands = availability.candidate_rows(g, pb_t, inj_t, labelled=False)
    cands = cands[cands.game_id.isin(day_ids)]
    train = _G['batch_cands'][_G['batch_cands'].season < season]
    allc = pd.concat([train, cands], ignore_index=True)
    return availability.build_game_features(allc, games[games.game_id.isin(day_ids)], ratings,
                                            log=lambda *a: None, seasons={season})


def ratings_replay():
    games, _, _ = availability.load_inputs()
    stints = pd.read_parquet(S.OUT / 'stints.parquet')
    stints = stints[stints.season >= 2021]
    g = games.set_index('game_id')
    stints['day'] = pd.to_datetime(stints.game_id.map(g.game_date)).values.astype('datetime64[D]').astype('int64')
    batch = pd.read_parquet(S.OUT / 'rapm_ratings.parquet')
    rows, worst, compared = [], 0.0, 0
    first = rapm.day_num('2024-10-01')
    for R in [d for d in rapm.refit_days('2021-12-01', '2026-10-31') if d >= first]:      # same weekly grid as the batch run
        st = stints[stints.day <= R - 1].drop(columns='day')            # every stint from day R onward deleted
        design = rapm.Design(st, games)
        beta, _ = design.fit(R - 1, 3000, 730)
        P = design.P
        m = pd.Series(beta[2:2 + P] - beta[2 + P:], index=design.players)
        b = batch[batch.refit_day == R].set_index('athlete_id')
        common = m.index.intersection(b.index)
        assert len(common) > 100, f'refit day {R} has no batch counterpart; the comparison would be vacuous'
        compared += len(common)
        worst = max(worst, float((m[common] - b.net[common]).abs().max()))
        rows.append(pd.DataFrame({'refit_day': R, 'athlete_id': m.index, 'net': m.values}))
    print('player-ratings compared', compared, flush=True)
    return pd.concat(rows, ignore_index=True), worst


def main():
    init()
    print('ratings replay', flush=True)
    rr, worst = ratings_replay()
    print('max abs rating difference vs batch', worst, flush=True)
    dates = sorted(_G['games'].loc[_G['games'].season.isin([2025, 2026]) & _G['games'].completed & _G['games'].verified, 'game_date'].unique())
    parts = []
    for i, D in enumerate(dates):
        parts.append(feature_day(D, rr))
        if i % 25 == 0:
            print('day', D, i + 1, '/', len(dates), flush=True)
    rep = pd.concat(parts, ignore_index=True).set_index('game_id')
    batch = pd.read_parquet(S.OUT / 'avail_features.parquet').set_index('game_id')
    cols = ['full_value_diff', 'avail_effect_diff', 'missing_min_diff', 'avail_value_diff', 'rapm_refit_day']
    common = rep.index.intersection(batch.index)
    diff = (rep.loc[common, cols] - batch.loc[common, cols]).abs().max()
    out = {'dates': len(dates), 'games_replayed': int(len(rep)), 'compared': int(len(common)),
           'max_abs_rating_difference': worst, 'max_abs_feature_difference': {k: float(v) for k, v in diff.items()}}
    (S.OUT / 'AVAIL_REPLAY_CHECK.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
