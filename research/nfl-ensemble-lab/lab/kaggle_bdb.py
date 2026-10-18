r"""Optional: NFL Big Data Bowl competition files (Kaggle) into data/raw/kaggle/<handle>/ (gitignored).

Prerequisites, done by Travis, never by the lab:
  1. sign in at kaggle.com and accept the rules of EACH competition at https://www.kaggle.com/competitions/<handle>/rules
  2. create an API token (Settings -> API) and save it as %USERPROFILE%\.kaggle\kaggle.json (or set KAGGLE_USERNAME / KAGGLE_KEY)
Competition data stays local: the rules restrict use and forbid redistribution, so nothing here is ever published or committed.
Run: python -m lab.kaggle_bdb            (all three)   or   python -m lab.kaggle_bdb nfl-big-data-bowl-2025
"""
from __future__ import annotations

import hashlib
import json

import pandas as pd

from .config import RAW_DIR

HANDLES = ("nfl-big-data-bowl-2025", "nfl-big-data-bowl-2026-prediction", "nfl-big-data-bowl-2026-analytics")
ROOT = RAW_DIR / "kaggle"


def download(handle: str) -> dict:
    import kagglehub
    OUT = ROOT / handle
    OUT.mkdir(parents=True, exist_ok=True)
    path = kagglehub.competition_download(handle, output_dir=str(OUT))
    files = []
    for f in sorted(OUT.rglob("*")):
        if f.is_file() and f.name != "provenance.json":
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            files.append({"file": str(f.relative_to(OUT)), "bytes": f.stat().st_size, "sha256": h.hexdigest()})
    prov = {"source": f"https://www.kaggle.com/competitions/{handle}/data", "downloaded_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "kagglehub_path": path, "files": files, "terms": "Kaggle competition rules: local research use only, no redistribution"}
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2))
    return prov


if __name__ == "__main__":
    import sys
    for h in sys.argv[1:] or HANDLES:
        try:
            p = download(h)
            print(f"{h}: {len(p['files'])} files, {sum(f['bytes'] for f in p['files']) / 1e9:.2f} GB -> {ROOT / h}")
        except Exception as e:  # usually: rules not accepted or no API token
            print(f"{h}: FAILED - {e}")
