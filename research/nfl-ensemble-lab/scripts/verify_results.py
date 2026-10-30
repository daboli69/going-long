"""Mechanical checks behind docs/VERIFICATION.md. Read-only: git history and saved freezes only.

For each study: the protocol commit and code commit exist, and the protocol was committed before the code
that produced the results. Also re-hashes the saved forecast and props freezes. Exit code 1 if anything fails.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# (study, protocol commit, code commits)
STUDIES = [
    ("1 Deep home-win model", "741a13e7", ["555d5317"]),
    ("2 Home-win v2", "18e98172", ["7fa8c37b"]),
    ("3 Drive-level simulator", "067e5583", ["8e3cdb51"]),
    ("4 Kalshi props vs simulator", "31af0b08", ["60b72455"]),
    ("5 Market-anchored props", "7964284b", ["6ff6e5bc"]),
    ("6 Joint score model", "94e455cc", ["cc41214a"]),
    ("7 Market lag, availability, usage", "396af66a", ["5bb093a1", "d7c047c9"]),
]


def git(*args: str) -> int:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True).returncode


def check_studies() -> list[str]:
    bad = []
    for name, proto, codes in STUDIES:
        if git("cat-file", "-e", f"{proto}^{{commit}}"):
            bad.append(f"{name}: protocol commit {proto} not found")
            continue
        for code in codes:
            if git("cat-file", "-e", f"{code}^{{commit}}"):
                bad.append(f"{name}: code commit {code} not found")
            elif git("merge-base", "--is-ancestor", proto, code):
                bad.append(f"{name}: protocol {proto} is not an ancestor of code {code}")
    return bad


def check_freezes() -> list[str]:
    from lab.gamecenter_data import load_freezes

    bad = []
    for kind in ("forecast_games", "props_kalshi"):
        for (season, week), rec in load_freezes(kind).items():
            if not rec.get("hash_ok"):
                bad.append(f"{kind} {season} week {week}: saved hash does not match contents ({rec.get('file')})")
    return bad


def main() -> int:
    problems = check_studies() + check_freezes()
    for p in problems:
        print("FAIL", p)
    if not problems:
        print(f"OK: {len(STUDIES)} studies in protocol-before-code order; all saved freezes match their hashes.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
