"""Phase 9: publish the sanitised GOING feed (separate from the scheduler; never blocks forecasting).

Mechanism: the validated feed is written locally, then (only with --push) committed to a dedicated branch
`nfl-lab-feed` of the repository's `origin` using git plumbing (hash-object / mktree / commit-tree / push). The
working checkout, its index and its branches are never touched. GOING's /api/nfl-lab reads the latest commit of that
branch from GitHub, so the website works while this PC is off and shows the feed's age.

  python -m lab.publish_going            # build + validate + write locally (dry run, nothing leaves the PC)
  python -m lab.publish_going --push     # also publish to origin/nfl-lab-feed (uses your existing git credentials)
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import LAB_ROOT

PUB_DIR = LAB_ROOT / "publish"
FEED_FILE = PUB_DIR / "nfl_lab_feed.json"
HISTORY = PUB_DIR / "history.jsonl"
BRANCH = "nfl-lab-feed"
REMOTE_PATH = "nfl_lab_feed.json"
GIT_ROOT = LAB_ROOT.parents[1]
VERCEL_CONFIG = '{"git": {"deploymentEnabled": false}, "ignoreCommand": "exit 0"}\n'


def _log(entry: dict) -> dict:
    PUB_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")} | entry
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _git(*args, cwd=GIT_ROOT, input_=None, env=None) -> str:
    # binary pipes: on Windows a text-mode stdin turns LF into CRLF, which would corrupt mktree file names
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, input=input_.encode("utf-8") if input_ else None,
                       env=env, timeout=120)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return r.stdout.decode("utf-8", "replace").strip()


def push_feed(path: Path, remote: str = "origin", branch: str = BRANCH, repo=GIT_ROOT) -> str:
    """Commit `path` (plus a deploy guard) on `branch` (parent = current remote tip, if any) and push it. Returns the commit."""
    blob = _git("hash-object", "-w", str(path), cwd=repo)
    # Vercel builds every pushed branch and reads vercel.json from the deployed commit itself, so a data-only feed
    # commit must disable deployment for this branch; otherwise each publication creates a failed Preview deployment.
    cfg = _git("hash-object", "-w", "--stdin", cwd=repo, input_=VERCEL_CONFIG)
    tree = _git("mktree", cwd=repo, input_=f"100644 blob {blob}\t{REMOTE_PATH}\n100644 blob {cfg}\tvercel.json\n")
    parent = None
    try:
        _git("fetch", "--quiet", remote, f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}", cwd=repo)
        parent = _git("rev-parse", f"refs/remotes/{remote}/{branch}", cwd=repo)
    except RuntimeError:
        parent = None                                      # first publication: the branch does not exist yet
    if parent and _git("rev-parse", f"{parent}^{{tree}}", cwd=repo) == tree:
        return parent                                      # identical content already published
    msg = f"nfl-lab feed {json.loads(path.read_text())['generated_at']}"
    commit = _git("commit-tree", tree, *(["-p", parent] if parent else []), "-m", msg, cwd=repo)
    _git("push", "--quiet", remote, f"{commit}:refs/heads/{branch}", cwd=repo)
    return commit


def publish(push: bool = False, now=None) -> dict:
    """Build, validate, write; optionally push. Never raises: every outcome is logged for the health panel."""
    from .going_feed import build, validate
    try:
        feed = build(now)
        errs = validate(feed)
        if errs:
            return _log({"ok": False, "stage": "validate", "errors": errs[:10]})
        from .cache73 import _atomic_write_bytes
        _atomic_write_bytes(FEED_FILE, json.dumps(feed, separators=(",", ":")).encode("utf-8"))
        entry = {"ok": True, "stage": "written", "games": len(feed["games"]), "generated_at": feed["generated_at"],
                 "latest_forecast": (feed.get("freshness") or {}).get("latest_forecast_archived_at"), "pushed": False}
        if push:
            try:
                entry |= {"pushed": True, "commit": push_feed(FEED_FILE)[:10], "branch": BRANCH}
            except Exception as exc:
                entry |= {"ok": False, "stage": "push", "error": repr(exc)[:300]}
        return _log(entry)
    except Exception as exc:
        return _log({"ok": False, "stage": "build", "error": repr(exc)[:300]})


def health() -> dict:
    rows = [json.loads(x) for x in HISTORY.read_text(encoding="utf-8").splitlines() if x.strip()] if HISTORY.exists() else []
    last_ok_push = next((r for r in reversed(rows) if r.get("ok") and r.get("pushed")), None)
    last_write = next((r for r in reversed(rows) if r.get("ok")), None)
    return {"attempts": len(rows), "last_attempt": rows[-1] if rows else None, "last_local_write": last_write,
            "last_published": last_ok_push, "automatic": False,
            "note": "Publication runs only when started (publish_going.bat or a separate scheduled task); it is not part of the "
                    "forecast scheduler, so it can never delay or block a forecast."}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--push", action="store_true", help="publish to origin/nfl-lab-feed")
    a = ap.parse_args(argv)
    r = publish(push=a.push)
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
