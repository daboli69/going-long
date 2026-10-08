"""Phase 1 of the stat-api historical archive: slate and contest INVENTORY only (slate rows cost 1 record each; contest listings are free).

Writes <archive>/inventory.sqlite (slates, contests). Resumable: a slate whose contests are already stored is skipped. Run:
    STATAPI_KEY=... python scripts/statapi/inventory.py <archive_root> [first_date] [last_date]
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from statapi.client import Client  # noqa: E402

SCHEMA = """
create table if not exists slates(id integer primary key, date text, name text, game_type text, main integer, game_count integer, contest_count integer, lineup_contest_count integer,
  status text, start_time text, raw text);
create table if not exists contests(id integer primary key, slate_id integer, name text, contest_type integer, entry_count integer, entry_fee integer, prize_pool integer, paid_places integer,
  max_entries integer, max_entries_per_user integer, lineups_status text, status text, guaranteed integer, raw text);
create table if not exists inventory_progress(slate_id integer primary key, contests_fetched integer);
"""


def open_db(root):
    db = sqlite3.connect(str(Path(root) / 'inventory.sqlite'))
    db.executescript(SCHEMA)
    return db


def fetch_slates(client, db, first, last):
    for slate in client.pages('slates', {'operator': 'draftkings', 'sport': 'nfl', 'date__gte': first, 'date__lte': last}, 'slates', 'slates'):
        db.execute('insert or replace into slates values(?,?,?,?,?,?,?,?,?,?,?)', (slate['id'], slate['date'], slate['name'], slate['game_type'], int(bool(slate['main'])), slate['game_count'],
                                                                                  slate['contest_count'], slate['lineup_contest_count'], slate['status'], slate['start_time'], json.dumps(slate)))
    db.commit()


def fetch_contests(client, db):
    todo = [r[0] for r in db.execute("select id from slates where contest_count>0 and id not in (select slate_id from inventory_progress) order by date")]
    for number, slate_id in enumerate(todo, 1):
        for c in client.pages('contests', {'slate_id': slate_id}, 'contests', 'contests'):
            db.execute('insert or replace into contests values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (c['id'], slate_id, c['name'], c['contest_type'], c['entry_count'], c['entry_fee'], c['prize_pool'], c['paid_places'],
                                                                                                c['max_entries'], c['max_entries_per_user'], c.get('lineups_status'), c['status'], c['guaranteed'], json.dumps(c)))
        db.execute('insert or replace into inventory_progress values(?,1)', (slate_id,))
        db.commit()
        if number % 100 == 0:
            print(f'contests fetched for {number}/{len(todo)} slates; quota used {client.quota.get("used")}', flush=True)


if __name__ == '__main__':
    root = sys.argv[1]
    first, last = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ('2021-01-01', '2026-12-31')
    client = Client(root)
    db = open_db(root)
    fetch_slates(client, db, first, last)
    print('slates stored:', db.execute('select count(*) from slates').fetchone()[0], 'quota used', client.quota.get('used'), flush=True)
    fetch_contests(client, db)
    print('contests stored:', db.execute('select count(*) from contests').fetchone()[0], 'quota used', client.quota.get('used'), flush=True)
