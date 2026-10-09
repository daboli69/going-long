"""Build the compact, versioned JSON files behind the GOING Charts section (public data only).

    python scripts/charts_build.py [--season 2026] [--cache-dir DIR] [--out data/charts] [--only name ...]

Inputs: data/history.json (profiles and the public `scoring_role` record), data/public_tracker (settled predictions; aggregate output only) and
public nflverse / ffverse files (weekly player stats, snap counts, players, play-by-play, ffopportunity expected points).
Licensed Fantasy Points data is never read here. Every file carries a schema, an as_of, provenance and per-field method flags:
'descriptive' (describes what happened) or 'predictive' (survived a pre-registered out-of-sample test). Nothing is flagged 'predictive' today:
research/trend-intelligence/OPPORTUNITY_VS_PRODUCTION.md (E12) found the PPR residual descriptive only.

A section whose source is unavailable is skipped and its previous file is left untouched (missing is unknown, never zero).
"""
import argparse
import hashlib
import json
import math
import numbers
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

SCHEMA_VERSION = 1
MAX_BYTES = 380_000  # hard ceiling is 400 KB; leave headroom
SKILL = ('QB', 'RB', 'WR', 'TE')
NFLVERSE = 'https://github.com/nflverse/nflverse-data/releases/download'
URLS = {
    'weekly': NFLVERSE + '/stats_player/stats_player_week_{season}.csv',
    'snaps': NFLVERSE + '/snap_counts/snap_counts_{season}.csv',
    'players': NFLVERSE + '/players/players.csv',
    'pbp': NFLVERSE + '/pbp/play_by_play_{season}.parquet',
    'ffopp': 'https://github.com/ffverse/ffopportunity/releases/download/v1.0.0-data/ep_weekly_{season}.parquet',
}
ATTRIBUTION = {
    'nflverse': 'nflverse (nflverse-data releases): weekly player stats, snap counts, rosters, play-by-play',
    'ffopportunity': 'ffverse/ffopportunity weekly expected fantasy points (release v1.0.0-data). No stated data licence beyond GPL-3 code; credit given. '
                     'The expected model was fitted on earlier seasons and is not retrained in-season.',
    'going': 'GOING data/history.json (public nflverse-derived profiles and scoring_role) and data/public_tracker (frozen predictions and public settlements)',
}


# ----------------------------------------------------------------------------------------------------------------------------- helpers
def num(v):
    return isinstance(v, numbers.Real) and not isinstance(v, bool) and math.isfinite(v)


def r(v, d=2):
    """Round a finite number; anything else is unknown (None), never zero."""
    return round(float(v), d) if num(v) else None


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def envelope(name, *, as_of, sources, method_flags, fields, notes, data, unavailable=None):
    return {
        'schema': {'id': f'going-charts/{name}', 'version': SCHEMA_VERSION, 'fields': fields},
        'as_of': as_of,
        'generated_at': None,  # filled by write_chart (kept stable while content is unchanged)
        'provenance': {'sources': sources, 'attribution': [ATTRIBUTION[k] for k in sorted({s['attribution'] for s in sources})],
                       'licensed_data_used': False},
        'method_flags': method_flags,
        'unavailable_fields': unavailable or {},
        'notes': notes,
        'data': data,
    }


def src(name, attribution, **extra):
    return dict({'name': name, 'attribution': attribution}, **extra)


def write_chart(out_dir, name, payload, now):
    """Write `<name>.json` (compact). generated_at only moves when the content changes, so identical rebuilds produce no git diff."""
    path = Path(out_dir) / f'{name}.json'
    body_key = {k: v for k, v in payload.items() if k != 'generated_at'}
    previous = None
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            previous = None
    if previous and canonical({k: v for k, v in previous.items() if k != 'generated_at'}) == canonical(body_key):
        payload['generated_at'] = previous.get('generated_at')
    else:
        payload['generated_at'] = now
    text = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    size = len(text.encode('utf-8'))
    if size > MAX_BYTES:
        raise ValueError(f'{name}.json is {size} bytes, over the {MAX_BYTES} byte budget')
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')
    return size


def fit_budget(make_payload, rows, key_rows):
    """Drop the lowest-ranked rows until the serialised payload fits the byte budget. `rows` is ordered best-first."""
    lo, hi, best = 0, len(rows), None
    while lo <= hi:
        mid = (lo + hi) // 2
        payload = make_payload(rows[:mid])
        if len(json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')) <= MAX_BYTES:
            best, lo = payload, mid + 1
        else:
            hi = mid - 1
    return best if best is not None else make_payload([])


# ----------------------------------------------------------------------------------------------------------------------------- sources
def fetch(url, cache_dir, refresh=True, timeout=180):
    """Download (or reuse) a public file. With refresh, the cache is a fallback if the network fails."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / url.rsplit('/', 1)[-1]
    if refresh or not dest.exists():
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'going-charts/1'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            tmp = dest.with_suffix(dest.suffix + '.tmp')
            tmp.write_bytes(body)
            tmp.replace(dest)
        except Exception:
            if not dest.exists():
                raise
    return dest


# ----------------------------------------------------------------------------------------------------------------------------- 1. opportunity vs production
def build_opportunity(ep, season, min_exp_pg=2.0):
    """Per skill player season-to-date expected vs actual PPR from ffopportunity rows (a pandas DataFrame; completed games only).

    expected_ppr = total_fantasy_points_exp, actual_ppr = total_fantasy_points (both PPR). residual = actual - expected.
    """
    import pandas as pd
    df = ep.copy()
    df['season'] = pd.to_numeric(df['season'], errors='coerce')
    df['week'] = pd.to_numeric(df['week'], errors='coerce')
    df = df[(df.season == season) & df.position.isin(SKILL)].dropna(subset=['week', 'total_fantasy_points_exp', 'total_fantasy_points'])
    through = int(df.week.max()) if len(df) else None
    players = []
    for pid, g in df.sort_values('week').groupby('player_id'):
        exp_l, act_l = g.total_fantasy_points_exp.tolist(), g.total_fantasy_points.tolist()
        n = len(g)
        if n < 1 or sum(exp_l) / n < min_exp_pg:
            continue
        last = g.tail(3)
        l3_exp, l3_act = last.total_fantasy_points_exp.mean(), last.total_fantasy_points.mean()
        prior = g.iloc[:-3]
        prior_res = (prior.total_fantasy_points - prior.total_fantasy_points_exp).mean() if len(prior) else None
        res = sum(act_l) - sum(exp_l)
        players.append({
            'id': pid, 'name': g.full_name.iloc[-1], 'pos': g.position.iloc[-1], 'team': g.posteam.iloc[-1], 'g': n,
            'exp': r(sum(exp_l), 1), 'act': r(sum(act_l), 1), 'res': r(res, 1),
            'exp_pg': r(sum(exp_l) / n), 'act_pg': r(sum(act_l) / n), 'res_pg': r(res / n),
            'trend3': {'exp_pg': r(l3_exp), 'act_pg': r(l3_act), 'res_pg': r(l3_act - l3_exp), 'prior_res_pg': r(prior_res),
                       'games': [[int(w), r(e, 1), r(a, 1)] for w, e, a in zip(last.week, last.total_fantasy_points_exp, last.total_fantasy_points)]},
        })
    players.sort(key=lambda p: -p['exp'])
    fields = {
        'id': 'nflverse gsis player id', 'g': 'completed regular-season games with an ffopportunity row', 'exp': 'season-to-date expected PPR points',
        'act': 'season-to-date actual PPR points (same source as exp)', 'res': 'act - exp', 'exp_pg/act_pg/res_pg': 'per-game values',
        'trend3': 'last up to 3 games: per-game exp/act/res, the residual per game over earlier games (prior_res_pg), and [week, exp, act] rows',
    }
    flags = {'exp': 'descriptive', 'act': 'descriptive', 'res': 'descriptive', 'trend3': 'descriptive'}
    notes = [
        'Residual is descriptive. E12 (research/trend-intelligence/OPPORTUNITY_VS_PRODUCTION.md) found no pre-registered out-of-sample forecasting use after controlling for workload and production.',
        'Touchdowns dominate the residual in small samples. A player missing from the source is unknown, not zero.',
        f'Players with under {min_exp_pg} expected PPR per game are omitted for size.',
    ]

    def make(rows):
        return envelope('opportunity_vs_production', as_of={'season': season, 'through_week': through},
                        sources=[src('ffopportunity ep_weekly', 'ffopportunity', url=URLS['ffopp'].format(season=season))],
                        method_flags=flags, fields=fields, notes=notes, data={'season': season, 'positions': list(SKILL), 'players': rows})

    return fit_budget(make, players, 'players') if players else None


# ----------------------------------------------------------------------------------------------------------------------------- 2. weekly roles
def build_weekly_roles(weekly, snaps, players_map, season, n_weeks=8):
    """Last `n_weeks` played weeks: offensive snap share, target share and carry share per skill player (arrays aligned to `weeks`; null = no data).

    weekly: nflverse stats_player_week rows; snaps: nflverse snap_counts rows; players_map: pfr_id -> gsis_id.
    """
    import pandas as pd
    w = weekly[(weekly.season == season) & (weekly.season_type == 'REG')].copy()
    if not len(w):
        return None
    weeks = sorted(int(x) for x in w.week.unique())[-n_weeks:]
    w = w[w.week.isin(weeks)]
    for c in ('targets', 'carries'):
        w[c] = w[c].fillna(0)
    team_t = w.groupby(['team', 'week']).targets.transform('sum')
    team_c = w.groupby(['team', 'week']).carries.transform('sum')
    w['tgt_share'] = (w.targets / team_t.where(team_t > 0))
    w['car_share'] = (w.carries / team_c.where(team_c > 0))
    s = snaps[(snaps.season == season) & (snaps.game_type == 'REG') & snaps.week.isin(weeks)].copy()
    s['player_id'] = s.pfr_player_id.map(players_map)
    s = s.dropna(subset=['player_id']).drop_duplicates(['player_id', 'week'])
    snap_pct = {(a, int(b)): c for a, b, c in zip(s.player_id, s.week, s.offense_pct)}
    out = []
    skill = w[w.position.isin(SKILL)].sort_values(['player_id', 'week'])
    for pid, g in skill.groupby('player_id'):
        by_week = {int(k): row for k, row in zip(g.week, g.itertuples())}
        snap = [r(snap_pct.get((pid, k)), 3) for k in weeks]
        tgt = [r(by_week[k].tgt_share, 3) if k in by_week else None for k in weeks]
        car = [r(by_week[k].car_share, 3) if k in by_week else None for k in weeks]
        sig = lambda xs, floor: any(x is not None and x >= floor for x in xs)
        pos = g.position.iloc[-1]
        if not (sig(tgt, 0.08) or sig(car, 0.12) or (pos == 'QB' and sig(snap, 0.5))):
            continue
        out.append({'id': pid, 'name': g.player_display_name.iloc[-1], 'pos': pos, 'team': g.team.iloc[-1], 'snap': snap, 'tgt': tgt, 'car': car})
    out.sort(key=lambda p: -(max([x for x in p['tgt'] if x is not None] + [0]) + max([x for x in p['car'] if x is not None] + [0])))
    fields = {'weeks': 'NFL weeks (the last N played weeks league-wide; a bye or absence is null)', 'snap': 'share of team offensive snaps (0-1)',
              'tgt': "player targets / team targets that week (0-1)", 'car': "player carries / team carries that week (0-1)",
              'routes': 'not published: route counts are not in public nflverse data'}
    flags = {'snap': 'descriptive', 'tgt': 'descriptive', 'car': 'descriptive'}
    notes = ['Descriptive usage by week. Whether recent share predicts the next game is tested separately in the validation journal, not claimed here.',
             'Team totals use every player row in the stats file for that team-week, so shares sum to <= 1 over listed players.',
             'Players are listed when they reached an 8% target share, a 12% carry share (QBs: a 50% snap share) in any listed week.']

    def make(rows):
        return envelope('weekly_roles', as_of={'season': season, 'through_week': weeks[-1]},
                        sources=[src('nflverse stats_player_week', 'nflverse', url=URLS['weekly'].format(season=season)),
                                 src('nflverse snap_counts', 'nflverse', url=URLS['snaps'].format(season=season))],
                        method_flags=flags, fields=fields, notes=notes,
                        unavailable={'routes': 'public nflverse data has no route counts; shown as absent rather than estimated'},
                        data={'season': season, 'weeks': weeks, 'players': rows})

    return fit_budget(make, out, 'players')


# ----------------------------------------------------------------------------------------------------------------------------- 3. scoring opportunity
def build_scoring_opportunity(history, season, today=None):
    """Expected vs actual touchdowns and zone usage from data/history.json `scoring_role` (rolling windows of the player's own prior appearances)."""
    profiles = (history.get('betting') or {}).get('profiles') or {}
    rows, as_ofs = [], []
    for pid, p in profiles.items():
        sr = p.get('scoring_role') or {}
        if p.get('position') not in SKILL or sr.get('confidence') != 'ok' or not sr.get('as_of'):
            continue
        if str(p.get('last_game') or '') < f'{season}-08-01':
            continue  # not active this season
        as_ofs.append(sr['as_of'])
        trend = sr.get('trend') or {}
        rows.append({'id': p.get('id', pid), 'name': p.get('name'), 'pos': p['position'], 'team': p.get('team'), 'n': sr.get('n'), 'as_of': sr['as_of'], 'tier': sr.get('tier'),
                     'xtd_pg': r(sr.get('xtd_pg_l12'), 3), 'td_pg': r(sr.get('td_pg_l12'), 3), 'td_luck': r(sr.get('td_luck_l12'), 3),
                     'xtd_pg_l6': r(sr.get('xtd_pg_l6'), 3), 'xtd_share_l6': r(sr.get('xtd_share_l6'), 3),
                     'rz_tgt_pg': r(sr.get('rz_tgt_pg_l12'), 2), 'in5_pg': r(sr.get('inside5_touch_pg_l12'), 2), 'gl_car_pg': r(sr.get('gl_carry_pg_l12'), 2),
                     'd_xtd_3v6': r(trend.get('d_xtd36'), 3)})
    if not rows:
        return None
    rows.sort(key=lambda x: -(x['xtd_pg'] or 0))
    fields = {'xtd_pg': 'expected touchdowns per game over the last up-to-12 appearances (league zone rates x carries/targets by yard line)',
              'td_pg': 'actual offensive touchdowns per game, same window', 'td_luck': 'td_pg - xtd_pg', 'xtd_pg_l6': 'expected TDs per game, last 6',
              'xtd_share_l6': "player's share of team expected TDs, last 6", 'rz_tgt_pg': 'targets inside the 20 per game, last 12',
              'in5_pg': 'carries+targets inside the 5 per game, last 12', 'gl_car_pg': 'carries inside the 2 per game, last 12',
              'd_xtd_3v6': 'xtd per game last 3 minus last 6', 'tier': 'PRIMARY/SECONDARY/TERTIARY/FRINGE by xtd_share_l6'}
    flags = dict.fromkeys(('xtd_pg', 'td_pg', 'td_luck', 'xtd_pg_l6', 'xtd_share_l6', 'rz_tgt_pg', 'in5_pg', 'gl_car_pg', 'd_xtd_3v6', 'tier'), 'descriptive')
    notes = ['Descriptive. td_luck is not a forecast of regression: the scoring_role record is a role description, and the E12 residual study found no predictive use.',
             'Windows cover the player\'s own prior appearances (they cross season boundaries), so early-season rows include last year.',
             'Inside-10 usage is not part of the scoring_role record, so it is not shown; red-zone (inside-20), inside-5 and inside-2 usage are.']

    def make(rows_):
        return envelope('scoring_opportunity', as_of={'season': season, 'player_as_of_max': max(as_ofs), 'player_as_of_min': min(as_ofs)},
                        sources=[src('GOING history scoring_role', 'going', path='data/history.json#betting.profiles[*].scoring_role')],
                        method_flags=flags, fields=fields, notes=notes,
                        unavailable={'inside_10': 'not in scoring_role; not estimated'},
                        data={'season': season, 'players': rows_})

    return fit_budget(make, rows, 'players')


# ----------------------------------------------------------------------------------------------------------------------------- 4. team trends
def build_team_trends(pbp, season):
    """Plays per game and pass rate over expectation (nflfastR xpass) by team and week; all plays and a neutral-situation subset."""
    import pandas as pd
    d = pbp[(pbp.season == season) & (pbp.season_type == 'REG') & pbp.play_type.isin(['pass', 'run']) & pbp.posteam.notna()].copy()
    if not len(d):
        return None
    d['is_pass'] = (d.play_type == 'pass').astype(int)
    d['neutral'] = (d.down.isin([1, 2])) & (d.wp.between(0.2, 0.8)) & (d.half_seconds_remaining > 120)
    weeks = sorted(int(x) for x in d.week.unique())

    def agg(frame):
        g = frame.groupby(['posteam', 'week'])
        return pd.DataFrame({'plays': g.size(), 'pass_rate': g.is_pass.mean(), 'xpass': g.xpass.mean()})

    a, n = agg(d), agg(d[d.neutral])
    teams = {}
    for team in sorted(d.posteam.unique()):
        def col(frame, name, scale=1.0, digits=3):
            return [r(frame[name].get((team, w)) * scale, digits) if (team, w) in frame.index and num(frame[name].get((team, w))) else None for w in weeks]
        proe_all = [r((pr - xp) * 100, 1) if pr is not None and xp is not None else None
                    for pr, xp in zip(col(a, 'pass_rate'), col(a, 'xpass'))]
        proe_neu = [r((pr - xp) * 100, 1) if pr is not None and xp is not None else None
                    for pr, xp in zip(col(n, 'pass_rate'), col(n, 'xpass'))]
        ta, tn = d[d.posteam == team], d[(d.posteam == team) & d.neutral]
        games = ta.game_id.nunique()
        teams[team] = {
            'plays': col(a, 'plays', 1, 0), 'pass_rate': col(a, 'pass_rate'), 'proe': proe_all, 'proe_neutral': proe_neu, 'neutral_plays': col(n, 'plays', 1, 0),
            'season': {'games': games, 'plays_pg': r(len(ta) / games, 1) if games else None, 'pass_rate': r(ta.is_pass.mean(), 3),
                       'proe': r((ta.is_pass.mean() - ta.xpass.mean()) * 100, 1) if ta.xpass.notna().any() else None,
                       'proe_neutral': r((tn.is_pass.mean() - tn.xpass.mean()) * 100, 1) if len(tn) and tn.xpass.notna().any() else None},
        }
    league = [r(d[d.week == w].is_pass.mean(), 3) for w in weeks]
    fields = {'weeks': 'NFL weeks with plays', 'plays': "team's scrimmage plays (pass+run, no penalties-only plays, kneels or spikes) that week",
              'pass_rate': 'pass plays / (pass+run), sacks count as passes', 'proe': 'pass rate minus mean nflfastR xpass, percentage points, all plays',
              'proe_neutral': 'same on neutral situations: 1st/2nd down, win probability 20-80%, more than 2 minutes left in the half',
              'season': 'season-to-date summary', 'league_pass_rate': 'league pass rate per week'}
    flags = {'plays': 'descriptive', 'pass_rate': 'descriptive', 'proe': 'descriptive', 'proe_neutral': 'descriptive', 'season': 'descriptive'}
    notes = ['PROE is relative to the nflfastR xpass model (fitted on earlier seasons), not to a GOING model. Single weeks are noisy; use season-to-date.',
             'Pass-rate persistence by game script was tested in E5 (REJECTED/no evidence of gain); this file describes, it does not forecast.']
    return envelope('team_trends', as_of={'season': season, 'through_week': weeks[-1]},
                    sources=[src('nflverse play_by_play', 'nflverse', url=URLS['pbp'].format(season=season))], method_flags=flags, fields=fields, notes=notes,
                    data={'season': season, 'weeks': weeks, 'league_pass_rate': league, 'teams': teams})


# ----------------------------------------------------------------------------------------------------------------------------- 5. model calibration
BINS = [(i / 10, (i + 1) / 10) for i in range(10)]


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [r(max(0.0, c - h), 3), r(min(1.0, c + h), 3)]


def reliability(items):
    """items: [(probability, outcome 0/1)] -> n, Brier, base rate, reference Brier, skill and 10 equal-width reliability bins."""
    n = len(items)
    if not n:
        return None
    brier = sum((p - y) ** 2 for p, y in items) / n
    base = sum(y for _, y in items) / n
    ref = base * (1 - base)
    bins = []
    for lo, hi in BINS:
        sel = [(p, y) for p, y in items if lo <= p < hi or (hi == 1.0 and p == 1.0)]
        if sel:
            k = sum(y for _, y in sel)
            bins.append({'lo': lo, 'hi': hi, 'n': len(sel), 'mean_p': r(sum(p for p, _ in sel) / len(sel), 3), 'freq': r(k / len(sel), 3), 'ci': wilson(k, len(sel))})
    return {'n': n, 'brier': r(brier, 4), 'base_rate': r(base, 3), 'brier_base_rate_ref': r(ref, 4), 'skill_vs_base_rate': r(1 - brier / ref, 3) if ref > 0 else None,
            'mean_p': r(sum(p for p, _ in items) / n, 3), 'bins': bins, 'low_n': n < 30}


def settled_items(records):
    """First pre-kickoff observation per (tracking group, canonical contract) with a win/loss settlement. Pushes/refunds/voids are excluded.

    The stored probability is the model's chance that the side wins; when the record notes a push probability it is conditioned on no push, as in calibration_audit.mjs.
    """
    settle = {}
    for rec in records:
        if rec.get('kind') == 'settlement':
            p = rec['payload']
            prev = settle.get(p.get('prediction_id'))
            if not prev or str(p.get('observed_at')) >= str(prev.get('observed_at')):
                settle[p.get('prediction_id')] = p
    seen, items, latest = set(), [], None
    preds = sorted((x for x in records if x.get('kind') == 'prediction'), key=lambda x: str(x['payload'].get('observed_at')))
    for rec in preds:
        p = rec['payload']
        s = settle.get(p.get('id') or rec.get('id'))
        if not s or s.get('status') not in ('win', 'loss'):
            continue
        if not (str(p.get('observed_at')) < str(p.get('kickoff'))):
            continue
        key = (p.get('tracking_group'), canonical(p.get('canonical_contract') or p.get('selection')))
        if key in seen:
            continue
        seen.add(key)
        push = (p.get('model_evidence') or {}).get('push') or 0
        prob = p.get('probability')
        if not num(prob) or not (0 <= push < 1):
            continue
        prob = prob / (1 - push)
        if not 0 <= prob <= 1:
            continue
        items.append({'group': p.get('tracking_group'), 'market': p.get('market'), 'contract': key[1], 'p': prob, 'y': 1 if s['status'] == 'win' else 0})
        latest = max(latest or '', str(s.get('observed_at')))
    return items, latest


def build_calibration(records):
    items, latest = settled_items(records)
    if not items:
        return None
    by_market, by_group, seen = {}, {}, set()
    unique = []  # items are in observation order, so this keeps the earliest observation of a contract that several tracking groups froze
    for it in items:
        by_group.setdefault(it['group'], []).append((it['p'], it['y']))
        if it['contract'] not in seen:
            seen.add(it['contract'])
            unique.append(it)
            by_market.setdefault(it['market'], []).append((it['p'], it['y']))
    markets = {k: reliability(v) for k, v in sorted(by_market.items())}
    groups = {k: reliability(v) for k, v in sorted(by_group.items())}
    overall = reliability([(i['p'], i['y']) for i in unique])
    fields = {'n': 'settled win/loss contracts counted once (first pre-kickoff observation; overall and markets de-duplicate across tracking groups, groups de-duplicate within the group)', 'brier': 'mean squared error of the stated probability',
              'brier_base_rate_ref': 'Brier of always predicting the observed base rate (in-sample reference)', 'skill_vs_base_rate': '1 - brier / reference',
              'bins': 'equal-width probability bins with mean predicted probability, observed frequency and Wilson 95% interval'}
    flags = {'overall': 'descriptive', 'markets': 'descriptive', 'groups': 'descriptive'}
    notes = ['Aggregate only: no player, game or price information is published here. Probabilities are the model stated at the first pre-kickoff observation.',
             'Calibration is not profitability: no odds, stakes or returns are used. Markets with n < 30 are flagged low_n and should not be read as findings.',
             'Tracking began 2026-09-20; sample is small and correlated within games and players.']
    return envelope('model_calibration', as_of={'latest_settlement_observed_at': latest}, sources=[src('GOING public tracker', 'going', path='data/public_tracker')],
                    method_flags=flags, fields=fields, notes=notes, data={'overall': overall, 'markets': markets, 'groups': groups})


# ----------------------------------------------------------------------------------------------------------------------------- orchestration
def load_history(root):
    return json.loads((Path(root) / 'data' / 'history.json').read_text(encoding='utf-8'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--season', type=int, default=int(__import__('os').environ.get('SEASON', '2026')))
    ap.add_argument('--root', default=str(ROOT))
    ap.add_argument('--out', default=None)
    ap.add_argument('--cache-dir', default=None, help='download cache (default: a temp directory next to the output, not committed)')
    ap.add_argument('--offline', action='store_true', help='reuse files already in the cache')
    ap.add_argument('--only', nargs='*', default=None)
    a = ap.parse_args(argv)
    import pandas as pd
    root = Path(a.root)
    out = Path(a.out) if a.out else root / 'data' / 'charts'
    cache = Path(a.cache_dir) if a.cache_dir else Path(__import__('tempfile').gettempdir()) / 'going-charts-cache'
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    want = lambda n: not a.only or n in a.only
    status = {}

    def run(name, fn):
        if not want(name):
            return
        try:
            payload = fn()
            if payload is None:
                status[name] = 'skipped: no data'
                return
            size = write_chart(out, name, payload, now)
            status[name] = f'ok {size} bytes'
        except Exception as exc:  # one failed source must not block the others; the previous file stays
            status[name] = f'FAILED {type(exc).__name__}: {exc}'

    def get(key):
        return fetch(URLS[key].format(season=a.season), cache, refresh=not a.offline)

    def opportunity():
        return build_opportunity(pd.read_parquet(get('ffopp')), a.season)

    def roles():
        weekly = pd.read_csv(get('weekly'), low_memory=False)
        snaps = pd.read_csv(get('snaps'), usecols=['season', 'game_type', 'week', 'pfr_player_id', 'offense_pct'])
        pl = pd.read_csv(fetch(URLS['players'], cache, refresh=not a.offline), usecols=['gsis_id', 'pfr_id']).dropna()
        return build_weekly_roles(weekly, snaps, dict(zip(pl.pfr_id, pl.gsis_id)), a.season)

    def scoring():
        return build_scoring_opportunity(load_history(root), a.season)

    def teams():
        cols = ['game_id', 'season', 'week', 'season_type', 'posteam', 'play_type', 'down', 'wp', 'half_seconds_remaining', 'xpass']
        return build_team_trends(pd.read_parquet(get('pbp'), columns=cols), a.season)

    def calibration():
        from tracker_store import load_tracker
        return build_calibration(load_tracker(root / 'data')['records'])

    run('opportunity_vs_production', opportunity)
    run('weekly_roles', roles)
    run('scoring_opportunity', scoring)
    run('team_trends', teams)
    run('model_calibration', calibration)

    # index of what exists (sizes and hashes; stable while the files are unchanged)
    index = {}
    for f in sorted(out.glob('*.json')) if out.exists() else []:
        if f.name == 'index.json':
            continue
        raw = f.read_bytes()
        doc = json.loads(raw)
        index[f.stem] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()[:16], 'as_of': doc.get('as_of'), 'schema': doc.get('schema', {}).get('id'),
                         'schema_version': doc.get('schema', {}).get('version')}
    if index:
        write_chart(out, 'index', {'schema': {'id': 'going-charts/index', 'version': SCHEMA_VERSION, 'fields': {'files': 'published chart files'}}, 'as_of': None,
                                    'generated_at': None, 'files': index}, now)
    for k, v in status.items():
        print(f'[charts] {k}: {v}')
    return 1 if any(v.startswith('FAILED') for v in status.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
