"""One Windows sign-in worker, with private credentials and restart-safe storage."""
import contextlib
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / 'private'


def refresh_inputs():
    """Refresh settlement inputs, retaining the last usable file during outages."""
    target = PRIVATE / 'scanner-data' / 'data'
    target.mkdir(parents=True, exist_ok=True)
    for name, required in [('results.json', 'games'), ('history.json', 'betting'), ('nfl_betting.json', 'games')]:
        path = target / name
        if not path.exists():
            shutil.copyfile(ROOT / 'data' / name, path)
        try:
            response = requests.get('https://raw.githubusercontent.com/daboli69/going-long/main/data/' + name, timeout=30)
            response.raise_for_status()
            body = response.json()
            if required not in body:
                raise ValueError('Missing required dataset field')
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(body, allow_nan=False), encoding='utf-8')
            temp.replace(path)
        except (requests.RequestException, ValueError):
            logging.warning('Input refresh unavailable: %s; retaining last file', name)


def main():
    PRIVATE.mkdir(exist_ok=True)
    import msvcrt
    lock = open(PRIVATE / 'scanner.lock', 'a+b')
    lock.seek(0)
    if not lock.read(1):
        lock.write(b'1'); lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return  # Another sign-in or manually started collector already owns it.
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(PRIVATE / 'scanner.log', maxBytes=2_000_000, backupCount=3)], format='%(asctime)s %(levelname)s %(message)s')
    os.environ.update(json.loads((PRIVATE / 'connections.json').read_text(encoding='utf-8')))
    os.environ['TOPDOWN_DATA_ROOT'] = str(PRIVATE / 'scanner-data')
    os.environ['TOPDOWN_STATUS_FILE'] = str(PRIVATE / 'scanner-status.json')
    from scan_markets import scan
    from topdown.journal import Journal
    journal = Journal(PRIVATE / 'topdown.sqlite')
    next_refresh = 0
    next_finals = 0
    next_board = 0
    logging.info('Collector started; 60-second polling while this PC is awake')
    while True:
        started = time.monotonic()
        try:
            if started >= next_refresh:
                refresh_inputs()
                next_refresh = time.monotonic() + 3600
            if started >= next_finals:
                from topdown.live_results import refresh_finals
                logging.info('Final score refresh: %s',refresh_finals(PRIVATE / 'scanner-data',time.time()))
                next_finals=time.monotonic()+120
            if started >= next_board:
                from topdown.tracking import collect_board
                try:logging.info('Automatic board picks frozen: %s',collect_board(journal,ROOT,time.time()))
                except Exception as exc:logging.warning('Board tracking unavailable: %s',type(exc).__name__)
                next_board=time.monotonic()+300
            with contextlib.redirect_stdout(io.StringIO()):
                result = scan(journal, send=True)
            logging.info('Scan: pairs=%s eligible=%s delivery=%s failures=%s', result['quote_pairs'], result['actionable_predictions'], result['supabase']['status'], len(result['failures']))
        except Exception as exc:
            # Request exceptions can contain credential-bearing URLs.
            logging.error('Scan failed: %s; retrying next cycle', type(exc).__name__)
        time.sleep(max(10, 60 - (time.monotonic() - started)))


if __name__ == '__main__':
    main()
