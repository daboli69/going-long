r"""Tracker commands: select (record pre-kickoff evaluations), settle (record finals), report, verify.

    .venv\Scripts\python.exe scripts/track.py select --origin backfill   # first run only
    .venv\Scripts\python.exe scripts/track.py select
    .venv\Scripts\python.exe scripts/track.py settle
    .venv\Scripts\python.exe scripts/track.py report
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import tracker  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["select", "settle", "report", "verify"])
    ap.add_argument("--origin", default="live", choices=["live", "backfill"])
    a = ap.parse_args()
    if a.cmd == "select":
        print(f"recorded {len(tracker.select(a.origin))} new evaluations (rule {tracker.RULE_ID})")
    elif a.cmd == "settle":
        print(f"settled {len(tracker.settle())} rows")
    elif a.cmd == "verify":
        p = tracker.verify()
        print("\n".join(p) if p else "record intact")
        return 1 if any("chain" in x or "duplicate" in x or "orphan" in x or "before kickoff" in x for x in p) else 0
    else:
        r = tracker.performance()
        r.pop("cumulative")
        print(json.dumps(r, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
