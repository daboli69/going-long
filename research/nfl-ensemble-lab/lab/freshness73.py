"""Phase 7.3: how fast new official injury information reaches model-ready features and archived forecasts.

For every archived version of the official report:
  retrieved_at        - when the lab first saw that content (archive file time)
  game_statuses       - Out/Doubtful/Questionable rows it carried for its newest week
  first_build_at      - first feature build that finished after retrieval (build ledger, Phase 7.3 onward)
  first_forecast_at   - first archived forecast whose injury source names this archive version
Model inputs use the nflverse copy (unchanged champion semantics). NFL.com is the same league report and is
used for monitoring; its lead over nflverse is measured here so the decision to adopt it can be made on data.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import pandas as pd

from .config import SNAPSHOTS_DIR

TICK_MINUTES = 5


def _ts(stem: str, part: int) -> pd.Timestamp:
    return pd.Timestamp(datetime.strptime(stem.split("_")[part], "%Y%m%dT%H%M%SZ"), tz="UTC")


def versions() -> pd.DataFrame:
    from . import extra_sources as X
    from .availability import ARCHIVE_DIR
    rows = []
    for f in sorted(ARCHIVE_DIR.glob("nflverse_injuries_*.parquet")):
        try:
            d = pd.read_parquet(f, columns=["season", "week", "report_status"])
        except Exception:
            continue
        d["season"], d["week"] = pd.to_numeric(d["season"]), pd.to_numeric(d["week"])
        s = int(d["season"].max())
        w = int(d[d["season"] == s]["week"].max())
        x = d[(d["season"] == s) & (d["week"] == w)]
        rows.append({"source": "nflverse (model input)", "version": f.stem.split("_")[2], "retrieved_at": _ts(f.stem, 2),
                     "season": s, "week": w, "game_statuses": int(x["report_status"].isin(["Out", "Doubtful", "Questionable"]).sum())})
    for f in sorted(X.ARCHIVE.glob("nflcom_injuries_*.parquet")):
        d = pd.read_parquet(f)
        if d.empty:
            continue
        rows.append({"source": "NFL.com (monitoring)", "version": f.stem.split("_")[2], "retrieved_at": X.retrieved_at(f),
                     "season": int(d["season"].max()), "week": int(d["week"].max()),
                     "game_statuses": int(d["report_status"].isin(["Out", "Doubtful", "Questionable"]).sum())})
    return pd.DataFrame(rows).sort_values("retrieved_at") if rows else pd.DataFrame()


def propagation() -> pd.DataFrame:
    from .data_pipeline import BUILD_LEDGER
    from .prospective import load_ledger
    v = versions()
    if v.empty:
        return v
    builds = pd.DataFrame([json.loads(x) for x in BUILD_LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]) \
        if BUILD_LEDGER.exists() else pd.DataFrame()
    if len(builds):
        builds = builds[builds["rebuilt"].astype(bool)]
        builds["finished_at"] = pd.to_datetime(builds["finished_at"], utc=True)
    led = load_ledger()
    used = {}
    for r in led.itertuples(index=False):
        try:
            s = json.loads((SNAPSHOTS_DIR / str(r.path).replace("\\", os.sep)).read_text(encoding="utf-8"))
        except Exception:
            continue
        src = ((s.get("availability") or {}).get("home") or {}).get("inj_source") or ""
        if src.startswith("lab archive "):
            k = src.split(" ")[-1]
            t = pd.Timestamp(s["predicted_at"])
            used[k] = min(used.get(k, t), t)
    out = []
    for r in v.itertuples(index=False):
        row = r._asdict()
        if r.source.startswith("nflverse"):
            b = builds[builds["finished_at"] >= r.retrieved_at]["finished_at"].min() if len(builds) else pd.NaT
            row["first_build_at"] = b
            row["minutes_to_model_ready"] = round((b - r.retrieved_at).total_seconds() / 60, 1) if pd.notna(b) else None
            f = used.get(r.version)
            row["first_forecast_at"] = f
            row["minutes_to_first_forecast"] = round((f - r.retrieved_at).total_seconds() / 60, 1) if f is not None else None
        else:
            row["first_build_at"], row["first_forecast_at"] = None, None
            row["minutes_to_model_ready"] = row["minutes_to_first_forecast"] = None
        out.append(row)
    return pd.DataFrame(out)


def source_lead() -> pd.DataFrame:
    """Per week: first retrieval at which each source carried the final game statuses (>= 50 designations)."""
    v = versions()
    if v.empty:
        return v
    f = v[v["game_statuses"] >= 50].groupby(["season", "week", "source"])["retrieved_at"].min().unstack("source")
    if {"nflverse (model input)", "NFL.com (monitoring)"} <= set(f.columns):
        f["nflcom_lead_hours"] = ((f["nflverse (model input)"] - f["NFL.com (monitoring)"]).dt.total_seconds() / 3600).round(2)
    return f.reset_index()


def cadence_note(compute_seconds: float | None = None) -> str:
    c = f"{compute_seconds:.0f} s" if compute_seconds else "about 30-40 s"
    return (f"The scheduler checks every {TICK_MINUTES} minutes and a stage forecast takes {c}, so new information is "
            f"reflected within about {TICK_MINUTES} minutes plus processing. Teams announce inactives about 90 minutes "
            "before kickoff; the 90-, 60- and 30-minute stages each see them on the next tick.")
