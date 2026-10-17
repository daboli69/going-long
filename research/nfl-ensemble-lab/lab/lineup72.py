"""Phase 7.2: injury-adjusted expected lineups and lineup-change features (strictly as-of).

Per team-game, from information available before kickoff:
  normal lineup   = each player's average snap share over the team's last 4 completed games
  availability    = P(player participates) given his verified pregame report status and last practice
                    status, estimated ONLY from seasons before the target season (2016 uses the
                    deterministic rule Out/Doubtful = 0, else 1); reserve/IR from the PREVIOUS week's
                    weekly roster (known before this week's game); confirmed absences are Out, reserve,
                    or no longer on the team's roster.
  expected lineup = normal share x availability
  player value    = Phase 7 snap-model rating from that week's as-of fit (shrunk; offense: EPA/play added,
                    defense: EPA/play allowed)
Features are CHANGES versus the normal lineup (the lineup that produced the team's recent ratings), so a
player who has already been missing for weeks is not counted again (no double counting with ratings).
Without a verified report for the team-game, injury-dependent features are NaN (never 'healthy').
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import CACHE_DIR, RAW_DIR
from .players import UNITS, _positions, snap_shares

META = CACHE_DIR / "lineup72.json"
VALUES = CACHE_DIR / "lineup72_values.parquet"
RESERVE = ("RES", "PUP", "NFI", "RSN", "SUS", "EXE")
STARTER = 0.6            # average snap share over the last 4 games that defines a regular starter
OFF_UNITS, DEF_UNITS = ("QB", "OL", "SKILL"), ("DL", "LB", "DB")


def _practice(s) -> str:
    s = str(s or "").lower()
    return "dnp" if "did not" in s else "limited" if "limited" in s else "full" if "full" in s else "none"


def _status_key(report, practice) -> str:
    r = report if report in ("Out", "Doubtful", "Questionable") else "listed_no_status"
    return f"{r}|{_practice(practice)}"


def played_table(games: pd.DataFrame, seasons) -> pd.DataFrame:
    sh = snap_shares(games, seasons)
    return sh.assign(played=(sh["offense_pct"].fillna(0) + sh["defense_pct"].fillna(0)) > 0)


def availability_rates(valid: pd.DataFrame, played: pd.DataFrame, before_season: int) -> dict:
    """P(played | status, practice) from reported players in seasons < before_season (empirical, smoothed)."""
    v = valid[valid["season"] < before_season]
    if v.empty:
        return {}
    pl = set(zip(played.loc[played["played"], "game_id"], played.loc[played["played"], "gsis_id"]))
    v = v.assign(key=[_status_key(a, b) for a, b in zip(v["report_status"], v["practice_status"])],
                 y=[(g, p) in pl for g, p in zip(v["game_id"], v["gsis_id"])])
    out = {}
    for k, d in v.groupby("key"):
        prior = 0.0 if k.startswith("Out") else 0.5
        out[k] = float((d["y"].sum() + 5 * prior) / (len(d) + 5))     # light smoothing toward a status prior
    return out


def role_rates(games, valid, played, before_season: int) -> dict:
    """As-of P(played | status, practice, starter role) from seasons < before_season. Used ONLY by the live
    player table (display); the tested Phase 7.2 features use the pooled rates."""
    v = valid[valid["season"] < before_season]
    if v.empty:
        return {}
    pl = set(zip(played.loc[played["played"], "game_id"], played.loc[played["played"], "gsis_id"]))
    sh = played.sort_values("kickoff_utc")
    usual = {}
    for t, d in sh.groupby("team"):
        gl = d["game_id"].drop_duplicates().tolist()
        idx = {g: i for i, g in enumerate(gl)}
        for g in set(v.loc[v["team"] == t, "game_id"]):
            i = idx.get(g)
            if i is None or i < 4:
                continue
            x = d[d["game_id"].isin(gl[i - 4:i])].groupby("gsis_id")[["offense_pct", "defense_pct"]].sum().max(axis=1) / 4
            for p_, u in x.items():
                usual[(g, p_)] = u
    v = v.assign(key=[_status_key(a, b) for a, b in zip(v["report_status"], v["practice_status"])],
                 starter=[usual.get((g, p_), 0) >= STARTER for g, p_ in zip(v["game_id"], v["gsis_id"])],
                 y=[(g, p_) in pl for g, p_ in zip(v["game_id"], v["gsis_id"])])
    out = {}
    for (k, stt), d in v.groupby(["key", "starter"]):
        prior = 0.0 if k.startswith("Out") else 0.5
        out[f"{k}|{'starter' if stt else 'other'}"] = float((d["y"].sum() + 5 * prior) / (len(d) + 5))
    return out


def _deterministic(key: str) -> float:
    return 0.0 if key.startswith(("Out", "Doubtful")) else 1.0


def build(games: pd.DataFrame, valid: pd.DataFrame, inj_team: pd.DataFrame, seasons: list, progress=print) -> pd.DataFrame:
    from .snap_model import SAPM, choose_lambda, team_rows
    tstats = pd.read_parquet(CACHE_DIR / "team_game_stats.parquet")
    shares = snap_shares(games, seasons)
    played = shares.assign(played=(shares["offense_pct"].fillna(0) + shares["defense_pct"].fillna(0)) > 0)
    rows_ = team_rows(games[games["season"] >= 2016], tstats, shares)
    lam, _ = choose_lambda(rows_, shares, progress=lambda m: None)
    model = SAPM(rows_, shares, lam)
    cut = games[games["season"] >= 2016].groupby(["season", "week"])["kickoff_utc"].min().reset_index(name="cutoff_utc")
    fits = model.fit_schedule(cut, progress=lambda m: None)
    pos = _positions()
    rates = {s: availability_rates(valid, played, s) for s in sorted(games["season"].unique()) if s >= 2016}
    roster = {}
    for s in seasons:
        p = RAW_DIR / f"roster_weekly_{s}.parquet"
        if p.exists():
            r = pd.read_parquet(p, columns=["season", "week", "team", "gsis_id", "status"])
            from .availability import _team
            r["team"] = r["team"].map(_team)
            roster[s] = r
    vi = valid.assign(key=[_status_key(a, b) for a, b in zip(valid["report_status"], valid["practice_status"])])
    rep = {(g, t, p): k for g, t, p, k in zip(vi["game_id"], vi["team"], vi["gsis_id"], vi["key"])}
    have_rep = {(g, t) for g, t, a in zip(inj_team["game_id"], inj_team["team"], inj_team["inj_report_available"]) if a == 1}
    by_team = {t: d.sort_values("kickoff_utc") for t, d in shares.groupby("team")}
    out = []
    for g in games[games["season"] >= 2016].itertuples(index=False):
        fit = fits.get((g.season, g.week))
        prev_roster = None
        if g.season in roster and g.week > 1:
            rr = roster[g.season]
            rr = rr[rr["week"] == g.week - 1]
            prev_roster = rr
        for team in (g.home_team, g.away_team):
            r = {"game_id": g.game_id, "team": team}
            d = by_team.get(team)
            prior = d[d["kickoff_utc"] < g.kickoff_utc] if d is not None else None
            if fit is None or prior is None or prior.empty:
                out.append(r)
                continue
            last = prior["game_id"].drop_duplicates().iloc[-4:]
            sh = prior[prior["game_id"].isin(last)].groupby("gsis_id")[["offense_pct", "defense_pct"]].sum() / len(last)
            last_game = prior[prior["game_id"] == last.iloc[-1]].set_index("gsis_id")
            known = (g.game_id, team) in have_rep
            rt = rates.get(g.season) or {}
            res_ids, off_team = set(), set()
            if prev_roster is not None and len(prev_roster):
                tr = prev_roster[prev_roster["gsis_id"].isin(sh.index)]
                res_ids = set(tr.loc[(tr["team"] == team) & tr["status"].isin(RESERVE), "gsis_id"])
                off_team = set(sh.index) - set(tr.loc[tr["team"] == team, "gsis_id"]) if (tr["team"] == team).any() else set()
            avail, confirmed = {}, {}
            for p in sh.index:
                if p in res_ids or p in off_team:
                    avail[p], confirmed[p] = 0.0, True              # reserve/IR or left the roster (known last week)
                    continue
                k = rep.get((g.game_id, team, p))
                if k is None:
                    avail[p], confirmed[p] = 1.0, False             # not on a verified report: expected to play
                else:
                    avail[p] = rt.get(k, _deterministic(k)) if rt else _deterministic(k)
                    confirmed[p] = k.startswith("Out")
            r["p72_report_known"] = int(known)
            for side, col, units in (("off", "offense_pct", OFF_UNITS), ("def", "defense_pct", DEF_UNITS)):
                s = sh[col][sh[col] > 0]
                if s.empty:
                    continue
                ids = list(s.index)
                v = np.array([fit[side][model.pid[p]] if p in model.pid else 0.0 for p in ids])
                a = s.to_numpy()
                av = np.array([avail[p] for p in ids])
                grp = np.array([pos.get(p, "OTH") for p in ids])
                # replacement: the unit's bench (share < 0.5 and available) absorbs missing snaps at its own value
                exp_v = a * av * v
                miss = a * (1 - av)
                for u, gs in UNITS.items():
                    if (side == "off") != (u in OFF_UNITS):
                        continue
                    m = np.isin(grp, gs)
                    if not m.any():
                        continue
                    bench = m & (a < 0.5) & (av > 0.5)
                    bval = float(np.average(v[bench], weights=a[bench])) if bench.any() else 0.0
                    normal = float(a[m] @ v[m])
                    expected = float(exp_v[m].sum() + miss[m].sum() * bval)
                    r[f"p72_{u}_delta"] = expected - normal                            # change vs the recent lineup
                    r[f"p72_{u}_missing_share"] = float(miss[m].sum())                 # expected snaps lost
                    r[f"p72_{u}_uncertainty"] = float(np.sum(a[m] ** 2 * av[m] * (1 - av[m])))
                    st = m & (a >= STARTER)
                    r[f"p72_{u}_starters_out"] = float(np.sum(1 - av[st]))            # expected missing starters
                    r[f"p72_{u}_starters_confirmed_out"] = int(sum(1 for i in np.flatnonzero(st) if confirmed[ids[i]]))
                if side == "off":
                    ol = [p for p in s.sort_values(ascending=False).index if pos.get(p) == "OL"][:5]
                    r["p72_ol_expected_continuity"] = float(sum(avail[p] for p in ol) / 5) if len(ol) == 5 else np.nan
                    lg = last_game[last_game["offense_pct"] > 0.5] if len(last_game) else last_game
                    r["p72_ol_same_as_last_game"] = float(sum(p in lg.index for p in ol if avail[p] > 0.5) / 5) if len(ol) == 5 else np.nan
            if not known:                                   # never assume healthy without a verified report
                for c in [c for c in r if c.startswith("p72_") and c not in ("p72_report_known",)]:
                    if not c.endswith(("_continuity", "same_as_last_game")):
                        r[c] = np.nan
            out.append(r)
    latest = max(fits)                                         # newest as-of fit: values for the live player table
    inv = {i: p for p, i in model.pid.items()}
    pd.DataFrame({"gsis_id": [inv[i] for i in range(model.P)], "off_value": fits[latest]["off"], "def_value": fits[latest]["def"],
                  "fit_season": latest[0], "fit_week": latest[1]}).to_parquet(VALUES, index=False)
    live_season = int(games["season"].max())
    rr = role_rates(games, valid, played, live_season)
    META.write_text(json.dumps({"rates_by_season": {str(k): v for k, v in rates.items()}, "role_rates_live": rr,
                                "role_rates_season": live_season, "starter_share": STARTER,
                                "reserve_statuses": list(RESERVE), "lambda": lam}, indent=2))
    return pd.DataFrame(out)


def lineup_accuracy(games, valid, seasons) -> pd.DataFrame:
    """How well availability predicts participation for regular players (share >= 0.3 over last 4 games)."""
    shares = snap_shares(games, seasons)
    played = shares.assign(played=(shares["offense_pct"].fillna(0) + shares["defense_pct"].fillna(0)) > 0)
    pl = set(zip(played.loc[played["played"], "game_id"], played.loc[played["played"], "gsis_id"]))
    done = set(games.loc[games["completed"], "game_id"])
    vi = valid[valid["game_id"].isin(done)]
    vi = vi.assign(key=[_status_key(a, b) for a, b in zip(vi["report_status"], vi["practice_status"])])
    rows = []
    for s in sorted(x for x in vi["season"].unique() if x >= 2017):
        rt = availability_rates(valid, played, s)
        d = vi[vi["season"] == s]
        p = d["key"].map(lambda k: rt.get(k, _deterministic(k)))
        y = np.array([(g, q) in pl for g, q in zip(d["game_id"], d["gsis_id"])], dtype=float)
        det = d["key"].map(_deterministic).to_numpy()
        rows.append({"season": int(s), "reported_players": len(d), "brier_asof_rates": float(np.mean((p - y) ** 2)),
                     "brier_deterministic_rule": float(np.mean((det - y) ** 2)), "played_rate": float(y.mean())})
    return pd.DataFrame(rows)


def player_table(game_row: pd.Series, team: str) -> pd.DataFrame:
    """Live, per-player expected lineup for one team (analysis; not an input of the champion or registered challengers)."""
    from .availability import _team, load_injury_rows, player_names
    from .data_pipeline import GAMES_TABLE
    games = pd.read_parquet(GAMES_TABLE)
    season, week = int(game_row["season"]), int(game_row["week"])
    sh = snap_shares(games, [season - 1, season])
    sh = sh[(sh["team"] == team) & (sh["kickoff_utc"] < game_row["kickoff_utc"])]
    if sh.empty:
        return pd.DataFrame()
    last = sh.sort_values("kickoff_utc")["game_id"].drop_duplicates().iloc[-4:]
    s = sh[sh["game_id"].isin(last)].groupby("gsis_id")[["offense_pct", "defense_pct"]].sum() / len(last)
    meta = json.loads(META.read_text()) if META.exists() else {}
    rt = (meta.get("rates_by_season") or {}).get(str(season), {})
    vals = pd.read_parquet(VALUES).set_index("gsis_id") if VALUES.exists() else pd.DataFrame()
    rows = load_injury_rows([season])
    rows = rows[(rows["week"] == week) & (rows["team"] == team)].sort_values("available_at").drop_duplicates("gsis_id", keep="last")
    rep = rows.set_index("gsis_id")
    ro = RAW_DIR / f"roster_weekly_{season}.parquet"
    res = set()
    if ro.exists() and week > 1:
        r = pd.read_parquet(ro, columns=["week", "team", "gsis_id", "status"])
        r["team"] = r["team"].map(_team)
        r = r[(r["week"] == week - 1) & (r["team"] == team)]
        res = set(r.loc[r["status"].isin(RESERVE), "gsis_id"])
    pos, names = _positions(), player_names()
    out = []
    for p, x in s.iterrows():
        side = "offense" if x["offense_pct"] >= x["defense_pct"] else "defense"
        share = float(max(x["offense_pct"], x["defense_pct"]))
        if share < 0.15:
            continue
        if p in res:
            av, why, kind = 0.0, "reserve/IR on last week's roster", "confirmed absence"
        elif p in rep.index:
            k = _status_key(rep.loc[p, "report_status"], rep.loc[p, "practice_status"])
            rr = meta.get("role_rates_live") or {}
            av = rr.get(f"{k}|{'starter' if share >= STARTER else 'other'}", rt.get(k, _deterministic(k)))
            st = rep.loc[p, "report_status"] if isinstance(rep.loc[p, "report_status"], str) else "listed, no game status"
            why = f"{st} ({_practice(rep.loc[p, 'practice_status'])} practice)"
            kind = "confirmed absence" if st == "Out" else "projected (role-conditioned probability from past seasons)"
        else:
            av, why, kind = 1.0, "not on the report" if len(rep) else "no verified report yet",                 "expected" if len(rep) else "unknown (no report)"
        v = vals.loc[p, "off_value" if side == "offense" else "def_value"] if p in vals.index else None
        out.append({"player": names.get(p, p), "unit": pos.get(p, "OTH"), "side": side, "usual_snap_share": round(share, 2),
                    "starter": share >= STARTER, "availability": round(float(av), 2), "basis": why, "status_type": kind,
                    "expected_snap_share": round(share * float(av), 2),
                    "player_value_epa_per_play": None if v is None else round(float(v), 4)})
    return pd.DataFrame(out).sort_values(["side", "unit", "usual_snap_share"], ascending=[False, True, False])
