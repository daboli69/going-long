#!/usr/bin/env python3
"""Prediction-equivalence check for the shadow capture: runs the SAME board at the SAME clock through two code trees and compares every record.

    python scripts/shadow_equivalence_check.py --old-tree <dir with the earlier scripts/> --root <FantasyPoints> --board board.json [--now ISO]

Each tree is run in its own subprocess (`--emit`), which loads its inputs (the old tree always rebuilds; the new tree uses its cache, building it on first use) and prints the
canonical JSON of the records plan_captures() would write. Nothing is written to the capture directory. Compared: record keys, feature hashes (exact), every forecast
(expected total and probability, max absolute difference), market fields, cutoffs.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path


def emit(tree, root, board, now, out):
    sys.path.insert(0, str(Path(tree) / 'scripts'))
    import fp_shadow as fs
    data = json.loads(Path(board).read_bytes())
    clock = fs.parse_time(now) if now else fs.parse_time(data['generated_at']) + timedelta(minutes=5)
    if hasattr(fs, 'prepare_inputs'):
        features, fitted, cutoffs, hashes, spec_sha, status = fs.prepare_inputs(root, out)
    else:
        features, fitted, cutoffs, hashes, spec_sha = fs.load_inputs(root)
        status = 'old_tree_always_rebuilds'
    records, exclusions = fs.plan_captures(data['games'], features, fitted, clock, market_generated_at=data['generated_at'], market_sha256='x' * 64, source_hashes={}, cutoffs=cutoffs,
                                           weeks=(6, 10), code_sha='equivalence', spec_sha=spec_sha)
    print(json.dumps({'status': status, 'records': records, 'exclusions': exclusions}, sort_keys=True))


def run(tree, root, board, now, out):
    cmd = [sys.executable, __file__, '--emit', '--old-tree', str(tree), '--root', str(root), '--board', str(board), '--out', str(out)] + (['--now', now] if now else [])
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def compare(old, new):
    a, b = {r['game_id']: r for r in old['records']}, {r['game_id']: r for r in new['records']}
    report = {'games_old': len(a), 'games_new': len(b), 'same_games': set(a) == set(b), 'exclusions_equal': sorted(map(json.dumps, old['exclusions'])) == sorted(map(json.dumps, new['exclusions'])),
              'feature_hash_mismatches': 0, 'cutoff_mismatches': 0, 'market_mismatches': 0, 'null_pattern_mismatches': 0, 'max_abs_diff_expected_total': 0.0, 'max_abs_diff_p_over': 0.0}
    for gid in set(a) & set(b):
        x, y = a[gid], b[gid]
        report['feature_hash_mismatches'] += x['feature_hash'] != y['feature_hash']
        report['cutoff_mismatches'] += x['feature_cutoffs'] != y['feature_cutoffs']
        report['market_mismatches'] += x['market'] != y['market']
        for model in x['forecasts']:
            fx, fy = x['forecasts'][model], y['forecasts'][model]
            if (fx is None) != (fy is None):
                report['null_pattern_mismatches'] += 1
            elif fx:
                report['max_abs_diff_expected_total'] = max(report['max_abs_diff_expected_total'], abs(fx['expected_total'] - fy['expected_total']))
                report['max_abs_diff_p_over'] = max(report['max_abs_diff_p_over'], abs(fx['p_over'] - fy['p_over']))
    report['equivalent'] = (report['same_games'] and report['exclusions_equal'] and not report['feature_hash_mismatches'] and not report['cutoff_mismatches'] and not report['market_mismatches']
                            and not report['null_pattern_mismatches'] and report['max_abs_diff_expected_total'] < 1e-9 and report['max_abs_diff_p_over'] < 1e-12)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old-tree', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--board', type=Path, required=True)
    p.add_argument('--now')
    p.add_argument('--emit', action='store_true')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    if a.emit:
        emit(a.old_tree, a.root, a.board, a.now, a.out)
        return
    new_tree = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as scratch:
        old = run(a.old_tree, a.root, a.board, a.now, scratch)
        new = run(new_tree, a.root, a.board, a.now, scratch)  # builds the cache on first use
        warm = run(new_tree, a.root, a.board, a.now, scratch)  # served from the cache
        out = {'cache_status': [new['status'], warm['status']], 'old_vs_new_cold': compare(old, new), 'old_vs_new_cache_hit': compare(old, warm)}
    print(json.dumps(out, indent=1))
    sys.exit(0 if out['old_vs_new_cold']['equivalent'] and out['old_vs_new_cache_hit']['equivalent'] else 1)


if __name__ == '__main__':
    main()
