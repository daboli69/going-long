"""Halftime forecasts for games in progress, from the free ESPN game summary.

Reads the newest stored snapshot of each game that has reached halftime, rebuilds the first-half
inputs of lab/halftime.py from the play list, and writes one frozen forecast file per game.
Sportsbook lines in data/raw/halftime_lines/ are compared when present.

    python -m lab.halftime_live                 # every captured game at or past halftime, not yet frozen
    python -m lab.halftime_live --pull          # ask ESPN first for games now at halftime
    python -m lab.halftime_live --check         # live-built inputs against play-by-play, no outcomes read
"""
from __future__ import annotations

import argparse
import pickle
import re

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import halftime as H
from . import ingame_feed as F
from .ingest import normalize_team

OUT = H.REPORT / "live"
EPA = ["home_h1_epa", "away_h1_epa"]   # not published during a game; the live game model is fitted without it
NAME = r"[A-Z][A-Za-z]*\.\s?(?:St\. ?)?[A-Z][A-Za-z'\-]+"
RUN_WORDS = ("left end", "left tackle", "left guard", "up the middle", "right guard", "right tackle", "right end", "scrambles")
STATS = ["tgt", "rec", "rec_yds", "car", "rush_yds"]


# --------------------------------------------------------------------------- first half from the feed
def _yards(text: str) -> float:
    m = re.search(r"for (-?\d+) yards?", text)
    return float(m.group(1)) if m else 0.0


def first_half_plays(raw: dict) -> pd.DataFrame:
    """Every first-half pass, run, sack and kneel in the snapshot, one row per play, in nflverse terms."""
    drives = raw.get("drives") or {}
    rows, seen = [], set()
    for drive in (drives.get("previous") or []) + ([drives["current"]] if drives.get("current") else []):
        team = normalize_team((drive.get("team") or {}).get("abbreviation", ""))
        for play in drive.get("plays") or []:
            period, text = play["period"]["number"], play.get("text") or ""
            if period > 2 or play.get("id") in seen or "No Play" in text or "TWO-POINT" in text:
                continue
            seen.add(play.get("id"))
            text = text.split("REVERSED.")[-1]   # a reversed ruling repeats the play; the last version stands
            text = re.sub(r"^(?:[^.]*\.[^.]* reported in as eligible\.\s*)+", "", text.strip())
            text = re.sub(r"^(\([^)]*\)\s*)+", "", text).strip()
            left = (4 - period) * 900 + (F._secs(play["clock"]["displayValue"]) or 0)
            row = {"team": team, "qtr": period, "left": left, "player": None, "kind": None, "complete": 0.0, "yards": 0.0}
            if "sacked" in text or "spiked" in text:
                row.update(kind="dropback", yards=_yards(text) if "sacked" in text else 0.0)
            elif " pass " in text:
                m = re.search(rf" pass .*?(?:to|intended for) ({NAME})", text)
                caught = bool(m) and "incomplete" not in text and "INTERCEPTED" not in text
                row.update(kind="pass", player=m.group(1).replace(". ", ".") if m else None, complete=float(caught),
                           yards=_yards(text[m.end():]) if caught else 0.0)
            elif " kneels" in text:
                row.update(kind="kneel", yards=_yards(text))
            elif re.match(NAME, text) and (any(w in text for w in RUN_WORDS) or re.match(rf"{NAME} (?:to [A-Z]+ \d+|to \d+|ran ob|pushed ob) ", text)):
                row.update(kind="rush", player=re.match(NAME, text).group(0).replace(". ", "."), yards=_yards(text))
            else:
                continue
            rows.append(row)
    return pd.DataFrame(rows, columns=["team", "qtr", "left", "player", "kind", "complete", "yards"])


def game_info(raw: dict, schedule: pd.DataFrame) -> dict:
    """Teams, halftime score, pregame line and who receives the second-half kickoff."""
    comp = raw["header"]["competitions"][0]
    side = {c["homeAway"]: c for c in comp["competitors"]}
    home, away = (normalize_team(side[k]["team"]["abbreviation"]) for k in ("home", "away"))

    def half(c):
        periods = c.get("linescores") or []
        return float(sum(int(x["displayValue"]) for x in periods[:2])) if len(periods) >= 2 else float(c.get("score") or 0)

    match = schedule[schedule.espn.astype(str) == str(raw["header"]["id"])]
    info = {"home_team": home, "away_team": away, "h1_home": half(side["home"]), "h1_away": half(side["away"]),
            "state": comp["status"]["type"]["name"], "period": comp["status"].get("period")}
    if len(match):
        g = match.iloc[0]
        info.update(game_id=g.game_id, season=int(g.season), week=int(g.week), spread_line=g.spread_line, total_line=g.total_line)
    else:
        season = raw["header"]["season"]["year"]
        info.update(game_id=f"{season}_{int(raw['header']['week']):02d}_{away}_{home}", season=season, week=int(raw["header"]["week"]),
                    spread_line=np.nan, total_line=np.nan)
    pick = (raw.get("pickcenter") or [{}])[0]
    if pd.isna(info["spread_line"]) and pick.get("spread") is not None:
        info["spread_line"] = -float(pick["spread"])   # ESPN quotes the home side; nflverse counts a home favourite as positive
    if pd.isna(info["total_line"]) and pick.get("overUnder") is not None:
        info["total_line"] = float(pick["overUnder"])
    # The team with the opening drive took the opening kickoff, so the other team receives after halftime.
    opening = ((raw.get("drives") or {}).get("previous") or [{}])[0].get("team") or {}
    info["home_receives_h2"] = float(normalize_team(opening.get("abbreviation", "")) != home)
    return info


def history(season: int, week: int) -> pd.DataFrame:
    """Each player's trailing averages over games before this week, as lab.halftime computes them."""
    path = H.CACHE / f"history_{season}_{week:02d}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    p = H.load_plays(range(season - 2, season + 1))
    p = p[(p.season < season) | (p.week < week)]
    rows = H.player_rows(p, H.game_rows(p), keep_all=True).sort_values(["player_id", "season", "week"])
    for stat in STATS:
        rows[f"pre_{stat}"] = rows[f"h1_{stat}"] + rows[f"h2_{stat}"]
    for stat in ("rec_yds", "rec", "rush_yds"):
        rows[f"pre_h2_{stat}"] = rows[f"h2_{stat}"]
    last = rows.groupby("player_id").tail(H.WINDOW)
    cols = [c for c in rows.columns if c.startswith("pre_") and c != "pre_games"]
    out = last.groupby("player_id")[cols].mean()
    out["last_season"] = last.groupby("player_id").season.max()
    out["pre_games"] = last.groupby("player_id").size()
    out = out.join(last.groupby("player_id").agg(name=("name", "last"), team=("team", "last"))).reset_index()
    H.CACHE.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return out


def tables(raw: dict, schedule: pd.DataFrame, hist: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The game row and player rows lab.halftime expects, built from one snapshot."""
    info, plays = game_info(raw, schedule), first_half_plays(raw)
    game = dict(info, h1_total=info["h1_home"] + info["h1_away"], h1_margin=info["h1_home"] - info["h1_away"])
    for label, team in (("home", info["home_team"]), ("away", info["away_team"])):
        t = plays[plays.team == team]
        game[f"{label}_h1_pass"] = float(t.kind.isin(["pass", "dropback"]).sum())
        game[f"{label}_h1_rush"] = float(t.kind.isin(["rush", "kneel"]).sum())
        game[f"{label}_h1_yards"] = float(t.yards.sum())
        game[f"{label}_h1_epa"] = 0.0
    touch = plays[plays.player.notna()]
    if touch.empty:
        return pd.DataFrame([game]), pd.DataFrame(columns=["game_id", "player_id", "team", "name"] + H.PLAYER_FEATURES)
    is_pass = touch.kind == "pass"
    touch = touch.assign(tgt=is_pass.astype(int), rec=touch.complete, rec_yds=np.where(is_pass, touch.yards, 0.0),
                         car=(~is_pass).astype(int), rush_yds=np.where(is_pass, 0.0, touch.yards), q2=(touch.qtr == 2).astype(int))
    pl = touch.groupby(["team", "player"]).agg(h1_tgt=("tgt", "sum"), h1_rec=("rec", "sum"), h1_rec_yds=("rec_yds", "sum"), h1_car=("car", "sum"),
                                               h1_rush_yds=("rush_yds", "sum"), h1_q2_touches=("q2", "sum"), last_left=("left", "min")).reset_index()
    pl = pl.rename(columns={"player": "name"})
    pl["h1_since_touch"] = pl.pop("last_left") - 1800
    pl["home"] = (pl.team == info["home_team"]).astype(float)
    sign = np.where(pl.home == 1, 1.0, -1.0)
    pl["team_h1_margin"], pl["team_spread"] = sign * game["h1_margin"], sign * info["spread_line"]
    pl["receives_h2"] = np.where(pl.home == 1, info["home_receives_h2"], 1 - info["home_receives_h2"])
    pl["team_h1_pass"] = pl.groupby("team").h1_tgt.transform("sum")
    pl["team_h1_rush"] = pl.groupby("team").h1_car.transform("sum")
    pl["tgt_share"] = pl.h1_tgt / pl.team_h1_pass.clip(lower=1)
    pl["car_share"] = pl.h1_car / pl.team_h1_rush.clip(lower=1)
    hist = history(info["season"], info["week"]) if hist is None else hist
    pre = [c for c in hist.columns if c.startswith("pre_")]
    out = pl.merge(hist[["player_id", "team", "name"] + pre], on=["team", "name"], how="left")
    # A player who changed teams since last season keeps his history when his name is the only one of its kind.
    moved = hist[hist.last_season >= info["season"] - 1] if "last_season" in hist else hist
    lone = moved.drop_duplicates("name", keep=False).set_index("name")
    gap = out.player_id.isna() & out.name.isin(lone.index)
    for c in ["player_id"] + pre:
        out.loc[gap, c] = out.loc[gap, "name"].map(lone[c])
    out["pre_games"] = out.pre_games.fillna(0)
    return pd.DataFrame([game]), out.assign(game_id=info["game_id"], season=info["season"], week=info["week"], total_line=info["total_line"])


# --------------------------------------------------------------------------- model
def live_model(refit: bool = False) -> dict:
    """The halftime model with its game targets refitted without first-half EPA, which no free live feed carries."""
    path = H.ARTIFACT / "model_live.pkl"
    if path.exists() and not refit:
        with open(path, "rb") as f:
            return pickle.load(f)
    model = H.load_model()
    games, _ = H.tables()
    blank = games.assign(**{c: 0.0 for c in EPA})
    train, val = H.split(blank, "fit").dropna(subset=["spread_line", "total_line"]), H.split(blank, "validation")
    model["live_validation_mae"] = {}
    for target in H.GAME_TARGETS:
        ridge = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 4, 20))).fit(train[H.GAME_FEATURES], train[target])
        resid = (val[target] - ridge.predict(val[H.GAME_FEATURES])).to_numpy()
        model["targets"][target] = dict(model["targets"][target], model=ridge, residuals=np.sort(resid))
        model["live_validation_mae"][target] = float(np.abs(resid).mean())
    with open(path, "wb") as f:
        pickle.dump(model, f)
    return model


def forecast(model: dict, game: pd.DataFrame, players: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    game, players = game.copy(), players.copy()
    for target in H.GAME_TARGETS:
        game[f"{target}_forecast"] = H.predict(model, game, target).forecast.round(1)
    for target, (_, _, kind) in H.PLAYER_TARGETS.items():
        players[f"{target}_forecast"] = np.nan
        rows = H.scope(players, kind)
        if len(rows):
            players.loc[rows.index, f"{target}_forecast"] = H.predict(model, rows, target).forecast.round(1)
    return game, players


# --------------------------------------------------------------------------- command line
def halftime_snapshot(eid: str):
    """The newest stored snapshot at or after halftime, or None before then."""
    snaps = F.snapshots(eid)
    if not snaps:
        return None
    stamp, path = snaps[-1]
    raw = F.load(path)
    status = raw["header"]["competitions"][0]["status"]
    state, period = status["type"]["name"], status.get("period") or 0
    reached = state in ("STATUS_HALFTIME", "STATUS_FINAL") or period >= 3
    return (stamp, raw) if reached else None


def pull_halftime() -> list[str]:
    """Store a fresh summary for every game the scoreboard shows at halftime. Free ESPN endpoint."""
    import requests
    board = requests.get(F.SUMMARY.replace("summary", "scoreboard"), timeout=10).json()
    events = [e["id"] for e in board.get("events", []) if e["competitions"][0]["status"]["type"]["name"] == "STATUS_HALFTIME"]
    for eid in events:
        F.pull(eid)
    return events


def run(pull: bool = False, force: bool = False, only: str | None = None) -> list[str]:
    schedule, model, lines = pd.read_csv(H.RAW / "games.csv"), live_model(), H.load_lines()
    events = pull_halftime() if pull else []
    OUT.mkdir(parents=True, exist_ok=True)
    done = []
    for folder in sorted(F.CAPTURE.iterdir()) if F.CAPTURE.exists() else []:
        if not folder.is_dir() or (only and folder.name != only) or (pull and folder.name not in events):
            continue
        found = halftime_snapshot(folder.name)
        if not found:
            continue
        stamp, raw = found
        game, players = forecast(model, *tables(raw, schedule))
        gid = game.game_id.iloc[0]
        path = OUT / f"{gid}_players.csv"
        if path.exists() and not force:   # a forecast is written once; later snapshots do not replace it
            continue
        cols = ["game_id", "team", "name", "player_id", "h1_tgt", "h1_rec", "h1_rec_yds", "h1_car", "h1_rush_yds"] + [f"{t}_forecast" for t in H.PLAYER_TARGETS]
        players = players.sort_values(["team", "h2_rec_yds_forecast"], ascending=[True, False])
        players[cols].assign(snapshot=stamp).to_csv(path, index=False)
        gcols = ["game_id", "home_team", "away_team", "h1_home", "h1_away", "spread_line", "total_line"] + [f"{t}_forecast" for t in H.GAME_TARGETS]
        game[gcols + ["state"]].assign(snapshot=stamp).to_csv(OUT / f"{gid}_game.csv", index=False)
        print(game[gcols].to_string(index=False))
        print(players[cols[1:3] + cols[4:]].head(16).to_string(index=False))
        if len(lines):
            e = H.edges(model, game, players.dropna(subset=["player_id"]), lines[lines.game_id == gid])
            if len(e):
                e.to_csv(OUT / f"{gid}_edges.csv", index=False)
                print(e.sort_values("edge", ascending=False).to_string(index=False))
        done.append(gid)
    return done


def check() -> pd.DataFrame:
    """Live-built first-half inputs beside the play-by-play ones for every captured game already in the tables. No outcome is read."""
    schedule, champion = pd.read_csv(H.RAW / "games.csv"), H.load_model()
    games, players = H.tables()
    out = []
    for folder in sorted(F.CAPTURE.iterdir()):
        found = halftime_snapshot(folder.name) if folder.is_dir() else None
        if not found:
            continue
        game, live = tables(found[1], schedule)
        gid = game.game_id.iloc[0]
        truth = players[players.game_id == gid]
        if truth.empty:
            continue
        both = truth.merge(live, on=["team", "name"], suffixes=("", "_live"))
        row = {"game_id": gid, "pbp_players": len(truth), "live_players": len(live), "matched": len(both),
               "id_agree": float((both.player_id == both.player_id_live).mean())}
        for c in H.PLAYER_FEATURES:
            row[c] = float((both[c].fillna(-99) - both[f"{c}_live"].fillna(-99)).abs().mean())
        g = games[games.game_id == gid].iloc[0]
        for c in [c for c in H.GAME_FEATURES if c not in EPA]:
            row[f"game_{c}"] = float(abs(g[c] - game[c].iloc[0]))
        for target, (_, _, kind) in H.PLAYER_TARGETS.items():
            rows = H.scope(both, kind)
            live_x = rows[[f"{c}_live" for c in H.PLAYER_FEATURES]].set_axis(H.PLAYER_FEATURES, axis=1)
            m = champion["targets"][target]["model"]
            row[f"{target}_forecast_gap"] = float(np.abs(m.predict(rows[H.PLAYER_FEATURES]) - m.predict(live_x)).mean())
        out.append(row)
    return pd.DataFrame(out)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pull", action="store_true", help="fetch games now at halftime from ESPN before forecasting")
    ap.add_argument("--force", action="store_true", help="rewrite a forecast that was already frozen")
    ap.add_argument("--event", help="one ESPN event id")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--refit", action="store_true", help="refit the game targets without EPA")
    args = ap.parse_args(argv)
    if args.refit:
        print(live_model(refit=True)["live_validation_mae"])
    if args.check:
        c = check()
        OUT.mkdir(parents=True, exist_ok=True)
        c.to_csv(OUT / "feature_check.csv", index=False)
        print(c.set_index("game_id").T.round(3).to_string())
    elif not args.refit:
        done = run(args.pull, args.force, args.event)
        print(f"{len(done)} game(s) frozen -> {OUT}")


if __name__ == "__main__":
    main()
