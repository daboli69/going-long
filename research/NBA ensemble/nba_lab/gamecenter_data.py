"""NBA Game Center data: read-only views of saved forecasts for the web app and the dashboard. Local files only; nothing is invented.

The headline win chance is the frozen six-model ensemble. Shadow forecasts and the score model are shown beside it, never blended in.
The winner models use no market prices, so there is no market number here.
"""
from __future__ import annotations

import math
from datetime import date as Date

import numpy as np
import pandas as pd

from nba_lab.config import ARCHIVES, CACHE, KEYS, NAMES, REPORTS, read

ET = "America/New_York"
GID_PATTERN = r"^\d{6,12}$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
Z90 = 1.2815516

TEAMS = {
    "ATL": ("Atlanta Hawks", "#e03a3e"), "BOS": ("Boston Celtics", "#007a33"), "BKN": ("Brooklyn Nets", "#3a3a3a"),
    "CHA": ("Charlotte Hornets", "#1d8cab"), "CHI": ("Chicago Bulls", "#ce1141"), "CLE": ("Cleveland Cavaliers", "#860038"),
    "DAL": ("Dallas Mavericks", "#0064b1"), "DEN": ("Denver Nuggets", "#0e2240"), "DET": ("Detroit Pistons", "#c8102e"),
    "GS": ("Golden State Warriors", "#1d428a"), "HOU": ("Houston Rockets", "#ce1141"), "IND": ("Indiana Pacers", "#002d62"),
    "LAC": ("LA Clippers", "#c8102e"), "LAL": ("Los Angeles Lakers", "#552583"), "MEM": ("Memphis Grizzlies", "#5d76a9"),
    "MIA": ("Miami Heat", "#98002e"), "MIL": ("Milwaukee Bucks", "#00471b"), "MIN": ("Minnesota Timberwolves", "#236192"),
    "NO": ("New Orleans Pelicans", "#0c2340"), "NY": ("New York Knicks", "#006bb6"), "OKC": ("Oklahoma City Thunder", "#007ac1"),
    "ORL": ("Orlando Magic", "#0077c0"), "PHI": ("Philadelphia 76ers", "#006bb6"), "PHX": ("Phoenix Suns", "#e56020"),
    "POR": ("Portland Trail Blazers", "#e03a3e"), "SAC": ("Sacramento Kings", "#5a2d81"), "SA": ("San Antonio Spurs", "#8a8d8f"),
    "TOR": ("Toronto Raptors", "#ce1141"), "UTAH": ("Utah Jazz", "#3e2680"), "WSH": ("Washington Wizards", "#002b5c"),
}
SHADOWS = {"strength_forecasts": "Team strength research copy", "injury_forecasts": "Official injury report research copy",
           "context_forecasts": "Roster continuity research copy"}
GLOSSARY = [
    {"term": "Win chance", "text": "How often a team wins games like this one, according to the six models combined. 60% means about 6 wins in 10 such games."},
    {"term": "Six models", "text": "Six different statistical methods trained on the same past games. They often agree because they see the same inputs, so 6 of 6 agreeing is not 100%."},
    {"term": "Vote", "text": "How many of the six models lean toward each team. A 3-3 vote is a tie; the win chance comes from the combination method, not the vote."},
    {"term": "Spread and total", "text": "From a separate score model, not a sportsbook. The spread is the expected winning margin; the total is both teams' points combined."},
    {"term": "Range", "text": "8 in 10 games like this land inside the shown range. The chart is a smooth curve drawn through the score model's saved range."},
    {"term": "Research copies", "text": "Forecasts from changed versions of the models, saved for testing. None has passed its tests yet, so none changes the headline."},
    {"term": "Injuries", "text": "Players listed on the latest saved injury check. The original forecast does not use them."},
]


def clean(x):
    """Make numpy/pandas values JSON safe (NaN and inf become null)."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if math.isfinite(float(x)) else None
    if isinstance(x, pd.Timestamp):
        return None if pd.isna(x) else x.isoformat()
    if x is pd.NaT:
        return None
    return x


def team(abbr: str) -> tuple[str, str]:
    return TEAMS.get(abbr, (abbr, "#475569"))


def pmf(mu: float, sd: float, lo: int, hi: int) -> list[dict]:
    """Normal curve through the score model's 10/50/90 range, binned to whole points and renormalised."""
    x = np.arange(lo, hi + 1)
    cdf = lambda v: 0.5 * (1 + np.vectorize(math.erf)((v - mu) / (sd * math.sqrt(2))))
    p = cdf(x + 0.5) - cdf(x - 0.5)
    p = p / p.sum()
    return [{"x": int(a), "p": float(b)} for a, b in zip(x, p)]


# --------------------------------------------------------------------------- loading

def games_table() -> pd.DataFrame:
    path = CACHE / "games.parquet"
    if not path.exists():
        return pd.DataFrame()
    g = pd.read_parquet(path)
    g["tipoff"] = pd.to_datetime(g["tipoff"], utc=True)
    g["date_et"] = g["tipoff"].dt.tz_convert(ET).dt.strftime("%Y-%m-%d")
    return g.sort_values("tipoff").reset_index(drop=True)


def _frames(folder: str, day: str | None = None) -> pd.DataFrame:
    paths = sorted((ARCHIVES / folder).glob(f"{day or '*'}_*/predictions.parquet"))
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True) if paths else pd.DataFrame()


def saved(folder: str, day: str) -> pd.DataFrame:
    """Latest saved revision per game for this Eastern date (same rule as the dashboard's Today table)."""
    f = _frames(folder, day)
    return f.sort_values("created_at").drop_duplicates("game_id", keep="last").set_index("game_id") if len(f) else f


def forecast_dates() -> list[str]:
    root = ARCHIVES / "forecasts"
    return sorted({p.name[:10] for p in root.iterdir() if p.is_dir()}) if root.exists() else []


def track_record(games: pd.DataFrame) -> dict:
    """Earliest pregame revision per game, scored on finished games. Small samples are reported as they are."""
    f = _frames("forecasts")
    if f.empty or games.empty:
        return {}
    f["created"] = pd.to_datetime(f["created_at"], utc=True)
    f = f[f["created"] < pd.to_datetime(f["tipoff"], utc=True)].sort_values("created").drop_duplicates("game_id")
    done = games[games.completed].set_index("game_id")
    f = f[f.game_id.isin(done.index)]
    if f.empty:
        return {"games": 0}
    home_won = (done.loc[f.game_id, "home_score"].values > done.loc[f.game_id, "away_score"].values)
    picked_home = f.p_home.values > 0.5
    out = {"games": int(len(f)), "accuracy": float((picked_home == home_won).mean()), "home_team_accuracy": float(home_won.mean())}
    s = _frames("score_forecasts")
    if len(s):
        s["created"] = pd.to_datetime(s["created_at"], utc=True)
        s = s[s["created"] < pd.to_datetime(s["tipoff"], utc=True)].sort_values("created").drop_duplicates("game_id")
        s = s[s.game_id.isin(done.index)]
        if len(s):
            actual = done.loc[s.game_id, "home_score"].values - done.loc[s.game_id, "away_score"].values
            out["margin_miss"] = {"games": int(len(s)), "points": float(np.abs(s.margin_p50.values - actual).mean())}
    return out


# --------------------------------------------------------------------------- API views

def meta() -> dict:
    games = games_table()
    dates = forecast_dates()
    if games.empty or not dates:
        return {"ok": False, "reason": "No saved NBA forecasts yet. Run option 2 in START_NBA.bat to refresh data and save today's forecasts."}
    today = pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d")
    default = today if today in dates else next((d for d in dates if d > today), dates[-1])
    status = read(REPORTS / "CONFIRMATION.json").get("decision") if (REPORTS / "CONFIRMATION.json").exists() else None
    return {"ok": True, "dates": dates, "default_date": default, "today": today, "track_record": track_record(games),
            "evaluation_status": status,
            "reality_check": ("Research only. These models use no betting market prices and have not shown an advantage over the market. "
                              "Current injuries are shown for context; the original forecast does not use them.")}


def day_games(day: str) -> list[dict]:
    games = games_table()
    if games.empty:
        return []
    g = games[games.date_et.eq(day)]
    f = saved("forecasts", day)
    rows = []
    for r in g.itertuples():
        p = float(f.loc[r.game_id, "p_home"]) if r.game_id in f.index else None
        rows.append({"gid": r.game_id, "away": r.away, "home": r.home, "away_color": team(r.away)[1], "home_color": team(r.home)[1],
                     "tipoff_utc": r.tipoff.isoformat(), "completed": bool(r.completed), "started": bool(r.tipoff <= pd.Timestamp.now(tz="UTC")),
                     "away_score": r.away_score if r.completed else None, "home_score": r.home_score if r.completed else None, "p_home": p})
    return clean(rows)


def _team_summary(games: pd.DataFrame, abbr: str, season: int, before: pd.Timestamp) -> dict:
    g = games[(games.season == season) & games.completed & (games.tipoff < before) & ((games.home == abbr) | (games.away == abbr))]
    if g.empty:
        return {"record": "0-0", "games": 0, "pf": None, "pa": None, "last": []}
    home = g.home.eq(abbr)
    pf = np.where(home, g.home_score, g.away_score)
    pa = np.where(home, g.away_score, g.home_score)
    won = pf > pa
    return {"record": f"{int(won.sum())}-{int((~won).sum())}", "games": int(len(g)), "pf": float(pf.mean()), "pa": float(pa.mean()),
            "last": ["W" if w else "L" for w in won[-5:]]}


def _injuries(gid: str, home: str, away: str) -> dict:
    path = CACHE / "availability.csv"
    if not path.exists():
        return {"retrieved": None, "teams": {home: [], away: []}}
    a = pd.read_csv(path, dtype={"game_id": str})
    a = a[a.game_id.eq(gid)]
    out = {home: [], away: []}
    for r in a.sort_values("retrieved_at").drop_duplicates(["team", "player"], keep="last").itertuples():
        key = r.team if r.team in out else None
        if key is None:
            continue
        tone = "red" if str(r.status).lower() == "out" else "amber"
        out[key].append({"player": r.player, "status": r.status, "tone": tone, "updated": r.injury_published_at,
                         "note": r.warning if isinstance(r.warning, str) else ""})
    return {"retrieved": a.retrieved_at.max() if len(a) else None, "teams": out}


def game_detail(gid: str) -> dict | None:
    games = games_table()
    if games.empty:
        return None
    hit = games[games.game_id.eq(gid)]
    if hit.empty:
        return None
    g = hit.iloc[0]
    day, home, away = g.date_et, g.home, g.away
    tip_et = g.tipoff.tz_convert(ET)
    d = {"gid": gid, "date": day, "away": away, "home": home, "away_name": team(away)[0], "home_name": team(home)[0],
         "away_color": team(away)[1], "home_color": team(home)[1], "tipoff_utc": g.tipoff.isoformat(),
         "date_label": tip_et.strftime("%a, %b %d").replace(" 0", " "), "time_label": tip_et.strftime("%I:%M %p").lstrip("0"),
         "completed": bool(g.completed), "away_score": g.away_score if g.completed else None, "home_score": g.home_score if g.completed else None,
         "matchup": {t: _team_summary(games, t, int(g.season), g.tipoff) for t in (away, home)}}
    d["records"] = {t: d["matchup"][t]["record"] for t in (away, home)}
    d["injuries"] = _injuries(gid, home, away)

    f = saved("forecasts", day)
    d["has_forecast"] = gid in f.index
    if d["has_forecast"]:
        r = f.loc[gid]
        p = float(r.p_home)
        fav = home if p >= 0.5 else away
        d["headline"] = {"p_home": p, "favored": fav, "favored_name": team(fav)[0], "p_favored": max(p, 1 - p),
                         "saved_at": str(r.created_at), "model_version": r.model_version,
                         "p_label": "six-model combined forecast, frozen settings"}
        d["models"] = [{"name": NAMES[k], "p_home": float(r[k])} for k in KEYS]
        hv, av = int(r.home_votes), int(r.away_votes)
        d["vote"] = {"home": hv, "away": av, "tie": hv == av}
        d["disagreement_points"] = 100 * (float(r.member_max) - float(r.member_min))
        d["forecast_warning"] = r.warning if isinstance(r.warning, str) and r.warning else None
        d["sources"] = [{"name": label, "p_home": float(s.loc[gid, "p_home"])} for folder, label in SHADOWS.items()
                        if gid in (s := saved(folder, day)).index and "p_home" in s.columns]

    s = saved("score_forecasts", day)
    if gid in s.index:
        r = s.loc[gid]
        sd_m = (r.margin_p90 - r.margin_p10) / (2 * Z90)
        sd_t = (r.total_p90 - r.total_p10) / (2 * Z90)
        d["expected"] = {"home_pts": r.home_points, "away_pts": r.away_points, "margin": r.home_margin, "total": r.total, "margin_mid": r.margin_p50, "total_mid": r.total_p50,
                         "margin_range": [r.margin_p10, r.margin_p90], "total_range": [r.total_p10, r.total_p90],
                         "p_home_score_model": r.p_home_score_model, "spread_label": r.spread}
        if sd_m > 0 and sd_t > 0:
            mt = int(round(r.total_p50))
            d["distribution"] = {"margin": pmf(float(r.margin_p50), float(sd_m), -40, 40), "total": pmf(float(r.total_p50), float(sd_t), mt - 45, mt + 45)}
        if d.get("has_forecast"):
            d["sources"].append({"name": "Score model", "p_home": float(r.p_home_score_model)})

    if g.completed and d.get("headline"):
        winner = home if g.home_score > g.away_score else away
        d["result"] = {"winner": winner, "favorite_won": winner == d["headline"]["favored"]}
    return clean(d)


def glossary() -> list[dict]:
    return GLOSSARY


def valid_date(day: str) -> bool:
    try:
        Date.fromisoformat(day)
        return True
    except ValueError:
        return False
