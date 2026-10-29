"""OpenTimestamps submission without the `ots` CLI (which needs libcrypto on Windows).

Submits only the SHA-256 digest (plus a random nonce, as the official client does) to public calendar servers and writes a standard
`<file>.ots` proof. The proof is 'pending' until a Bitcoin block commits it; run `ots upgrade`/`ots verify` on a machine where the CLI works,
or any OpenTimestamps verifier, to complete and check it.
"""
import hashlib
import os
import sys
from pathlib import Path
from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.serialize import StreamSerializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

CALENDARS = ['https://alice.btc.calendar.opentimestamps.org', 'https://bob.btc.calendar.opentimestamps.org',
             'https://finney.calendar.eternitywall.com']


def stamp(path):
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).digest()
    file_ts = Timestamp(digest)
    nonce_ts = file_ts.ops.add(OpAppend(os.urandom(16)))
    merkle = nonce_ts.ops.add(OpSHA256())
    ok = []
    for url in CALENDARS:
        try:
            merkle.merge(RemoteCalendar(url).submit(merkle.msg, timeout=20))
            ok.append(url)
        except Exception as e:
            print('calendar failed', url, type(e).__name__, str(e)[:80])
    assert ok, 'no calendar accepted the digest; the file is NOT timestamped'
    detached = DetachedTimestampFile(OpSHA256(), file_ts)
    out = path.with_name(path.name + '.ots')
    with out.open('wb') as f:
        detached.serialize(StreamSerializationContext(f))
    return out, ok, digest.hex()


if __name__ == '__main__':
    out, ok, d = stamp(sys.argv[1])
    print('proof', out, 'sha256', d, 'accepted by', ok)
