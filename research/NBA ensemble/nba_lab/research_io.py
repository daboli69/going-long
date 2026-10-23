"""Small local research I/O helpers; original frozen modules remain unchanged."""
import hashlib
import json
import time
from importlib.metadata import version
from .config import atomic,digest


def update(path,value):
    for attempt in range(5):
        try:return atomic(path,value)
        except PermissionError:
            if attempt==4:raise
            time.sleep(.1*(attempt+1))


def fingerprint(paths):
    payload={'files':{str(p):digest(p) for p in paths},
             'runtime':{k:version(k) for k in ('numpy','pandas','scikit-learn','xgboost')}}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
