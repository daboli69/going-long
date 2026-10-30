"""Prospective collection and weekly freeze for market-anchored props
(docs/PROPS_MARKET_ANCHORED_PREREGISTRATION.md, commits 7964284b and 4909f1ba). Manual commands; nothing is scheduled.

  python scripts/props_kalshi_collect.py snapshot [--max-markets N]   trades since last run, order books, inactives, injuries
  python scripts/props_kalshi_collect.py freeze [--dry]               next week's market-anchored prop distributions, sealed

Read-only public Kalshi data. No order, account or trading calls exist in this file or in lab.kalshi.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab import homewin_deep as h  # noqa: E402
from lab import homewin_eval as ev  # noqa: E402
from lab import kalshi as K  # noqa: E402
from lab import props_kalshi as pk  # noqa: E402
from lab.archive10 import save  # noqa: E402
from lab.config import RAW_DIR  # noqa: E402
from lab.ingest import normalize_team  # noqa: E402

PREREG = "4909f1ba"
STATE = pk.CACHE / "collect_state.json"
LEDGER = pk.REPORT.parent / "props_market" / "freeze_ledger.jsonl"
POINTS = {"T-3h": (150, 210), "T-90m": (75, 105), "T-30m": (15, 45)}
FEE_RATE = 0.07


def log(m):
    print(m, flush=True)


def point_label(minutes: float) -> str:
    return next((k for k, (a, b) in POINTS.items() if a <= minutes <= b), "unlabeled")


def snapshot(args):
    now = pd.Timestamp.now(tz="UTC")
    games, _ = h.load_games()
    up = games[~games["played"] & (games["kickoff_utc"] > now) & (games["kickoff_utc"] <= now + pd.Timedelta(days=4))]
    log(f"{len(up)} games kick off in the next 4 days")
    m = pk.live_markets(games, pk.PROP_SERIES)
    m = m[m["gid"].isin(up["gid"])].copy()
    m["minutes_to_kickoff"] = (m["kickoff"] - now).dt.total_seconds() / 60
    quoted = m["bid"].notna() & m["ask"].notna() & (m["bid"] >= 0.02) & (m["ask"] <= 0.98) & ((m["open_interest"] > 0) | (m["vol24"] > 0))
    active = m[(m["vol24"] > 0) | quoted].sort_values("vol24", ascending=False)
    if args.max_markets:
        active = active.head(args.max_markets)
    log(f"{len(m)} player-prop markets open; {len(active)} active (traded or quoted)")
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    books, trades, errors = [], [], 0
    for r in active.itertuples(index=False):
        try:
            ob = K._get(f"/markets/{r.ticker}/orderbook").get("orderbook_fp", {})
            books.append({"ticker": r.ticker, "gid": r.gid, "minutes_to_kickoff": round(r.minutes_to_kickoff, 1), "orderbook": ob})
            if r.vol24 > 0:
                since = int(state.get(r.ticker, (now - pd.Timedelta(days=4)).timestamp()))
                cur, got = "", []
                while True:
                    d = K._get(f"/markets/trades?ticker={r.ticker}&min_ts={since}&limit=1000" + (f"&cursor={cur}" if cur else ""))
                    got += d.get("trades", [])
                    cur = d.get("cursor")
                    if not cur or not d.get("trades"):
                        break
                if got:
                    trades.append({"ticker": r.ticker, "gid": r.gid, "trades": got})
                    state[r.ticker] = int(now.timestamp())
        except Exception as exc:  # one market failing must not stop the snapshot
            errors += 1
            if errors <= 3:
                log(f"  warning: {r.ticker}: {str(exc)[:80]}")
    labels = active.groupby("gid")["minutes_to_kickoff"].min().map(point_label).to_dict()
    meta = {"prereg": PREREG, "source": K.BASE, "retrieved_at": now.isoformat(), "timestamp_class": "T1 observed (lab retrieval time)",
            "point_labels_by_game": labels}
    b = save("props_kalshi_books", f"{now:%Y%m%d}", books, meta)
    t = save("props_kalshi_trades", f"{now:%Y%m%d}", trades, meta)
    STATE.write_text(json.dumps(state), encoding="utf-8")
    log(f"books: {len(books)} markets ({'new' if b['new'] else 'unchanged'}); trade prints: {sum(len(x['trades']) for x in trades)} in {len(trades)} markets; "
        f"errors {errors}; labels {pd.Series(labels).value_counts().to_dict()}")

    report = {"books": len(books), "trade_markets": len(trades), "errors": errors}
    try:
        from lab import inactives10
        r = inactives10.collect(games)
        report["inactives"] = {k: r.get(k) for k in ("ok", "games", "reason")} | {"failures": len(r.get("failures") or [])}
    except Exception as exc:
        report["inactives"] = f"not collected: {str(exc)[:100]}"
    try:
        from lab import availability
        availability.refresh_sources([h.v1.current_season()], h.v1.current_season(), progress=lambda m_: None, live_only=True)
        report["injuries"] = "live injury report, depth chart and ESPN feed refreshed (archived with retrieval time)"
    except Exception as exc:
        report["injuries"] = f"not collected: {str(exc)[:100]}"
    log(json.dumps(report))


def freeze(args):
    now = pd.Timestamp.now(tz="UTC")
    games, _ = h.load_games()
    up = games[~games["played"] & (games["kickoff_utc"] > now)].sort_values("kickoff_utc")
    if up.empty:
        log("no upcoming games")
        return
    season, week = int(up["season"].iloc[0]), int(up["week"].iloc[0])
    wk = up[(up["season"] == season) & (up["week"] == week)]
    log(f"freeze {season} week {week}: {len(wk)} games not yet kicked off")
    live = pk.live_markets(games)
    live = live[live["gid"].isin(wk["gid"])].copy()
    live["pid"] = np.nan
    lad = live["series"].isin(list(pk.LADDERS))
    live.loc[lad, "pid"] = pk.player_ids(live[lad], season).to_numpy()
    prices = K.live_prices(games).set_index("gid")["p_home"]
    envs, env_info = {}, {}
    for r in wk.itertuples(index=False):
        e = pk.game_environment(live[live["gid"] == r.gid], r.home, r.away, now, float(prices.get(r.gid, np.nan)), live=True)
        env_info[r.gid] = {k: (None if pd.isna(v) else float(v)) for k, v in e.items()}
        if not np.isnan(e["margin"]) and not np.isnan(e["total"]):
            envs[r.gid] = {"K": ((e["total"] + e["margin"]) / 2, (e["total"] - e["margin"]) / 2)}
    log(f"Kalshi environments for {len(envs)} of {len(wk)} games")

    from lab.props import weekly as W
    gcsv = W.load_games()
    wkc = gcsv[(gcsv["season"] == season) & (gcsv["week"] == week) & gcsv["game_id"].isin(envs)].sort_values("game_id")
    inj_f = RAW_DIR / f"injuries_{season}.parquet"
    inj = pd.read_parquet(inj_f) if inj_f.exists() else pd.DataFrame(columns=["team", "week", "gsis_id", "report_status"])
    inj = inj.assign(team=inj["team"].map(normalize_team))
    sim = pk.Replayer(season, gcsv).week(week, wkc, envs, inj, log=log)
    v2 = sim[sim["version"] == "v2"].set_index(["gid", "pid", "stat"])
    base = sim[sim["version"] == "base"].set_index(["gid", "pid", "stat"])

    import props_market_model as PM
    T0 = pd.read_parquet(pk.CACHE / "scored_thresholds.parquet")
    bstat = {st: PM.fit_b(g["p_market90"], g["p_K"], g["y_home_win"].to_numpy(float)) if len(g) >= PM.MIN_TRAIN else 0.0 for st, g in T0.groupby("stat")}
    out_ids = {}
    for t, d in inj[(inj["week"] == week)].groupby("team"):
        out_ids[t] = sorted(d.loc[d["report_status"].isin(["Out", "Doubtful"]), "gsis_id"].dropna().astype(str))
    ladders = []
    L = live[lad & live["pid"].notna()]
    for (gid, pid, stat), g in L.groupby(["gid", "pid", "stat"]):
        g = g.sort_values("strike")
        liquid = (g["bid"] >= 0.02) & (g["ask"] <= 0.98) & ((g["ask"] - g["bid"]) <= 0.05) & (g["vol24"] >= 500)
        if liquid.sum() < 3:
            continue
        ks = (np.floor(g["strike"].astype(float)) + 1).to_numpy()
        row = {"gid": gid, "pid": pid, "stat": stat, "player": g["player"].iloc[0], "team": g["team"].iloc[0], "b": bstat.get(stat, 0.0),
               "thresholds": [{"k": float(k), "bid": float(bi), "ask": float(a), "last": None if pd.isna(la) else float(la), "vol24": float(v),
                               "mid": float((bi + a) / 2) if pd.notna(bi) and pd.notna(a) and bi >= 0.02 and a <= 0.98 else None}
                              for k, bi, a, la, v in zip(ks, g["bid"], g["ask"], g["last"], g["vol24"])]}
        if (gid, pid, stat) in v2.index:
            q = v2.loc[(gid, pid, stat), pk.G.QCOLS if hasattr(pk, "G") else [f"q{i:02d}" for i in range(1, 100)]].to_numpy(float)
            for th in row["thresholds"]:
                ps = pk.p_at_least(q, th["k"])
                th["p_sim"] = ps
                if th["mid"] is not None:
                    th["p_corr"] = float(PM.sig(PM.lg(th["mid"]) + row["b"] * (PM.lg(ps) - PM.lg(th["mid"]))))
        if (gid, pid, stat) in base.index:
            qb = base.loc[(gid, pid, stat), [f"q{i:02d}" for i in range(1, 100)]].to_numpy(float)
            for th in row["thresholds"]:
                th["p_base"] = pk.p_at_least(qb, th["k"])
        ladders.append(row)
    content = {"season": season, "week": week, "environments": env_info, "b_by_stat": bstat, "ladders": ladders,
               "availability_out_or_doubtful": out_ids, "fee": {"type": "quadratic", "formula": f"{FEE_RATE} * price * (1 - price) per contract, taker"}}
    log(f"{len(ladders)} liquid ladders; b by stat {({k: round(v, 3) for k, v in bstat.items()})}")
    if args.dry:
        log("dry run: not archived")
        return
    meta = {"prereg": PREREG, "code_commit": ev._git_sha(), "frozen_at": now.isoformat(), "timestamp_class": "T1 observed (lab retrieval time)",
            "first_kickoff_utc": wk["kickoff_utc"].min().isoformat()}
    saved = save("props_kalshi", f"{season}_w{week:02d}", content, meta)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if saved["new"]:
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"season": season, "week": week, "games": len(envs), "ladders": len(ladders), "frozen_at": now.isoformat(),
                                 "sha256": saved["sha256"]}) + "\n")
    log(f"Froze {len(ladders)} ladders in {len(envs)} games: sha256 {saved['sha256']} ({'new' if saved['new'] else 'identical content already archived'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["snapshot", "freeze"])
    ap.add_argument("--max-markets", type=int, default=0)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    {"snapshot": snapshot, "freeze": freeze}[args.command](args)


if __name__ == "__main__":
    main()
