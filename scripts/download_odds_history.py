"""One-time, quota-limited historical acquisition. No current endpoints or alerts."""
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time

from odds_history import Archive, BOOKS, PROPS, ROOT, default_root, encoded, iso


def run(root=None):
    archive = Archive(root or default_root())
    key = json.loads((archive.root / 'credential.json').read_text())['api_key']
    plan_path = archive.root / 'plan.json'
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        schedule = json.loads((ROOT / 'data/nfl_betting.json').read_text(encoding='utf-8'))
        windows = sorted({(iso(game['kickoff']) - timedelta(minutes=30)).isoformat()
                          for game in schedule['games'] if game.get('completed') is True
                          and game.get('season') in (2024, 2025, 2026)
                          and iso(game['kickoff']) < cutoff}, reverse=True)
        plan = {'schema': 'going-history-acquisition-v1', 'cutoff': cutoff.isoformat(),
                'seasons': [2024, 2025, 2026], 'sport': 'americanfootball_nfl',
                'bookmakers': BOOKS, 'featured_windows': windows,
                'pregame_minutes': 30, 'selection': 'outcome-blind round-robin seasons, sha256 event order',
                'lifetime_credit_limit': 20000, 'props': PROPS}
        plan_path.write_bytes(encoded(plan))
    cutoff = iso(plan['cutoff'])
    base = '/v4/historical/sports/americanfootball_nfl'
    def fetch(path, date, markets, cost):
        body = archive.request(path, {'date': date, 'bookmakers': plan['bookmakers'],
                                     'markets': markets, 'oddsFormat': 'american'}, cost, key)
        status = archive.status()
        # Contains counts only, never credentials, request URLs or raw responses.
        summary = {k: status[k] for k in ['credits_charged_or_reserved', 'requests', 'quotes', 'events']}
        (archive.root / 'progress.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary), flush=True)
        if body is not None:
            time.sleep(.25)
        return body
    for date in plan['featured_windows']:
        fetch(base + '/odds', date, 'h2h,spreads,totals', 30)
    # Historical event ids come from already purchased snapshots, not a new live feed.
    with closing(archive.connect()) as db:
        events = db.execute('SELECT event_id,MAX(kickoff) FROM quotes GROUP BY event_id').fetchall()
    buckets = defaultdict(list)
    for event, kickoff in events:
        date = iso(kickoff)
        season = date.year - int(date.month < 7)
        if season in plan['seasons'] and date < cutoff:
            buckets[season].append((event, kickoff))
    for rows in buckets.values():
        rows.sort(key=lambda row: hashlib.sha256(row[0].encode()).hexdigest())
    ordered = []
    while any(buckets.values()):
        for season in reversed(plan['seasons']):
            if buckets[season]: ordered.append(buckets[season].pop())
    for event, kickoff in ordered:
        date = (iso(kickoff) - timedelta(minutes=plan['pregame_minutes'])).isoformat()
        fetch(base + '/events/' + event + '/odds', date, plan['props'], 60)
    # Spend a remainder only on new useful market scopes, never on repeat snapshots.
    status = archive.status()
    remaining = min(20000 - status['credits_charged_or_reserved'], int(status['control'].get('provider_remaining', 0)))
    if remaining >= 10:
        for event, kickoff in reversed(ordered):
            date = (iso(kickoff) - timedelta(hours=24)).isoformat()
            count = min(6, remaining // 10)
            if count < 1: break
            fetch(base + '/events/' + event + '/odds', date, ','.join(plan['props'].split(',')[:count]), 10 * count)
            status = archive.status()
            remaining = min(20000 - status['credits_charged_or_reserved'], int(status['control'].get('provider_remaining', 0)))
    status = archive.status()
    status['acquisition_complete'] = True
    status['remaining_below_cheapest_odds_request'] = min(20000 - status['credits_charged_or_reserved'], int(status['control'].get('provider_remaining', 0))) < 10
    (archive.root / 'summary.json').write_text(json.dumps(status, indent=2))
    print(json.dumps(status, indent=2), flush=True)


if __name__ == '__main__':
    try:
        run()
    except RuntimeError as error:
        # Provider/transport exceptions in Archive are deliberately credential-free.
        print(str(error), flush=True)
        raise SystemExit(1)
