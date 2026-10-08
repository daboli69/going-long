"""Resumable acquisition steps for the private stat-api DFS archive. Every step records what it fetched in inventory.sqlite (fetch_log) so a restart never repeats a completed
download. Usage (key only via the environment):
    STATAPI_KEY=... python scripts/statapi/archive.py <archive_root> projections [max_seconds]
    STATAPI_KEY=... python scripts/statapi/archive.py <archive_root> plan
    STATAPI_KEY=... python scripts/statapi/archive.py <archive_root> download [max_seconds] [budget_records]
"""
import collections
import datetime
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from statapi.client import ApiError, Client  # noqa: E402

EXTRA = """
create table if not exists fetch_log(kind text, key text, sha256 text, raw_path text, bytes integer, records_cost integer, fetched_at text, status text, note text, primary key(kind,key));
create table if not exists plan(contest_id integer primary key, slate_id integer, rank integer, tier text, est_cost integer, reason text);
"""


def db_open(root):
    db = sqlite3.connect(str(Path(root) / 'inventory.sqlite'))
    db.executescript(EXTRA)
    return db


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def projections(client, db, max_seconds):
    start = time.time()
    todo = [r[0] for r in db.execute("select id from slates where contest_count>0 and id not in (select cast(key as integer) from fetch_log where kind='projections' and status='ok') order by date")]
    done = 0
    for slate_id in todo:
        if time.time() - start > max_seconds:
            break
        before = int(client.quota.get('used') or 0)
        try:
            data, path, _ = client.get(f'slates/{slate_id}/projections', {'mode': 'full'}, 'projections')
            status, note = 'ok', data.get('projection_status')
        except ApiError as error:
            path, status, note = None, 'error', str(error)[:200]
            data = None
        db.execute('insert or replace into fetch_log values(?,?,?,?,?,?,?,?,?)', ('projections', str(slate_id), path.name.split('.')[0] if path else None, str(path) if path else None,
                                                                                  path.stat().st_size if path else None, int(client.quota.get('used') or 0) - before, now(), status, note))
        db.commit()
        done += 1
    left = db.execute("select count(*) from slates where contest_count>0 and id not in (select cast(key as integer) from fetch_log where kind='projections' and status='ok')").fetchone()[0]
    print(f'projections fetched this run: {done}; slates still to fetch: {left}; quota used {client.quota.get("used")}', flush=True)


# ------------------------------------------------------------------ plan
TARGET = {'showdown': 35000, 'classic': 40000}
BAND = {'showdown': (10000, 90000), 'classic': (10000, 120000)}
SHARE = {'showdown': 0.60, 'classic': 0.36}  # of the planned budget; the rest is held back for validation re-downloads and the second pass
BUDGET = 9_300_000


def day_class(date, start_time):
    weekday = datetime.date.fromisoformat(date).weekday()  # Monday 0
    hour = int(start_time[11:13]) if start_time else 0
    if weekday == 3:
        return 'thursday'
    if weekday == 0 or (weekday == 1 and hour < 6):
        return 'monday'
    if weekday == 6 or (weekday == 0 and False):
        return 'sunday_night' if hour >= 23 or hour < 6 else 'sunday_day'
    return 'other'


def plan(db):
    rows = db.execute("""select c.id,c.slate_id,s.date,s.game_type,s.start_time,c.name,c.entry_count,c.prize_pool,c.max_entries_per_user from contests c join slates s on s.id=c.slate_id
        where c.contest_type=0 and c.lineups_status='available' and c.status='Completed' and c.entry_count>=3000""").fetchall()
    by_slate = collections.defaultdict(list)
    for r in rows:
        by_slate[r[1]].append(r)
    picks = {'showdown': [], 'classic': []}
    for slate_id, contests in by_slate.items():
        game_type = contests[0][3]
        low, high = BAND[game_type]
        inside = [c for c in contests if low <= c[6] <= high]
        if not inside:  # only fields outside the band exist (tiny or enormous): left for the second pass
            continue
        best = min(inside, key=lambda c: abs(c[6] - TARGET[game_type]))
        picks[game_type].append(best)
    chosen = []
    for game_type, items in picks.items():
        budget = int(BUDGET * SHARE[game_type])
        strata = collections.defaultdict(list)
        for c in items:
            season = c[2][:4]
            strata[(season, day_class(c[2], c[4]))].append(c)
        for key in strata:  # inside a stratum, spread over the calendar: alternate from both ends, then the middle
            strata[key].sort(key=lambda c: c[2])
            ordered, lo, hi, toggle = [], 0, len(strata[key]) - 1, True
            while lo <= hi:
                ordered.append(strata[key][lo] if toggle else strata[key][hi])
                lo, hi = (lo + 1, hi) if toggle else (lo, hi - 1)
                toggle = not toggle
            strata[key] = ordered
        spent, rank, progressed = 0, 0, True
        while progressed:
            progressed = False
            for key in sorted(strata, key=lambda k: (k[0], k[1])):
                if not strata[key]:
                    continue
                c = strata[key].pop(0)
                cost = c[6] + 400  # entries plus the player pool rows (a Classic pool has a few hundred, Showdown about 2 x 100)
                if spent + cost > budget:
                    continue
                spent += cost
                rank += 1
                chosen.append((c[0], c[1], rank, game_type, cost, f'{key[0]} {key[1]} {game_type} entries {c[6]}'))
                progressed = True
    db.execute('delete from plan')
    db.executemany('insert into plan values(?,?,?,?,?,?)', chosen)
    db.commit()
    for game_type in ('showdown', 'classic'):
        r = db.execute('select count(*), sum(est_cost) from plan where tier=?', (game_type,)).fetchone()
        print(game_type, 'planned contests', r[0], 'estimated records', r[1])
    print('by season/type:')
    for r in db.execute("select substr(s.date,1,4), p.tier, count(*), sum(p.est_cost) from plan p join slates s on s.id=p.slate_id group by 1,2 order by 1,2"):
        print('  ', r)


# ------------------------------------------------------------------ download
def download(client, db, max_seconds, budget_records):
    start = time.time()
    spent_before = int(client.quota.get('used') or 0)
    rows = db.execute("select p.contest_id, p.est_cost, p.tier from plan p where p.contest_id not in (select cast(key as integer) from fetch_log where kind='contest' and status in ('ok','ok_partial')) order by p.rank").fetchall()
    # interleave tiers by the order of rank within tier so Showdown and Classic both advance
    n = 0
    for contest_id, est, tier in rows:
        if time.time() - start > max_seconds:
            break
        used = int(client.quota.get('used') or 0)
        if used + est > budget_records:
            db.execute('insert or replace into fetch_log values(?,?,?,?,?,?,?,?,?)', ('contest', str(contest_id), None, None, None, 0, now(), 'skipped_budget', f'estimated {est}, used {used}, budget {budget_records}'))
            db.commit()
            continue
        try:
            data, path, _ = client.get(f'contests/{contest_id}/download', {'format': 'json'}, 'contests')
        except ApiError as error:
            db.execute('insert or replace into fetch_log values(?,?,?,?,?,?,?,?,?)', ('contest', str(contest_id), None, None, None, 0, now(), 'error', str(error)[:300]))
            db.commit()
            continue
        cost = int(client.quota.get('used') or 0) - used
        entries = len(data.get('lineups', []))
        total = (data.get('contest') or {}).get('total_entries')
        status = 'ok' if total is not None and entries == total else 'ok_partial'
        db.execute('insert or replace into fetch_log values(?,?,?,?,?,?,?,?,?)', ('contest', str(contest_id), path.name.split('.')[0], str(path), path.stat().st_size, cost, now(), status, f'entries {entries} of {total}'))
        db.commit()
        n += 1
        print(f'contest {contest_id}: {entries}/{total} lineups, cost {cost}, quota used {client.quota.get("used")}', flush=True)
    print(f'downloaded this run: {n}; quota used {client.quota.get("used")} (this run {int(client.quota.get("used") or 0) - spent_before})', flush=True)


if __name__ == '__main__':
    root, step = sys.argv[1], sys.argv[2]
    db = db_open(root)
    if step == 'plan':
        plan(db)
    else:
        client = Client(root)
        # learn the current quota without spending anything
        client.get('slates/seasons', {'sport': 'nfl'}, 'misc')
        if step == 'projections':
            projections(client, db, float(sys.argv[3]) if len(sys.argv) > 3 else 240)
        elif step == 'download':
            download(client, db, float(sys.argv[3]) if len(sys.argv) > 3 else 240, int(sys.argv[4]) if len(sys.argv) > 4 else 9_600_000)
