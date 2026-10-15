"""Offline, read-only export of the private historical odds archive for Missions validation.

Never calls a provider, never reads credential.json, never writes inside Git. It applies the archive's own actual-schedule
gate (unique completed home/away game within 36 h, snapshot strictly before the ACTUAL kickoff), keeps one decision snapshot
per game, pairs prices only inside one book/market/line, and attaches the real final score from the public NFL results.
Pushes are dropped, not refunded, because the scoring rule is conditional on no push.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from odds_history import ROOT, default_root, iso, encoded
from fp_ingest.identity import canonical_team, TeamError

MARKETS = {'h2h': 'moneyline', 'spreads': 'spread', 'totals': 'total'}


def outcome(market, home_score, away_score, line):
    """1 when side A (home / over) wins, 0 when side B wins, None for a push."""
    if market == 'moneyline':
        margin = home_score - away_score
        return None if margin == 0 else int(margin > 0)
    if market == 'spread':
        value = home_score - away_score + line
    else:
        value = home_score + away_score - line
    return None if value == 0 else int(value > 0)


def export(root, results_path=ROOT / 'data/nfl_betting.json'):
    root = Path(root)
    plan = json.loads((root / 'plan.json').read_text())
    schedule = json.loads((root / 'schedule.json').read_text())['games']
    scores = {g['game_id']: g for g in json.loads(Path(results_path).read_text())['games']
              if g.get('completed') is True and isinstance(g.get('home_score'), (int, float)) and isinstance(g.get('away_score'), (int, float))}
    records, gaps = [], {'unmatched_events': 0, 'no_score': 0, 'no_pair': 0, 'push': 0}
    with closing(sqlite3.connect(f'file:{root / "index.sqlite3"}?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        matched = {}
        for event_id, home, away, kickoff in db.execute('SELECT event_id,home,away,MAX(kickoff) FROM quotes GROUP BY event_id'):
            try:
                home, away = canonical_team(home), canonical_team(away)
            except TeamError:
                gaps['unmatched_events'] += 1
                continue
            candidates = [g for g in schedule if g['home'] == home and g['away'] == away and g.get('completed') is True
                          and iso(g['kickoff']) <= iso(plan['cutoff'])
                          and abs((iso(g['kickoff']) - iso(kickoff)).total_seconds()) <= 36 * 3600]
            if len(candidates) == 1:
                matched.setdefault(candidates[0]['game_id'], {'game': candidates[0], 'ids': []})['ids'].append(event_id)
            else:
                gaps['unmatched_events'] += 1
        for game_id, match in sorted(matched.items()):
            game, ids = match['game'], match['ids']
            if game_id not in scores:
                gaps['no_score'] += 1
                continue
            kick = iso(game['kickoff'])
            sql = ('SELECT book,market,side,line,price,snapshot_at,quote_at FROM quotes WHERE player IS NULL AND market IN (?,?,?) AND event_id IN ('
                   + ','.join('?' for _ in ids) + ')')
            rows = [dict(r) for r in db.execute(sql, [*MARKETS, *ids]) if iso(r['snapshot_at']) < kick]
            if not rows:
                continue
            snapshot = max(r['snapshot_at'] for r in rows)  # the single latest pre-kickoff decision board
            rows = [r for r in rows if r['snapshot_at'] == snapshot]
            for raw_market, market in MARKETS.items():
                per_book = {}
                for r in (x for x in rows if x['market'] == raw_market):
                    per_book.setdefault(r['book'], []).append(r)
                pairs = {}
                for book, quotes in per_book.items():
                    if market == 'total':
                        a = [q for q in quotes if q['side'] == 'Over']; b = [q for q in quotes if q['side'] == 'Under']
                        for qa in a:
                            for qb in b:
                                if qa['line'] == qb['line']:
                                    pairs.setdefault(qa['line'], {})[book] = [qa['price'], qb['price']]
                    else:
                        # Provider names are full team names; side A is the canonical home team.
                        def team(q):
                            try: return canonical_team(q['side'])
                            except TeamError: return None
                        a = [q for q in quotes if team(q) == game['home']]; b = [q for q in quotes if team(q) == game['away']]
                        if market == 'moneyline':
                            if len(a) == 1 and len(b) == 1:
                                pairs.setdefault(None, {})[book] = [a[0]['price'], b[0]['price']]
                        else:
                            for qa in a:
                                for qb in b:
                                    if qa['line'] is not None and qa['line'] == -qb['line']:
                                        pairs.setdefault(qa['line'], {})[book] = [qa['price'], qb['price']]
                if not pairs:
                    gaps['no_pair'] += 1
                    continue
                line, quotes = max(pairs.items(), key=lambda kv: (len(kv[1]), -abs(kv[0] or 0)))  # most books on one identical line
                y = outcome(market, scores[game_id]['home_score'], scores[game_id]['away_score'], line)
                if y is None:
                    gaps['push'] += 1
                    continue
                records.append({'gameId': game_id, 'market': market, 'line': line, 'y': y, 'snapshotAt': snapshot,
                                'kickoff': game['kickoff'], 'quotes': quotes})
    return {'schema': 'going-missions-history-v1', 'historicalOnly': True, 'records': records, 'gaps': gaps,
            'note': 'One pre-kickoff board per game (about 30 min before kickoff). Not a certified closing line; Novig/Kalshi are not in this archive.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=default_root())
    p.add_argument('--out', type=Path, default=None, help='Defaults to <root>/missions-backtest-input.json; refuses paths inside the Git checkout')
    a = p.parse_args()
    out = a.out or a.root / 'missions-backtest-input.json'
    if ROOT in out.resolve().parents:
        raise SystemExit('Refusing to write private archive derivatives inside the repository')
    result = export(a.root)
    out.write_bytes(encoded(result))
    print(json.dumps({'records': len(result['records']), 'gaps': result['gaps'], 'out': str(out)}))


if __name__ == '__main__':
    main()
