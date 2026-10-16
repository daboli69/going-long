#!/usr/bin/env python3
"""Offline, read-only memory profile of the local scanner's per-cycle loads.

    python scripts/profile_scanner_memory.py --db <topdown.sqlite> --data <scanner-data dir> STAGE [STAGE...]

Stages: rows_prediction rows_reference rows_settlement rows_notification
        history_json nfl_betting_json results_json ids_prediction_sql
        stream_untracked stream_used list_actionable (the post-fix code paths)
Each invocation is one stage in a fresh interpreter, so the OS peak is clean.
The database is opened mode=ro / query_only; nothing is written, no network is used,
and no scanner module is imported (the queries mirror topdown/journal.py).
Run it with the real interpreter (the venv python.exe is a launcher on Windows).
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

MB = 1 << 20


class PMC(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD)] + [(n, ctypes.c_size_t) for n in (
        'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
        'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]


def counters():
    c = PMC(); c.cb = ctypes.sizeof(c)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.GetCurrentProcess.restype = wt.HANDLE
    k.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
    k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c


def run_stage(stage, db_path, data):
    db = sqlite3.connect('file:' + str(db_path) + '?mode=ro', uri=True, timeout=5)
    db.execute('PRAGMA query_only=1')
    before = counters(); t = time.perf_counter(); n = None
    if stage.startswith('rows_'):
        kind = stage[5:]
        obj = [json.loads(r[0]) for r in db.execute('SELECT payload FROM journal WHERE kind=? ORDER BY observed_at', (kind,))]
        n = len(obj)
    elif stage in ('stream_untracked', 'stream_used', 'list_actionable'):
        where = {'stream_untracked': "COALESCE(json_extract(payload,'$.tracking_group'),'')=''",
                 'stream_used': "COALESCE(json_extract(payload,'$.actionable'),0)!=0 OR COALESCE(json_extract(payload,'$.tracking_group'),'')!=''",
                 'list_actionable': "COALESCE(json_extract(payload,'$.actionable'),0)!=0"}[stage]
        cur = db.execute("SELECT payload FROM journal WHERE kind='prediction' AND (" + where + ") ORDER BY observed_at")
        if stage == 'list_actionable':
            obj = [json.loads(r[0]) for r in cur]; n = len(obj)
        else:
            n = sum(1 for r in cur if json.loads(r[0]))  # streamed; nothing retained
            obj = None
    elif stage == 'ids_prediction_sql':
        obj = {r[0] for r in db.execute("SELECT id FROM journal WHERE kind='prediction' AND json_extract(payload,'$.tracking_group') IS NOT NULL")}
        n = len(obj)
    else:
        name = {'history_json': 'history.json', 'nfl_betting_json': 'nfl_betting.json', 'results_json': 'results.json'}[stage]
        obj = json.loads((Path(data) / 'data' / name).read_text())
    after = counters()
    print(json.dumps({'stage': stage, 'items': n, 'seconds': round(time.perf_counter() - t, 1),
                      'start_ws_mb': round(before.WorkingSetSize / MB), 'peak_ws_mb': round(after.PeakWorkingSetSize / MB),
                      'held_ws_mb': round(after.WorkingSetSize / MB)}))
    del obj


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--db', required=True); ap.add_argument('--data', required=True)
    ap.add_argument('--child', action='store_true'); ap.add_argument('stages', nargs='+')
    a = ap.parse_args()
    if a.child:
        run_stage(a.stages[0], a.db, a.data); return
    for s in a.stages:
        subprocess.run([sys.executable, __file__, '--child', '--db', a.db, '--data', a.data, s], check=True)


if __name__ == '__main__':
    main()
