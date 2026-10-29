"""Timing ledger: what each game's own-tipoff injury report adds over the day's first-tipoff report.

Per game: the report version in force one hour before the day's FIRST tipoff (what the earlier study used) against the last version
published at least one hour before THIS game's tipoff; how many versions arrived in between; how many player statuses changed;
and how many changes involve a rotation player (>= 5 of the team's previous 10 games, >= 10 average minutes) moving between
'unlikely to play' (Out, Doubtful) and 'may play' (everything else, including not listed).
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from . import data
from .avail_study import OUT, ROOT

ET = 'America/New_York'
LEAD = pd.Timedelta(hours=1)
LOW = {'Out', 'Doubtful'}


def load_versions():
    v = pd.read_parquet(ROOT / 'data' / 'cache' / 'injury_report_versions.parquet')
    v['published_at'] = pd.to_datetime(v.published_at, utc=True)
    v = v[v.game_id.notna()].copy()
    v['game_id'] = v.game_id.astype(str)
    same_day = v.game_date.eq(pd.to_datetime(v.report_day).dt.strftime('%m/%d/%Y'))
    return v[same_day].copy()


def ledger(log=print):
    games, _ = data.load()
    g = games[(games.season >= 2022) & (games.season <= 2026) & games.completed & games.verified].copy()
    g['tip'] = pd.to_datetime(g.tipoff_utc, utc=True)
    g['day'] = g.tip.dt.tz_convert(ET).dt.strftime('%Y-%m-%d')
    g['first_tip'] = g.groupby('day').tip.transform('min')
    v = load_versions()
    versions = v.groupby('report_day').published_at.apply(lambda s: np.sort(s.astype('int64').unique())).to_dict()   # ns since epoch (UTC)
    rows = []
    for r in g.itertuples(index=False):
        pubs = versions.get(r.day)
        if pubs is None:
            continue
        i_first = np.searchsorted(pubs, (r.first_tip - LEAD).value, side='right') - 1
        i_own = np.searchsorted(pubs, (r.tip - LEAD).value, side='right') - 1
        if i_first < 0:
            continue
        rows.append((r.game_id, r.season, r.day, r.tip, pd.Timestamp(pubs[i_first], tz='UTC'), pd.Timestamp(pubs[i_own], tz='UTC'),
                     int(i_own - i_first), (r.tip - pd.Timestamp(pubs[i_own], tz='UTC')).total_seconds() / 3600.0))
    L = pd.DataFrame(rows, columns=['game_id', 'season', 'day', 'tip', 'first_version', 'own_version', 'versions_between', 'hours_before_tip'])
    assert len(L) > 4000, f'ledger covers only {len(L)} games'
    L['first_version'] = pd.to_datetime(L.first_version, utc=True)
    L['own_version'] = pd.to_datetime(L.own_version, utc=True)
    # player-level status at the two versions
    keys = v[['game_id', 'team_id', 'athlete_id', 'status', 'published_at', 'not_yet_submitted']].copy()
    keys['athlete_id'] = pd.to_numeric(keys.athlete_id, errors='coerce')
    keys = keys.dropna(subset=['athlete_id'])
    keys['athlete_id'] = keys.athlete_id.astype('int64')
    a = L[['game_id', 'first_version']].merge(keys, left_on=['game_id', 'first_version'], right_on=['game_id', 'published_at'])
    b = L[['game_id', 'own_version']].merge(keys, left_on=['game_id', 'own_version'], right_on=['game_id', 'published_at'])
    a = a.rename(columns={'status': 'status_first'})[['game_id', 'team_id', 'athlete_id', 'status_first']]
    b = b.rename(columns={'status': 'status_own'})[['game_id', 'team_id', 'athlete_id', 'status_own']]
    m = a.merge(b, on=['game_id', 'team_id', 'athlete_id'], how='outer')
    m['status_first'] = m.status_first.fillna('NotListed')
    m['status_own'] = m.status_own.fillna('NotListed')
    m['changed'] = m.status_first != m.status_own
    m['low_first'] = m.status_first.isin(LOW)
    m['low_own'] = m.status_own.isin(LOW)
    m['flip'] = m.low_first != m.low_own
    cands = pd.read_parquet(OUT / 'avail_candidates.parquet')[['game_id', 'team_id', 'athlete_id', 'gp_last10', 'avg_min']]
    cands['athlete_id'] = cands.athlete_id.astype('int64')
    m = m.merge(cands, on=['game_id', 'team_id', 'athlete_id'], how='left')
    m['rotation'] = (m.gp_last10.fillna(0) >= 5) & (m.avg_min.fillna(0) >= 10)
    m['rot_flip'] = m.flip & m.rotation
    m['rot_to_out'] = m.rot_flip & m.low_own & ~m.low_first
    m['rot_back_in'] = m.rot_flip & m.low_first & ~m.low_own
    agg = m.groupby('game_id').agg(status_changes=('changed', 'sum'), lineup_flips=('flip', 'sum'), rotation_flips=('rot_flip', 'sum'),
                                   rotation_newly_out=('rot_to_out', 'sum'), rotation_back_in=('rot_back_in', 'sum')).reset_index()
    L = L.merge(agg, on='game_id', how='left').fillna({'status_changes': 0, 'lineup_flips': 0, 'rotation_flips': 0,
                                                       'rotation_newly_out': 0, 'rotation_back_in': 0})
    L['tip_hour_et'] = L.tip.dt.tz_convert(ET).dt.hour
    return L


def summarize(L):
    s = {'games': int(len(L)), 'share_with_newer_version': float((L.versions_between > 0).mean()),
         'mean_versions_between': float(L.versions_between.mean()),
         'share_with_any_status_change': float((L.status_changes > 0).mean()),
         'share_with_rotation_flip': float((L.rotation_flips > 0).mean()),
         'share_with_rotation_newly_out': float((L.rotation_newly_out > 0).mean()),
         'share_with_rotation_back_in': float((L.rotation_back_in > 0).mean()),
         'median_hours_between_own_version_and_tip': float(L.hours_before_tip.median())}
    s['by_season'] = {int(k): {'games': int(len(x)), 'rotation_flip_share': float((x.rotation_flips > 0).mean())} for k, x in L.groupby('season')}
    L = L.assign(bucket=pd.cut(L.tip_hour_et, [-1, 14, 18, 20, 22, 24], labels=['by 2pm', '3-6pm', '7-8pm', '9-10pm', '11pm+']))
    s['by_tip_hour'] = {str(k): {'games': int(len(x)), 'rotation_flip_share': float((x.rotation_flips > 0).mean()),
                                 'mean_versions_between': float(x.versions_between.mean())} for k, x in L.groupby('bucket', observed=True)}
    return s


if __name__ == '__main__':
    L = ledger()
    L.to_parquet(OUT / 'timing_ledger.parquet', index=False)
    s = summarize(L)
    (OUT / 'TIMING_LEDGER_SUMMARY.json').write_text(json.dumps(s, indent=2), encoding='utf-8')
    print(json.dumps(s, indent=2))
