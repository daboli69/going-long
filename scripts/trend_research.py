#!/usr/bin/env python
"""Trend Intelligence research runner (research only).

    python scripts/trend_research.py register            pre-register every spec in the ledger (hash stored before any run)
    python scripts/trend_research.py run E1 [E2 ...]      run pre-registered experiments and record aggregate results
    python scripts/trend_research.py show                 print the ledger

Reads the local, licensed Fantasy Points archive (never committed) and public nflverse weekly stats. Only aggregate metrics are written to
research/trend-intelligence/ledger.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_ingest.store import Manifest, find_root  # noqa: E402
from trend_research import experiments, ledger  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def cmd_register(args):
    book = ledger.load()
    for spec in experiments.SPECS.values():
        entry = ledger.register(book, spec)
        print(f"{spec['id']}: {entry['status']} spec {entry['spec_sha256'][:12]} registered {entry['registered_at']}")
    ledger.save(book)
    return 0


def cmd_run(args):
    root = find_root(args.root, REPO)
    manifest = Manifest(root)
    book = ledger.load()
    for exp_id in args.ids:
        spec = experiments.SPECS[exp_id]
        if exp_id not in book['experiments']:
            raise SystemExit(f'{exp_id} is not pre-registered; run `register` first')
        started = time.time()
        result, status = experiments.RUNNERS[exp_id](root, manifest)
        result['seconds'] = round(time.time() - started, 1)
        ledger.record(book, exp_id, spec, result, status)
        ledger.save(book)
        print(f'{exp_id}: {status} ({result["seconds"]}s)')
    return 0


def cmd_show(args):
    book = ledger.load()
    for exp_id, entry in book['experiments'].items():
        print(f"{exp_id} [{entry['status']}] {entry['spec']['title']}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('register').set_defaults(func=cmd_register)
    p = sub.add_parser('run')
    p.add_argument('ids', nargs='+')
    p.set_defaults(func=cmd_run)
    sub.add_parser('show').set_defaults(func=cmd_show)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
