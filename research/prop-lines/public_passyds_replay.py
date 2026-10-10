#!/usr/bin/env python3
"""Fixed-model replay using PUBLIC Git snapshots only; never reads private caches.

Run after freezing CONTINUATION_PROTOCOL.json:
  python research/prop-lines/public_passyds_replay.py --output research/prop-lines/out/public_passyds_replay.json
No network, fitting, promotion, wager, alert or production write is performed.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from scipy.stats import norm as normal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_pipeline as pipeline
from build_quotes import collapse_quotes, norm
from extract_git_props import extract

MODELS = ['raw', 'shrink', 'refit', 'trailing', 'market']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def iso(value):
    try:
        if not isinstance(value, str):
            return None
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except ValueError:
        return None


def canonical_team(value, names):
    value = names.get(value, value)
    return {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS'}.get(value, value)


def match_game(row, games, names):
    home, away = canonical_team(row.home, names), canonical_team(row.away, names)
    matches = [g for g in games if g['home'] == home and g['away'] == away and iso(g['kickoff']) == row.kick.to_pydatetime()]
    return matches[0] if len(matches) == 1 else None


def match_profile(profiles, player, teams, names):
    matches = [p for p in profiles.values() if p.get('position') == 'QB' and norm(p.get('name')) == norm(player)
               and canonical_team(p.get('team'), names) in teams]
    return matches[0] if len(matches) == 1 else None


def model_history(profile, day, season, window=12, lookback=730):
    minimum_day = (datetime.fromisoformat(day) - timedelta(days=lookback)).date().isoformat()
    games = [g for g in profile.get('games', []) if g.get('verified_start') is True
             and isinstance(g.get('date'), str) and minimum_day <= g['date'] < day
             and g.get('season', season + 1) <= season and pipeline.finite(g.get('pass_yds'))]
    games.sort(key=lambda g: (g['date'], g['season'], g.get('week', 0)))
    if len({(g['season'], g.get('week'), g['date']) for g in games}) != len(games):
        return None, 'duplicate_history'
    games = games[-window:]
    # Public profile.games contains last appearances, while the production QB
    # model uses last starts. Relief appearances can hide an older start.
    expected_n = profile.get('stats', {}).get('pass_yds', {}).get('n')
    if expected_n != len(games):
        return None, 'incomplete_public_start_window'
    if len(games) < 5:
        return None, 'fewer_than_five_verified_starts'
    return [{'season': g['season'], 'week': g.get('week'), 'passing_yards': g['pass_yds']} for g in games], None


def fixed_models(history, season, params):
    raw = pipeline.season_fit(history, 'passing_yards', 'lognormal', season, 5)
    if raw.get('status') != 'ready' or not pipeline.finite(raw.get('sigma_log')) or raw['sigma_log'] <= 0:
        return None
    trailing_mean = float(np.mean([g['passing_yards'] for g in history]))
    refit = pipeline.lognormal_refit(raw, trailing_mean, params)
    if refit is None:
        return None
    return {'raw': raw, 'refit': dict(raw, **refit),
            'trailing': dict(raw, mean=trailing_mean, mu_log=math.log(trailing_mean) - raw['sigma_log'] ** 2 / 2)}


def cdf(x, model):
    mass = model.get('nonpositive') or []
    weights = model.get('nonpositive_weights') or [1 / model['n']] * len(mass)
    empirical = sum(w for v, w in zip(mass, weights) if v <= x)
    positive = model.get('positive_weight', 1)
    if x <= 0 or positive <= 0:
        return empirical
    return min(1, empirical + positive * normal.cdf((math.log(x) - model['mu_log']) / model['sigma_log']))


def probabilities(models, line, shrink):
    values = {}
    for key, model in models.items():
        under = cdf(math.ceil(line) - .5, model)
        over = 1 - cdf(math.floor(line) + .5, model)
        values[key] = over / (over + under) if over + under > 0 else np.nan
    center = models['raw']['mean']
    values['shrink'] = (shrink['w'] * values['raw'] + (1 - shrink['w']) * shrink['target']) if .5 * center <= line <= 1.5 * center else values['raw']
    return values


class PublicHistory:
    def __init__(self, revision):
        log = subprocess.check_output(['git', 'log', '--format=%H|%cI', revision, '--', 'data/history.json'], cwd=ROOT, text=True)
        self.entries = sorted([(iso(t), rev) for rev, t in (line.split('|') for line in log.splitlines())])
        self.cache, self.receipts = {}, {}

    def at(self, observed, max_age):
        eligible = [(stamp, rev) for stamp, rev in self.entries if stamp <= observed]
        if not eligible:
            return None, 'no_pregame_public_history'
        stamp, rev = eligible[-1]
        if rev not in self.cache:
            raw = subprocess.check_output(['git', 'show', f'{rev}:data/history.json'], cwd=ROOT)
            self.receipts[rev] = {'revision': rev, 'commit_time': stamp.isoformat(), 'sha256': sha(raw)}
            try:
                doc = json.loads(raw).get('betting')
            except ValueError:
                doc = None
            self.cache[rev] = doc
        doc = self.cache[rev]
        generated = iso(doc.get('generated_at')) if isinstance(doc, dict) else None
        if generated is None or generated > observed or observed - generated > timedelta(hours=max_age):
            return None, 'public_history_missing_stale_or_future'
        if not isinstance(doc.get('profiles'), dict):
            return None, 'public_history_profiles_missing'
        return doc, None


def calibrate(p, y):
    p, y = np.asarray(p), np.asarray(y)
    if len(y) < 10 or len(np.unique(y)) < 2 or np.std(logit(np.clip(p, 1e-6, 1 - 1e-6))) < .01:
        return {'intercept': None, 'slope': None, 'status': 'insufficient_outcomes_or_probability_variation'}
    x = logit(np.clip(p, 1e-6, 1 - 1e-6))
    def loss(ab):
        z = ab[0] + ab[1] * x
        return np.mean(np.logaddexp(0, z) - y * z)
    fit = minimize(loss, [0, 1], method='BFGS')
    return {'intercept': float(fit.x[0]), 'slope': float(fit.x[1]), 'status': 'converged' if fit.success else 'optimizer_warning'}


def paired_ci(frame, first, second, cluster, kind, rng, repetitions):
    y = frame.y.to_numpy()
    a, b = frame[first].to_numpy(), frame[second].to_numpy()
    if kind == 'brier':
        delta = (a - y) ** 2 - (b - y) ** 2
    else:
        a, b = np.clip(a, 1e-6, 1 - 1e-6), np.clip(b, 1e-6, 1 - 1e-6)
        delta = -(y * np.log(a) + (1 - y) * np.log1p(-a)) + y * np.log(b) + (1 - y) * np.log1p(-b)
    clusters = pd.DataFrame({'key': frame[cluster].to_numpy(), 'delta': delta}).groupby('key').delta.agg(['sum', 'size'])
    if len(clusters) < 2:
        return {'difference': float(np.mean(delta)), 'ci95': None, 'clusters': len(clusters)}
    indices = rng.integers(0, len(clusters), (repetitions, len(clusters)))
    scores = clusters['sum'].to_numpy()[indices].sum(axis=1) / clusters['size'].to_numpy()[indices].sum(axis=1)
    return {'difference': float(np.mean(delta)), 'ci95': np.quantile(scores, [.025, .975]).tolist(), 'clusters': len(clusters)}


def report(frame, protocol):
    if frame.empty:
        return {'lines': 0, 'status': 'no_eligible_comparison'}
    y = frame.y.to_numpy()
    output = {'lines': len(frame), 'player_games': frame.pg.nunique(), 'games': frame.game_id.nunique(),
              'players': frame.pid.nunique(), 'over_rate': float(y.mean()), 'models': {}, 'paired': {}}
    rng = np.random.default_rng(protocol['bootstrap']['seed'])
    for name in MODELS:
        p = np.clip(frame[name].to_numpy(), 1e-6, 1 - 1e-6)
        output['models'][name] = {'brier': float(np.mean((p - y) ** 2)),
                                  'log_loss': float(-np.mean(y * np.log(p) + (1 - y) * np.log1p(-p))),
                                  'calibration': calibrate(p, y)}
        point = frame['point_' + ('market' if name == 'market' else 'raw' if name == 'shrink' else name)]
        error = point - frame.actual
        # An alternate threshold is not the market's median forecast; comparing
        # its yardage error with a model median would mislabel a baseline.
        point_scored = name != 'market' or bool(frame.main.all())
        output['models'][name].update(mae=float(error.abs().mean()) if point_scored else None,
                                      bias_prediction_minus_actual=float(error.mean()) if point_scored else None,
                                      point_definition='posted main-line threshold, approximate market median' if name == 'market' and point_scored else
                                      'not scored: alternate threshold is not a forecast median' if name == 'market' else 'model distribution median')
    for benchmark in ['raw', 'shrink', 'trailing', 'market']:
        output['paired']['refit_minus_' + benchmark] = {
            cluster: {loss: paired_ci(frame, 'refit', benchmark, cluster, loss, rng, protocol['bootstrap']['replications'])
                      for loss in ['brier', 'log_loss']} for cluster in ['game_id', 'pid']}
    return output


def choose_main_lines(lines):
    """Choose from market prices alone; pushes/missing models cannot reroute it."""
    main = {}
    for pg, group in lines.groupby('pg'):
        candidates = group[group.books >= 2]
        candidates = candidates if len(candidates) else group
        picked = candidates.assign(distance=(candidates.market - .5).abs()).sort_values(['distance', 'line'], kind='stable').iloc[0]
        main[pg] = picked.line
    return main


def run(protocol_path):
    raw_protocol = protocol_path.read_bytes()
    protocol = json.loads(raw_protocol)
    for path, digest in protocol['sources'].items():
        if sha((ROOT / path).read_bytes()) != digest:
            raise ValueError('Frozen source changed: ' + path)
    revision = protocol['git_quote_and_history_ancestor']
    revision = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options', f'{revision}^{{commit}}'], cwd=ROOT, text=True).strip()
    raw, quotes_receipts = extract(revision=revision, market='pass_yds')
    latest = json.loads((ROOT / 'data/history.json').read_bytes())['betting']
    names = latest.get('team_names', {})
    raw['home'], raw['away'] = raw.home.map(lambda v: canonical_team(v, names)), raw.away.map(lambda v: canonical_team(v, names))
    quotes, extraction_counts = collapse_quotes(raw)
    outcomes = json.loads((ROOT / 'data/results.json').read_bytes())
    games = [g for g in outcomes['games'].values() if g.get('sport') == 'nfl'
             and re.fullmatch(r'2026_\d{2}_[A-Z]+_[A-Z]+', str(g.get('id', '')))
             and iso(g.get('kickoff')) is not None and iso(g['kickoff']) < iso(protocol['completed_target_cutoff'])]
    history = PublicHistory(revision)
    attrition, records = Counter(), []
    calibration = json.loads((ROOT / 'config/calibration_policy.json').read_bytes())['markets']['pass_yds']
    for row in quotes.itertuples():
        attrition['collapsed_quotes'] += 1
        game = match_game(row, games, names)
        if game is None:
            attrition['no_exact_completed_game'] += 1
            continue
        if not all(pipeline.finite(v) and abs(v) >= 100 for v in (row.over, row.under)) or not pipeline.finite(row.line) or row.line < 0:
            attrition['not_valid_intact_two_sided_quote'] += 1
            continue
        if (row.observed_at - row.upd).total_seconds() > protocol['selection']['quote_max_age_hours'] * 3600:
            attrition['stale_quote'] += 1
            continue
        decimal = lambda value: 1 + value / 100 if value > 0 else 1 + 100 / -value
        qo, qu = 1 / decimal(row.over), 1 / decimal(row.under)
        if not -.01 < qo + qu - 1 < .25:
            attrition['invalid_overround'] += 1
            continue
        day = row.gameday
        doc, error = history.at(row.observed_at.to_pydatetime(), protocol['selection']['history_max_age_hours'])
        if error:
            attrition[error] += 1
            continue
        profile = match_profile(doc['profiles'], row.player, {game['home'], game['away']}, names)
        if profile is None:
            attrition['no_unique_QB_game_identity'] += 1
            continue
        inputs, error = model_history(profile, day, protocol['target_season'],
                                      protocol['selection']['window'], protocol['selection']['lookback_days'])
        modeled = fixed_models(inputs, protocol['target_season'], calibration['params']) if inputs else None
        # Preserve all otherwise eligible market contracts for main-line choice;
        # selecting a main line must not depend on this model's missingness.
        values = probabilities(modeled, row.line, calibration['superseded_shrink_const']['params']) if modeled else {}
        actual = outcomes['players'].get(profile['id'] + '|' + day, {}).get('pass_yds')
        record = dict(game_id=game['id'], pid=profile['id'], week=int(game['id'].split('_')[1]), pg=game['id'] + '|' + profile['id'],
                      line=row.line, book=row.book, market=qo / (qo + qu), actual=actual, reason=error or ('invalid_model' if not modeled else None),
                      **values, point_market=row.line)
        if modeled:
            record.update({f'point_{name}': math.exp(model['mu_log']) for name, model in modeled.items()})
        records.append(record)
        if error:
            attrition[error] += 1
    frame = pd.DataFrame(records)
    result = {'schema': protocol['schema'], 'protocol_sha256': sha(raw_protocol), 'baseline_revision': revision,
              'cohort': 'matched published-snapshot retrospective replay; distinct from original cache-based cohort',
              'extraction_counts': extraction_counts, 'attrition': dict(attrition),
              'quote_sources': quotes_receipts, 'history_sources': list(history.receipts.values()),
              'execution_source_sha256': {path: sha((ROOT / path).read_bytes()) for path in
                  ['research/prop-lines/public_passyds_replay.py', 'research/prop-lines/extract_git_props.py', 'research/prop-lines/build_quotes.py']},
              'limitations': protocol['limitations'], 'reports': {}}
    if frame.empty:
        result['status'] = 'blocked_no_matched_public_snapshot_rows'
        return result
    grouped = []
    for (pg, line), group in frame.groupby(['pg', 'line'], sort=True):
        first = group.iloc[0]
        valid = group[group.reason.isna() & group.actual.map(pipeline.finite)].copy()
        summary = {key: first[key] for key in ['pg', 'game_id', 'pid', 'week', 'line']}
        summary.update(market=float(group.market.mean()), books=group.book.nunique(), eligible=len(valid) == len(group),
                       actual=valid.actual.iloc[0] if len(valid) else None)
        if len(valid):
            summary.update({key: float(valid[key].mean()) for key in ['raw', 'shrink', 'refit', 'trailing', 'point_raw', 'point_refit', 'point_trailing']})
        summary['point_market'] = line
        grouped.append(summary)
    lines = pd.DataFrame(grouped)
    main = choose_main_lines(lines)
    lines['main'] = lines.line == lines.pg.map(main)
    result['attrition'].update(main_lines_before_outcome_or_model_exclusion=int(lines.main.sum()),
                               player_games_before_outcome_or_model_exclusion=lines.pg.nunique(),
                               ineligible_model_or_outcome_lines=int((~lines.eligible).sum()),
                               pushes=int((lines.eligible & (lines.actual == lines.line)).sum()))
    selected = lines[lines.eligible & (lines.actual != lines.line)].copy()
    selected['y'] = (selected.actual > selected.line).astype(float)
    for label, group in [('all_main', selected[selected.main]), ('all_alternate', selected[~selected.main]),
                         ('early_weeks_1_3_main', selected[selected.main & (selected.week <= 3)]),
                         ('later_weeks_4_5_main', selected[selected.main & selected.week.between(4, 5)])]:
        result['reports'][label] = report(group, protocol)
    result['status'] = 'completed_no_fit_no_promotion'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=ROOT / 'research/prop-lines/CONTINUATION_PROTOCOL.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['status', 'extraction_counts', 'attrition', 'reports']}, indent=2))


if __name__ == '__main__':
    main()
