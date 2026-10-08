#!/usr/bin/env python3
"""Free-role Challenger in SHADOW (research P3-4): for the games still to be played, record the Champion's mean next to a role-adjusted Challenger mean, with the free role inputs
(offensive snap share, share of team targets, share of team carries; last 1/3/6 games and the changes) and the data cutoff. Write-once per week; outcomes are added later by `settle`.
Uses only public nflverse data. The Challenger is a ridge regression fitted on 2021-2025 (research/trend-intelligence, P3-4). It does not touch the Champion or any displayed probability.

    python scripts/role_shadow.py record [YYYY-MM-DD]     # games on or after this UTC date (default today)
    python scripts/role_shadow.py settle                  # append actual outcomes for recorded weeks that have been played
"""
import datetime
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trend_research import champion, weekly_features as wf  # noqa: E402
from trend_research.experiments2 import champion_rows  # noqa: E402
from trend_research.experiments6 import _cols, baseline_cols  # noqa: E402
from trend_research.stats import Ridge  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'data' / 'role_shadow'
POPULATIONS = {('WR', 'TE'): ['targets', 'rec_yds'], ('RB',): ['carries', 'rush_yds']}
ROLE_COLS = _cols('role.', wf.ROLE_FREE, ('level', 'trend'))
ACTUAL_COLUMN = {'targets': 'targets', 'rec_yds': 'receiving_yards', 'carries': 'carries', 'rush_yds': 'rushing_yards'}


def with_features(frame, root):
    frame = wf.nfl_recency(frame, root)
    frame = wf.nfl_role(frame, root)
    frame = wf.with_trends(frame, 'nfl.', wf.NFL_VOLUME)
    frame = wf.with_trends(frame, 'role.', wf.ROLE_FREE)
    frame['is_te'] = (frame.position == 'TE').astype(float)
    return frame


def prepare(frame, outcome):
    cols, cur, champ = baseline_cols(outcome)
    work = frame.copy()
    work[cur] = work[cur].fillna(work[champ])
    return work, cols, champ


def fit_models(root):
    hist = champion_rows(root)
    models = {}
    for positions, outcomes in POPULATIONS.items():
        frame = with_features(hist[hist.position.isin(positions)].reset_index(drop=True), root)
        for outcome in outcomes:
            work, base, champ = prepare(frame, outcome)
            cols = base + ROLE_COLS
            work = work.dropna(subset=cols + ['y_' + outcome])
            models[(positions, outcome)] = (Ridge().fit(work[cols], work['y_' + outcome]), cols, len(work))
    return models


def upcoming(root, today):
    games = champion.load_games(root)
    games = games[(games.season == games.season.max()) & (games.game_type == 'REG') & (games.gameday >= today)]
    week = int(games.week.min())
    return games[games.week == week], week


def record(root, today):
    games, week = upcoming(root, today)
    season = int(games.season.iloc[0])
    target = OUT / f'{season}-week-{week:02d}.json'
    if target.exists():
        print('already recorded (write-once):', target)
        return
    teams = {}
    for g in games.itertuples():
        teams[g.home_team], teams[g.away_team] = g.away_team, g.home_team
    appear = champion.appearances(root, range(2019, season + 1))
    last = appear[appear.season == season].sort_values(['player_id', 'week']).groupby('player_id').tail(1)
    last = last[last.team.isin(teams) & last.position.isin(['WR', 'TE', 'RB'])]
    extra = last.copy()
    extra['week'] = week
    extra['opponent_team'] = extra.team.map(teams)
    keep = {'player_id', 'season', 'week', 'position', 'team', 'opponent_team', 'player_display_name'}
    for c in extra.columns:
        if c not in keep:
            extra[c] = np.nan
    frame = champion.champion_frame(root, {season}, extra=extra)
    frame = frame[(frame.week == week) & frame.y_targets.isna()].reset_index(drop=True)
    names = dict(zip(appear.player_id, appear.player_display_name))
    models = fit_models(root)
    rows = []
    for positions, outcomes in POPULATIONS.items():
        sub = frame[frame.position.isin(positions) & frame.ready].reset_index(drop=True)
        if sub.empty:
            continue
        sub = with_features(sub, root)
        for outcome in outcomes:
            work, base, champ = prepare(sub, outcome)
            model, cols, n_train = models[(positions, outcome)]
            ok = work.dropna(subset=cols)
            pred = model.predict(ok[cols])
            for (_, r), p in zip(ok.iterrows(), pred):
                rows.append({'player_id': r.player_id, 'name': names.get(r.player_id), 'team': r.team, 'opponent': r.opponent, 'position': r.position, 'outcome': outcome,
                             'champion_mean': float(r[champ]), 'challenger_mean': float(max(p, 0.0)), 'current_games': int(r.k),
                             'role': {c: (None if pd.isna(r[c]) else float(r[c])) for c in ROLE_COLS}, 'train_rows': n_train})
    OUT.mkdir(parents=True, exist_ok=True)
    doc = {'schema': 'role-shadow-v1', 'season': season, 'week': week,
           'games': [{'home': g.home_team, 'away': g.away_team, 'kickoff_date': str(g.gameday)} for g in games.itertuples()],
           'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
           'data_cutoff': f'nflverse weekly stats and snap counts through week {week - 1} of {season}',
           'challenger': 'ridge on Champion mean, current-season mean, games played, TE flag, nflverse last 1/3/6 box-score volume plus free role level and trend (research P3-4)',
           'status': 'SHADOW: not used by any projection, probability, rating or recommendation', 'rows': rows}
    target.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8')
    print(f'recorded {len(rows)} shadow predictions for {season} week {week} -> {target}')


def settle(root):
    for path in sorted(OUT.glob('*-week-??.json')):
        out = path.with_name(path.stem + '-outcomes.json')
        if out.exists():
            continue
        doc = json.loads(path.read_text(encoding='utf-8'))
        weekly = champion.load_weekly(root, [doc['season']])
        weekly = weekly[weekly.season_type == 'REG']
        if int(weekly.week.max()) <= doc['week']:
            continue  # the week is not finished yet
        actual = weekly[weekly.week == doc['week']].drop_duplicates('player_id').set_index('player_id')
        rows = [{'player_id': r['player_id'], 'outcome': r['outcome'], 'actual': (None if r['player_id'] not in actual.index else float(actual.at[r['player_id'], ACTUAL_COLUMN[r['outcome']]]))}
                for r in doc['rows']]
        out.write_text(json.dumps({'schema': 'role-shadow-outcomes-v1', 'season': doc['season'], 'week': doc['week'], 'rows': rows}, indent=1) + '\n', encoding='utf-8')
        print('settled', out)


if __name__ == '__main__':
    root = os.environ.get('GOING_FP_ROOT') or str(REPO.parent / 'GOING' / 'FantasyPoints')
    if sys.argv[1] == 'record':
        record(root, sys.argv[2] if len(sys.argv) > 2 else datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'))
    else:
        settle(root)
