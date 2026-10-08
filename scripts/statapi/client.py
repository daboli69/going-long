"""stat-api client for the private historical DFS archive.

* The key is read ONLY from the STATAPI_KEY environment variable. It is never written to disk, logged or put in a URL.
* Every response is stored byte-for-byte (content-addressed) before anything parses it; quota headers are logged after each call.
* 429 -> wait Retry-After and retry; other errors are raised, never swallowed, and never retried in a loop.
* Documentation: https://stat-api.com/docs/api/dfs/ (base https://api.stat-api.com/api/v1/dfs/, Authorization: Bearer <key>).
"""
import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://api.stat-api.com/api/v1/dfs/'
USER_AGENT = 'going-research/1.0 (personal historical archive)'
MIN_INTERVAL = 0.15  # about 400 requests per minute, under the 600 per minute limit


class ApiError(RuntimeError):
    def __init__(self, status, message, url):
        super().__init__(f'HTTP {status} for {url}: {message}')
        self.status = status


class Client:
    def __init__(self, archive_root, key=None, quota_floor=0):
        self.key = key or os.environ.get('STATAPI_KEY')
        if not self.key:
            raise RuntimeError('STATAPI_KEY is not set in the environment')
        self.root = Path(archive_root)
        (self.root / 'raw').mkdir(parents=True, exist_ok=True)
        (self.root / 'logs').mkdir(parents=True, exist_ok=True)
        self.quota = {}
        self.quota_floor = quota_floor  # refuse to start a download that would leave less than this many records
        self._last = 0.0

    def _log(self, line):
        with open(self.root / 'logs' / 'requests.log', 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')

    def get(self, path, params=None, raw_dir='misc', expect_json=True):
        """GET base+path. Returns (parsed_or_text, raw_path, headers). The raw body is archived under raw/<raw_dir>/<sha256>.<ext> before parsing."""
        url = BASE + path.lstrip('/') + ('?' + urllib.parse.urlencode(params) if params else '')
        for attempt in range(6):
            wait = MIN_INTERVAL - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + self.key, 'User-Agent': USER_AGENT, 'Accept': 'application/json' if expect_json else '*/*'})
            self._last = time.time()
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    body = response.read()
                    headers = {k.lower(): v for k, v in response.headers.items()}
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    delay = int(error.headers.get('Retry-After', '5'))
                    self._log(f'429 {path} retry-after {delay}s')
                    time.sleep(delay + 1)
                    continue
                raise ApiError(error.code, error.read()[:300].decode('utf-8', 'replace'), url.split('?')[0])
            except (urllib.error.URLError, TimeoutError) as error:
                self._log(f'network {path}: {error}')
                time.sleep(2 ** attempt)
                continue
            digest = hashlib.sha256(body).hexdigest()
            # stored gzip-compressed; the file name is the sha256 of the ORIGINAL bytes so the provider response can always be re-verified
            target = self.root / 'raw' / raw_dir / f'{digest}.{"json" if expect_json else "csv"}.gz'
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(target.suffix + '.tmp')
                temporary.write_bytes(gzip.compress(body, 6))
                os.replace(temporary, target)
            self.quota = {'limit': headers.get('x-quota-limit'), 'used': headers.get('x-quota-used'), 'remaining': headers.get('x-quota-remaining')}
            self._log(f'200 {path} bytes={len(body)} quota_used={self.quota["used"]} remaining={self.quota["remaining"]}')
            return (json.loads(body) if expect_json else body.decode('utf-8')), target, headers
        raise ApiError(0, 'gave up after repeated rate-limit/network errors', url.split('?')[0])

    def pages(self, path, params, wrapper, raw_dir, limit=5000):
        """Cursor pagination (limit / from_id -> next_from_id). Yields rows."""
        cursor = None
        while True:
            query = {**params, 'limit': limit}
            if cursor is not None:
                query['from_id'] = cursor
            data, _, _ = self.get(path, query, raw_dir)
            for row in data[wrapper]:
                yield row
            cursor = data.get('next_from_id')
            if cursor is None:
                return
