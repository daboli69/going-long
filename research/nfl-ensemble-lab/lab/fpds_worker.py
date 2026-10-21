"""I/O-only adapter for transient Windows sharing locks on mutable pointers.

Study source/data/config fingerprints and all fitted calculations stay intact.
Failed configurations remain skipped; only already-computed JSON pointer writes
are retried. Never applies to immutable raw snapshots or forecast files.
"""
import os
from pathlib import Path
import time
import json


def retry_atomic(operation,path,value,*,sleep=time.sleep,retries=10,logpath=None):
    for attempt in range(retries):
        try:return operation(path,value)
        except PermissionError:
            if attempt+1==retries:raise
            if logpath is not None:
                from .fpds_research.common import now
                p=Path(logpath);p.parent.mkdir(parents=True,exist_ok=True)
                with p.open('a',encoding='utf-8') as f:
                    f.write(json.dumps({'created_at':now(),'target_name':Path(path).name,'attempt':attempt+1,'purpose':'mutable JSON pointer write only'})+'\n')
            sleep(min(.1*2**attempt,3.2))


def install():
    from .fpds_research import common as C
    if not getattr(C.atomic,'_fpds_io_retry',False):
        original=C.atomic
        log=C.ROOT/'operational_io'/f'retries_{os.getpid()}.jsonl'
        def adapter(path,value):return retry_atomic(original,path,value,logpath=log)
        adapter._fpds_io_retry=True
        C.atomic=adapter
    from .fpds_sources import install as source_policy
    source_policy()


def main():
    install()
    from .fpds_research.__main__ import main as cli
    return cli()


if __name__=='__main__':raise SystemExit(main())
