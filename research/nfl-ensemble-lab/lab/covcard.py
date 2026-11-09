"""Coverage matchup card: each QB's targets and EPA by coverage and receiver position, and each defense's coverage mix and position profile.

Descriptive only. Nothing here is a forecast, a fitted model or a pick. Shrinkage constants are fixed below and were not tuned on results.
Coverage tags come from nflverse pbp_participation (2022 to 2025; there is no 2026 file, so 2026 passes carry no coverage tag).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import RAW_DIR

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "data" / "cache" / "covcard.json"
QB_SEASONS = (2022, 2023, 2024, 2025)
DEF_SEASONS = (2025, 2026)
COVS = ["COVER_1", "COVER_2", "COVER_3", "COVER_4", "OTHER"]
POS = ["WR", "TE", "RB"]
EXPLOSIVE = 20
CAP_YARDS = 40      # robust=True: per-play passing yards capped here before any mean (docs/EPNET_ROBUST_RULE.md)
CAP_EPA = 3.0       # robust=True: per-play EPA clipped to +/- this
K_QB_SHARE = 40.0   # targets of prior weight toward the league share in that coverage
K_QB_EPA = 60.0     # attempts of prior weight toward the league EPA in that coverage
K_DEF_COV = 150.0   # tagged attempts of prior weight toward the league coverage mix
K_DEF_POS = 120.0   # targets of prior weight toward the league rate at that position
PLAYS = ["game_id", "play_id", "season", "week", "posteam", "defteam", "play_type", "passer_id", "receiver_id",
         "pass_attempt", "yards_gained", "complete_pass", "epa"]


def _cov_group(c: str) -> str:
    return c if c in ("COVER_1", "COVER_2", "COVER_3", "COVER_4") else "OTHER"


def _passes(seasons, before: tuple[int, int] | None = None, robust: bool = False) -> pd.DataFrame:
    players = pd.read_parquet(RAW_DIR / "players.parquet").drop_duplicates("gsis_id").set_index("gsis_id")
    pos = players["position"].replace({"FB": "RB"})
    frames = []
    for s in seasons:
        p = pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=PLAYS)
        p = p[(p["pass_attempt"] == 1) & (p["play_type"] == "pass") & p["passer_id"].notna()].copy()
        if before is not None:  # as-of view: nothing from the given season's week onward
            p = p[(p["season"] < before[0]) | (p["week"] < before[1])]
        f = RAW_DIR / f"participation_{s}.parquet"
        if f.exists():
            t = pd.read_parquet(f, columns=["nflverse_game_id", "play_id", "defense_coverage_type", "defense_man_zone_type"])
            p = p.merge(t, left_on=["game_id", "play_id"], right_on=["nflverse_game_id", "play_id"], how="left")
        else:
            p["defense_coverage_type"], p["defense_man_zone_type"] = np.nan, np.nan
        frames.append(p)
    d = pd.concat(frames, ignore_index=True)
    d["pos"] = d["receiver_id"].map(pos)
    d["pos"] = d["pos"].where(d["pos"].isin(POS))
    d["tagged"] = d["defense_coverage_type"].notna() & (d["defense_coverage_type"] != "")
    d["cov"] = np.where(d["tagged"], d["defense_coverage_type"].map(_cov_group), None)
    d["mz"] = np.where(d["tagged"] & d["defense_man_zone_type"].isin(["MAN_COVERAGE", "ZONE_COVERAGE"]),
                       d["defense_man_zone_type"].str.replace("_COVERAGE", "", regex=False), None)
    d["explosive"] = ((d["complete_pass"] == 1) & (d["yards_gained"] >= EXPLOSIVE)).astype(int)
    d["yards"] = np.where(d["complete_pass"] == 1, d["yards_gained"], 0)
    if robust:  # explosive was set above from the raw yards, so a capped play still counts as explosive
        d["yards"] = d["yards"].clip(upper=CAP_YARDS)
        d["epa"] = d["epa"].clip(-CAP_EPA, CAP_EPA)
    return d, players


def _group_stats(x: pd.DataFrame) -> dict:
    t = x[x["pos"].notna()]
    out = {"att": int(len(x)), "epa": round(float(x["epa"].mean()), 4) if len(x) else None}
    out["tgt"] = {p: int((t["pos"] == p).sum()) for p in POS}
    out["yds"] = {p: int(t.loc[t["pos"] == p, "yards"].sum()) for p in POS}
    out["epa_tgt"] = {p: round(float(t.loc[t["pos"] == p, "epa"].sum()), 3) for p in POS}
    return out


def build(before: tuple[int, int] | None = None, robust: bool = False) -> dict:
    """`before=(season, week)` drops every pass from that week on, for a retrospective that must not see the game."""
    qb_all, players = _passes(QB_SEASONS + (2026,), before, robust)
    name = players["display_name"] if "display_name" in players else players.index.to_series()
    qb_tag = qb_all[qb_all["tagged"] & qb_all["season"].isin(QB_SEASONS)]

    league = {"cov": {}, "mz": {}}
    for c in COVS:
        x = qb_tag[qb_tag["cov"] == c]
        league["cov"][c] = _group_stats(x)
    for m in ("MAN", "ZONE"):
        league["mz"][m] = _group_stats(qb_tag[qb_tag["mz"] == m])
    league["all"] = _group_stats(qb_tag)

    qbs = {}
    for qid, x in qb_all.groupby("passer_id"):
        xt = x[x["tagged"] & x["season"].isin(QB_SEASONS)]
        if len(xt) < 20 and not (x["season"] == 2026).any():
            continue
        last = x.sort_values(["season", "week"]).iloc[-1]
        qbs[qid] = {"name": str(name.get(qid, qid)), "team": last["posteam"], "last_season": int(last["season"]), "last_week": int(last["week"]),
                    "att_tagged": int(len(xt)), "att_2026_untagged": int((x["season"] == 2026).sum()),
                    "by_season": {int(s): int(n) for s, n in xt.groupby("season").size().items()},
                    "cov": {c: _group_stats(xt[xt["cov"] == c]) for c in COVS},
                    "mz": {m: _group_stats(xt[xt["mz"] == m]) for m in ("MAN", "ZONE")},
                    "all": _group_stats(xt)}

    dp, _ = _passes(DEF_SEASONS, before, robust)
    dtag = dp[dp["tagged"] & (dp["season"] == 2025)]
    def_league_cov = dtag["cov"].value_counts(normalize=True).to_dict()
    def_league_mz = dtag["mz"].value_counts(normalize=True).to_dict()
    dpos = dp[dp["pos"].notna()]
    league_pos = {p: {"share": float((dpos["pos"] == p).mean()), "ypt": float(dpos.loc[dpos["pos"] == p, "yards"].mean()),
                      "cmp": float(dpos.loc[dpos["pos"] == p, "complete_pass"].mean()), "expl": float(dpos.loc[dpos["pos"] == p, "explosive"].mean()),
                      "epa": float(dpos.loc[dpos["pos"] == p, "epa"].mean())} for p in POS}
    defs = {}
    for team, x in dp.groupby("defteam"):
        xt = dtag[dtag["defteam"] == team]
        cov_n = {c: int((xt["cov"] == c).sum()) for c in COVS}
        t = x[x["pos"].notna()]
        pos = {}
        for p in POS:
            y = t[t["pos"] == p]
            pos[p] = {"tgt": int(len(y)), "yds": int(y["yards"].sum()), "cmp": int(y["complete_pass"].sum()), "expl": int(y["explosive"].sum()),
                      "epa": round(float(y["epa"].sum()), 3)}
        defs[team] = {"cov_n": cov_n, "tagged": int(len(xt)), "man_n": int((xt["mz"] == "MAN").sum()), "mz_n": int(xt["mz"].notna().sum()),
                      "pos": pos, "tgt_known": int(len(t)), "att_2025": int((x["season"] == 2025).sum()), "att_2026": int((x["season"] == 2026).sum())}
    return {"params": {"K_QB_SHARE": K_QB_SHARE, "K_QB_EPA": K_QB_EPA, "K_DEF_COV": K_DEF_COV, "K_DEF_POS": K_DEF_POS, "explosive_yards": EXPLOSIVE, "robust": robust,
                       "qb_seasons": list(QB_SEASONS), "def_position_seasons": list(DEF_SEASONS), "def_coverage_season": 2025},
            "league": league, "qbs": qbs, "defs": defs,
            "def_league": {"cov": def_league_cov, "man": def_league_mz.get("MAN", 0.0), "pos": league_pos}}


def starters() -> dict:
    """team -> (gsis id, name) of the QB with the most dropbacks in the team's latest 2026 game (a default; check the injury report)."""
    p = pd.read_parquet(RAW_DIR / "play_by_play_2026.parquet", columns=["posteam", "week", "passer_id", "passer", "pass_attempt"])
    p = p[(p["pass_attempt"] == 1) & p["passer_id"].notna()]
    last = p.groupby("posteam")["week"].max()
    out = {}
    for team, wk in last.items():
        x = p[(p["posteam"] == team) & (p["week"] == wk)]
        top = x["passer_id"].value_counts().index[0]
        out[team] = (top, x.loc[x["passer_id"] == top, "passer"].iloc[0])
    return out


def main():
    d = build()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(d), encoding="utf-8")
    print("qbs", len(d["qbs"]), "defs", len(d["defs"]), "->", OUT_JSON)


if __name__ == "__main__":
    main()
