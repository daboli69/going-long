"""Gate recent-player-file reads on a committed Amendment 1 frozen configuration."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess

from ...config import LAB_ROOT

START, END = "<!-- PHASE10_FROZEN_CONFIG_START -->", "<!-- PHASE10_FROZEN_CONFIG_END -->"


def load():
    path = LAB_ROOT / "docs" / "PHASE10_PREREGISTRATION.md"
    if not path.exists():
        raise ValueError("Recent props data is blocked until Amendment 1/FROZEN CONFIG is committed")
    current = path.read_text(encoding="utf-8")
    tracked = subprocess.run(["git", "ls-files", "--full-name", "docs/PHASE10_PREREGISTRATION.md"], cwd=LAB_ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    committed = subprocess.run(["git", "show", f"HEAD:{tracked}"], cwd=LAB_ROOT,
                               capture_output=True, text=True, encoding="utf-8", check=True).stdout
    def extract(text):
        if "Amendment 1" not in text or START not in text or END not in text:
            raise ValueError("Recent props data is blocked until Amendment 1/FROZEN CONFIG is committed")
        payload = text.split(START, 1)[1].split(END, 1)[0].strip()
        return json.loads(payload), payload
    config, payload = extract(current)
    frozen, frozen_payload = extract(committed)
    if config != frozen:
        raise ValueError("Frozen config differs from committed HEAD; commit before any recent-player-file read")
    from .spec import runtime_spec
    if config.get("runtime_spec") != runtime_spec():
        raise ValueError("Runtime model settings differ from the committed frozen configuration")
    return config | {"config_sha256": hashlib.sha256(frozen_payload.encode()).hexdigest()}
