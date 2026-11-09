"""Week 9 Sunday coverage retro. Rule: docs/COVERAGE_RETRO_W9.md (committed before this ran).

    .venv\\Scripts\\python.exe scripts\\covcard_retro.py

Writes docs/coverage_retro_w9.json. Read-only: no network, no freezes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import covcard as cc  # noqa: E402
from lab import covgame as cg  # noqa: E402
from lab.config import RAW_DIR  # noqa: E402
from lab.ingest import normalize_team  # noqa: E402

SEASON, WEEK, SUNDAY, SEED, PERMS = 2026, 9, "2026-11-08", 20261109, 10000
ROBUST = "--robust" in sys.argv  # sensitivity run with capped play values; writes a separate json
POS = cc.POS


def spearman(x, y) -> float:
    return float(pd.Series(x).rank().corr(pd.Series(y).rank()))


def perm_p(x, y, rng) -> float:
    obs = abs(spearman(x, y))
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    c = [abs(np.corrcoef(rx, rng.permutation(ry))[0, 1]) for _ in range(PERMS)]
    return float((np.sum(np.array(c) >= obs - 1e-12) + 1) / (PERMS + 1))


def summarize(x, y, rng) -> dict:
    x, y = np.asarray(x, float), np.asarray(y, float)
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    nz = (x != 0) & (y != 0)
    return {"n": int(len(x)), "spearman": round(spearman(x, y), 3), "perm_p": round(perm_p(x, y, rng), 4),
            "sign_agree": round(float((np.sign(x[nz]) == np.sign(y[nz])).mean()), 3) if nz.any() else None}


def main():
    rng = np.random.default_rng(SEED)
    games = pd.read_csv(RAW_DIR / "games.csv")
    g = games[(games["season"] == SEASON) & (games["week"] == WEEK) & (games["gameday"] == SUNDAY) & games["home_score"].notna()]
    gids = [f"{SEASON}_{WEEK:02d}_{normalize_team(r.away_team)}_{normalize_team(r.home_team)}" for r in g.itertuples()]

    cols = ["game_id", "week", "posteam", "defteam", "passer_id", "receiver_id", "receiver", "pass_attempt", "play_type", "yards_gained", "complete_pass", "epa"]
    p = pd.read_parquet(RAW_DIR / "play_by_play_2026.parquet", columns=cols)
    p = p[(p["pass_attempt"] == 1) & (p["play_type"] == "pass")]
    pos_of = pd.read_parquet(RAW_DIR / "players.parquet").drop_duplicates("gsis_id").set_index("gsis_id")["position"].replace({"FB": "RB"})
    p = p.assign(pos=p["receiver_id"].map(pos_of), yds=np.where(p["complete_pass"] == 1, p["yards_gained"], 0))
    prior = p[p["week"] < WEEK]
    played = p[p["week"] == WEEK]

    data = cc.build(before=(SEASON, WEEK), robust=ROBUST)
    rec_rows, pos_rows, qb_rows = [], [], []
    for gid in gids:
        _, _, away, home = gid.split("_")
        for team, opp in ((away, home), (home, away)):
            x = played[(played["posteam"] == team) & (played["defteam"] == opp)]
            if x.empty:
                continue
            qid = x["passer_id"].value_counts().index[0]
            rec_rows.append((gid, team, qid))
    qbmap = {}
    for gid, team, qid in rec_rows:
        qbmap.setdefault(gid, {})[team] = qid

    for gid in gids:
        card = cg.card(gid, qbs=qbmap.get(gid, {}), data=data)
        if card is None:
            continue
        for s in card["sides"]:
            team, opp = s["qb_team"], s["defense"]
            x = played[(played["posteam"] == team) & (played["defteam"] == opp)]
            if x.empty:
                continue
            qid = qbmap[gid][team]
            q_all = prior[(prior["posteam"] == team) & (prior["passer_id"] == qid)]
            # 1. receivers
            for r in s["receivers"]:
                if r.get("edge") is None:
                    continue
                mine_week = x[x["receiver_id"] == r["pid"]]
                mine_prior = prior[(prior["posteam"] == team) & (prior["receiver_id"] == r["pid"])]
                team_games = prior[prior["posteam"] == team]["week"].nunique()
                base = float(mine_prior["yds"].sum()) / max(team_games, 1)
                rec_rows_item = {"gid": gid, "team": team, "vs": opp, "name": r["name"], "pos": r["pos"], "edge": r["edge"], "man_yprr": r["man_yprr"], "zone_yprr": r["zone_yprr"],
                                 "yards": float(mine_week["yds"].sum()), "targets": int(len(mine_week)), "baseline_yards": round(base, 1),
                                 "diff": float(mine_week["yds"].sum()) - base, "matched": bool(len(mine_prior) or len(mine_week))}
                pos_rows.append(("rec", rec_rows_item))
            # 2. position share
            if s.get("compare"):
                tx = x[x["pos"].isin(POS)]
                for pp in POS:
                    act = float((tx["pos"] == pp).mean()) if len(tx) else np.nan
                    pos_rows.append(("pos", {"gid": gid, "team": team, "vs": opp, "pos": pp, "pred": s["compare"]["expected"][pp] - s["compare"]["usual"][pp],
                                             "actual": act - s["compare"]["usual"][pp], "targets": int(len(tx))}))
                # 3. QB EPA
                if len(x[x["passer_id"] == qid]):
                    qb_rows.append({"gid": gid, "team": team, "vs": opp, "qb": s["qb"].get("name"), "passes": int((x["passer_id"] == qid).sum()),
                                    "pred": s["compare"]["expected_epa"] - s["compare"]["usual_epa"],
                                    "actual": float(x.loc[x["passer_id"] == qid, "epa"].mean()) - s["compare"]["usual_epa"],
                                    "expected_epa": s["compare"]["expected_epa"], "usual_epa": s["compare"]["usual_epa"]})

    rec = pd.DataFrame([r for k, r in pos_rows if k == "rec"])
    pos = pd.DataFrame([r for k, r in pos_rows if k == "pos"])
    qb = pd.DataFrame(qb_rows)
    out = {"games": len(gids), "seed": SEED, "perms": PERMS,
           "receivers": summarize(rec["edge"], rec["diff"], rng) if len(rec) else None,
           "position_share": summarize(pos["pred"], pos["actual"], rng) if len(pos) else None,
           "qb_epa": summarize(qb["pred"], qb["actual"], rng) if len(qb) else None}
    # Added after the first run (not in the rule): the three positions of one team-game sum to 1, so shuffle whole team-games, and split by position.
    if len(pos):
        pos = pos.reset_index(drop=True)
        groups = [g.index.to_numpy() for _, g in pos.groupby(["gid", "team"]) if len(g) == 3]
        px, py = pos["pred"].to_numpy(), pos["actual"].to_numpy()
        rx = pd.Series(px).rank().to_numpy()
        obs = abs(spearman(px, py))
        hits = 0
        for _ in range(PERMS):
            order = rng.permutation(len(groups))
            ys = py.copy()
            for g_idx, o in zip(groups, order):
                ys[g_idx] = py[groups[o]]
            hits += abs(np.corrcoef(rx, pd.Series(ys).rank().to_numpy())[0, 1]) >= obs - 1e-12
        out["position_share_block"] = {"team_games": len(groups), "perm_p": round((hits + 1) / (PERMS + 1), 4)}
        out["position_share_by_pos"] = {pp: {"n": int((pos["pos"] == pp).sum()), "spearman": round(spearman(pos.loc[pos["pos"] == pp, "pred"], pos.loc[pos["pos"] == pp, "actual"]), 3),
                                             "mean_pred": round(float(pos.loc[pos["pos"] == pp, "pred"].mean()), 4), "mean_actual": round(float(pos.loc[pos["pos"] == pp, "actual"].mean()), 4)} for pp in POS}
        out["position_rows"] = pos.round(4).to_dict("records")
    out["receiver_rows"] = rec.sort_values("edge", ascending=False).round(3).to_dict("records")
    out["qb_rows"] = qb.round(3).to_dict("records")
    (ROOT / "docs" / ("coverage_retro_w9_robust.json" if ROBUST else "coverage_retro_w9.json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("games", "receivers", "position_share", "position_share_block", "position_share_by_pos", "qb_epa") if k in out}, indent=1))


if __name__ == "__main__":
    main()
