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
                         "rating_epa": r["epa_margin_ratings"][team] if r else np.nan})
    return pd.DataFrame(rows)


def qb_pregame(games: pd.DataFrame, qb_games: pd.DataFrame) -> pd.DataFrame:
    """Starting-QB trailing efficiency (shrunk EPA/dropback) and QB-change flag."""
    kick = games.set_index("game_id")["kickoff_utc"]
    q = qb_games.copy()
    q["kickoff_utc"] = q["game_id"].map(kick)
    q = q.dropna(subset=["kickoff_utc"]).sort_values(["qb_id", "kickoff_utc"])
    # trailing sums over the last QB_WINDOW dropbacks, approximated game-wise
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
    st = pd.DataFrame(states, columns=["qb_id", "kickoff_utc", "qb_eff", "qb_career_db"])
    rows = []
    for side in ("home", "away"):
        t = games[["game_id", "kickoff_utc"]].copy()
        t["team"] = games[f"{side}_team"].values
        t["qb_id"] = games[f"{side}_qb_id"].values
        rows.append(t)
    t = pd.concat(rows, ignore_index=True).sort_values(["team", "kickoff_utc"])
    t["qb_known"] = t["qb_id"].notna().astype(int)
    prev_qb = t.groupby("team")["qb_id"].shift(1)
    t["qb_change"] = ((t["qb_id"] != prev_qb) & prev_qb.notna() & t["qb_id"].notna()).astype(int)
    known = t[t["qb_id"].notna()]
    m = _asof(known, st, "qb_id", ["qb_eff", "qb_career_db"])
    t = t.merge(m[["game_id", "team", "qb_eff", "qb_career_db"]], on=["game_id", "team"], how="left")
    t["qb_eff"] = t["qb_eff"].where(t["qb_id"].isna(), t["qb_eff"].fillna(QB_PRIOR_MEAN))
    t["qb_career_db"] = t["qb_career_db"].fillna(0)
    t["qb_log_exp"] = np.log1p(t["qb_career_db"])
    return t[["game_id", "team", "qb_known", "qb_change", "qb_eff", "qb_log_exp"]]


META_COLUMNS = [
    "game_id", "season", "week", "game_type", "gameday", "kickoff_utc", "home_team", "away_team",
    "completed", "home_score", "away_score", "margin", "home_win", "tie", "spread_line", "total_line",
    "home_moneyline", "away_moneyline", "market_p_home_novig", "home_qb_name", "away_qb_name",
]


def build_feature_store(games: pd.DataFrame, tstats: pd.DataFrame, qb_games: pd.DataFrame) -> pd.DataFrame:
    long = _team_game_long(games, tstats)
    team_state = team_pregame_states(games, long)
    rest = _rest_days(games)
    ratings = opponent_adjusted_ratings(games, long)
    qb = qb_pregame(games, qb_games)
    per_team = (team_state.drop(columns=["season", "kickoff_utc"])
                .merge(rest, on=["game_id", "team"], how="left")
                .merge(ratings, on=["game_id", "team"], how="left")
                .merge(qb, on=["game_id", "team"], how="left"))
    team_cols = [c for c in per_team.columns if c not in ("game_id", "team")]
    fs = games[META_COLUMNS + ["neutral_site", "div_game", "roof"]].copy()
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
    new["ctx_dome"] = fs["roof"].isin(["dome", "closed"]).astype(int)
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
    # offense-vs-defense matchups: home offense against away defense, and vice versa
    for c in ("epa_pp", "pass_epa", "rush_epa", "sr", "pass_sr", "rush_sr", "explosive_rate"):
        new[f"mx_home_off_vs_def_{c}"] = fs[f"home_blend_{c}"] + fs[f"away_blend_d_{c}"]
        new[f"mx_away_off_vs_def_{c}"] = fs[f"away_blend_{c}"] + fs[f"home_blend_d_{c}"]
        new[f"mx_net_{c}"] = new[f"mx_home_off_vs_def_{c}"] - new[f"mx_away_off_vs_def_{c}"]
    new["mx_turnover_margin"] = (fs["home_blend_d_turnovers"] - fs["home_blend_turnovers"]) - (fs["away_blend_d_turnovers"] - fs["away_blend_turnovers"])
    new["mx_recent_form"] = (fs["home_l3_points"] - fs["home_l3_d_points"]) - (fs["away_l3_points"] - fs["away_l3_d_points"])
    new["mx_form_vs_season"] = ((fs["home_l3_epa_pp"] - fs["home_l3_d_epa_pp"]) - (fs["home_blend_epa_pp"] - fs["home_blend_d_epa_pp"])) - \
                              ((fs["away_l3_epa_pp"] - fs["away_l3_d_epa_pp"]) - (fs["away_blend_epa_pp"] - fs["away_blend_d_epa_pp"]))
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
        "Quarterback": [c for c in cols if c in ("diff_qb_eff", "diff_qb_log_exp", "home_qb_change", "away_qb_change")],
        "Efficiency differences (blended season)": [f"diff_blend_{c}" for c in core if f"diff_blend_{c}" in cols],
        "Recent form differences (last 3 / last 5)": [f"diff_{w}_{c}" for w in ("l3", "l5") for c in core[:8] if f"diff_{w}_{c}" in cols],
        "Volume and pace differences": [f"diff_blend_{c}" for c in volume if f"diff_blend_{c}" in cols],
        "Offense-vs-defense matchups": [c for c in cols if c.startswith("mx_")],
    }


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
        if c in META_COLUMNS or c in ("neutral_site", "div_game", "roof", "feature_cutoff_utc", "features_built_at"):
            continue
        source, formula = "nflverse pbp + nfldata schedule", ""
        parts = c.split("_", 2)
        if c.startswith("ctx_"):
            source, formula = "nfldata schedule", "schedule-derived context (rest = days since previous game, capped 3-21; 14 for first game)"
        elif "rating" in c:
            source, formula = "nfldata scores + pbp", (f"ridge rating (lambda={RATING_RIDGE}) fit on games before the week's first kickoff; "
                                                      f"previous season weighted {RATING_PREV_WEIGHT}")
        elif "qb_" in c:
            source, formula = "nfldata starting QB + pbp qb_epa", (f"starter's last {QB_WINDOW} dropbacks EPA, shrunk toward {QB_PRIOR_MEAN} "
                                                                   f"with k={QB_PRIOR_K:g}; starter identity is the listed/actual starter")
        elif c.startswith("mx_"):
            formula = "offense-vs-defense combination of blended windows (see features.py)"
        elif parts[0] in ("home", "away", "diff") and len(parts) == 3 and parts[1] in desc:
            stat = parts[2]
            formula = f"{'home minus away of ' if parts[0] == 'diff' else ''}{stat} ({'allowed by defense' if stat.startswith('d_') else 'offense'}): {desc[parts[1]]}"
        rows.append({"feature": c, "group": member.get(c, "Feature store only"), "source": source, "formula": formula,
                     "pregame_available": "yes: built only from games with kickoff strictly before this game's kickoff"})
    excluded = [
        ("weather temp/wind", "nfldata games.csv", "EXCLUDED: recorded at game time, not a pregame forecast"),
        ("injuries", "nflverse injuries", "EXCLUDED: report modification dates can postdate kickoff"),
        ("pressure rate", "FTN charting", "EXCLUDED: coverage only from 2022"),
        ("spread / moneyline / total", "nfldata games.csv", "EXCLUDED as features: closing lines without timestamps; benchmark only"),
    ]
    for f, s, why in excluded:
        rows.append({"feature": f, "group": "Not used", "source": s, "formula": "", "pregame_available": why})
    return pd.DataFrame(rows)
