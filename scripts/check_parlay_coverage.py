"""Isolated provider read check. Never publish snapshots, freeze picks or alert."""
import argparse
import json
from pathlib import Path

from parlay_feed import ROOT, _fetch_parlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads((ROOT / 'data/nfl_betting.json').read_text(encoding='utf-8'))
    result = _fetch_parlay('nfl', previous)
    report = {field: result[field] for field in (
        'generated_at', 'feed_status', 'source_states', 'source_errors', 'coverage')}
    report['normalized_quote_count'] = len(result['props'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if result['feed_status'] == 'FRESH' else 1


if __name__ == '__main__':
    raise SystemExit(main())
