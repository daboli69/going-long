"""Coherence weekly record: quarterback and listed-receiver means from the newest weekly run, the incoherence c and the reconciled values, saved write-once with a hash before kickoff."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from . import coherence as C
from . import ou_calls
from .config import DATA_DIR

OUT = DATA_DIR / "coherence"
FROZEN = OUT / "frozen"
LEDGER = OUT / "ledger.jsonl"


def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def weekly() -> dict:
    tg, r = C.load_teamgames("base_mean")
    share = C.share_by_k(tg)
    b = C.fit_slopes(tg, r, share)
    f = ou_calls.latest_file()
    if f is None:
        raise SystemExit("no weekly leans file")
    d = pd.read_csv(f)
    d = d[(d["arm"] == "frozen") & d["mean"].notna()]
    d = d[pd.to_datetime(d["kickoff_utc"], utc=True) > pd.Timestamp.now(tz="UTC")]
    if d.empty:
        raise SystemExit("every game in the newest leans file has already kicked off")
    rows = []
    for (gid, team), g in d.groupby(["game_id", "team"]):
        q = g[(g["stat"] == "pass_yds") & (g["position"] == "QB")]
        rc = g[(g["stat"] == "rec_yds") & g["position"].isin(["WR", "TE", "RB"])]
        if len(q) != 1 or rc.empty:
            continue
        fq, fr = float(q["mean"].iloc[0]), rc["mean"].astype(float)
        k = len(rc)
        c = fq - fr.sum() - fq * share[int(min(k, 5))]
        rows.append({"game_id": gid, "team": team, "qb": q["name"].iloc[0], "k_listed": k, "qb_mean": fq, "listed_sum": float(fr.sum()), "incoherence": float(c), "qb_reconciled": float(fq + b["b_Q"] * c),
                     "receivers": [{"name": n, "mean": float(m), "reconciled": float(m + b["b_R"] * c * m / fr.sum())} for n, m in zip(rc["name"], fr)]})
    rec = {"season": int(d["season"].iloc[0]), "week": int(d["week"].iloc[0]), "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": f.name, "slopes": b, "share_by_k": {str(k): v for k, v in share.items()}, "rows": rows,
           "note": "Slopes and remainder shares were fitted on 2022 to 2024 baseline forecasts and are applied to the newest weekly run's means, a different model. Outcomes are scored later."}
    rec["sha256"] = hashlib.sha256(_canon(rec).encode()).hexdigest()
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
