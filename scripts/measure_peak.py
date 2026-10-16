#!/usr/bin/env python3
"""Run a Python script IN THIS PROCESS and report the operating system's peak working set and wall time (Windows; standard library only).

    python scripts/measure_peak.py scripts/trend_research.py --root <FantasyPoints> run P5-2

In-process on purpose: the venv python.exe on Windows is a launcher that starts the real interpreter as a child, so measuring the launcher would report about 4 MB.
Use it to find which command is actually memory-heavy before changing anything. The script's own stdout is suppressed; the exit status is reported.
"""
import contextlib
import io
import json
import runpy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_capture import MB, counters  # noqa: E402


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    script, args = Path(sys.argv[1]).resolve(), sys.argv[2:]
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script)] + args
    before = counters()
    started = time.perf_counter()
    status = 0
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(script), run_name='__main__')
    except SystemExit as exc:
        status = exc.code or 0
    c = counters()
    print(json.dumps({'script': script.name, 'args': ' '.join(args)[:120], 'exit': status, 'seconds': round(time.perf_counter() - started, 1),
                      'start_working_set_mb': round(before.WorkingSetSize / MB), 'peak_working_set_mb': round(c.PeakWorkingSetSize / MB), 'peak_pagefile_mb': round(c.PeakPagefileUsage / MB)}))


if __name__ == '__main__':
    main()
