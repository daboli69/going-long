"""2026 prospective stage for the props simulator (docs/PROPS_V2_PREREGISTRATION.md). Manual only: Travis runs it; the
pinned scheduler does not.

  python -m lab.props.weekly                 archive v1 / v2 / baseline-B quantiles for the coming week's unstarted games
  python -m lab.props.weekly archive --week 7
  python -m lab.props.weekly preview         same projections for every upcoming game with lines; re-runnable, not archived or scored
  python -m lab.props.weekly score           score archived games that are final and have play-by-play (written once)
  python -m lab.props.weekly summary         descriptive interim table (not the pre-registered test)

Pregame inputs only: games.csv lines and listed QBs, rosters / injury report as of the run, play-by-play of earlier weeks.
Archive: artifacts/props/prospective/<season>_w<week>/<game_id>.parquet + .json, created exclusively (never overwritten).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import time
import zlib
from pathlib import Path

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

SEASON = 2026
OUT = E.OUT / "prospective"
N_SIMS = 10_000
TZ = "America/New_York"


def kickoff(gameday, gametime) -> pd.Timestamp:
    return pd.Timestamp(f"{gameday} {gametime or '13:00'}").tz_localize(TZ)


def load_games() -> pd.DataFrame:
    g = pd.read_csv(RAW_DIR / "games.csv")
    for c in ("home_team", "away_team"):
        g[c] = g[c].map(normalize_team)
    return g[g["game_type"] == "REG"]


def pick_week(games: pd.DataFrame, season: int, now: pd.Timestamp):
    g = games[(games["season"] == season) & games["home_score"].isna()]
    g = g[[kickoff(d, t) > now for d, t in zip(g["gameday"], g["gametime"])]]
    return int(g["week"].min()) if len(g) else None


def availability(ros: pd.DataFrame, inj: pd.DataFrame, week: int, team: str):
    """(DataFrame pid/position, rule). ros/inj are one season with normalised team codes."""
    r = ros[(ros["posteam"] == team) & (ros["week"] == week)]
    rule = "ACT (game-day inactives published)"
    if not len(r) or not (r["status"] == "INA").any():
        if not len(r):
            prev = ros[(ros["posteam"] == team) & (ros["week"] < week)]
            if not len(prev):
                return pd.DataFrame(columns=["pid", "position"]), "no roster"
            r = prev[prev["week"] == prev["week"].max()]
            rule = f"week {int(r['week'].iloc[0])} ACT roster minus injury-report Out (no week {week} roster yet)"
        else:
            rule = "ACT roster minus injury-report Out (inactives not yet published)"
        out = set(inj.loc[(inj["team"] == team) & (inj["week"] == week) & (inj["report_status"] == "Out"), "gsis_id"])
        r = r[r["status"] == "ACT"]
        return r[~r["pid"].isin(out)][["pid", "position"]], rule
    return r[r["status"] == "ACT"][["pid", "position"]], rule


def _commit():
    try:
        root = Path(__file__).resolve().parents[2]
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "lab/props"], cwd=root, capture_output=True, text=True).stdout.strip())
        return sha + ("+dirty" if dirty else "")
    except OSError:
        return "unknown"


def _write_once(path: Path, data: bytes):
    with open(path, "xb") as fh:              # exclusive create: an archived file is never overwritten
        fh.write(data)


def _qrow(version, x_mean, q):
    return {"version": version, "mean": float(x_mean), **dict(zip(G.QCOLS, np.asarray(q, float)))}


def archive(season=SEASON, week=None, now=None, n_sims=N_SIMS, out=OUT, log=print, only=None, preview=False) -> dict:
    """preview=True: overwritable projections under <out>/preview/ for viewing only; never part of the pre-registered test."""
    now = now or pd.Timestamp.now(tz=TZ)
    games = load_games()
    week = week or pick_week(games, season, now)
    if week is None:
        log("No unplayed games left this season.")
        return {"week": None, "archived": [], "skipped": []}
    wk = games[(games["season"] == season) & (games["week"] == week)].sort_values("game_id")
    odir = out / f"{season}_w{week:02d}"
    wdir = out / "preview" / f"{season}_w{week:02d}" if preview else odir
    wdir.mkdir(parents=True, exist_ok=True)
    todo, skipped = [], []
    for g in wk.itertuples(index=False):
        ko = kickoff(g.gameday, g.gametime)
        why = ("already archived" if (odir / f"{g.game_id}.parquet").exists() else "kicked off" if ko <= now
               else "no spread/total yet" if pd.isna(g.spread_line) or pd.isna(g.total_line) else None)
        if only and g.game_id not in only:
            why = why or "not selected"
        (skipped if why else todo).append((g, why))
    for g, why in skipped:
        log(f"skip {g.game_id}: {why}")
    if not todo:
        return {"week": week, "archived": [], "skipped": [(g.game_id, w) for g, w in skipped]}
    tuned = V2.TUNED
    T1 = M.fit(range(2016, season))
    S.calibrate_clock(T1)
    T2 = V2.prepare(T1) if tuned else None
    p = M.load_pbp([season - 1, season])
    p = p[(p["season"] < season) | (p["week"] < week)]
    pan = PL.panel(p, T1)
    a = PL.asof(pan, season, week)
    possd = E._pos_sd(pan, season)
    ros = pd.read_parquet(RAW_DIR / f"roster_weekly_{season}.parquet", columns=["week", "team", "gsis_id", "status", "position", "full_name"])
    ros = ros.rename(columns={"gsis_id": "pid", "team": "posteam"}).assign(posteam=lambda d: d["posteam"].map(normalize_team))
    names = ros.drop_duplicates("pid", keep="last").set_index("pid")["full_name"]
    inj_f = RAW_DIR / f"injuries_{season}.parquet"
    inj = pd.read_parquet(inj_f) if inj_f.exists() else pd.DataFrame(columns=["team", "week", "gsis_id", "report_status"])
    inj = inj.assign(team=inj["team"].map(normalize_team))
    ps = p[p["season"] == season]
    first_qb = ps[ps["play_type"] == "pass"].dropna(subset=["passer_player_id"]).sort_values(["week", "game_id", "play_id"]) \
        .groupby(["game_id", "posteam"])["passer_player_id"].first().reset_index().merge(ps.drop_duplicates("game_id")[["game_id", "week"]])
    pbp_games = int(ps["game_id"].nunique())
    done_games = int(games[(games["season"] == season) & (games["week"] < week) & games["home_score"].notna()]["game_id"].nunique())
    archived = []
    for g, _ in todo:
        t0 = time.time()
        sides = [g.home_team, g.away_team]
        avail, rules, qbs, qsrc, hist = {}, {}, {}, {}, {}
        for t, qcol in zip(sides, ("home_qb_id", "away_qb_id")):
            avail[t], rules[t] = availability(ros, inj, week, t)
            q = getattr(g, qcol)
            if isinstance(q, str) and q:
                qbs[t], qsrc[t] = q, "games.csv listed QB"
            else:
                last = first_qb[first_qb["posteam"] == t].sort_values("week")
                qbs[t], qsrc[t] = (last["passer_player_id"].iloc[-1], "most recent starter") if len(last) else (None, "none")
            tp = pan[pan["posteam"] == t]
            hist[t] = (tp[(tp["season"] == season) & (tp["week"] < week)].drop_duplicates("game_id"), tp[tp["season"] == season - 1].drop_duplicates("game_id"))
        teams, pl, cols, info = G.build(a, avail, hist, week, qbs, sides)
        elig = G.eligible(info, a)
        imp = [(g.total_line + g.spread_line) / 2, (g.total_line - g.spread_line) / 2]
        seed = zlib.crc32(g.game_id.encode())
        rng = np.random.default_rng(seed)
        e1, _ = S.calibrate(T1, teams, pl, imp, rng)
        r1 = S.simulate(T1, teams, pl, n_sims, e1, rng)
        res = {"v1": (e1, r1)}
        if tuned:
            rng2 = np.random.default_rng(seed + 1)
            e2, _ = S.calibrate_v2(T2, teams, pl, imp, rng2)
            res["v2"] = (e2, S.simulate(T2, teams, pl, n_sims, e2, rng2))
        rows = []
        for t, pid, k in elig:
            si = sides.index(t)
            ratio = float(np.clip(imp[si] / max(E._team_ppg(games, season, week, t), 1.0), 0.6, 1.6))
            base = {"game_id": g.game_id, "season": season, "week": week, "team": t, "pid": pid, "name": names.get(pid, ""), "stat": k}
            for v, (_, r) in res.items():
                x = r["stats"][k][:, cols[pid]]
                if v == "v2":
                    x = V2.correct(x, k)
                rows.append(base | _qrow(v, x.mean(), np.quantile(x, G.LEVELS)))
            b = G.baseline(a, pid, k, ratio, possd)
            if b is not None:
                rows.append(base | _qrow("base", *G.baseline_quantiles(b)))
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        data = buf.getvalue()
        meta = {"game_id": g.game_id, "season": season, "week": week, "created_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                "kickoff_et": kickoff(g.gameday, g.gametime).isoformat(), "spread_line": float(g.spread_line), "total_line": float(g.total_line),
                "implied": imp, "availability": rules, "qb": qbs, "qb_source": qsrc, "n_sims": n_sims, "commit": _commit(),
                "versions": sorted(res) + ["base"], "v2_tuned": tuned, "v2_params": {**V2.DISPERSION, "mean_corr": V2.MEAN_CORR} if tuned else None,
                "sim_points": {v: [float(r["points"][:, 0].mean()), float(r["points"][:, 1].mean())] for v, (_, r) in res.items()},
                "efficiency": {v: [float(e[0]), float(e[1])] for v, (e, _) in res.items()},
                "pbp_games_this_season": pbp_games, "completed_games_before_week": done_games,
                "player_stats": int(df[["pid", "stat"]].drop_duplicates().shape[0]) if len(df) else 0, "sha256": hashlib.sha256(data).hexdigest()}
        if preview:
            meta["preview"] = True
            (wdir / f"{g.game_id}.parquet").write_bytes(data)
            (wdir / f"{g.game_id}.json").write_text(json.dumps(meta, indent=2))
            archived.append(g.game_id)
            log(f"previewed {g.game_id} ({meta['player_stats']} player-stats) {time.time() - t0:.0f}s")
            continue
        _write_once(wdir / f"{g.game_id}.parquet", data)
        _write_once(wdir / f"{g.game_id}.json", json.dumps(meta, indent=2).encode())
        with open(out / "archive_log.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: meta[k] for k in ("game_id", "created_utc", "kickoff_et", "commit", "versions", "sha256")}) + "\n")
        archived.append(g.game_id)
        log(f"archived {g.game_id} ({meta['player_stats']} player-stats, {', '.join(sorted(set(rules.values())))}) {time.time() - t0:.0f}s")
    return {"week": week, "archived": archived, "skipped": [(g.game_id, w) for g, w in skipped]}


def actuals(p: pd.DataFrame) -> pd.DataFrame:
    """Regulation stats per (game_id, pid) with v1's definitions (lab.props.players.panel)."""
    s = p[(p["qtr"] <= 4) & p["play_type"].isin(["pass", "run"]) & (p["two_point_attempt"] == 0) & (p["qb_kneel"] == 0) & (p["qb_spike"] == 0)]
    tg = s[(s["play_type"] == "pass") & (s["sack"] == 0) & s["receiver_player_id"].notna()]
    rec = tg.groupby(["game_id", "receiver_player_id"]).agg(rec_yds=("receiving_yards", "sum"), rec=("complete_pass", "sum"))
    rus = s[(s["play_type"] == "run") & s["rusher_player_id"].notna()].groupby(["game_id", "rusher_player_id"]).agg(rush_yds=("rushing_yards", "sum"))
    pas = s[s["play_type"] == "pass"].groupby(["game_id", "passer_player_id"]).agg(pass_yds=("passing_yards", "sum"))
    out = pd.concat([x.rename_axis(["game_id", "pid"]) for x in (rec, rus, pas)], axis=1).fillna(0)
    return out.reset_index()


def score(season=SEASON, out=OUT, log=print) -> list:
    games = load_games().set_index("game_id")
    files = sorted(out.glob(f"{season}_w*/*.parquet"))
    sdir = out / "scores"
    sdir.mkdir(parents=True, exist_ok=True)
    todo = [f for f in files if not (sdir / f.name).exists() and f.stem in games.index and pd.notna(games.loc[f.stem, "home_score"])]
    if not todo:
        log("Nothing new to score.")
        return []
    p = M.load_pbp([season])
    act = actuals(p[p["game_id"].isin([f.stem for f in todo])]).set_index(["game_id", "pid"])
    ros = pd.read_parquet(RAW_DIR / f"roster_weekly_{season}.parquet", columns=["week", "gsis_id", "status"])
    done = []
    for f in todo:
        if not (p["game_id"] == f.stem).any():
            log(f"wait {f.stem}: final, but its play-by-play is not in data/raw yet")
            continue
        df = pd.read_parquet(f)
        week = int(games.loc[f.stem, "week"])
        act_ros = set(ros.loc[(ros["week"] == week) & (ros["status"] == "ACT"), "gsis_id"])
        rows = []
        for r in df.itertuples(index=False):
            key = (f.stem, r.pid)
            if key in act.index:
                y = float(act.loc[key, r.stat])
            elif r.pid in act_ros:
                y = 0.0
            else:
                continue                                    # did not play: excluded from every version alike
            q = np.array([getattr(r, c) for c in G.QCOLS], float)
            rows.append({"game_id": f.stem, "week": week, "team": r.team, "pid": r.pid, "name": r.name, "stat": r.stat, "version": r.version,
                         "actual": y, "mean": r.mean, "crps": float(G.qcrps(q, y)), "in80": float(G.coverage(q, y, 10, 90)),
                         "in50": float(G.coverage(q, y, 25, 75))})
        buf = io.BytesIO()
        pd.DataFrame(rows).to_parquet(buf, index=False)
        _write_once(sdir / f.name, buf.getvalue())
        done.append(f.stem)
        log(f"scored {f.stem}: {len(rows)} rows")
    return done


def load_scores(out=OUT) -> pd.DataFrame:
    fs = sorted((out / "scores").glob("*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


STAT_LABEL = {"pass_yds": "Passing yards", "rush_yds": "Rushing yards", "rec_yds": "Receiving yards", "rec": "Receptions"}


def load_archive(out=OUT, season=SEASON, preview=False) -> pd.DataFrame:
    fs = sorted((out / "preview" if preview else out).glob(f"{season}_w*/*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


def projection_table(arch: pd.DataFrame, scores: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per offensive player-stat of one game: median / mean / 80% range per version, plus the actual once scored."""
    out = arch[["team", "pid", "name", "stat"]].drop_duplicates().set_index(["team", "pid", "name", "stat"])
    for v, lab in (("v2", "v2"), ("v1", "v1"), ("base", "Baseline")):
        s = arch[arch["version"] == v].set_index(["team", "pid", "name", "stat"])
        if not len(s):
            continue
        out[f"{lab} median"] = s["q50"]
        out[f"{lab} mean"] = s["mean"]
        if v != "base":
            out[f"{lab} 10-90%"] = s["q10"].round(1).astype(str) + " - " + s["q90"].round(1).astype(str)
    out = out.reset_index()
    if scores is not None and len(scores):
        act = scores.drop_duplicates(["game_id", "pid", "stat"])
        act = act[act["game_id"].isin(arch["game_id"].unique())][["pid", "stat", "actual"]]
        out = out.merge(act.rename(columns={"actual": "Actual"}), on=["pid", "stat"], how="left")
    out["stat"] = pd.Categorical(out["stat"].map(STAT_LABEL), list(STAT_LABEL.values()))
    return out.sort_values(["team", "stat", "name"]).drop(columns="pid").rename(columns={"team": "Team", "name": "Player", "stat": "Stat"})


def summary(out=OUT) -> dict:
    """Descriptive interim numbers only; the pre-registered v2-vs-v1 test is taken once, after week 18."""
    arch = sorted(out.glob(f"{SEASON}_w*/*.json"))
    s = load_scores(out)
    res = {"archived_games": len(arch), "scored_games": int(s["game_id"].nunique()) if len(s) else 0}
    if not len(s):
        return res
    res["by_version_stat"] = s.groupby(["version", "stat"]).agg(n=("crps", "size"), crps=("crps", "mean"), mean=("mean", "mean"),
                                                                  actual=("actual", "mean"), cov80=("in80", "mean"), cov50=("in50", "mean")).reset_index()
    w = s.pivot_table(index=["game_id", "pid", "stat"], columns="version", values="crps")
    if {"v1", "v2"} <= set(w.columns):
        both = w.dropna(subset=["v1", "v2"])
        res["paired_v2_minus_v1"] = {"n": int(len(both)), "games": int(both.index.get_level_values(0).nunique()),
                                     "mean_diff": float((both["v2"] - both["v1"]).mean()) if len(both) else None}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m lab.props.weekly")
    ap.add_argument("cmd", nargs="?", default="archive", choices=["archive", "preview", "score", "summary"])
    ap.add_argument("--week", type=int)
    ap.add_argument("--season", type=int, default=SEASON)
    ap.add_argument("--sims", type=int, default=N_SIMS)
    ap.add_argument("--game", action="append", help="archive only these game_ids (repeatable)")
    args = ap.parse_args()
    if args.cmd in ("archive", "preview"):
        r = archive(args.season, args.week, n_sims=args.sims, only=args.game, preview=args.cmd == "preview")
        print(json.dumps(r, indent=2, default=str))
    elif args.cmd == "score":
        print(score(args.season))
    else:
        r = summary()
        for k, v in r.items():
            print(k, v if not isinstance(v, pd.DataFrame) else "\n" + v.round(3).to_string(index=False))
