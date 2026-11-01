"""Touchdown card for one player in one game: the reasons behind his anytime-touchdown chance, built from raw play-by-play.

Everything is as of before the game's week, over the team's last seven games of the season (fewer early on). Sections:
  script       favorite or underdog, total, implied points, pace rank
  profile      red-zone role and claim, touches, goal-line work, target share, touchdown rate, team red-zone trips and conversion
  cheat code   expected touchdowns from where his touches happen (goal line, red zone, fringe, open field) against touchdowns scored
  role tax     his per-game numbers against what the opposing defense allows to the same role (lead back, WR1 and so on), with ranks
  leaks        positions and roles the defense has been giving touchdowns to
  opportunity  touchdowns the defense allowed by position game by game, snap share, games since his last touchdown
Expected touchdowns use league touchdown rates for each kind of touch and zone from the 2022 to 2025 regular seasons.
Local files only, read-only, deterministic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from . import usage as U
from .config import RAW_DIR
from .ingest import normalize_team

WINDOW = 7            # the defense's record: its last seven games
PLAYER_WINDOW = 5     # a player and his team: the last five games
LEAGUE_SEASONS = (2022, 2023, 2024, 2025)
FIRST_SEASON = min(LEAGUE_SEASONS)
ZONES = (("gl", "Goal line (in 5)"), ("rz", "Red zone (6 to 20)"), ("fringe", "Fringe (21 to 40)"), ("open", "Open field"))
PLAY_COLS = ["game_id", "season", "week", "season_type", "posteam", "defteam", "play_type", "yardline_100", "rusher_player_id", "receiver_player_id",
             "rush_touchdown", "pass_touchdown", "two_point_attempt", "qb_kneel", "rushing_yards", "receiving_yards", "complete_pass", "fixed_drive",
             "fixed_drive_result", "sack"]
POS_LABEL = {"RB": "running backs", "WR": "wide receivers", "TE": "tight ends", "QB": "quarterbacks (rushing)"}
ROLES = {"RB": ["Lead back", "Second back", "Third back"], "WR": ["WR1", "WR2", "WR3"], "TE": ["TE1", "TE2"], "QB": ["Quarterback"]}
ROLE_METRICS = [("carries", "Rush att"), ("rush_yds", "Rush yds"), ("rush_td", "Rush TD"), ("targets", "Targets"), ("rec_yds", "Rec yds"),
                ("rec_td", "Rec TD"), ("rz_touches", "RZ touches")]

_CACHE: dict = {}


def _stamp() -> tuple:
    return tuple((RAW_DIR / f"play_by_play_{s}.parquet").stat().st_mtime_ns for s in range(FIRST_SEASON, D.SEASON + 1) if (RAW_DIR / f"play_by_play_{s}.parquet").exists())


def _load():
    """(touches, drives): one row per rush or target, and one per offensive drive with its red-zone flag and result."""
    key = _stamp()
    if _CACHE.get("key") == key:
        return _CACHE["tables"]
    parts = [pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=PLAY_COLS) for s in range(FIRST_SEASON, D.SEASON + 1)
             if (RAW_DIR / f"play_by_play_{s}.parquet").exists()]
    p = pd.concat(parts, ignore_index=True)
    p = p[(p["season_type"] == "REG") & p["posteam"].notna() & p["yardline_100"].notna()].copy()
    p["team"] = p["posteam"].map(normalize_team)
    p["opp"] = p["defteam"].map(lambda t: normalize_team(t) if isinstance(t, str) else t)
    no2 = p["two_point_attempt"].fillna(0) != 1
    rush = p[(p["play_type"] == "run") & p["rusher_player_id"].notna() & no2 & (p["qb_kneel"].fillna(0) != 1)]
    tgt = p[(p["play_type"] == "pass") & p["receiver_player_id"].notna() & no2]
    t = pd.concat([
        pd.DataFrame({"season": rush["season"], "week": rush["week"], "game_id": rush["game_id"], "team": rush["team"], "opp": rush["opp"], "pid": rush["rusher_player_id"],
                      "kind": 0, "yl": rush["yardline_100"], "td": (rush["rush_touchdown"] == 1).astype(int), "yards": rush["rushing_yards"].fillna(0), "complete": 1}),
        pd.DataFrame({"season": tgt["season"], "week": tgt["week"], "game_id": tgt["game_id"], "team": tgt["team"], "opp": tgt["opp"], "pid": tgt["receiver_player_id"],
                      "kind": 1, "yl": tgt["yardline_100"], "td": (tgt["pass_touchdown"] == 1).astype(int), "yards": tgt["receiving_yards"].fillna(0),
                      "complete": tgt["complete_pass"].fillna(0).astype(int)})], ignore_index=True)
    t["zone"] = np.select([t["yl"] <= 5, t["yl"] <= 20, t["yl"] <= 40], [0, 1, 2], 3)
    t["pos"] = t["pid"].map(U.positions()).fillna("OTHER")
    d = p[p["fixed_drive"].notna() & p["play_type"].isin(["pass", "run", "field_goal", "no_play", "qb_kneel", "qb_spike"])]
    dr = d.groupby(["season", "week", "game_id", "team", "opp", "fixed_drive"], as_index=False).agg(rz=("yardline_100", lambda s: bool((s <= 20).any())),
                                                                                                    result=("fixed_drive_result", "last"), plays=("yardline_100", "size"))
    dr["td"] = dr["result"].eq("Touchdown")
    lg = t[t["season"].isin(LEAGUE_SEASONS)]
    rate = lg.groupby(["kind", "zone"])["td"].mean().unstack().reindex(index=[0, 1], columns=range(4)).fillna(0.0)
    by_pos = lg.groupby(["pos", "kind", "zone"])["td"].agg(["mean", "size"])
    rate_pos = by_pos["mean"].where(by_pos["size"] >= 200)   # a position's own rate where it has at least 200 touches of that kind in that zone
    v = rate_pos.reindex(pd.MultiIndex.from_arrays([t["pos"], t["kind"], t["zone"]])).to_numpy()
    t["xtd"] = np.where(np.isnan(v), rate.to_numpy()[t["kind"].to_numpy(), t["zone"].to_numpy()], v)
    plays = p[p["play_type"].isin(["pass", "run"])].groupby(["season", "week", "game_id", "team"], as_index=False).size().rename(columns={"size": "plays"})
    _CACHE.update(key=key, tables=(t, dr, plays, rate))
    return _CACHE["tables"]


def league_rates() -> dict:
    """Touchdown chance per rush and per target by zone, 2022 to 2025 (the expected-touchdown yardstick)."""
    rate = _load()[3]
    return {kind: {z[0]: float(rate.loc[i, j]) for j, z in enumerate(ZONES)} for i, kind in ((0, "rush"), (1, "target"))}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _window_weeks(df: pd.DataFrame, team_col: str, team: str, season: int, week: int) -> list[int]:
    w = sorted(df.loc[(df["season"] == season) & (df[team_col] == team) & (df["week"] < week), "week"].unique())
    return [int(x) for x in w[-WINDOW:]]


def _games(t: pd.DataFrame, season: int, week: int, window: int = WINDOW) -> pd.DataFrame:
    """Per player-game table inside each team's last-seven-game window: touches by zone, yards, touchdowns, expected touchdowns, role."""
    g = t[(t["season"] == season) & (t["week"] < week)]
    teams = g["team"].unique()
    keep = []
    for tm in teams:
        ws = sorted(g.loc[g["team"] == tm, "week"].unique())[-window:]
        keep.append(g[(g["team"] == tm) & g["week"].isin(ws)])
    g = pd.concat(keep, ignore_index=True)
    r, x = g[g["kind"] == 0], g[g["kind"] == 1]
    keys = ["season", "week", "game_id", "team", "opp", "pid", "pos"]
    a = r.groupby(keys).agg(carries=("td", "size"), rush_yds=("yards", "sum"), rush_td=("td", "sum"), rush_xtd=("xtd", "sum"),
                            gl_carries=("zone", lambda s: int((s == 0).sum())), rz_carries=("zone", lambda s: int((s <= 1).sum())))
    b = x.groupby(keys).agg(targets=("td", "size"), rec=("complete", "sum"), rec_yds=("yards", "sum"), rec_td=("td", "sum"), tgt_xtd=("xtd", "sum"),
                            gl_targets=("zone", lambda s: int((s == 0).sum())), rz_targets=("zone", lambda s: int((s <= 1).sum())))
    pg = a.join(b, how="outer").fillna(0).reset_index()
    pg["rz_touches"] = pg["rz_carries"] + pg["rz_targets"]
    pg["gl_touches"] = pg["gl_carries"] + pg["gl_targets"]
    pg["touches"] = pg["carries"] + pg["targets"]
    pg["tds"] = pg["rush_td"] + pg["rec_td"]
    pg["xtd"] = pg["rush_xtd"] + pg["tgt_xtd"]
    # role in that game: by carries for backs, by targets for receivers
    metric = np.where(pg["pos"] == "RB", pg["carries"], pg["targets"])
    pg["role_metric"] = metric
    pg["role_rank"] = pg.assign(m=metric).groupby(["game_id", "team", "pos"])["m"].rank(method="first", ascending=False).astype(int)
    return pg


def _role_name(pos: str, rank: int) -> str | None:
    names = ROLES.get(pos)
    return names[rank - 1] if names and 1 <= rank <= len(names) else None


def _rank_desc(s: pd.Series, key) -> int:
    """1 = the highest value among the 32 teams."""
    return int(s.rank(method="min", ascending=False).loc[key])


def card(team: str, pid: str, week: int, opp: str, margin_for: float | None, total: float | None, season: int = D.SEASON, tdp: float | None = None) -> dict | None:
    """The touchdown card, or None when the player has no touches in the team's last seven games."""
    t, dr, plays, rate = _load()
    pg = _games(t, season, week, PLAYER_WINDOW)
    me = pg[(pg["team"] == team) & (pg["pid"] == pid)]
    if me.empty:
        return None
    pos = me["pos"].iloc[0]
    team_pg = pg[pg["team"] == team]
    team_games = sorted(team_pg["week"].unique())
    n_g = int(me["game_id"].nunique())
    # ---- role in this window
    grp = team_pg[team_pg["pos"] == pos].groupby("pid")["role_metric"].sum().sort_values(ascending=False)
    my_rank = int(list(grp.index).index(pid)) + 1
    role = _role_name(pos, my_rank)
    # ---- team context
    rz_touch_team = float(team_pg["rz_touches"].sum())
    grp_rz = float(team_pg.loc[team_pg["pos"] == pos, "rz_touches"].sum())
    my_rz = float(me["rz_touches"].sum())
    tgt_team = float(team_pg["targets"].sum())
    drv = dr[(dr["season"] == season) & (dr["team"] == team) & dr["week"].isin(team_games)]
    trips_pg = float(drv["rz"].sum() / max(len(team_games), 1))
    rz_td_rate = float(drv.loc[drv["rz"], "td"].mean()) if drv["rz"].any() else None
    # defense allowed (drives): every team's defense over its own last seven games
    d_all = dr[(dr["season"] == season) & (dr["week"] < week)]
    d_rz = {}
    for tm, df in d_all.groupby("opp"):
        ws = sorted(df["week"].unique())[-WINDOW:]
        x = df[df["week"].isin(ws) & df["rz"]]
        d_rz[tm] = float(x["td"].mean()) if len(x) else np.nan
    d_rz = pd.Series(d_rz).dropna()
    opp_rz = float(d_rz.get(opp, np.nan)) if opp in d_rz.index else None
    opp_rz_rank = _rank_desc(d_rz, opp) if opp in d_rz.index else None
    # pace: offensive plays per game, last seven games
    pl = plays[(plays["season"] == season) & (plays["week"] < week)]
    pace = {}
    for tm, df in pl.groupby("team"):
        pace[tm] = float(df.sort_values("week").tail(WINDOW)["plays"].mean())
    pace = pd.Series(pace)
    # ---- his rates
    carries, targets = float(me["carries"].sum()), float(me["targets"].sum())
    touches = carries + targets
    tds = float(me["tds"].sum())
    xtd = float(me["xtd"].sum())
    zone_rows = []
    mine_t = t[(t["season"] == season) & (t["team"] == team) & (t["pid"] == pid) & t["week"].isin(team_games)]
    for i, (key, label) in enumerate(ZONES):
        r, x = mine_t[(mine_t["kind"] == 0) & (mine_t["zone"] == i)], mine_t[(mine_t["kind"] == 1) & (mine_t["zone"] == i)]
        zone_rows.append({"zone": label, "carries": int(len(r)), "targets": int(len(x)), "xtd": float(r["xtd"].sum() + x["xtd"].sum())})
    profile = {"rz_role": my_rz / rz_touch_team if rz_touch_team else None,
               "rz_claim": {"mine": int(my_rz), "group": int(grp_rz), "share": my_rz / grp_rz if grp_rz else None, "group_label": pos, "team_rz_touches": int(rz_touch_team)},
               "rz_targets_pg": float(me["rz_targets"].sum() / n_g), "rz_carries_pg": float(me["rz_carries"].sum() / n_g),
               "team_rz_trips_pg": trips_pg, "team_rz_td_rate": rz_td_rate, "opp_rz_td_rate_allowed": opp_rz, "opp_rz_rank": opp_rz_rank,
               "touches_pg": touches / n_g, "gl_pg": float(me["gl_touches"].sum() / n_g), "target_share": targets / tgt_team if tgt_team else None,
               "td_rate": tds / touches if touches else None}
    # ---- defense allowed: TDs by position, game by game, and by role
    opp_games_all = t[(t["season"] == season) & (t["week"] < week)]
    tds_allowed = {}
    for tm, df in opp_games_all.groupby("opp"):
        ws = sorted(df["week"].unique())[-WINDOW:]
        x = df[df["week"].isin(ws) & (df["td"] == 1)]
        tds_allowed[tm] = x.groupby("pos").size().reindex(["RB", "WR", "TE", "QB"]).fillna(0).astype(int)
        tds_allowed[tm]["games"] = len(ws)
    ta = pd.DataFrame(tds_allowed).T.fillna(0)
    opp_ws = sorted(opp_games_all.loc[opp_games_all["opp"] == opp, "week"].unique())[-WINDOW:]
    table = []
    for w in opp_ws:
        x = opp_games_all[(opp_games_all["opp"] == opp) & (opp_games_all["week"] == w) & (opp_games_all["td"] == 1)]
        row = {"week": int(w), "vs": x["team"].iloc[0] if len(x) else opp_games_all.loc[(opp_games_all["opp"] == opp) & (opp_games_all["week"] == w), "team"].iloc[0]}
        for ps in ("RB", "WR", "TE", "QB"):
            row[ps] = int((x["pos"] == ps).sum())
        table.append(row)
    ranks = {ps: _rank_desc(ta[ps], opp) for ps in ("RB", "WR", "TE", "QB")} if opp in ta.index else {}
    totals = {ps: int(ta.loc[opp, ps]) for ps in ("RB", "WR", "TE", "QB")} if opp in ta.index else {}
    # ADV: share of his offense's touchdowns that go to his position minus the share this defense gives up there
    off_td = team_pg.groupby("pos")["tds"].sum()
    my_share = float(off_td.get(pos, 0) / off_td.sum()) if off_td.sum() else 0.0
    def_share = float(ta.loc[opp, pos] / max(ta.loc[opp, ["RB", "WR", "TE", "QB"]].sum(), 1)) if opp in ta.index and pos in ta.columns else 0.0
    adv = {pos: my_share - def_share}
    # ---- role tax
    role_tax = None
    if role and pos in ("RB", "WR", "TE"):
        pr = _games(t, season, week, WINDOW)
        pr = pr[(pr["pos"] == pos) & (pr["role_rank"] == ROLES[pos].index(role) + 1)]
        by_def = pr.groupby("opp")[[m for m, _ in ROLE_METRICS]].mean()
        counts = pr.groupby("opp").size()
        by_def = by_def[counts >= 3]
        mine = me[[m for m, _ in ROLE_METRICS]].sum() / n_g
        rows = []
        for m, lab in ROLE_METRICS:
            if opp in by_def.index:
                rows.append({"metric": lab, "him": float(mine[m]), "allows": float(by_def.loc[opp, m]), "rank": _rank_desc(by_def[m], opp) if by_def[m].nunique() > 1 else None})
        role_tax = {"role": role, "rows": rows}
    # ---- leaks
    leaks = []
    for ps, lab in POS_LABEL.items():
        if ranks.get(ps) is not None and ranks[ps] <= 8 and totals.get(ps, 0) > 0:
            leaks.append({"text": f"{opp} has allowed {totals[ps]} TDs to {lab} in its last {len(opp_ws)} games, {ordinal(ranks[ps])} most.", "hits_role": ps == pos})
    if role_tax:
        for r in role_tax["rows"]:
            if r["metric"] in ("Rush TD", "Rec TD") and r["rank"] is not None and r["rank"] <= 8 and r["allows"] > 0:
                n = r["allows"] * len(opp_ws)
                leaks.append({"text": f"{opp} has allowed {n:.0f} {r['metric'].split()[0].lower()} TDs to {role.lower() if role[0] != 'W' and role[0] != 'T' else role} in its last {len(opp_ws)} games, {ordinal(r['rank'])} most.", "hits_role": True})
    # ---- opportunity extras
    my_games_weeks = sorted(me["week"].unique())
    last_td = me[me["tds"] > 0]["week"].max() if (me["tds"] > 0).any() else None
    since = int(sum(1 for w in team_games if last_td is None or w > last_td))
    snap = _snap_share(pid, team, season, week)
    script = {"favored_by": margin_for, "total": total, "implied": None if (margin_for is None or total is None) else (total + margin_for) / 2,
              "pace_rank": _rank_desc(pace, team) if team in pace.index else None, "pace": float(pace[team]) if team in pace.index else None}
    # ---- tags
    tags = []
    def tag(label, fired, why):
        tags.append({"label": label, "fired": bool(fired), "why": why})
    rz_role = profile["rz_role"] or 0.0
    rz_need = 0.30 if pos == "RB" else 0.15
    tag("Red-zone role", rz_role >= rz_need, f"{rz_role:.0%} of his team's red-zone touches (needs {rz_need:.0%})")
    if pos == "RB":
        tag("Goal-line back", profile["gl_pg"] >= 1.5, f"{profile['gl_pg']:.1f} goal-line touches a game (needs 1.5)")
        tag("High volume", profile["touches_pg"] >= 17, f"{profile['touches_pg']:.1f} touches a game (needs 17)")
    else:
        tag("High volume", targets / n_g >= 7, f"{targets / n_g:.1f} targets a game (needs 7)")
    tag("Favored", margin_for is not None and margin_for >= 3, "favored by 3 or more" if margin_for is not None else "no line")
    soft = ranks.get(pos)
    tag(f"Defense bottom 8 vs {pos}", soft is not None and soft <= 8, f"{opp} ranks {ordinal(soft)} in touchdowns allowed to {POS_LABEL.get(pos, pos)}" if soft else "no data")
    tag("Active leak", any(l["hits_role"] for l in leaks), "the defense has been giving up touchdowns to his role" if leaks else "no leak found")
    debt = xtd - tds
    tag("Due to convert", debt >= 1.0, f"expected {xtd:.1f} touchdowns, scored {tds:.0f}")
    tag("Running hot", debt <= -1.5, f"scored {tds:.0f} on {xtd:.1f} expected")
    fired = [x for x in tags if x["fired"]]
    return {"player": None, "pid": pid, "team": team, "opp": opp, "pos": pos, "role": role, "tdp": tdp,
            "window": {"weeks": [my_games_weeks[0], my_games_weeks[-1]] if my_games_weeks else [], "games": n_g, "team_games": len(team_games)},
            "script": script, "profile": profile,
            "cheat": {"expected": xtd, "scored": tds, "debt": debt, "zones": zone_rows},
            "role_tax": role_tax, "leaks": leaks,
            "opportunity": {"matchup_pg": (totals.get(pos, 0) / max(len(opp_ws), 1)) if totals else None, "table": table, "totals": totals, "ranks": ranks, "adv": adv,
                            "snap_share": snap, "games_since_td": since},
            "tags": tags, "tagline": " + ".join(x["label"] for x in fired[:3]), "fired": len(fired)}


def _snap_share(pid: str, team: str, season: int, week: int) -> float | None:
    path = RAW_DIR / f"snap_counts_{season}.parquet"
    if not path.exists():
        return None
    s = D._cached(("snaps", season), D._mt(path), lambda: pd.read_parquet(path, columns=["week", "player", "team", "offense_pct", "position"]).assign(
        team=lambda d: d["team"].map(lambda x: normalize_team(x) if isinstance(x, str) else x)))
    from . import gamesim as S
    name = S._names().get(pid)
    if not name:
        return None
    x = s[(s["team"] == team) & (s["week"] < week) & (s["player"].map(S._norm) == S._norm(name))].sort_values("week").tail(WINDOW)
    return float(x["offense_pct"].mean()) if len(x) else None
