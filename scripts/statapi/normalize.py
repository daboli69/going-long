"""Normalize one archived contest download into parquet and validate it. The raw response is never touched; everything here is re-derivable from it.

Outputs under <archive>/normalized/contest_<internal id>/ : pool.parquet, lineups.parquet, validation.json
Schema version is recorded in every validation.json so a later parser can re-derive and compare.
"""
import collections
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA = 'statapi-dfs-normalized-v1'
SALARY_CAP = 50000


def _f(value):
    return float('nan') if value is None else float(value)


def load_raw(path):
    return json.loads(gzip.open(path, 'rb').read().decode('utf-8'))


def normalize(data, meta):
    contest = data['contest']
    slots = contest['slots']
    showdown = contest['game_type'] == 'showdown'
    rows = []
    for p in data['player_pool']:
        o = p.get('ownership') or {}
        rows.append({'player_key': p['id'], 'slot': p['slot'], 'canonical_player_id': p.get('canonical_player_id'), 'name': p['name'], 'team': p['team'], 'position': p['position'], 'salary': p['salary'],
                     'fantasy_points': p['fantasy_points'], 'field_pct': o.get('field_pct'), 'cash_pct': o.get('cash_pct'), 'top1_pct': o.get('top1_pct'), 'cpt_field_pct': o.get('cpt_field_pct'),
                     'flex_field_pct': o.get('flex_field_pct'), 'is_unresolved': p.get('is_unresolved'), 'export_id': p.get('export_id')})
    pool = pd.DataFrame(rows)
    lineups = pd.DataFrame({'rank': [x['rank'] for x in data['lineups']], 'username': [x['username'] for x in data['lineups']], 'points': [x['points'] for x in data['lineups']],
                            'payout_cents': [x.get('payout_cents') for x in data['lineups']]})
    seats = np.array([x['slots'] for x in data['lineups']], dtype='int64') if data['lineups'] else np.zeros((0, len(slots)), dtype='int64')
    for i in range(seats.shape[1]):
        lineups[f'seat{i}'] = seats[:, i]
    lineups.attrs['slots'] = slots
    return pool, lineups, slots, showdown


def validate(data, meta, pool, lineups, slots, showdown):
    problems = []
    contest = data['contest']
    n = len(lineups)
    total = contest.get('total_entries')
    report = {'schema': SCHEMA, 'contest_internal_id': meta['id'], 'external_id': contest['id'], 'date': contest['date'], 'game_type': contest['game_type'], 'lineups': n, 'total_entries': total,
              'is_sampled': contest.get('is_sampled'), 'sampled_lineups_count': contest.get('sampled_lineups_count'), 'coverage': (n / total) if total else None}
    if total and n != total and not contest.get('is_sampled'):
        problems.append(f'unsampled contest has {n} lineups but {total} entries')
    if contest.get('is_sampled') and contest.get('sampled_lineups_count') not in (None, n):
        problems.append(f'sampled_lineups_count {contest.get("sampled_lineups_count")} != lineups {n}')
    if n == 0:
        problems.append('no lineups')
        report['problems'] = problems
        return report
    seat_cols = [f'seat{i}' for i in range(len(slots))]
    # (id, slot) uniqueness in the pool
    if pool.duplicated(['player_key', 'slot']).any():
        problems.append('duplicate (player, slot) pool rows')
    unresolved = int(pool.is_unresolved.fillna(False).astype(bool).sum())
    report['unresolved_pool_rows'] = unresolved
    # ownership ranges
    for col in ('field_pct', 'cpt_field_pct', 'flex_field_pct'):
        vals = pool[col].dropna()
        if len(vals) and ((vals < -1e-9) | (vals > 100 + 1e-9)).any():
            problems.append(f'{col} outside 0..100')
    report['ownership_available'] = bool(pool.field_pct.notna().any())
    if showdown:
        report['cpt_ownership_available'] = bool(pool.cpt_field_pct.notna().any())
        report['flex_ownership_available'] = bool(pool.flex_field_pct.notna().any())
    # lookup tables
    by_key = {}
    for r in pool.itertuples():
        by_key[(r.player_key, r.slot)] = r
    ids_in_pool = set(pool.player_key)
    seats = lineups[seat_cols].to_numpy()
    unresolved_ids = set(pool.loc[pool.is_unresolved.fillna(False).astype(bool) | pool.position.isna(), 'player_key'])
    zero = (seats == 0) | np.isin(seats, list(unresolved_ids)) if unresolved_ids else (seats == 0)  # athlete the provider could not resolve (id 0 or a negative placeholder): kept, never guessed
    report['unresolved_seats'] = int(zero.sum())
    report['lineups_with_unresolved_seat'] = int(zero.any(axis=1).sum())
    unknown = int((~np.isin(seats, list(ids_in_pool)) & ~zero).sum())
    if unknown:
        problems.append(f'{unknown} lineup seats reference players absent from the pool')
    salary = np.zeros(n)
    points = np.zeros(n)
    bad_roster = 0
    if showdown:
        cpt_salary = {k: _f(v.salary) for (k, s), v in by_key.items() if s in ('CPT', 'MVP')}
        flex_salary = {k: _f(v.salary) for (k, s), v in by_key.items() if s in ('FLEX', 'UTIL')}
        cpt_points = {k: _f(v.fantasy_points) for (k, s), v in by_key.items() if s in ('CPT', 'MVP')}
        flex_points = {k: _f(v.fantasy_points) for (k, s), v in by_key.items() if s in ('FLEX', 'UTIL')}
        first = seats[:, 0]
        salary += np.array([cpt_salary.get(i, np.nan) for i in first])
        points += np.array([cpt_points.get(i, np.nan) for i in first])
        for j in range(1, seats.shape[1]):
            col = seats[:, j]
            salary += np.array([flex_salary.get(i, np.nan) for i in col])
            points += np.array([flex_points.get(i, np.nan) for i in col])
        distinct = np.array([len(set(x for x in row if x != 0 and x not in unresolved_ids)) + sum(1 for x in row if x == 0 or x in unresolved_ids) for row in seats])
        bad_roster = int((distinct != seats.shape[1]).sum())  # one Captain and five different FLEX players: six distinct athletes (unresolved seats count as distinct)
        report['captain_slot_role'] = 'first seat'
    else:
        pos = {k: v.position for (k, s), v in by_key.items()}
        sal = {k: _f(v.salary) for (k, s), v in by_key.items()}
        pts = {k: _f(v.fantasy_points) for (k, s), v in by_key.items()}
        salary = np.array([[sal.get(i, np.nan) for i in row] for row in seats]).sum(axis=1)
        points = np.array([[pts.get(i, np.nan) for i in row] for row in seats]).sum(axis=1)
        expected = [s.rstrip('0123456789') for s in slots]
        for row in seats[: min(n, 20000)]:
            bad = False
            for want, athlete in zip(expected, row):
                if athlete == 0 or athlete in unresolved_ids:
                    continue
                got = pos.get(athlete)
                if (want == 'FLEX' and got not in ('RB', 'WR', 'TE')) or (want != 'FLEX' and got != want):
                    bad = True
                    break
            known = [x for x in row if x != 0 and x not in unresolved_ids]
            if bad or len(set(known)) != len(known):
                bad_roster += 1
    report['bad_roster_lineups'] = bad_roster
    if bad_roster:
        problems.append(f'{bad_roster} lineups violate the roster structure')
    complete = ~zero.any(axis=1)
    over_cap = int(((salary > SALARY_CAP + 1e-6) & complete).sum())
    report['over_cap_lineups'] = over_cap
    report['mean_salary_used'] = float(np.nanmean(salary[complete])) if complete.any() else None
    report['mean_unused_salary'] = float(np.nanmean(SALARY_CAP - salary[complete])) if complete.any() else None
    if over_cap:
        problems.append(f'{over_cap} lineups exceed the {SALARY_CAP} cap')
    diff = np.abs(points - lineups.points.to_numpy())
    report['score_mismatch_over_0.05'] = int(((diff > 0.05) & complete).sum())
    report['score_mismatch_over_1'] = int(((diff > 1.0) & complete).sum())
    report['score_missing'] = int(np.isnan(diff).sum())
    if report['score_mismatch_over_1']:
        problems.append(f'{report["score_mismatch_over_1"]} lineup scores differ from the pool points by more than 1')
    ranks = lineups['rank'].to_numpy()
    report['rank_monotonic_by_points'] = bool((np.diff(lineups.points.to_numpy()[np.argsort(ranks, kind="stable")]) <= 1e-9).all())
    if not report['rank_monotonic_by_points']:
        problems.append('ranks are not ordered by points')
    report['paid_lineups'] = int((lineups.payout_cents.fillna(0) > 0).sum())
    report['total_payout_cents'] = float(lineups.payout_cents.fillna(0).sum())
    # duplication structure
    keys = [tuple(r) for r in seats]
    counts = collections.Counter(keys)
    report['unique_lineups'] = len(counts)
    report['duplicated_lineups'] = int(sum(c for c in counts.values() if c > 1))
    report['max_duplicates'] = max(counts.values())
    if showdown:
        by_set = collections.Counter(frozenset(k) for k in keys)
        by_cpt_flex = collections.Counter((k[0], frozenset(k[1:])) for k in keys)
        report['unique_player_sets'] = len(by_set)
        report['same_players_different_captain_extra'] = len(counts) - len(by_set)
        report['same_captain_different_flex_groups'] = len(by_cpt_flex)
    report['problems'] = problems
    return report


def run(archive_root, internal_id, raw_path, meta):
    data = load_raw(raw_path)
    pool, lineups, slots, showdown = normalize(data, meta)
    report = validate(data, meta, pool, lineups, slots, showdown)
    out = Path(archive_root) / 'normalized' / f'contest_{internal_id}'
    out.mkdir(parents=True, exist_ok=True)
    pool.to_parquet(out / 'pool.parquet')
    lineups.to_parquet(out / 'lineups.parquet')
    report['contest_meta'] = meta
    (out / 'validation.json').write_text(json.dumps(report, indent=1, default=str), encoding='utf-8')
    return report


if __name__ == '__main__':
    import sqlite3
    root = sys.argv[1]
    db = sqlite3.connect(str(Path(root) / 'inventory.sqlite'))
    rows = db.execute("select key, raw_path from fetch_log where kind='contest' and status in ('ok','ok_partial')").fetchall()
    for key, raw in rows:
        out = Path(root) / 'normalized' / f'contest_{key}' / 'validation.json'
        if out.exists() and '--force' not in sys.argv:
            continue
        c = db.execute('select id,name,contest_type,entry_count,entry_fee,prize_pool,paid_places,max_entries_per_user,slate_id from contests where id=?', (int(key),)).fetchone()
        meta = dict(zip(('id', 'name', 'contest_type', 'entry_count', 'entry_fee_cents', 'prize_pool_cents', 'paid_places', 'max_entries_per_user', 'slate_id'), c))
        r = run(root, key, raw, meta)
        print(key, r['lineups'], r['problems'] or 'ok', flush=True)
