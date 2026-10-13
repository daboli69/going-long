"""Automatic private inbox intake, for a Windows scheduled task. No paid APIs or public writes."""
import argparse
import json
import datetime as dt
import os
import urllib.request
import time
import sys
import hashlib
from pathlib import Path
from fp_ingest.registry import load
from fp_ingest.store import RunLock
from fp_ingest.store import write_json
from fp_ingest.weekly import sync


def prediction_period(schedule, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    season = now.year if now.month >= 7 else now.year - 1
    games = schedule.get('games', [])
    future = []
    for game in games:
        if game.get('season') != season or not isinstance(game.get('week'), int) or not 1 <= game['week'] <= 18:
            continue
        try:
            kickoff = dt.datetime.fromisoformat(game['kickoff'].replace('Z', '+00:00'))
            if kickoff.tzinfo and kickoff > now:
                future.append((kickoff, game['week']))
        except (ValueError, KeyError, TypeError):
            continue
    if not future:
        raise ValueError('No verified upcoming current-season NFL game; not guessing from a folder name or stale roster week')
    return season, min(future)[1]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    p.add_argument('--schedule', required=True, help='GOING nfl_betting.json with dated season/week games')
    a = p.parse_args(argv)
    schedule = json.loads(Path(a.schedule).read_text(encoding='utf-8'))
    season, week = prediction_period(schedule)
    with RunLock(a.root):
        report = sync(a.root, load(), season, week)
        token = os.environ.get('GOING_FP_INGEST_TOKEN')
        endpoint = os.environ.get('GOING_FP_INGEST_URL')
        if token and endpoint:
            if endpoint != 'https://going-long.vercel.app/api/fp-ingest' or len(token) < 32:
                raise ValueError('Private uploader configuration invalid')
            body = (Path(a.root) / 'model_inputs/current.json').read_bytes()
            bundle = json.loads(body)
            fingerprint = hashlib.sha256(json.dumps([season,week,[(d['sha256'],d['scope']) for d in bundle['datasets']]]).encode()).hexdigest()
            published_path = Path(a.root) / 'model_inputs/last_published.json'
            published = json.loads(published_path.read_text()) if published_path.exists() else {}
            if published.get('fingerprint') == fingerprint and published.get('endpoint') == endpoint:
                report['sync'] = 'private_backend_unchanged_no_upload'
                write_json(Path(a.root) / 'model_inputs/status.json', report)
                print(json.dumps({'sync':report['sync'],'accepted':report['accepted']}))
                return 0
            try:
                request = urllib.request.Request(endpoint, data=body, method='POST', headers={
                    'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=20) as response:
                    receipt = json.load(response)
                    if response.status != 200 or receipt.get('ok') is not True or receipt.get('season') != season or receipt.get('week') != week or receipt.get('datasets') != len(bundle['datasets']):
                        raise RuntimeError('Private upload rejected')
                report['sync'] = 'private_backend_updated'
                write_json(published_path, {'fingerprint':fingerprint,'endpoint':endpoint,'at':dt.datetime.now(dt.timezone.utc).isoformat()})
            except Exception:
                report['sync'] = 'private_backend_failed_previous_inputs_retained'
            write_json(Path(a.root) / 'model_inputs/status.json', report)
    print(json.dumps({key: report[key] for key in ('season', 'prediction_week', 'files_scanned', 'accepted', 'sync')}))
    return 0


def watch(argv):
    # The lock is held for the life of the watcher; multiple startup/task launches
    # cannot run parallel import loops. Only the import itself uses .import.lock.
    root = Path(argv[argv.index('--root') + 1])
    lock_path = root / 'manifests/.autoload.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:return 0
        else:
            import fcntl
            try:fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:return 0
        write_json(root / 'manifests/autoload_process.json', {'pid':os.getpid(),'runtime':str(Path(__file__).resolve()),'started_at':dt.datetime.now(dt.timezone.utc).isoformat()})
        while True:
            try:main(argv)
            except Exception as error:
                write_json(root / 'model_inputs/last_error.json', {'at':dt.datetime.now(dt.timezone.utc).isoformat(),'error':type(error).__name__,'detail':str(error),'sync':'failed_previous_backend_inputs_retained'})
            time.sleep(300)


if __name__ == '__main__':
    args=sys.argv[1:]
    if '--watch' in args:
        args.remove('--watch');raise SystemExit(watch(args))
    raise SystemExit(main(args))
