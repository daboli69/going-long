"""Read-only audit of the private historical odds archive's game-line export (P5-3).

Re-derives, from the raw SQLite index and public nflverse results, every fact the Missions comparison relies on: actual-game mapping, final scores,
market/period scope, paired sides and lines, price agreement, timestamp order, one decision snapshot per game and de-vig sanity.
Never calls a provider, never reads credential.json, writes nothing. Returns aggregates only (no quotes, no prices).

    python scripts/archive_game_line_audit.py --root <odds-history dir> --games <nflverse games.csv>
"""
import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import statistics

import pandas as pd

from fp_ingest.identity import TeamError, canonical_team
from missions_history_export import MARKETS, export, outcome
from odds_history import ROOT, default_root, iso

ALLOWED_PARAM_MARKETS = {'h2h', 'spreads', 'totals'}


def _decimal(american):
    return 1 + american / 100 if american > 0 else 1 + 100 / abs(american)


def _kick(row):
    local = pd.Timestamp(f"{row['gameday']} {row['gametime'] if isinstance(row['gametime'], str) else '13:00'}", tz='America/New_York')
    return local.tz_convert('UTC').to_pydatetime()


def _stats(values):
    values = sorted(values)
    if not values:
        return None
    return {'n': len(values), 'min': values[0], 'median': statistics.median(values), 'p95': values[int(0.95 * (len(values) - 1))], 'max': values[-1]}


def audit(root, games_csv, results_path=ROOT / 'data/nfl_betting.json'):
    root = Path(root)
    exported = export(root, results_path)
    records = exported['records']
    games = pd.read_csv(games_csv).set_index('game_id')
    scores = {g['game_id']: g for g in json.loads(Path(results_path).read_text())['games']}
    out = {'records': len(records), 'games': len({r['gameId'] for r in records}), 'gaps_from_export': exported['gaps']}
    violations, unverifiable = {}, set()

    def bad(name, n=1):
        violations[name] = violations.get(name, 0) + n

    with closing(sqlite3.connect(f'file:{root / "index.sqlite3"}?mode=ro', uri=True)) as db:
        # --- scope: which markets were requested, and are any period / alternate markets present at all
        seen_params = set()
        for (params,) in db.execute('SELECT params FROM pulls'):
            try:
                markets = json.loads(params).get('markets') if params else None
            except (TypeError, ValueError):
                markets = None
            if markets:
                seen_params.update(str(markets).split(','))
        out['scope'] = {'requested_market_keys': sorted(seen_params), 'player_null_market_keys': sorted(r[0] for r in db.execute('SELECT DISTINCT market FROM quotes WHERE player IS NULL')),
                        'period_or_alternate_keys_requested': sorted(k for k in seen_params if k.startswith('alternate_') or '_h' in k or '_q' in k or k.endswith('_h1'))}
        if set(out['scope']['player_null_market_keys']) - ALLOWED_PARAM_MARKETS:
            bad('unexpected_game_market_keys', len(set(out['scope']['player_null_market_keys']) - ALLOWED_PARAM_MARKETS))
        # --- event -> game mapping rebuilt from raw quotes (independent of export())
        by_game = {}
        for event_id, home, away, kickoff in db.execute('SELECT event_id,home,away,MAX(kickoff) FROM quotes GROUP BY event_id'):
            try:
                home, away = canonical_team(home), canonical_team(away)
            except TeamError:
                continue
            by_game.setdefault((home, away), []).append((event_id, iso(kickoff)))
        snapshot_by_game, snap_lag, quote_lag, quote_to_snap, overrounds = {}, [], [], [], []
        pair_checked = pair_bad = 0
        kick_diff = []
        for r in records:
            gid = r['gameId']
            snapshot_by_game.setdefault(gid, set()).add(r['snapshotAt'])
            if gid not in games.index:
                bad('game_not_in_nflverse')
                continue
            g = games.loc[gid]
            home, away = canonical_team(g['home_team']), canonical_team(g['away_team'])
            sched = scores.get(gid)
            if not sched or canonical_team(sched['home']) != home or canonical_team(sched['away']) != away:
                bad('schedule_team_mismatch')
            independent = not pd.isna(g['home_score']) and not pd.isna(g['away_score'])
            if not independent:
                unverifiable.add(gid)  # the public cache has no final score yet: counted, never silently passed
            elif sched and (sched.get('home_score') != g['home_score'] or sched.get('away_score') != g['away_score']):
                bad('score_mismatch_vs_nflverse')
            actual_kick = _kick(g)
            kick_diff.append(abs((iso(r['kickoff']) - actual_kick).total_seconds()) / 3600)
            expected_y = outcome(r['market'], g['home_score'], g['away_score'], r['line']) if independent else r['y']
            if expected_y != r['y']:
                bad('outcome_mismatch')
            if not iso(r['snapshotAt']) < iso(r['kickoff']):
                bad('snapshot_not_before_kickoff')
            snap_lag.append((iso(r['kickoff']) - iso(r['snapshotAt'])).total_seconds() / 60)
            events = [e for e, k in by_game.get((home, away), []) if abs((k - actual_kick).total_seconds()) <= 36 * 3600]
            if not events:
                bad('no_raw_event_for_record')
                continue
            raw_market = {v: k for k, v in MARKETS.items()}[r['market']]
            sql = ('SELECT book,side,line,price,quote_at,snapshot_at FROM quotes WHERE player IS NULL AND market=? AND snapshot_at=? AND event_id IN ('
                   + ','.join('?' for _ in events) + ')')
            raw = [dict(zip(('book', 'side', 'line', 'price', 'quote_at', 'snapshot_at'), row)) for row in db.execute(sql, [raw_market, r['snapshotAt'], *events])]
            for book, (price_a, price_b) in r['quotes'].items():
                pair_checked += 1
                mine = [q for q in raw if q['book'] == book]
                if r['market'] == 'total':
                    a = [q for q in mine if q['side'] == 'Over' and q['line'] == r['line']]
                    b = [q for q in mine if q['side'] == 'Under' and q['line'] == r['line']]
                else:
                    def team(q):
                        try:
                            return canonical_team(q['side'])
                        except TeamError:
                            return None
                    a = [q for q in mine if team(q) == home and (r['market'] == 'moneyline' or q['line'] == r['line'])]
                    b = [q for q in mine if team(q) == away and (r['market'] == 'moneyline' or q['line'] == -r['line'])]
                if len(a) != 1 or len(b) != 1 or a[0]['price'] != price_a or b[0]['price'] != price_b:
                    pair_bad += 1
                    continue
                for q in (a[0], b[0]):
                    if not iso(q['quote_at']) <= iso(q['snapshot_at']):
                        bad('quote_after_snapshot')
                    if not iso(q['snapshot_at']) < actual_kick:
                        bad('quote_snapshot_not_before_actual_kickoff')
                    quote_to_snap.append((iso(q['snapshot_at']) - iso(q['quote_at'])).total_seconds())
                    quote_lag.append((actual_kick - iso(q['quote_at'])).total_seconds() / 60)
                overrounds.append(1 / _decimal(price_a) + 1 / _decimal(price_b))
        multi = sum(1 for s in snapshot_by_game.values() if len(s) > 1)
        if multi:
            bad('game_with_more_than_one_snapshot', multi)
    out['pairs'] = {'book_pairs_checked': pair_checked, 'book_pairs_not_reproduced_from_raw': pair_bad}
    if pair_bad:
        bad('book_pair_not_reproduced', pair_bad)
    out['timestamps'] = {'snapshot_minutes_before_actual_kickoff': _stats(snap_lag), 'quote_minutes_before_actual_kickoff': _stats(quote_lag),
                         'seconds_between_quote_at_and_snapshot_at': _stats(quote_to_snap), 'schedule_vs_nflverse_kickoff_hours_abs': _stats(kick_diff),
                         'distinction': 'snapshot_at = provider board capture; quote_at = bookmaker update; neither is a forecast creation time or a feature availability time'}
    out['devig'] = {'overround_sum_of_implied': _stats(overrounds), 'below_1_00': sum(1 for o in overrounds if o < 1.0), 'above_1_15': sum(1 for o in overrounds if o > 1.15)}
    out['violations'] = violations
    out['independent_score_unavailable'] = {'games': len(unverifiable), 'share_of_games': len(unverifiable) / max(1, out['games']), 'weeks': sorted({g[:7] for g in unverifiable})}
    # frozen criterion: no violation, and unverifiable games below 1% of games
    out['status'] = 'PASS' if not violations and out['independent_score_unavailable']['share_of_games'] < 0.01 else 'FAIL'
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=default_root())
    p.add_argument('--games', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(audit(a.root, a.games), indent=1, default=str))


if __name__ == '__main__':
    main()
