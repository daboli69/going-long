"""With and without: how a player's teammates do when he is on the field, and when he is active or out.

Descriptive history only; nothing here is a forecast or feeds the simulation. Two views, kept apart because their data differ:
- on_field(): nflverse participation (the offensive players on the field for every play), 2022 to 2025. Large samples, no 2026 file.
- game_level(): games he did not suit up (weekly roster status inactive or injured reserve, or Out or Doubtful on the injury report) against games he was active, for a team and season (2026 and 2025 work). A few games at most.

Both are raw splits, not causal: the opponent, game script and other injuries move with who plays.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RAW_DIR

SEASONS = (2022, 2023, 2024, 2025)
OUT_STATUSES = {"Out", "Doubtful", "Injured Reserve", "IR", "Suspended"}
MIN_PLAYS = 40      # pass plays with the teammate on the field, on each side of the split
MIN_TGT = 15        # targets on each side before a yards or EPA gap is called readable
_cache: dict = {}


def _names() -> pd.Series:
    if "names" not in _cache:
        _cache["names"] = pd.read_parquet(RAW_DIR / "players.parquet").drop_duplicates("gsis_id").set_index("gsis_id")["display_name"]
    return _cache["names"]


def _pass_plays() -> pd.DataFrame:
    if "plays" in _cache:
        return _cache["plays"]
    frames = []
    for s in SEASONS:
        p = pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=["game_id", "play_id", "season", "week", "posteam", "pass_attempt", "play_type",
                                                                           "receiver_id", "passer_id", "yards_gained", "complete_pass", "epa"])
        p = p[(p["pass_attempt"] == 1) & (p["play_type"] == "pass")]
        t = pd.read_parquet(RAW_DIR / f"participation_{s}.parquet", columns=["nflverse_game_id", "play_id", "offense_players"])
        frames.append(p.merge(t, left_on=["game_id", "play_id"], right_on=["nflverse_game_id", "play_id"], how="inner"))
    d = pd.concat(frames, ignore_index=True)
    d["yds"] = np.where(d["complete_pass"] == 1, d["yards_gained"], 0.0)
    d["offense_players"] = d["offense_players"].fillna("")
    _cache["plays"] = d
    return d


def _on(d: pd.DataFrame, pid: str) -> np.ndarray:
    return d["offense_players"].str.contains(pid, regex=False).to_numpy()


def _gap(on: pd.Series, off: pd.Series) -> dict:
    """Difference of means (on minus off) with a normal standard error."""
    n1, n0 = len(on), len(off)
    if n1 < 2 or n0 < 2:
        return {"on": None, "off": None, "diff": None, "z": None}
    m1, m0 = float(on.mean()), float(off.mean())
    se = float(np.sqrt(on.var(ddof=1) / n1 + off.var(ddof=1) / n0))
    return {"on": round(m1, 3), "off": round(m0, 3), "diff": round(m1 - m0, 3), "z": round((m1 - m0) / se, 2) if se > 0 else None}


def on_field(pid: str, team_now: str | None = None) -> dict:
    """Teammate rates with `pid` on and off the field, 2022 to 2025, within the team-seasons where he played at least MIN_PLAYS pass plays."""
    d = _pass_plays()
    d = d.assign(x_on=_on(d, pid))
    spent = d[d["x_on"]].groupby(["season", "posteam"]).size()
    stints = [(int(s), t, int(n)) for (s, t), n in spent.items() if n >= MIN_PLAYS]
    if not stints:
        return {"player": str(_names().get(pid, pid)), "stints": [], "teammates": [], "team": []}
    keys = {(s, t) for s, t, _ in stints}
    g = d[[(s, t) in keys for s, t in zip(d["season"], d["posteam"])]]
    out_team = []
    for (s, t) in sorted(keys):
        x = g[(g["season"] == s) & (g["posteam"] == t)]
        row = {"season": s, "team": t, "plays_on": int(x["x_on"].sum()), "plays_off": int((~x["x_on"]).sum()),
               "pass_epa": _gap(x.loc[x["x_on"], "epa"], x.loc[~x["x_on"], "epa"]),
               "pass_epa_pp_on": None}
        out_team.append(row)
    mates = []
    cand = g.groupby("receiver_id").size()
    for yid in [i for i, n in cand.items() if n >= 25 and i != pid]:
        y_on = g["offense_players"].str.contains(yid, regex=False).to_numpy()
        gy = g[y_on]
        a, b = gy[gy["x_on"]], gy[~gy["x_on"]]
        if len(a) < MIN_PLAYS or len(b) < MIN_PLAYS:
            continue
        ta, tb = a[a["receiver_id"] == yid], b[b["receiver_id"] == yid]
        ra, rb = len(ta) / len(a), len(tb) / len(b)
        se = float(np.sqrt(ra * (1 - ra) / len(a) + rb * (1 - rb) / len(b)))
        readable = len(ta) >= MIN_TGT and len(tb) >= MIN_TGT
        mates.append({"pid": yid, "name": str(_names().get(yid, yid)), "team": str(gy["posteam"].mode().iloc[0]),
                      "plays_on": int(len(a)), "plays_off": int(len(b)), "tgt_on": int(len(ta)), "tgt_off": int(len(tb)),
                      "tgt_rate": {"on": round(ra, 3), "off": round(rb, 3), "diff": round(ra - rb, 3), "z": round((ra - rb) / se, 2) if se > 0 else None},
                      "ypt": _gap(ta["yds"], tb["yds"]) if readable else None, "epa_tgt": _gap(ta["epa"], tb["epa"]) if readable else None})
    mates.sort(key=lambda r: -(abs(r["tgt_rate"]["z"] or 0)))
    return {"player": str(_names().get(pid, pid)), "stints": [{"season": s, "team": t, "plays": n} for s, t, n in stints], "teammates": mates, "team": out_team,
            "current_team_overlap": [m["name"] for m in mates if team_now and m["team"] == team_now]}


def _roster(season: int) -> pd.DataFrame:
    key = ("roster", season)
    if key not in _cache:
        f = RAW_DIR / f"roster_weekly_{season}.parquet"
        _cache[key] = pd.read_parquet(f, columns=["gsis_id", "team", "week", "status"]) if f.exists() else pd.DataFrame(columns=["gsis_id", "team", "week", "status"])
    return _cache[key]


def _out_weeks(pid: str, team: str, season: int) -> list[int]:
    """Weeks the player did not suit up: weekly roster status other than active (inactive, injured reserve and so on), or Out or Doubtful on the injury report.

    The injury report alone misses games a player sat while listed Questionable, so the roster status leads."""
    r = _roster(season)
    r = r[(r["gsis_id"] == pid) & (r["team"] == team)]
    weeks = set(int(w) for w in r.loc[r["status"].fillna("") != "ACT", "week"])
    try:
        from . import availability
        inj = availability.load_injury_rows([season])
        x = inj[(inj["season"] == season) & (inj["team"] == team) & (inj["gsis_id"] == pid) & inj["available_at"].notna()]
        x = x.sort_values("available_at").drop_duplicates("week", keep="last")
        weeks |= set(int(w) for w in x.loc[x["report_status"].isin(OUT_STATUSES), "week"])
    except Exception:
        pass
    return sorted(weeks)


def game_level(pid: str, team: str, season: int = 2026, upto_week: int | None = None) -> dict:
    """Teammates' targets and receiving yards per game in the team's games with `pid` out against games he was active."""
    p = pd.read_parquet(RAW_DIR / f"play_by_play_{season}.parquet", columns=["week", "posteam", "pass_attempt", "play_type", "receiver_id", "yards_gained", "complete_pass"])
    p = p[(p["pass_attempt"] == 1) & (p["play_type"] == "pass") & (p["posteam"] == team)]
    weeks = sorted(int(w) for w in p["week"].unique() if upto_week is None or w < upto_week)
    out_w = [w for w in _out_weeks(pid, team, season) if w in weeks]
    res = {"player": str(_names().get(pid, pid)), "team": team, "season": season, "weeks_played_by_team": len(weeks), "weeks_out": out_w, "teammates": []}
    if len(out_w) < 1 or len(weeks) - len(out_w) < 3:
        return res
    p = p.assign(yds=np.where(p["complete_pass"] == 1, p["yards_gained"], 0.0))
    per = p.groupby(["receiver_id", "week"]).agg(tgt=("yds", "size"), yds=("yds", "sum")).reset_index()
    for yid, gy in per.groupby("receiver_id"):
        if yid == pid or gy["tgt"].sum() < 15:
            continue
        y_out = set(_out_weeks(yid, team, season))
        use = [w for w in weeks if w not in y_out]
        t = gy.set_index("week").reindex(use).fillna(0.0)
        a, b = t.loc[[w for w in use if w not in out_w]], t.loc[[w for w in use if w in out_w]]
        if len(b) < 1 or len(a) < 3:
            continue
        res["teammates"].append({"pid": yid, "name": str(_names().get(yid, yid)), "games_active": int(len(a)), "games_out": int(len(b)),
                                 "tgt_active": round(float(a["tgt"].mean()), 1), "tgt_out": round(float(b["tgt"].mean()), 1),
                                 "yds_active": round(float(a["yds"].mean()), 1), "yds_out": round(float(b["yds"].mean()), 1)})
    res["teammates"].sort(key=lambda r: -(r["tgt_out"] - r["tgt_active"]))
    return res
