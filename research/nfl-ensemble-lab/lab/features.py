"""Pregame feature store: one row per game, built only from games that kicked
off strictly before the game being described.

Leakage rule: every team/QB statistic is attached with an as-of join on
kickoff time (`merge_asof(..., allow_exact_matches=False)`) against states
computed from completed games only. Ratings for week w are fit on games that
kicked off before the first kickoff of week w.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Per-game offensive stats aggregated from play-by-play (ingest.team_game_stats)
# plus points from the schedule. Each also gets a defensive mirror (`d_`) from the opponent.
STATS = [
    "points", "pass_yds", "rush_yds", "total_yds", "pass_td", "rush_td", "turnovers",
    "epa_pp", "pass_epa", "rush_epa", "sr", "pass_sr", "rush_sr", "early_epa", "early_sr",
    "third_conv", "rz_td_rate", "explosive_rate", "sack_rate", "plays", "sec_per_play", "pass_rate",
]
# Defensive mirrors that are meaningful (opponent's offense against this team).
DEF_STATS = [
    "points", "pass_yds", "rush_yds", "total_yds", "turnovers", "epa_pp", "pass_epa", "rush_epa",
    "sr", "pass_sr", "rush_sr", "explosive_rate", "sack_rate", "third_conv", "rz_td_rate",
]
WINDOWS = ("std", "l3", "l5", "prev", "blend")
BLEND_K = 3.0           # prior-season games of weight when blending with season-to-date
QB_PRIOR_MEAN = -0.05   # EPA/dropback shrinkage target for QBs with little history
QB_PRIOR_K = 150.0      # pseudo-dropbacks of shrinkage
QB_WINDOW = 600         # trailing dropbacks used for QB efficiency
RATING_PREV_WEIGHT = 0.35
RATING_RIDGE = 2.0


def _team_game_long(games: pd.DataFrame, tstats: pd.DataFrame) -> pd.DataFrame:
    """Two rows per completed game (one per team) with offense and defense stats."""
    done = games[games["completed"]]
    sides = []
    for side, opp in (("home", "away"), ("away", "home")):
        s = done[["game_id", "season", "week", "kickoff_utc"]].copy()
        s["team"] = done[f"{side}_team"].values
        s["opp"] = done[f"{opp}_team"].values
        s["points"] = done[f"{side}_score"].values
        s["d_points"] = done[f"{opp}_score"].values
        sides.append(s)
    long = pd.concat(sides, ignore_index=True)
    off = tstats.drop(columns=[c for c in ("points",) if c in tstats.columns])
    long = long.merge(off, on=["game_id", "team"], how="left")
    deff = tstats[["game_id", "team"] + [c for c in DEF_STATS if c in tstats.columns and c != "points"]]
    deff = deff.rename(columns={"team": "opp", **{c: f"d_{c}" for c in deff.columns if c not in ("game_id", "team")}})
    long = long.merge(deff, on=["game_id", "opp"], how="left")
    return long.sort_values(["team", "kickoff_utc"]).reset_index(drop=True)


def stat_columns() -> list[str]:
    return STATS + [f"d_{c}" for c in DEF_STATS]


def _post_game_states(long: pd.DataFrame) -> pd.DataFrame:
    """For each team after each completed game: season-to-date, last-3 and last-5 means
    INCLUDING that game. Joined as-of to strictly later kickoffs only."""
    cols = stat_columns()
    out = long[["team", "season", "kickoff_utc"]].copy()
    vals = long[cols].astype(float)
    filled, present = vals.fillna(0.0), vals.notna().astype(float)
    g = long.groupby(["team", "season"])
    csum = filled.groupby([long["team"], long["season"]]).cumsum()
    ccnt = present.groupby([long["team"], long["season"]]).cumsum()
    parts = [out, (csum / ccnt.replace(0, np.nan)).set_axis([f"std_{c}" for c in cols], axis=1),
             (g.cumcount() + 1).rename("std_games")]
    for n in (3, 5):
        roll = vals.groupby(long["team"]).transform(lambda s: s.rolling(n, min_periods=1).mean())
        parts.append(roll.set_axis([f"l{n}_{c}" for c in cols], axis=1))
    return pd.concat(parts, axis=1)


def _prev_season(long: pd.DataFrame) -> pd.DataFrame:
    cols = stat_columns()
    prev = long.groupby(["team", "season"])[cols].mean().reset_index()
    prev["season"] += 1
    return prev.rename(columns={c: f"prev_{c}" for c in cols})


def _asof(left: pd.DataFrame, right: pd.DataFrame, by: str, prefix_cols: list[str]) -> pd.DataFrame:
    """Attach the latest right row with kickoff strictly before left's kickoff."""
    l = left.sort_values("kickoff_utc")
    r = right.sort_values("kickoff_utc").rename(columns={"kickoff_utc": "_state_time"})
    merged = pd.merge_asof(l, r[[by, "_state_time"] + prefix_cols], left_on="kickoff_utc", right_on="_state_time",
                           by=by, direction="backward", allow_exact_matches=False)
    return merged


def team_pregame_states(games: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    """One row per (game_id, team) with every window of every stat as of kickoff."""
    cols = stat_columns()
    sides = []
    for side in ("home", "away"):
        s = games[["game_id", "season", "kickoff_utc"]].copy()
        s["team"] = games[f"{side}_team"].values
        sides.append(s)
    targets = pd.concat(sides, ignore_index=True)
    states = _post_game_states(long).rename(columns={"season": "_state_season"})
    state_cols = [c for c in states.columns if c not in ("team", "kickoff_utc")]
    m = _asof(targets, states, "team", state_cols)
    same = m["_state_season"] == m["season"]
    std_cols = [f"std_{c}" for c in cols] + ["std_games"]
    m.loc[~same, std_cols] = np.nan
    m["std_games"] = m["std_games"].fillna(0)
    m = m.merge(_prev_season(long), on=["team", "season"], how="left")
    n = m["std_games"].to_numpy()[:, None]
    std = m[[f"std_{c}" for c in cols]].to_numpy()
    prev = m[[f"prev_{c}" for c in cols]].to_numpy()
    blend = np.where(np.isnan(std), prev, np.where(np.isnan(prev), std, (n * np.nan_to_num(std) + BLEND_K * np.nan_to_num(prev)) / (n + BLEND_K)))
    m[[f"blend_{c}" for c in cols]] = blend
    return m.drop(columns=["_state_time", "_state_season"])


def _rest_days(games: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for side in ("home", "away"):
        rows.append(pd.DataFrame({"game_id": games["game_id"], "team": games[f"{side}_team"],
                                  "season": games["season"], "kickoff_utc": games["kickoff_utc"]}))
    t = pd.concat(rows).sort_values(["team", "kickoff_utc"])
    prev_kick = t.groupby("team")["kickoff_utc"].shift(1)
    prev_season = t.groupby("team")["season"].shift(1)
    days = (t["kickoff_utc"].dt.normalize() - prev_kick.dt.normalize()).dt.days
    t["rest_days"] = np.where(prev_season == t["season"], days, 14).clip(3, 21)
    return t[["game_id", "team", "rest_days"]]


def opponent_adjusted_ratings(games: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    """Ridge ratings of point margin and EPA/play margin, fit per (season, week) on
    games that kicked off before the first kickoff of that week."""
    teams = sorted(set(games["home_team"]) | set(games["away_team"]))
    idx = {t: i for i, t in enumerate(teams)}
    epa = long.pivot_table(index="game_id", columns="team", values="epa_pp")
    done = games[games["completed"]].copy()
    done["epa_margin"] = [epa.at[g, h] - epa.at[g, a] if g in epa.index and h in epa.columns and a in epa.columns else np.nan
                          for g, h, a in zip(done["game_id"], done["home_team"], done["away_team"])]
    out = []
    for (season, week), wk in games.groupby(["season", "week"]):
        cutoff = wk["kickoff_utc"].min()
        hist = done[(done["kickoff_utc"] < cutoff) & (done["season"] >= season - 1)]
        if len(hist) < 16:
            continue
        w = np.where(hist["season"] == season, 1.0, RATING_PREV_WEIGHT)
        X = np.zeros((len(hist), len(teams) + 1))
        X[np.arange(len(hist)), hist["home_team"].map(idx)] = 1
        X[np.arange(len(hist)), hist["away_team"].map(idx)] = -1
        X[:, -1] = 1 - hist["neutral_site"].to_numpy()
        res = {"season": season, "week": week}
        hl = long[(long["kickoff_utc"] < cutoff) & (long["season"] >= season - 1)].dropna(subset=["epa_pp"])
        if len(hl) >= 32:
            wl = np.where(hl["season"] == season, 1.0, RATING_PREV_WEIGHT)
            nT = len(teams)
            Xo = np.zeros((len(hl), 2 * nT + 1))
            Xo[np.arange(len(hl)), hl["team"].map(idx)] = 1          # offense strength
            Xo[np.arange(len(hl)), nT + hl["opp"].map(idx)] = 1      # defense allowed
            home_side = hl["game_id"].map(done.set_index("game_id")["home_team"]) == hl["team"]
            neutral = hl["game_id"].map(done.set_index("game_id")["neutral_site"]).fillna(0)
            Xo[:, -1] = (home_side & (neutral == 0)).astype(float)
            yo = hl["epa_pp"].to_numpy(float) - hl["epa_pp"].mean()
            pen = np.eye(Xo.shape[1]) * 5.0
            pen[-1, -1] = 0.0
            bo = np.linalg.solve(Xo.T @ (Xo * wl[:, None]) + pen, Xo.T @ (wl * yo))
            res["off_ratings"] = {t: bo[i] for t, i in idx.items()}
            res["def_ratings"] = {t: bo[nT + i] for t, i in idx.items()}
        for target in ("margin", "epa_margin"):
            y = hist[target].to_numpy(dtype=float)
            ok = ~np.isnan(y)
            Xw, yw, ww = X[ok], y[ok], w[ok]
            pen = np.eye(X.shape[1]) * RATING_RIDGE
            pen[-1, -1] = 0.0
            beta = np.linalg.solve(Xw.T @ (Xw * ww[:, None]) + pen, Xw.T @ (ww * yw))
            res[f"{target}_ratings"] = {t: beta[i] - beta[:-1].mean() for t, i in idx.items()}
        out.append(res)
    rows = []
    rmap = {(r["season"], r["week"]): r for r in out}
    for g in games.itertuples(index=False):
        r = rmap.get((g.season, g.week))
        for side, team in (("home", g.home_team), ("away", g.away_team)):
            rows.append({"game_id": g.game_id, "team": team,
                         "rating_margin": r["margin_ratings"][team] if r else np.nan,
                         "rating_epa": r["epa_margin_ratings"][team] if r else np.nan,
                         "rating_off_epa": r["off_ratings"][team] if r and "off_ratings" in r else np.nan,
                         "rating_def_epa": r["def_ratings"][team] if r and "def_ratings" in r else np.nan})
    return pd.DataFrame(rows)


def _qb_states(q: pd.DataFrame) -> pd.DataFrame:
    """Post-game efficiency state of each QB: shrunk EPA/dropback over his last QB_WINDOW dropbacks."""
    q = q.sort_values(["qb_id", "kickoff_utc"])
    q = q.groupby(["qb_id", "kickoff_utc"], as_index=False)[["qb_dropbacks", "qb_epa_sum"]].sum()
    q["cum_db"] = q.groupby("qb_id")["qb_dropbacks"].cumsum()
    q["cum_epa"] = q.groupby("qb_id")["qb_epa_sum"].cumsum()
    states = []
    for qb, d in q.groupby("qb_id", sort=False):
        db, ep = d["cum_db"].to_numpy(), d["cum_epa"].to_numpy()
        for i in range(len(d)):
            j = np.searchsorted(db, db[i] - QB_WINDOW, side="right") - 1
            base_db, base_ep = (db[j], ep[j]) if j >= 0 else (0.0, 0.0)
            n, s = db[i] - base_db, ep[i] - base_ep
            states.append((qb, d["kickoff_utc"].iloc[i], (s + QB_PRIOR_K * QB_PRIOR_MEAN) / (n + QB_PRIOR_K), db[i]))
    return pd.DataFrame(states, columns=["qb_id", "kickoff_utc", "qb_eff", "qb_career_db"])


def project_starters(games: pd.DataFrame, qb_games: pd.DataFrame, status: dict | None = None) -> pd.DataFrame:
    """Pregame projected starting QB per (game, team), using only information
    available before kickoff:
      1. the starter of the team's previous completed game (most dropbacks);
      2. if a verified pregame injury report lists that QB Out/Doubtful, the team's
         other QB with the most dropbacks for the team in this and last season;
         if none, an unknown replacement (efficiency = shrinkage prior).
    The QB who actually started is never used."""
    status = status or {}
    kick = games.set_index("game_id")["kickoff_utc"]
    q = qb_games.assign(kickoff_utc=qb_games["game_id"].map(kick)).dropna(subset=["kickoff_utc"])
    q["season"] = q["game_id"].str[:4].astype(int)
    starters = (q.sort_values("qb_dropbacks").groupby(["game_id", "team"]).tail(1)
                [["team", "qb_id", "kickoff_utc", "season"]].rename(columns={"qb_id": "prev_starter", "kickoff_utc": "_t", "season": "_prev_season"}))
    sides = []
    for side in ("home", "away"):
        sides.append(games[["game_id", "season", "kickoff_utc"]].assign(team=games[f"{side}_team"].values))
    t = pd.concat(sides, ignore_index=True).sort_values("kickoff_utc")
    t = pd.merge_asof(t, starters.sort_values("_t"), left_on="kickoff_utc", right_on="_t", by="team",
                      direction="backward", allow_exact_matches=False)
    t["qb_offseason"] = (t["_prev_season"] != t["season"]).astype(int)
    st_ = [status.get((g, tm, p)) for g, tm, p in zip(t["game_id"], t["team"], t["prev_starter"])]
    t["qb_projected_out"] = [int(s in ("Out", "Doubtful")) for s in st_]
    t["qb_questionable"] = [int(s == "Questionable") for s in st_]
    proj = t["prev_starter"].copy()
    for i in np.flatnonzero(t["qb_projected_out"].to_numpy()):
        r = t.iloc[i]
        pool = q[(q["team"] == r["team"]) & (q["kickoff_utc"] < r["kickoff_utc"]) & (q["season"] >= r["season"] - 1)
                 & (q["qb_id"] != r["prev_starter"])]
        proj.iloc[i] = pool.groupby("qb_id")["qb_dropbacks"].sum().idxmax() if len(pool) else None
    t["qb_projected_id"] = proj.values
    t["qb_change"] = (t["qb_projected_out"] == 1).astype(int)
    return t


def qb_pregame(games: pd.DataFrame, qb_games: pd.DataFrame, status: dict | None = None) -> pd.DataFrame:
    """Projected starter's trailing efficiency plus QB-uncertainty flags."""
    kick = games.set_index("game_id")["kickoff_utc"]
    st = _qb_states(qb_games.assign(kickoff_utc=qb_games["game_id"].map(kick)).dropna(subset=["kickoff_utc"]))
    t = project_starters(games, qb_games, status)
    t["qb_known"] = t["prev_starter"].notna().astype(int)
    known = t[t["qb_projected_id"].notna()].rename(columns={"qb_projected_id": "qb_id"})
    m = _asof(known.drop(columns=["_t"], errors="ignore"), st, "qb_id", ["qb_eff", "qb_career_db"])
    t = t.merge(m[["game_id", "team", "qb_eff", "qb_career_db"]], on=["game_id", "team"], how="left")
    # unknown replacement or no history: replacement-level prior, no experience
    t["qb_eff"] = t["qb_eff"].where(t["qb_known"] == 0, t["qb_eff"].fillna(QB_PRIOR_MEAN))
    t["qb_career_db"] = t["qb_career_db"].fillna(0)
    t["qb_log_exp"] = np.log1p(t["qb_career_db"])
    return t[["game_id", "team", "qb_projected_id", "qb_known", "qb_change", "qb_projected_out", "qb_questionable",
              "qb_offseason", "qb_eff", "qb_log_exp"]]


def travel_coach_context(games: pd.DataFrame) -> pd.DataFrame:
    """Schedule-derived travel, time-zone and head-coach context per (game, team).
    Team home base = most common stadium of its non-neutral home games that season."""
    from . import geo
    g = games.copy()
    g["site"] = [geo.site_key(s, n) for s, n in zip(g["stadium_id"], g.get("stadium", pd.Series([""] * len(g))))]
    homes = g[g["neutral_site"] == 0].groupby(["season", "home_team"])["site"].agg(lambda s: s.mode().iloc[0] if len(s.dropna()) else None)
    rows = []
    for r in g.itertuples(index=False):
        for side, team in (("home", r.home_team), ("away", r.away_team)):
            base = homes.get((r.season, team))
            rows.append({"game_id": r.game_id, "team": team, "season": r.season, "kickoff_utc": r.kickoff_utc,
                         "coach": getattr(r, f"{side}_coach", None),
                         "travel_km": geo.km(base, r.site) if base and r.site else np.nan,
                         "tz_shift": (geo.utc_offset_hours(r.site, r.kickoff_utc) - geo.utc_offset_hours(base, r.kickoff_utc))
                         if base and r.site else np.nan,
                         "body_clock_hour": geo.local_hour(base, r.kickoff_utc) if base else np.nan})
    t = pd.DataFrame(rows).sort_values(["team", "kickoff_utc"])
    # coaching: tenure counts only earlier games coached for this team; changes are known pregame
    t["coach_tenure_games"] = t.groupby(["team", "coach"]).cumcount()
    prev_coach = t.groupby("team")["coach"].shift(1)
    prev_season = t.groupby("team")["season"].shift(1)
    t["coach_new_this_season"] = ((t["coach"] != prev_coach) & (prev_season != t["season"]) & prev_coach.notna()).astype(int)
    t["coach_changed_midseason"] = ((t["coach"] != prev_coach) & (prev_season == t["season"])).astype(int)
    t["coach_log_tenure"] = np.log1p(t["coach_tenure_games"])
    return t[["game_id", "team", "travel_km", "tz_shift", "body_clock_hour", "coach_log_tenure",
              "coach_new_this_season", "coach_changed_midseason"]]


META_COLUMNS = [
    "game_id", "season", "week", "game_type", "gameday", "kickoff_utc", "home_team", "away_team",
    "completed", "home_score", "away_score", "margin", "home_win", "tie", "spread_line", "total_line",
    "home_moneyline", "away_moneyline", "market_p_home_novig", "home_qb_name", "away_qb_name",
]


def build_feature_store(games: pd.DataFrame, tstats: pd.DataFrame, qb_games: pd.DataFrame,
                        injuries: pd.DataFrame | None = None, qb_status: dict | None = None,
                        extra_team: pd.DataFrame | None = None, advanced: bool = False,
                        advanced_transform=None) -> pd.DataFrame:
    """injuries: per (game_id, team) output of availability.team_injury_features (verified rows only).
    qb_status: (game_id, team, gsis_id) -> verified pregame report status."""
    long = _team_game_long(games, tstats)
    team_state = team_pregame_states(games, long)
    rest = _rest_days(games)
    ratings = opponent_adjusted_ratings(games, long)
    qb = qb_pregame(games, qb_games, qb_status)
    per_team = (team_state.drop(columns=["season", "kickoff_utc"])
                .merge(rest, on=["game_id", "team"], how="left")
                .merge(ratings, on=["game_id", "team"], how="left")
                .merge(qb, on=["game_id", "team"], how="left"))
    if injuries is not None:
        per_team = per_team.merge(injuries, on=["game_id", "team"], how="left")
    if {"stadium_id", "home_coach"} <= set(games.columns):
        per_team = per_team.merge(travel_coach_context(games), on=["game_id", "team"], how="left")
    if extra_team is not None:
        per_team = per_team.merge(extra_team, on=["game_id", "team"], how="left")
    if advanced:
        from . import advanced as adv
        per_team = per_team.merge(adv.build_team_features(games, tstats, ratings, advanced_transform), on=["game_id", "team"], how="left")
    team_cols = [c for c in per_team.columns if c not in ("game_id", "team")]
    fs = games[META_COLUMNS + ["neutral_site", "div_game", "roof_type"]].copy()
    for side in ("home", "away"):
        part = per_team.rename(columns={c: f"{side}_{c}" for c in team_cols}).rename(columns={"team": f"{side}_team"})
        fs = fs.merge(part, on=["game_id", f"{side}_team"], how="left")
    # Derived columns are collected first and joined once (avoids frame fragmentation).
    new: dict[str, pd.Series] = {}
    # context
    new["ctx_home_field"] = 1 - fs["neutral_site"]
    new["ctx_neutral"] = fs["neutral_site"]
    new["ctx_div_game"] = fs["div_game"]
    new["ctx_playoff"] = (fs["game_type"] != "REG").astype(int)
    new["ctx_week"] = fs["week"]
    # Static stadium roof type; game-day open/closed status is not known pregame.
    new["ctx_dome"] = (fs["roof_type"] == "dome").astype(int)
    new["ctx_retractable"] = (fs["roof_type"] == "retractable").astype(int)
    new["ctx_rest_diff"] = fs["home_rest_days"] - fs["away_rest_days"]
    for side in ("home", "away"):
        new[f"ctx_{side}_short_week"] = (fs[f"{side}_rest_days"] <= 5).astype(int)
        new[f"ctx_{side}_off_bye"] = (fs[f"{side}_rest_days"] >= 12).astype(int)
    # matchup differences (home minus away) for every window/stat, ratings and QB
    for w in WINDOWS:
        for c in stat_columns():
            new[f"diff_{w}_{c}"] = fs[f"home_{w}_{c}"] - fs[f"away_{w}_{c}"]
    for c in ("rating_margin", "rating_epa", "qb_eff", "qb_log_exp"):
        new[f"diff_{c}"] = fs[f"home_{c}"] - fs[f"away_{c}"]
    # Phase 3 context (present only when the inputs exist)
    for c in ("rating_off_epa", "rating_def_epa", "travel_km", "tz_shift", "body_clock_hour", "coach_log_tenure",
              "coach_new_this_season", "coach_changed_midseason", "ol_churn_l4"):
        if f"home_{c}" in fs:
            new[f"p3_diff_{c}"] = fs[f"home_{c}"] - fs[f"away_{c}"]
    if "home_rating_off_epa" in fs:
        new["p3_mx_home_off_vs_away_def"] = fs["home_rating_off_epa"] + fs["away_rating_def_epa"]
        new["p3_mx_away_off_vs_home_def"] = fs["away_rating_off_epa"] + fs["home_rating_def_epa"]
    # Phase 4 advanced groups: home-minus-away for every windowed team feature, plus matchups
    for c in [c[5:] for c in fs.columns if c.startswith("home_p4")]:
        new[f"diff_{c}"] = fs[f"home_{c}"] - fs[f"away_{c}"]
    pairs = {"pressure": ("p4pfr_blend_pfr_pressured_rate", "p4pfr_blend_def_pfr_def_pressure_rate"),
             "run_block": ("p4pfr_blend_pfr_ybc_per_carry", "p4pfr_blend_def_pfr_ybc_allowed"),
             "separation": ("p4ngs_blend_ngs_separation", "p4ngs_blend_def_ngs_separation_allowed")}
    for name, (o, d) in pairs.items():
        if f"home_{o}" in fs and f"away_{d}" in fs:
            new[f"p4mx_home_{name}"] = fs[f"home_{o}"] + fs[f"away_{d}"]
            new[f"p4mx_away_{name}"] = fs[f"away_{o}"] + fs[f"home_{d}"]
            new[f"p4mx_net_{name}"] = new[f"p4mx_home_{name}"] - new[f"p4mx_away_{name}"]
    if "away_travel_km" in fs:
        new["p3_away_travel_km"] = fs["away_travel_km"]
        new["p3_away_tz_shift"] = fs["away_tz_shift"]
        new["p3_away_body_clock_hour"] = fs["away_body_clock_hour"]
    # offense-vs-defense matchups: home offense against away defense, and vice versa
    for c in ("epa_pp", "pass_epa", "rush_epa", "sr", "pass_sr", "rush_sr", "explosive_rate"):
        new[f"mx_home_off_vs_def_{c}"] = fs[f"home_blend_{c}"] + fs[f"away_blend_d_{c}"]
        new[f"mx_away_off_vs_def_{c}"] = fs[f"away_blend_{c}"] + fs[f"home_blend_d_{c}"]
        new[f"mx_net_{c}"] = new[f"mx_home_off_vs_def_{c}"] - new[f"mx_away_off_vs_def_{c}"]
    new["mx_turnover_margin"] = (fs["home_blend_d_turnovers"] - fs["home_blend_turnovers"]) - (fs["away_blend_d_turnovers"] - fs["away_blend_turnovers"])
    new["mx_recent_form"] = (fs["home_l3_points"] - fs["home_l3_d_points"]) - (fs["away_l3_points"] - fs["away_l3_d_points"])
    new["mx_form_vs_season"] = ((fs["home_l3_epa_pp"] - fs["home_l3_d_epa_pp"]) - (fs["home_blend_epa_pp"] - fs["home_blend_d_epa_pp"])) - \
                              ((fs["away_l3_epa_pp"] - fs["away_l3_d_epa_pp"]) - (fs["away_blend_epa_pp"] - fs["away_blend_d_epa_pp"]))
    if "home_inj_report_available" in fs:
        skip = ("inj_report_time", "inj_source", "inj_report_available", "inj_final_published")
        for c in [c[5:] for c in fs.columns if c.startswith("home_inj_") and c[5:] not in skip]:
            new[f"diff_{c}"] = fs[f"home_{c}"] - fs[f"away_{c}"]
        new["inj_available"] = ((fs["home_inj_report_available"] == 1) & (fs["away_inj_report_available"] == 1)).astype(int)
        # availability x opponent-strength interactions (NaN when no verified report)
        new["inj_mx_home_ol_out_x_opp_pass_rush"] = fs["home_inj_out_OL"] * fs["away_blend_d_sack_rate"]
        new["inj_mx_away_ol_out_x_opp_pass_rush"] = fs["away_inj_out_OL"] * fs["home_blend_d_sack_rate"]
        new["inj_mx_home_db_out_x_opp_pass_off"] = (fs["home_inj_out_CB"] + fs["home_inj_out_S"]) * fs["away_blend_pass_epa"]
        new["inj_mx_away_db_out_x_opp_pass_off"] = (fs["away_inj_out_CB"] + fs["away_inj_out_S"]) * fs["home_blend_pass_epa"]
        new["inj_mx_home_dl_out_x_opp_rush_off"] = fs["home_inj_out_DL"] * fs["away_blend_rush_epa"]
        new["inj_mx_away_dl_out_x_opp_rush_off"] = fs["away_inj_out_DL"] * fs["home_blend_rush_epa"]
    new["feature_cutoff_utc"] = fs["kickoff_utc"]
    new["features_built_at"] = pd.Series(pd.Timestamp.now(tz="UTC"), index=fs.index)
    fs = pd.concat([fs, pd.DataFrame(new, index=fs.index)], axis=1)
    return fs.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


# --------------------------------------------------------------------------- feature groups

def feature_groups(columns) -> dict[str, list[str]]:
    cols = list(columns)
    core = ["epa_pp", "pass_epa", "rush_epa", "sr", "pass_sr", "rush_sr", "points", "turnovers",
            "explosive_rate", "sack_rate", "early_epa", "third_conv", "rz_td_rate",
            "d_epa_pp", "d_pass_epa", "d_rush_epa", "d_sr", "d_points", "d_turnovers", "d_explosive_rate", "d_sack_rate"]
    volume = ["pass_yds", "rush_yds", "total_yds", "pass_td", "rush_td", "plays", "sec_per_play", "pass_rate",
              "d_pass_yds", "d_rush_yds", "d_total_yds", "early_sr", "pass_sr", "d_pass_sr", "d_rush_sr", "d_third_conv", "d_rz_td_rate"]
    return {
        "Context (home field, rest, week, dome)": [c for c in cols if c.startswith("ctx_")],
        "Opponent-adjusted ratings": [c for c in cols if c in ("diff_rating_margin", "diff_rating_epa")],
        "Quarterback": [c for c in cols if c in ("diff_qb_eff", "diff_qb_log_exp") or
                        (c.startswith(("home_qb_", "away_qb_")) and c.split("_", 2)[2] in ("change", "projected_out", "questionable", "offseason"))],
        "Efficiency differences (blended season)": [f"diff_blend_{c}" for c in core if f"diff_blend_{c}" in cols],
        "Recent form differences (last 3 / last 5)": [f"diff_{w}_{c}" for w in ("l3", "l5") for c in core[:8] if f"diff_{w}_{c}" in cols],
        "Volume and pace differences": [f"diff_blend_{c}" for c in volume if f"diff_blend_{c}" in cols],
        "Offense-vs-defense matchups": [c for c in cols if c.startswith("mx_")],
        INJURY_GROUP: [c for c in cols if c.startswith(("diff_inj_", "inj_mx_")) or c == "inj_available"],
        PHASE3_GROUP: [c for c in cols if c.startswith("p3_")],
        **{name: [c for c in cols if c.startswith(pfx)] for name, pfx in P4_GROUPS.items()},
    }


P4_GROUPS = {
    "Phase 4: personnel & pressure (participation)": "diff_p4pers_",
    "Phase 4: Next Gen Stats": "diff_p4ngs_",
    "Phase 4: PFR advanced (pressure, contact, tackling)": "diff_p4pfr_",
    "Phase 4: roster experience, depth & continuity": "diff_p4roster_",
    "Phase 4: strength of schedule faced": "diff_p4sos_",
    "Phase 4: advanced matchups (pressure, run blocking, separation)": "p4mx_",
}
PHASE3_GROUP = "Phase 3 context (travel, time zone, coaching, opp-adjusted off/def EPA, OL churn)"
INJURY_GROUP = "Injury availability (verified pregame reports, 2016-2024 + lab archive)"

DEFAULT_GROUPS = (
    "Context (home field, rest, week, dome)", "Opponent-adjusted ratings", "Quarterback",
    "Efficiency differences (blended season)", "Recent form differences (last 3 / last 5)",
    "Offense-vs-defense matchups",
)


def select_features(columns, groups=DEFAULT_GROUPS) -> list[str]:
    fg = feature_groups(columns)
    out: list[str] = []
    for g in groups:
        out += [c for c in fg[g] if c not in out]
    return out


def feature_catalog(columns) -> pd.DataFrame:
    """Source, formula and pregame-availability statement for every feature."""
    desc = {
        "std": "season-to-date mean over this team's completed games this season before kickoff",
        "l3": "mean of the team's last 3 completed games before kickoff (may span seasons)",
        "l5": "mean of the team's last 5 completed games before kickoff (may span seasons)",
        "prev": "mean over the team's full previous season (complete before this season starts)",
        "blend": f"(n*season_to_date + {BLEND_K:g}*previous_season)/(n+{BLEND_K:g}), n = games played this season",
    }
    rows = []
    groups = feature_groups(columns)
    member = {c: g for g, cs in groups.items() for c in cs}
    for c in columns:
        if c in META_COLUMNS or c in ("neutral_site", "div_game", "roof_type", "feature_cutoff_utc", "features_built_at"):
            continue
        source, formula = "nflverse pbp + nfldata schedule", ""
        parts = c.split("_", 2)
        if c.startswith("ctx_"):
            source, formula = "nfldata schedule", "schedule-derived context (rest = days since previous game, capped 3-21; 14 for first game)"
        elif "rating" in c:
            source, formula = "nfldata scores + pbp", (f"ridge rating (lambda={RATING_RIDGE}) fit on games before the week's first kickoff; "
                                                      f"previous season weighted {RATING_PREV_WEIGHT}")
        elif "p4" in c:
            source, formula = ("nflverse participation / Next Gen Stats / PFR advanced weekly / snap counts + players",
                               "Phase 4: per team-game aggregate from earlier games only; blend = (n*season-to-date + 3*previous "
                               "season)/(n+3), l5 = last 5 games; def_ = what this team's defense allowed; NaN where the source "
                               "does not cover the season")
        elif c.startswith("p3_") or any(k in c for k in ("travel_km", "tz_shift", "body_clock", "coach_", "ol_churn", "rating_off", "rating_def")):
            source, formula = ("nfldata schedule (stadium, coaches) + static stadium geography + pbp + PFR snap counts",
                               "Phase 3: travel = great-circle km from the team's home stadium that season to the game site; "
                               "tz_shift / body_clock from stadium time zones at kickoff; coach tenure = earlier games coached "
                               "for the team; opp-adjusted off/def EPA = ridge fit on games before the week's first kickoff; "
                               "ol_churn_l4 = distinct OL with >=50% snaps in the team's last 4 completed games")
        elif "inj_" in c:
            source, formula = ("official NFL injury report via nflverse + PFR snap counts", "sum of listed players' mean snap share over "
                               "their last 4 games, by status (out = Out/Doubtful, q = Questionable) and position group; "
                               "starters_out counts players with share >= 0.5; NaN when no verified pre-kickoff report exists")
        elif "qb_" in c:
            source, formula = "pbp qb_epa + verified injury report", (f"PROJECTED starter (previous game's starter, replaced only if a verified "
                                                                      f"pregame report lists him Out/Doubtful); last {QB_WINDOW} dropbacks EPA shrunk "
                                                                      f"toward {QB_PRIOR_MEAN} with k={QB_PRIOR_K:g}. The actual starter is never used.")
        elif c.startswith("mx_"):
            formula = "offense-vs-defense combination of blended windows (see features.py)"
        elif parts[0] in ("home", "away", "diff") and len(parts) == 3 and parts[1] in desc:
            stat = parts[2]
            formula = f"{'home minus away of ' if parts[0] == 'diff' else ''}{stat} ({'allowed by defense' if stat.startswith('d_') else 'offense'}): {desc[parts[1]]}"
        rows.append({"feature": c, "group": member.get(c, "Feature store only"), "source": source, "formula": formula,
                     "pregame_available": "yes: built only from games with kickoff strictly before this game's kickoff"})
    excluded = [
        ("weather temp/wind", "nfldata games.csv", "EXCLUDED: recorded at game time, not a pregame forecast"),
        ("injury rows modified after kickoff", "nflverse injuries", "EXCLUDED: only rows available before kickoff are used"),
        ("2025 injury reports / 2026 weeks before archiving", "nflverse injuries", "EXCLUDED: no row timestamps; NaN + inj_available=0"),
        ("actual starting QB", "nfldata games.csv", "EXCLUDED from features: replaced by pregame projected starter"),
        ("game-day roof open/closed", "nfldata games.csv", "EXCLUDED: replaced by static stadium roof type"),
        ("depth charts 2016-2024", "nflverse depth_charts", "EXCLUDED: no publication timestamps"),
        ("ESPN injuries / ESPN depth charts", "ESPN public API", "LIVE MONITORING ONLY: never model inputs"),
        ("pressure rate", "FTN charting", "EXCLUDED: coverage only from 2022"),
        ("spread / moneyline / total", "nfldata games.csv", "EXCLUDED as features: closing lines without timestamps; benchmark only"),
    ]
    for f, s, why in excluded:
        rows.append({"feature": f, "group": "Not used", "source": s, "formula": "", "pregame_available": why})
    return pd.DataFrame(rows)
