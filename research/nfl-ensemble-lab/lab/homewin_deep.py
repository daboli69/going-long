"""Deep home-win model. Frozen protocol: docs/HOMEWIN_DEEP_PREREGISTRATION.md (commit 741a13e7).

Data layer, kickoff-known features and the four base models. Every feature for week w
is built from rows timestamped before T_w = first kickoff of the week minus 90 minutes.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import CACHE_DIR, RAW_DIR
from .ingest import canonical_game_id, normalize_team

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import xgb_home_win as v1  # noqa: E402

CACHE = CACHE_DIR / "homewin_deep"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
START_SEASON = 2002
EVAL_START = 2012
MARGIN_TRAIN_START = 2004
DECISION_LEAD = pd.Timedelta(minutes=90)

RIDGE_RHO = 0.5
RIDGE_LAMBDA = 4.0
QB_N0 = 250
OUT_STATUSES = {"Out", "Doubtful", "Injured Reserve", "IR", "Suspended"}
RATINGS = ["pass_epa", "run_epa", "pass_sr", "run_sr"]
MARGIN_X = ["pass_epa_edge", "run_epa_edge", "qb_delta_diff", "rest_diff", "homefield"]
DEEP_X = ["pass_epa_edge", "run_epa_edge", "pass_sr_edge", "run_sr_edge", "qb_delta_home", "qb_delta_away",
          "elo_diff", "homefield", "rest_diff", "week"]
DEEP_MONOTONE = (1, 1, 1, 1, 1, -1, 1, 1, 0, 0)

# Reviewed nfldata-vs-ESPN neutral-site disagreements: gid -> reason.
NEUTRAL_ALLOWLIST: dict[str, str] = {
    "2021_01_GB_NO": "Moved to Jacksonville by Hurricane Ida; nfldata neutral is right, ESPN not flagged (reviewed 2026-10-28).",
}


class DataCheckError(RuntimeError):
    """A preregistered data check failed; the run must stop."""


@dataclass(frozen=True)
class Data:
    games: pd.DataFrame       # one row per regular-season game
    team_games: pd.DataFrame  # one row per team offense per played game
    qb_games: pd.DataFrame    # dropbacks and EPA per QB per played game
    injuries: pd.DataFrame    # season, week, team, gsis_id, report_status, available_at
    inactives: pd.DataFrame   # season, week, team, gsis_id, observed_at
    quotes: pd.DataFrame      # GOING T1 h2h quotes


# --------------------------------------------------------------------------- sources

def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def espn_events(year: int, live: bool, refresh: bool = False) -> list[dict]:
    """All ESPN regular-season events kicking off in calendar `year` (cached unless live)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"espn_events_{year}.json"
    if path.exists() and not live and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for e in _get_json(f"{ESPN_SCOREBOARD}?dates={year}&seasontype=2&limit=1000")["events"]:
        if e.get("season", {}).get("type") != 2:
            continue
        comp = e["competitions"][0]
        side = {c["homeAway"]: c for c in comp["competitors"]}
        try:
            home, away = normalize_team(side["home"]["team"]["abbreviation"]), normalize_team(side["away"]["team"]["abbreviation"])
        except (KeyError, ValueError):
            continue
        done = bool(comp.get("status", {}).get("type", {}).get("completed"))
        rows.append({"event_id": e["id"], "season": e["season"]["year"], "kickoff": e["date"], "home": home, "away": away,
                     "neutral": bool(comp.get("neutralSite")), "completed": done,
                     "home_score": float(side["home"]["score"]) if done else None,
                     "away_score": float(side["away"]["score"]) if done else None})
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def load_games(refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """nfldata API games joined to ESPN kickoffs; scores cross-checked (fails loudly)."""
    g = v1.load_data(START_SEASON, refresh)
    live = v1.current_season()
    espn = pd.DataFrame([r for y in range(START_SEASON, live + 2) for r in espn_events(y, live=y >= live, refresh=refresh)])
    espn["kickoff"] = pd.to_datetime(espn["kickoff"], utc=True)
    espn = espn.drop_duplicates("event_id")

    by_teams: dict[tuple, list] = {}
    for r in espn.itertuples(index=False):
        by_teams.setdefault((r.season, frozenset((r.home, r.away))), []).append(r)
    kick, ev_neutral, ev_ids, bad, unmatched = [], [], [], [], []
    for r in g.itertuples(index=False):
        cands = [e for e in by_teams.get((r.season, frozenset((r.home_id, r.away_id))), [])
                 if abs((e.kickoff.tz_localize(None).normalize() - r.date).days) <= 1]
        if len(cands) > 1 and sum(e.completed for e in cands) == 1:  # postponed duplicate (e.g. 2014 NYJ@BUF)
            cands = [e for e in cands if e.completed]
        if len(cands) != 1:
            kick.append(pd.NaT), ev_neutral.append(np.nan), ev_ids.append((None, None))
            unmatched.append(f"{r.season} wk{r.week} {r.away_id}@{r.home_id} ({len(cands)} ESPN matches)")
            continue
        e = cands[0]
        kick.append(e.kickoff), ev_neutral.append(float(e.neutral)), ev_ids.append((e.event_id, e.home))
        if r.played:
            hs, as_ = (e.home_score, e.away_score) if e.home == r.home_id else (e.away_score, e.home_score)
            if not e.completed or hs != r.score_home or as_ != r.score_away:
                bad.append(f"{r.season} wk{r.week} {r.away_id}@{r.home_id}: nfldata {r.score_away:.0f}-{r.score_home:.0f} "
                           f"vs ESPN {as_}-{hs}")
    g = g.assign(kickoff_utc=pd.to_datetime(pd.Series(kick, index=g.index), utc=True), espn_neutral=ev_neutral,
                 espn_event_id=[i for i, _ in ev_ids], espn_home=[h for _, h in ev_ids])
    played_unmatched = [u for u, p in zip(unmatched, g.loc[g["kickoff_utc"].isna(), "played"]) if p]
    if bad or played_unmatched:
        raise DataCheckError("Score cross-check failed:\n" + "\n".join((bad + played_unmatched)[:40]))
    # Unplayed games with no ESPN event fall back to noon US Eastern on the scheduled date.
    fallback = (g["date"] + pd.Timedelta(hours=17)).dt.tz_localize("UTC")
    g["kickoff_utc"] = g["kickoff_utc"].fillna(fallback)
    g["gid"] = [canonical_game_id(s, w, a, h) for s, w, a, h in zip(g["season"], g["week"], g["away_id"], g["home_id"])]
    g = g.rename(columns={"home_id": "home", "away_id": "away"})
    g["margin"] = g["score_home"] - g["score_away"]
    g["decision_utc"] = g.groupby(["season", "week"])["kickoff_utc"].transform("min") - DECISION_LEAD
    report = {"games": len(g), "played": int(g["played"].sum()), "espn_matched": int(g["espn_neutral"].notna().sum()),
              "score_mismatches": 0, "unplayed_without_espn_event": len(unmatched) - len(played_unmatched)}
    return g.sort_values(["kickoff_utc", "gid"]).reset_index(drop=True), report


def neutral_check(games: pd.DataFrame) -> dict:
    """nfldata `location` (lab games table) vs ESPN neutralSite, in seasons where ESPN flags any."""
    lab = pd.read_parquet(CACHE_DIR / "games.parquet")[["game_id", "neutral_site"]]
    m = games.merge(lab, left_on="gid", right_on="game_id", how="inner")
    flagged = m.groupby("season")["espn_neutral"].transform(lambda s: s.fillna(0).sum() > 0)
    m = m[flagged & m["espn_neutral"].notna()]
    dis = m[m["neutral_site"].astype(int) != m["espn_neutral"].astype(int)]
    unexplained = dis[~dis["gid"].isin(NEUTRAL_ALLOWLIST)]
    if len(unexplained):
        raise DataCheckError("Neutral-site disagreement (nfldata vs ESPN):\n" + unexplained[
            ["gid", "neutral_site", "espn_neutral"]].to_string(index=False))
    return {"compared": len(m), "seasons": sorted(int(s) for s in m["season"].unique()),
            "disagreements_allowlisted": {k: NEUTRAL_ALLOWLIST[k] for k in dis["gid"]},
            "model_flag_vs_nfldata_disagree": int((m["neutral"] != m["neutral_site"].astype(int)).sum())}


PBP_COLS = ["season", "week", "season_type", "home_team", "away_team", "posteam", "defteam", "play_type", "pass", "rush",
            "epa", "success", "qb_kneel", "qb_spike", "two_point_attempt", "passer_id", "passer_player_id", "rusher_player_id"]


def pbp_tables(games: pd.DataFrame, refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Per team-game offense pass/run EPA and success, and per QB-game dropback EPA, from raw plays."""
    from . import sources
    live = v1.current_season()
    tg_parts, qb_parts, prov, unmatched = [], [], {}, 0
    ids = dict(zip(zip(games["season"], games["week"], games["home"], games["away"]), games["gid"]))
    for s in range(START_SEASON, live + 1):
        entry = sources.download_pbp(s, live=s == live, force=refresh, progress=lambda m: None)
        prov[s] = entry["sha256"]
        cache = CACHE / f"pbp_agg_{s}_{entry['sha256'][:12]}.parquet"
        if cache.exists():
            both = pd.read_parquet(cache)
        else:
            p = pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=PBP_COLS)
            p = p[(p["season_type"] == "REG") & ((p["pass"] == 1) | (p["rush"] == 1)) & p["epa"].notna()
                  & ~p["play_type"].isin(["no_play", "qb_kneel", "qb_spike"]) & (p["qb_kneel"] != 1)
                  & (p["qb_spike"] != 1) & (p["two_point_attempt"] != 1) & p["posteam"].notna()]
            for c in ("home_team", "away_team", "posteam", "defteam"):
                p[c] = p[c].map(normalize_team)
            p["is_pass"] = (p["pass"] == 1).astype(int)
            p["qb"] = p["passer_id"].fillna(p["passer_player_id"]).fillna(p["rusher_player_id"])
            agg = p.groupby(["season", "week", "home_team", "away_team", "posteam", "defteam", "is_pass"]).agg(
                n=("epa", "size"), epa=("epa", "sum"), sr=("success", "sum")).reset_index()
            qb = p[p["is_pass"] == 1].groupby(["season", "week", "home_team", "away_team", "posteam", "qb"]).agg(
                n=("epa", "size"), epa=("epa", "sum")).reset_index()
            both = pd.concat([agg.assign(kind="team"), qb.assign(kind="qb")], ignore_index=True)
            both.to_parquet(cache)
        both["gid"] = [ids.get(k) for k in zip(both["season"], both["week"], both["home_team"], both["away_team"])]
        unmatched += int(both["gid"].isna().sum())
        both = both.dropna(subset=["gid"])
        tg_parts.append(both[both["kind"] == "team"])
        qb_parts.append(both[both["kind"] == "qb"])

    t = pd.concat(tg_parts, ignore_index=True)
    wide = t.pivot_table(index=["gid", "posteam", "defteam"], columns="is_pass", values=["n", "epa", "sr"], aggfunc="sum").fillna(0)
    wide.columns = [f"{v}_{'pass' if k else 'run'}" for v, k in wide.columns]
    tg = wide.reset_index().rename(columns={"posteam": "team", "defteam": "opp"})
    for kind in ("pass", "run"):
        tg[f"{kind}_epa"] = tg[f"epa_{kind}"] / tg[f"n_{kind}"].where(tg[f"n_{kind}"] > 0)
        tg[f"{kind}_sr"] = tg[f"sr_{kind}"] / tg[f"n_{kind}"].where(tg[f"n_{kind}"] > 0)
    meta = games.set_index("gid")[["season", "week", "kickoff_utc", "home", "neutral"]]
    tg = tg.join(meta, on="gid")
    tg["home_sign"] = np.where(tg["neutral"] == 1, 0, np.where(tg["team"] == tg["home"], 1, -1))
    q = pd.concat(qb_parts, ignore_index=True).rename(columns={"posteam": "team"})
    q = q[["gid", "team", "qb", "n", "epa"]].join(meta[["season", "kickoff_utc"]], on="gid")
    prov_report = {"pbp_sha256": {int(k): v for k, v in prov.items()}, "pbp_rows_unmatched_to_games": unmatched,
                   "team_games": len(tg), "qb_games": len(q)}
    return tg, q, prov_report


def load_injuries() -> pd.DataFrame:
    from . import availability
    r = availability.load_injury_rows(list(range(2009, v1.current_season() + 1)))
    return r[["season", "week", "team", "gsis_id", "report_status", "available_at", "source"]]


def load_inactives() -> pd.DataFrame:
    """Archived official inactives (lab.inactives10). None archived as of 2026-10-28."""
    rows = []
    for p in sorted((RAW_DIR / "archive" / "inactives").glob("official_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        c = d.get("content") or {}
        for team, players in (c.get("inactives") or {}).items():
            for pl in players:
                rows.append({"gid": c.get("event"), "team": team, "gsis_id": pl.get("gsis_id"),
                             "observed_at": pd.Timestamp(d.get("retrieved_at"), tz="UTC")})
    return pd.DataFrame(rows, columns=["gid", "team", "gsis_id", "observed_at"])


def load_quotes(refresh: bool = False) -> pd.DataFrame:
    """GOING T1 h2h quotes from GOING's own git history (local, read-only)."""
    path = CACHE / "going_quotes.parquet"
    if refresh or not path.exists():
        from . import market81
        market81.going_quotes().to_parquet(path)
    q = pd.read_parquet(path)
    return q[(q["market"] == "h2h") & q["side"].isin(["home", "away"])].copy()


def load_all(refresh: bool = False) -> tuple[Data, dict]:
    games, score_report = load_games(refresh)
    games, _ = _with_elo(games)
    tg, qb, pbp_report = pbp_tables(games, refresh)
    data = Data(games, tg, qb, load_injuries(), load_inactives(), load_quotes(refresh))
    return data, {"scores": score_report, "pbp": pbp_report}


def _with_elo(games: pd.DataFrame):
    elo_in = games.rename(columns={"home": "home_id", "away": "away_id"})
    out, ratings = v1.add_elo_pregame(elo_in)
    return out.rename(columns={"home_id": "home", "away_id": "away"}), ratings


# --------------------------------------------------------------------------- ratings

def _ridge(rows: pd.DataFrame, y: str, teams: list[str], prior: dict | None) -> dict:
    """y = mu + O[team] + D[opp] + h*home_sign, O and D shrunk toward the prior; returns {team: (O, D)}."""
    k = len(teams)
    idx = {t: i for i, t in enumerate(teams)}
    b0 = np.zeros(2 + 2 * k)
    if prior:
        for t, (o, d) in prior.items():
            if t in idx:
                b0[2 + idx[t]], b0[2 + k + idx[t]] = RIDGE_RHO * o, RIDGE_RHO * d
    lam = np.r_[1e-8, 1e-8, np.full(2 * k, RIDGE_LAMBDA)]
    rows = rows[rows[y].notna()]
    if rows.empty:
        b = b0
    else:
        n = rows[f"n_{y.split('_')[0]}"].to_numpy(float)
        w = n / n.mean()
        X = np.zeros((len(rows), 2 + 2 * k))
        X[:, 0] = 1
        X[:, 1] = rows["home_sign"].to_numpy()
        X[np.arange(len(rows)), 2 + rows["team"].map(idx).to_numpy()] = 1
        X[np.arange(len(rows)), 2 + k + rows["opp"].map(idx).to_numpy()] = 1
        A = X.T @ (X * w[:, None]) + np.diag(lam)
        b = np.linalg.solve(A, X.T @ (w * rows[y].to_numpy()) + lam * b0)
    return {t: (b[2 + i], b[2 + k + i]) for t, i in idx.items()}


def season_end_ratings(team_games: pd.DataFrame) -> dict:
    """{season: {rating: {team: (O, D)}}} fit on each full season, prior = rho * previous season."""
    teams = sorted(set(team_games["team"]) | set(team_games["opp"]))
    out, prev = {}, {r: None for r in RATINGS}
    for s, rows in team_games.groupby("season"):
        out[s] = {r: _ridge(rows, r, teams, prev[r]) for r in RATINGS}
        prev = out[s]
    return out


# --------------------------------------------------------------------------- QB

def qb_prior_mean(qb_games: pd.DataFrame) -> float:
    """Mean EPA/dropback over the first 250 career dropbacks of QBs debuting 2003-2011."""
    q = qb_games.sort_values(["kickoff_utc", "gid"])
    first = q.groupby("qb")["season"].transform("min")
    q = q[(first >= 2003) & (first <= 2011)].copy()
    q["cum_before"] = q.groupby("qb")["n"].cumsum() - q["n"]
    early = q[q["cum_before"] < QB_N0]
    return float(early["epa"].sum() / early["n"].sum())


def _qb_value(prior_rows: pd.DataFrame, prior_mean: float) -> pd.Series:
    agg = prior_rows.groupby("qb")[["n", "epa"]].sum()
    return (agg["epa"] + QB_N0 * prior_mean) / (agg["n"] + QB_N0)


def team_qb_state(data: Data, team: str, season: int, week: int, cutoff: pd.Timestamp, values: pd.Series,
                  prior_mean: float) -> dict:
    q = data.qb_games
    tq = q[(q["team"] == team) & (q["kickoff_utc"] < cutoff)]
    if tq.empty:
        return {"qb_expected": None, "qb_change": 0, "qb_delta": 0.0}
    last_gid = tq.loc[tq["kickoff_utc"].idxmax(), "gid"]
    last = tq[tq["gid"] == last_gid]
    starter = last.loc[last["n"].idxmax(), "qb"]

    inj = data.injuries
    rep = inj[(inj["season"] == season) & (inj["week"] == week) & (inj["team"] == team)
              & inj["available_at"].notna() & (inj["available_at"] < cutoff)]
    rep = rep.sort_values("available_at").drop_duplicates("gsis_id", keep="last")
    out_ids = set(rep.loc[rep["report_status"].isin(OUT_STATUSES), "gsis_id"])
    ina = data.inactives
    out_ids |= set(ina.loc[(ina["team"] == team) & (ina["observed_at"] < cutoff), "gsis_id"]) if len(ina) else set()

    expected, change = starter, 0
    if starter in out_ids:
        change = 1
        expected = None
        for pool in (tq[tq["season"] == season], tq[tq["season"] == season - 1]):
            alt = pool[~pool["qb"].isin(out_ids)].groupby("qb")["n"].sum()
            if len(alt):
                expected = alt.idxmax()
                break
    window = tq[tq["season"] == season]
    if window.empty:
        window = tq[tq["season"] == season - 1]
    w = window.groupby("qb")["n"].sum()
    window_value = float((w * values.reindex(w.index).fillna(prior_mean)).sum() / w.sum()) if w.sum() else prior_mean
    exp_value = float(values.get(expected, prior_mean)) if expected is not None else prior_mean
    return {"qb_expected": expected, "qb_change": change, "qb_delta": exp_value - window_value}


# --------------------------------------------------------------------------- weekly features

def week_cutoff(data: Data, season: int, week: int) -> pd.Timestamp:
    g = data.games
    return g.loc[(g["season"] == season) & (g["week"] == week), "decision_utc"].min()


def _rest(games: pd.DataFrame) -> pd.DataFrame:
    """Days since each team's previous scheduled game (schedule only, no results), capped."""
    sides = pd.concat([games[["gid", "kickoff_utc", "home"]].rename(columns={"home": "team"}),
                       games[["gid", "kickoff_utc", "away"]].rename(columns={"away": "team"})])
    sides = sides.sort_values(["team", "kickoff_utc"])
    sides["rest"] = sides.groupby("team")["kickoff_utc"].diff().dt.days.clip(upper=v1.REST_CAP).fillna(v1.REST_CAP)
    return sides.set_index(["gid", "team"])["rest"]


def week_features(data: Data, season: int, week: int, cutoff: pd.Timestamp | None = None,
                  end_ratings: dict | None = None, prior_mean: float | None = None,
                  rest: pd.Series | None = None) -> pd.DataFrame:
    """Kickoff-known features for every game of (season, week), using rows before `cutoff` only."""
    cutoff = week_cutoff(data, season, week) if cutoff is None else cutoff
    g = data.games[(data.games["season"] == season) & (data.games["week"] == week)].copy()
    tg = data.team_games[data.team_games["kickoff_utc"] < cutoff]
    if end_ratings is None:
        end_ratings = season_end_ratings(tg[tg["season"] < season])
    if prior_mean is None:
        prior_mean = qb_prior_mean(data.qb_games[data.qb_games["season"] <= 2011])
    rest = _rest(data.games) if rest is None else rest
    teams = sorted(set(data.team_games["team"]) | set(data.team_games["opp"]))
    prev = end_ratings.get(season - 1, {})
    cur = tg[tg["season"] == season]
    rat = {r: _ridge(cur, r, teams, prev.get(r)) for r in RATINGS}
    values = _qb_value(data.qb_games[data.qb_games["kickoff_utc"] < cutoff], prior_mean)

    rows = []
    for r in g.itertuples(index=False):
        row = {"gid": r.gid}
        for name in RATINGS:
            oh, dh = rat[name].get(r.home, (0.0, 0.0))
            oa, da = rat[name].get(r.away, (0.0, 0.0))
            row[f"{name}_edge"] = (oh + da) - (oa + dh)
        for side, team in (("home", r.home), ("away", r.away)):
            st = team_qb_state(data, team, season, week, cutoff, values, prior_mean)
            row[f"qb_delta_{side}"] = st["qb_delta"]
            row[f"qb_change_{side}"] = st["qb_change"]
            row[f"qb_expected_{side}"] = st["qb_expected"]
            row[f"rest_{side}"] = rest.get((r.gid, team), v1.REST_CAP)
        row["qb_delta_diff"] = row["qb_delta_home"] - row["qb_delta_away"]
        row["rest_diff"] = row["rest_home"] - row["rest_away"]
        row["homefield"] = 1 - int(r.neutral)
        row["elo_diff"] = r.home_elo - r.away_elo
        row["elo_prob_home"] = r.elo_prob_home
        row["week"] = week
        rows.append(row)
    return pd.DataFrame(rows)


def all_week_features(data: Data, first_season: int = 2003, progress=print) -> pd.DataFrame:
    end = season_end_ratings(data.team_games[data.team_games["kickoff_utc"] < data.games["decision_utc"].max()])
    pm = qb_prior_mean(data.qb_games[data.qb_games["season"] <= 2011])
    rest = _rest(data.games)
    weeks = data.games[data.games["season"] >= first_season][["season", "week"]].drop_duplicates().sort_values(["season", "week"])
    parts = []
    for s, w in weeks.itertuples(index=False):
        # end-of-season ratings of earlier seasons only: built from complete earlier seasons
        parts.append(week_features(data, s, w, end_ratings={k: v for k, v in end.items() if k < s}, prior_mean=pm, rest=rest))
        if w == 1:
            progress(f"  features {s}")
    f = pd.concat(parts, ignore_index=True)
    return f.merge(data.games[["gid", "season", "kickoff_utc", "decision_utc", "played", "tie", "margin", "y_home_win"]], on="gid")


# --------------------------------------------------------------------------- market

def market_probability(quotes: pd.DataFrame, home: str, away: str, kickoff: pd.Timestamp, cutoff: pd.Timestamp) -> dict:
    """Median across books of each book's latest no-vig home probability observed before `cutoff`.

    A quote counts only if both the book's last_update and GOING's commit time precede the cutoff,
    and the quote precedes kickoff.
    """
    q = quotes[(quotes["home"] == home) & (quotes["away"] == away)
               & ((quotes["commence_time"] - kickoff).abs() < pd.Timedelta(hours=36))
               & (quotes["quote_time"] < kickoff) & (quotes["quote_time"] < cutoff) & (quotes["committed_at"] < cutoff)]
    if q.empty:
        return {"p_home": np.nan, "books": 0, "quote_time": None}
    w = q.sort_values("quote_time").pivot_table(index=["book", "quote_time"], columns="side", values="price", aggfunc="last")
    w = w.dropna().reset_index().sort_values("quote_time").groupby("book").tail(1)
    if w.empty or not {"home", "away"} <= set(w.columns):
        return {"p_home": np.nan, "books": 0, "quote_time": None}
    ph = np.where(w["home"] < 0, -w["home"] / (-w["home"] + 100), 100 / (w["home"] + 100))
    pa = np.where(w["away"] < 0, -w["away"] / (-w["away"] + 100), 100 / (w["away"] + 100))
    ok = (w["home"].abs() >= 100) & (w["away"].abs() >= 100)
    p = (ph / (ph + pa))[ok.to_numpy()]
    if not len(p):
        return {"p_home": np.nan, "books": 0, "quote_time": None}
    return {"p_home": float(np.median(p)), "books": int(len(p)), "quote_time": str(w["quote_time"].max())}


# --------------------------------------------------------------------------- models

def margin_predict(train: pd.DataFrame, test: pd.DataFrame, oos_resid: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    X, y = train[MARGIN_X].to_numpy(float), train["margin"].to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    if len(oos_resid) >= 256:
        sigma = float(np.std(oos_resid, ddof=1))
    else:
        resid = y - X @ beta
        sigma = float(np.sqrt(resid @ resid / (len(y) - X.shape[1])))
    pred = test[MARGIN_X].to_numpy(float) @ beta
    return pred, norm.cdf(pred / sigma), sigma


def platt(p_hist: np.ndarray, y_hist: np.ndarray, p_new: np.ndarray) -> np.ndarray:
    if len(p_hist) < 256:
        return p_new
    from sklearn.linear_model import LogisticRegression
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))  # noqa: E731
    m = LogisticRegression(C=1e6).fit(lg(p_hist)[:, None], y_hist)
    return m.predict_proba(lg(p_new)[:, None])[:, 1]


def tune_deep(train: pd.DataFrame, season: int, n_trials: int = 25) -> dict:
    import optuna
    from sklearn.metrics import log_loss
    from xgboost import XGBClassifier
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    fit = train[train["season"] < season - 2]
    val = train[train["season"] >= season - 2]

    def objective(trial):
        params = dict(max_depth=trial.suggest_int("max_depth", 2, 5),
                      learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                      min_child_weight=trial.suggest_float("min_child_weight", 1, 20),
                      subsample=trial.suggest_float("subsample", 0.6, 1.0),
                      colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
                      reg_lambda=trial.suggest_float("reg_lambda", 0.1, 10, log=True))
        m = XGBClassifier(n_estimators=1000, early_stopping_rounds=50, monotone_constraints=DEEP_MONOTONE,
                          eval_metric="logloss", random_state=0, **params)
        m.fit(fit[DEEP_X], fit["y_home_win"], eval_set=[(val[DEEP_X], val["y_home_win"])], verbose=False)
        return log_loss(val["y_home_win"], m.predict_proba(val[DEEP_X])[:, 1], labels=[0, 1])

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=0))
    study.optimize(objective, n_trials=n_trials)
    return study.best_params


def deep_predict(train: pd.DataFrame, test: pd.DataFrame, params: dict) -> np.ndarray:
    from xgboost import XGBClassifier
    train = train.sort_values("kickoff_utc")
    cut = int(len(train) * 0.85)
    fit, val = train.iloc[:cut], train.iloc[cut:]
    m = XGBClassifier(n_estimators=1000, early_stopping_rounds=50, monotone_constraints=DEEP_MONOTONE,
                      eval_metric="logloss", random_state=0, **params)
    m.fit(fit[DEEP_X], fit["y_home_win"], eval_set=[(val[DEEP_X], val["y_home_win"])], verbose=False)
    return m.predict_proba(test[DEEP_X])[:, 1]


def v1_frame(data: Data) -> tuple[pd.DataFrame, pd.DataFrame]:
    """xgb_home_win.py features (v1) for every played non-tied game, keyed by gid."""
    g = data.games.rename(columns={"home": "home_id", "away": "away_id"})
    hist = v1.build_team_history(g)
    X, y, seasons, dates, ids = v1.build_feature_matrix(g, hist, return_ids=True)
    gid = g.set_index("game_id").loc[ids, "gid"].to_numpy()
    return X.assign(gid=gid), hist


def perturb_after(data: Data, cutoff: pd.Timestamp, season: int, week: int, seed: int = 0) -> Data:
    """Corrupt every result, play aggregate, injury row, inactive and quote at or after `cutoff` (leakage tests)."""
    rng = np.random.default_rng(seed)
    g = data.games.copy()
    late = g["kickoff_utc"] >= cutoff
    g.loc[late & g["played"], "score_home"] = rng.integers(0, 60, int((late & g["played"]).sum()))
    g.loc[late & g["played"], "score_away"] = rng.integers(0, 60, int((late & g["played"]).sum()))
    g["margin"] = g["score_home"] - g["score_away"]
    g, _ = _with_elo(g.drop(columns=["home_elo", "away_elo", "elo_prob_home"]))
    tg = data.team_games.copy()
    lt = tg["kickoff_utc"] >= cutoff
    for c in ("pass_epa", "run_epa", "pass_sr", "run_sr"):
        tg.loc[lt, c] = rng.normal(0, 1, int(lt.sum()))
    q = data.qb_games.copy()
    lq = q["kickoff_utc"] >= cutoff
    q.loc[lq, "epa"] = rng.normal(0, 30, int(lq.sum()))
    q.loc[lq, "n"] = rng.integers(1, 60, int(lq.sum()))
    inj = data.injuries.copy()
    inj.loc[inj["available_at"] >= cutoff, "report_status"] = "Out"
    extra = q[q["season"].isin([season, season - 1])].drop_duplicates(["team", "qb"])[["team", "qb"]].rename(columns={"qb": "gsis_id"})
    inj = pd.concat([inj, extra.assign(season=season, week=week, report_status="Out", available_at=cutoff,
                                       source="perturb")], ignore_index=True)
    quotes = data.quotes.copy()
    quotes.loc[quotes["committed_at"] >= cutoff, "price"] = rng.choice([-500, 400], int((quotes["committed_at"] >= cutoff).sum()))
    return replace(data, games=g, team_games=tg, qb_games=q, injuries=inj, quotes=quotes)
