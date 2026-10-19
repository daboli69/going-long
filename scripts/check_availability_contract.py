"""Read-only check of live availability source contracts; no snapshots written."""
import json
from collections import Counter
from availability_source import load_source
from injury_context import build_current
import eligibility as E


def check():
    import os
    season = int(os.environ.get('SEASON', '2026'))
    roster, _ = load_source('rosters', season)
    injuries, _ = load_source('injuries', season, roster=roster)
    players, reports, *_ = build_current(season, injuries, [], roster, {}, [], [])
    invalid = []
    for kind, rows, validate in [('players', players, E._valid_player), ('reports', reports, E._valid_report)]:
        for key, row in rows.items():
            if not validate(row) or not isinstance(row.get('gsis_id'), str) or not row['gsis_id'].strip():
                invalid.append({'kind': kind, 'key': key, 'fields': {k: row.get(k) for k in
                    ['gsis_id', 'roster_status', 'roster_week', 'team', 'week', 'report_status', 'practice_status']}})
    print(json.dumps({'report_statuses': dict(Counter(str(r.get('report_status')) for r in reports.values())),
                      'invalid': invalid}, indent=2))
    return 1 if invalid else 0


if __name__ == '__main__':
    raise SystemExit(check())
