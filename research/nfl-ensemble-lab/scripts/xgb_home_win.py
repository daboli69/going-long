"""XGBoost home-win classifier for NFL regular-season games.

Pipeline: load_data -> add_elo_pregame -> build_team_history ->
build_feature_matrix -> train_and_evaluate (time split) -> refit on every game
played before the target games -> predict_upcoming.

Data comes from the free api.nfldata.org JSON API (/v1/games), fetched
automatically on every run: no files to download. Completed seasons are cached
in data/cache/xgb_api_games/ after the first fetch; the current season is
re-fetched each run so new results and the remaining schedule are picked up.
Team codes are normalized to current franchise IDs (OAK->LV, SD->LAC, STL->LA)
by the lab's own lab.ingest.normalize_team. Neutral sites combine a stadium
check with ESPN's public scoreboard API neutralSite flag (the nfldata API lists
some international games, e.g. 2025, at the home team's own stadium).

Every feature is known before kickoff: Elo is recorded before the game's own
update, and rolling form is shifted so a game never sees its own result.
Rest days for upcoming games come from each team's most recent *played* game,
so they are exact for the next unplayed week and only estimates beyond it.

Usage:
  python scripts/xgb_home_win.py
  python scripts/xgb_home_win.py --refresh            # re-fetch every season
  python scripts/xgb_home_win.py --season 2026 --week 8
  python scripts/xgb_home_win.py --date 2026-10-29 --home LAC --away MIN
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from xgboost import XGBClassifier

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
from lab.ingest import normalize_team  # noqa: E402
from lab.sources import fetch_api_games  # noqa: E402

CACHE_DIR = LAB / "data" / "cache" / "xgb_api_games"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

# Modern era only: older rules and styles would only add noise.
START_SEASON = 2002

# Optional single matchup ("tomorrow's game"), by team code. None = score a whole week.
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


def current_season(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 3 else today.year - 1


def fetch_season(season: int, live: bool, refresh: bool = False) -> list[dict]:
    """One season of games from the API; completed seasons come from the local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{season}.json"
    if path.exists() and not live and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        rows = fetch_api_games(season, progress=lambda m: None)
    except (ConnectionError, FileNotFoundError) as exc:
        if path.exists():
            print(f"  warning: API fetch for {season} failed ({exc}); using cached copy")
            return json.loads(path.read_text(encoding="utf-8"))
        raise
    if not rows:
        raise RuntimeError(f"API returned no games for {season}")
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def fetch_espn_neutral(year: int, live: bool, refresh: bool = False) -> list[dict]:
    """ESPN neutral-site regular-season games kicking off in calendar `year`."""
    path = CACHE_DIR / f"espn_neutral_{year}.json"
    if path.exists() and not live and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    url = f"{ESPN_SCOREBOARD}?dates={year}&seasontype=2&limit=1000"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        events = json.load(resp)["events"]
    rows = []
    for e in events:
        comp = e["competitions"][0]
        if not comp.get("neutralSite"):
            continue
        try:
            teams = sorted(normalize_team(c["team"]["abbreviation"]) for c in comp["competitors"])
        except ValueError:  # all-star style events
            continue
        rows.append({"teams": teams, "date": e["date"][:10], "venue": comp.get("venue", {}).get("fullName")})
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def espn_neutral_games(start_season: int, live: int, refresh: bool) -> list[dict]:
    rows = []
    for year in range(start_season, live + 2):
        try:
            rows += fetch_espn_neutral(year, live=year >= live, refresh=refresh)
        except Exception as exc:  # optional source: the stadium check still runs
            print(f"  warning: ESPN neutral-site fetch for {year} failed ({exc})")
    return rows


def load_data(start_season: int = START_SEASON, refresh: bool = False) -> pd.DataFrame:
    """API games -> one clean, time-ordered row per regular-season game."""
    live = current_season()
    print(f"Fetching seasons {start_season}-{live} from api.nfldata.org ...")
    raw = pd.DataFrame([r for s in range(start_season, live + 1)
                        for r in fetch_season(s, live=(s == live), refresh=refresh)])

    df = raw[raw["game_type"] == "REG"].copy()  # drops playoff games
    df["date"] = pd.to_datetime(df["gameday"])
    df["season"] = df["season"].astype(int)
    df = df[df["season"] >= start_season]
    df["home_id"] = df["home_team"].map(normalize_team)  # raises on an unknown code
    df["away_id"] = df["away_team"].map(normalize_team)
    df["week"] = df["week"].astype(int)

    # The API has no neutral-site flag: a game is neutral when it is not at the
    # home team's usual stadium that season, or when ESPN flags it neutral.
    usual = df.groupby(["season", "home_id"])["stadium"].agg(lambda x: x.mode().iat[0])
    off_home = df["stadium"].to_numpy() != usual.loc[list(zip(df["season"], df["home_id"]))].to_numpy()
    espn = {}
    for r in espn_neutral_games(start_season, live, refresh):
        espn.setdefault(tuple(r["teams"]), []).append(pd.Timestamp(r["date"]))
    espn_flag = [any(abs((d - t).days) <= 1 for t in espn.get(tuple(sorted((h, a))), []))
                 for d, h, a in zip(df["date"], df["home_id"], df["away_id"])]
    df["neutral"] = (off_home | np.array(espn_flag, dtype=bool)).astype(int)

    df["score_home"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["score_away"] = pd.to_numeric(df["away_score"], errors="coerce")
    df["played"] = df["score_home"].notna() & df["score_away"].notna()
    df["tie"] = df["played"] & (df["score_home"] == df["score_away"])
    # Target. NaN for unplayed games; ties are kept for Elo/form but not trained on.
    df["y_home_win"] = np.where(df["played"], (df["score_home"] > df["score_away"]).astype(float), np.nan)

    for season, g in df.groupby("season"):
        expected = 272 if season >= 2021 else 256
        expected -= season == 2022  # BUF-CIN week 17 was canceled, never replayed
        if len(g) != expected:
            print(f"  warning: {season} has {len(g)} regular-season games, expected {expected}")

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


def build_feature_matrix(games: pd.DataFrame, hist: pd.DataFrame, return_ids: bool = False):
    """One row per played, non-tied game: X, y, season, date (and game_id if return_ids)."""
    form = hist[["game_id", "team"] + FORM_COLS]
    df = games[games["played"] & ~games["tie"]]
    df = df.merge(form.rename(columns={"team": "home_id", **{c: f"home_{c}" for c in FORM_COLS}}),
                  on=["game_id", "home_id"], how="left")
    df = df.merge(form.rename(columns={"team": "away_id", **{c: f"away_{c}" for c in FORM_COLS}}),
                  on=["game_id", "away_id"], how="left")
    out = (_matchup_features(df), df["y_home_win"].astype(int), df["season"], df["date"])
    return out + (df["game_id"],) if return_ids else out


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
    ap.add_argument("--refresh", action="store_true", help="re-fetch cached completed seasons too")
    ap.add_argument("--start-season", type=int, default=START_SEASON)
    ap.add_argument("--test-start", type=int, help="first test season (default: latest season with results minus one)")
    ap.add_argument("--season", type=int)
    ap.add_argument("--week", type=int)
    ap.add_argument("--date", default=GAME_DATE)
    ap.add_argument("--home", default=HOME_TEAM)
    ap.add_argument("--away", default=AWAY_TEAM)
    ap.add_argument("--out", type=Path, help="optional CSV of predictions")
    args = ap.parse_args()

    games = load_data(args.start_season, args.refresh)
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
