"""Append-only prediction tracker: flat 1-unit moneyline picks from frozen pre-kickoff snapshots.

Two CSV files, both append-only:
  evaluations.csv  one row per (game, rule) written when the snapshot is read; says whether the pick qualified.
                   Non-qualifying games are recorded too, so nobody can later say a losing game was never a candidate.
  settlements.csv  one row per (game, rule) written after the game is final.
Neither file is ever edited or sorted. Each evaluation row carries the hash of the rule, and a chain hash
over the previous row, so an edit anywhere breaks verification.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .config import LAB_ROOT, RAW_DIR, SNAPSHOTS_DIR

TRACK_DIR = LAB_ROOT / "reports" / "tracker"
EVAL_CSV = TRACK_DIR / "evaluations.csv"
SETTLE_CSV = TRACK_DIR / "settlements.csv"
LEDGER = SNAPSHOTS_DIR / "prospective" / "ledger.jsonl"

# Frozen on 2026-11-09, before this tracker had scored anything. Changing any value makes a new rule_id;
# old rows keep the old id, and report() shows rules separately.
RULE = {
    "name": "ml_edge_v1",
    "market": "moneyline",
    "model_p": "p_champion",
    "market_p": "market_at_snapshot.p_home_novig",
    "min_edge": 0.05,
    "stake_units": 1.0,
    "price": "market_at_snapshot home/away moneyline",
    "book": "nfldata consensus line (not one sportsbook)",
}
RULE_ID = hashlib.sha256(json.dumps(RULE, sort_keys=True).encode()).hexdigest()[:12]

EVAL_COLS = ["game_id", "rule_id", "snapshot_window", "snapshot_at", "kickoff_utc", "recorded_at", "origin", "book",
             "side", "american_odds", "line_spread", "model_p_side", "market_p_novig_side", "edge", "qualified",
             "stale_data", "flags", "prev_hash", "row_hash"]
SETTLE_COLS = ["game_id", "rule_id", "settled_at", "home_score", "away_score", "outcome", "units"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def units_for(american: float, outcome: str, stake: float = 1.0) -> float:
    if outcome == "push":
        return 0.0
    if outcome == "loss":
        return -stake
    return stake * (100.0 / abs(american) if american < 0 else american / 100.0)


def _row_hash(row: dict, prev: str) -> str:
    body = "|".join(str(row.get(c, "")) for c in EVAL_COLS if c not in ("prev_hash", "row_hash"))
    return hashlib.sha256((prev + body).encode()).hexdigest()[:16]


def _read(path: Path, cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _append(path: Path, cols: list[str], rows: list[dict]) -> None:
    TRACK_DIR.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerows(rows)


def latest_prekickoff_snapshots() -> dict[str, dict]:
    """Latest snapshot per game written before kickoff. Snapshots written after kickoff are ignored."""
    best: dict[str, tuple[str, dict]] = {}
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if pd.Timestamp(e["predicted_at"]) >= pd.Timestamp(e["kickoff_utc"]):
            continue
        cur = best.get(e["game_id"])
        if cur is None or e["predicted_at"] > cur[0]:
            best[e["game_id"]] = (e["predicted_at"], e)
    return {g: v[1] for g, v in best.items()}


def evaluate_snapshot(entry: dict) -> dict:
    snap = json.loads((SNAPSHOTS_DIR / entry["path"].replace("\\", "/")).read_text(encoding="utf-8"))
    m = snap.get("market_at_snapshot") or {}
    flags = []
    p_home = snap["p_champion"]
    row = {"game_id": entry["game_id"], "rule_id": RULE_ID, "snapshot_window": entry["window"],
           "snapshot_at": entry["predicted_at"], "kickoff_utc": entry["kickoff_utc"], "recorded_at": _now(),
           "book": "nfldata_consensus", "stale_data": str(bool(snap.get("stale_data"))).lower()}
    if snap.get("stale_data"):
        flags.append("stale_data")
    pn, ml_h, ml_a = m.get("p_home_novig"), m.get("home_moneyline"), m.get("away_moneyline")
    if pn is None or ml_h is None or ml_a is None or any(pd.isna(x) for x in (pn, ml_h, ml_a)):
        row.update(side="", american_odds="", line_spread="", model_p_side="", market_p_novig_side="", edge="", qualified="0")
        flags.append("no_market_odds")
    else:
        edge_h = p_home - pn
        side = "home" if edge_h >= 0 else "away"
        edge = abs(edge_h)
        row.update(side=side, american_odds=ml_h if side == "home" else ml_a, line_spread=m.get("spread_line", ""),
                   model_p_side=round(p_home if side == "home" else 1 - p_home, 6),
                   market_p_novig_side=round(pn if side == "home" else 1 - pn, 6), edge=round(edge, 6),
                   qualified="1" if edge >= RULE["min_edge"] else "0")
    row["flags"] = ";".join(flags)
    return row


def select(origin: str = "live") -> list[dict]:
    """Append an evaluation row for every pre-kickoff snapshot not yet recorded under this rule."""
    ev = _read(EVAL_CSV, EVAL_COLS)
    done = set(ev.loc[ev.rule_id == RULE_ID, "game_id"])
    prev = ev["row_hash"].iloc[-1] if len(ev) else "GENESIS"
    new = []
    for gid, entry in sorted(latest_prekickoff_snapshots().items()):
        if gid in done:
            continue
        row = evaluate_snapshot(entry)
        row["origin"] = origin
        row["prev_hash"] = prev
        row["row_hash"] = prev = _row_hash(row, prev)
        new.append(row)
    if new:
        _append(EVAL_CSV, EVAL_COLS, new)
    return new


def settle() -> list[dict]:
    ev, st = _read(EVAL_CSV, EVAL_COLS), _read(SETTLE_CSV, SETTLE_COLS)
    games = pd.read_csv(RAW_DIR / "games.csv").set_index("game_id")
    done = set(zip(st.game_id, st.rule_id))
    out = []
    for r in ev.itertuples():
        if (r.game_id, r.rule_id) in done or r.game_id not in games.index:
            continue
        g = games.loc[r.game_id]
        if pd.isna(g.home_score) or pd.isna(g.away_score):
            continue
        margin = g.home_score - g.away_score
        if margin == 0:
            outcome = "push"
        elif r.side == "":
            outcome = "no_bet"
        else:
            outcome = "win" if (margin > 0) == (r.side == "home") else "loss"
        units = ""
        if r.qualified == "1":
            units = round(units_for(float(r.american_odds), outcome, RULE["stake_units"]), 4)
        out.append({"game_id": r.game_id, "rule_id": r.rule_id, "settled_at": _now(), "home_score": int(g.home_score),
                    "away_score": int(g.away_score), "outcome": outcome, "units": units})
    if out:
        _append(SETTLE_CSV, SETTLE_COLS, out)
    return out


def verify() -> list[str]:
    """Problems that make the record unverifiable. An empty list means the chain and joins are intact."""
    problems = []
    ev, st = _read(EVAL_CSV, EVAL_COLS), _read(SETTLE_CSV, SETTLE_COLS)
    prev = "GENESIS"
    for i, r in ev.iterrows():
        if r.prev_hash != prev or _row_hash(r.to_dict(), prev) != r.row_hash:
            problems.append(f"evaluations.csv row {i + 2}: hash chain broken at {r.game_id}")
            break
        prev = r.row_hash
        if pd.Timestamp(r.snapshot_at) >= pd.Timestamp(r.kickoff_utc):
            problems.append(f"{r.game_id}: snapshot not before kickoff")
    if ev.duplicated(["game_id", "rule_id"]).any():
        problems.append("duplicate (game_id, rule_id) in evaluations.csv")
    if st.duplicated(["game_id", "rule_id"]).any():
        problems.append("duplicate (game_id, rule_id) in settlements.csv")
    orphan = set(zip(st.game_id, st.rule_id)) - set(zip(ev.game_id, ev.rule_id))
    problems += [f"settlement with no evaluation: {g}" for g, _ in sorted(orphan)]
    games = pd.read_csv(RAW_DIR / "games.csv")
    played = games[(games.season >= 2026) & games.home_score.notna()]
    snaps = latest_prekickoff_snapshots()
    first = min(pd.Timestamp(e["predicted_at"]) for e in snaps.values()) if snaps else None
    kick = pd.to_datetime(played.gameday + " " + played.gametime.fillna("13:00"), errors="coerce")
    before = played[(kick < first.tz_localize(None)) if first is not None else False]
    missing = sorted(set(played.game_id) - set(snaps) - set(before.game_id))
    if missing:
        problems.append(f"played games with no pre-kickoff snapshot (unrecorded, not scored): {', '.join(missing)}")
    if len(before):
        problems.append(f"note: {len(before)} played games predate the snapshot system (first snapshot {first:%Y-%m-%d}); they are not in the record")
    flagged = ev[ev["flags"] != ""]
    for r in flagged.itertuples():
        problems.append(f"{r.game_id}: flagged {r.flags}")
    return problems


QUOTES = RAW_DIR / "market" / "going_quotes.parquet"
MAX_QUOTE_AGE_MIN = 30.0


def best_book_price(quotes: pd.DataFrame, game_id: str, side: str, snapshot_at: str, kickoff_utc: str) -> dict | None:
    """Best moneyline a named book showed for this side at snapshot time, if any quote is under 30 minutes old."""
    _, _, away, home = game_id.split("_")
    t, k = pd.Timestamp(snapshot_at), pd.Timestamp(kickoff_utc)
    x = quotes[(quotes.market == "h2h") & (quotes.home == home) & (quotes.away == away) & (quotes.side == side)
               & ((quotes.commence_time - k).abs() < pd.Timedelta(hours=12)) & (quotes.quote_time <= t)
               & (quotes.quote_time >= t - pd.Timedelta(minutes=MAX_QUOTE_AGE_MIN))]
    if x.empty:
        return None
    x = x.sort_values("quote_time").groupby("book").tail(1)
    best = x.loc[x.price.map(lambda o: units_for(o, "win")).idxmax()]
    return {"book": str(best.book), "american_odds": float(best.price), "quote_time": best.quote_time.isoformat()}


def bettable(done: pd.DataFrame, quotes: pd.DataFrame | None = None) -> dict:
    """Units for settled bets re-priced at a real book. A bet with no fresh quote is not counted."""
    if quotes is None:
        quotes = pd.read_parquet(QUOTES) if QUOTES.exists() else pd.DataFrame()
    n, units = 0, 0.0
    for r in done.itertuples():
        b = best_book_price(quotes, r.game_id, r.side, r.snapshot_at, r.kickoff_utc) if len(quotes) else None
        if b:
            n, units = n + 1, units + units_for(b["american_odds"], r.outcome)
    return {"priced_bets": n, "unpriced_bets": int(len(done) - n), "units": float(units) if n else None,
            "max_quote_age_minutes": MAX_QUOTE_AGE_MIN}


def performance(rule_id: str = RULE_ID, origin: str | None = "live") -> dict:
    """Record for one rule. Default is live rows only: backfill rows were scored after the rule was written, so they
    stay in the files but are not a performance claim. Pass origin=None for every row, "backfill" for the backfill."""
    ev, st = _read(EVAL_CSV, EVAL_COLS), _read(SETTLE_CSV, SETTLE_COLS)
    ev, st = ev[ev.rule_id == rule_id], st[st.rule_id == rule_id]
    if origin is not None:
        ev = ev[ev.origin == origin]
    q = ev[ev.qualified == "1"].merge(st[["game_id", "outcome", "units", "settled_at"]], on="game_id", how="left")
    done = q[q.outcome.isin(["win", "loss", "push"])].copy()
    done["units"] = done.units.astype(float)
    done = done.sort_values("kickoff_utc")
    cum = done.units.cumsum()
    dd = float((cum - cum.cummax().clip(lower=0)).min()) if len(done) else 0.0
    wl = done[done.outcome != "push"]
    return {"rule_id": rule_id, "origin": origin or "all", "price_basis": "nfldata consensus line, not a bettable book",
            "bettable_price": bettable(done), "games_evaluated": int(len(ev)), "qualified": int(len(q)), "open": int(len(q) - len(done)),
            "settled": int(len(done)), "wins": int((wl.outcome == "win").sum()),
            "win_rate": float((wl.outcome == "win").mean()) if len(wl) else None,
            "units": float(done.units.sum()), "roi_per_unit": float(done.units.sum() / len(done)) if len(done) else None,
            "max_drawdown_units": dd, "cumulative": [round(float(x), 4) for x in cum]}
