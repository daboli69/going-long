from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

from ..config import LAB_ROOT, RAW_DIR, CACHE_DIR
from ..fpds_ingest import write_once, sha

ROOT = CACHE_DIR / 'fpds' / 'amendment6'
RAW = RAW_DIR / 'fpds' / 'amendment6'
SOURCE = LAB_ROOT.parents[1] / 'FantasyPoints' / 'Inbox'
REPORT = LAB_ROOT / 'reports' / 'run_20261020'
VERSION = 2
SEED = 20261020
STATS = ('rec', 'rec_yds', 'rush_yds', 'anytime_td', 'pass_yds', 'pass_tds')


def now():
    return datetime.now(timezone.utc).isoformat()


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic(path, value):
    """Mutable job pointers/status only; raw versions and forecasts use write_once."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')
    os.replace(tmp, path)


def registered():
    rel = subprocess.check_output(['git', 'ls-files', '--full-name', 'docs/PHASE10_PREREGISTRATION.md'], cwd=LAB_ROOT, text=True).strip()
    committed = subprocess.check_output(['git', 'show', 'HEAD:' + rel], cwd=LAB_ROOT, text=True, encoding='utf-8')
    current = (LAB_ROOT / 'docs/PHASE10_PREREGISTRATION.md').read_text(encoding='utf-8')
    if '## Amendment 6' not in committed or committed != current:
        raise ValueError('Commit Amendment 6 unchanged before fitting')
    protocol = LAB_ROOT / 'docs' / 'FPDS_AMENDMENT6_TRIALS.json'
    rel = subprocess.check_output(['git', 'ls-files', '--full-name', str(protocol)], cwd=LAB_ROOT, text=True).strip()
    frozen = subprocess.check_output(['git', 'show', 'HEAD:' + rel], cwd=LAB_ROOT)
    if frozen.decode('utf-8').replace('\r\n','\n') != protocol.read_text(encoding='utf-8'):
        raise ValueError('Trial manifest must match committed version')
    return digest({'preregistration': committed, 'trials': read(protocol)})


def private_error(label):
    import traceback
    path = ROOT / 'errors' / f'{stamp()}_{label}.txt'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(traceback.format_exc(), encoding='utf-8')
    return str(path)
