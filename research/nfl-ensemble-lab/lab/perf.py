"""Phase 7.3: profiling, benchmarks and prediction-equality fixtures for the live pipeline.

`profile_rebuild` runs exactly the steps of data_pipeline.rebuild_features / assemble_from_cache with a timer
around each; `profile_forecast` times champion + challenger inference and snapshot serialisation for a slate.
`fixture` / `compare_fixtures` store and compare the full feature store and every model's predictions so an
optimisation can be shown to leave outputs unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR

OUT = ARTIFACTS_DIR / "phase73"


class Timer:
    def __init__(self):
        self.rows = []
        import psutil
        self.proc = psutil.Process()

    @contextmanager
    def __call__(self, name):
        t0, c0 = time.perf_counter(), self.proc.cpu_times()
        try:
            yield
        finally:
            c1 = self.proc.cpu_times()
            self.rows.append({"step": name, "seconds": round(time.perf_counter() - t0, 3),
                              "cpu_seconds": round((c1.user + c1.system) - (c0.user + c0.system), 2),
                              "rss_mb": round(self.proc.memory_info().rss / 2 ** 20, 1)})

    def frame(self):
        return pd.DataFrame(self.rows)


def profile_rebuild(timer: Timer | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    from . import availability, features, ingest, players, snap_model, lineup72
    from .config import CARRYOVER_SEASON, RAW_DIR
    from .data_pipeline import QB_GAMES, TEAM_GAMES, current_season
    from . import cache73
    cache73.STATS.clear()
    T = timer or Timer()
    live = current_season()
    with T("load schedule + team/QB game stats"):
        games, _ = ingest.load_games(RAW_DIR / "games.csv", CARRYOVER_SEASON)
        tstats, qstats = pd.read_parquet(TEAM_GAMES), pd.read_parquet(QB_GAMES)
        seasons = sorted(int(s) for s in games["season"].unique() if s <= live)
    with T("injury rows + pregame validation"):
        rows = availability.load_injury_rows([s for s in seasons if s >= 2016])
        valid = availability.pregame_injuries(rows, games)
    with T("player roles + team injury features"):
        snaps = availability.player_roles(seasons)
        inj = availability.team_injury_features(games, valid, snaps, rows)
    with T("OL churn"):
        churn = availability.ol_churn(seasons, games)
    with T("Phase 5 player model (RAPM load + lineups)"):
        p5 = players.build_team_player_features(games, valid, inj, seasons, progress=lambda m: None)
    with T("Phase 7 snap model (fit + features)"):
        p7 = snap_model.build_features(games, tstats, valid, inj, seasons, progress=lambda m: None)
    with T("Phase 7.2 expected lineups"):
        p72 = lineup72.build(games, valid, inj, seasons, progress=lambda m: None)
    with T("feature store assembly (ratings, QB, advanced, diffs)"):
        extra = churn.merge(p5, on=["game_id", "team"], how="outer").merge(p7, on=["game_id", "team"], how="outer") \
            .merge(p72, on=["game_id", "team"], how="outer")
        fs = features.build_feature_store(games, tstats.drop(columns=["season"], errors="ignore"),
                                          qstats.drop(columns=["season"], errors="ignore"), inj,
                                          availability.report_status_lookup(valid), extra, advanced=True)
    return fs, T.frame()


def predictions(fs: pd.DataFrame, game_ids) -> pd.DataFrame:
    """Every tracked version's six model probabilities, ensemble probability and margins for fixed games."""
    from .prospective import challenger_versions
    from .training import current_version, load_bundle, load_run
    from .weekly import predict_games
    g = fs[fs["game_id"].isin(game_ids)].sort_values("game_id")
    out = []
    for v in [current_version()] + challenger_versions():
        b = load_bundle(v)
        t, _ = predict_games(g, b, load_run(v), explain=False, challengers=False)
        cols = ["game_id", "p_champion", "margin_ensemble"] + [f"p_{k}" for k in b["model_keys"]] + \
               [f"margin_{k}" for k in b["model_keys"] if f"margin_{k}" in t]
        out.append(t[cols].melt(id_vars="game_id", var_name="output", value_name="value").assign(version=v))
    return pd.concat(out, ignore_index=True)


def profile_forecast(fs: pd.DataFrame, game_ids, timer: Timer | None = None) -> pd.DataFrame:
    from . import prospective as P
    from .data_pipeline import load_status
    T = timer or Timer()
    g = fs[fs["game_id"].isin(game_ids)]
    with T(f"build snapshot records for {len(g)} games (champion + challengers + monitoring)"):
        recs = P.build_records(g, pd.Timestamp.now(tz="UTC"), load_status(), False, None)
    with T("serialise + hash records"):
        for r in recs:
            P._content_hash(r)
            json.dumps(r, default=str)
    with T("postgame scoring"):
        try:
            P.score(progress=lambda m: None)
        except Exception:
            pass
    return T.frame()


def fixture(path, fs: pd.DataFrame, game_ids) -> dict:
    os.makedirs(path, exist_ok=True)
    fs.sort_values("game_id").reset_index(drop=True).to_parquet(f"{path}/feature_store.parquet", index=False)
    pr = predictions(fs, game_ids)
    pr.to_parquet(f"{path}/predictions.parquet", index=False)
    return {"rows": len(fs), "cols": fs.shape[1], "predictions": len(pr)}


def compare_fixtures(a, b, tol: float = 0.0) -> dict:
    fa = pd.read_parquet(f"{a}/feature_store.parquet")
    fb = pd.read_parquet(f"{b}/feature_store.parquet")
    res = {"feature_rows": (len(fa), len(fb)), "feature_cols_only_in_a": sorted(set(fa) - set(fb)),
           "feature_cols_only_in_b": sorted(set(fb) - set(fa))}
    common = [c for c in fa.columns if c in fb.columns]
    fa, fb = fa[common].set_index("game_id").sort_index(), fb[common].set_index("game_id").sort_index()
    diff_cols = {}
    for c in fa.columns:
        x, y = fa[c], fb[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv, yv = x.to_numpy(float), y.to_numpy(float)
            same_nan = np.isnan(xv) == np.isnan(yv)
            d = np.nanmax(np.abs(xv - yv)) if (~np.isnan(xv)).any() else 0.0
            if not same_nan.all() or d > tol:
                diff_cols[c] = {"max_abs_diff": float(d), "nan_mismatch": int((~same_nan).sum())}
        else:
            ne = ~((x == y) | (x.isna() & y.isna()))
            if ne.any():
                diff_cols[c] = {"values_differ": int(ne.sum())}
    res["feature_columns_differing"] = diff_cols
    pa, pb = pd.read_parquet(f"{a}/predictions.parquet"), pd.read_parquet(f"{b}/predictions.parquet")
    m = pa.merge(pb, on=["version", "game_id", "output"], suffixes=("_a", "_b"))
    m["d"] = (m["value_a"] - m["value_b"]).abs()
    res["predictions_compared"] = len(m)
    res["predictions_max_abs_diff"] = float(m["d"].max()) if len(m) else None
    res["predictions_differing"] = int((m["d"] > tol).sum())
    return res


def digest(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()[:16]


# --------------------------------------------------------------------------- benchmark (Phase 7.3)

class PeakRSS:
    def __init__(self):
        import psutil
        import threading
        self.p, self.peak, self._stop = psutil.Process(), 0, False
        self.t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop:
            self.peak = max(self.peak, self.p.memory_info().rss)
            time.sleep(0.2)

    def __enter__(self):
        self.t.start()
        return self

    def __exit__(self, *a):
        self._stop = True
        self.t.join()


def benchmark(include_full_refresh: bool = False) -> pd.DataFrame:
    import shutil
    from . import cache73, prospective as P
    from .data_pipeline import STATUS, load_status, rebuild_features
    rows = []

    def run(name, fn):
        with PeakRSS() as m:
            t0 = time.perf_counter()
            out = fn()
            sec = time.perf_counter() - t0
        rows.append({"scenario": name, "seconds": round(sec, 1), "peak_rss_mb": round(m.peak / 2 ** 20)})
        return out

    def force_rebuild():
        s = load_status()
        s["model_inputs"] = {}
        STATUS.write_text(json.dumps(s), encoding="utf-8")
        return rebuild_features(progress=lambda m: None)
    shutil.rmtree(cache73.DIR, ignore_errors=True)
    run("feature rebuild, cold caches (code or history changed)", force_rebuild)
    run("feature rebuild, warm caches, inputs changed but no season affected", force_rebuild)
    for n in ("p5_player_features", "p7_snap_features", "p72_lineups", "qb_v2_projection", "roster_team_games"):
        p = cache73.DIR / f"{n}.json"
        m = cache73.load_json(p)
        m.pop("2026", None)
        p.write_text(json.dumps(m))
    run("feature rebuild, warm caches, 2026 data changed (typical live update)", force_rebuild)
    run("rebuild skipped (no model input changed)", lambda: rebuild_features(progress=lambda m: None))
    from .data_pipeline import load_feature_store
    fs = load_feature_store()
    up = fs[(fs["season"] == fs["season"].max()) & (~fs["completed"])]
    wk = up[up["week"] == up["week"].min()]
    from .data_pipeline import load_status as ls
    run("forecast records: 1 game (champion + 2 challengers + monitoring)", lambda: P.build_records(wk.head(1), pd.Timestamp.now(tz="UTC"), ls(), False, None))
    run(f"forecast records: full slate ({len(wk)} games)", lambda: P.build_records(wk, pd.Timestamp.now(tz="UTC"), ls(), False, None))
    from . import scheduler as S
    now = pd.Timestamp.now(tz="UTC")
    due = pd.DataFrame([{"event_id": f"bench:{g}:{now:%H%M%S}", "kind": "stage", "game_id": g, "stage": "bench_t60",
                         "time_utc": now, "deadline_utc": k, "kickoff_utc": k, "action": "snapshot"}
                        for g, k in zip(wk["game_id"], wk["kickoff_utc"])])
    res = run(f"end-to-end stage: light refresh + rebuild + {len(wk)} archived forecasts", lambda: S.run_actions(due, now, lambda m: None))
    t = [v for v in (res.get("snapshots") or {}).get("by_event", {}).values()]
    rows[-1]["detail"] = f"{sum(v.get('ok', False) for v in t)} archived; timeliness {pd.Series([v.get('timeliness') for v in t]).value_counts().to_dict()}"
    if include_full_refresh:
        from .data_pipeline import refresh_data
        run("full daily refresh (downloads + rebuild)", lambda: refresh_data(progress=lambda m: None))
    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "benchmark.csv", index=False)
    return out
