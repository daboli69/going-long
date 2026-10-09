"""SHADOW touchdown-market probabilities (anytime / first / last / longest TD), recorded before kickoff and settled after the week. Public data only.

The probabilities come from the lean score of research/trend-intelligence/JACKPOT_TD_REPORT.md (constants in config/td_shadow_recipe.json). They are NOT shown to users or
written to history.json: this script only archives them so 2026 outcomes can confirm or refute the 2021-2025 research.

    python scripts/td_shadow.py record [YYYY-MM-DD] [--supersede]   write-once (--supersede: re-record before the first kickoff, keeping the old sha256) data/td_shadow/<season>-week-NN.json for the slate on/after the date (default: today)
    python scripts/td_shadow.py settle                append outcomes (nflverse play-by-play) to every recorded week whose games are final
"""
import hashlib
import json
import math
import os
import sys
from zoneinfo import ZoneInfo
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scoring_role  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'td_shadow'
FEATURES = ('xtd_pg_l12', 'xtd_share_l6', 'snap_pct_l3', 'inside5_touch_pg_l12')
MAX_STALE_DAYS = 28
SCHEMA_VERSION = 2
GATE_VERSION = 'availability-gate-2'
QB_RUSH_SHARE = 0.05  # a backup QB with a recorded rushing role at least this large stays a candidate
TD_COLUMNS = ['game_id', 'play_id', 'season', 'week', 'season_type', 'posteam', 'td_team', 'td_player_id', 'touchdown', 'two_point_attempt', 'play_deleted', 'play_type',
              'kickoff_attempt', 'punt_attempt', 'yards_gained', 'return_yards', 'fumble', 'fumble_recovery_1_team', 'fumble_recovery_1_yards', 'fumble_recovery_2_team',
              'fumble_recovery_2_yards', 'pass_touchdown', 'game_seconds_remaining']


def load_recipe(path=None):
    return json.loads(Path(path or ROOT / 'config/td_shadow_recipe.json').read_text(encoding='utf-8'))


def _clip(v, lo, hi):
    return max(lo, min(hi, v))


def anytime_score(rate, role, recipe):
    """Linear predictor (logit) of the anytime-TD score from the Champion rate and the scoring_role features; missing features take the development median."""
    a = recipe['anytime']
    coef, wins = a['coefficients_raw'], a['winsor']
    s = coef['intercept'] + coef['log_champion_rate'] * math.log(max(rate, a['rate_floor']))
    used = {}
    for key, source in recipe['features_map'].items():
        w = wins[key]
        v = role.get(source)
        v = w['median'] if v is None else _clip(v, w['lo'], w['hi'])
        used[source] = v
        s += coef[key] * v
    return s, used


def king_extra(role, recipe):
    total = 0.0
    for source, e in recipe['king_extras'].items():
        v = role.get(source)
        v = e['median'] if v is None else _clip(v, e['lo'], e['hi'])
        total += e['coef'] * (v - e['mean']) / e['sd']
    return total


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def softmax_with_other(utilities, other_utility):
    """P(i) = exp(u_i) / (exp(u0) + sum_j exp(u_j)); returns (probabilities, p_other). Sums to exactly one with the 'other' alternative."""
    top = max([other_utility] + list(utilities))
    e = [math.exp(u - top) for u in utilities]
    denom = math.exp(other_utility - top) + sum(e)
    return [x / denom for x in e], math.exp(other_utility - top) / denom


def game_probabilities(candidates, recipe):
    """candidates: dicts with `score` and `king_extra`. Returns per-market probabilities aligned with candidates, and the 'other' mass per market."""
    out, other = {}, {}
    for market in ('first', 'last', 'king'):
        g = recipe['game'][market]
        extra = [c.get('king_extra', 0.0) if market == 'king' else 0.0 for c in candidates]
        probs, po = softmax_with_other([g['k'] * c['score'] + x for c, x in zip(candidates, extra)], g['u'])
        out[market], other[market] = probs, po
    return out, other


def slate(schedule, on_or_after):
    rows = [g for g in schedule if g.get('game_type') == 'REG' and str(g.get('gameday') or '') >= on_or_after]
    if not rows:
        return None, None, []
    week = min(g['week'] for g in rows)
    return rows[0]['season'], week, sorted((g for g in rows if g['week'] == week), key=lambda g: (g['gameday'], g.get('gametime') or '', g['game_id']))


def eligible(profile, current, cutoff):
    """Availability gate. `current` = data/injury_context.json current_players keyed by gsis id. Only ACT players qualify; no entry -> last game within 28 days.
    A QB must also be the depth-chart QB1 unless he has a recorded rushing role."""
    entry = current.get(profile['id'])
    if entry is None:
        return (profile.get('last_game') or '') >= cutoff
    if entry.get('roster_status') != 'ACT':
        return False
    if profile.get('position') == 'QB' and entry.get('depth_rank') != 1 and (entry.get('rush_share') or 0) < QB_RUSH_SHARE:
        return False
    return True


def build_week(profiles, games, recipe, on_or_after, current=None):
    current = current or {}
    cutoff = (Date.fromisoformat(on_or_after) - timedelta(days=MAX_STALE_DAYS)).isoformat()
    result = []
    for g in games:
        candidates = []
        for p in sorted(profiles.values(), key=lambda p: p['id']):
            role, atd = p.get('scoring_role'), p.get('stats', {}).get('atd', {})
            if p.get('team') not in (g['home_team'], g['away_team']) or not role or role.get('confidence') != 'ok':
                continue
            if atd.get('status') != 'ready' or atd.get('mean') is None or not eligible(p, current, cutoff):
                continue
            score, used = anytime_score(atd['mean'], role, recipe)
            candidates.append({'player_id': p['id'], 'name': p['name'], 'team': p['team'], 'position': p['position'], 'champion_rate': round(atd['mean'], 4), 'features': {k: round(v, 3) for k, v in used.items()},
                               'score': score, 'king_extra': king_extra(role, recipe), 'tier': role.get('tier')})
        probs, other = game_probabilities(candidates, recipe) if candidates else ({}, {})
        rows = []
        for i, c in enumerate(candidates):
            rows.append({k: c[k] for k in ('player_id', 'name', 'team', 'position', 'tier', 'champion_rate', 'features')} |
                        {'p_anytime': round(sigmoid(c['score']), 4), 'p_first': round(probs['first'][i], 4), 'p_last': round(probs['last'][i], 4), 'p_king': round(probs['king'][i], 4)})
        result.append({'game_id': g['game_id'], 'home': g['home_team'], 'away': g['away_team'], 'gameday': g['gameday'], 'gametime': g.get('gametime'),
                       'p_other': {m: round(v, 4) for m, v in other.items()}, 'candidates': rows})
    return result


def first_kickoff(games):
    return min(datetime.fromisoformat(f"{g['gameday']}T{g.get('gametime') or '00:00'}").replace(tzinfo=ZoneInfo('America/New_York')) for g in games)


def record(on_or_after=None, now=None, supersede=False):
    import nflreadpy as nfl
    now = now or datetime.now(timezone.utc)
    on_or_after = on_or_after or now.date().isoformat()
    history = json.loads((ROOT / 'data/history.json').read_text(encoding='utf-8'))['betting']
    season = int(on_or_after[:4])
    schedule = nfl.load_schedules([season]).to_dicts()
    season, week, games = slate(schedule, on_or_after)
    if not games:
        print('no regular-season games on/after', on_or_after)
        return None
    path = OUT / f'{season}-week-{week:02d}.json'
    superseded = None
    if path.exists():
        if not supersede:
            print(f'{path.name} already recorded (write-once); nothing changed')
            return path
        old_bytes = path.read_bytes()
        old = json.loads(old_bytes)
        old_games = old['games']
        if now >= first_kickoff([{'gameday': g['gameday'], 'gametime': g.get('gametime')} for g in old_games]):
            raise SystemExit(f'{path.name}: --supersede refused, the first game has kicked off')
        superseded = {'sha256': hashlib.sha256(old_bytes).hexdigest(), 'recorded_at': old['recorded_at'], 'schema_version': old.get('schema_version'),
                      'reason': 'candidate set included non-active players (RES/DEV/practice squad) and non-starting QBs, diluting teammate first/last/king shares; gated on injury_context roster_status'}
    profiles = history['profiles']
    recipe = load_recipe()
    cutoff = max((p['scoring_role']['as_of'] for p in profiles.values() if p.get('scoring_role')), default=None)
    current = json.loads((ROOT / 'data/injury_context.json').read_text(encoding='utf-8')).get('current_players', {})
    current = {v['gsis_id']: v for v in current.values() if v.get('gsis_id')}
    payload = {'schema_version': SCHEMA_VERSION, 'candidate_gate': GATE_VERSION, 'status': 'SHADOW', 'season': season, 'week': week, 'recorded_at': now.isoformat(timespec='seconds'), 'slate_on_or_after': on_or_after,
               'data_cutoff': {'history_generated_at': history.get('generated_at'), 'latest_game_used': cutoff, 'rule': 'scoring_role uses games strictly before the history build date'},
               'recipe': {'file': 'config/td_shadow_recipe.json', 'version': recipe['version']},
               'population_note': 'candidates: profiles with scoring_role confidence ok, atd status ready, injury_context roster_status ACT (no entry: latest appearance within 28 days), QBs only if depth-chart QB1 or rush share >= 5%; availability/inactives are NOT modelled (probabilities are conditional on '
                                  'the candidate set; settle records who appeared)',
               'games': build_week(profiles, games, recipe, on_or_after, current)}
    if superseded:
        payload['supersedes'] = superseded
        path.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:  # write-once
        json.dump(payload, handle, separators=(',', ':'), allow_nan=False)
    print(f"{path.name}: {len(payload['games'])} games, {sum(len(g['candidates']) for g in payload['games'])} player rows")
    return path


def td_outcomes(rows):
    """game_id -> {n_td, first, last, longest: {players, yards}, scorers} from play rows (same event rules as the research: no 2-pt tries, no nullified plays)."""
    events = []
    for r in rows:
        if r.get('season_type', 'REG') != 'REG' or r.get('touchdown') != 1 or r.get('two_point_attempt') == 1 or r.get('play_deleted') == 1 or r.get('play_type') == 'no_play' or not r.get('td_team'):
            continue
        returned = r.get('kickoff_attempt') == 1 or r.get('punt_attempt') == 1
        defense = not returned and r['td_team'] != r.get('posteam')
        dist = r.get('return_yards') if returned or defense else r.get('yards_gained')
        if defense and r.get('fumble') == 1:
            dist = next((r.get(f'fumble_recovery_{i}_yards') for i in (1, 2) if r.get(f'fumble_recovery_{i}_team') == r['td_team']), dist)
        valid = isinstance(dist, (int, float)) and math.isfinite(dist) and 0 <= dist <= 109
        events.append({'game_id': r['game_id'], 'play_id': r['play_id'], 'team': r['td_team'], 'player': r.get('td_player_id'), 'yards': dist if valid else None})
    events.sort(key=lambda e: (e['game_id'], e['play_id']))
    out = {}
    for e in events:
        out.setdefault(e['game_id'], []).append(e)
    result = {}
    for gid, evs in out.items():
        yards = [e['yards'] for e in evs if e['yards'] is not None]
        top = max(yards) if yards else None
        result[gid] = {'n_td': len(evs), 'first': {'player': evs[0]['player'], 'team': evs[0]['team']}, 'last': {'player': evs[-1]['player'], 'team': evs[-1]['team']},
                       'longest': {'yards': top, 'players': sorted({e['player'] for e in evs if e['yards'] == top and e['player']}) if top is not None else []},
                       'scorers': sorted({e['player'] for e in evs if e['player']})}
    return result


def settle(now=None):
    import nflreadpy as nfl
    import polars as pl
    now = now or datetime.now(timezone.utc)
    for path in sorted(OUT.glob('*-week-*.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        if payload.get('settlement'):
            continue
        season = payload['season']
        schedule = {g['game_id']: g for g in nfl.load_schedules([season]).to_dicts()}
        ids = [g['game_id'] for g in payload['games']]
        if any(schedule.get(i, {}).get('home_score') is None for i in ids):
            print(f'{path.name}: games not final yet')
            continue
        frame = nfl.load_pbp([season]).filter(pl.col('game_id').is_in(ids))
        rows = frame.select([c for c in TD_COLUMNS if c in frame.columns]).to_dicts()
        ended = {r['game_id'] for r in rows if r.get('game_seconds_remaining') == 0}
        if set(ids) - ended:
            print(f'{path.name}: play-by-play not complete yet')
            continue
        outcomes = td_outcomes(rows)
        roster = nfl.load_rosters([season]).to_dicts()
        snaps = scoring_role.snap_share_map(roster, nfl.load_snap_counts([season]).to_dicts())
        week = payload['week']
        games = {}
        for g in payload['games']:
            o = outcomes.get(g['game_id'], {'n_td': 0, 'first': None, 'last': None, 'longest': {'yards': None, 'players': []}, 'scorers': []})
            weight = 1 / len(o['longest']['players']) if o['longest']['players'] else 0
            games[g['game_id']] = dict(o, players={c['player_id']: {
                'appeared': bool(snaps.get((c['player_id'], season, week), 0) > 0 or c['player_id'] in o['scorers']),
                'anytime': c['player_id'] in o['scorers'], 'first': bool(o['first'] and o['first']['player'] == c['player_id']),
                'last': bool(o['last'] and o['last']['player'] == c['player_id']), 'king': weight if c['player_id'] in o['longest']['players'] else 0.0} for c in g['candidates']})
        payload['settlement'] = {'settled_at': now.isoformat(timespec='seconds'), 'source': 'nflverse play-by-play, snap counts', 'games': games}
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False), encoding='utf-8')
        os.replace(tmp, path)
        print(f'{path.name}: settled {len(games)} games')


if __name__ == '__main__':
    command = sys.argv[1:2]
    if command == ['record']:
        args = [a for a in sys.argv[2:] if a != '--supersede']
        record(args[0] if args else None, supersede='--supersede' in sys.argv)
    elif command == ['settle']:
        settle()
    else:
        raise SystemExit(__doc__)
