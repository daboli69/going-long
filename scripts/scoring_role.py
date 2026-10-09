"""Public scoring-role record for QB/RB/WR/TE profiles (descriptive intelligence; public nflverse play-by-play only).

For each player the record summarises his own earlier appearances (strictly before the build date, windows count his own appearances, so byes and missed games cannot
misalign them): expected touchdowns (xTD) from carries and targets by yard-line zone, share of team xTD, snap share, goal-line usage, TD luck, role tier. Definitions and the
evidence behind them: research/trend-intelligence/JACKPOT_TD_REPORT.md. Zone rates: config/td_zone_rates.json (league rates fitted on public 2019-2023 plays).

    python scripts/scoring_role.py backfill      attach/refresh `scoring_role` in data/history.json profiles from public play-by-play (no other field changes)
"""
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = 1
POSITIONS = {'QB', 'RB', 'WR', 'TE'}
MIN_APPEARANCES = 5
TIERS = ((0.30, 'PRIMARY'), (0.15, 'SECONDARY'), (0.05, 'TERTIARY'))
PBP_COLUMNS = ['game_id', 'play_id', 'season', 'week', 'season_type', 'posteam', 'qtr', 'yardline_100', 'play_type', 'rush_attempt', 'pass_attempt', 'qb_kneel', 'qb_spike',
               'touchdown', 'td_team', 'td_player_id', 'rusher_player_id', 'receiver_player_id', 'air_yards', 'yards_gained', 'two_point_attempt', 'play_deleted',
               'kickoff_attempt', 'punt_attempt', 'score_differential', 'fixed_drive', 'game_date']


def load_rates(path=None):
    return json.loads(Path(path or ROOT / 'config/td_zone_rates.json').read_text(encoding='utf-8'))


def tier(share):
    if share is None:
        return None
    for floor, name in TIERS:
        if share >= floor:
            return name
    return 'FRINGE'


def zone(yardline):
    for name, top in (('z1', 1), ('z2', 2), ('z3_5', 5), ('z6_10', 10), ('z11_20', 20)):
        if yardline <= top:
            return name
    return 'far'


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def aggregate_plays(rows, rates):
    """Per-player-game opportunity facts and per-game touchdown events from play rows (dicts with the PBP_COLUMNS keys). Regular season only."""
    rows = [r for r in rows if r.get('season_type', 'REG') == 'REG']
    ops = []
    for r in rows:
        if r.get('play_deleted') == 1 or r.get('play_type') == 'no_play' or r.get('qb_kneel') == 1 or r.get('qb_spike') == 1 or not r.get('posteam') or not _num(r.get('yardline_100')):
            continue
        if r.get('rush_attempt') == 1 and r.get('rusher_player_id'):
            ops.append((r, r['rusher_player_id'], 'carry'))
        if r.get('pass_attempt') == 1 and r.get('receiver_player_id'):
            ops.append((r, r['receiver_player_id'], 'target'))
    possessions = defaultdict(set)
    for r, _, _ in ops:
        if _num(r.get('fixed_drive')):
            possessions[(r['game_id'], r['posteam'])].add(r['fixed_drive'])
    first_two = {k: set(sorted(v)[:2]) for k, v in possessions.items()}
    fields = ('xtd', 'inside5', 'rz_tgt', 'gl_car', 'open', 'late_car', 'air', 'air_n')
    games = defaultdict(lambda: dict.fromkeys(fields, 0.0))
    team = defaultdict(lambda: dict.fromkeys(('xtd', 'open', 'late_car'), 0.0))
    meta = {}
    for r, pid, kind in ops:
        yl = r['yardline_100']
        rate = rates['rates'][kind][zone(yl)]
        g, t = games[(r['game_id'], pid)], team[(r['game_id'], r['posteam'])]
        meta[(r['game_id'], pid)] = (r['season'], r['week'], r['posteam'])
        g['xtd'] += rate
        t['xtd'] += rate
        if yl <= 5:
            g['inside5'] += 1
        if kind == 'target' and yl <= 20:
            g['rz_tgt'] += 1
        if kind == 'carry' and yl <= 2:
            g['gl_car'] += 1
        if r.get('fixed_drive') in first_two.get((r['game_id'], r['posteam']), ()):
            g['open'] += 1
            t['open'] += 1
        if kind == 'carry' and (r.get('qtr') or 0) >= 4 and (r.get('score_differential') or 0) > 0:
            g['late_car'] += 1
            t['late_car'] += 1
        if kind == 'target' and _num(r.get('air_yards')):
            g['air'] += r['air_yards']
            g['air_n'] += 1
    events = []
    for r in rows:
        if r.get('touchdown') != 1 or r.get('two_point_attempt') == 1 or r.get('play_deleted') == 1 or r.get('play_type') == 'no_play' or not r.get('td_team') or not r.get('td_player_id'):
            continue
        offense = r.get('td_team') == r.get('posteam') and r.get('kickoff_attempt') != 1 and r.get('punt_attempt') != 1
        events.append({'game_id': r['game_id'], 'play_id': r['play_id'], 'season': r['season'], 'week': r['week'], 'team': r['td_team'], 'player': r['td_player_id'],
                       'long': bool(offense and _num(r.get('yards_gained')) and r['yards_gained'] >= rates['long_td']['min_yards'])})
    events.sort(key=lambda e: (e['game_id'], e['play_id']))
    first = {}
    for e in events:
        first.setdefault(e['game_id'], e['team'])
    player_games = {}
    for (gid, pid), g in games.items():
        season, week, posteam = meta[(gid, pid)]
        t = team[(gid, posteam)]
        player_games[(pid, season, week)] = dict(g, team=posteam, game_id=gid, open_share=g['open'] / t['open'] if t['open'] else 0.0,
                                                 late_share=g['late_car'] / t['late_car'] if t['late_car'] else 0.0, xtd_share=g['xtd'] / t['xtd'] if t['xtd'] else 0.0)
    by_player = defaultdict(list)
    for e in events:
        by_player[e['player']].append(e)
    return {'player_games': player_games, 'events': events, 'by_player': by_player, 'first_td_team': first, 'covered': {(r['season'], r['week']) for r in rows}}


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _r(v):
    return None if v is None else round(v, 3)


def _team_first_rates(agg, today_by_game):
    """Share of the team's last 8 games (before the build date) in which it scored the game's first TD, per team (needs >= 3 games)."""
    per_team = defaultdict(dict)
    for (pid, season, week), g in agg['player_games'].items():
        per_team[g['team']][(season, week)] = g['game_id']
    out = {}
    for team, games in per_team.items():
        recent = sorted(games)[-8:]
        if len(recent) >= 3:
            out[team] = sum(agg['first_td_team'].get(games[k]) == team for k in recent) / len(recent)
    return out


def record_for(profile, agg, snap_share, rates, today, team_first):
    games = sorted((g for g in profile.get('games', []) if g.get('date') and g['date'] < today and (g['season'], g['week']) in agg['covered']), key=lambda g: (g['season'], g['week']))[-12:]
    if not games:
        return None
    pid = profile['id']
    zero = dict.fromkeys(('xtd', 'inside5', 'rz_tgt', 'gl_car', 'open', 'late_car', 'air', 'air_n', 'open_share', 'late_share', 'xtd_share'), 0.0)
    per = [agg['player_games'].get((pid, g['season'], g['week']), zero) for g in games]
    snaps = [snap_share.get((pid, g['season'], g['week'])) for g in games]
    tds = defaultdict(float)
    window = {(g['season'], g['week']) for g in games}
    for e in agg['by_player'].get(pid, ()):
        if (e['season'], e['week']) in window:
            tds['n'] += 1
            tds['long'] += e['long']
    n = len(games)
    out = {'version': VERSION, 'as_of': games[-1]['date'], 'n': n, 'confidence': 'ok' if n >= MIN_APPEARANCES else 'low'}
    keys = ['xtd_pg_l12', 'xtd_pg_l6', 'xtd_share_l6', 'snap_pct_l3', 'snap_pct_l6', 'inside5_touch_pg_l12', 'rz_tgt_pg_l12', 'gl_carry_pg_l12', 'td_pg_l12', 'td_luck_l12',
            'open_share_l6', 'tm_first_td_rate_l8', 'late_lead_carry_share_l6', 'long_td_share', 'adot_l12']
    if n < MIN_APPEARANCES:
        out.update(dict.fromkeys(keys), tier=None, trend={'d_xtd36': None, 'd_snap36': None})
        return out
    col = lambda name, k: [p[name] for p in per[-k:]]
    td_pg = tds['n'] / n
    xtd12 = _mean(col('xtd', 12))
    xtd6, xtd3 = _mean(col('xtd', 6)), _mean(col('xtd', 3))
    snap3, snap6 = _mean(snaps[-3:]), _mean(snaps[-6:])
    air_n = sum(col('air_n', 12))
    lt = rates['long_td']
    out.update({'xtd_pg_l12': _r(xtd12), 'xtd_pg_l6': _r(xtd6), 'xtd_share_l6': _r(_mean(col('xtd_share', 6))), 'snap_pct_l3': _r(snap3), 'snap_pct_l6': _r(snap6),
                'inside5_touch_pg_l12': _r(_mean(col('inside5', 12))), 'rz_tgt_pg_l12': _r(_mean(col('rz_tgt', 12))), 'gl_carry_pg_l12': _r(_mean(col('gl_car', 12))),
                'td_pg_l12': _r(td_pg), 'td_luck_l12': _r(td_pg - xtd12), 'open_share_l6': _r(_mean(col('open_share', 6))), 'tm_first_td_rate_l8': _r(team_first.get(profile.get('team'))),
                'late_lead_carry_share_l6': _r(_mean(col('late_share', 6))),
                'long_td_share': _r((tds['long'] + lt['shrink_tds'] * lt['league_share']) / (tds['n'] + lt['shrink_tds'])),
                'adot_l12': _r(sum(col('air', 12)) / air_n) if air_n else None})
    out['tier'] = tier(out['xtd_share_l6'])
    out['trend'] = {'d_xtd36': _r(xtd3 - xtd6), 'd_snap36': _r(snap3 - snap6) if snap3 is not None and snap6 is not None else None}
    return out


def attach(profiles, pbp_rows, snap_share, today, rates=None):
    """Adds `scoring_role` to every QB/RB/WR/TE profile with >= 1 appearance before `today` (YYYY-MM-DD); returns the count. Deterministic: depends only on its inputs."""
    rates = rates or load_rates()
    pbp_rows = [r for r in pbp_rows if not r.get('game_date') or str(r['game_date'])[:10] < today]  # strictly before the build date
    agg = aggregate_plays(pbp_rows, rates)
    team_first = _team_first_rates(agg, None)
    count = 0
    for profile in profiles.values():
        profile.pop('scoring_role', None)
        if profile.get('position') not in POSITIONS:
            continue
        rec = record_for(profile, agg, snap_share, rates, today, team_first)
        if rec:
            profile['scoring_role'] = rec
            count += 1
    return count


def load_pbp_rows(seasons):
    """Regular-season play rows (only the columns used here). FEATURE_INPUT_DIR/nfl.parquet is honoured like pbp_features.py; otherwise nflreadpy's public loader."""
    import nflreadpy as nfl
    import polars as pl
    cache = Path(os.environ['FEATURE_INPUT_DIR']) if os.getenv('FEATURE_INPUT_DIR') else None
    frames = [pl.read_parquet(cache / 'nfl.parquet')] if cache else []
    if not cache:
        for year in seasons:
            try:
                frames.append(nfl.load_pbp([year]))
            except Exception as exc:
                if '404' not in str(exc):
                    raise
    rows = []
    for frame in frames:
        cols = [c for c in PBP_COLUMNS if c in frame.columns]
        frame = frame.filter((pl.col('season_type') == 'REG') & ((pl.col('rush_attempt') == 1) | (pl.col('pass_attempt') == 1) | (pl.col('touchdown') == 1))).select(cols)
        rows.extend(frame.to_dicts())
    return rows


def snap_share_map(roster, snaps):
    pfr = {r['pfr_id']: r['gsis_id'] for r in roster if r.get('pfr_id') and r.get('gsis_id')}
    out = {}
    for s in snaps:
        pid = pfr.get(s.get('pfr_player_id'))
        if pid and s.get('game_type') == 'REG' and _num(s.get('offense_pct')):
            out[(pid, s['season'], s['week'])] = s['offense_pct']
    return out


def backfill(history_path=None):
    """Patch only `scoring_role` into data/history.json profiles (same function the build calls)."""
    import nflreadpy as nfl
    from datetime import datetime, timezone
    path = Path(history_path or ROOT / 'data/history.json')
    history = json.loads(path.read_text(encoding='utf-8'))
    profiles = history['betting']['profiles']
    today = datetime.now(timezone.utc).date().isoformat()
    season = max(g['season'] for p in profiles.values() for g in p['games'])
    seasons = list(range(season - 2, season + 1))
    roster, snaps = [], []
    for year in seasons:
        roster.extend(nfl.load_rosters([year]).to_dicts())
        try:
            snaps.extend(nfl.load_snap_counts([year]).to_dicts())
        except Exception as exc:
            if '404' not in str(exc):
                raise
    count = attach(profiles, load_pbp_rows(seasons), snap_share_map(roster, snaps), today)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(history, separators=(',', ':'), allow_nan=False, default=str), encoding='utf-8')
    os.replace(tmp, path)
    print(f'[scoring_role] {count} of {len(profiles)} profiles')


if __name__ == '__main__':
    if sys.argv[1:] == ['backfill']:
        backfill()
    else:
        raise SystemExit(__doc__)
