#!/usr/bin/env python3
"""Prospective, write-once SHADOW capture of the P5-2 game-total forecasts for unstarted 2026 games (research only; shown to no one).

For every game of 2026 Weeks 6-10 that has NOT started and has a posted total, record BEFORE kickoff: the raw Champion trailing average (CH_RAW), the simple baselines
(B_PTS, B_NFL), the Challenger with Fantasy Points pace (C_FP), and the matched market price, together with source hashes, per-source feature cutoffs, exclusions and the
real capture time. A forecast is never created after kickoff and never overwritten: capture files are created exclusively and chained in an append-only ledger.

    python scripts/fp_shadow.py capture [--root FantasyPoints] [--out DIR] [--weeks 6-10] [--dry-run [--now ISO]]
    python scripts/fp_shadow.py settle  [--out DIR]       append outcomes from final scores (never edits a capture)
    python scripts/fp_shadow.py score   [--out DIR]       aggregate Brier of each model vs the market on settled captures
    python scripts/fp_shadow.py receipt [--out DIR] --to FILE   credential-free hashes/timestamps only (no probabilities, no licensed values)
    python scripts/fp_shadow.py verify  [--out DIR]       check the ledger chain and every capture hash

Capture files hold values derived from licensed Fantasy Points data, so the default directory is private (outside Git) and a path inside the repository is refused.
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[1]
SCHEMA = 'going-fp-shadow-v1'
MIN_LEAD_MINUTES = 30
MAX_MARKET_AGE_HOURS = 6
SEASON = 2026
MODELS = ('CH_RAW', 'B_PTS', 'B_NFL', 'C_FP')


class ShadowError(RuntimeError):
    pass


def default_out():
    return Path(os.environ.get('GOING_FP_SHADOW') or Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'GOING' / 'private' / 'fp-shadow')


def check_out_dir(out):
    out = Path(out).resolve()
    if out == REPO or REPO in out.parents:
        raise ShadowError('refusing to write licensed-derived captures inside the Git checkout')
    return out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def parse_time(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)


def american_to_decimal(price):
    return 1 + price / 100 if price > 0 else 1 + 100 / abs(price)


def devig_over(over_odds, under_odds):
    """Proportional (multiplicative) de-vig of a two-way price. Records the method; not the probit used by the archive comparison."""
    o, u = 1 / american_to_decimal(over_odds), 1 / american_to_decimal(under_odds)
    return o / (o + u), o + u


def _num(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else float(x)


# ------------------------------------------------------------------ pure capture logic (tested without private data)
def plan_captures(games, features, fitted, now, *, market_generated_at, market_sha256, source_hashes, cutoffs, weeks=(6, 10), code_sha=None, spec_sha=None, max_market_age_hours=MAX_MARKET_AGE_HOURS):
    """Returns (records, exclusions). Nothing is written here.

    games: iterable of dicts from data/nfl_betting.json. features: {game_id: {pts6_offset: exp_total, nfl_plays6.., fp_..}} (lagged, same season).
    fitted: {model: (predictor(feature_dict_without_line)->r_hat or None, sigma)}.
    """
    records, exclusions = [], []
    market_age_h = (now - parse_time(market_generated_at)).total_seconds() / 3600
    for g in games:
        gid = g['game_id']

        def skip(reason):
            exclusions.append({'game_id': gid, 'week': g.get('week'), 'reason': reason})

        if g.get('season') != SEASON or not (weeks[0] <= g.get('week', 0) <= weeks[1]):
            continue
        if g.get('completed') or g.get('home_score') is not None or g.get('away_score') is not None:
            skip('already_played')
            continue
        kickoff = parse_time(g['kickoff'])
        if kickoff - now < timedelta(minutes=MIN_LEAD_MINUTES):
            skip('started_or_less_than_%d_min_to_kickoff' % MIN_LEAD_MINUTES)
            continue
        if g.get('total') is None or g.get('over_odds') is None or g.get('under_odds') is None:
            skip('no_matched_market_price')
            continue
        if market_age_h > max_market_age_hours:
            skip('market_snapshot_older_than_%gh' % max_market_age_hours)
            continue
        f = features.get(gid)
        if not f or _num(f.get('exp_total')) is None:
            skip('fewer_than_3_prior_same_season_games')
            continue
        line = float(g['total'])
        p_mkt, overround = devig_over(g['over_odds'], g['under_odds'])
        feats = {'pts6': f['exp_total'] - line, **{k: _num(f.get(k)) for k in ('nfl_plays6', 'nfl_pass6', 'fp_snaps6', 'fp_pass6', 'fp_neutral6')}}
        forecasts = {}
        for name in MODELS:
            predictor, sigma = fitted[name]
            r_hat = predictor(feats)
            if r_hat is None or not math.isfinite(r_hat):
                forecasts[name] = None
            else:
                forecasts[name] = {'expected_total': line + float(r_hat), 'p_over': 0.5 * math.erfc(-(r_hat / sigma) / math.sqrt(2)), 'sigma': sigma}
        records.append({
            'schema': SCHEMA, 'game_id': gid, 'season': SEASON, 'week': g['week'], 'away': g['away'], 'home': g['home'], 'kickoff': kickoff.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'captured_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'status': 'pregame_prospective_capture',
            'market': {'line': line, 'over_odds': g['over_odds'], 'under_odds': g['under_odds'], 'p_over_devig_proportional': p_mkt, 'overround': overround,
                       'source_generated_at': market_generated_at, 'source_sha256': market_sha256, 'note': 'single-provider consensus board from data/nfl_betting.json; not the multi-book archive board'},
            'forecasts': forecasts, 'feature_hash': sha256_text(canonical({k: _num(v) for k, v in feats.items()})), 'feature_cutoffs': cutoffs.get(gid, {}),
            'source_hashes': source_hashes, 'code_sha': code_sha, 'protocol_spec_sha256': spec_sha,
            'timestamps': {'market_snapshot': market_generated_at, 'forecast_created': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'bookmaker_update': None,
                           'features_available_through': cutoffs.get(gid, {})}})
    return records, exclusions


def _ledger_entries(out):
    path = out / 'ledger.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


def write_once(out, record, clock=lambda: datetime.now(timezone.utc)):
    """Create the capture exclusively and chain it. Returns 'written' or a reason it was not. Never overwrites and never writes after kickoff."""
    out = check_out_dir(out)
    (out / 'captures').mkdir(parents=True, exist_ok=True)
    path = out / 'captures' / f"{record['game_id']}.json"
    if path.exists():
        return 'already_captured'
    now = clock()
    if now >= parse_time(record['kickoff']) - timedelta(minutes=MIN_LEAD_MINUTES):
        return 'refused_too_late'  # time passed between planning and writing: never record a forecast as if it were pregame
    record = {**record, 'captured_at': now.strftime('%Y-%m-%dT%H:%M:%SZ')}
    body = canonical(record)
    try:
        with open(path, 'x', encoding='utf-8') as f:
            f.write(body)
    except FileExistsError:
        return 'already_captured'
    os.chmod(path, 0o444)
    entries = _ledger_entries(out)
    prev = entries[-1]['entry_sha256'] if entries else '0' * 64
    entry = {'seq': len(entries) + 1, 'captured_at': record['captured_at'], 'game_id': record['game_id'], 'file_sha256': sha256_text(body), 'prev_entry_sha256': prev}
    entry['entry_sha256'] = sha256_text(canonical(entry))
    with open(out / 'ledger.jsonl', 'a', encoding='utf-8') as f:
        f.write(canonical(entry) + '\n')
    return 'written'


def verify(out):
    out = Path(out)
    problems, prev = [], '0' * 64
    entries = _ledger_entries(out)
    for e in entries:
        body = {k: v for k, v in e.items() if k != 'entry_sha256'}
        if e['prev_entry_sha256'] != prev or sha256_text(canonical(body)) != e['entry_sha256']:
            problems.append(f"ledger break at seq {e['seq']}")
        prev = e['entry_sha256']
        path = out / 'captures' / f"{e['game_id']}.json"
        if not path.exists() or sha256_text(path.read_text(encoding='utf-8')) != e['file_sha256']:
            problems.append(f"capture {e['game_id']} missing or modified")
    extra = {p.stem for p in (out / 'captures').glob('*.json')} - {e['game_id'] for e in entries} if (out / 'captures').exists() else set()
    problems += [f'capture {g} is not in the ledger' for g in sorted(extra)]
    return {'entries': len(entries), 'problems': problems, 'ok': not problems}


# ------------------------------------------------------------------ loading real inputs (private data required)
def load_inputs(root):
    from trend_research import experiments14 as e14, ledger
    games_tbl, tg = e14.team_games(root)
    g = e14.game_features(games_tbl, tg)
    dev = g[g.season.isin([2021, 2022, 2023]) & g.total_line.notna() & g.total.notna()].copy()
    dev['pts6'] = dev.exp_total - dev.total_line
    dev = dev.dropna(subset=e14.FEATS['C_FP'])
    raw = e14._fit_totals(dev)
    fitted = {}
    for name in MODELS:
        model, sigma = raw[name]
        cols = ['pts6'] if name == 'CH_RAW' else e14.FEATS[name]

        def predictor(feats, model=model, cols=cols, name=name):
            vals = [feats.get(c) for c in cols]
            if any(v is None or not math.isfinite(v) for v in vals):
                return None
            return vals[0] if name == 'CH_RAW' else float(model.predict(__import__('numpy').array([vals], float))[0])
        fitted[name] = (predictor, sigma)
    cur = g[g.season == SEASON]
    features, cutoffs = {}, {}
    for r in cur.itertuples():
        features[r.game_id] = {'exp_total': None if r.exp_total != r.exp_total else float(r.exp_total), **{c: getattr(r, c) for c in ('nfl_plays6', 'nfl_pass6', 'fp_snaps6', 'fp_pass6', 'fp_neutral6')}}
        prior = tg[(tg.season == SEASON) & (tg.week < r.week) & tg.team.isin([r.home, r.away])]
        cutoffs[r.game_id] = {'scores_through_week': {t: _last(prior, t, 'pf') for t in (r.home, r.away)}, 'nflverse_weekly_through_week': {t: _last(prior, t, 'nfl_plays') for t in (r.home, r.away)},
                              'fantasy_points_run_pass_through_week': {t: _last(prior, t, 'fp_snaps') for t in (r.home, r.away)}, 'window_games': e14.WINDOW, 'min_prior_games': e14.MIN_PRIOR}
    cache = Path(root) / 'research' / 'cache'
    hashes = {'games_csv_sha256': sha256_file(cache / 'games.csv'), 'stats_player_week_2026_sha256': sha256_file(cache / 'stats_player_week_2026.csv'),
              'fantasy_points_manifest_index_sha256': sha256_file(Path(root) / 'manifests' / 'index.json')}
    book = ledger.load()
    spec_sha = book['experiments']['P5-2']['spec_sha256']
    return features, fitted, cutoffs, hashes, spec_sha


def _last(frame, team, col):
    sub = frame[(frame.team == team) & frame[col].notna()]
    return None if sub.empty else int(sub.week.max())


def git_sha():
    try:
        return subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=20, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def board_from_git(ref='origin/main', path='data/nfl_betting.json', fetch=True):
    """Latest published game-line board without touching the working tree: fetch (read-only network call to the project's own remote) then read the blob. Returns bytes."""
    if fetch:
        subprocess.run(['git', '-C', str(REPO), 'fetch', '-q', 'origin', ref.split('/', 1)[-1]], check=True, timeout=120)
    return subprocess.run(['git', '-C', str(REPO), 'show', f'{ref}:{path}'], check=True, capture_output=True, timeout=60).stdout


def capture(root, out, *, weeks=(6, 10), dry_run=False, now=None, results_path=REPO / 'data' / 'nfl_betting.json', max_market_age_hours=MAX_MARKET_AGE_HOURS, market_bytes=None):
    out = check_out_dir(out)
    if now is not None and not dry_run:
        raise ShadowError('--now is only allowed with --dry-run: a real capture always uses the wall clock')
    now = now or datetime.now(timezone.utc)
    market_text = market_bytes if market_bytes is not None else Path(results_path).read_bytes()
    market = json.loads(market_text)
    features, fitted, cutoffs, hashes, spec_sha = load_inputs(root)
    records, exclusions = plan_captures(market['games'], features, fitted, now, market_generated_at=market['generated_at'], market_sha256=hashlib.sha256(market_text).hexdigest(),
                                        source_hashes=hashes, cutoffs=cutoffs, weeks=weeks, code_sha=git_sha(), spec_sha=spec_sha, max_market_age_hours=max_market_age_hours)
    results = {}
    for rec in records:
        results[rec['game_id']] = 'dry_run' if dry_run else write_once(out, rec)
    report = {'captured_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'dry_run': dry_run, 'results': results, 'exclusions': exclusions,
              'counts': {s: sum(1 for v in results.values() if v == s) for s in set(results.values())}}
    if not dry_run:
        (out / 'runs').mkdir(parents=True, exist_ok=True)
        run_path = out / 'runs' / f"{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        if not run_path.exists():
            run_path.write_text(canonical(report), encoding='utf-8')
    return report


# ------------------------------------------------------------------ settlement and scoring (never edits a capture)
def settle(out, results_path=REPO / 'data' / 'nfl_betting.json'):
    out = check_out_dir(out)
    final = {g['game_id']: g for g in json.loads(Path(results_path).read_text(encoding='utf-8'))['games'] if g.get('completed') is True
             and isinstance(g.get('home_score'), (int, float)) and isinstance(g.get('away_score'), (int, float))}
    (out / 'settled').mkdir(parents=True, exist_ok=True)
    done = {}
    for path in sorted((out / 'captures').glob('*.json')):
        rec = json.loads(path.read_text(encoding='utf-8'))
        target = out / 'settled' / path.name
        if rec['game_id'] not in final:
            done[rec['game_id']] = 'not_final'
            continue
        if target.exists():
            done[rec['game_id']] = 'already_settled'
            continue
        g = final[rec['game_id']]
        total = g['home_score'] + g['away_score']
        y = None if total == rec['market']['line'] else int(total > rec['market']['line'])
        with open(target, 'x', encoding='utf-8') as f:
            f.write(canonical({'game_id': rec['game_id'], 'capture_file_sha256': sha256_text(path.read_text(encoding='utf-8')), 'total': total, 'y_over': y,
                               'push': y is None, 'settled_from': 'data/nfl_betting.json final score'}))
        done[rec['game_id']] = 'settled'
    return done


def score(out):
    import numpy as np
    out = Path(out)
    rows = []
    for path in sorted((out / 'settled').glob('*.json')):
        s = json.loads(path.read_text(encoding='utf-8'))
        if s['y_over'] is None:
            continue
        rec = json.loads((out / 'captures' / path.name).read_text(encoding='utf-8'))
        row = {'y': s['y_over'], 'MKT': rec['market']['p_over_devig_proportional']}
        for m in MODELS:
            row[m] = rec['forecasts'][m]['p_over'] if rec['forecasts'].get(m) else None
        rows.append(row)
    result = {'settled_non_push': len(rows), 'models': {}}
    if not rows:
        return result
    from trend_research.experiments5 import _cluster_ci
    for m in MODELS:
        ok = [r for r in rows if r[m] is not None]
        if not ok:
            continue
        y = np.array([r['y'] for r in ok], float)
        pm, pn = np.array([r['MKT'] for r in ok]), np.array([r[m] for r in ok])
        gain = (pm - y) ** 2 - (pn - y) ** 2
        mean, lo, hi = _cluster_ci(gain, np.arange(len(ok)), 0.95) if len(ok) > 2 else (float(gain.mean()), None, None)
        result['models'][m] = {'n': len(ok), 'brier_market': float(((pm - y) ** 2).mean()), 'brier_model': float(((pn - y) ** 2).mean()), 'brier_gain_vs_market': [mean, lo, hi]}
    return result


def receipt(out):
    out = Path(out)
    entries = _ledger_entries(out)
    games = []
    for e in entries:
        rec = json.loads((out / 'captures' / f"{e['game_id']}.json").read_text(encoding='utf-8'))
        games.append({'game_id': e['game_id'], 'week': rec['week'], 'kickoff': rec['kickoff'], 'captured_at': e['captured_at'], 'file_sha256': e['file_sha256'], 'entry_sha256': e['entry_sha256'],
                      'models': sorted(k for k, v in rec['forecasts'].items() if v), 'minutes_before_kickoff': round((parse_time(rec['kickoff']) - parse_time(rec['captured_at'])).total_seconds() / 60, 1),
                      'protocol_spec_sha256': rec['protocol_spec_sha256'], 'code_sha': rec['code_sha'], 'source_hashes': rec['source_hashes']})
    return {'schema': 'going-fp-shadow-receipt-v1', 'note': 'hashes, timestamps and model names only; no probabilities, features or licensed values', 'verification': verify(out), 'captures': games}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('capture')
    c.add_argument('--root', type=Path, default=REPO / 'FantasyPoints')
    c.add_argument('--out', type=Path, default=default_out())
    c.add_argument('--weeks', default='6-10')
    c.add_argument('--market', type=Path, default=REPO / 'data' / 'nfl_betting.json', help='fresh game-line board (default: the checkout copy; use the latest origin/main data refresh)')
    c.add_argument('--market-from-git', metavar='REF', help='read the board from a git ref (for example origin/main) after fetching it, instead of the working-tree file')
    c.add_argument('--max-market-age-hours', type=float, default=MAX_MARKET_AGE_HOURS)
    c.add_argument('--dry-run', action='store_true')
    c.add_argument('--now')
    for name in ('settle', 'score', 'verify'):
        s = sub.add_parser(name)
        s.add_argument('--out', type=Path, default=default_out())
    r = sub.add_parser('receipt')
    r.add_argument('--out', type=Path, default=default_out())
    r.add_argument('--to', type=Path, required=True)
    a = p.parse_args()
    if a.cmd == 'capture':
        lo, hi = (int(x) for x in a.weeks.split('-'))
        print(json.dumps(capture(a.root, a.out, weeks=(lo, hi), dry_run=a.dry_run, now=parse_time(a.now) if a.now else None, results_path=a.market, max_market_age_hours=a.max_market_age_hours,
                                 market_bytes=board_from_git(a.market_from_git) if a.market_from_git else None), indent=1))
    elif a.cmd == 'settle':
        print(json.dumps(settle(a.out), indent=1))
    elif a.cmd == 'score':
        print(json.dumps(score(a.out), indent=1))
    elif a.cmd == 'verify':
        res = verify(a.out)
        print(json.dumps(res, indent=1))
        sys.exit(0 if res['ok'] else 1)
    else:
        a.to.write_text(json.dumps(receipt(a.out), indent=1), encoding='utf-8')
        print(f'wrote {a.to}')


if __name__ == '__main__':
    main()
