"""Dependence weekly record: single-leg and joint over probabilities for the next unplayed week, saved write-once with a hash before kickoff."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

from . import dependence as D
from . import ou_calls
from .config import DATA_DIR

OUT = DATA_DIR / "dependence"
FROZEN = OUT / "frozen"
LEDGER = OUT / "ledger.jsonl"
LEG = {"A_qb_wr": ("pass_yds", "rec_yds", "WR"), "B_qb_te": ("pass_yds", "rec_yds", "TE"), "C_qb_rb_rush": ("pass_yds", "rush_yds", "RB")}


def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def joint_over(fam: str, par: tuple, p1: float, p2: float, seed: int, n: int = 400_000) -> float:
    z = D.sample(fam, par, n, 1, np.random.default_rng(seed))[:, 0, :]
    u = stats.norm.cdf(z)
    return float(np.mean((u[:, 0] > 1 - p1) & (u[:, 1] > 1 - p2)))


def weekly() -> dict:
    fit = json.loads((D.PROPS.parents[1] / "docs" / "dependence_fit.json").read_text())["fit"]
    f = ou_calls.latest_file()
    if f is None:
        raise SystemExit("no weekly leans file")
    d = pd.read_csv(f)
    d = d[(d["arm"] == "frozen") & d["consensus_line"].notna() & d["p_over"].notna()]
    now = pd.Timestamp.now(tz="UTC")
    d = d[pd.to_datetime(d["kickoff_utc"], utc=True) > now]
    if d.empty:
        raise SystemExit("every game in the newest leans file has already kicked off")
    season, week = int(d["season"].iloc[0]), int(d["week"].iloc[0])
    rows = []
    for cls, (s1, s2, pos) in LEG.items():
        fam = fit[cls]["chosen"]
        par = tuple(fit[cls][fam]["par"])
        q = d[(d["stat"] == s1) & (d["position"] == "QB")]
        r = d[(d["stat"] == s2) & (d["position"] == pos)]
        for a in q.itertuples():
            for b in r[(r["game_id"] == a.game_id) & (r["team"] == a.team)].itertuples():
                rows.append({"class": cls, "game_id": a.game_id, "team": a.team, "kickoff_utc": a.kickoff_utc, "leg1": {"name": a.name, "pid": a.pid, "stat": s1, "line": float(a.consensus_line), "p_over": float(a.p_over)},
                             "leg2": {"name": b.name, "pid": b.pid, "stat": s2, "line": float(b.consensus_line), "p_over": float(b.p_over)}, "family": fam, "par": list(par),
                             "joint_over_independent": float(a.p_over * b.p_over), "joint_over_copula": joint_over(fam, par, float(a.p_over), float(b.p_over), 20261106 + len(rows))})
    rec = {"season": season, "week": week, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": str(f.name), "rows": rows,
           "note": "Fit on 2022 to 2024 normal scores. Single-leg probabilities come from the newest weekly run, not from the fitted marginals, so the copula is applied as an approximation. Outcomes are scored later."}
    body = _canon(rec)
    rec["sha256"] = hashlib.sha256(body.encode()).hexdigest()
    return rec


def freeze() -> dict:
    rec = weekly()
    FROZEN.mkdir(parents=True, exist_ok=True)
    path = FROZEN / f"week_{rec['season']}_{rec['week']:02d}.json"
    if path.exists():
        raise SystemExit(f"{path.name} already saved; write-once")
    path.write_text(json.dumps(rec, indent=1))
    with LEDGER.open("a") as fh:
        fh.write(_canon({"file": path.name, "sha256": rec["sha256"], "created_at": rec["created_at"], "rows": len(rec["rows"])}) + "\n")
    return {"file": path.name, "rows": len(rec["rows"]), "sha256": rec["sha256"]}


def verify() -> list[dict]:
    out = []
    for line in LEDGER.read_text().splitlines() if LEDGER.exists() else []:
        L = json.loads(line)
        rec = json.loads((FROZEN / L["file"]).read_text())
        h = rec.pop("sha256")
        out.append({"file": L["file"], "ok": h == L["sha256"] == hashlib.sha256(_canon(rec).encode()).hexdigest()})
    return out
