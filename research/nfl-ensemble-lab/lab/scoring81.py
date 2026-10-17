"""Phase 8.1: prospective archive of the experimental drive simulator's scoring distributions.

Separate from official forecasts and from the winner-challenger registry. Runs only AFTER a tick's official stage
snapshots are written, never raises, and writes one immutable file per (game, stage).
Parameters (league rates, home edge, Platt calibration) come from completed seasons before the current one.
"""
from __future__ import annotations

import json
import os
import stat

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR, CACHE_DIR, RAW_DIR

ARCH = ARTIFACTS_DIR / "phase81" / "drive_sim_archive"
RATES = CACHE_DIR / "phase81_drive_rates.parquet"


def _rates(games, season):
    """Pregame drive rates; rebuilt only when this season's play-by-play file changes."""
    from .specialists import drives
    pbp = RAW_DIR / f"play_by_play_{season}.parquet"
    stamp = f"{pbp.stat().st_mtime_ns}" if pbp.exists() else "none"
    meta = RATES.with_suffix(".json")
    if RATES.exists() and meta.exists() and json.loads(meta.read_text()).get("stamp") == stamp:
        return pd.read_parquet(RATES)
    w = drives.build(games, sorted(games["season"].unique()))
    w.to_parquet(RATES, index=False)
    meta.write_text(json.dumps({"stamp": stamp}))
    return w


def archive(due: pd.DataFrame, now=None) -> dict:
    try:
        from .data_pipeline import GAMES_TABLE, load_feature_store
        from .specialists.core import DriveSim, OUT as P8, _platt
        now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC"))
        games = pd.read_parquet(GAMES_TABLE)
        season = int(games["season"].max())
        fs = load_feature_store()
        w = _rates(games, season)
        df = fs.copy()
        for side in ("home", "away"):
            df = df.merge(w.rename(columns={c: f"{side}_{c}" for c in w.columns if c not in ("game_id", "team")})
                          .rename(columns={"team": f"{side}_team"}), on=["game_id", f"{side}_team"], how="left")
        train = df[(df["season"] < season) & (df["season"] >= 2016) & df["home_win"].notna()]
        sp = pd.read_parquet(P8 / "specialist_oof.parquet")
        hist = sp[(sp["specialist"] == "E") & (sp["season"] < season)].dropna(subset=["raw", "home_win"])
        written = 0
        ARCH.mkdir(parents=True, exist_ok=True)
        for ev in due.itertuples(index=False):
            g = df[df["game_id"] == ev.game_id]
            if g.empty:
                continue
            f = ARCH / f"{ev.game_id}_{ev.stage}.json"
            if f.exists():
                continue                                      # one immutable file per (game, stage)
            pr = DriveSim().fit_predict(train, g).iloc[0]
            if pd.isna(pr["raw"]):
                continue
            p_cal = float(_platt(hist["raw"].to_numpy(), hist["home_win"].to_numpy(), np.array([pr["raw"]]))[0])
            rec = {"game_id": ev.game_id, "stage": ev.stage, "archived_at": pd.Timestamp.now(tz="UTC").isoformat(),
                   "kickoff_utc": str(g["kickoff_utc"].iloc[0]), "model": "Phase 8 specialist E drive simulator (experimental)",
                   "trained_through_season": season - 1, "p_home_raw": float(pr["raw"]), "p_home_calibrated": p_cal,
                   **{k: float(pr[k]) for k in ("margin", "total", "margin_p10", "margin_p90", "total_p10", "total_p90")},
                   "note": "experimental scoring distribution; not an official or tracked winner forecast"}
            if pd.Timestamp(rec["archived_at"]) >= pd.Timestamp(rec["kickoff_utc"]):
                continue
            f.write_text(json.dumps(rec, indent=2))
            os.chmod(f, stat.S_IREAD)
            written += 1
        return {"ok": True, "written": written}
    except Exception as exc:
        return {"ok": False, "reason": repr(exc)[:200]}


def evaluate() -> pd.DataFrame:
    """Score archived distributions against completed games (coverage, MAE); descriptive until large samples."""
    files = sorted(ARCH.glob("*.json"))
    if not files:
        return pd.DataFrame()
    from .data_pipeline import GAMES_TABLE
    g = pd.read_parquet(GAMES_TABLE).set_index("game_id")
    rows = []
    for f in files:
        r = json.loads(f.read_text())
        if r["game_id"] not in g.index or not bool(g.loc[r["game_id"], "completed"]):
            continue
        h, a = g.loc[r["game_id"], "home_score"], g.loc[r["game_id"], "away_score"]
        m, t = h - a, h + a
        rows.append(r | {"actual_margin": m, "actual_total": t, "margin_abs_err": abs(r["margin"] - m), "total_abs_err": abs(r["total"] - t),
                         "margin_in_80": r["margin_p10"] <= m <= r["margin_p90"], "total_in_80": r["total_p10"] <= t <= r["total_p90"]})
    return pd.DataFrame(rows)
