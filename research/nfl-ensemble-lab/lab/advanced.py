"""Phase 4 advanced football intelligence: richer free data, aggregated per team-game
and turned into strictly-pregame features (only games that kicked off earlier).

Sources (nflverse-data releases, free, no authentication):
  pbp_participation  2016-2025  personnel groupings, box counts, pass rushers, pressure
  nextgen_stats      2016-2026  weekly NGS passing / rushing / receiving
  pfr_advstats       2018-2026  weekly PFR pressures, blitzes, contact yards, missed tackles
  snap_counts+players 2012-2026 roster experience, depth and continuity
Everything from a game is used only for LATER games (as-of joins, strict '<' kickoff).
Missing seasons/columns stay NaN.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import sources
from .config import RAW_DIR
from .ingest import normalize_team

NFLV = "https://github.com/nflverse/nflverse-data/releases/download"
PART_URL = NFLV + "/pbp_participation/pbp_participation_{s}.parquet"
NGS_URL = NFLV + "/nextgen_stats/ngs_{kind}.parquet"
PFR_URL = NFLV + "/pfr_advstats/advstats_week_{kind}_{s}.parquet"
BLEND_K = 3.0

SOURCE_INFO = [
    {"source": "nflverse pbp_participation", "seasons": "2016-2025 (no 2026 file yet)", "used_for": "personnel, box counts, blitz, pressure",
     "limits": "pressure/time-to-throw ~40% of plays before 2018; man/zone only 2023+ (not used); 2026 games fall back to 2025 tendencies"},
    {"source": "nflverse nextgen_stats", "seasons": "2016-2026 weekly", "used_for": "CPOE, time to throw, aggressiveness, RYOE, separation, YAC over expected",
     "limits": "player-weeks below NGS volume thresholds are absent"},
    {"source": "nflverse pfr_advstats (weekly)", "seasons": "2018-2026", "used_for": "pressures/blitzes/hurries, bad throws, drops, contact yards, broken & missed tackles",
     "limits": "starts 2018; earlier games NaN"},
    {"source": "nflverse snap_counts + players", "seasons": "2012-2026", "used_for": "OL/defense experience, depth, returning snap share",
     "limits": "experience = season - rookie_season (static player attribute)"},
    {"source": "derived from the lab's own ratings", "seasons": "2016-2026", "used_for": "strength of schedule faced", "limits": "-"},
]
INVESTIGATED_NOT_USED = [
    ("FTN charting", "2022+ only; too short for training"),
    ("Participation man/zone coverage", "2023+ only"),
    ("Depth charts 2016-2024", "no publication timestamps (live monitoring only)"),
    ("Weekly roster status (ACT/INA)", "game-day inactive status is not pregame information"),
    ("ESPN QBR weekly (nflverse espn_data)", "largely redundant with EPA-based QB efficiency"),
    ("FiveThirtyEight Elo", "project discontinued; its QB adjustment used actual starters"),
    ("Kaggle / PFF / Sports Info Solutions", "login or subscription required: not accessed"),
    ("Historical weather (Open-Meteo, Meteostat)", "observations or short-lead model analyses, not forecasts at our cutoffs"),
]


# --------------------------------------------------------------------------- downloads

def refresh(seasons: list[int], live: int, progress=print) -> list[str]:
    errors = []
    for s in seasons:
        if s < 2016:
            continue
        try:
            sources.download(f"nflverse_participation_{s}", PART_URL.format(s=s), RAW_DIR / f"participation_{s}.parquet",
                             max_age_hours=sources.LIVE_MAX_AGE_HOURS if s == live else None,
                             validate=sources._validate_parquet, progress=progress)
        except FileNotFoundError:
            pass  # not published (e.g. live season)
        except Exception as exc:
            errors.append(f"participation {s}: {exc}")
        if s >= 2018:
            for kind in ("pass", "rush", "def"):
                try:
                    sources.download(f"nflverse_pfradv_{kind}_{s}", PFR_URL.format(kind=kind, s=s), RAW_DIR / f"pfradv_{kind}_{s}.parquet",
                                     max_age_hours=sources.LIVE_MAX_AGE_HOURS if s == live else None,
                                     validate=sources._validate_parquet, progress=progress)
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    errors.append(f"pfr {kind} {s}: {exc}")
    for kind in ("passing", "rushing", "receiving"):
        try:
            sources.download(f"nflverse_ngs_{kind}", NGS_URL.format(kind=kind), RAW_DIR / f"ngs_{kind}.parquet",
                             max_age_hours=sources.LIVE_MAX_AGE_HOURS, validate=sources._validate_parquet, progress=progress)
        except Exception as exc:
            errors.append(f"ngs {kind}: {exc}")
    return errors


def _team(x):
    try:
        return normalize_team(x)
    except ValueError:
        return None


def _id_map(games):
    m = dict(zip(games["source_game_id"], games["game_id"]))
    m.update({g: g for g in games["game_id"]})
    return m


def _opp_map(games):
    d = {}
    for g, h, a in zip(games["game_id"], games["home_team"], games["away_team"]):
        d[(g, h)], d[(g, a)] = a, h
    return d


# --------------------------------------------------------------------------- team-game aggregates

def participation_team_games(games, seasons) -> pd.DataFrame:
    idm, opp = _id_map(games), _opp_map(games)
    rows = []
    for s in seasons:
        p = RAW_DIR / f"participation_{s}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["nflverse_game_id", "possession_team", "offense_personnel", "defenders_in_box",
                                        "defense_personnel", "number_of_pass_rushers", "was_pressure", "time_to_throw"])
        d["game_id"] = d["nflverse_game_id"].map(idm)
        d["team"] = d["possession_team"].map(_team)
        d = d.dropna(subset=["game_id", "team"])
        op = d["offense_personnel"].fillna("")
        rb = op.str.extract(r"(\d) RB")[0].astype(float)
        te = op.str.extract(r"(\d) TE")[0].astype(float)
        wr = op.str.extract(r"(\d) WR")[0].astype(float)
        db = d["defense_personnel"].fillna("").str.extract(r"(\d) DB")[0].astype(float)
        has_p = op.str.len() > 0
        d = d.assign(pers11=np.where(has_p, ((rb == 1) & (te == 1) & (wr == 3)).astype(float), np.nan),
                     heavy=np.where(has_p, ((te >= 2) | (rb >= 2)).astype(float), np.nan),
                     box=d["defenders_in_box"].astype(float),
                     nickel_plus=np.where(db.notna(), (db >= 5).astype(float), np.nan),
                     dime=np.where(db.notna(), (db >= 6).astype(float), np.nan),
                     blitz=np.where(d["number_of_pass_rushers"].notna(), (d["number_of_pass_rushers"] >= 5).astype(float), np.nan),
                     pressure=pd.to_numeric(d["was_pressure"], errors="coerce").astype(float),
                     ttt=pd.to_numeric(d["time_to_throw"], errors="coerce").astype(float))
        g = d.groupby(["game_id", "team"]).agg(pers11_rate=("pers11", "mean"), heavy_rate=("heavy", "mean"), box_faced=("box", "mean"),
                                                faced_nickel_rate=("nickel_plus", "mean"), faced_blitz_rate=("blitz", "mean"),
                                                pressure_allowed_rate=("pressure", "mean"), time_to_throw=("ttt", "mean")).reset_index()
        rows.append(g)
    if not rows:
        return pd.DataFrame(columns=["game_id", "team"])
    off = pd.concat(rows, ignore_index=True)
    return _with_defense(off, opp, {"faced_nickel_rate": "nickel_rate", "faced_blitz_rate": "blitz_rate",
                                    "pressure_allowed_rate": "pressure_rate", "box_faced": "box_used"})


def _with_defense(off: pd.DataFrame, opp: dict, mirror: dict) -> pd.DataFrame:
    """Attach the defensive view: what this team's defense did = the opponent's offense row."""
    d = off.copy()
    d["def_team"] = [opp.get((g, t)) for g, t in zip(d["game_id"], d["team"])]
    dd = d[["game_id", "def_team"] + list(mirror)].rename(columns={"def_team": "team", **{k: f"def_{v}" for k, v in mirror.items()}})
    return off.merge(dd, on=["game_id", "team"], how="outer")


def ngs_team_games(games) -> pd.DataFrame:
    gk = pd.concat([games[["game_id", "season", "week"]].assign(team=games["home_team"]),
                    games[["game_id", "season", "week"]].assign(team=games["away_team"])])
    key = {(s, w, t): g for g, s, w, t in zip(gk["game_id"], gk["season"], gk["week"], gk["team"])}
    parts = []
    spec = {"passing": ("attempts", {"avg_time_to_throw": "ngs_ttt", "completion_percentage_above_expectation": "ngs_cpoe",
                                     "aggressiveness": "ngs_aggressiveness", "avg_air_yards_differential": "ngs_air_diff"}),
            "rushing": ("rush_attempts", {"rush_yards_over_expected_per_att": "ngs_ryoe", "efficiency": "ngs_rush_efficiency",
                                          "percent_attempts_gte_eight_defenders": "ngs_stacked_box_rate"}),
            "receiving": ("targets", {"avg_separation": "ngs_separation", "avg_yac_above_expectation": "ngs_yac_oe",
                                      "avg_cushion": "ngs_cushion"})}
    for kind, (wcol, cols) in spec.items():
        p = RAW_DIR / f"ngs_{kind}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        d = d[d["week"] > 0].copy()
        d["team"] = d["team_abbr"].map(_team)
        d["game_id"] = [key.get((s, w, t)) for s, w, t in zip(d["season"], d["week"], d["team"])]
        d = d.dropna(subset=["game_id"])
        w = d[wcol].astype(float).fillna(0)
        agg = {}
        for src, dst in cols.items():
            v = d[src].astype(float)
            agg[dst] = (v * w).groupby([d["game_id"], d["team"]]).sum() / w.where(v.notna(), 0).groupby([d["game_id"], d["team"]]).sum()
        parts.append(pd.DataFrame(agg))
    if not parts:
        return pd.DataFrame(columns=["game_id", "team"])
    off = pd.concat(parts, axis=1).reset_index().rename(columns={"level_0": "game_id", "level_1": "team"})
    return _with_defense(off, _opp_map(games), {"ngs_cpoe": "ngs_cpoe_allowed", "ngs_ryoe": "ngs_ryoe_allowed",
                                                "ngs_separation": "ngs_separation_allowed", "ngs_ttt": "ngs_ttt_forced"})


def pfr_team_games(games, seasons, tstats: pd.DataFrame) -> pd.DataFrame:
    idm, opp = _id_map(games), _opp_map(games)
    db = tstats.set_index(["game_id", "team"])["dropbacks"] if len(tstats) else pd.Series(dtype=float)
    out = []
    for s in seasons:
        if s < 2018:
            continue
        frames = {}
        for kind in ("pass", "rush", "def"):
            p = RAW_DIR / f"pfradv_{kind}_{s}.parquet"
            if p.exists():
                d = pd.read_parquet(p)
                d["game_id"] = d["game_id"].map(idm)
                d["team"] = d["team"].map(_team)
                frames[kind] = d.dropna(subset=["game_id", "team"])
        if not frames:
            continue
        g = None
        if "pass" in frames:
            a = frames["pass"].groupby(["game_id", "team"])[["times_pressured", "times_blitzed", "times_hurried", "times_hit",
                                                             "passing_bad_throws", "passing_drops"]].sum(min_count=1)
            dbk = db.reindex(a.index)
            a = pd.DataFrame({"pfr_pressured_rate": a["times_pressured"] / dbk, "pfr_blitzed_rate": a["times_blitzed"] / dbk,
                              "pfr_hit_rate": a["times_hit"] / dbk, "pfr_bad_throw_rate": a["passing_bad_throws"] / dbk,
                              "pfr_drop_rate": a["passing_drops"] / dbk})
            g = a
        if "rush" in frames:
            r = frames["rush"].groupby(["game_id", "team"])[["carries", "rushing_yards_before_contact", "rushing_yards_after_contact",
                                                             "rushing_broken_tackles"]].sum(min_count=1)
            r = pd.DataFrame({"pfr_ybc_per_carry": r["rushing_yards_before_contact"] / r["carries"],
                              "pfr_yac_per_carry": r["rushing_yards_after_contact"] / r["carries"],
                              "pfr_broken_tackle_rate": r["rushing_broken_tackles"] / r["carries"]})
            g = r if g is None else g.join(r, how="outer")
        if "def" in frames:
            dfn = frames["def"].groupby(["game_id", "team"])[["def_pressures", "def_missed_tackles", "def_tackles_combined",
                                                              "def_times_blitzed"]].sum(min_count=1)
            opp_db = pd.Series([db.get((gi, opp.get((gi, t))), np.nan) for gi, t in dfn.index], index=dfn.index)
            dfn = pd.DataFrame({"pfr_def_pressure_rate": dfn["def_pressures"] / opp_db, "pfr_def_blitz_rate": dfn["def_times_blitzed"] / opp_db,
                                "pfr_def_missed_tackle_rate": dfn["def_missed_tackles"] / (dfn["def_tackles_combined"] + dfn["def_missed_tackles"])})
            g = dfn if g is None else g.join(dfn, how="outer")
        out.append(g.reset_index())
    if not out:
        return pd.DataFrame(columns=["game_id", "team"])
    off = pd.concat(out, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    return _with_defense(off, opp, {"pfr_ybc_per_carry": "pfr_ybc_allowed", "pfr_yac_per_carry": "pfr_yac_allowed"})


def roster_team_games(games, seasons) -> pd.DataFrame:
    """Per completed team-game, from that game's snap counts: snap-weighted experience of the
    offensive line and defense, group depth, and the share of snaps by players who also
    played for the team the previous season. Used only for LATER games."""
    parts = []
    for s in seasons:
        p = RAW_DIR / f"snap_counts_{s}.parquet"
        if p.exists():
            parts.append(pd.read_parquet(p, columns=["game_id", "season", "pfr_player_id", "position", "team", "offense_pct", "defense_pct"]))
    if not parts:
        return pd.DataFrame(columns=["game_id", "team"])
    sn = pd.concat(parts, ignore_index=True)
    pl = pd.read_parquet(RAW_DIR / "players.parquet", columns=["pfr_id", "rookie_season"]).dropna().drop_duplicates("pfr_id")
    sn = sn.merge(pl, left_on="pfr_player_id", right_on="pfr_id", how="left")
    sn["team"] = sn["team"].map(_team)
    sn["game_id"] = sn["game_id"].map(_id_map(games))
    sn = sn.dropna(subset=["game_id", "team"])
    sn["exp"] = (sn["season"] - sn["rookie_season"]).clip(lower=0)
    prev_players = sn.groupby(["team", "season"])["pfr_player_id"].apply(set).to_dict()
    sn["returning"] = [pid in prev_players.get((t, s - 1), set()) for pid, t, s in zip(sn["pfr_player_id"], sn["team"], sn["season"])]
    grp = {"OL": ("T", "G", "C", "OT", "OG", "OL"), "DL": ("DE", "DT", "NT", "DL"), "LB": ("LB", "ILB", "OLB", "MLB"),
           "DB": ("CB", "S", "SS", "FS", "DB"), "WR": ("WR",)}
    rows = []
    for (g, t), d in sn.groupby(["game_id", "team"]):
        r = {"game_id": g, "team": t}
        ol = d[d["position"].isin(grp["OL"])]
        de = d[d["position"].isin(grp["DL"] + grp["LB"] + grp["DB"])]
        r["ol_exp"] = np.average(ol["exp"].fillna(ol["exp"].median()), weights=ol["offense_pct"]) if ol["offense_pct"].sum() > 0 and ol["exp"].notna().any() else np.nan
        r["def_exp"] = np.average(de["exp"].fillna(de["exp"].median()), weights=de["defense_pct"]) if de["defense_pct"].sum() > 0 and de["exp"].notna().any() else np.nan
        tot = d["offense_pct"].sum() + d["defense_pct"].sum()
        r["returning_snap_share"] = float(((d["offense_pct"] + d["defense_pct"]) * d["returning"]).sum() / tot) if tot > 0 else np.nan
        for k, pos in grp.items():
            col = "offense_pct" if k in ("OL", "WR") else "defense_pct"
            r[f"depth_{k}"] = int((d[d["position"].isin(pos)][col] >= 0.25).sum())
        rows.append(r)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- strictly-pregame windows

def window_features(games: pd.DataFrame, tg: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """For every (game, team): season-blended and last-5 means of the team-game values
    from games that kicked off strictly before. Missing stays missing."""
    cols = [c for c in tg.columns if c not in ("game_id", "team")]
    kick = games.set_index("game_id")[["kickoff_utc", "season"]]
    t = tg.merge(kick, left_on="game_id", right_index=True, how="inner").sort_values(["team", "kickoff_utc"]).reset_index(drop=True)
    vals = t[cols].astype(float)
    grp = [t["team"], t["season"]]
    csum = vals.fillna(0).groupby(grp).cumsum()
    ccnt = vals.notna().astype(float).groupby(grp).cumsum()
    std = (csum / ccnt.replace(0, np.nan)).set_axis([f"std_{c}" for c in cols], axis=1)
    l5 = vals.groupby(t["team"]).transform(lambda s: s.rolling(5, min_periods=1).mean()).set_axis([f"l5_{c}" for c in cols], axis=1)
    n = ccnt.set_axis([f"n_{c}" for c in cols], axis=1)
    states = pd.concat([t[["team", "season", "kickoff_utc"]].rename(columns={"season": "_ss"}), std, l5, n], axis=1).sort_values("kickoff_utc")
    prev = t.groupby(["team", "season"])[cols].mean().reset_index()
    prev["season"] += 1
    prev = prev.rename(columns={c: f"prev_{c}" for c in cols})
    tgt = pd.concat([games[["game_id", "season", "kickoff_utc"]].assign(team=games["home_team"]),
                     games[["game_id", "season", "kickoff_utc"]].assign(team=games["away_team"])]).sort_values("kickoff_utc")
    m = pd.merge_asof(tgt, states.rename(columns={"kickoff_utc": "_t"}), left_on="kickoff_utc", right_on="_t", by="team",
                      direction="backward", allow_exact_matches=False)
    same = m["_ss"] == m["season"]
    m = m.merge(prev, on=["team", "season"], how="left")
    out = {"game_id": m["game_id"].values, "team": m["team"].values}
    for c in cols:
        s_ = np.where(same, m[f"std_{c}"], np.nan)
        nn = np.where(same, m[f"n_{c}"], 0.0)
        pv = m[f"prev_{c}"].to_numpy(float)
        blend = np.where(np.isnan(s_), pv, np.where(np.isnan(pv), s_, (nn * np.nan_to_num(s_) + BLEND_K * np.nan_to_num(pv)) / (nn + BLEND_K)))
        out[f"{prefix}blend_{c}"] = blend
        out[f"{prefix}l5_{c}"] = m[f"l5_{c}"].to_numpy(float)
    return pd.DataFrame(out)


def strength_of_schedule(games: pd.DataFrame, ratings: pd.DataFrame) -> pd.DataFrame:
    """Mean pregame opponent rating of games already played (season-blended, last 5)."""
    r = ratings.set_index(["game_id", "team"])["rating_margin"]
    done = games[games["completed"]]
    rows = []
    for g, h, a in zip(done["game_id"], done["home_team"], done["away_team"]):
        rows.append({"game_id": g, "team": h, "opp_rating": r.get((g, a), np.nan)})
        rows.append({"game_id": g, "team": a, "opp_rating": r.get((g, h), np.nan)})
    return window_features(games, pd.DataFrame(rows), "p4sos_")


def build_team_features(games: pd.DataFrame, tstats: pd.DataFrame, ratings: pd.DataFrame | None = None,
                        transform=None) -> pd.DataFrame:
    """transform(tg) may alter team-game tables before windowing (used by the leakage gate)."""
    seasons = sorted(int(s) for s in games["season"].unique())
    done = games[games["completed"]]
    parts = []
    for fn, prefix in ((lambda: participation_team_games(done, seasons), "p4pers_"), (lambda: ngs_team_games(done), "p4ngs_"),
                       (lambda: pfr_team_games(done, seasons, tstats), "p4pfr_"), (lambda: roster_team_games(done, seasons), "p4roster_")):
        tg = fn()
        if transform is not None and len(tg):
            tg = transform(tg)
        if len(tg) and len(tg.columns) > 2:
            parts.append(window_features(games, tg, prefix))
    if ratings is not None:
        parts.append(strength_of_schedule(games, ratings))
    if not parts:
        return pd.DataFrame(columns=["game_id", "team"])
    out = parts[0]
    for p in parts[1:]:
        out = out.merge(p, on=["game_id", "team"], how="outer")
    return out
