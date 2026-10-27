"""python -m scripts.nba_winners --help"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

from .data import digest, load_snapshot, normalize_sdv, snapshot, utc, write_new
from .evaluation import replay, report
from .features import FEATURES, feature_rows, state_at
from .models import fit, probabilities, weights, debate

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / 'config/nba_winners_v1.json'


def receipts(config, source):
    files = sorted(Path(__file__).parent.glob('*.py'))
    return {'protocol': config, 'protocol_sha256': digest(config), 'snapshot_sha256': source['sha256'],
            'code_sha256': {p.name: sha256(p.read_bytes()).hexdigest() for p in files}, 'features': FEATURES}


def development_games(source, config):
    seasons = {g['season'] for g in source['games']}
    if seasons & set(config['untouched_holdout_seasons']):
        raise ValueError('Holdout season is locked: use development-only snapshots')
    if not seasons <= set(config['development_seasons']):
        raise ValueError('Snapshot includes seasons outside the registered development cohort')
    return source['games']


def main():
    parser = argparse.ArgumentParser(description='NBA six-model winner research; no production or paid calls')
    sub = parser.add_subparsers(dest='command', required=True)
    intake = sub.add_parser('ingest', help='Normalize cached SportsDataverse parquet or hoopR schedule JSON')
    intake.add_argument('--input', nargs='+', required=True)
    intake.add_argument('--output', required=True)
    fetch = sub.add_parser('fetch', help='Download the public archives used by sportsdataverse/hoopR loaders')
    fetch.add_argument('--seasons', nargs='+', type=int, required=True)
    fetch.add_argument('--cache', required=True)
    fetch.add_argument('--output', required=True)
    backtest = sub.add_parser('backtest', help='Chronological development diagnostic; holdout locked')
    backtest.add_argument('--input', required=True)
    backtest.add_argument('--output', required=True)
    predict = sub.add_parser('predict', help='Local research slate, with source freshness and pre-tipoff guards')
    predict.add_argument('--input', required=True)
    predict.add_argument('--output', required=True)
    args = parser.parse_args()
    config = json.loads(PROTOCOL.read_text())
    if Path(args.output).exists():
        parser.error('Output exists; choose a new receipt path')
    if args.command in ('ingest', 'fetch'):
        paths = []
        if args.command == 'fetch':
            if set(args.seasons) & set(config['untouched_holdout_seasons']):
                parser.error('Registered holdout downloads are locked')
            import requests
            cache = Path(args.cache)
            cache.mkdir(parents=True, exist_ok=True)
            for season in sorted(set(args.seasons)):
                url = f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_schedules/nba_schedule_{season}.parquet'
                response = requests.get(url, timeout=45)
                response.raise_for_status()
                raw_hash = sha256(response.content).hexdigest()
                path = cache / f'schedule_{season}_{raw_hash}.parquet'
                if path.exists() and sha256(path.read_bytes()).hexdigest() != raw_hash:
                    raise ValueError('Corrupt content-addressed source cache')
                if not path.exists():
                    with path.open('xb') as out:
                        out.write(response.content)
                paths.append((path, url, datetime.now(timezone.utc).isoformat()))
        else:
            paths = [(Path(p), 'local hoopR/SportsDataverse export; upstream publication time unverified', None) for p in args.input]
        rows, sources = [], []
        for path, url, retrieved_at in paths:
            raw = path.read_bytes()
            if path.suffix == '.parquet':
                import polars as pl
                rows.extend(pl.read_parquet(path).to_dicts())
            else:
                content = json.loads(raw)
                if not isinstance(content, list):
                    raise ValueError('Schedule JSON must be an array of provider rows')
                rows.extend(content)
            sources.append({'provider': 'SportsDataverse/ESPN', 'path': str(path), 'url': url,
                            'raw_sha256': sha256(raw).hexdigest(), 'retrieved_at': retrieved_at})
        games, excluded = normalize_sdv(rows)
        write_new(args.output, snapshot(games, sources, excluded))
        print(json.dumps({'output': args.output, 'games': len(games), 'excluded': excluded}))
        return
    source = load_snapshot(args.input)
    if args.command == 'backtest':
        games = development_games(source, config)
        forecasts, coverage = replay(games, config)
        result = {'receipts': receipts(config, source), 'coverage': coverage,
                  'report': report(forecasts, config), 'forecasts': forecasts}
    else:
        origin = datetime.now(timezone.utc)
        if not source.get('freshness_verified') or not source['sources'] or any(
            not s.get('retrieved_at') or not timedelta(0) <= origin - utc(s['retrieved_at']) <= timedelta(hours=36)
            for s in source['sources']
        ):
            raise ValueError('Current source retrieval receipts required; local archive ingestion cannot certify freshness')
        age = origin - utc(source['observed_at'])
        if age < timedelta(0) or age > timedelta(hours=36):
            raise ValueError('Source receipt must be observed before now and no older than 36h')
        games = source['games']
        if any(g['completed'] and utc(g['tipoff']) >= origin for g in games):
            raise ValueError('Source contains a final result for a future game')
        if any(g['season'] in config['untouched_holdout_seasons'] for g in games):
            raise ValueError('Holdout season is locked even in local prediction training')
        # Training hyperparameters frozen. No future or holdout outcomes enter here.
        history = [g for g in games if g['completed']]
        training = feature_rows(history, config, as_of=origin)
        models = fit(training, config)
        development = [g for g in history if g['season'] in config['development_seasons']]
        earlier, _ = replay(development, config)
        earlier = [r for r in earlier if utc(r['tipoff']) + timedelta(hours=config['historical_result_lag_hours']) < origin]
        w, state = weights(earlier, config), state_at(history, config, origin)
        predictions, excluded = [], Counter()
        for g in games:
            if g['completed'] or not origin < utc(g['tipoff']) <= origin + timedelta(hours=24):
                continue
            x, counts = state.features(g)
            if x is None:
                excluded['insufficient_current_season_team_history'] += 1
                continue
            prediction = debate(g, probabilities(models, x), w, counts, config)
            prediction['feature_values'] = dict(zip(FEATURES, x.tolist()))
            predictions.append(prediction)
        result = {'receipts': receipts(config, source), 'origin': origin.isoformat(),
                  'status': 'unvalidated_local_research', 'training_games': len(training),
                  'weight_training_games': len(earlier), 'predictions': predictions, 'excluded': dict(excluded)}
    write_new(args.output, result)
    print(json.dumps({'output': args.output, 'forecasts': len(result.get('forecasts', result.get('predictions', []))),
                      'status': result.get('status', 'development_diagnostic')}))


if __name__ == '__main__':
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        main()
