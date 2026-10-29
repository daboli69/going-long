"""Kalshi player props study runner (docs/PROPS_KALSHI_PREREGISTRATION.md, steps 1-5, commit 31af0b08). All local.

  python scripts/props_kalshi.py pilot     # 2025 weeks 1-4, arm A only, pseudo-ladders -> power (commit before replay)
  python scripts/props_kalshi.py pull      # Kalshi candles (+ trades for liquid markets), quotes at T-90 and close, environments
  python scripts/props_kalshi.py replay    # as-of simulator replay, arms A and K, scored weeks (resumable per week)
  python scripts/props_kalshi.py score     # one look: families G, S, C + descriptive; writes reports/props_kalshi/results.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import homewin_deep as h  # noqa: E402
from lab import homewin_eval as ev  # noqa: E402
from lab import kalshi as K  # noqa: E402
from lab import props_kalshi as pk  # noqa: E402
from lab.props import game as G  # noqa: E402
from lab.props import weekly as W  # noqa: E402

PSEUDO = {"pass_yds": [200, 225, 250, 275, 300], "rush_yds": [40, 60, 80, 100], "rec_yds": [40, 60, 80, 100], "rec": [3, 4, 5, 6]}
EMPTY_INJ = pd.DataFrame(columns=["team", "week", "gsis_id", "report_status"])


def log(m):
    print(m, flush=True)


def _write(name, obj):
    pk.REPORT.mkdir(parents=True, exist_ok=True)
    body = json.dumps(obj, indent=1, default=str)
    (pk.REPORT / name).write_bytes(body.encode("utf-8"))
    log(f"Wrote reports/props_kalshi/{name} sha256 {hashlib.sha256(body.encode()).hexdigest()}")


def actual_stats(season: int) -> pd.DataFrame:
    from lab.props import models as M
    p = M.load_pbp([season])
    reg = W.actuals(p)
    # full game incl. overtime, same definitions otherwise (Kalshi settles on the game)
    s = p[p["play_type"].isin(["pass", "run"]) & (p["two_point_attempt"] == 0) & (p["qb_kneel"] == 0) & (p["qb_spike"] == 0)]
    tg = s[(s["play_type"] == "pass") & (s["sack"] == 0) & s["receiver_player_id"].notna()]
    rec = tg.groupby(["game_id", "receiver_player_id"]).agg(rec_yds=("receiving_yards", "sum"), rec=("complete_pass", "sum"))
    rus = s[(s["play_type"] == "run") & s["rusher_player_id"].notna()].groupby(["game_id", "rusher_player_id"]).agg(rush_yds=("rushing_yards", "sum"))
    pas = s[s["play_type"] == "pass"].groupby(["game_id", "passer_player_id"]).agg(pass_yds=("passing_yards", "sum"))
    full = pd.concat([x.rename_axis(["game_id", "pid"]) for x in (rec, rus, pas)], axis=1).fillna(0).reset_index()
    long = lambda d, tag: d.melt(id_vars=["game_id", "pid"], value_vars=list(PSEUDO), var_name="stat", value_name=tag)  # noqa: E731
    return long(reg, "actual_reg").merge(long(full, "actual_full"), on=["game_id", "pid", "stat"], how="outer")


def ladder_crps(probs: np.ndarray, yes: np.ndarray) -> float:
    return float(((probs - yes) ** 2).sum())


def pilot(args):
    gcsv = W.load_games()
    R = pk.Replayer(2025, gcsv)
    parts = []
    for w in range(1, 5):
        wk = gcsv[(gcsv["season"] == 2025) & (gcsv["week"] == w)].sort_values("game_id")
        envs = {r.game_id: {"A": ((r.total_line + r.spread_line) / 2, (r.total_line - r.spread_line) / 2)} for r in wk.itertuples()}
        parts.append(R.week(w, wk, envs, EMPTY_INJ, log=log))
        log(f"  pilot week {w} done")
    sim = pd.concat(parts, ignore_index=True)
    sim.to_parquet(pk.CACHE / "pilot_sim.parquet")
    act = actual_stats(2025).rename(columns={"game_id": "gid"})
    rows = []
    for (gid, pid, stat), d in sim.groupby(["gid", "pid", "stat"]):
        a = act[(act["gid"] == gid) & (act["pid"] == pid) & (act["stat"] == stat)]
        if a.empty or {"v2", "base"} - set(d["version"]):
            continue
        y = float(a["actual_full"].iloc[0])
        ks = np.array(PSEUDO[stat], float)
        yes = (y >= ks).astype(float)
        sc = {}
        for v in ("v2", "base"):
            q = d.loc[d["version"] == v, G.QCOLS].to_numpy(float)[0]
            sc[v] = ladder_crps(np.array([pk.p_at_least(q, k) for k in ks]), yes)
        rows.append({"gid": gid, "week": int(d["week"].iloc[0]), "stat": stat, "v2": sc["v2"], "base": sc["base"]})
    x = pd.DataFrame(rows)
    x["d"] = x["v2"] - x["base"]
    wk = x.groupby("week")["d"].mean()
    per_week_pilot = len(x) / x["week"].nunique()
    step0 = json.loads((pk.LAB_ROOT / "reports" / "kalshi" / "props_step0.json").read_text(encoding="utf-8"))["series"]
    games_per_week = 14.0
    scored_per_week = games_per_week * sum(step0[s]["est_liquid_markets_per_game"] / 3 for s in pk.LADDERS)
    sd_w = float(wk.std(ddof=1)) * np.sqrt(per_week_pilot / scored_per_week)  # rescale to the scored ladder count
    alpha = 0.05 / 3
    z = norm.ppf(1 - alpha / 2) + norm.ppf(0.8)
    sesoi = 0.02 * float(x["base"].mean())
    weeks_scored = int(_scored_weeks(gcsv).shape[0])
    res = {"prereg": pk.PREREG, "pilot_ladders": int(len(x)), "pilot_weeks": 4, "pilot_mean_base_crps": float(x["base"].mean()),
           "pilot_mean_v2_crps": float(x["v2"].mean()), "pilot_ladders_per_week": per_week_pilot,
           "expected_scored_ladders_per_week": scored_per_week, "sd_week_mean_rescaled": sd_w, "sesoi": sesoi,
           "scored_weeks": weeks_scored, "history_mde": float(z * sd_w / np.sqrt(weeks_scored)),
           "N_weeks_for_sesoi": int(np.ceil((z * sd_w / sesoi) ** 2))}
    _write("power.json", res)
    log(json.dumps({k: res[k] for k in ("pilot_ladders", "sesoi", "history_mde", "scored_weeks", "N_weeks_for_sesoi")}))


def _scored_weeks(gcsv) -> pd.DataFrame:
    g = gcsv[gcsv["home_score"].notna()]
    g = g[((g["season"] == 2025) & (g["week"] >= 5)) | (g["season"] == 2026)]
    return g[["season", "week"]].drop_duplicates().sort_values(["season", "week"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["pilot", "pull", "replay", "score"])
    args = ap.parse_args()
    if args.command == "pilot":
        return pilot(args)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import props_kalshi_stages as st  # noqa: E402  (pull/replay/score live beside this file)
    {"pull": st.pull, "replay": st.replay, "score": st.score}[args.command](args)


if __name__ == "__main__":
    main()
