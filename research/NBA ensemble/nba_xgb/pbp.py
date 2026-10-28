"""Lineup and stint reconstruction from raw ESPN play-by-play (SportsDataverse release files).

Starters are inferred from the event stream (a player seen acting, or leaving the floor, before any recorded
'enters the game' event). Everything after that follows the recorded substitutions. Games whose lineups cannot be
reconstructed to five players per side throughout are reported and excluded, never repaired by guessing.
"""
from __future__ import annotations
import glob
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
from . import data

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_nba_xgb'
PBP_DIR = ROOT / 'data' / 'raw' / 'archive'
USECOLS = ['game_id', 'season', 'season_type', 'sequence_number', 'game_play_number', 'type_text', 'text', 'team_id',
           'athlete_id_1', 'athlete_id_2', 'period_number', 'clock_display_value', 'home_score', 'away_score',
           'scoring_play', 'shooting_play', 'wallclock', 'home_team_id', 'away_team_id']
ENTERS = re.compile(r'enters the game for')


def pbp_file(season: int) -> str:
    return sorted(glob.glob(str(PBP_DIR / f'pbp_{season}' / '*.parquet')))[-1]


def clock_seconds(s: pd.Series) -> np.ndarray:
    m = s.astype(str).str.extract(r'^(\d+):(\d+)(?:\.(\d+))?$')
    return (m[0].astype(float) * 60 + m[1].astype(float) + m[2].astype(float).fillna(0) / 10).values


def elapsed(period: np.ndarray, remaining: np.ndarray) -> np.ndarray:
    start = np.where(period <= 4, 720.0 * (period - 1), 2880.0 + 300.0 * (period - 5))
    length = np.where(period <= 4, 720.0, 300.0)
    return start + (length - remaining)


def event_kind(t: str) -> str:
    t = t or ''
    if t.startswith('Free Throw'):
        return 'fta'
    if t == 'Offensive Rebound':
        return 'oreb'
    if 'Turnover' in t:
        return 'tov'
    if t == 'Substitution':
        return 'sub'
    return 'other'


def reconstruct_game(ev: pd.DataFrame, home_id: str, away_id: str, starters_hint=None):
    """Return (stints list, status). `ev` is one game's events, already sorted."""
    team = ev.team_id.astype('Int64').astype(str).values
    a1 = ev.athlete_id_1.values
    a2 = ev.athlete_id_2.values
    kind = ev.type_text.map(event_kind).values
    text = ev.text.fillna('').values
    is_sub = kind == 'sub'
    in_flag = np.array([bool(ENTERS.search(t)) for t in text])
    # players per side that appear before entering: starters
    seen_in, starters = {home_id: set(), away_id: set()}, {home_id: [], away_id: []}
    for i in range(len(ev)):
        t = team[i]
        if t not in starters:
            continue
        if is_sub[i] and in_flag[i]:
            p_in, p_out = a1[i], a2[i]
            if p_out == p_out and p_out not in seen_in[t]:
                seen_in[t].add(p_out)
                starters[t].append(p_out)          # left the floor before ever entering
            if p_in == p_in:
                seen_in[t].add(p_in)
        elif not is_sub[i]:
            actors = [a1[i]]
            if ev.scoring_play.values[i] and a2[i] == a2[i] and kind[i] == 'other':
                actors.append(a2[i])                # assist: same team as the scorer
            for p in actors:
                if p == p and p not in seen_in[t]:
                    seen_in[t].add(p)
                    starters[t].append(p)
    for t in (home_id, away_id):
        if len(starters[t]) != 5 and starters_hint is not None and len(starters_hint.get(t, [])) == 5:
            starters[t] = list(starters_hint[t])
        if len(starters[t]) != 5:
            return None, f'starters_{len(starters[t])}'
    lineup = {home_id: set(starters[home_id]), away_id: set(starters[away_id])}
    period = ev.period_number.values.astype(float)
    t_el = elapsed(period, clock_seconds(ev.clock_display_value))
    hs, as_ = ev.home_score.values.astype(float), ev.away_score.values.astype(float)
    stints = []
    cur = dict(t0=0.0, hp=hs[0] if len(hs) else 0.0, ap=as_[0] if len(as_) else 0.0,
               h=dict(poss=0.0, fga=0, fta=0, oreb=0, tov=0), a=dict(poss=0.0, fga=0, fta=0, oreb=0, tov=0),
               hl=tuple(sorted(lineup[home_id])), al=tuple(sorted(lineup[away_id])))
    cur['hp'], cur['ap'] = 0.0, 0.0
    last_h, last_a = 0.0, 0.0

    def close(t_end, hscore, ascore):
        st = dict(cur)
        st['t1'] = t_end
        st['home_pts'] = hscore - st['hp']
        st['away_pts'] = ascore - st['ap']
        return st

    for i in range(len(ev)):
        t = team[i]
        last_h, last_a = hs[i], as_[i]
        k = kind[i]
        if k == 'sub' and t in lineup and in_flag[i]:
            p_in, p_out = a1[i], a2[i]
            side_set = lineup[t]
            if p_out not in side_set or p_in in side_set:
                return None, 'sub_inconsistent'
            # close current stint just before this substitution
            if t_el[i] > cur['t0']:
                stints.append(close(t_el[i], hs[i], as_[i]))
                cur = dict(t0=t_el[i], hp=hs[i], ap=as_[i], h=dict(poss=0.0, fga=0, fta=0, oreb=0, tov=0),
                           a=dict(poss=0.0, fga=0, fta=0, oreb=0, tov=0), hl=cur['hl'], al=cur['al'])
            side_set.discard(p_out)
            side_set.add(p_in)
            cur['hl'] = tuple(sorted(lineup[home_id]))
            cur['al'] = tuple(sorted(lineup[away_id]))
            continue
        if t in (home_id, away_id):
            side = 'h' if t == home_id else 'a'
            if k == 'fta':
                cur[side]['fta'] += 1
            elif k == 'oreb':
                cur[side]['oreb'] += 1
            elif k == 'tov':
                cur[side]['tov'] += 1
            elif ev.shooting_play.values[i] and k == 'other':
                cur[side]['fga'] += 1
    stints.append(close(t_el[-1], last_h, last_a))
    for s in stints:
        for side in ('h', 'a'):
            d = s[side]
            d['poss'] = d['fga'] + 0.44 * d['fta'] - d['oreb'] + d['tov']
    return stints, 'ok'


def build_season(season: int, games: pd.DataFrame, pbox: pd.DataFrame | None, log=print):
    raw = pd.read_parquet(pbp_file(season), columns=USECOLS)
    raw = raw[raw.season_type.eq(2)].copy()
    raw['game_id'] = raw.game_id.astype(str)
    g = games[(games.season == season) & games.completed & games.verified].set_index('game_id')
    raw = raw[raw.game_id.isin(g.index)]
    sort_key = ['game_id', 'game_play_number']
    raw = raw.sort_values(sort_key, kind='stable')
    rows, status = [], {}
    hints = {}
    if pbox is not None:
        st = pbox[(pbox.season == season) & pbox.starter.fillna(False).astype(bool)]
        for (gid, tid), grp in st.groupby(['game_id', 'team_id']):
            hints.setdefault(str(gid), {})[str(tid)] = [float(x) for x in grp.athlete_id.values]
    for gid, ev in raw.groupby('game_id', sort=False):
        home_id, away_id = g.loc[gid, 'home_id'], g.loc[gid, 'away_id']
        ev = ev.reset_index(drop=True)
        stints, why = reconstruct_game(ev, home_id, away_id, hints.get(gid))
        status[gid] = why
        if stints is None:
            continue
        for i, s in enumerate(stints):
            if s['t1'] <= s['t0']:
                continue
            rows.append((gid, season, i, s['t0'], s['t1'], s['hl'], s['al'], s['home_pts'], s['away_pts'],
                         s['h']['poss'], s['a']['poss']))
    stint_df = pd.DataFrame(rows, columns=['game_id', 'season', 'stint', 't0', 't1', 'home_lineup', 'away_lineup',
                                           'home_pts', 'away_pts', 'home_poss', 'away_poss'])
    missing = sorted(set(g.index) - set(raw.game_id))
    for gid in missing:
        status[gid] = 'no_pbp'
    return stint_df, status


def main(seasons=range(2019, 2028), log=print):
    games, boxes = data.load()
    pbox = None
    p = ROOT / 'data' / 'cache' / 'player_boxes.parquet'
    if p.exists():
        pbox = pd.read_parquet(p)
    OUT.mkdir(exist_ok=True)
    all_stints, audit = [], {}
    for s in seasons:
        st, status = build_season(s, games, pbox, log)
        all_stints.append(st)
        counts = pd.Series(status).value_counts().to_dict()
        audit[s] = {'games_expected': int(((games.season == s) & games.completed & games.verified).sum()),
                    'status': counts, 'stints': len(st)}
        log(s, audit[s], flush=True) if False else log(s, audit[s])
    stints = pd.concat(all_stints, ignore_index=True)
    stints.to_parquet(OUT / 'stints.parquet', index=False)
    (OUT / 'PBP_AUDIT.json').write_text(json.dumps(audit, indent=2, default=str), encoding='utf-8')
    return stints, audit


if __name__ == '__main__':
    main()
