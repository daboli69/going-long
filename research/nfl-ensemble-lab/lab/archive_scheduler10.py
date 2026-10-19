"""Post-forecast local archive hook. Never fetches an odds endpoint or git remote."""
from __future__ import annotations

import pandas as pd

from .archive10 import going_remote_main
from .market81 import archive_local_markets
from .props.lines import archive_lines


def collect_local():
    data, meta = going_remote_main()
    return {"ok": True, "market": archive_local_markets(data, meta), "props": archive_lines(data, meta),
            "generated_at": data.get("generated_at"), "note": "last fetched origin/main; no automatic git fetch"}


def collect_context(games):
    from .prospective import fetch_weather
    from .inactives10 import collect
    now = pd.Timestamp.now(tz="UTC")
    upcoming = games[(games["kickoff_utc"] > now) & (games["kickoff_utc"] <= now + pd.Timedelta(days=9))]
    result = {"weather": fetch_weather(upcoming)}
    try:
        result["inactives"] = collect(upcoming, now)
    except Exception as exc:
        result["inactives"] = {"ok": False, "reason": repr(exc)}
    return result
