"""Halftime model: second-half totals, margins and player stats from first-half play-by-play.

Pre-registration: docs/HALFTIME_PREREG.md. Second half includes overtime, as books settle it.

    python -m lab.halftime build                      # rebuild the game and player tables
    python -m lab.halftime fit                        # fit on 2012-2022, spread from 2023-2024
    python -m lab.halftime eval --split validation    # score against the simple rule
    python -m lab.halftime predict --season 2026 --week 9
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "cache" / "halftime"
ARTIFACT = ROOT / "artifacts" / "halftime"
REPORT = ROOT / "reports" / "halftime"
LINES = RAW / "halftime_lines"

FIT = range(2012, 2023)
VALIDATION = (2023, 2024)
TEST = (2025,)
HOLDOUT = (2026,)   # Weeks 1 to 9 stay unscored until a later registered look
WINDOW = 8          # earlier games behind a player's trailing average
BINS = 10           # forecast-size bins for the spread of player outcomes
CALL = 0.55         # an "over" or "under" call needs at least this probability

PBP_COLS = ["game_id", "season", "week", "season_type", "qtr", "game_seconds_remaining", "posteam", "home_team", "away_team",
            "total_home_score", "total_away_score", "home_score", "away_score", "spread_line", "total_line", "pass_attempt",
            "rush_attempt", "qb_kneel", "complete_pass", "sack", "yards_gained", "receiving_yards", "rushing_yards",
            "receiver_player_id", "rusher_player_id", "receiver_player_name", "rusher_player_name", "epa"]

GAME_TARGETS = {"h2_total": ("total_line", "h1_total"), "h2_margin": ("spread_line", "h1_margin")}
PLAYER_TARGETS = {"h2_rec_yds": ("pre_rec_yds", "h1_rec_yds", "rec"), "h2_rec": ("pre_rec", "h1_rec", "rec"),
                  "h2_rush_yds": ("pre_rush_yds", "h1_rush_yds", "rush")}
GAME_FEATURES = ["spread_line", "total_line", "h1_home", "h1_away", "h1_total", "h1_margin", "home_receives_h2",
                 "home_h1_pass", "home_h1_rush", "home_h1_yards", "home_h1_epa", "away_h1_pass", "away_h1_rush", "away_h1_yards", "away_h1_epa"]
PLAYER_FEATURES = ["h1_tgt", "h1_rec", "h1_rec_yds", "h1_car", "h1_rush_yds", "h1_q2_touches", "h1_since_touch", "tgt_share", "car_share",
                   "pre_tgt", "pre_rec", "pre_rec_yds", "pre_car", "pre_rush_yds", "pre_h2_rec_yds", "pre_h2_rec", "pre_h2_rush_yds", "pre_games",
                   "team_h1_pass", "team_h1_rush", "team_h1_margin", "team_spread", "total_line", "home", "receives_h2"]


# --------------------------------------------------------------------------- tables

def load_plays(seasons) -> pd.DataFrame:
    frames = []
    for s in seasons:
        path = RAW / f"play_by_play_{s}.parquet"
        if path.exists():
            d = pd.read_parquet(path, columns=PBP_COLS)
            frames.append(d[d["season_type"] == "REG"])
    return pd.concat(frames, ignore_index=True)


def game_rows(p: pd.DataFrame) -> pd.DataFrame:
    """One row per game, built from quarters 1 and 2 and the pregame line only."""
    h1 = p[p.qtr <= 2]
    g = p.groupby("game_id").agg(season=("season", "first"), week=("week", "first"), home_team=("home_team", "first"),
                                 away_team=("away_team", "first"), spread_line=("spread_line", "first"), total_line=("total_line", "first"),
                                 home_final=("home_score", "first"), away_final=("away_score", "first"), last_qtr=("qtr", "max"))
    g = g.join(h1.groupby("game_id").agg(h1_home=("total_home_score", "max"), h1_away=("total_away_score", "max")))
    g["h1_total"] = g.h1_home + g.h1_away
    g["h1_margin"] = g.h1_home - g.h1_away
    # nflfastR lists the receiving team as the possession team on a kickoff.
    first_q3 = p[(p.qtr == 3) & p.posteam.notna()].groupby("game_id").posteam.first()
    g["home_receives_h2"] = (first_q3.reindex(g.index) == g.home_team).astype(float)
    off = h1[h1.posteam.notna()].assign(is_home=lambda d: d.posteam == d.home_team)
    stats = off.groupby(["game_id", "is_home"]).agg(h1_pass=("pass_attempt", "sum"), h1_rush=("rush_attempt", "sum"),
                                                     h1_yards=("yards_gained", "sum"), h1_epa=("epa", "sum")).unstack()
    for stat in ("h1_pass", "h1_rush", "h1_yards", "h1_epa"):
        g[f"home_{stat}"] = stats[(stat, True)].reindex(g.index)
        g[f"away_{stat}"] = stats[(stat, False)].reindex(g.index)
    g["h2_total"] = g.home_final + g.away_final - g.h1_total
    g["h2_margin"] = g.home_final - g.away_final - g.h1_margin
    return g[g.last_qtr >= 4].drop(columns="last_qtr").reset_index()


def touches(p: pd.DataFrame) -> pd.DataFrame:
    """Targets and carries, one row per play and player."""
    rec = p[(p.pass_attempt == 1) & (p.sack == 0) & p.receiver_player_id.notna()]
    rec = pd.DataFrame({"game_id": rec.game_id, "player_id": rec.receiver_player_id, "name": rec.receiver_player_name, "team": rec.posteam,
                        "qtr": rec.qtr, "left": rec.game_seconds_remaining, "tgt": 1, "rec": rec.complete_pass.fillna(0),
                        "rec_yds": rec.receiving_yards.fillna(0), "car": 0, "rush_yds": 0.0})
    run = p[(p.rush_attempt == 1) & (p.qb_kneel == 0) & p.rusher_player_id.notna()]
    run = pd.DataFrame({"game_id": run.game_id, "player_id": run.rusher_player_id, "name": run.rusher_player_name, "team": run.posteam,
                        "qtr": run.qtr, "left": run.game_seconds_remaining, "tgt": 0, "rec": 0.0, "rec_yds": 0.0, "car": 1,
                        "rush_yds": run.rushing_yards.fillna(0)})
    return pd.concat([rec, run], ignore_index=True)


def player_rows(p: pd.DataFrame, games: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
    """One row per player with a first-half target or carry. Later plays feed targets and later games' history only. keep_all keeps players without one, for trailing averages."""
    t = touches(p)
    t["half"] = np.where(t.qtr <= 2, "h1", "h2")
    stats = ["tgt", "rec", "rec_yds", "car", "rush_yds"]
    wide = t.pivot_table(index=["game_id", "player_id", "team"], columns="half", values=stats, aggfunc="sum", fill_value=0)
    wide.columns = [f"{half}_{stat}" for stat, half in wide.columns]
    wide = wide.reset_index()
    first = t[t.half == "h1"].groupby(["game_id", "player_id"]).agg(
        name=("name", "first"), last_left=("left", "min"), h1_q2_touches=("qtr", lambda q: int((q == 2).sum())))
    wide = wide.merge(first.reset_index(), on=["game_id", "player_id"], how="left")
    wide["h1_since_touch"] = wide.last_left - 1800
    g = games.set_index("game_id")
    wide = wide.join(g[["season", "week", "home_team", "spread_line", "total_line", "h1_margin", "home_receives_h2"]], on="game_id", how="inner")
    wide["home"] = (wide.team == wide.home_team).astype(float)
    sign = np.where(wide.home == 1, 1.0, -1.0)
    wide["team_h1_margin"] = sign * wide.h1_margin
    wide["team_spread"] = sign * wide.spread_line
    wide["receives_h2"] = np.where(wide.home == 1, wide.home_receives_h2, 1 - wide.home_receives_h2)
    team = wide.groupby(["game_id", "team"]).agg(team_h1_pass=("h1_tgt", "sum"), team_h1_rush=("h1_car", "sum")).reset_index()
    wide = wide.merge(team, on=["game_id", "team"])
    wide["tgt_share"] = wide.h1_tgt / wide.team_h1_pass.clip(lower=1)
    wide["car_share"] = wide.h1_car / wide.team_h1_rush.clip(lower=1)
    # Trailing averages over the player's earlier games; shift(1) keeps the current game out.
    wide = wide.sort_values(["player_id", "season", "week"]).reset_index(drop=True)
    by = wide.groupby("player_id")
    for stat in stats:
        full = wide[f"h1_{stat}"] + wide[f"h2_{stat}"]
        wide[f"pre_{stat}"] = full.groupby(wide.player_id).transform(lambda s: s.shift(1).rolling(WINDOW, min_periods=1).mean())
    for stat in ("rec_yds", "rec", "rush_yds"):
        wide[f"pre_h2_{stat}"] = by[f"h2_{stat}"].transform(lambda s: s.shift(1).rolling(WINDOW, min_periods=1).mean())
    wide["pre_games"] = by.cumcount().clip(upper=WINDOW)
    if not keep_all:
        wide = wide[(wide.h1_tgt + wide.h1_car) >= 1]
    return wide.drop(columns=["home_team", "h1_margin", "home_receives_h2", "last_left", "spread_line"]).reset_index(drop=True)


def build(seasons=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Two extra seasons so the first fit season has trailing averages.
    p = load_plays(seasons or range(min(FIT) - 2, max(HOLDOUT) + 1))
    games = game_rows(p)
    players = player_rows(p, games)
    CACHE.mkdir(parents=True, exist_ok=True)
    games.to_parquet(CACHE / "games.parquet", index=False)
    players.to_parquet(CACHE / "players.parquet", index=False)
    return games, players


def tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not (CACHE / "games.parquet").exists():
        return build()
    return pd.read_parquet(CACHE / "games.parquet"), pd.read_parquet(CACHE / "players.parquet")


def scope(players: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Rows a player target is fitted and scored on: some first-half or trailing involvement of that kind."""
    if kind == "rec":
        return players[(players.h1_tgt >= 1) | (players.pre_tgt >= 2)]
    return players[(players.h1_car >= 1) | (players.pre_car >= 2)]


def split(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    seasons = {"fit": FIT, "validation": VALIDATION, "test": TEST}[name]
    return frame[frame.season.isin(list(seasons))]


# --------------------------------------------------------------------------- model

def _rule_x(frame: pd.DataFrame, cols) -> np.ndarray:
    return frame[list(cols)].fillna(0).to_numpy(float)


def fit(games: pd.DataFrame, players: pd.DataFrame) -> dict:
    """Models and the simple rule on the fit seasons; the spread of outcomes from the validation seasons."""
    model = {"targets": {}}
    for target, rule_cols in GAME_TARGETS.items():
        train, val = split(games, "fit").dropna(subset=["spread_line", "total_line"]), split(games, "validation")
        # Boosted trees lost to the simple rule on the validation seasons (about 3,000 fit games); ridge did not.
        trees = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 4, 20))).fit(train[GAME_FEATURES], train[target])
        rule = LinearRegression().fit(_rule_x(train, rule_cols), train[target])
        model["targets"][target] = {"kind": "game", "model": trees, "rule": rule, "rule_cols": rule_cols,
                                    "residuals": np.sort((val[target] - trees.predict(val[GAME_FEATURES])).to_numpy())}
    for target, (pre, h1, kind) in PLAYER_TARGETS.items():
        rows = scope(players, kind)
        train, val = split(rows, "fit"), split(rows, "validation")
        trees = HistGradientBoostingRegressor(loss="poisson", max_depth=4, learning_rate=0.05, max_iter=400, random_state=0)
        trees.fit(train[PLAYER_FEATURES], train[target].clip(lower=0))
        rule = LinearRegression().fit(_rule_x(train, (pre, h1)), train[target])
        mu = trees.predict(val[PLAYER_FEATURES])
        edges = np.quantile(mu, np.linspace(0, 1, BINS + 1)[1:-1])
        which = np.searchsorted(edges, mu)
        pools = [(val[target].to_numpy()[which == b], float(mu[which == b].mean())) for b in range(BINS)]
        model["targets"][target] = {"kind": kind, "model": trees, "rule": rule, "rule_cols": (pre, h1), "edges": edges, "pools": pools}
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT / "model.pkl", "wb") as f:
        pickle.dump(model, f)
    return model


def load_model() -> dict:
    with open(ARTIFACT / "model.pkl", "rb") as f:
        return pickle.load(f)


def predict(model: dict, frame: pd.DataFrame, target: str) -> pd.DataFrame:
    """Forecast and simple-rule forecast for each row of the right table."""
    m = model["targets"][target]
    features = GAME_FEATURES if m["kind"] == "game" else PLAYER_FEATURES
    return pd.DataFrame({"forecast": m["model"].predict(frame[features]), "rule": m["rule"].predict(_rule_x(frame, m["rule_cols"]))}, index=frame.index)


def prob_over(model: dict, target: str, forecast, line) -> np.ndarray:
    """Chance the outcome lands above the line, from validation-season outcomes around forecasts of this size."""
    m = model["targets"][target]
    forecast, line = np.atleast_1d(np.asarray(forecast, float)), np.atleast_1d(np.asarray(line, float))
    if m["kind"] == "game":
        need = line - forecast  # P(forecast + residual > line)
        return 1 - np.searchsorted(m["residuals"], need, side="right") / len(m["residuals"])
    out = np.empty(len(forecast))
    for i, (mu, ln) in enumerate(zip(forecast, line)):
        outcomes, centre = m["pools"][int(np.searchsorted(m["edges"], mu))]
        out[i] = float((outcomes * mu / max(centre, 1e-9) > ln).mean())
    return out


# --------------------------------------------------------------------------- scoring

def _half_line(x) -> np.ndarray:
    return np.floor(np.asarray(x, float)) + 0.5


def evaluate(model: dict, games: pd.DataFrame, players: pd.DataFrame, name: str, draws: int = 2000, seed: int = 0) -> dict:
    """Mean absolute error against the simple rule, with a bootstrap over whole games."""
    rng = np.random.default_rng(seed)
    out = {"split": name, "targets": {}}
    for target, m in model["targets"].items():
        rows = split(games if m["kind"] == "game" else scope(players, m["kind"]), name)
        rows = rows.dropna(subset=["total_line"])
        pred = predict(model, rows, target)
        y = rows[target].to_numpy(float)
        gain = np.abs(y - pred.rule.to_numpy()) - np.abs(y - pred.forecast.to_numpy())
        per_game = pd.DataFrame({"g": rows.game_id.to_numpy(), "gain": gain}).groupby("g").gain.agg(["sum", "count"])
        s, c = per_game["sum"].to_numpy(), per_game["count"].to_numpy()
        idx = rng.integers(0, len(s), size=(draws, len(s)))
        boot = s[idx].sum(1) / c[idx].sum(1)
        # Calls against a line set at the simple rule's forecast. This line is not a sportsbook price.
        line = _half_line(pred.rule)
        p = prob_over(model, target, pred.forecast, line)
        over, under = p >= CALL, p <= 1 - CALL
        won = np.where(over, y > line, y < line)[over | under]
        out["targets"][target] = {"rows": int(len(y)), "games": int(len(s)), "mae_model": float(np.abs(y - pred.forecast).mean()),
                                  "mae_rule": float(np.abs(y - pred.rule).mean()), "gain": float(gain.mean()),
                                  "gain_low": float(np.quantile(boot, 0.025)), "gain_high": float(np.quantile(boot, 0.975)),
                                  "p_one_sided": float((boot <= 0).mean()),
                                  "rmse_model": float(np.sqrt(((y - pred.forecast) ** 2).mean())), "rmse_rule": float(np.sqrt(((y - pred.rule) ** 2).mean())),
                                  "calls": int(won.size), "calls_won": float(won.mean()) if won.size else None}
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / f"eval_{name}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


# --------------------------------------------------------------------------- sportsbook lines (none on disk yet)

LINE_COLS = ["game_id", "book", "captured_at_utc", "market", "player_id", "line", "over_price", "under_price"]


def load_lines(folder: Path | None = None) -> pd.DataFrame:
    files = sorted(Path(folder or LINES).glob("*.csv"))
    if not files:
        return pd.DataFrame(columns=LINE_COLS)
    lines = pd.concat([pd.read_csv(f, dtype={"player_id": str}) for f in files], ignore_index=True)
    missing = [c for c in LINE_COLS if c not in lines.columns]
    if missing:
        raise ValueError(f"Halftime line files lack columns: {missing}")
    return lines[LINE_COLS]


def implied(price) -> np.ndarray:
    """American price to implied probability, vig included."""
    price = np.asarray(price, float)
    return np.where(price < 0, -price / (-price + 100), 100 / (price + 100))


def edges(model: dict, games: pd.DataFrame, players: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Model chance of the over beside the book's vig-free chance, for each quoted line."""
    out = []
    for market, quoted in lines.groupby("market"):
        target = {"h2_spread_home": "h2_margin"}.get(market, market)
        m = model["targets"][target]
        if m["kind"] == "game":
            rows = quoted.merge(games, on="game_id")
        else:
            rows = quoted.merge(scope(players, m["kind"]), on=["game_id", "player_id"])
        if rows.empty:
            continue
        forecast = predict(model, rows, target).forecast.to_numpy()
        # A home spread of -3.5 wins when the second-half home margin is above 3.5.
        line = -rows.line.to_numpy(float) if market == "h2_spread_home" else rows.line.to_numpy(float)
        over, under = implied(rows.over_price), implied(rows.under_price)
        rows = rows[LINE_COLS].assign(forecast=forecast, model_over=prob_over(model, target, forecast, line), book_over=over / (over + under))
        out.append(rows.assign(edge=rows.model_over - rows.book_over))
    cols = LINE_COLS + ["forecast", "model_over", "book_over", "edge"]
    return pd.concat(out, ignore_index=True)[cols] if out else pd.DataFrame(columns=cols)


# --------------------------------------------------------------------------- command line

def week_forecasts(model: dict, games: pd.DataFrame, players: pd.DataFrame, season: int, week: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    g = games[(games.season == season) & (games.week == week)].copy()
    for target in GAME_TARGETS:
        g[f"{target}_forecast"] = predict(model, g, target).forecast.round(1)
    pl = players[(players.season == season) & (players.week == week)].copy()
    for target, (_, _, kind) in PLAYER_TARGETS.items():
        rows = scope(pl, kind)
        pl.loc[rows.index, f"{target}_forecast"] = predict(model, rows, target).forecast.round(1)
    game_cols = ["game_id", "h1_home", "h1_away", "spread_line", "total_line"] + [f"{t}_forecast" for t in GAME_TARGETS]
    player_cols = ["game_id", "team", "name", "h1_tgt", "h1_rec", "h1_rec_yds", "h1_car", "h1_rush_yds"] + [f"{t}_forecast" for t in PLAYER_TARGETS]
    return g[game_cols], pl[player_cols].sort_values(["game_id", "team", "h2_rec_yds_forecast"], ascending=[True, True, False])


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("fit")
    e = sub.add_parser("eval")
    e.add_argument("--split", choices=["validation", "test"], default="validation")
    e.add_argument("--registered-test", action="store_true", help="required for the one registered look at the test seasons")
    pr = sub.add_parser("predict")
    pr.add_argument("--season", type=int, required=True)
    pr.add_argument("--week", type=int, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        games, players = build()
        print(f"{len(games)} games, {len(players)} player rows -> {CACHE}")
        return
    games, players = tables()
    if args.cmd == "fit":
        fit(games, players)
        print(f"model -> {ARTIFACT / 'model.pkl'}")
    elif args.cmd == "eval":
        if args.split == "test" and not args.registered_test:
            raise SystemExit("The test seasons get one look (docs/HALFTIME_PREREG.md). Pass --registered-test to take it.")
        print(json.dumps(evaluate(load_model(), games, players, args.split), indent=1))
    else:
        model = load_model()
        g, pl = week_forecasts(model, games, players, args.season, args.week)
        REPORT.mkdir(parents=True, exist_ok=True)
        stem = f"{args.season}_w{args.week:02d}"
        g.to_csv(REPORT / f"{stem}_games.csv", index=False)
        pl.to_csv(REPORT / f"{stem}_players.csv", index=False)
        found = edges(model, games, players, load_lines())
        found[found.game_id.isin(g.game_id)].to_csv(REPORT / f"{stem}_edges.csv", index=False)
        print(g.to_string(index=False))
        print(f"{len(pl)} player rows, {len(found)} priced lines -> {REPORT}")


if __name__ == "__main__":
    main()
