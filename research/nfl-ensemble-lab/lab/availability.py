"""Player availability: official NFL injury reports (via nflverse), snap-count
roles, pregame projected starting QBs, and live-only monitoring.

Timestamp rule (the whole point of this module): an injury row may describe a
game only if its availability time is strictly before that game's kickoff.
  * 2016-2024 nflverse rows carry `date_modified`; that is the availability time.
  * 2025+ nflverse files dropped `date_modified`. Their rows are available only
    via snapshots this lab archived itself (`retrieved_at` = our download time).
    Rows from a snapshot downloaded after kickoff are never used.
  * ESPN's public injury feed and ESPN depth charts are live monitoring only;
    they never enter model features.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import sources
from .config import RAW_DIR
from .ingest import TEAM_ALIASES, TEAMS

ARCHIVE_DIR = RAW_DIR / "archive"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"
INJURY_URL = NFLVERSE + "/injuries/injuries_{season}.parquet"
SNAP_URL = NFLVERSE + "/snap_counts/snap_counts_{season}.parquet"
PLAYERS_URL = NFLVERSE + "/players/players.parquet"
DEPTH_URL = NFLVERSE + "/depth_charts/depth_charts_{season}.parquet"
ESPN_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
LAST_TIMESTAMPED_SEASON = 2024   # last nflverse injury season with date_modified

GROUPS = {
    "QB": ("QB",), "RB": ("RB", "FB", "HB"), "WR": ("WR",), "TE": ("TE",),
    "OL": ("T", "OT", "G", "OG", "C", "OL", "LT", "RT", "LG", "RG"),
    "DL": ("DE", "DT", "NT", "DL", "EDGE"), "LB": ("LB", "ILB", "OLB", "MLB"),
    "CB": ("CB",), "S": ("S", "SS", "FS", "DB", "SAF"),
}
POS_TO_GROUP = {p: g for g, ps in GROUPS.items() for p in ps}
OUT_STATUSES = {"Out", "Doubtful"}
STARTER_ROLE = 0.5      # snap share that counts a player as a regular starter
ROLE_GAMES = 4          # trailing games used for a player's role


def _team(code):
    code = str(code).strip().upper()
    code = TEAM_ALIASES.get(code, code)
    return code if code in TEAMS else None


# --------------------------------------------------------------------------- downloads

def refresh_sources(seasons: list[int], live: int, progress=print) -> dict:
    """Download injury, snap-count and player files. The live season's injury file
    is archived with our retrieval time whenever its content changes."""
    status = {"injury_seasons": [], "snap_seasons": [], "errors": []}
    sources.download("nflverse_players", PLAYERS_URL, RAW_DIR / "players.parquet", max_age_hours=24 * 7,
                     validate=sources._validate_parquet, progress=progress)
    for s in seasons:
        is_live = s == live
        for kind, url, key in (("injuries", INJURY_URL, "injury_seasons"), ("snap_counts", SNAP_URL, "snap_seasons")):
            try:
                e = sources.download(f"nflverse_{kind}_{s}", url.format(season=s), RAW_DIR / f"{kind}_{s}.parquet",
                                     max_age_hours=sources.LIVE_MAX_AGE_HOURS if is_live else None,
                                     validate=sources._validate_parquet, progress=progress)
                status[key].append(int(s))
                if kind == "injuries" and is_live:
                    archive_snapshot(RAW_DIR / f"injuries_{s}.parquet", e, "nflverse_injuries")
            except Exception as exc:
                status["errors"].append(f"{kind} {s}: {exc}")
    try:
        sources.download(f"nflverse_depth_{live}", DEPTH_URL.format(season=live), RAW_DIR / f"depth_charts_{live}.parquet",
                         max_age_hours=sources.LIVE_MAX_AGE_HOURS, validate=sources._validate_parquet, progress=progress)
    except Exception as exc:
        status["errors"].append(f"depth chart {live}: {exc}")
    try:
        body, _ = sources._fetch(ESPN_INJURIES, timeout=60)
        payload = json.loads(body)
        path = ARCHIVE_DIR / f"espn_injuries_{_stamp()}.json"
        path.write_bytes(body)
        status["espn_retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        status["espn_records"] = sum(len(t.get("injuries", [])) for t in payload.get("injuries", []))
    except Exception as exc:
        status["errors"].append(f"ESPN injuries: {exc}")
    return status


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def archive_snapshot(path, entry: dict, kind: str) -> None:
    """Keep a copy of a live file per content hash, named by retrieval time."""
    existing = list(ARCHIVE_DIR.glob(f"{kind}_*_{entry['sha256'][:12]}.parquet"))
    if existing:
        return
    ts = datetime.fromisoformat(entry["downloaded_at"]).strftime("%Y%m%dT%H%M%SZ")
    (ARCHIVE_DIR / f"{kind}_{ts}_{entry['sha256'][:12]}.parquet").write_bytes(path.read_bytes())


# --------------------------------------------------------------------------- injury rows

def _norm_injuries(d: pd.DataFrame, available_at) -> pd.DataFrame:
    out = pd.DataFrame({
        "season": pd.to_numeric(d["season"]).astype(int), "week": pd.to_numeric(d["week"]).astype(int),
        "team": d["team"].map(_team), "gsis_id": d["gsis_id"], "full_name": d.get("full_name"),
        "position": d["position"].astype(str).str.upper(),
        "report_status": d["report_status"], "practice_status": d.get("practice_status"),
        "available_at": available_at,
    })
    out["group"] = out["position"].map(POS_TO_GROUP)
    return out.dropna(subset=["team"])


def load_injury_rows(seasons: list[int]) -> pd.DataFrame:
    """All candidate injury rows with an `available_at` timestamp (NaT = unverifiable)."""
    parts = []
    for s in seasons:
        p = RAW_DIR / f"injuries_{s}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        if "date_modified" in d.columns:
            parts.append(_norm_injuries(d, pd.to_datetime(d["date_modified"], utc=True)).assign(source="nflverse date_modified"))
        else:
            parts.append(_norm_injuries(d, pd.NaT).assign(source="nflverse (no row timestamp)"))
    for p in sorted(ARCHIVE_DIR.glob("nflverse_injuries_*.parquet")):
        ts = pd.Timestamp(datetime.strptime(p.stem.split("_")[2], "%Y%m%dT%H%M%SZ"), tz="UTC")
        d = pd.read_parquet(p)
        parts.append(_norm_injuries(d, ts).assign(source=f"lab archive {p.stem.split('_')[2]}"))
    if not parts:
        return pd.DataFrame(columns=["season", "week", "team", "gsis_id", "position", "group", "report_status", "available_at", "source"])
    return pd.concat(parts, ignore_index=True)


def pregame_injuries(rows: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """For each (game, team) keep only rows available strictly before kickoff.
    Among archived snapshots the latest pre-kickoff snapshot wins."""
    sides = []
    for side in ("home", "away"):
        sides.append(games[["game_id", "season", "week", "kickoff_utc"]].assign(team=games[f"{side}_team"].values))
    gt = pd.concat(sides, ignore_index=True)
    m = rows.merge(gt, on=["season", "week", "team"], how="inner")
    m = m[m["available_at"].notna() & (m["available_at"] < m["kickoff_utc"])]
    if m.empty:
        return m
    latest = m.groupby(["game_id", "team", "source"])["available_at"].transform("max")
    m = m.assign(_snap=latest)
    # one source per game-team: the most recent one available before kickoff
    best = m.groupby(["game_id", "team"])["_snap"].transform("max")
    m = m[m["_snap"] == best].drop(columns="_snap")
    return m.drop_duplicates(["game_id", "team", "gsis_id"], keep="last")


def report_coverage(games: pd.DataFrame, valid: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    """Per game-team: was a timestamped report for that week available before THIS
    game's kickoff? (Teams can have empty reports, so coverage is decided by the
    earliest timestamped row of the week from any team, compared to this kickoff.)"""
    sides = []
    for side in ("home", "away"):
        sides.append(games[["game_id", "season", "week", "kickoff_utc"]].assign(team=games[f"{side}_team"].values))
    gt = pd.concat(sides, ignore_index=True)
    first = rows.dropna(subset=["available_at"]).groupby(["season", "week"])["available_at"].min() if len(rows) else pd.Series(dtype="datetime64[ns, UTC]")
    t0 = pd.Series([first.get((s, w), pd.NaT) for s, w in zip(gt["season"], gt["week"])], index=gt.index)
    gt["inj_report_available"] = (t0.notna() & (t0 < gt["kickoff_utc"])).astype(int)
    gt = gt.drop(columns="kickoff_utc")
    t = valid.groupby(["game_id", "team"]).agg(inj_report_time=("available_at", "max"), inj_source=("source", "first")).reset_index() if len(valid) else pd.DataFrame(columns=["game_id", "team", "inj_report_time", "inj_source"])
    return gt.merge(t, on=["game_id", "team"], how="left")


# --------------------------------------------------------------------------- player roles

def player_roles(seasons: list[int]) -> pd.DataFrame:
    """Snap share per player per game (max of offense/defense share), keyed by gsis_id."""
    parts = []
    for s in seasons:
        p = RAW_DIR / f"snap_counts_{s}.parquet"
        if p.exists():
            parts.append(pd.read_parquet(p, columns=["game_id", "pfr_player_id", "position", "team", "offense_pct", "defense_pct"]))
    if not parts:
        return pd.DataFrame(columns=["game_id", "gsis_id", "role"])
    snaps = pd.concat(parts, ignore_index=True)
    players = pd.read_parquet(RAW_DIR / "players.parquet", columns=["gsis_id", "pfr_id"]).dropna()
    snaps = snaps.merge(players.drop_duplicates("pfr_id"), left_on="pfr_player_id", right_on="pfr_id", how="inner")
    snaps["role"] = snaps[["offense_pct", "defense_pct"]].fillna(0).max(axis=1)
    return snaps[["game_id", "gsis_id", "role"]]


def role_asof(snaps: pd.DataFrame, games: pd.DataFrame, targets: pd.DataFrame) -> pd.Series:
    """Mean snap share over each player's last ROLE_GAMES games before the target kickoff.
    targets: DataFrame with gsis_id and kickoff_utc."""
    # snap files use source ids (e.g. OAK before relocation); accept both id forms
    kick = pd.concat([games.set_index("game_id")["kickoff_utc"],
                      games.set_index("source_game_id")["kickoff_utc"]]) if "source_game_id" in games else games.set_index("game_id")["kickoff_utc"]
    kick = kick[~kick.index.duplicated()]
    s = snaps.assign(kickoff_utc=snaps["game_id"].map(kick)).dropna(subset=["kickoff_utc"]).sort_values(["gsis_id", "kickoff_utc"])
    s["role_state"] = s.groupby("gsis_id")["role"].transform(lambda r: r.rolling(ROLE_GAMES, min_periods=1).mean())
    s = s.sort_values("kickoff_utc")
    t = targets.reset_index().sort_values("kickoff_utc")
    m = pd.merge_asof(t, s[["gsis_id", "kickoff_utc", "role_state"]].rename(columns={"kickoff_utc": "_t"}),
                      left_on="kickoff_utc", right_on="_t", by="gsis_id", direction="backward", allow_exact_matches=False)
    return m.set_index("index")["role_state"].reindex(targets.index).fillna(0.0)


# --------------------------------------------------------------------------- team features

INJ_GROUPS = list(GROUPS)


def team_injury_features(games: pd.DataFrame, valid: pd.DataFrame, snaps: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    """Team-level availability loss per position group, from verified pregame reports.
    Loads are sums of the listed players' recent snap shares, so weights come from
    observed playing time, not hand-set importance scores."""
    cov = report_coverage(games, valid, rows)
    cols = [f"inj_out_{g}" for g in INJ_GROUPS] + [f"inj_q_{g}" for g in INJ_GROUPS] + \
           [f"inj_starters_out_{g}" for g in INJ_GROUPS] + ["inj_out_off", "inj_out_def", "inj_q_off", "inj_q_def"]
    if len(valid):
        v = valid.copy()
        v["role"] = role_asof(snaps, games, v[["gsis_id", "kickoff_utc"]]).values
        v["is_out"] = v["report_status"].isin(OUT_STATUSES)
        v["is_q"] = v["report_status"].eq("Questionable")
        agg = {}
        for g in INJ_GROUPS:
            gv = v[v["group"] == g]
            agg[f"inj_out_{g}"] = (gv["role"] * gv["is_out"]).groupby([gv["game_id"], gv["team"]]).sum()
            agg[f"inj_q_{g}"] = (gv["role"] * gv["is_q"]).groupby([gv["game_id"], gv["team"]]).sum()
            agg[f"inj_starters_out_{g}"] = (gv["is_out"] & (gv["role"] >= STARTER_ROLE)).groupby([gv["game_id"], gv["team"]]).sum()
        loads = pd.DataFrame(agg).reset_index().rename(columns={"level_0": "game_id", "level_1": "team"})
        cov = cov.merge(loads, on=["game_id", "team"], how="left")
    for c in cols[:-4]:
        if c not in cov:
            cov[c] = np.nan
    # Practice-only reports (no game-status designations yet) are not a final report.
    final = valid.groupby(["game_id", "team"])["report_status"].apply(lambda r: r.notna().any()) if len(valid) else pd.Series(dtype=bool)
    # nflverse rows through LAST_TIMESTAMPED_SEASON are final weekly reports (a team without
    # designations was healthy). Live archive snapshots can predate Friday's final report,
    # so there a team counts as final only once it carries at least one game designation.
    cov["inj_final_published"] = [bool(final.get((g, t), False)) or s <= LAST_TIMESTAMPED_SEASON
                                  for g, t, s in zip(cov["game_id"], cov["team"], cov["season"])]
    cov["inj_report_available"] = (cov["inj_report_available"].astype(bool) & cov["inj_final_published"]).astype(int)
    avail = cov["inj_report_available"] == 1
    for c in cols[:-4]:
        cov[c] = np.where(avail, cov[c].fillna(0.0), np.nan)
    off, deff = ["QB", "RB", "WR", "TE", "OL"], ["DL", "LB", "CB", "S"]
    for kind in ("out", "q"):
        cov[f"inj_{kind}_off"] = cov[[f"inj_{kind}_{g}" for g in off]].sum(axis=1, min_count=1)
        cov[f"inj_{kind}_def"] = cov[[f"inj_{kind}_{g}" for g in deff]].sum(axis=1, min_count=1)
    return cov[["game_id", "team", "inj_report_available", "inj_final_published", "inj_report_time", "inj_source"] + cols]


def report_status_lookup(valid: pd.DataFrame) -> dict:
    """(game_id, team, gsis_id) -> report_status, for QB projection."""
    if valid is None or not len(valid):
        return {}
    return {(g, t, p): s for g, t, p, s in zip(valid["game_id"], valid["team"], valid["gsis_id"], valid["report_status"])}


# --------------------------------------------------------------------------- live monitoring (not model input)

def espn_latest() -> tuple[pd.DataFrame, str | None]:
    files = sorted(ARCHIVE_DIR.glob("espn_injuries_*.json"))
    if not files:
        return pd.DataFrame(), None
    payload = json.loads(files[-1].read_text(encoding="utf-8"))
    rows = []
    for t in payload.get("injuries", []):
        for i in t.get("injuries", []):
            a = i.get("athlete", {})
            rows.append({"team": _team(a.get("team", {}).get("abbreviation", "")), "player": a.get("displayName"),
                         "espn_id": str(a.get("links", [{}])[0].get("href", "")).split("/id/")[-1].split("/")[0] if a.get("links") else None,
                         "position": a.get("position", {}).get("abbreviation"), "status": i.get("status"),
                         "updated": i.get("date"), "note": i.get("shortComment")})
    return pd.DataFrame(rows), files[-1].stem.split("_")[-1]


def depth_chart_qb1(season: int) -> tuple[dict, str | None]:
    p = RAW_DIR / f"depth_charts_{season}.parquet"
    if not p.exists():
        return {}, None
    d = pd.read_parquet(p)
    if "dt" not in d.columns:
        return {}, None
    last = d["dt"].max()
    q = d[(d["dt"] == last) & (d["pos_abb"] == "QB") & (d["pos_rank"] == 1)]
    return {(_team(t)): (n, gid) for t, n, gid in zip(q["team"], q["player_name"], q["gsis_id"])}, last


def player_names() -> dict:
    p = RAW_DIR / "players.parquet"
    if not p.exists():
        return {}
    d = pd.read_parquet(p, columns=["gsis_id", "display_name"]).dropna()
    return dict(zip(d["gsis_id"], d["display_name"]))


def live_monitor(games: pd.DataFrame, fs_rows: pd.DataFrame, all_games: pd.DataFrame) -> list[dict]:
    """Live-only availability context for upcoming games. Shown to the user and stored
    in snapshots, but NEVER used as model input (it has no validated history)."""
    names = player_names()
    season = int(games["season"].iloc[0])
    qb1, depth_time = depth_chart_qb1(season)
    espn, espn_time = espn_latest()
    rows = load_injury_rows([season])
    live_rows = rows[rows["source"].str.startswith("lab archive")] if len(rows) else rows
    snaps = player_roles([season - 1, season])
    out = []
    for _, g in fs_rows.iterrows():
        for side in ("home", "away"):
            team = g[f"{side}_team"]
            proj = g.get(f"{side}_qb_projected_id")
            listed = g.get(f"{side}_qb_name")
            dc = qb1.get(team, (None, None))
            rep = live_rows[(live_rows["team"] == team) & (live_rows["week"] == g["week"])]
            if len(rep):
                rep = rep[rep["available_at"] == rep["available_at"].max()]
            key = []
            if len(rep):
                r = rep.assign(kickoff_utc=g["kickoff_utc"])
                r["role"] = role_asof(snaps, all_games, r[["gsis_id", "kickoff_utc"]]).values
                for _, x in r[(r["role"] >= 0.4) & (r["report_status"].notna() | r["practice_status"].fillna("").str.contains("Did Not"))].iterrows():
                    key.append({"player": x["full_name"], "pos": x["position"], "status": x["report_status"] or "no game status yet",
                                "practice": x["practice_status"], "recent_snap_share": round(float(x["role"]), 2)})
            e = espn[espn["team"] == team] if len(espn) else espn
            proj_name = names.get(proj, proj)
            espn_q = e[e["player"] == proj_name]["status"].tolist() if len(e) else []
            flags = []
            if g.get(f"{side}_qb_projected_out", 0) == 1:
                flags.append("projected starter listed Out/Doubtful; replacement projected")
            if g.get(f"{side}_qb_questionable", 0) == 1:
                flags.append("projected starter Questionable")
            if espn_q and espn_q[0] not in ("Active",):
                flags.append(f"ESPN lists projected QB as {espn_q[0]}")
            if dc[0] and proj_name and dc[0] != proj_name:
                flags.append(f"ESPN depth chart QB1 is {dc[0]}")
            if isinstance(listed, str) and proj_name and listed != proj_name:
                flags.append(f"nfldata lists {listed}")
            if g.get(f"{side}_qb_offseason", 0) == 1:
                flags.append("first game of season: projection uses last season's starter")
            out.append({
                "game_id": g["game_id"], "team": team, "side": side,
                "projected_qb": proj_name, "nfldata_listed_qb": listed, "espn_depth_qb1": dc[0],
                "qb_uncertain": bool(flags), "qb_flags": flags,
                "official_report_final": bool(g.get(f"{side}_inj_report_available") == 1),
                "official_report_retrieved_at": str(rep["available_at"].max()) if len(rep) else None,
                "key_listed_players": key,
                "espn_out_or_ir": e[e["status"].isin(["Out", "Injured Reserve", "Doubtful"])][["player", "position", "status"]].to_dict("records") if len(e) else [],
                "espn_retrieved": espn_time, "depth_chart_time": str(depth_time) if depth_time else None,
            })
    return out



def ol_churn(seasons: list[int], games: pd.DataFrame) -> pd.DataFrame:
    """Offensive-line lineup churn before each game: number of distinct offensive linemen who
    played >= 50% of offensive snaps in the team's last 4 completed games (5 = stable line).
    Uses only snap counts of earlier games."""
    parts = []
    for s in seasons:
        p = RAW_DIR / f"snap_counts_{s}.parquet"
        if p.exists():
            parts.append(pd.read_parquet(p, columns=["game_id", "pfr_player_id", "position", "team", "offense_pct"]))
    if not parts:
        return pd.DataFrame(columns=["game_id", "team", "ol_churn_l4"])
    sn = pd.concat(parts, ignore_index=True)
    sn = sn[sn["position"].isin(["T", "G", "C", "OT", "OG", "OL"]) & (sn["offense_pct"] >= 0.5)]
    sn["team"] = sn["team"].map(_team)
    kick = pd.concat([games.set_index("game_id")["kickoff_utc"], games.set_index("source_game_id")["kickoff_utc"]])
    kick = kick[~kick.index.duplicated()]
    sn["kickoff_utc"] = sn["game_id"].map(kick)
    sn = sn.dropna(subset=["kickoff_utc", "team"])
    per_game = sn.groupby(["team", "kickoff_utc"])["pfr_player_id"].apply(set).reset_index().sort_values(["team", "kickoff_utc"])
    states = []
    for team, d in per_game.groupby("team"):
        sets = d["pfr_player_id"].tolist()
        for i in range(len(d)):
            states.append((team, d["kickoff_utc"].iloc[i], len(set().union(*sets[max(0, i - 3): i + 1]))))
    st = pd.DataFrame(states, columns=["team", "_t", "ol_churn_l4"]).sort_values("_t")
    sides = []
    for side in ("home", "away"):
        sides.append(games[["game_id", "kickoff_utc"]].assign(team=games[f"{side}_team"].values))
    t = pd.concat(sides, ignore_index=True).sort_values("kickoff_utc")
    m = pd.merge_asof(t, st, left_on="kickoff_utc", right_on="_t", by="team", direction="backward", allow_exact_matches=False)
    return m[["game_id", "team", "ol_churn_l4"]]
