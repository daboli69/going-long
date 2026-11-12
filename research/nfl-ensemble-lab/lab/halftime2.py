"""Halftime challenger (v2) for the player targets. Notes and result: docs/HALFTIME2_NOTES.md.

Adds to lab/halftime.py: position, a quarterback-change flag, a game-script forecast of the team's
second-half pass and rush attempts, a Bayes-updated share of those attempts, shrunk yards per
target and carry, the opponent's trailing yards allowed, a blend with the simple rule, and
quantile models so the chance of an over comes from a fitted distribution.

    python -m lab.halftime2 build
    python -m lab.halftime2 fit
    python -m lab.halftime2 eval --split validation
"""
from __future__ import annotations

import argparse
import json
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold, cross_val_predict

from . import halftime as H

QUANTILES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
PRIOR_WEIGHTS = (5, 10, 20, 40, 80, 160)   # candidate strengths of the trailing-share prior, in team attempts
YARD_PRIOR = 20                            # attempts of league-average efficiency mixed into a player's rate
POSITIONS = {"QB": 0, "RB": 1, "FB": 1, "WR": 2, "TE": 3}
SCRIPT_FEATURES = ["team_h1_pass", "team_h1_rush", "team_h1_margin", "team_spread", "total_line", "home", "receives_h2"]
NEW_FEATURES = ["pos", "qb_changed", "qb_new", "exp_h2_pass", "exp_h2_rush", "tgt_share_post", "car_share_post", "ypt", "catch_rate", "ypc",
                "struct_rec_yds", "struct_rec", "struct_rush_yds", "opp_rec_yds_allowed", "opp_rush_yds_allowed"]
FEATURES = H.PLAYER_FEATURES + NEW_FEATURES
STRUCT = {"h2_rec_yds": "struct_rec_yds", "h2_rec": "struct_rec", "h2_rush_yds": "struct_rush_yds"}
SPLITS = {"fit": H.FIT, "validation": H.VALIDATION, "test": H.TEST, "holdout": H.HOLDOUT}


def _trail(frame: pd.DataFrame, key: str, col: str) -> pd.Series:
    return frame.groupby(key)[col].transform(lambda s: s.shift(1).rolling(H.WINDOW, min_periods=1).mean())


def team_rows(p: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One row per team and game: attempts by half, the opponent, quarterback flags and trailing figures."""
    t = H.touches(p)
    t["half"] = np.where(t.qtr <= 2, "h1", "h2")
    tt = t.pivot_table(index=["game_id", "team"], columns="half", values=["tgt", "car", "rec_yds", "rush_yds"], aggfunc="sum", fill_value=0)
    tt.columns = [f"{half}_{stat}" for stat, half in tt.columns]
    tt = tt.reset_index().merge(games[["game_id", "season", "week", "home_team", "away_team"]], on="game_id")
    tt["opp"] = np.where(tt.team == tt.home_team, tt.away_team, tt.home_team)
    for stat in ("tgt", "car", "rec_yds", "rush_yds"):
        tt[f"full_{stat}"] = tt[f"h1_{stat}"] + tt[f"h2_{stat}"]
    tt = tt.sort_values(["season", "week"]).reset_index(drop=True)
    tt["pre_team_tgt"] = _trail(tt, "team", "full_tgt")
    tt["pre_team_car"] = _trail(tt, "team", "full_car")
    # Yards a defence gave up in its earlier games: the offence's yards, trailed by the opponent column.
    tt["opp_rec_yds_allowed"] = _trail(tt, "opp", "full_rec_yds")
    tt["opp_rush_yds_allowed"] = _trail(tt, "opp", "full_rush_yds")
    # Quarterback: most first-half attempts, last first-half attempt, and last game's starter.
    passes = p[(p.qtr <= 2) & (p.pass_attempt == 1) & p.passer_player_id.notna()].sort_values("game_seconds_remaining", ascending=False)
    qb = passes.groupby(["game_id", "posteam"]).passer_player_id.agg(main=lambda s: s.mode().iat[0], last="last").reset_index().rename(columns={"posteam": "team"})
    tt = tt.merge(qb, on=["game_id", "team"], how="left")
    tt["qb_changed"] = (tt["last"] != tt["main"]).astype(float)
    tt["qb_new"] = (tt.groupby("team")["main"].shift(1) != tt["main"]).astype(float)
    return tt[["game_id", "team", "h2_tgt", "h2_car", "pre_team_tgt", "pre_team_car", "opp_rec_yds_allowed", "opp_rush_yds_allowed", "qb_changed", "qb_new"]].rename(
        columns={"h2_tgt": "team_h2_pass", "h2_car": "team_h2_rush"})


def build() -> pd.DataFrame:
    p = pd.concat([pd.read_parquet(f, columns=H.PBP_COLS + ["passer_player_id"]) for s in range(min(H.FIT) - 2, max(H.HOLDOUT) + 1)
                   if (f := H.RAW / f"play_by_play_{s}.parquet").exists()], ignore_index=True)
    p = p[p.season_type == "REG"]
    games = H.game_rows(p)
    players = H.player_rows(p, games).merge(team_rows(p, games), on=["game_id", "team"], how="left")
    position = pd.read_parquet(H.RAW / "players.parquet", columns=["gsis_id", "position"]).drop_duplicates("gsis_id").set_index("gsis_id").position
    players["pos"] = players.player_id.map(position).map(POSITIONS).fillna(4)
    H.CACHE.mkdir(parents=True, exist_ok=True)
    players.to_parquet(H.CACHE / "players2.parquet", index=False)
    return players


def tables() -> pd.DataFrame:
    path = H.CACHE / "players2.parquet"
    return pd.read_parquet(path) if path.exists() else build()


def split(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    return frame[frame.season.isin(list(SPLITS[name]))]


# --------------------------------------------------------------------------- structure

def posterior_share(prior, count, total, weight):
    """Beta-binomial update: a prior share worth `weight` team attempts, then the first-half count."""
    return (weight * prior + count) / (weight + total)


def fit_structure(players: pd.DataFrame) -> dict:
    """Everything the structural features need, learned from the fit seasons only."""
    train = split(players, "fit")
    s = {}
    teams = train.drop_duplicates(["game_id", "team"])
    for stat in ("pass", "rush"):
        s[f"script_{stat}"] = HistGradientBoostingRegressor(loss="poisson", max_depth=3, learning_rate=0.05, max_iter=200, random_state=0).fit(
            teams[SCRIPT_FEATURES], teams[f"team_h2_{stat}"])
    for kind, count, total, pre, pre_team, h2, team_h2 in (("tgt", "h1_tgt", "team_h1_pass", "pre_tgt", "pre_team_tgt", "h2_tgt", "team_h2_pass"),
                                                          ("car", "h1_car", "team_h1_rush", "pre_car", "pre_team_car", "h2_car", "team_h2_rush")):
        fresh = train[train[pre].isna()]
        s[f"{kind}_fallback"] = float(fresh[count].sum() / fresh[total].sum())
        prior = (train[pre] / train[pre_team]).clip(0, 1).fillna(s[f"{kind}_fallback"])
        actual = train[h2] / train[team_h2].clip(lower=1)
        errors = {w: float(((posterior_share(prior, train[count], train[total], w) - actual) ** 2).mean()) for w in PRIOR_WEIGHTS}
        s[f"{kind}_weight"] = min(errors, key=errors.get)
    s["ypt"] = float((train.h1_rec_yds + train.h2_rec_yds).sum() / (train.h1_tgt + train.h2_tgt).sum())
    s["catch_rate"] = float((train.h1_rec + train.h2_rec).sum() / (train.h1_tgt + train.h2_tgt).sum())
    s["ypc"] = float((train.h1_rush_yds + train.h2_rush_yds).sum() / (train.h1_car + train.h2_car).sum())
    return s


def add_structure(players: pd.DataFrame, s: dict, crossfit: bool = False) -> pd.DataFrame:
    """Attach the structural features. With crossfit, fit-season rows get script forecasts from models that never saw their season."""
    d = players.copy()
    teams = d.drop_duplicates(["game_id", "team"])
    for stat in ("pass", "rush"):
        pred = pd.Series(s[f"script_{stat}"].predict(teams[SCRIPT_FEATURES]), index=teams.index)
        if crossfit:
            inside = teams[teams.season.isin(list(H.FIT))]
            model = HistGradientBoostingRegressor(loss="poisson", max_depth=3, learning_rate=0.05, max_iter=200, random_state=0)
            pred.loc[inside.index] = cross_val_predict(model, inside[SCRIPT_FEATURES], inside[f"team_h2_{stat}"], groups=inside.season, cv=GroupKFold(5))
        d = d.merge(teams[["game_id", "team"]].assign(**{f"exp_h2_{stat}": pred.to_numpy()}), on=["game_id", "team"], how="left")
    for kind, count, total, pre, pre_team in (("tgt", "h1_tgt", "team_h1_pass", "pre_tgt", "pre_team_tgt"), ("car", "h1_car", "team_h1_rush", "pre_car", "pre_team_car")):
        prior = (d[pre] / d[pre_team]).clip(0, 1).fillna(s[f"{kind}_fallback"])
        d[f"{kind}_share_post"] = posterior_share(prior, d[count], d[total], s[f"{kind}_weight"])
    games = d.pre_games.fillna(0)
    past_tgt, past_car = (d.pre_tgt.fillna(0) * games + d.h1_tgt), (d.pre_car.fillna(0) * games + d.h1_car)
    d["ypt"] = (d.pre_rec_yds.fillna(0) * games + d.h1_rec_yds + YARD_PRIOR * s["ypt"]) / (past_tgt + YARD_PRIOR)
    d["catch_rate"] = (d.pre_rec.fillna(0) * games + d.h1_rec + YARD_PRIOR * s["catch_rate"]) / (past_tgt + YARD_PRIOR)
    d["ypc"] = (d.pre_rush_yds.fillna(0) * games + d.h1_rush_yds + YARD_PRIOR * s["ypc"]) / (past_car + YARD_PRIOR)
    d["struct_rec_yds"] = d.exp_h2_pass * d.tgt_share_post * d.ypt
    d["struct_rec"] = d.exp_h2_pass * d.tgt_share_post * d.catch_rate
    d["struct_rush_yds"] = d.exp_h2_rush * d.car_share_post * d.ypc
    return d


# --------------------------------------------------------------------------- model

def fit(players: pd.DataFrame) -> dict:
    structure = fit_structure(players)
    d = add_structure(players, structure, crossfit=True)
    model = {"structure": structure, "targets": {}}
    champion = H.load_model()
    for target, (_, _, kind) in H.PLAYER_TARGETS.items():
        rows = H.scope(d, kind)
        train, val = split(rows, "fit"), split(rows, "validation")
        y = train[target].clip(lower=0)
        trees = HistGradientBoostingRegressor(loss="poisson", max_depth=4, learning_rate=0.05, max_iter=400, random_state=0).fit(train[FEATURES], y)
        quantiles = [HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=4, learning_rate=0.05, max_iter=300, random_state=0).fit(train[FEATURES], y)
                     for q in QUANTILES]
        # Weight on the trees against the simple rule, chosen on the validation seasons.
        mu, rule = trees.predict(val[FEATURES]), H.predict(champion, val, target).rule.to_numpy()
        errors = {w: float(np.abs(val[target] - (w * mu + (1 - w) * rule)).mean()) for w in np.linspace(0, 1, 11)}
        model["targets"][target] = {"kind": kind, "trees": trees, "quantiles": quantiles, "blend": float(min(errors, key=errors.get))}
    H.ARTIFACT.mkdir(parents=True, exist_ok=True)
    with open(H.ARTIFACT / "model2.pkl", "wb") as f:
        pickle.dump(model, f)
    return model


def load_model() -> dict:
    with open(H.ARTIFACT / "model2.pkl", "rb") as f:
        return pickle.load(f)


def predict(model: dict, champion: dict, rows: pd.DataFrame, target: str) -> tuple[np.ndarray, np.ndarray]:
    """Blended mean forecast and the fitted quantiles (rows x len(QUANTILES)), for rows that carry the structural features."""
    m = model["targets"][target]
    mean = m["blend"] * m["trees"].predict(rows[FEATURES]) + (1 - m["blend"]) * H.predict(champion, rows, target).rule.to_numpy()
    q = np.sort(np.column_stack([t.predict(rows[FEATURES]) for t in m["quantiles"]]), axis=1)
    return mean, np.clip(q, 0, None)


def prob_over(quantiles: np.ndarray, line) -> np.ndarray:
    """Chance of landing above the line, by straight-line interpolation through the fitted quantiles."""
    line = np.broadcast_to(np.asarray(line, float), (len(quantiles),))
    out = np.empty(len(quantiles))
    for i, (q, ln) in enumerate(zip(quantiles, line)):
        xs = np.concatenate([[0.0], q, [max(q[-1] * 2.5, q[-1] + 1)]]) + np.arange(len(q) + 2) * 1e-9
        out[i] = 1 - np.interp(ln, xs, np.concatenate([[0.0], QUANTILES, [1.0]]))
    return out


def champion_quantiles(champion: dict, target: str, forecast: np.ndarray) -> np.ndarray:
    """The champion's quantiles: validation outcomes around forecasts of this size, scaled to the forecast."""
    m = champion["targets"][target]
    out = np.empty((len(forecast), len(QUANTILES)))
    for i, mu in enumerate(forecast):
        outcomes, centre = m["pools"][int(np.searchsorted(m["edges"], mu))]
        out[i] = np.quantile(outcomes * mu / max(centre, 1e-9), QUANTILES)
    return out


def pinball(y: np.ndarray, quantiles: np.ndarray) -> np.ndarray:
    """Mean quantile loss per row; lower means a better-placed distribution."""
    diff = y[:, None] - quantiles
    return np.maximum(np.asarray(QUANTILES) * diff, (np.asarray(QUANTILES) - 1) * diff).mean(1)


# --------------------------------------------------------------------------- scoring

def _boot(gain: np.ndarray, game_ids: np.ndarray, rng, draws: int) -> dict:
    per = pd.DataFrame({"g": game_ids, "gain": gain}).groupby("g").gain.agg(["sum", "count"])
    s, c = per["sum"].to_numpy(), per["count"].to_numpy()
    idx = rng.integers(0, len(s), size=(draws, len(s)))
    boot = s[idx].sum(1) / c[idx].sum(1)
    return {"gain": float(gain.mean()), "low": float(np.quantile(boot, 0.025)), "high": float(np.quantile(boot, 0.975)), "p_one_sided": float((boot <= 0).mean())}


def evaluate(model: dict, players: pd.DataFrame, name: str, draws: int = 4000, seed: int = 0) -> dict:
    """Challenger against the champion (lab/halftime.py): mean absolute error and quantile loss, bootstrapped over games."""
    rng = np.random.default_rng(seed)
    champion = H.load_model()
    d = add_structure(players, model["structure"])
    out = {"split": name, "targets": {}}
    for target, m in model["targets"].items():
        rows = split(H.scope(d, m["kind"]), name)
        y = rows[target].to_numpy(float)
        old = H.predict(champion, rows, target)
        mean, q = predict(model, champion, rows, target)
        games = rows.game_id.to_numpy()
        mae_old, mae_new = np.abs(y - old.forecast.to_numpy()), np.abs(y - mean)
        pin_old, pin_new = pinball(y, champion_quantiles(champion, target, old.forecast.to_numpy())), pinball(y, q)
        out["targets"][target] = {"rows": int(len(y)), "games": int(len(set(games))), "blend": m["blend"],
                                  "mae_champion": float(mae_old.mean()), "mae_challenger": float(mae_new.mean()), "mae_rule": float(np.abs(y - old.rule).mean()),
                                  "mae_structure": float(np.abs(y - rows[STRUCT[target]]).mean()),
                                  "mae": _boot(mae_old - mae_new, games, rng, draws),
                                  "pinball_champion": float(pin_old.mean()), "pinball_challenger": float(pin_new.mean()),
                                  "pinball": _boot(pin_old - pin_new, games, rng, draws)}
    H.REPORT.mkdir(parents=True, exist_ok=True)
    (H.REPORT / f"eval2_{name}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("fit")
    e = sub.add_parser("eval")
    e.add_argument("--split", choices=["validation", "holdout"], default="validation")
    e.add_argument("--registered-test", action="store_true", help="required for the one registered look at the 2026 holdout")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        print(f"{len(build())} player rows")
    elif args.cmd == "fit":
        model = fit(tables())
        print({k: v for k, v in model["structure"].items() if not k.startswith("script")}, {t: m["blend"] for t, m in model["targets"].items()})
    else:
        if args.split == "holdout" and not args.registered_test:
            raise SystemExit("The challenger lost on validation (docs/HALFTIME2_NOTES.md); the 2026 holdout is not to be spent on it. --registered-test overrides.")
        print(json.dumps(evaluate(load_model(), tables(), args.split), indent=1))


if __name__ == "__main__":
    main()
