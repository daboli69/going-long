"""Archive every committed version of GOING data/nfl_betting.json that the lab does not yet hold (read-only git, no network). python scripts/going_harvest.py"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab.archive10 import going_versions  # noqa: E402
from lab.market81 import archive_local_markets  # noqa: E402
from lab.props.lines import archive_lines, player_map  # noqa: E402

if __name__ == "__main__":
    have = {json.load(open(f)).get("commit") for f in glob.glob(str(ROOT / "data" / "raw" / "archive" / "props" / "going_*.json"))}
    mapping = player_map()
    n = new_p = new_m = 0
    for data, meta in going_versions(history=True):
        n += 1
        if meta.get("commit") in have:
            continue
        new_m += int(archive_local_markets(data, meta)["new"])
        new_p += int(archive_lines(data, meta, mapping)["new"])
        print(meta.get("commit"), meta.get("available_at"), flush=True)
    print({"versions": n, "already_held": len(have), "new_market_files": new_m, "new_props_files": new_p})
