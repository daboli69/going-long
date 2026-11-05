"""Read-only pull of Kalshi candlesticks and trade tape for spread and total ladders (Tails Amendment 2). Cached; safe to rerun.
python scripts/tails_ladder_fetch.py"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import props_kalshi as pk  # noqa: E402

SCOPE = ROOT / "data" / "cache" / "tails_ladder_scope.parquet"


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


if __name__ == "__main__":
    sc = pd.read_parquet(SCOPE)
    sc = sc[sc["status"] == "finalized"].sort_values("kickoff", ascending=False).reset_index(drop=True)
    log(f"{len(sc)} settled rungs")
    bad = 0
    for i, m in enumerate(sc.itertuples(index=False)):
        try:
            pk.candles(pd.Series(m._asdict()))
        except Exception as e:
            bad += 1
            log(f"candle error {m.ticker}: {str(e)[:80]}")
        if i % 500 == 0:
            log(f"candles {i}/{len(sc)} errors {bad}")
    log("candles done; choosing center rungs for the trade tape")
    rows = []
    for m in sc.itertuples(index=False):
        c = pk.candles(pd.Series(m._asdict()))
        q = pk.quote_at(c, m.kickoff - pd.Timedelta(hours=1))
        rows.append((m.ticker, m.gid, m.series, abs(q["mid"] - 0.5) if pd.notna(q["mid"]) else np.inf))
    d = pd.DataFrame(rows, columns=["ticker", "gid", "series", "dist"])
    keep = set(d.sort_values("dist").groupby(["gid", "series"]).head(6)["ticker"])
    center = sc[sc["ticker"].isin(keep)]
    log(f"{len(center)} center rungs for the trade tape")
    bad = 0
    for i, m in enumerate(center.itertuples(index=False)):
        try:
            pk.trades(pd.Series(m._asdict()), m.kickoff - pd.Timedelta(hours=1))
        except Exception as e:
            bad += 1
            log(f"trade error {m.ticker}: {str(e)[:80]}")
        if i % 300 == 0:
            log(f"trades {i}/{len(center)} errors {bad}")
    log("done")
