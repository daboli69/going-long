"""v2 tuning on the 2022 development season only (docs/PROPS_V2_PREREGISTRATION.md, fixes 1(b) and 3).

  python -m lab.props.tune_v2          run the grid (sub-models 2016-21, every second 2022 game, 1,000 sims per point)
  python -m lab.props.tune_v2 shard I N   run games I, I+N, ... only (parallel processes; then `select` merges the shards)
  python -m lab.props.tune_v2 select   re-apply the selection rule to the saved rows

Writes artifacts/props/v2_tuning/{rows.parquet, games.parquet, selection.json}. Never reads 2023-25.
"""
from __future__ import annotations

import copy
import itertools
import json
import sys
import time
import zlib

import numpy as np
import pandas as pd

from ..config import RAW_DIR
from ..ingest import normalize_team
from . import evaluate as E
from . import game as G
from . import models as M
from . import players as PL
from . import sim as S
from . import v2 as V2

SEASON = 2022
OUT = E.OUT / "v2_tuning"
SIGMAS, KRECV, KRUSH = (0.15, 0.25, 0.35), (30.0, 60.0, 120.0), (10.0, 30.0)
N_GRID = 1000


def run(log=print, limit=None, shard=None):
    assert SEASON not in E.EVAL
    T1 = M.fit(range(2016, SEASON))
    S.calibrate_clock(T1)
    T2 = V2.prepare(T1, {"sigma_e": SIGMAS[0], "kappa_recv": KRECV[0], "kappa_rush": KRUSH[0]})
    log(f"fix 1(a): g_comp {T2['g_comp']:.4f}, g_rush {T2['g_rush']:.4f}, rz_boost {T2['rz_boost']:.3f} (v1 {T1['rz_boost']:.3f})")
    p = M.load_pbp([SEASON - 1, SEASON])
    pan = PL.panel(p, T1)
    games = pd.read_csv(RAW_DIR / "games.csv")
    for c in ("home_team", "away_team"):
        games[c] = games[c].map(normalize_team)
    games = games[games["game_type"] == "REG"]
    target = games[(games["season"] == SEASON) & games["home_score"].notna()].dropna(subset=["spread_line", "total_line"])
    target = target.sort_values(["week", "game_id"]).iloc[::2]
    if limit:
        target = target.head(limit)
    if shard:
        target = target.iloc[shard[0]::shard[1]]
    possd = E._pos_sd(pan, SEASON)
    ps = p[p["season"] == SEASON]
    first_qb = ps[ps["play_type"] == "pass"].dropna(subset=["passer_player_id"]).groupby(["game_id", "posteam"])["passer_player_id"].first()
    rows, grows = [], []
    cache_week, a = None, None
    t0 = time.time()
    for gi, g in enumerate(target.itertuples(index=False)):
        if g.week != cache_week:
            a, cache_week = PL.asof(pan, SEASON, g.week), g.week
        sides = [g.home_team, g.away_team]
        ros = pan[(pan["season"] == SEASON) & (pan["week"] == g.week)]
        hist = {}
        for t in sides:
            tp = pan[pan["posteam"] == t]
            hist[t] = (tp[(tp["season"] == SEASON) & (tp["week"] < g.week)].drop_duplicates("game_id"), tp[tp["season"] == SEASON - 1].drop_duplicates("game_id"))
        teams, pl, cols, info = G.build(a, {t: ros[ros["posteam"] == t] for t in sides}, hist, g.week,
                                        {t: first_qb.get((g.game_id, t)) for t in sides}, sides)
        elig = G.eligible(info, a)
        act = pan[pan["game_id"] == g.game_id].set_index("pid")
        elig = [(t, pid, k) for t, pid, k in elig if pid in act.index]
        imp = [(g.total_line + g.spread_line) / 2, (g.total_line - g.spread_line) / 2]
        seed = zlib.crc32(g.game_id.encode())
        for sg in SIGMAS:
            Tc = copy.copy(T2)
            Tc.update(sigma_e=sg, kappa_recv=60.0, kappa_rush=30.0)
            e, cal = S.calibrate_v2(Tc, teams, pl, imp, np.random.default_rng(seed))
            for kr, ku in itertools.product(KRECV, KRUSH):
                Tc.update(kappa_recv=kr, kappa_rush=ku)
                r = S.simulate(Tc, teams, pl, N_GRID, e, np.random.default_rng(seed + 1))
                grows.append({"game_id": g.game_id, "sigma_e": sg, "kappa_recv": kr, "kappa_rush": ku, "imp_home": imp[0], "imp_away": imp[1],
                              "cal_home": cal[0], "cal_away": cal[1], "sim_home": float(r["points"][:, 0].mean()), "sim_away": float(r["points"][:, 1].mean())})
                for t, pid, k in elig:
                    x = r["stats"][k][:, cols[pid]]
                    rows.append({"game_id": g.game_id, "week": g.week, "pid": pid, "stat": k, "sigma_e": sg, "kappa_recv": kr, "kappa_rush": ku,
                                 "actual": float(act.loc[pid, k]), "sim_mean": float(x.mean()),
                                 **dict(zip(G.QCOLS, np.quantile(x, G.LEVELS).astype(np.float32)))})
        if gi % 10 == 0:
            log(f"{gi + 1}/{len(target)} {g.game_id} {time.time() - t0:.0f}s")
    OUT.mkdir(parents=True, exist_ok=True)
    sfx = f"_{shard[0]}of{shard[1]}" if shard else ""
    pd.DataFrame(rows).to_parquet(OUT / f"rows{sfx}.parquet", index=False)
    pd.DataFrame(grows).to_parquet(OUT / f"games{sfx}.parquet", index=False)
    meta = {"g_comp": T2["g_comp"], "g_rush": T2["g_rush"], "rz_boost_v2": T2["rz_boost"], "rz_boost_v1": T1["rz_boost"],
            "clock_scale": T1["clock_scale"], "games": int(len(target)), "season": SEASON, "sims_per_point": N_GRID}
    (OUT / f"fix_1a{sfx}.json").write_text(json.dumps(meta, indent=2))
    return None if shard else select(meta)


def select(meta=None) -> dict:
    """Selection rule: per grid point apply its own 2022 per-stat mean ratios, then lowest pooled quantile-CRPS;
    ties within 0.5% -> 80% coverages closest to 0.80."""
    shards = sorted(OUT.glob("rows_*of*.parquet"))
    if shards:
        df = pd.concat([pd.read_parquet(f) for f in shards], ignore_index=True)
        gm = pd.concat([pd.read_parquet(f) for f in sorted(OUT.glob("games_*of*.parquet"))], ignore_index=True)
        meta = meta or json.loads(sorted(OUT.glob("fix_1a_*of*.json"))[0].read_text())
    else:
        df, gm = pd.read_parquet(OUT / "rows.parquet"), pd.read_parquet(OUT / "games.parquet")
        meta = meta or json.loads((OUT / "fix_1a.json").read_text())
    pts = []
    for key, s in df.groupby(["sigma_e", "kappa_recv", "kappa_rush"]):
        corr = {k: float(np.clip(v["actual"].mean() / v["sim_mean"].mean(), *V2.CLIP)) for k, v in s.groupby("stat")}
        q = s[G.QCOLS].to_numpy(float) * s["stat"].map(corr).to_numpy()[:, None]
        cr = G.qcrps(q, s["actual"].to_numpy())
        c80 = G.coverage(q, s["actual"].to_numpy(), 10, 90)
        c50 = G.coverage(q, s["actual"].to_numpy(), 25, 75)
        raw = G.qcrps(s[G.QCOLS].to_numpy(float), s["actual"].to_numpy())
        by = {k: {"n": int(m.sum()), "crps": float(cr[m].mean()), "crps_uncorrected": float(raw[m].mean()), "cov80": float(c80[m].mean()),
                  "cov50": float(c50[m].mean()), "mean_sim": float(s.loc[m, "sim_mean"].mean()), "mean_actual": float(s.loc[m, "actual"].mean())}
              for k in corr for m in [(s["stat"] == k).to_numpy()]}
        pts.append({"sigma_e": key[0], "kappa_recv": key[1], "kappa_rush": key[2], "crps": float(cr.mean()), "mean_corr": corr,
                    "cov_gap": float(sum(abs(v["cov80"] - 0.80) for v in by.values())), "by_stat": by})
    best = min(p["crps"] for p in pts)
    tied = [p for p in pts if p["crps"] <= best * 1.005]
    pick = min(tied, key=lambda p: p["cov_gap"])
    g0 = gm[(gm["sigma_e"] == pick["sigma_e"]) & (gm["kappa_recv"] == pick["kappa_recv"]) & (gm["kappa_rush"] == pick["kappa_rush"])]
    miss = np.abs(g0[["cal_home", "cal_away"]].to_numpy() - g0[["imp_home", "imp_away"]].to_numpy()).max(1)
    meta = {**meta, "games": int(gm["game_id"].nunique())}
    res = {"fix_1a": meta, "grid": sorted(pts, key=lambda p: p["crps"]), "selected": {k: pick[k] for k in ("sigma_e", "kappa_recv", "kappa_rush")},
           "selected_mean_corr": pick["mean_corr"], "selected_crps": pick["crps"], "tied_within_0.5pct": len(tied),
           "calibration_v2": {"games": int(len(g0)), "share_miss_gt_2": float((miss > 2).mean()), "median_miss": float(np.median(miss)),
                              "max_miss": float(miss.max())}}
    (OUT / "selection.json").write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "select":
        r = select()
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        with open(OUT / "run.log", "a", encoding="utf-8") as fh:
            def log(m):
                fh.write(f"{pd.Timestamp.now(tz='UTC').isoformat()} {m}\n")
                fh.flush()
            a_ = sys.argv[1:]
            r = run(log=log, limit=int(a_[1]) if a_[:1] == ["limit"] else None,
                    shard=(int(a_[1]), int(a_[2])) if a_[:1] == ["shard"] else None)
    if r is None:
        sys.exit(0)
    print(json.dumps({k: r[k] for k in ("selected", "selected_mean_corr", "selected_crps", "calibration_v2")}, indent=2))
