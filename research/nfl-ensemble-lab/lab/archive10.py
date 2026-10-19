"""Small immutable JSON archives. Content hashes exclude retrieval metadata."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pandas as pd

from .config import RAW_DIR

ARCHIVE = RAW_DIR / "archive"


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False, default=str).encode("utf-8")


def save(kind: str, prefix: str, content, metadata: dict, *, root: Path = ARCHIVE,
         every_pull: bool = False) -> dict:
    """Exclusive creation; identical content is deduplicated unless every_pull=True.

    A hash names the exact normalized content; metadata records when/how it was seen.
    Existing archives are never edited, including under concurrent collectors.
    """
    directory = root / kind
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(canonical(content)).hexdigest()
    if not every_pull:
        existing = next(directory.glob(f"{prefix}_*_{digest}.json"), None)
        if existing:
            return {"new": False, "file": str(existing), "sha256": digest}
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{prefix}_{stamp}_{digest}.json"
    payload = metadata | {"archived_at": pd.Timestamp.now(tz="UTC").isoformat(),
                          "content_sha256": digest, "content": content}
    try:
        with path.open("xb") as fh:
            fh.write(canonical(payload))
        os.chmod(path, stat.S_IREAD)
    except FileExistsError:
        return {"new": False, "file": str(path), "sha256": digest}
    return {"new": True, "file": str(path), "sha256": digest}


def utc(value):
    if value is None or value == "":
        return None
    t = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(t) else t.isoformat()


def temporal(quote_time, available_at, kickoff) -> dict:
    """T1 needs both a source quote time AND observed file/commit time before kickoff.

    Unknown times stay unclassified; retrieval after kickoff never proves pregame
    availability, even when an embedded quote is backdated. T2/T3 are not inferred.
    """
    qt, av, ko = utc(quote_time), utc(available_at), utc(kickoff)
    valid = bool(qt and av and ko and pd.Timestamp(qt) <= pd.Timestamp(av) < pd.Timestamp(ko))
    return {"quote_time": qt, "available_at": av, "kickoff": ko,
            "timestamp_class": "T1" if valid else "unverified",
            "pregame_verified": valid}


def going_versions(*, history=True, root=None):
    """Read only the authorized JSON path and git blobs; never inspect credentials."""
    import subprocess
    from .market81 import GOING_ROOT
    root = Path(root or GOING_ROOT)
    path = root / "data" / "nfl_betting.json"
    if path.exists() and not history:
        yield json.loads(path.read_text(encoding="utf-8")), {
            "source": "GOING/data/nfl_betting.json", "commit": None,
            "available_at": pd.Timestamp.now(tz="UTC").isoformat()}
    if not history:
        return
    log = subprocess.run(["git", "-C", str(root), "log", "--all", "--format=%H %cI", "--", "data/nfl_betting.json"],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    for line in reversed(log):
        sha, when = line.split(maxsplit=1)
        blob = subprocess.run(["git", "-C", str(root), "show", f"{sha}:data/nfl_betting.json"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if blob.returncode:
            continue
        try:
            data = json.loads(blob.stdout)
        except json.JSONDecodeError:
            continue
        yield data, {"source": "GOING/data/nfl_betting.json git history", "commit": sha,
                     "available_at": utc(when)}
    if path.exists():
        yield json.loads(path.read_text(encoding="utf-8")), {
            "source": "GOING/data/nfl_betting.json", "commit": None,
            "available_at": pd.Timestamp.now(tz="UTC").isoformat()}
