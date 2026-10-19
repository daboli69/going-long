"""Archive local GOING market/prop snapshots; no network or credentials.

python -m lab.phase10_archive [--history]
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

from .archive10 import going_versions, going_remote_main
from .config import REPORTS_DIR
from .market81 import archive_local_markets
from .props.lines import archive_lines, archived_lines, player_map


def run(history=False, remote_main=False):
    mapping = player_map()
    result = {"versions": 0, "market_files_new": 0, "props_files_new": 0, "errors": []}
    versions = [going_remote_main()] if remote_main else going_versions(history=history)
    for data, meta in versions:
        result["versions"] += 1
        for name, fn in (("market", lambda: archive_local_markets(data, meta)),
                         ("props", lambda: archive_lines(data, meta, mapping))):
            try:
                row = fn()
                result[name + "_files_new"] += int(row["new"])
            except Exception as exc:
                result["errors"].append({"kind": name, "commit": meta.get("commit"), "error": str(exc)})
    lines = archived_lines()
    if len(lines):
        verified = lines[lines["pregame_verified"]]
        result |= {"prop_markets": sorted(lines["stat"].unique()),
                   "unmatched_players": sorted(lines.loc[lines["gsis_id"].isna(), "player"].dropna().unique()),
                   "rows_archived": len(lines), "pregame_verified_rows": len(verified),
                   "earliest_usable_quote": verified["quote_time"].min() if len(verified) else None,
                   "latest_usable_quote": verified["quote_time"].max() if len(verified) else None}
    directory = REPORTS_DIR / "run_20261019"
    directory.mkdir(parents=True, exist_ok=True)
    name = "archive_status_remote_main.json" if remote_main else "archive_status.json"
    (directory / name).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--remote-main", action="store_true", help="Read latest fetched origin/main copy without switching branches")
    args = parser.parse_args()
    print(json.dumps(run(args.history, args.remote_main), indent=2, default=str))
