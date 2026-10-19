"""Frozen <=2021 simulator tables; 2022 development or unplayed 2026 forecasts.

No lab.props.evaluate run is invoked. Full-game market anchors come exclusively
from the authorized local GOING archive; missing benchmarks stay missing.
"""
from __future__ import annotations

import argparse
import json
import time
import zlib

import joblib
import numpy as np
import pandas as pd

from ...archive10 import ARCHIVE, temporal
from ...config import RAW_DIR
from ...data_pipeline import FEATURE_STORE
from .. import game as G, models as M, players as PL, sim as S
from ..independent import IndependentAnchor
from .data import OUT


def local_game_lines(games, now):
    """Last timestamp-eligible full-game quote per book; median line across books.

    Matching requires teams AND kickoff within 15 minutes. Periods are never used
    as full-game lines. No fallback to nfldata closing lines or live odds services.
    """
    quotes = []
    for path in (ARCHIVE / "market").glob("going_*.json"):
        d = json.loads(path.read_text(encoding="utf-8"))
        av = d.get("available_at")
        if not av or pd.Timestamp(av) > now:
            continue
        for r in d["content"]:
            if r.get("period") != "FULL" or r.get("in_play"):
                continue
            if not temporal(r.get("quote_time"), av, r.get("kickoff"))["pregame_verified"]:
                continue
            if r["market"] == "spreads" and r["side"] == "home":
                value, stat = -float(r["point"]), "margin"
            elif r["market"] == "totals" and str(r["side"]).lower() == "over":
                value, stat = float(r["point"]), "total"
            else:
                continue
            quotes.append(r | {"value": value, "stat": stat, "available_at": av})
    q = pd.DataFrame(quotes)
    result = {}
    if q.empty:
        return result
    for g in games.itertuples(index=False):
        d = q[(q["home"] == g.home_team) & (q["away"] == g.away_team)].copy()
        if d.empty:
            continue
        d = d[(pd.to_datetime(d["kickoff"], utc=True) - g.kickoff_utc).abs() <= pd.Timedelta(minutes=15)]
        d = d.sort_values("quote_time").groupby(["book", "stat"]).tail(1)
        values = d.groupby("stat")["value"].median().to_dict()
        if {"margin", "total"} <= values.keys():
            result[g.game_id] = values | {"quote_time": d["quote_time"].max(), "books": sorted(d["book"].unique())}
    return result


def tables(log=print):
    path = OUT / "simulator_tables_through_2021.joblib"
    if path.exists():
        result = joblib.load(path)
        if result.get("phase10_train_max_season") != 2021:
            raise ValueError("Unsafe structural cache")
        return result
    log("fit simulator submodels on 2016–2021 only")
    result = M.fit(range(2016, 2022))
    S.calibrate_clock(result)
    result["phase10_train_max_season"] = 2021
    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump(result, path)
    return result


def run(season=2022, week=None, n_sims=1000, limit=None, log=print, deadline=None):
    if season not in (2022, 2026):
        raise ValueError("Only 2022 development and 2026 prospective allowed")
    frame = pd.read_parquet(OUT / "features.parquet")
    fs = pd.read_parquet(FEATURE_STORE)
    now = pd.Timestamp.now(tz="UTC")
    games = fs[(fs["season"] == season) & fs["game_type"].eq("REG")].sort_values(["week", "game_id"])
    if week is not None:
        games = games[games["week"] == week]
    if season == 2026:
        games = games[(games["kickoff_utc"] > now) & ~games["completed"]]
    if limit:
        games = games.head(limit)
    markets = local_game_lines(games, now)
    # In 2022 the authorized GOING source has no quotes. No closing-line fallback.
    table = tables(log)
    p = M.load_pbp([2021, 2022] + ([2026] if season == 2026 else []))
    p = p[(p["season"] < 2026) | (p["week"] < (week or 1))]
    panel = PL.panel(p, table)
    del p
    anchor = IndependentAnchor().fit(fs)
    directory = OUT / ("structural_dev2022" if season == 2022 else "structural_prospective2026")
    directory.mkdir(parents=True, exist_ok=True)
    errors = []
    for g in games.itertuples(index=False):
        if deadline and pd.Timestamp.now(tz="UTC") >= pd.Timestamp(deadline):
            log("deadline reached; no further structural games started")
            break
        if season == 2026 and g.kickoff_utc <= pd.Timestamp.now(tz="UTC"):
            continue
        path = directory / f"{g.game_id}.parquet"
        if path.exists():
            continue
        started = time.perf_counter()
        try:
            candidate = frame[frame["game_id"] == g.game_id]
            a = PL.asof(panel, season, g.week)
            sides = [g.home_team, g.away_team]
            avail, hist, qbs = {}, {}, {}
            for team in sides:
                c = candidate[candidate["team"] == team]
                avail[team] = c[["pid", "position"]]
                qbs[team] = c["projected_qb"].dropna().iloc[0] if c["projected_qb"].notna().any() else None
                tp = panel[panel["posteam"] == team]
                hist[team] = (tp[(tp["season"] == season) & (tp["week"] < g.week)].drop_duplicates("game_id"),
                              tp[tp["season"] == season - 1].drop_duplicates("game_id"))
            teams, players, cols, info = G.build(a, avail, hist, g.week, qbs, sides)
            if any(not len(t["recv_cols"]) or not len(t["rush_cols"]) for t in teams):
                raise ValueError("Missing eligible receiver/rusher pool")
            pred = anchor.predict(fs[fs["game_id"] == g.game_id]).iloc[0]
            modes = {"sim_independent": [pred.home_points, pred.away_points]}
            if g.game_id in markets:
                line = markets[g.game_id]
                modes["simulator_v1"] = [(line["total"] + line["margin"]) / 2, (line["total"] - line["margin"]) / 2]
            rows, game_rows = [], []
            eligible = G.eligible(info, a)
            eligible += [(t, pid, "pass_tds") for t, pid, k in eligible if k == "pass_yds"]
            eligible += [(t, pid, "anytime_td") for t, pid in sorted({(t, pid) for t, pid, k in eligible if k in ("rec", "rush_yds")})]
            for mode, points in modes.items():
                seed = zlib.crc32(g.game_id.encode())
                rng = np.random.default_rng(seed)
                # Preserve v1's original calibration for the market benchmark.
                efficiency, calibrated = (S.calibrate if mode == "simulator_v1" else S.calibrate_v2)(table, teams, players, points, rng)
                result = S.simulate(table, teams, players, n_sims, efficiency, rng, record_td=True)
                for team, pid, stat in eligible:
                    samples = result["stats"][stat][:, cols[pid]]
                    rows.append({"game_id": g.game_id, "season": season, "week": g.week, "team": team, "pid": pid,
                        "stat": stat, "member": mode, "mean": float(samples.mean()),
                        "q10": float(np.quantile(samples, .1)), "q50": float(np.quantile(samples, .5)), "q90": float(np.quantile(samples, .9)),
                        "first_td": float((result["first_td_col"] == cols[pid]).mean()),
                        "anytime_td": float(result["stats"]["anytime_td"][:, cols[pid]].mean()),
                        "samples": samples.astype(np.float32).tolist()})
                # Every simulated scorer stays in the categorical first-TD set,
                # including low-share players outside statistical eligibility.
                first = {pid: float((result["first_td_col"] == col).mean()) for pid, col in cols.items()}
                no_td = float((result["first_td_col"] == -1).mean())
                points_array = result["points"]
                margin, total = points_array[:, 0] - points_array[:, 1], points_array.sum(1)
                game_rows.append({"member": mode, "anchor_points": list(map(float, points)), "calibrated_points": list(map(float, calibrated)),
                    "margin_mean": float(margin.mean()), "margin_q10_50_90": np.quantile(margin, [.1, .5, .9]).tolist(),
                    "total_mean": float(total.mean()), "total_q10_50_90": np.quantile(total, [.1, .5, .9]).tolist(),
                    "margin_samples": margin.tolist(), "total_samples": total.tolist(), "first_td": first, "no_offensive_td": no_td})
            pd.DataFrame(rows).to_parquet(path, index=False)
            meta = {"game_id": g.game_id, "season": season, "week": g.week, "n_sims": n_sims,
                    "generated_at": pd.Timestamp.now(tz="UTC").isoformat(), "kickoff": g.kickoff_utc.isoformat(),
                    "training_max_season": 2021, "market_available": g.game_id in markets, "games": game_rows,
                    "td_definition": "first offensive rushing/receiving TD; passing/defensive/special-teams TDs excluded"}
            with path.with_suffix(".json").open("x", encoding="utf-8") as fh:
                json.dump(meta, fh)
            log(f"{g.game_id}: {len(rows)} structural rows; {time.perf_counter() - started:.1f}s")
        except Exception as exc:
            errors.append({"game_id": g.game_id, "error": repr(exc)})
            log(f"FAILED {g.game_id}: {exc}; skipped")
    (directory / "errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    return {"files": len(list(directory.glob("*.parquet"))), "errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2022)
    parser.add_argument("--week", type=int)
    parser.add_argument("--sims", type=int, default=1000)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--deadline")
    a = parser.parse_args()
    print(json.dumps(run(a.season, a.week, a.sims, a.limit, deadline=a.deadline), indent=2))
