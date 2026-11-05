"""Tails weekly record: flags and ranges for the next unplayed week, saved write-once with a hash before kickoff and scored after the games."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

from . import tails
from .tails import OUT, RAW, expected_tail, rule

FROZEN = OUT / "frozen"
LEDGER = OUT / "ledger.jsonl"


def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def weekly(week: int | None = None) -> dict:
    R = rule()
    g, fitted = tails.build()
    season = R["upcoming_season"]
    up = g[(g["season"] == season) & g["result"].isna() & g["spread_line"].notna()]
    if up.empty:
        raise SystemExit("no unplayed games with a closing line")
    week = int(week or up["week"].min())
    up = up[up["week"] == week]
    played = g[g["result"].notna()]
    last = {}
    for r in played.itertuples():
        last[r.home_team], last[r.away_team] = r.home_qb_id, r.away_qb_id
    dc = pd.read_parquet(RAW / "depth_charts_2026.parquet")
    dc = dc[(dc["pos_abb"] == "QB") & (dc["pos_rank"].astype(str) == "1")].sort_values("dt").groupby("team").tail(1)
    starter = {r.team: (r.gsis_id, r.player_name) for r in dc.itertuples()}
    disc = g[g["season"].between(*R["discovery"]) & g["result"].notna()]
    sigma = float(disc.loc[~disc["u_any"], "e"].std())
    from sklearn.linear_model import QuantileRegressor
    X = lambda d: np.column_stack([d["u_qb"].astype(float), d["gap"]])
    qm = {q: QuantileRegressor(quantile=q, alpha=0.0, solver="highs").fit(X(disc), disc["e"].to_numpy()) for q in (0.05, 0.95)}
    rows = []
    for r in up.itertuples():
        info, flag_qb, vals = {}, False, {}
        for side, team in (("home", r.home_team), ("away", r.away_team)):
            qid, name = starter.get(team, (last.get(team), None))
            val, n = tails.QB_NOW.get(qid, (tails.PRIOR_MEAN, 0))
            vals[side] = val
            changed = bool(qid != last.get(team))
            flag_qb |= changed or n < R["new_qb_dropbacks"]
            info[side] = {"qb": name or str(qid), "career_dropbacks": int(n), "changed": changed}
        elo_qb = float(r.elo + fitted["qb_beta_points_per_epa"] * (vals["home"] - vals["away"]))
        gap = abs(elo_qb - r.spread_line)
        u_gap = bool(gap >= fitted["gap_threshold"])
        feat = np.array([[float(flag_qb), gap]])
        lo, hi = (float(r.spread_line + qm[q].predict(feat)[0]) for q in (0.05, 0.95))
        rows.append({"gid": r.game_id, "away": r.away_team, "home": r.home_team, "closing_spread_home": float(r.spread_line), "elo_qb_margin": elo_qb, "gap": gap,
                     "u_qb": bool(flag_qb), "u_gap": u_gap, "u_any": bool(flag_qb or u_gap), "range_90": [lo, hi], "baseline_tail_14": expected_tail(sigma, 14), "baseline_tail_21": expected_tail(sigma, 21),
                     "starters": info})
    return {"season": season, "week": week, "reference_sigma": sigma, "fitted": fitted, "games": rows}


def freeze(week: int | None = None) -> dict:
    """Write-once: an existing record for the week is returned unchanged."""
    rec = weekly(week)
    FROZEN.mkdir(parents=True, exist_ok=True)
    path = FROZEN / f"{rec['season']}_w{rec['week']:02d}.json"
    if path.exists():
        return json.loads(path.read_text())
    body = {"created": datetime.now(timezone.utc).isoformat(), "rule_sha256": tails.freeze_rule_hash(), "forecast": rec}
    body["sha256"] = hashlib.sha256(_canon(body).encode()).hexdigest()
    path.write_text(json.dumps(body, indent=1))
    with LEDGER.open("a") as f:
        f.write(json.dumps({"file": path.name, "sha256": body["sha256"], "created": body["created"]}) + "\n")
    return body


def verify(body: dict) -> bool:
    b = {k: v for k, v in body.items() if k != "sha256"}
    return hashlib.sha256(_canon(b).encode()).hexdigest() == body.get("sha256")


def score() -> dict:
    """Score every frozen week whose games are finished: tail hits against the closing line, by flag. Frozen files are never edited."""
    g = tails.load_games()
    res = g.set_index("game_id")
    tot = {f: {"games": 0, "hit14": 0, "hit21": 0, "priced14": 0.0, "priced21": 0.0} for f in ("u_qb", "u_gap", "u_any", "all")}
    weeks = []
    for path in sorted(FROZEN.glob("*.json")):
        body = json.loads(path.read_text())
        if not verify(body):
            weeks.append({"file": path.name, "status": "hash mismatch, not scored"})
            continue
        n = 0
        for r in body["forecast"]["games"]:
            if r["gid"] not in res.index or pd.isna(res.loc[r["gid"], "result"]):
                continue
            e = abs(res.loc[r["gid"], "result"] - res.loc[r["gid"], "spread_line"])
            n += 1
            for f in ("u_qb", "u_gap", "u_any", "all"):
                if f == "all" or r[f]:
                    t = tot[f]
                    t["games"] += 1
                    t["hit14"] += int(e >= 14)
                    t["hit21"] += int(e >= 21)
                    t["priced14"] += r["baseline_tail_14"]
                    t["priced21"] += r["baseline_tail_21"]
        weeks.append({"file": path.name, "scored_games": n, "games": len(body["forecast"]["games"])})
    return {"weeks": weeks, "by_flag": tot}
