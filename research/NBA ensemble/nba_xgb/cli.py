"""Command line: python -m nba_xgb.cli <command>. Run from the NBA ensemble folder."""
from __future__ import annotations
import argparse
import json
import stat
import sys
import numpy as np
import pandas as pd
from . import data, pipeline
from .develop import OUT, file_hash


def cmd_final(args):
    F = pd.read_parquet(OUT / 'features_lag1.parquet')
    pred = pipeline.run_final(F)
    OUT.mkdir(exist_ok=True)
    sha = pipeline.write_once(OUT / 'batch_predictions_2025_2026.csv', pred)
    print('batch predictions', len(pred), sha)


def cmd_replay(args):
    games, boxes = data.load()
    frozen = pipeline.load_frozen()
    pipeline.check_frozen(frozen)
    pred, feats = pipeline.replay(games, boxes, frozen, args.season)
    sha = pipeline.write_once(OUT / f'replay_predictions_{args.season}.csv', pred)
    feats.to_csv(OUT / f'replay_features_{args.season}.csv', index=False)
    print('replay predictions', len(pred), sha)


def cmd_compare(args):
    """Replay (information visible as of each day) must reproduce the batch features and predictions exactly."""
    batch = pd.read_csv(OUT / 'batch_predictions_2025_2026.csv', dtype={'game_id': str})
    F = pd.read_parquet(OUT / 'features_lag1.parquet').set_index('game_id')
    report = {}
    for season in (2025, 2026):
        rp = pd.read_csv(OUT / f'replay_predictions_{season}.csv', dtype={'game_id': str})
        b = batch[batch.season == season]
        m = rp.merge(b, on=['game_id', 'model'], suffixes=('_replay', '_batch'), how='outer', indicator=True)
        feats = pd.read_csv(OUT / f'replay_features_{season}.csv', dtype={'game_id': str}).set_index('game_id')
        cols = [c for c in feats.columns if c in F.columns and c not in ('game_date', 'prediction_cutoff_utc')]
        fd = (feats[cols] - F.loc[feats.index, cols]).abs().max()
        assert len(rp) > 0 and len(b) > 0 and int((m._merge == 'both').sum()) > 0, 'replay comparison would cover zero rows'
        assert len(cols) > 0, 'no feature columns to compare'
        report[season] = {'rows_replay': len(rp), 'rows_batch': len(b), 'unmatched_rows': int((m._merge != 'both').sum()),
                          'max_abs_prediction_diff': float((m.p_home_replay - m.p_home_batch).abs().max()),
                          'max_abs_feature_diff': {k: float(v) for k, v in fd.items()}}
    (OUT / 'REPLAY_CHECK.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def cmd_daily(args):
    pred = pipeline.daily(args.date)
    print(pred[pred.model == 'xgb'][['game_id', 'p_home']].to_string(index=False))


def cmd_audit(args):
    s = data.build(write=not args.dry)
    print(pd.DataFrame(s['coverage']).to_string())


def main(argv=None):
    ap = argparse.ArgumentParser(prog='nba_xgb')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('final').set_defaults(fn=cmd_final)
    r = sub.add_parser('replay'); r.add_argument('--season', type=int, required=True); r.set_defaults(fn=cmd_replay)
    sub.add_parser('compare').set_defaults(fn=cmd_compare)
    d = sub.add_parser('daily'); d.add_argument('--date', required=True, help='ET game date YYYY-MM-DD'); d.set_defaults(fn=cmd_daily)
    a = sub.add_parser('audit'); a.add_argument('--dry', action='store_true'); a.set_defaults(fn=cmd_audit)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == '__main__':
    main()
