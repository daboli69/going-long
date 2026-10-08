"""Research ledger with pre-registration: a spec is hashed and stored BEFORE the experiment runs; the run refuses to execute a spec that
differs from what was registered, so a hypothesis cannot be quietly adjusted after the result is known."""
import datetime
import hashlib
import json
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parents[2] / 'research' / 'trend-intelligence' / 'ledger.json'


def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def load(path=LEDGER_PATH):
    if Path(path).exists():
        return json.loads(Path(path).read_text(encoding='utf-8'))
    return {'version': 1, 'note': 'Aggregate research results only (no licensed player-level values). Negative findings are kept on purpose.', 'experiments': {}}


def save(ledger, path=LEDGER_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(ledger, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')


def register(ledger, spec, now=None):
    """Store the pre-registration. Re-registering an identical spec is a no-op; a changed spec for the same id is refused."""
    exp_id, digest = spec['id'], spec_hash(spec)
    existing = ledger['experiments'].get(exp_id)
    if existing:
        if existing['spec_sha256'] != digest:
            raise ValueError(f'{exp_id}: the spec differs from its pre-registration; register a new experiment id instead')
        return existing
    ledger['experiments'][exp_id] = {'spec': spec, 'spec_sha256': digest, 'registered_at': (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                     'status': 'REGISTERED', 'result': None}
    return ledger['experiments'][exp_id]


def record(ledger, exp_id, spec, result, status, now=None):
    entry = ledger['experiments'].get(exp_id)
    if not entry or entry['spec_sha256'] != spec_hash(spec):
        raise ValueError(f'{exp_id}: refusing to record a result for a spec that was not pre-registered unchanged')
    entry['status'] = status
    entry['result'] = result
    entry['completed_at'] = (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return entry
