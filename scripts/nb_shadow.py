"""Prospective SHADOW: NB1 (variance = c * mean) vs production Poisson for RECEPTIONS props. Never feeds production.

  fit <champion_2021_2025.parquet>   fit c on 2021-2023 only (blend mean c=2), writes config/nb_shadow.json
  record [date] [--now ISO]          write-once data/nb_shadow/<season>-week-NN.json for props with kickoff on/after date (ET)
  settle                             write <file>-outcomes.json for files whose games are all final; summary only with >= MIN_SUMMARY rows
Uses only data already in the repo (nfl_betting.json, history.json, results.json). Rows whose kickoff (or the history cutoff) is not strictly after
the recording time are rejected, so a recorded probability can never have seen the game.
"""
import argparse
import json
import math
import re
import statistics
import sys
import unicodedata
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'nb-shadow-1'
MIN_SUMMARY = 30


# ------------------------------------------------------------------ distributions
def poisson_cdf(k, mean):
    if k < 0:
        return 0.0
    if mean <= 0:
        return 1.0
    k = int(math.floor(k))
    term = math.exp(-mean)
    total = term
    for i in range(1, k + 1):
        term *= mean / i
        total += term
    return min(1.0, total)


def nb1_cdf(k, mean, c):
    """NB with mean `mean` and variance c*mean (c > 1): size r = mean/(c-1), success prob 1/c. Exact pmf recurrence."""
    if k < 0:
        return 0.0
    if mean <= 0:
        return 1.0
    if not c > 1:
        return poisson_cdf(k, mean)
    k = int(math.floor(k))
    r = mean / (c - 1.0)
    q = 1.0 - 1.0 / c
    term = math.exp(r * math.log(1.0 / c))
    total = term
    for i in range(k):
        term *= (i + r) / (i + 1.0) * q
        total += term
    return min(1.0, total)


def p_over(cdf, line, *args):
    """P(X > line); an integer line's push is excluded from over."""
    return 1.0 - cdf(math.floor(line), *args)


# ------------------------------------------------------------------ helpers
def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def parse_ts(text):
    value = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def et_date(text):
    """ET calendar date of a timestamp."""
    ts = parse_ts(text)
    try:
        from zoneinfo import ZoneInfo
        return ts.astimezone(ZoneInfo('America/New_York')).date()
    except Exception:  # no tzdata: US Eastern DST approximation (2nd Sun Mar - 1st Sun Nov)
        year = ts.year
        march = Date(year, 3, 8) + timedelta(days=(6 - Date(year, 3, 8).weekday()) % 7)
        nov = Date(year, 11, 1) + timedelta(days=(6 - Date(year, 11, 1).weekday()) % 7)
        offset = -4 if march <= ts.date() < nov else -5
        return (ts.astimezone(timezone.utc) + timedelta(hours=offset)).date()


def median_line(lines):
    """Median line across books; an even count takes the lower middle value so the result stays a posted line."""
    return statistics.median_low(sorted(lines))


def norm_name(name):
    text = re.sub(r'\s*\([A-Za-z]{2,4}\)\s*$', '', str(name))
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r'[^a-z0-9 ]', '', text).strip()
    text = re.sub(r'\s+', ' ', text)
    return re.sub(r'\s+(jr|sr|ii|iii|iv|v)$', '', text)


def resolve_profile(prop, history):
    aliases, profiles = history.get('aliases', {}), history.get('profiles', {})
    hit = aliases.get(f"{prop['eventId']}|{norm_name(prop['player'])}")
    if hit and hit.get('player_id') in profiles:
        return hit['player_id']
    key = norm_name(prop['player'])
    matches = [pid for pid, p in profiles.items() if p.get('name_key') == key or norm_name(p.get('name', '')) == key]
    return matches[0] if len(matches) == 1 else None


def find_game(games, team, kickoff_ts):
    for game in games:
        if team in (game.get('home'), game.get('away')) and abs((parse_ts(game['kickoff']) - kickoff_ts).total_seconds()) < 36 * 3600:
            return game
    return None


# ------------------------------------------------------------------ record
def build_rows(betting, history, config, since, now):
    """Returns ({(season, week): rows}, {reason: count})."""
    rejected = {}

    def reject(reason):
        rejected[reason] = rejected.get(reason, 0) + 1

    cutoff_ts = parse_ts(history['generated_at'])
    groups = {}
    for prop in betting.get('props', []):
        if prop.get('market') != 'receptions' or not isinstance(prop.get('line'), (int, float)) or not prop.get('kickoff'):
            continue
        if et_date(prop['kickoff']) < since:
            continue
        groups.setdefault((prop['eventId'], norm_name(prop['player'])), []).append(prop)
    out = {}
    for (event, _), props in sorted(groups.items()):
        first = props[0]
        kickoff_ts = parse_ts(first['kickoff'])
        if kickoff_ts <= now:
            reject('kickoff_not_after_recording_time')
            continue
        if cutoff_ts >= kickoff_ts:
            reject('history_cutoff_not_before_kickoff')
            continue
        pid = resolve_profile(first, history)
        profile = history['profiles'].get(pid) if pid else None
        model = (profile or {}).get('stats', {}).get('receptions') or {}
        if not profile or not model.get('policy') or not isinstance(model.get('mean'), (int, float)):
            reject('no_champion_v2_receptions_mean')
            continue
        mean = float(model['mean'])
        line = float(median_line([p['line'] for p in props]))
        game = find_game(betting.get('games', []), profile.get('team'), kickoff_ts)
        if not game or game.get('season') is None:
            reject('game_not_matched')
            continue
        c = config['c']
        row = {'player': first['player'], 'profile_id': pid, 'team': profile.get('team'), 'position': profile.get('position'), 'event_id': event,
               'game_id': game['game_id'], 'line': line, 'n_books': len({p.get('bookKey') for p in props}),
               'line_min': min(p['line'] for p in props), 'line_max': max(p['line'] for p in props),
               'mean': mean, 'policy': model['policy'], 'p_over_poisson': p_over(poisson_cdf, line, mean), 'p_over_nb1': p_over(nb1_cdf, line, mean, c),
               'kickoff': first['kickoff'], 'et_date': et_date(first['kickoff']).isoformat()}
        out.setdefault((game['season'], game['week']), []).append(row)
    return out, rejected


def record(since, now=None, root=ROOT):
    now = now or datetime.now(timezone.utc)
    config = load(root / 'config' / 'nb_shadow.json')
    betting, history = load(root / 'data' / 'nfl_betting.json'), load(root / 'data' / 'history.json')['betting']
    weeks, rejected = build_rows(betting, history, config, since, now)
    outdir = root / 'data' / 'nb_shadow'
    targets = {w: outdir / f'{w[0]}-week-{w[1]:02d}.json' for w in weeks}
    clash = [p.name for p in targets.values() if p.exists()]
    if clash:
        raise FileExistsError(f'write-once: {clash} already recorded; nothing written')
    outdir.mkdir(parents=True, exist_ok=True)
    for week, rows in weeks.items():
        doc = {'version': VERSION, 'season': week[0], 'week': week[1], 'recorded_at': now.isoformat(), 'data_cutoff': history['generated_at'],
               'betting_generated_at': betting.get('generated_at'), 'champion_policy': sorted({r['policy'] for r in rows}), 'nb1_c': config['c'],
               'config_version': config.get('version'), 'models': {'baseline': 'Poisson(mean)', 'shadow': f"NB1 variance = {config['c']} * mean"},
               'rows': sorted(rows, key=lambda r: (r['kickoff'], r['player']))}
        with open(targets[week], 'x', encoding='utf8') as handle:  # 'x': refuses to overwrite even under a race
            handle.write(json.dumps(doc, indent=1))
    return {'files': [p.name for p in targets.values()], 'rows': sum(len(r) for r in weeks.values()), 'rejected': rejected}


# ------------------------------------------------------------------ settle
def calibration_slope(p, y):
    xs = []
    for v in p:
        v = min(max(v, 1e-6), 1 - 1e-6)
        xs.append(math.log(v / (1 - v)))
    a, b = 0.0, 1.0
    for _ in range(50):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, t in zip(xs, y):
            q = 1 / (1 + math.exp(-(a + b * x)))
            w = q * (1 - q)
            g0 += q - t
            g1 += (q - t) * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            return None
        da, db = (h11 * g0 - h01 * g1) / det, (h00 * g1 - h01 * g0) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-9:
            break
    return {'intercept': a, 'slope': b}


def summarize(rows):
    live = [r for r in rows if r.get('actual') is not None and r['actual'] != r['line']]
    if len(live) < MIN_SUMMARY:
        return None
    y = [1.0 if r['actual'] > r['line'] else 0.0 for r in live]
    out = {'n': len(live)}
    for name in ('poisson', 'nb1'):
        p = [min(max(r[f'p_over_{name}'], 1e-6), 1 - 1e-6) for r in live]
        out[name] = {'brier': sum((a - b) ** 2 for a, b in zip(p, y)) / len(y),
                     'logloss': -sum(t * math.log(a) + (1 - t) * math.log(1 - a) for a, t in zip(p, y)) / len(y),
                     'mean_p_over': sum(p) / len(p), 'calibration': calibration_slope(p, y)}
    out['actual_over_rate'] = sum(y) / len(y)
    out['brier_nb1_minus_poisson'] = out['nb1']['brier'] - out['poisson']['brier']
    out['logloss_nb1_minus_poisson'] = out['nb1']['logloss'] - out['poisson']['logloss']
    return out


def settle(root=ROOT):
    betting, results = load(root / 'data' / 'nfl_betting.json'), load(root / 'data' / 'results.json')
    final = {g['game_id']: bool(g.get('completed')) for g in betting.get('games', [])}
    report = []
    for path in sorted((root / 'data' / 'nb_shadow').glob('*-week-[0-9][0-9].json')):
        target = path.with_name(path.stem + '-outcomes.json')
        if target.exists():
            report.append((path.name, 'already settled'))
            continue
        doc = load(path)
        pending = sorted({r['game_id'] for r in doc['rows'] if not final.get(r['game_id'])})
        if pending:
            report.append((path.name, f'waiting on {len(pending)} games'))
            continue
        rows, missing = [], 0
        for r in doc['rows']:
            rec = results['players'].get(f"{r['profile_id']}|{r['et_date']}")
            actual = rec.get('receptions') if rec else None
            missing += actual is None
            rows.append({**{k: r[k] for k in ('player', 'profile_id', 'line', 'p_over_poisson', 'p_over_nb1')}, 'actual': actual})
        summary = summarize(rows)
        with open(target, 'x', encoding='utf8') as handle:
            handle.write(json.dumps({'version': VERSION, 'source_file': path.name, 'settled_at': datetime.now(timezone.utc).isoformat(),
                                     'results_generated_at': results.get('generated_at'), 'no_result_rows': missing, 'summary': summary,
                                     'summary_note': None if summary else f'fewer than {MIN_SUMMARY} settled rows', 'rows': rows}, indent=1))
        report.append((path.name, f'settled, {len(rows) - missing} with results'))
    return report


# ------------------------------------------------------------------ fit
def fit(parquet, root=ROOT):
    import numpy as np
    import pandas as pd
    from scipy.optimize import minimize_scalar
    from scipy.stats import nbinom, poisson
    f = pd.read_parquet(parquet)
    f = f[f.ready & f.position.isin(['WR', 'TE', 'RB'])].dropna(subset=['champ_receptions', 'y_receptions'])
    cur, prior, k = f['cur_receptions'].to_numpy(float), f['prior_receptions'].to_numpy(float), f['k'].to_numpy(float)
    mu = np.maximum(np.where(np.isnan(cur), prior, np.where(np.isnan(prior), cur, (k * np.nan_to_num(cur) + 2 * np.nan_to_num(prior)) / (k + 2))), 0.01)
    dev = (f.season <= 2023).to_numpy()
    y = f['y_receptions'].to_numpy(float)

    def ll(a):
        n = mu[dev] / a
        return nbinom.logpmf(y[dev], n, n / (n + mu[dev])).mean()
    res = minimize_scalar(lambda a: -ll(a), bounds=(1e-4, 3), method='bounded')
    pois = float(poisson.logpmf(y[dev], mu[dev]).mean())
    doc = {'version': 'nb-shadow-config-1', 'market': 'receptions', 'family': 'nb1', 'definition': 'variance = c * mean, c = 1 + a',
           'a': float(res.x), 'c': round(1 + float(res.x), 4),
           'fit': {'data': 'nflverse-derived champion rows 2021-2023 only', 'mean': 'blend c=2', 'n_rows': int(dev.sum()),
                   'loglik_nb1': -float(res.fun), 'loglik_poisson': pois, 'delta_nats_per_row': -float(res.fun) - pois}}
    (root / 'config' / 'nb_shadow.json').write_text(json.dumps(doc, indent=1), encoding='utf8')
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('record')
    r.add_argument('date', nargs='?')
    r.add_argument('--now')
    sub.add_parser('settle')
    f = sub.add_parser('fit')
    f.add_argument('parquet')
    args = ap.parse_args(argv)
    if args.cmd == 'record':
        since = Date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
        print(json.dumps(record(since, parse_ts(args.now) if args.now else None), indent=1))
    elif args.cmd == 'settle':
        for name, status in settle():
            print(name, status)
    else:
        print(json.dumps(fit(args.parquet), indent=1))


if __name__ == '__main__':
    sys.exit(main())
