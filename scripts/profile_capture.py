#!/usr/bin/env python3
"""Peak-memory and runtime profile of the real `fp_shadow.py capture` command, by stage (Windows; standard library only).

    python scripts/profile_capture.py --root <FantasyPoints> [--market-from-url main] [--out report.json]

A background thread samples the process working set every 10 ms; each stage reports the peak working set reached while it ran, the working set when it ended and
its wall time. The final line is the operating system's own PeakWorkingSetSize for the whole process. Runs the capture with --dry-run semantics (writes nothing).
Stages are found by wrapping existing functions, so the same script measures the code before and after an optimisation.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import importlib
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


class COUNTERS(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]


_k = ctypes.WinDLL('kernel32', use_last_error=True)
_k.GetCurrentProcess.restype = wt.HANDLE
_k.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(COUNTERS), wt.DWORD]
_k.K32GetProcessMemoryInfo.restype = wt.BOOL


def counters(handle=None):
    c = COUNTERS()
    c.cb = ctypes.sizeof(c)
    if not _k.K32GetProcessMemoryInfo(handle or _k.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise OSError(ctypes.get_last_error(), 'GetProcessMemoryInfo failed')
    return c


MB = 1024 * 1024
stages, current, lock = [], {'peak': 0}, threading.Lock()
stop = threading.Event()


def sampler():
    while not stop.is_set():
        ws = counters().WorkingSetSize
        with lock:
            if ws > current['peak']:
                current['peak'] = ws
        time.sleep(0.01)


def wrap(module, name, label):
    original = getattr(module, name, None)
    if original is None:
        return

    def run(*a, **k):
        with lock:
            outer = current['peak']
            current['peak'] = counters().WorkingSetSize
        started, before = time.perf_counter(), counters().WorkingSetSize
        try:
            return original(*a, **k)
        finally:
            seconds, after = time.perf_counter() - started, counters().WorkingSetSize
            with lock:
                stages.append({'stage': label, 'start_mb': round(before / MB), 'peak_mb': round(max(current['peak'], after) / MB), 'end_mb': round(after / MB), 'seconds': round(seconds, 2)})
                current['peak'] = max(outer, current['peak'])
    setattr(module, name, run)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--market-from-url', default='main')
    p.add_argument('--max-market-age-hours', type=float, default=6)
    p.add_argument('--out', type=Path, help='write the JSON report here')
    p.add_argument('--capture-out', type=Path, help='capture directory (default: the private one); a dry run writes only the input cache there')
    p.add_argument('--rebuild-inputs', action='store_true')
    p.add_argument('--cold-start', action='store_true', help='name only; use a fresh --capture-out to force a cold cache')
    a = p.parse_args()
    threading.Thread(target=sampler, daemon=True).start()
    t0, ws0 = time.perf_counter(), counters().WorkingSetSize
    imports = {}
    for name in ('numpy', 'pandas', 'scipy.stats', 'trend_research.champion', 'trend_research.weekly', 'trend_research.experiments14', 'fp_shadow'):
        before = counters().WorkingSetSize
        started = time.perf_counter()
        importlib.import_module(name)
        imports[name] = {'seconds': round(time.perf_counter() - started, 2), 'delta_mb': round((counters().WorkingSetSize - before) / MB)}
    fp = sys.modules['fp_shadow']
    champion, weekly, e14 = sys.modules['trend_research.champion'], sys.modules['trend_research.weekly'], sys.modules['trend_research.experiments14']
    for module, name, label in ((fp, 'board_from_url', 'board fetch'), (fp, 'load_inputs', 'load_inputs (total)'), (champion, 'load_games', '  load games.csv'),
                                (champion, 'load_weekly', '  load nflverse weekly stats'), (weekly, 'load_table', '  load FP run/pass table'),
                                (e14, 'team_games', '  team_games (merge + lag)'), (e14, 'game_features', '  game_features'), (e14, '_fit_totals', '  fit dev models'),
                                (fp, 'plan_captures', 'plan_captures'), (fp, 'prepare_inputs', 'prepare_inputs (cache aware)'), (fp, 'build_inputs', '  build_inputs (cache miss)'),
                                (fp, 'precheck', 'precheck (board, games, captures)')):
        wrap(module, name, label)
    argv = ['fp_shadow.py', 'capture', '--root', str(a.root), '--dry-run', '--market-from-url', a.market_from_url, '--max-market-age-hours', str(a.max_market_age_hours)]
    if a.capture_out:
        argv += ['--out', str(a.capture_out)]
    if a.rebuild_inputs:
        argv += ['--rebuild-inputs']
    sys.argv = argv
    started = time.perf_counter()
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()) as out:
        fp.main()
    elapsed = time.perf_counter() - started
    stop.set()
    c = counters()
    report = {'imports': imports, 'stages': stages, 'capture_seconds': round(elapsed, 2), 'process_seconds': round(time.perf_counter() - t0, 2),
              'start_working_set_mb': round(ws0 / MB), 'peak_working_set_mb': round(c.PeakWorkingSetSize / MB), 'peak_pagefile_mb': round(c.PeakPagefileUsage / MB),
              'capture_counts': json.loads(out.getvalue()).get('counts')}
    text = json.dumps(report, indent=1)
    if a.out:
        a.out.write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
