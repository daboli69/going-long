"""Bounded, parallel, poison-safe collector for official NBA injury-report PDFs (live and recent days).

Why this exists: nba_lab.injury_reports.fetch records every HTTP 403 in the manifest forever. For a slot that has not been published
yet, 403 is expected and says nothing about the future, but the stock collector walks every remaining game day of the season and probes
dozens of future slots per day. That is slow (over 30 minutes for 2026-27) and it permanently marks tomorrow's real report slots as
missing. This module (1) never caches a miss unless the slot is old enough that it would exist by now, (2) never probes slots after
the current time, (3) probes a day's slots in parallel with short timeouts under a hard deadline, and (4) can purge the poisoned entries.
Selection and parsing reuse nba_lab.injury_reports unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from pathlib import Path
import pandas as pd
import requests
from nba_lab import injury_reports as IR
from nba_lab.config import CACHE, atomic, now

ET = IR.ET
MISS_GRACE = pd.Timedelta(hours=3)        # a missing slot is only trusted this long after its nominal time
LOCK = threading.Lock()
UA = {'User-Agent': 'NBA-Ensemble-Local-Research/1.0'}


def slot_time(url: str) -> pd.Timestamp:
    m = re.search(r'Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})(?:_(\d{2}))?(AM|PM)', url)
    day, hh, mm, ap = m.group(1), m.group(2), m.group(3) or '00', m.group(4)
    return pd.Timestamp(pd.to_datetime(f'{day} {hh}:{mm} {ap}', format='%Y-%m-%d %I:%M %p')).tz_localize(
        ET, ambiguous=True, nonexistent='shift_forward')


def purge_untrusted_misses(manifest: dict, backup=True) -> int:
    """Drop recorded misses that were recorded before the slot could be expected to exist."""
    bad = []
    for url, v in manifest.items():
        if v['status'] == 200:
            continue
        retrieved = pd.Timestamp(v['retrieved_at']).tz_convert(ET)
        if slot_time(url) + MISS_GRACE > retrieved:
            bad.append(url)
    if backup and bad:
        shutil.copy(IR.MANIFEST, IR.MANIFEST.with_name('MANIFEST.before_purge.json'))
    for url in bad:
        del manifest[url]
    return len(bad)


def safe_fetch(url: str, manifest: dict, session):
    """Return PDF bytes or None. Misses are cached only when trustworthy."""
    with LOCK:
        prior = manifest.get(url)
    if prior:
        return (Path(prior['path']).read_bytes(), prior) if prior['status'] == 200 else (None, prior)
    response = session.get(url, timeout=(5, 15), headers=UA)
    retrieved = now()
    if response.status_code in (403, 404):
        meta = {'status': response.status_code, 'retrieved_at': retrieved}
        if slot_time(url) + MISS_GRACE < pd.Timestamp(retrieved).tz_convert(ET):
            with LOCK:
                manifest[url] = meta
        return None, meta
    response.raise_for_status()
    body = response.content
    if not body.startswith(b'%PDF'):
        raise ValueError('Not a PDF: ' + url)
    checksum = hashlib.sha256(body).hexdigest()
    name = url.rsplit('/', 1)[1]
    directory = IR.ARCHIVE / name[14:24]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name[:-4] + '_' + checksum[:16] + '.pdf')
    if not path.exists():
        with path.open('xb') as f:
            f.write(body)
    modified = response.headers.get('Last-Modified')
    meta = {'status': 200, 'retrieved_at': retrieved, 'sha256': checksum, 'bytes': len(body), 'path': str(path),
            'last_modified': parsedate_to_datetime(modified).isoformat() if modified else None}
    with LOCK:
        manifest[url] = meta
    return body, meta


def day_report(day: str, first_tipoff, manifest, session, pool, now_et, lead_hours=1.0, deadline=None):
    """Latest report for one ET game day published at or before first tipoff - lead, probing only slots that can exist already."""
    cutoff = pd.Timestamp(first_tipoff).tz_convert(ET) - pd.Timedelta(hours=lead_hours)
    limit = min(cutoff, now_et)
    slots = IR.candidate_slots(limit)
    urls = [IR.slot_url(s) for s in slots]
    results = list(pool.map(lambda u: safe_fetch(u, manifest, session), urls))
    if deadline and time.time() > deadline:
        raise TimeoutError('collector deadline exceeded')
    for slot, url, (body, meta) in zip(slots, urls, results):
        if body is None:
            continue
        stamp, rows, issues = IR.parse_pdf(body)
        modified = pd.Timestamp(meta['last_modified']).tz_convert(ET) if meta.get('last_modified') else None
        published = max(t for t in (stamp, slot, modified) if t is not None)
        if published > cutoff:
            continue
        return {'day': day, 'url': url, 'slot': slot, 'report_time': stamp, 'available_at': published.tz_convert('UTC'),
                'cutoff': cutoff, 'sha256': meta['sha256'], 'retrieved_at': meta['retrieved_at'], 'rows': rows,
                'tried': len(urls), 'issues': issues}
    return {'day': day, 'url': None, 'cutoff': cutoff, 'rows': [], 'tried': len(urls), 'issues': []}


def collect(season: int, days_back: int = 3, deadline_s: float = 240.0, workers: int = 8, log=print):
    """Collect reports for the given season's game days from `days_back` days ago through today (ET) and merge into the cache."""
    t0 = time.time()
    deadline = t0 + deadline_s
    games = pd.read_parquet(CACHE / 'games.parquet')
    players = pd.read_parquet(CACHE / 'player_boxes.parquet')
    manifest = IR._manifest()
    purged = purge_untrusted_misses(manifest)
    log('purged untrusted misses:', purged)
    now_et = pd.Timestamp.now(tz='UTC').tz_convert(ET)
    g = games[games.season == season].copy()
    g['day'] = g.tipoff.dt.tz_convert(ET).dt.strftime('%Y-%m-%d')
    days = g.groupby('day').tipoff.min().reset_index()
    days = days[(pd.to_datetime(days.day) <= now_et.tz_localize(None).normalize()) &
                (pd.to_datetime(days.day) >= now_et.tz_localize(None).normalize() - pd.Timedelta(days=days_back))]
    session = requests.Session()
    frames, reports = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for day, tip in days.itertuples(index=False):
            rep = day_report(day, tip, manifest, session, pool, now_et, deadline=deadline)
            reports.append(rep)
            if rep['rows']:
                frames.append(pd.DataFrame(rep['rows']).assign(
                    season=season, report_day=day, report_url=rep['url'], report_sha256=rep['sha256'],
                    report_time=rep['report_time'].tz_convert('UTC'), available_at=rep['available_at']))
            log(day, 'report', rep['url'].rsplit('/', 1)[-1] if rep['url'] else None, 'rows', len(rep['rows']),
                'slots probed', rep['tried'], f'{time.time() - t0:.0f}s')
    atomic(IR.MANIFEST, manifest)
    if not frames:
        return {'rows': 0, 'days': len(days), 'seconds': time.time() - t0, 'purged': purged}
    rows = pd.concat(frames, ignore_index=True)
    same_day = rows.game_date.eq(pd.to_datetime(rows.report_day).dt.strftime('%m/%d/%Y'))
    rows = rows[same_day].reset_index(drop=True)
    rows['player_name'] = rows.player_name_raw.map(IR.display_name)
    rows = IR.map_rows(rows, games, players)
    rows['retrieved_at'] = rows.report_url.map(lambda u: manifest[u]['retrieved_at'])
    existing = pd.read_parquet(IR.OUTPUT)
    keep = existing[~((existing.season == season) & existing.report_day.isin(rows.report_day.unique()))]
    merged = pd.concat([keep, rows], ignore_index=True)
    merged.to_parquet(IR.OUTPUT, index=False)
    first_tip = g.groupby('game_id').tipoff.min()
    chk = rows.dropna(subset=['game_id'])
    chk = chk.assign(tip=chk.game_id.map(first_tip))
    assert len(chk) > 0, 'no mapped injury rows: the timing check would compare nothing'
    ok = bool((pd.to_datetime(chk.available_at, utc=True) < pd.to_datetime(chk.tip, utc=True)).all())
    return {'rows': len(rows), 'rows_with_game_id': len(chk), 'days': len(days), 'available_before_tipoff_all': ok,
            'seconds': round(time.time() - t0, 1), 'purged': purged}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--days-back', type=int, default=3)
    ap.add_argument('--deadline', type=float, default=240.0)
    a = ap.parse_args()
    print(json.dumps(collect(a.season, a.days_back, a.deadline), indent=1, default=str))
