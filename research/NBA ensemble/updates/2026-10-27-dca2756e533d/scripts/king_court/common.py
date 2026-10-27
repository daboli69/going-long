from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
EASTERN = ZoneInfo('America/New_York')
TEAMS = set('ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS'.split())
ALIASES = {'GS': 'GSW', 'SA': 'SAS', 'NY': 'NYK', 'NO': 'NOP', 'UTAH': 'UTA', 'WSH': 'WAS'}


def utc(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Explicit timezone required')
    return result.astimezone(timezone.utc)


def team(value):
    return ALIASES.get(str(value).upper(), str(value).upper())


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_new(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Validate before creating a receipt, so NaN cannot leave a partial artifact.
    payload = json.dumps(body, indent=2, allow_nan=False) + '\n'
    with path.open('x', encoding='utf-8') as out:
        out.write(payload)


def seal(body):
    return dict(body, sha256=digest(body))


def load_sealed(path):
    body = json.loads(Path(path).read_text())
    expected = body.pop('sha256')
    if digest(body) != expected:
        raise ValueError('Receipt content hash mismatch')
    return dict(body, sha256=expected)


def protocol():
    return json.loads((ROOT / 'config/king_court_protocol_v1.json').read_text())


def code_receipts():
    return {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}
