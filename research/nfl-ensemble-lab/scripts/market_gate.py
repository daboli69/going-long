r"""Recompute the market gate (champion vs closing consensus, paired bootstrap, per hold era).

    .venv\Scripts\python.exe scripts/market_gate.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import market_gate  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(market_gate.run(), indent=1))
