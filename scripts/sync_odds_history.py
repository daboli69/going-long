"""Back up the finished historical archive through GOING's private write-only API.

Never reads the sportsbook credential, calls its provider, or alters live feeds.
Uploads originals, acquisition receipts and per-event indexes; manifest goes last.
"""
import argparse
import base64
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

import requests

from odds_history import default_root, encoded, iso

ENDPOINT = 'https://going-long.vercel.app/api/odds-history'
MAX_BYTES = 200_000_000  # Additional private Storage, no database rows/paid quota.


def stage(root):
    root = Path(root)
    summary = json.loads((root / 'summary.json').read_text())
    if not summary.get('acquisition_complete') or summary['control'].get('stopped'):
        raise ValueError('Acquisition must finish cleanly before cloud publication')
    plan = json.loads((root / 'plan.json').read_text())
    cloud = root / 'cloud'
    cloud.mkdir(exist_ok=True)
    objects = []

    def add(kind, data=None, raw=None):
        raw = raw if raw is not None else gzip.compress(encoded(data), compresslevel=6, mtime=0)
        if len(raw) > 2_800_000 or len(gzip.decompress(raw)) > 8_000_000:
            raise ValueError('Historical object exceeds safe server size; originals retained')
        digest = hashlib.sha256(raw).hexdigest()
        path = cloud / (kind + '-' + digest + '.json.gz')
        if not path.exists(): path.write_bytes(raw)
        objects.append({'kind': kind, 'sha256': digest, 'path': path, 'bytes': len(raw)})
        return digest

    with closing(sqlite3.connect(root / 'index.sqlite3')) as db:
        db.row_factory = sqlite3.Row
        receipts = []
        for row in db.execute("SELECT * FROM pulls WHERE state='complete' ORDER BY id"):
            raw = (root / 'raw' / (row['id'] + '.json.gz')).read_bytes()
            if hashlib.sha256(gzip.decompress(raw)).hexdigest() != row['sha256']:
                raise ValueError('Original response checksum mismatch')
            params = json.loads(row['params'])
            if any(any(word in k.lower() for word in ('key', 'token', 'secret')) for k in params):
                raise ValueError('Private credential must never enter archive transport')
            receipts.append({**{k: row[k] for k in ('id', 'path', 'charge', 'snapshot_at', 'captured_at')},
                             'params': params, 'rawJsonSha256': row['sha256'], 'rawGzipSha256': add('raw', raw=raw)})
        gaps = [{**dict(r), 'params': json.loads(r['params'])} for r in db.execute("SELECT id,path,params,state,charge,captured_at FROM pulls WHERE state!='complete' ORDER BY id")]
        receipt_sha = add('receipts', {'schema': 'going-odds-history-receipts-v1', 'requests': receipts,
                                     'gaps': gaps, 'summary': summary})
        events = []
        for (event_id,) in db.execute('SELECT DISTINCT event_id FROM quotes ORDER BY event_id'):
            rows = [dict(r) for r in db.execute('SELECT * FROM quotes WHERE event_id=? ORDER BY snapshot_at DESC,id', (event_id,))]
            # Historic board snapshots can include future games. Keep them in the
            # originals, but only expose completed, cutoff-eligible game histories.
            rows = [r for r in rows if iso(r['kickoff']) <= iso(plan['cutoff'])]
            if not rows: continue
            digest = add('event', {'schema': 'going-odds-history-event-v1', 'id': event_id, 'quotes': rows})
            first = rows[0]
            events.append({'id': event_id, 'sha256': digest, 'home': first['home'], 'away': first['away'],
                           'kickoff': first['kickoff'], 'quotes': len(rows),
                           'books': sorted({r['book'] for r in rows}), 'markets': sorted({r['market'] for r in rows}),
                           'firstSnapshot': rows[-1]['snapshot_at'], 'lastSnapshot': rows[0]['snapshot_at']})
    events.sort(key=lambda e: e['kickoff'], reverse=True)
    index = {'schema': 'going-odds-history-index-v1', 'historicalOnly': True,
             'archiveId': hashlib.sha256(encoded(plan)).hexdigest(), 'cutoff': plan['cutoff'],
             'generatedAt': datetime.now(timezone.utc).isoformat(), 'receiptsSha256': receipt_sha,
             'credits': summary['credits_charged_or_reserved'], 'quotes': sum(e['quotes'] for e in events), 'events': events}
    add('index', index)
    if sum((o['bytes'] + 2) // 3 * 4 + 256 for o in objects) > MAX_BYTES:
        raise ValueError('Additional cloud backup exceeds200MB; local data intact, no paid storage used')
    return objects, index


def sync(root, *, post=requests.post, token=None):
    objects, index = stage(root)
    if token is None:
        # Existing constrained upload credential; no database or sportsbook key.
        config = Path(root).parent / 'fp-uploader.json'
        token = json.loads(config.read_text())['token']
    if not isinstance(token, str) or len(token) < 32: raise ValueError('Private upload token unavailable')
    ack_path = Path(root) / 'cloud-ack.json'
    ack = json.loads(ack_path.read_text()) if ack_path.exists() else {}
    current_ids = {obj['kind'] + '/' + obj['sha256'] for obj in objects}
    def upload(obj):
        identity = obj['kind'] + '/' + obj['sha256']
        body = {'schema': 'going-odds-history-upload-v1', 'kind': obj['kind'], 'sha256': obj['sha256'],
                'gzip': base64.b64encode(obj['path'].read_bytes()).decode()}
        try:
            response = post(ENDPOINT, headers={'Authorization': 'Bearer ' + token}, json=body,
                            timeout=(10, 65), allow_redirects=False)
            result = response.json() if response.status_code == 200 else {}
        except (requests.RequestException, ValueError):
            raise RuntimeError('Private archive sync interrupted; originals retained, retry is idempotent') from None
        if not result.get('ok') or result.get('sha256') != obj['sha256'] or result.get('bytes') != obj['bytes']:
            raise RuntimeError(f'Private archive write not verified (HTTP {response.status_code}); originals retained')
        return identity, obj

    def acknowledge(identity, obj):
        ack[identity] = {'bytes': obj['bytes']}
        ack_path.write_bytes(encoded(ack))
        print(json.dumps({'uploaded': len(current_ids & ack.keys()), 'objects': len(objects), 'kind': obj['kind']}), flush=True)

    pending = [obj for obj in objects if obj['kind'] != 'index' and not ack.get(obj['kind'] + '/' + obj['sha256'])]
    # Immutable, unrelated object writes may overlap. The mutable index remains
    # strictly last; checkpoint acknowledgements are written only on this thread.
    with ThreadPoolExecutor(max_workers=6) as pool:
        for future in as_completed([pool.submit(upload, obj) for obj in pending]):
            acknowledge(*future.result())
    acknowledge(*upload(objects[-1]))
    result = {'events': len(index['events']), 'quotes': index['quotes'], 'credits': index['credits'],
              'objects': len(objects), 'compressed_bytes': sum(o['bytes'] for o in objects),
              'estimated_storage_bytes': sum((o['bytes'] + 2) // 3 * 4 + 256 for o in objects), 'verified_upload': True}
    (Path(root) / 'cloud-summary.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=default_root())
    p.add_argument('--stage-only', action='store_true')
    args = p.parse_args()
    if args.stage_only:
        objects, index = stage(args.root)
        print(json.dumps({'objects': len(objects), 'bytes': sum(o['bytes'] for o in objects), 'events': len(index['events']), 'quotes': index['quotes']}))
    else:
        try: print(json.dumps(sync(args.root), indent=2))
        except RuntimeError as error: print(str(error)); raise SystemExit(1)
