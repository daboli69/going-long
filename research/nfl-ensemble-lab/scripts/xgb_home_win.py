"""XGBoost home-win classifier for NFL regular-season games.

Pipeline: load_data -> add_elo_pregame -> build_team_history ->
build_feature_matrix -> train_and_evaluate (time split) -> refit on every game
played before the target games -> predict_upcoming.

Inputs are the Kaggle "spreadspoke" tables:
  scores: schedule_date, schedule_season, schedule_week, schedule_playoff,
          team_home, score_home, score_away, team_away, stadium_neutral, ...
          (future games are rows with blank scores)
  teams:  team_name, team_id  (maps every historical name to one stable ID)

Every feature is known before kickoff: Elo is recorded before the game's own
update, and rolling form is shifted so a game never sees its own result.
Rest days for upcoming games come from each team's most recent *played* game,
so they are exact for the next unplayed week and only estimates beyond it.

Usage:
  python scripts/xgb_home_win.py
  python scripts/xgb_home_win.py --scores path/to/scores.csv --teams path/to/teams.csv
  python scripts/xgb_home_win.py --season 2026 --week 8
  python scripts/xgb_home_win.py --date 2026-10-29 --home LAC --away MIN
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from xgboost import XGBClassifier

LAB = Path(__file__).resolve().parents[1]
SCORES_PATH = LAB / "data" / "spreadspoke_scores.csv"
TEAMS_PATH = LAB / "data" / "nfl_teams.csv"

# Modern era only: older rules and styles would only add noise.
START_SEASON = 2002

# Optional single matchup ("tomorrow's game"), by team_id. None = score a whole week.
GAME_DATE = None  # e.g. "2026-10-29"
HOME_TEAM = None  # e.g. "LAC"
AWAY_TEAM = None  # e.g. "MIN"

ELO_START = 1500.0
ELO_K = 20.0
ELO_HFA = 55.0          # home-field advantage in Elo points
ELO_REVERT = 1.0 / 3.0  # share of each rating pulled back to 1500 between seasons
REST_CAP = 21           # season openers and byes beyond this look alike

STATS = ["win", "margin", "pf", "pa"]
FEATURES = (
    ["elo_diff", "elo_prob_home", "neutral", "week", "rest_diff", "home_rest", "away_rest",
     "home_std_games", "away_std_games"]
    + [f"std_{s}_diff" for s in STATS]
    + [f"l5_{s}_diff" for s in STATS]
)

XGB_PARAMS = dict(
    n_estimators=300,
    max_depth=3,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=5,
    reg_lambda=1.0,
    eval_metric="logloss",
    random_state=42,
)


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper().isin(["TRUE", "1", "YES"])


def load_data(scores_path=SCORES_PATH, teams_path=TEAMS_PATH, start_season=START_SEASON) -> pd.DataFrame:
    """Raw CSVs -> one clean, time-ordered row per regular-season game."""
    scores = pd.read_csv(scores_path)
    teams = pd.read_csv(teams_path)

    df = scores.copy()
    df["date"] = pd.to_datetime(df["schedule_date"])
    df["season"] = pd.to_numeric(df["schedule_season"]).astype(int)
    df = df[(df["season"] >= start_season) & ~_truthy(df["schedule_playoff"])].copy()

    name_to_id = dict(zip(teams["team_name"], teams["team_id"]))
    df["home_id"] = df["team_home"].map(name_to_id)
    df["away_id"] = df["team_away"].map(name_to_id)
    missing = sorted(set(df.loc[df["home_id"].isna(), "team_home"]) | set(df.loc[df["away_id"].isna(), "team_away"]))
    if missing:
        raise ValueError(f"Team names missing from {teams_path}: {missing}")

    df["week"] = pd.to_numeric(df["schedule_week"], errors="coerce")
    df["neutral"] = _truthy(df["stadium_neutral"]).astype(int) if "stadium_neutral" in df else 0
    df["score_home"] = pd.to_numeric(df["score_home"], errors="coerce")
    df["score_away"] = pd.to_numeric(df["score_away"], errors="coerce")
    df["played"] = df["score_home"].notna() & df["score_away"].notna()
    df["tie"] = df["played"] & (df["score_home"] == df["score_away"])
    # Target. NaN for unplayed games; ties are kept for Elo/form but not trained on.
    df["y_home_win"] = np.where(df["played"], (df["score_home"] > df["score_away"]).astype(float), np.nan)

    df = df.sort_values(["date", "home_id"]).reset_index(drop=True)
    df["game_id"] = df.index
    cols = ["game_id", "date", "season", "week", "home_id", "away_id", "neutral",
            "score_home", "score_away", "played", "tie", "y_home_win"]
    return df[cols]


def add_elo_pregame(games: pd.DataFrame):
    """Record each side's Elo before kickoff, then update only once the result is known."""
    ratings: dict[str, float] = {}
    season = None
    home_elo = np.empty(len(games))
    away_elo = np.empty(len(games))

    for i, g in enumerate(games.itertuples(index=False)):
        if g.season != season:
            ratings = {t: ELO_START + (1 - ELO_REVERT) * (r - ELO_START) for t, r in ratings.items()}
            season = g.season
        h = ratings.get(g.home_id, ELO_START)
        a = ratings.get(g.away_id, ELO_START)
        home_elo[i], away_elo[i] = h, a
        if not g.played:
            continue

        gap = h + (0 if g.neutral else ELO_HFA) - a
        expected = 1 / (1 + 10 ** (-gap / 400))
        margin = g.score_home - g.score_away
        actual = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        if margin == 0:
            mult = 1.0
        else:
            winner_gap = gap if margin > 0 else -gap
            mult = np.log(abs(margin) + 1) * 2.2 / (winner_gap * 0.001 + 2.2)
        delta = ELO_K * mult * (actual - expected)
        ratings[g.home_id] = h + delta
        ratings[g.away_id] = a - delta

    games = games.copy()
    games["home_elo"] = home_elo
    games["away_elo"] = away_elo
    hfa = np.where(games["neutral"] == 1, 0.0, ELO_HFA)
    games["elo_prob_home"] = 1 / (1 + 10 ** (-(games["home_elo"] + hfa - games["away_elo"]) / 400))
    return games, ratings


def build_team_history(games: pd.DataFrame) -> pd.DataFrame:
    """Two rows per played game (one per team) with pregame rolling form.

    shift(1) keeps each row's own result out of its features.
    std_* = season to date; l5_* = last five games (may span seasons).
    """
    played = games[games["played"]]
    home = pd.DataFrame({"game_id": played["game_id"], "date": played["date"], "season": played["season"],
                         "team": played["home_id"], "pf": played["score_home"], "pa": played["score_away"]})
    away = pd.DataFrame({"game_id": played["game_id"], "date": played["date"], "season": played["season"],
                         "team": played["away_id"], "pf": played["score_away"], "pa": played["score_home"]})
    hist = pd.concat([home, away]).sort_values(["team", "date", "game_id"]).reset_index(drop=True)
    hist["margin"] = hist["pf"] - hist["pa"]
    hist["win"] = (hist["margin"] > 0).astype(float) + 0.5 * (hist["margin"] == 0)

    by_team = hist.groupby("team")
    by_team_season = hist.groupby(["team", "season"])
    hist["rest"] = by_team["date"].diff().dt.days.clip(upper=REST_CAP)
    hist["std_games"] = by_team_season.cumcount()
    for s in STATS:
        hist[f"std_{s}"] = by_team_season[s].transform(lambda x: x.shift(1).expanding().mean())
        hist[f"l5_{s}"] = by_team[s].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    return hist


FORM_COLS = ["rest", "std_games"] + [f"std_{s}" for s in STATS] + [f"l5_{s}" for s in STATS]


def _matchup_features(df: pd.DataFrame) -> pd.DataFrame:
    """home_*/away_* columns -> model features (home minus away), in training order."""
    out = pd.DataFrame(index=df.index)
    out["elo_diff"] = df["home_elo"] - df["away_elo"]
    out["elo_prob_home"] = df["elo_prob_home"]
    out["neutral"] = df["neutral"]
    out["week"] = df["week"]
    out["home_rest"] = df["home_rest"]
    out["away_rest"] = df["away_rest"]
    out["rest_diff"] = df["home_rest"] - df["away_rest"]
    out["home_std_games"] = df["home_std_games"]
    out["away_std_games"] = df["away_std_games"]
    for s in STATS:
        out[f"std_{s}_diff"] = df[f"home_std_{s}"] - df[f"away_std_{s}"]
        out[f"l5_{s}_diff"] = df[f"home_l5_{s}"] - df[f"away_l5_{s}"]
    return out[FEATURES].astype(float)


def build_feature_matrix(games: pd.DataFrame, hist: pd.DataFrame):
    """One row per played, non-tied game: X, y, season, date."""
    form = hist[["game_id", "team"] + FORM_COLS]
    df = games[games["played"] & ~games["tie"]]
    df = df.merge(form.rename(columns={"team": "home_id", **{c: f"home_{c}" for c in FORM_COLS}}),
                  on=["game_id", "home_id"], how="left")
    df = df.merge(form.rename(columns={"team": "away_id", **{c: f"away_{c}" for c in FORM_COLS}}),
                  on=["game_id", "away_id"], how="left")
    return _matchup_features(df), df["y_home_win"].astype(int), df["season"], df["date"]


def _report(name: str, y, p) -> None:
    print(f"  {name:<18} log loss {log_loss(y, p, labels=[0, 1]):.4f}  "
          f"Brier {brier_score_loss(y, p):.4f}  "
          f"accuracy {accuracy_score(y, (p >= 0.5).astype(int)):.3f}  "
          f"ROC AUC {roc_auc_score(y, p) if len(set(y)) > 1 else float('nan'):.4f}")


def train_and_evaluate(X, y, seasons, test_start: int) -> XGBClassifier:
    """Train on older seasons, test on newer ones. No shuffling."""
    train, test = seasons < test_start, seasons >= test_start
    if not train.any() or not test.any():
        raise ValueError(f"Time split at {test_start} leaves an empty train or test set")
    model = XGBClassifier(**XGB_PARAMS).fit(X[train], y[train])
    p = model.predict_proba(X[test])[:, 1]

    print(f"Train seasons {seasons[train].min()}-{seasons[train].max()} ({train.sum()} games); "
          f"test seasons {seasons[test].min()}-{seasons[test].max()} ({test.sum()} games)")
    _report("XGBoost", y[test], p)
    _report("Elo only", y[test], X.loc[test, "elo_prob_home"].to_numpy())
    _report("Home base rate", y[test], np.full(test.sum(), y[train].mean()))
    return model


def team_form_asof(hist: pd.DataFrame, team: str, date: pd.Timestamp, season: int) -> dict:
    """Same form numbers as build_team_history, from games played before `date`."""
    prior = hist[(hist["team"] == team) & (hist["date"] < date)].sort_values(["date", "game_id"])
    this_season = prior[prior["season"] == season]
    form = {"std_games": float(len(this_season)),
            "rest": float(min((date - prior["date"].iloc[-1]).days, REST_CAP)) if len(prior) else np.nan}
    for s in STATS:
        form[f"std_{s}"] = this_season[s].mean() if len(this_season) else np.nan
        form[f"l5_{s}"] = prior[s].tail(5).mean() if len(prior) else np.nan
    return form


def predict_upcoming(model: XGBClassifier, games: pd.DataFrame, hist: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """One feature row per scheduled game -> home and away win probability."""
    rows = []
    for g in targets.itertuples(index=False):
        row = {"home_elo": g.home_elo, "away_elo": g.away_elo, "elo_prob_home": g.elo_prob_home,
               "neutral": g.neutral, "week": g.week}
        for side, team in (("home", g.home_id), ("away", g.away_id)):
            for k, v in team_form_asof(hist, team, g.date, g.season).items():
                row[f"{side}_{k}"] = v
        rows.append(row)
    X = _matchup_features(pd.DataFrame(rows, index=targets.index))
    out = targets[["season", "week", "date", "home_id", "away_id"]].copy()
    out["p_home"] = model.predict_proba(X[FEATURES])[:, 1]
    out["p_away"] = 1 - out["p_home"]
    return out


def select_targets(games: pd.DataFrame, args) -> pd.DataFrame:
    """Locate the scheduled rows to predict."""
    upcoming = games[~games["played"]]
    if args.home or args.away or args.date:
        if not (args.home and args.away and args.date):
            raise SystemExit("--date, --home and --away go together")
        hit = upcoming[(upcoming["date"] == pd.Timestamp(args.date))
                       & (upcoming["home_id"] == args.home) & (upcoming["away_id"] == args.away)]
        if hit.empty:
            raise SystemExit(f"No unplayed scheduled game {args.away} @ {args.home} on {args.date}")
        return hit
    if upcoming.empty:
        raise SystemExit("No unplayed games in the scores file")
    season = args.season or int(upcoming["season"].max())
    upcoming = upcoming[upcoming["season"] == season]
    week = args.week or upcoming["week"].min()
    hit = upcoming[upcoming["week"] == week]
    if hit.empty:
        raise SystemExit(f"No unplayed games for season {season} week {week}")
    return hit


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scores", type=Path, default=SCORES_PATH)
    ap.add_argument("--teams", type=Path, default=TEAMS_PATH)
    ap.add_argument("--start-season", type=int, default=START_SEASON)
    ap.add_argument("--test-start", type=int, help="first test season (default: latest season with results minus one)")
    ap.add_argument("--season", type=int)
    ap.add_argument("--week", type=int)
    ap.add_argument("--date", default=GAME_DATE)
    ap.add_argument("--home", default=HOME_TEAM)
    ap.add_argument("--away", default=AWAY_TEAM)
    ap.add_argument("--out", type=Path, help="optional CSV of predictions")
    args = ap.parse_args()

    games = load_data(args.scores, args.teams, args.start_season)
    games, _ = add_elo_pregame(games)
    hist = build_team_history(games)
    X, y, seasons, dates = build_feature_matrix(games, hist)

    targets = select_targets(games, args)
    cutoff = targets["date"].min()
    before = (dates < cutoff).to_numpy()
    X, y, seasons = X[before].reset_index(drop=True), y[before].reset_index(drop=True), seasons[before].reset_index(drop=True)

    test_start = args.test_start or int(seasons.max()) - 1
    print("== Time-split evaluation ==")
    train_and_evaluate(X, y, seasons, test_start)

    print(f"\n== Refit on {len(y)} games played before {cutoff.date()} ==")
    model = XGBClassifier(**XGB_PARAMS).fit(X, y)
    preds = predict_upcoming(model, games, hist, targets)
    for p in preds.itertuples(index=False):
        pick, prob = (p.home_id, p.p_home) if p.p_home >= 0.5 else (p.away_id, p.p_away)
        print(f"  {p.season} wk {p.week:g} {p.date.date()}  {p.away_id} @ {p.home_id}: "
              f"{p.home_id} {p.p_home:.1%} / {p.away_id} {p.p_away:.1%}  -> {pick} wins ({prob:.1%})")
    if args.out:
        preds.to_csv(args.out, index=False)
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
