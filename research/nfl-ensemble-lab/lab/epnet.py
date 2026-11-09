"""Approximation of nflfastR PR 618: score values net of the opponent's next possession. Rule: docs/EPNET_ROBUST_RULE.md.

Descriptive only. Keeps the published next-score probabilities and swaps the point values 7/3/2 for 6+xp-V, 3-V and 2+W, with V measured
from the first scrimmage play after kickoffs in the local data. Not the PR's model-based calculation; it is not wired into any forecast.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RAW_DIR

BINS = [-1, 60, 180, 420, 900, 10_000]
FREE_KICK_SPOT = 61.0
YARD_VALUE = 0.05
V_SEASONS = tuple(range(2016, 2027))
COLS = ["game_id", "play_id", "season", "week", "posteam", "defteam", "passer_id", "play_type", "pass_attempt", "kickoff_attempt", "down", "half_seconds_remaining",
        "touchdown", "field_goal_result", "safety", "td_prob", "fg_prob", "safety_prob", "opp_td_prob", "opp_fg_prob", "opp_safety_prob", "ep", "epa"]


def kickoff_spot(season: int) -> float:
    return 80.0 if season <= 2015 else 75.0 if season <= 2023 else 70.0 if season == 2024 else 69.0


def xp_value(season: int) -> float:
    return 0.99 if season <= 2014 else 0.94 if season <= 2022 else 0.96


def _load(season: int) -> pd.DataFrame:
    d = pd.read_parquet(RAW_DIR / f"play_by_play_{season}.parquet", columns=[c for c in COLS if c != "season"])
    d["season"] = season
    return d.sort_values(["game_id", "play_id"]).reset_index(drop=True)


def v_table() -> pd.DataFrame:
    """Mean ep of the first scrimmage play after a kickoff, by kickoff spot and seconds left in the half."""
    rows = []
    for s in V_SEASONS:
        d = _load(s)
        nxt_ep = d["ep"].shift(-1)
        same = d["game_id"] == d["game_id"].shift(-1)
        k = d[(d["kickoff_attempt"] == 1) & same & (d["half_seconds_remaining"] > 0)].copy()
        k["first_ep"] = nxt_ep[k.index]
        k["first_down"] = d["down"].shift(-1)[k.index]
        k = k[k["first_down"].notna() & k["first_ep"].notna()]
        rows.append(pd.DataFrame({"spot": kickoff_spot(s), "bin": pd.cut(k["half_seconds_remaining"], BINS, labels=False), "v": k["first_ep"]}))
    t = pd.concat(rows).groupby(["spot", "bin"])["v"].agg(["mean", "size"]).reset_index()
    return t.rename(columns={"mean": "V", "size": "n"})


def apply(d: pd.DataFrame, vt: pd.DataFrame) -> pd.DataFrame:
    """Adds ep_net, epa_net and the per-play V, W to one season of play-by-play."""
    s = int(d["season"].iloc[0])
    spot, xp = kickoff_spot(s), xp_value(s)
    lookup = vt[vt["spot"] == spot].set_index("bin")["V"]
    b = pd.cut(d["half_seconds_remaining"], BINS, labels=False)
    V = b.map(lookup).astype(float).fillna(lookup.mean())
    V = V.where(d["half_seconds_remaining"] > 0, 0.0)
    W = np.where(V > 0, V + YARD_VALUE * (spot - FREE_KICK_SPOT), 0.0)
    td, fg, sf = 6 + xp - V, 3 - V, 2 + W
    p = lambda c: d[c].fillna(0.0)
    d = d.assign(V=V, W=W)
    d["ep_old_recon"] = 7 * p("td_prob") + 3 * p("fg_prob") + 2 * p("safety_prob") - 7 * p("opp_td_prob") - 3 * p("opp_fg_prob") - 2 * p("opp_safety_prob")
    d["ep_net"] = td * p("td_prob") + fg * p("fg_prob") + sf * p("safety_prob") - td * p("opp_td_prob") - fg * p("opp_fg_prob") - sf * p("opp_safety_prob")
    after_old = d["ep"] + d["epa"]
    nxt = d["ep"].shift(-1)
    same = d["game_id"] == d["game_id"].shift(-1)
    nxt_net = d["ep_net"].shift(-1)
    keep = (d["play_type"].isin(["extra_point", "two_point_attempt"])) | after_old.isna()
    after = after_old.copy()
    flow = same & ((after_old - nxt).abs() < 1e-6)
    flip = same & ((after_old + nxt).abs() < 1e-6) & ~flow
    after = np.where(flow, nxt_net, np.where(flip, -nxt_net, after_old))
    a = pd.Series(after, index=d.index)
    scored = ~flow & ~flip
    sign = np.sign(after_old)
    a = a.where(~(scored & ((after_old.abs() - 7).abs() < 1e-6)), sign * td)
    a = a.where(~(scored & ((after_old.abs() - 3).abs() < 1e-6) & (d["field_goal_result"] == "made")), sign * fg)
    a = a.where(~(scored & ((after_old.abs() - 2).abs() < 1e-6) & (d["safety"] == 1)), sign * sf)
    d["after_net"] = a.where(~keep, after_old)
    d["epa_net"] = (d["after_net"] - d["ep_net"]).where(~keep, d["epa"])
    d["td_play"] = scored & ((after_old.abs() - 7).abs() < 1e-6)
    d["fg_play"] = scored & ((after_old.abs() - 3).abs() < 1e-6) & (d["field_goal_result"] == "made")
    return d


def season_net(season: int, vt: pd.DataFrame | None = None) -> pd.DataFrame:
    return apply(_load(season), vt if vt is not None else v_table())
