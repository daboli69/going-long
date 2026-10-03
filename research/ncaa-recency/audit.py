"""Offline snapshot provenance audit; never downloads, fits, or reads ranking data."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path


PUBLIC_INPUTS = ('data/history.json', 'data/ncaa_lines.json', 'data/results.json')
MODEL_SOURCES = ('scripts/build_pipeline.py', 'scripts/pbp_features.py',
                 'scripts/build_ncaa_lines.py', 'scripts/requirements.txt')


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone required')
    return parsed


def age_hours(as_of, observed):
    return round((stamp(as_of) - stamp(observed)).total_seconds() / 3600, 3)


def audit(root: Path, as_of: str):
    stamp(as_of)
    files = {name: root / name for name in (*PUBLIC_INPUTS, *MODEL_SOURCES)}
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest()
              for name, path in files.items()}
    documents = {name: json.loads(files[name].read_text(encoding='utf-8'))
                 for name in PUBLIC_INPUTS}
    betting = documents['data/history.json']['betting']
    season = max((g.get('season', 0) for g in betting['games']['ncaa']), default=None)
    models = [g for g in betting['games']['ncaa'] if g.get('model')]
    current_counts = Counter()
    weights = Counter()
    unknown_season_evidence = 0
    for game in models:
        evidence = game['model'].get('season_evidence') or {}
        values = [evidence.get(k) for k in ('home_current_games', 'away_current_games')]
        if all(isinstance(n, int) and not isinstance(n, bool) for n in values):
            current_counts[str(min(values))] += 1
        else:
            unknown_season_evidence += 1
        for side in ('home', 'away'):
            value = evidence.get(side + '_current_weight')
            weights[str(value) if value is not None else 'unknown'] += 1
    features = betting['features']
    teams = features['ncaa']['teams']
    dates = [t['last_game'] for t in teams.values() if t.get('last_game')]
    snapshot_generated = betting['generated_at']
    results = documents['data/results.json']
    ncaa_results = [v for k, v in results['games'].items() if k.startswith('ncaa|')]
    # Existing public snapshots are latest views, not replayable raw archives.
    # Do not infer publication timestamps or a usable backtest from result count.
    return {
        'schema_version': 1,
        'as_of': as_of,
        'status': 'AUDIT_ONLY_NO_BACKTEST',
        'file_sha256': hashes,
        'production': {
            'generated_at': snapshot_generated,
            'age_hours': age_hours(as_of, snapshot_generated),
            'window': betting['window'], 'minimum_games': betting['minimum_games'],
            'sources': betting['sources'], 'season': season,
            'scheduled_rows': len(betting['games']['ncaa']), 'modeled_rows': len(models),
            'scheduled_season_counts': dict(sorted(Counter(str(g.get('season')) for g in betting['games']['ncaa']).items())),
            'current_games_minimum_per_matchup': dict(sorted(current_counts.items())),
            'unknown_current_game_counts': unknown_season_evidence,
            'current_weight_team_rows': dict(sorted(weights.items())),
            'pooled_historical_diagnostic_not_holdout': betting['validation']['ncaa']
        },
        'ncaa_features': {
            'generated_at': features['generated_at'], 'sources': features['sources']['ncaa'],
            'team_rows': len(teams), 'player_rows': len(features['ncaa']['players']),
            'defense_rows': len(features['ncaa']['defenses']),
            'defense_coverage_rows': len(features['ncaa']['defense_coverage']),
            'eligible_snaps': features['ncaa']['eligible_snaps'],
            'neutral_snaps': features['ncaa']['neutral_snaps'],
            'team_latest_observation_years': dict(sorted(Counter(d[:4] for d in dates).items())),
            'missing_team_last_game': len(teams) - len(dates),
            'latest_observation': max(dates, default=None),
            'oldest_team_latest_observation': min(dates, default=None),
            'interpretation': 'Refresh timestamp does not establish current-season team evidence; year is observation calendar year, not an audited season membership.'
        },
        'quotes': {
            'generated_at': documents['data/ncaa_lines.json'].get('generated_at'),
            'raw_events': len(documents['data/ncaa_lines.json'].get('games_raw', [])),
            'feed_status': documents['data/ncaa_lines.json'].get('feed_status'),
            'last_fresh_at': documents['data/ncaa_lines.json'].get('last_fresh_at'),
            'interpretation': 'Saved provider freshness status is not a fresh quote at this audit clock; inspect each exact market timestamp.'
        },
        'outcomes': {
            'ncaa_results_rows': len(ncaa_results),
            'known_publication_timestamp_rows': sum(bool(g.get('result_available_at')) for g in ncaa_results),
            'interpretation': 'Results alone cannot reconstruct decision-time team inputs or prices.'
        },
        'experiment_status': 'BLOCKED_DATA_NOT_FITTED',
        'blocker': 'No archived raw season/game feature histories or trustworthy as-of publication metadata are supplied by these latest public snapshots. No challenger evaluation or calibrated confidence follows from the pooled diagnostic.'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--as-of', required=True, help='Explicit timezone-aware audit clock')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = json.dumps(audit(args.root, args.as_of), indent=2, allow_nan=False) + '\n'
    if args.output:
        # Explicit output only; the default cannot change a file or snapshot.
        args.output.write_text(output, encoding='utf-8')
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
