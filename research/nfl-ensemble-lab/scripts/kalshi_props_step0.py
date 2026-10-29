"""Step 0 of docs/PROPS_KALSHI_PREREGISTRATION.md (860324b6): liquidity of Kalshi NFL player markets at kickoff - 90 min.

Read-only public data. Writes reports/kalshi/props_step0.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import homewin_deep as h  # noqa: E402
from lab import kalshi as k  # noqa: E402
from lab.config import CACHE_DIR, LAB_ROOT  # noqa: E402

SERIES = ["KXNFLRECYDS", "KXNFLREC", "KXNFLRSHYDS", "KXNFLPASSYDS", "KXNFLANYTD", "KXNFLPASSTDS", "KXNFLTOTAL", "KXNFLSPREAD"]
LADDERS = {"KXNFLRECYDS", "KXNFLREC", "KXNFLRSHYDS", "KXNFLPASSYDS"}
PER_SERIES, SEED = 400, 0
LEAD = pd.Timedelta(minutes=90)


def wilson(x, n, z=1.96):
    if n == 0:
        return [None, None]
    p = x / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    w = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [float(c - w), float(c + w)]


def at_point(market, P):
    base = f"/historical/markets/{market.ticker}" if market.historical else f"/series/{market.series}/markets/{market.ticker}"
    d = k._get(f"{base}/candlesticks?start_ts={int((P - pd.Timedelta(hours=48)).timestamp())}&end_ts={int(P.timestamp())}&period_interval=60")
    cs = [c for c in d.get("candlesticks", []) if c["end_period_ts"] <= P.timestamp()]
    if not cs:
        return None

    def cl(b):
        b = b or {}
        return k._f(b.get("close_dollars", b.get("close")))
    last = cs[-1]
    vol = sum(k._f(c.get("volume_fp", c.get("volume"))) or 0 for c in cs[-24:])
    return {"bid": cl(last.get("yes_bid")), "ask": cl(last.get("yes_ask")), "vol24": float(vol),
            "age_h": float((P.timestamp() - last["end_period_ts"]) / 3600)}


def main():
    inv = pd.read_parquet(CACHE_DIR / "kalshi" / "player_inventory.parquet")
    games, _ = h.load_games()
    gm = k.match_games(k.game_markets(), games)
    code = {e.split("-", 1)[1]: (gid, ko) for e, gid, ko in zip(gm["event"], gm["gid"], gm["kickoff_utc"])}
    inv = inv[inv["series"].isin(SERIES)].copy()
    inv["code"] = inv["event"].str.split("-", n=1).str[1]
    inv = inv[inv["code"].isin(code)]
    inv["gid"] = inv["code"].map(lambda c: code[c][0])
    inv["kickoff"] = inv["code"].map(lambda c: code[c][1])
    res = {"prereg_commit": "860324b6", "filter": {"bid_min": 0.02, "ask_max": 0.98, "spread_max": 0.05, "vol24_min": 500,
                                                    "ladder_min_liquid_thresholds": 3}, "series": {}}
    rng = np.random.default_rng(SEED)
    for s, g in inv.groupby("series"):
        take = g.iloc[rng.permutation(len(g))[:PER_SERIES]]
        rows = []
        for m in take.itertuples(index=False):
            r = at_point(m, m.kickoff - LEAD)
            rows.append({"ticker": m.ticker, "gid": m.gid, "event": m.event, **(r or {"bid": np.nan, "ask": np.nan, "vol24": 0.0, "age_h": np.nan})})
        x = pd.DataFrame(rows)
        x["spread"] = x["ask"] - x["bid"]
        x["liquid"] = (x["bid"] >= 0.02) & (x["ask"] <= 0.98) & (x["spread"] <= 0.05) & (x["vol24"] >= 500)
        n, liq = len(x), int(x["liquid"].sum())
        share = liq / n if n else 0.0
        per_event_markets = g.groupby("event").size().median()
        q = lambda c: {f"p{int(p*100)}": float(x[c].quantile(p)) for p in (0.1, 0.25, 0.5, 0.75, 0.9)}  # noqa: E731
        rule = {}
        try:
            one = take.iloc[0]
            det = k._get(("/historical/markets/" if one.historical else "/markets/") + one.ticker)["market"]
            rule = {"rules_primary": det.get("rules_primary"), "rules_secondary": det.get("rules_secondary")}
        except Exception as exc:
            rule = {"error": str(exc)[:100]}
        res["series"][s] = {"games_in_inventory": int(g["gid"].nunique()), "seasons": sorted({int(i[:4]) for i in g["gid"]}),
                            "markets_in_inventory": int(len(g)), "sampled": n, "no_candle_before_P": int(x["bid"].isna().sum()),
                            "liquid": liq, "liquid_share": share, "liquid_share_wilson95": wilson(liq, n),
                            "spread_quantiles": q("spread"), "vol24_quantiles": q("vol24"),
                            "markets_per_game_median": float(per_event_markets),
                            "est_liquid_markets_per_game": float(share * per_event_markets), **rule}
        print(f"{s:<14} games {res['series'][s]['games_in_inventory']:>4} sampled {n:>3} liquid {liq:>3} ({share:.0%} "
              f"[{wilson(liq, n)[0]:.0%},{wilson(liq, n)[1]:.0%}]) spread p50 {x['spread'].median():.3f} vol24 p50 {x['vol24'].median():.0f} "
              f"est liquid/game {share * per_event_markets:.1f}", flush=True)
    lad = {s: v for s, v in res["series"].items() if s in LADDERS}
    # a ladder needs >= 3 liquid thresholds; approximate liquid ladders per game from liquid markets per game / ~3
    thin = all(v["liquid_share"] < 0.25 for v in lad.values()) or all(v["est_liquid_markets_per_game"] / 3 < 2 for v in lad.values())
    res["thin_rule_triggered"] = bool(thin)
    out = LAB_ROOT / "reports" / "kalshi"
    out.mkdir(parents=True, exist_ok=True)
    body = json.dumps(res, indent=1, default=str)
    (out / "props_step0.json").write_bytes(body.encode("utf-8"))
    print(f"thin rule triggered: {thin}; sha256 {hashlib.sha256(body.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
