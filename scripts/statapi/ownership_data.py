"""Joins the archived contest pools (actual field/CPT/FLEX ownership, salary, points) with the provider's archived slate projections (projected ownership, projection, quantiles).

Everything is read from the local archive; no API access is needed. The provider's projections are served by a current engine (backfilled/fallback flags in `_metadata`), so they are
a BENCHMARK for ownership models, not proof of what was knowable before lock; `projection_time` is kept so that can be checked.
"""
import gzip
import json
import sqlite3
from pathlib import Path

import pandas as pd


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_projection_table(path):
    d = json.loads(gzip.open(path, 'rb').read().decode('utf-8'))
    rows = []
    meta = d.get('_metadata') or {}
    for p in d.get('projections', []):
        pl, pr, ow = p.get('player') or {}, p.get('projection') or {}, p.get('ownership') or {}
        prov = p.get('provenance') or {}
        rows.append({'canonical_player_id': pl.get('player_id'), 'name': pl.get('name'), 'team': pl.get('team'), 'position': pl.get('position'), 'salary_proj': pl.get('salary'),
                     'proj_pts': _num(pr.get('fantasy_pts')), 'proj_floor': _num(pr.get('floor')), 'proj_ceiling': _num(pr.get('ceiling')), 'proj_sd': _num(pr.get('std_dev')),
                     'proj_own_pct': _num(ow.get('ownership_pct')), 'proj_cpt_own': _num(ow.get('captain_ownership')), 'proj_flex_own': _num(ow.get('flex_ownership')),
                     'proj_total_own': _num(ow.get('total_ownership')), 'proj_time': prov.get('last_update_time'), 'served_source': (d.get('source') or {}).get('name'),
                     'backfilled': meta.get('backfilled'), 'fallback': meta.get('fallback'), 'implied_total': (p.get('vegas_odds') or {}).get('team_implied_total') if isinstance(p.get('vegas_odds'), dict) else None})
    return pd.DataFrame(rows)


def build(archive_root):
    root = Path(archive_root)
    db = sqlite3.connect(str(root / 'inventory.sqlite'))
    contests = db.execute("select c.id, c.slate_id, s.date, s.game_type, s.start_time, c.entry_count, c.entry_fee, c.prize_pool, c.name from contests c join slates s on s.id=c.slate_id "
                          "where c.id in (select cast(key as integer) from fetch_log where kind='contest' and status like 'ok%')").fetchall()
    proj_paths = {int(k): p for k, p in db.execute("select key, raw_path from fetch_log where kind='projections' and status='ok'")}
    frames = []
    for cid, slate_id, date, game_type, start, entries, fee, prize, name in contests:
        pool = pd.read_parquet(root / 'normalized' / f'contest_{cid}' / 'pool.parquet')
        pool = pool[~pool.is_unresolved.fillna(False).astype(bool)].copy()
        pool['contest_id'], pool['slate_id'], pool['date'], pool['game_type'], pool['start_time'], pool['entries'], pool['entry_fee_cents'], pool['prize_pool_cents'], pool['contest_name'] = \
            cid, slate_id, date, game_type, start, entries, fee, prize, name
        if slate_id in proj_paths:
            proj = load_projection_table(proj_paths[slate_id]).drop_duplicates('canonical_player_id')
            pool = pool.merge(proj.drop(columns=['name', 'team', 'position']), on='canonical_player_id', how='left')
        frames.append(pool)
    return pd.concat(frames, ignore_index=True)
