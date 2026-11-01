"""One availability source for the simulated game and the tests behind it.

For every team-week it combines the official injury report (nflverse copy of the NFL report) with the weekly roster status, and turns
each player's status into a chance of playing learned from who actually appeared on the field (nflverse participation, 2016-2025).

Timing, stated plainly: both files are weekly snapshots without time stamps inside the week. Official report statuses (Out, Doubtful,
Questionable) are treated as known from the Friday report; roster IR/released/retired statuses as known from the start of the week;
"inactive" (INA) only on game day, when teams post their inactives about 90 minutes before kickoff. `evaluate` scores each rule at the
Friday and game-day decision times separately so nothing from game day leaks into an earlier decision.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from .config import RAW_DIR
from .ingest import normalize_team

HARD_ROSTER = {"RES", "CUT", "RET", "EXE", "TRC", "TRD"}   # on injured reserve or another reserve list, released, retired, exempt, traded away
GAME_DAY = {"INA"}                                           # inactive for this game (known about 90 minutes before kickoff)
GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "HB": "RB", "WR": "WR", "TE": "TE"}
SKILL = ("QB", "RB", "WR", "TE")


def _team(t):
    """Standard team code, or None for a blank or unknown one (kickoffs, free agents)."""
    if not isinstance(t, str) or not t.strip():
        return None
    try:
        return normalize_team(t)
    except ValueError:
        return None


def status_table(seasons) -> pd.DataFrame:
    """One row per (season, week, team, gsis_id): official report status and roster status."""
    frames = []
    for s in seasons:
        rp, ip = RAW_DIR / f"roster_weekly_{s}.parquet", RAW_DIR / f"injuries_{s}.parquet"
        if not rp.exists():
            continue

        def build(rp=rp, ip=ip, s=s):
            r = pd.read_parquet(rp, columns=["team", "week", "status", "gsis_id", "full_name", "position"]).rename(columns={"status": "roster"})
            r["team"] = r["team"].map(_team)
            r = r.dropna(subset=["team"])
            r["season"] = s
            if ip.exists():
                i = pd.read_parquet(ip, columns=["team", "week", "gsis_id", "report_status"]).rename(columns={"report_status": "official"})
                i["team"] = i["team"].map(_team)
                i = i.dropna(subset=["team"])
                r = r.merge(i.drop_duplicates(["team", "week", "gsis_id"]), on=["team", "week", "gsis_id"], how="left")
            else:
                r["official"] = None
            r["group"] = r["position"].map(GROUP)
            return r
        frames.append(D._cached(("status_table", s), (D._mt(rp), D._mt(ip) if ip.exists() else 0), build))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def appearances(seasons) -> pd.DataFrame:
    """(season, week, team, gsis_id) that were on the field for at least one offensive play (participation 2016-2025)."""
    frames = []
    for s in seasons:
        path = RAW_DIR / f"participation_{s}.parquet"
        if not path.exists():
            continue

        def build(path=path, s=s):
            p = pd.read_parquet(path, columns=["nflverse_game_id", "possession_team", "offense_players"]).dropna(subset=["offense_players"])
            p["week"] = p["nflverse_game_id"].str[5:7].astype(int)
            p["team"] = p["possession_team"].map(_team)
            p = p.dropna(subset=["team"])
            ex = p.assign(gsis_id=p["offense_players"].str.split(";")).explode("gsis_id")
            out = ex[["week", "team", "gsis_id"]].drop_duplicates()
            out["season"] = s
            return out
        frames.append(D._cached(("appearances", s), D._mt(path), build))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def classify(df: pd.DataFrame, game_day: bool) -> pd.Series:
    """The status class used to look up a chance of playing. Roster and official statuses, in order of how final they are."""
    roster = df["roster"].fillna("ACT")
    official = df["official"].fillna("")
    cls = pd.Series("clear", index=df.index)
    cls[roster == "DEV"] = "practice squad"
    cls[official == "Questionable"] = "Questionable"
    cls[official == "Doubtful"] = "Doubtful"
    cls[official == "Out"] = "Out"
    if game_day:
        cls[roster.isin(GAME_DAY)] = "inactive"
    cls[roster.isin(HARD_ROSTER)] = "reserve or gone"
    return cls


def fit_p_play(train_seasons, game_day: bool = True) -> dict:
    """{(class, group): chance of playing} for regular players (in at least 3 of their team's previous 4 games), smoothed by a one-in-two
    prior, from who appeared on the field. Regulars only, because a projection only counts on regulars; a backup's 90% would mislead."""
    seasons = list(train_seasons)
    st, ap = status_table(seasons), appearances(seasons)
    if st.empty or ap.empty:
        return {}
    reg = regulars(st, ap)
    reg = reg.assign(cls=classify(reg, game_day))
    g = reg.groupby(["cls", "group"])["played"].agg(["sum", "size"])
    return {k: float((v["sum"] + 1) / (v["size"] + 2)) for k, v in g.iterrows()}


def regulars(st: pd.DataFrame, ap: pd.DataFrame, min_games: int = 3, window: int = 4) -> pd.DataFrame:
    """Player-weeks of players who appeared in at least `min_games` of the team's previous `window` games (the players a projection counts on)."""
    a = ap.assign(played=1)
    t = st[st["group"].isin(SKILL)][["season", "week", "team", "gsis_id", "group", "roster", "official"]].merge(a, on=["season", "week", "team", "gsis_id"], how="left")
    t["played"] = t["played"].fillna(0)
    t = t.sort_values(["season", "team", "gsis_id", "week"])
    prev = t.groupby(["season", "team", "gsis_id"])["played"].transform(lambda x: x.shift(1).rolling(window, min_periods=window).sum())
    return t[prev >= min_games]


# --------------------------------------------------------------------------- how well each rule predicts who plays

def _paired_loss(new: np.ndarray, old: np.ndarray, groups: np.ndarray, draws: int = 2000, seed: int = 4) -> dict:
    """Mean of (new - old) loss and a 90% interval, resampling team-games."""
    d = new - old
    ids, inv = np.unique(groups, return_inverse=True)
    sums = np.bincount(inv, weights=d); cnt = np.bincount(inv)
    idx = np.random.default_rng(seed).integers(0, len(ids), (draws, len(ids)))
    m = sums[idx].sum(1) / cnt[idx].sum(1)
    return {"diff": float(d.mean()), "lo": float(np.percentile(m, 5)), "hi": float(np.percentile(m, 95))}


def rule_scores(train=(2022, 2023, 2024), test=(2025,)) -> dict:
    """Score four rules for who will play, on regular players in games the fit never saw, at the Friday and game-day decision times.

    Rules: official Out only (the old rule); Out and Doubtful; those plus roster injured reserve, released, retired and exempt (plus
    inactive on game day); and the fitted chance of playing by status class and position."""
    seasons = list(range(min(train) - 1, max(test) + 1))
    st, ap = status_table(seasons), appearances(seasons)
    reg = regulars(st[st["season"].isin(test)], ap)
    grp = (reg["season"].astype(str) + reg["week"].astype(str) + reg["team"]).to_numpy()
    y = reg["played"].to_numpy(float)
    out = {"player_weeks": int(len(reg)), "played_share": float(y.mean()), "timings": {}}
    for timing, gd in (("friday", False), ("game_day", True)):
        table = fit_p_play(train, gd)
        off = reg["official"].fillna("")
        hard = reg["roster"].isin(HARD_ROSTER) | (reg["roster"] == "DEV") | (reg["roster"].isin(GAME_DAY) if gd else False)
        p = {"R0 official Out only": np.where(off == "Out", 0.0, 1.0),
             "R1 Out and Doubtful": np.where(off.isin(["Out", "Doubtful"]), 0.0, 1.0),
             "R2 R1 plus roster IR, released, retired" + (", inactive" if gd else ""): np.where(off.isin(["Out", "Doubtful"]) | hard, 0.0, 1.0)}
        cls = classify(reg, gd)
        p["R3 fitted chance by status and position"] = np.array([table.get((c, g), 0.9) for c, g in zip(cls, reg["group"])])
        res = {}
        for name, pr in p.items():
            q = np.clip(pr, 0.02, 0.98)
            ll = -(y * np.log(q) + (1 - y) * np.log(1 - q))
            res[name] = {"log_loss": float(ll.mean()), "brier": float(((q - y) ** 2).mean()), "expected_but_absent": int(((pr >= 0.5) & (y == 0)).sum()),
                         "absent_expected_but_played": int(((pr < 0.5) & (y == 1)).sum()), "_ll": ll}
        names = list(res)
        for n in names[1:]:
            res[n]["vs_R0"] = _paired_loss(res[n]["_ll"], res[names[0]]["_ll"], grp)
        for n in names:
            res[n].pop("_ll")
        out["timings"][timing] = res
    return out
