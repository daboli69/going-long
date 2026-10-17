"""Phase 7.3: deterministic, as-of-safe caching for the feature pipeline.

Season cache: a builder's rows for season s depend only on inputs up to and including season s (every
builder is strictly as-of). The key for season s chains the hashes of every input restricted to seasons
<= s, plus a hash of the lab's source code and the builder's parameters:
    key(s) = H(key(s-1), H(inputs of season s), code, params)
so a change to 2026 data recomputes only 2026, a change to 2019 data recomputes 2019 onward, and any code
change recomputes everything. Nothing is ever reused across a changed historical cutoff.
Writes are atomic (temp file + replace); a corrupt or unreadable cache is ignored and rebuilt.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE_DIR

DIR = CACHE_DIR / "phase73"
LAB_DIR = Path(__file__).resolve().parent
STATS: dict = {}            # per-process hit/miss accounting for the dashboard and benchmarks
DISABLED = os.environ.get("NFL_LAB_NO_CACHE") == "1"   # the leakage gate always runs uncached


class disabled:
    """with cache73.disabled(): ...  -> every cached builder recomputes from scratch and writes nothing."""
    def __enter__(self):
        global DISABLED
        self._prev, DISABLED = DISABLED, True

    def __exit__(self, *a):
        global DISABLED
        DISABLED = self._prev


# modules whose code can change a feature value; editing any of them invalidates every cache
FEATURE_MODULES = ("advanced", "availability", "cache73", "config", "data_pipeline", "features", "geo", "ingest",
                   "lineup72", "players", "snap_model", "sources")


def code_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(LAB_DIR / f"{m}.py" for m in FEATURE_MODULES):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def frame_hash(df) -> str:
    if df is None:
        return "none"
    if isinstance(df, (bytes, str)):
        return hashlib.sha256(df if isinstance(df, bytes) else df.encode()).hexdigest()[:16]
    if isinstance(df, dict):
        df = pd.DataFrame({"k": list(map(str, df.keys())), "v": list(map(str, df.values()))}).sort_values("k")
    if isinstance(df, np.ndarray):
        return hashlib.sha256(np.ascontiguousarray(df).tobytes()).hexdigest()[:16]
    if len(df) == 0:
        return hashlib.sha256(",".join(map(str, df.columns)).encode()).hexdigest()[:16]
    d = df.reindex(sorted(df.columns), axis=1)
    h = pd.util.hash_pandas_object(d, index=False).to_numpy()
    return hashlib.sha256(np.sort(h).tobytes() + ",".join(map(str, d.columns)).encode()).hexdigest()[:16]


def _atomic_write_bytes(path: Path, data: bytes, retries: int = 5):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_bytes(data)
    for i in range(retries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:          # OneDrive / antivirus lock: bounded retry
            time.sleep(0.5 * (i + 1))
    tmp.unlink(missing_ok=True)
    raise PermissionError(f"could not replace {path}")


def save_frame(path: Path, df: pd.DataFrame):
    import io
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    _atomic_write_bytes(path, buf.getvalue())


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def season_keys(seasons, per_season_hash, params: str = "") -> dict:
    """Chained keys: key(s) depends on every season <= s."""
    code = code_hash()
    keys, prev = {}, "start"
    for s in sorted(seasons):
        prev = hashlib.sha256(f"{prev}|{per_season_hash(s)}|{code}|{params}".encode()).hexdigest()[:20]
        keys[int(s)] = prev
    return keys


def by_season(name: str, seasons, per_season_hash, compute, params: str = "", season_of=None) -> pd.DataFrame:
    """Rows for all `seasons`: reuse cached seasons whose chained key is unchanged; compute(list) for the rest.
    Output is sorted by (game_id, team) so cold and warm results are identical."""
    season_of = season_of or (lambda df: df["game_id"].str[:4].astype(int))
    seasons = sorted(int(s) for s in seasons)
    if DISABLED:
        out = compute(seasons)
        for c in out.columns:
            if c not in ("game_id", "team") and out[c].dtype == object:
                try:
                    out[c] = pd.to_numeric(out[c])
                except (ValueError, TypeError):
                    pass
        sort_cols = [c for c in ("game_id", "team") if c in out]
        return out.sort_values(sort_cols).reset_index(drop=True) if sort_cols else out
    keys = season_keys(seasons, per_season_hash, params)
    meta_p, data_p = DIR / f"{name}.json", DIR / f"{name}.parquet"
    meta = load_json(meta_p)
    cached = None
    if meta and data_p.exists():
        try:
            cached = pd.read_parquet(data_p)
        except Exception:
            cached, meta = None, {}
    reuse = [s for s in seasons if cached is not None and meta.get(str(s)) == keys[s]]
    need = [s for s in seasons if s not in reuse]
    parts = []
    if reuse:
        parts.append(cached[season_of(cached).isin(reuse)])
    if need:
        new = compute(need)
        if len(new):
            parts.append(new[season_of(new).isin(need)])
    out = pd.concat([p for p in parts if len(p)], ignore_index=True) if parts else pd.DataFrame(columns=["game_id", "team"])
    for c in out.columns:                          # same dtype normalisation on cold and warm paths
        if c not in ("game_id", "team") and out[c].dtype == object:
            try:
                out[c] = pd.to_numeric(out[c])
            except (ValueError, TypeError):
                pass
    sort_cols = [c for c in ("game_id", "team") if c in out]
    out = out.sort_values(sort_cols).reset_index(drop=True) if sort_cols else out
    STATS[name] = {"reused_seasons": reuse, "computed_seasons": need}
    if need:
        save_frame(data_p, out)
        _atomic_write_bytes(meta_p, json.dumps({str(k): v for k, v in keys.items()}).encode())
    return out


def memo(name: str, key: str, compute):
    """Single-artifact cache (joblib) with an exact key."""
    import joblib
    if DISABLED:
        return compute()
    p = DIR / f"{name}.joblib"
    key = f"{code_hash()}|{key}"                 # code changes always invalidate
    try:
        if p.exists():
            d = joblib.load(p)
            if d.get("key") == key:
                STATS[name] = {"hit": True}
                return d["value"]
    except Exception:
        pass
    v = compute()
    import io
    buf = io.BytesIO()
    joblib.dump({"key": key, "value": v}, buf)
    _atomic_write_bytes(p, buf.getvalue())
    STATS[name] = {"hit": False}
    return v


def health() -> pd.DataFrame:
    rows = []
    for p in sorted(DIR.glob("*")):
        if p.suffix in (".json", ".parquet", ".joblib"):
            rows.append({"file": p.name, "size_mb": round(p.stat().st_size / 2 ** 20, 2),
                         "modified_utc": pd.Timestamp(p.stat().st_mtime, unit="s", tz="UTC")})
    return pd.DataFrame(rows)
