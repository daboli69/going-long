#!/usr/bin/env python3
"""Prospective postmortem for one finished NFL game, against the pregame state frozen in git.

    python scripts/postmortem.py PRE_SHA SEASON WEEK AWAY HOME OUT.json

PRE_SHA is a data commit made BEFORE kickoff (its data/history.json carries the model profiles and data/nfl_betting.json the lines). Outcomes come from public nflverse weekly
player stats. Nothing here feeds any model; it is a read-only audit, and one game is one observation (do not tune on it).
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
STAT = {'pass_yds': 'passing_yards', 'rush_yds': 'rushing_yards', 'rec_yds': 'receiving_yards', 'receptions': 'receptions', 'pass_tds': 'passing_tds',
        'rush_tds': 'rushing_tds', 'rec_tds': 'receiving_tds'}
SHADOW_ACTUAL = {'targets': 'targets', 'rec_yds': 'receiving_yards', 'carries': 'carries', 'rush_yds': 'rushing_yards'}


def git_json(sha, path):
    return json.loads(subprocess.check_output(['git', 'show', f'{sha}:{path}'], cwd=REPO).decode('utf-8'))


def weekly(season, week):
    url = f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'
    df = pd.read_csv(url, low_memory=False)
    return df[(df.week == week) & (df.season_type == 'REG')]


def main(pre, season, week, away, home, out):
    history = git_json(pre, 'data/history.json')['betting']
    lines = git_json(pre, 'data/nfl_betting.json')
    teams = {away, home}
    actual = weekly(season, week)
    actual = actual[actual.team.isin(teams)].set_index('player_id')
    rows, directional = [], []
    props = [p for p in lines.get('props', []) if str(p.get('kickoff', ''))[:10] in ('', ) or True]
    by_player_market = {}
    for p in props:
        by_player_market.setdefault((p['player'], p['market']), []).append(p)
    for pid, prof in history['profiles'].items():
        if prof.get('team') not in teams or pid not in actual.index:
            continue
        a = actual.loc[pid]
        for market, col in STAT.items():
            model = (prof.get('stats') or {}).get(market)
            if not model or model.get('mean') is None or pd.isna(a.get(col)):
                continue
            row = {'player': prof['name'], 'position': prof.get('position'), 'market': market, 'model_mean': model['mean'], 'actual': float(a[col]),
                   'policy': model.get('policy', 'v1')}
            quotes = [q for q in by_player_market.get((prof['name'], market), []) if q.get('line') is not None]
            if quotes:
                line = float(np.median([q['line'] for q in quotes]))
                row['market_line'] = line
                if row['model_mean'] != line and row['actual'] != line:
                    directional.append({**row, 'model_over': row['model_mean'] > line, 'went_over': row['actual'] > line})
            rows.append(row)
    df = pd.DataFrame(rows)
    summary = {}
    for market, g in df.groupby('market'):
        e = g.model_mean - g.actual
        entry = {'n': int(len(g)), 'model_mae': float(e.abs().mean()), 'model_bias': float(e.mean())}
        h = g.dropna(subset=['market_line']) if 'market_line' in g else g.iloc[0:0]
        if len(h):
            entry.update({'lines': int(len(h)), 'market_mae': float((h.market_line - h.actual).abs().mean()), 'model_mae_on_lined': float((h.model_mean - h.actual).abs().mean())})
        summary[market] = entry
    dd = pd.DataFrame(directional)
    direction = {'n': int(len(dd)), 'model_side_hit_rate': float((dd.model_over == dd.went_over).mean()) if len(dd) else None}
    # Free-role Challenger vs Champion (recorded in shadow before kickoff)
    shadow = []
    path = REPO / 'data' / 'role_shadow' / f'{season}-week-{week:02d}.json'
    if path.exists():
        doc = json.loads(path.read_text(encoding='utf-8'))
        for r in doc['rows']:
            if r['team'] in teams and r['player_id'] in actual.index:
                y = actual.loc[r['player_id']].get(SHADOW_ACTUAL[r['outcome']])
                if pd.notna(y):
                    shadow.append({'outcome': r['outcome'], 'champion_error': abs(r['champion_mean'] - y), 'challenger_error': abs(r['challenger_mean'] - y)})
    sh = pd.DataFrame(shadow)
    shadow_summary = {o: {'n': int(len(g)), 'champion_mae': float(g.champion_error.mean()), 'challenger_mae': float(g.challenger_error.mean())} for o, g in sh.groupby('outcome')} if len(sh) else {}
    # Touchdowns: where did the scorers rank on the model's anytime-TD mean?
    td = []
    for pid, prof in history['profiles'].items():
        if prof.get('team') in teams and pid in actual.index:
            m = (prof.get('stats') or {}).get('atd')
            if m and m.get('mean') is not None:
                a = actual.loc[pid]
                td.append({'player': prof['name'], 'atd_mean': m['mean'], 'scored': int((a.get('rushing_tds', 0) or 0) + (a.get('receiving_tds', 0) or 0) > 0)})
    tdf = pd.DataFrame(td).sort_values('atd_mean', ascending=False).reset_index(drop=True)
    td_summary = {'players': int(len(tdf)), 'scorers': int(tdf.scored.sum()) if len(tdf) else 0,
                  'scorer_ranks': [int(i + 1) for i in tdf.index[tdf.scored == 1]] if len(tdf) else [],
                  'mean_model_atd_of_scorers': float(tdf[tdf.scored == 1].atd_mean.mean()) if len(tdf) and tdf.scored.sum() else None,
                  'mean_model_atd_of_nonscorers': float(tdf[tdf.scored == 0].atd_mean.mean()) if len(tdf) else None}
    result = {'game': f'{away} @ {home}', 'season': season, 'week': week, 'pregame_commit': pre,
              'note': 'One game is one observation. Descriptive only; no model was changed because of it.',
              'projection_vs_actual': summary, 'prop_direction': direction, 'role_shadow': shadow_summary, 'touchdowns': td_summary}
    Path(out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6])
