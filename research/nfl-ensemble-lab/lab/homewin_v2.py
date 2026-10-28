"""Home-win study v2. Frozen protocol: docs/HOMEWIN_V2_PREREGISTRATION.md (commit 18e98172).

Power, walk-forward expected points, per-game decision points, stacking and CLV, built on lab.homewin_deep.
"""
from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

from . import homewin_deep as h
from . import homewin_eval as ev
from .config import LAB_ROOT, RAW_DIR

PREREG_COMMIT = "18e98172"
REPORT_DIR = LAB_ROOT / "reports" / "homewin_v2"
CACHE = h.CACHE / "v2"
SESOI_LL = 0.005
SESOI_CLV = 0.005
POINTS = ["open", "wed", "fri", "t90", "close"]
CLV_POINTS = ["open", "wed", "fri", "t90"]
ET = "America/New_York"


# --------------------------------------------------------------------------- decision points

def decision_points(games: pd.DataFrame) -> pd.DataFrame:
    """Per game: open, Wednesday, Friday, T-90 and close timestamps (UTC), each capped at kickoff - 90 min."""
    k = games["kickoff_utc"]
    local = k.dt.tz_convert(ET)
    day = local.dt.normalize().dt.tz_localize(None)
    dow = day.dt.dayofweek  # Mon=0 ... Sun=6

    def at(d, hour):
        return (d + pd.Timedelta(hours=hour)).dt.tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")

    two_before = day - pd.Timedelta(days=2)
    open_day = two_before - pd.to_timedelta((two_before.dt.dayofweek - 6) % 7, unit="D")
    wed_day = day - pd.to_timedelta(((dow - 2) % 7).replace(0, 7), unit="D")
    fri_day = day - pd.to_timedelta(((dow - 4) % 7).replace(0, 7), unit="D")
    t90 = k - h.DECISION_LEAD
    out = pd.DataFrame({"gid": games["gid"], "kickoff_utc": k,
                        "open": at(open_day, 20), "wed": at(wed_day, 12), "fri": at(fri_day, 17), "t90": t90, "close": k})
    for p in ("open", "wed", "fri"):
        out[p] = out[p].where(out[p] < t90, t90)
    return out


# --------------------------------------------------------------------------- 0. power

def power(data: h.Data) -> dict:
    z_ll = norm.ppf(1 - 0.0125 / 2) + norm.ppf(0.80)
    z_clv = norm.ppf(1 - 0.05 / 2) + norm.ppf(0.80)
    v1 = pd.read_parquet(h.CACHE / "walk_forward.parquet")
    y = v1["y_home_win"].to_numpy(float)
    d = ev._ll(y, v1["p_margin_platt"].to_numpy()) - ev._ll(y, v1["p_elo"].to_numpy())
    wk = pd.Series(d).groupby((v1["season"].astype(str) + "_" + v1["week"].astype(str)).to_numpy()).mean()
    sd_w = float(wk.std(ddof=1))
    n_hist = len(wk)
    n_ll = int(np.ceil((z_ll * sd_w / SESOI_LL) ** 2))
    res = {"prereg_commit": PREREG_COMMIT,
           "log_loss": {"source": "v1 margin_platt - elo, week means (design-stage)", "sd_week_mean": sd_w,
                        "history_weeks": n_hist, "history_mde": z_ll * sd_w / np.sqrt(n_hist), "sesoi": SESOI_LL,
                        "prospective_mde_by_weeks": {n: z_ll * sd_w / np.sqrt(n) for n in (1, 4, 8, 17, 34, 68)},
                        "N_LL_weeks": n_ll}}

    g = data.games[data.games["played"] & ~data.games["tie"]]
    pts = decision_points(g).set_index("gid")
    clv = {}
    for p in CLV_POINTS:
        moves, weeks = [], []
        for r in g.itertuples(index=False):
            a = h.market_probability(data.quotes, r.home, r.away, r.kickoff_utc, pts.at[r.gid, p])["p_home"]
            if np.isnan(a):
                continue
            c = h.market_probability(data.quotes, r.home, r.away, r.kickoff_utc, r.kickoff_utc)["p_home"]
            if np.isnan(c):
                continue
            moves.append(c - a)
            weeks.append(f"{r.season}_{r.week}")
        m = np.asarray(moves)
        n_games, n_weeks = len(m), len(set(weeks))
        rms = float(np.sqrt((m ** 2).mean())) if n_games else np.nan  # SD of CLV under random sides
        per_week = n_games / n_weeks if n_weeks else np.nan
        mde_hist = z_clv * rms / np.sqrt(n_games) if n_games else np.nan
        n_clv = int(np.ceil((z_clv * rms / SESOI_CLV) ** 2 / per_week)) if n_games else None
        clv[p] = {"games": n_games, "weeks": n_weeks, "rms_move": rms, "share_zero_move": float((m == 0).mean()) if n_games else None,
                  "history_mde": mde_hist, "games_per_week": per_week, "N_CLV_weeks": n_clv,
                  "prospective_mde_by_weeks": {n: z_clv * rms / np.sqrt(per_week * n) for n in (1, 4, 8, 17, 34)} if n_games else {}}
    ok = {p: v for p, v in clv.items() if v["games"]}
    primary = min(CLV_POINTS, key=lambda p: (ok[p]["history_mde"] if p in ok else np.inf, CLV_POINTS.index(p)))
    res["clv"] = {"points": clv, "primary_point_original_rule": primary, "N_CLV_weeks_original_rule": clv[primary]["N_CLV_weeks"],
                  "sesoi": SESOI_CLV}
    # Amendment 1: only points whose typical move can contain an effect of size SESOI
    eligible = [p for p in CLV_POINTS if clv[p]["games"] and clv[p]["rms_move"] >= 2 * SESOI_CLV]
    amended = min(eligible, key=lambda p: (clv[p]["N_CLV_weeks"], CLV_POINTS.index(p)))
    res["clv"] |= {"primary_point": amended, "N_CLV_weeks": clv[amended]["N_CLV_weeks"], "rule": "Amendment 1"}
    return res


PRIMARY_CLV_POINT = "fri"   # Amendment 1, committed 98519f2f before any CLV sign was computed
N_CLV_WEEKS = 7
N_LL_WEEKS = 1126


# --------------------------------------------------------------------------- 1. walk-forward expected points

EP_VALUES = np.array([-7.0, -3.0, -2.0, 0.0, 2.0, 3.0, 7.0])
EP_X = ["down", "ydstogo", "yardline_100", "half_seconds_remaining", "home", "dome", "pos_to", "def_to"]
EP_PARAMS = dict(objective="multi:softprob", n_estimators=200, max_depth=5, learning_rate=0.1, subsample=0.8,
                 colsample_bytree=0.8, min_child_weight=5, tree_method="hist", random_state=0, n_jobs=-1)
RAW_COLS = ["game_id", "play_id", "season", "week", "season_type", "home_team", "away_team", "posteam", "defteam", "down",
            "ydstogo", "yardline_100", "half_seconds_remaining", "game_half", "posteam_timeouts_remaining",
            "defteam_timeouts_remaining", "roof", "play_type", "pass", "rush", "td_team", "field_goal_result", "safety",
            "qb_kneel", "qb_spike", "two_point_attempt", "passer_id", "passer_player_id", "rusher_player_id", "epa", "success"]


def _norm(s: pd.Series) -> pd.Series:
    return s.map(lambda x: h.normalize_team(x) if isinstance(x, str) and x else None)


def raw_plays(season: int) -> pd.DataFrame:
    """Scrimmage plays with the next-score label, from raw events (nflverse epa/success kept for comparison only)."""
    p = pd.read_parquet(RAW_DIR / f"play_by_play_{season}.parquet", columns=RAW_COLS)
    p = p[p["season_type"] == "REG"].sort_values(["game_id", "play_id"]).reset_index(drop=True)
    for c in ("home_team", "away_team", "posteam", "defteam", "td_team"):
        p[c] = _norm(p[c])
    td = p["td_team"].notna()
    fg = p["field_goal_result"].eq("made")
    sf = p["safety"].eq(1)
    p["score_team"] = np.where(td, p["td_team"], np.where(fg, p["posteam"], np.where(sf, p["defteam"], None)))
    p["score_pts"] = np.where(td, 7.0, np.where(fg, 3.0, np.where(sf, 2.0, 0.0)))
    p["scrim"] = (p["down"].between(1, 4) & p["posteam"].notna() & p["yardline_100"].notna()
                  & p["half_seconds_remaining"].notna())
    events = p.loc[p["score_team"].notna(), ["game_id", "game_half", "play_id", "score_team", "score_pts"]].rename(
        columns={"play_id": "ev_play", "score_team": "next_team", "score_pts": "next_pts"})
    s = p[p["scrim"]].drop(columns=["score_team", "score_pts"])
    s = pd.merge_asof(s.sort_values("play_id"), events.sort_values("ev_play"), left_on="play_id", right_on="ev_play",
                      by=["game_id", "game_half"], direction="forward")
    s = s.sort_values(["game_id", "play_id"]).reset_index(drop=True)
    sign = np.where(s["next_team"].isna(), 0.0, np.where(s["next_team"] == s["posteam"], 1.0, -1.0))
    s["label_value"] = sign * s["next_pts"].fillna(0.0)
    s["label"] = s["label_value"].map({v: i for i, v in enumerate(EP_VALUES)}).astype(int)
    s["home"] = (s["posteam"] == s["home_team"]).astype(int)
    s["dome"] = s["roof"].isin(["dome", "closed"]).astype(int)
    s["pos_to"] = s["posteam_timeouts_remaining"].fillna(3)
    s["def_to"] = s["defteam_timeouts_remaining"].fillna(3)
    return s


def _epa(s: pd.DataFrame) -> np.ndarray:
    """EP_after - EP_before. A score on the play or before the next scrimmage play ends the chain."""
    g = s.groupby(["game_id", "game_half"])
    nxt_play, nxt_ep, nxt_pos = g["play_id"].shift(-1), g["ep"].shift(-1), g["posteam"].shift(-1)
    scored = s["ev_play"].notna() & (nxt_play.isna() | (s["ev_play"] < nxt_play))
    after = np.where(scored, s["label_value"],
                     np.where(nxt_play.isna(), 0.0, np.where(nxt_pos == s["posteam"], nxt_ep, -nxt_ep)))
    return after - s["ep"].to_numpy()


def walk_forward_ep(first: int = 2003, last: int | None = None, progress=print) -> dict:
    """Each season's EP model is fit on up to 10 earlier seasons only; cached per input hashes."""
    import hashlib
    from xgboost import XGBClassifier
    from . import sources
    last = last or h.v1.current_season()
    CACHE.mkdir(parents=True, exist_ok=True)
    man = sources.load_manifest()
    raws, out = {}, {}
    for S in range(first, last + 1):
        train = list(range(max(h.START_SEASON, S - 10), S))
        key = hashlib.sha256("".join(man[f"nflverse_pbp_{t}"]["sha256"] for t in train + [S]).encode()).hexdigest()[:12]
        path = CACHE / f"ep_{S}_{key}.parquet"
        out[S] = path
        if path.exists():
            continue
        for t in train + [S]:
            if t not in raws:
                raws[t] = raw_plays(t)
        tr = pd.concat([raws[t] for t in train], ignore_index=True)
        m = XGBClassifier(num_class=len(EP_VALUES), **EP_PARAMS).fit(tr[EP_X], tr["label"])
        s = raws[S].copy()
        s["ep"] = m.predict_proba(s[EP_X]) @ EP_VALUES
        s["epa_wf"] = _epa(s)
        s["success_wf"] = (s["epa_wf"] > 0).astype(float)
        s.to_parquet(path)
        progress(f"  EP {S}: fit on {train[0]}-{train[-1]}, {len(tr)} plays")
        for t in [t for t in raws if t < S - 10]:
            raws.pop(t)
    return out


def wf_tables(games: pd.DataFrame, ep_paths: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """team_games / qb_games shaped like homewin_deep.pbp_tables, from walk-forward EPA; plus the EPA comparison."""
    ids = dict(zip(zip(games["season"], games["week"], games["home"], games["away"]), games["gid"]))
    team_parts, qb_parts, cmp = [], [], {}
    for S, path in sorted(ep_paths.items()):
        s = pd.read_parquet(path)
        p = s[((s["pass"] == 1) | (s["rush"] == 1)) & s["epa_wf"].notna()
              & ~s["play_type"].isin(["no_play", "qb_kneel", "qb_spike"]) & (s["qb_kneel"] != 1)
              & (s["qb_spike"] != 1) & (s["two_point_attempt"] != 1)].copy()
        both = p[p["epa"].notna()]
        cmp[int(S)] = {"plays": int(len(both)), "corr": float(np.corrcoef(both["epa_wf"], both["epa"])[0, 1]),
                       "mean_diff": float((both["epa_wf"] - both["epa"]).mean()),
                       "mean_abs_diff": float((both["epa_wf"] - both["epa"]).abs().mean()),
                       "success_agree": float(((both["epa_wf"] > 0) == (both["epa"] > 0)).mean())}
        p["is_pass"] = (p["pass"] == 1).astype(int)
        p["qb"] = p["passer_id"].fillna(p["passer_player_id"]).fillna(p["rusher_player_id"])
        p["gid"] = [ids.get(k) for k in zip(p["season"], p["week"], p["home_team"], p["away_team"])]
        p = p.dropna(subset=["gid"])
        team_parts.append(p.groupby(["gid", "posteam", "defteam", "is_pass"]).agg(
            n=("epa_wf", "size"), epa=("epa_wf", "sum"), sr=("success_wf", "sum"), epa_nv=("epa", "sum")).reset_index())
        qb_parts.append(p[p["is_pass"] == 1].groupby(["gid", "posteam", "qb"]).agg(
            n=("epa_wf", "size"), epa=("epa_wf", "sum")).reset_index())
    t = pd.concat(team_parts, ignore_index=True)
    tgc = t.groupby(["gid", "posteam"])[["n", "epa", "epa_nv"]].sum()
    cmp["team_game_epa_per_play_corr"] = float(np.corrcoef(tgc["epa"] / tgc["n"], tgc["epa_nv"] / tgc["n"])[0, 1])
    wide = t.pivot_table(index=["gid", "posteam", "defteam"], columns="is_pass", values=["n", "epa", "sr"],
                         aggfunc="sum").fillna(0)
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
    return tg, q, cmp


def wf_prior_mean(data: h.Data, qb_wf: pd.DataFrame) -> float:
    """QB prior as preregistered (QBs debuting 2003-2011); 2002 veterans identified from raw 2002 dropbacks."""
    vets = set(data.qb_games.loc[data.qb_games["season"] == 2002, "qb"])
    return h.qb_prior_mean(qb_wf[(qb_wf["season"] <= 2011) & ~qb_wf["qb"].isin(vets)])


# --------------------------------------------------------------------------- 2. per-game decision points

RESULT_LAG = pd.Timedelta(hours=4)  # a game's result counts once kickoff + 4h precedes the point


class PointBuilder:
    """Kickoff-known features at an arbitrary point P: results before P - 4h, injuries/inactives before P."""

    def __init__(self, data: h.Data, prior_mean: float):
        self.data, self.pm = data, prior_mean
        self.teams = sorted(set(data.team_games["team"]) | set(data.team_games["opp"]))
        self.end = h.season_end_ratings(data.team_games)
        self.tg = data.team_games.sort_values("kickoff_utc")
        self.tg_k = self.tg["kickoff_utc"].astype("int64").to_numpy()
        self.qb = data.qb_games.sort_values("kickoff_utc")
        self.qb_k = self.qb["kickoff_utc"].astype("int64").to_numpy()
        self.qb_team = {t: d for t, d in self.qb.groupby("team")}
        inj = data.injuries[data.injuries["available_at"].notna()]
        self.inj = {k: d.sort_values("available_at") for k, d in inj.groupby(["season", "week", "team"])}
        self.ina = data.inactives
        self.rest = h._rest(data.games)
        self._elo = self._elo_history(data.games)
        self._rat, self._val = {}, {}

    @staticmethod
    def _elo_history(games):
        v1 = h.v1
        ratings, season, hist = {}, None, {}
        for g in games.sort_values("kickoff_utc").itertuples(index=False):
            if g.season != season:
                ratings = {t: v1.ELO_START + (1 - v1.ELO_REVERT) * (r - v1.ELO_START) for t, r in ratings.items()}
                season = g.season
            hh, aa = ratings.get(g.home, v1.ELO_START), ratings.get(g.away, v1.ELO_START)
            if not g.played:
                continue
            gap = hh + (0 if g.neutral else v1.ELO_HFA) - aa
            exp = 1 / (1 + 10 ** (-gap / 400))
            mg = g.score_home - g.score_away
            act = 1.0 if mg > 0 else 0.0 if mg < 0 else 0.5
            mult = 1.0 if mg == 0 else np.log(abs(mg) + 1) * 2.2 / ((gap if mg > 0 else -gap) * 0.001 + 2.2)
            dl = v1.ELO_K * mult * (act - exp)
            ratings[g.home], ratings[g.away] = hh + dl, aa - dl
            for t, r in ((g.home, hh + dl), (g.away, aa - dl)):
                hist.setdefault(t, []).append((g.kickoff_utc.value, g.season, r))
        return {t: (np.array([x[0] for x in v], dtype=np.int64), np.array([x[1] for x in v]), np.array([x[2] for x in v]))
                for t, v in hist.items()}

    def elo(self, team, season, R):
        v1 = h.v1
        if team not in self._elo:
            return v1.ELO_START
        k, s, r = self._elo[team]
        i = np.searchsorted(k, R.value, side="left") - 1
        if i < 0:
            return v1.ELO_START
        return r[i] if s[i] == season else v1.ELO_START + (1 - v1.ELO_REVERT) ** (season - s[i]) * (r[i] - v1.ELO_START)

    def ratings(self, season, R):
        n = int(np.searchsorted(self.tg_k, R.value, side="left"))
        key = (season, n)
        if key not in self._rat:
            cur = self.tg.iloc[:n]
            cur = cur[cur["season"] == season]
            prev = self.end.get(season - 1, {})
            self._rat[key] = {r: h._ridge(cur, r, self.teams, prev.get(r)) for r in h.RATINGS}
        return self._rat[key]

    def values(self, R):
        n = int(np.searchsorted(self.qb_k, R.value, side="left"))
        if n not in self._val:
            self._val[n] = h._qb_value(self.qb.iloc[:n], self.pm)
        return self._val[n]

    def qb_state(self, team, season, week, R, P, values):
        tq = self.qb_team.get(team)
        if tq is None:
            return 0.0, 0, None
        tq = tq[tq["kickoff_utc"] < R]
        if tq.empty:
            return 0.0, 0, None
        last = tq[tq["gid"] == tq.iloc[-1]["gid"]]
        starter = last.loc[last["n"].idxmax(), "qb"]
        rep = self.inj.get((season, week, team))
        out_ids = set()
        if rep is not None:
            rep = rep[rep["available_at"] < P].drop_duplicates("gsis_id", keep="last")
            out_ids = set(rep.loc[rep["report_status"].isin(h.OUT_STATUSES), "gsis_id"])
        if len(self.ina):
            out_ids |= set(self.ina.loc[(self.ina["team"] == team) & (self.ina["observed_at"] < P), "gsis_id"])
        expected, change = starter, 0
        if starter in out_ids:
            change, expected = 1, None
            for pool in (tq[tq["season"] == season], tq[tq["season"] == season - 1]):
                alt = pool[~pool["qb"].isin(out_ids)].groupby("qb")["n"].sum()
                if len(alt):
                    expected = alt.idxmax()
                    break
        window = tq[tq["season"] == season]
        if window.empty:
            window = tq[tq["season"] == season - 1]
        w = window.groupby("qb")["n"].sum()
        wv = float((w * values.reindex(w.index).fillna(self.pm)).sum() / w.sum()) if w.sum() else self.pm
        ev_ = float(values.get(expected, self.pm)) if expected is not None else self.pm
        return ev_ - wv, change, expected

    def row(self, g, P) -> dict:
        R = P - RESULT_LAG
        rat, vals = self.ratings(g.season, R), self.values(R)
        out = {"gid": g.gid}
        for name in h.RATINGS:
            oh, dh = rat[name].get(g.home, (0.0, 0.0))
            oa, da = rat[name].get(g.away, (0.0, 0.0))
            out[f"{name}_edge"] = (oh + da) - (oa + dh)
        for side, team in (("home", g.home), ("away", g.away)):
            d, c, e = self.qb_state(team, g.season, g.week, R, P, vals)
            out[f"qb_delta_{side}"], out[f"qb_change_{side}"], out[f"qb_expected_{side}"] = d, c, e
            out[f"rest_{side}"] = self.rest.get((g.gid, team), h.v1.REST_CAP)
        out["qb_delta_diff"] = out["qb_delta_home"] - out["qb_delta_away"]
        out["rest_diff"] = out["rest_home"] - out["rest_away"]
        out["homefield"] = 1 - int(g.neutral)
        eh, ea = self.elo(g.home, g.season, R), self.elo(g.away, g.season, R)
        out["elo_diff"] = eh - ea
        out["elo_prob_home"] = 1 / (1 + 10 ** (-(eh + (0 if g.neutral else h.v1.ELO_HFA) - ea) / 400))
        out["week"] = g.week
        return out


def point_features(data: h.Data, prior_mean: float, first_season: int = 2003, progress=print,
                   points=POINTS, games: pd.DataFrame | None = None) -> dict:
    pb = PointBuilder(data, prior_mean)
    games = data.games[data.games["season"] >= first_season] if games is None else games
    pts = decision_points(games).set_index("gid")
    meta = data.games[["gid", "season", "kickoff_utc", "played", "tie", "margin", "y_home_win"]]
    out = {}
    for p in points:
        rows = [pb.row(g, pts.at[g.gid, p]) for g in games.itertuples(index=False)]
        f = pd.DataFrame(rows).merge(meta, on="gid")
        f["point_utc"] = f["gid"].map(pts[p])
        out[p] = f
        progress(f"  point features {p}: {len(f)} games")
    return out


def leakage_check_points(data: h.Data, prior_mean: float, sample=((2018, 9), (2024, 12), (2026, 6))) -> dict:
    """At each point, corrupt results kicking off at/after P-4h and injuries/quotes at/after P: features must not move."""
    res = {}
    for season, week in sample:
        g = data.games[(data.games["season"] == season) & (data.games["week"] == week)]
        pts = decision_points(g).set_index("gid")
        for p in POINTS:
            first = pts[p].min()
            bad = h.perturb_after(data, first, season, week, result_cutoff=first - RESULT_LAG)
            a = point_features(data, prior_mean, points=[p], games=g, progress=lambda m: None)[p]
            b = point_features(bad, prior_mean, points=[p], games=g, progress=lambda m: None)[p]
            num = [c for c in a.select_dtypes("number").columns if c not in ("margin", "y_home_win")]
            # only the earliest game of the week is guaranteed to be fully pre-cutoff under one perturbation
            gid0 = pts[p].idxmin()
            same = np.allclose(a.loc[a.gid == gid0, num].to_numpy(float), b.loc[b.gid == gid0, num].to_numpy(float), equal_nan=True)
            if not same:
                raise h.DataCheckError(f"LEAKAGE at point {p}, {season} w{week}")
            res[f"{season}_w{week}_{p}"] = True
    # negative control: a point 8 days late lets the corruption through
    season, week = sample[-1]
    g = data.games[(data.games["season"] == season) & (data.games["week"] == week)]
    first = decision_points(g)["t90"].min()
    bad = h.perturb_after(data, first, season, week, result_cutoff=first - RESULT_LAG)
    pb_a, pb_b = PointBuilder(data, prior_mean), PointBuilder(bad, prior_mean)
    late = first + pd.Timedelta(days=8)
    r0 = g.sort_values("kickoff_utc").iloc[0]
    ra, rb = pb_a.row(r0, late), pb_b.row(r0, late)
    if all(np.isclose(ra[k], rb[k]) for k in ra if isinstance(ra[k], float)):
        raise h.DataCheckError("point leakage negative control not detected")
    res["negative_control_detected"] = True
    return res


def walk_forward_points(feats: dict, progress=print, params: dict | None = None) -> tuple[dict, dict]:
    """Per point: for each week from 2012, train on games finished before the week's earliest point; predict that week."""
    params = dict(params or {})
    out = {}
    for p in ["t90"] + [x for x in POINTS if x != "t90"]:  # t90 first: it supplies the per-season tuning
        f = feats[p]
        usable = f[f["played"]]
        cls = usable[~usable["tie"]].assign(y_home_win=lambda d: d["y_home_win"].astype(int))
        weeks = cls.loc[cls["season"] >= h.EVAL_START, ["season", "week"]].drop_duplicates().sort_values(["season", "week"])
        rows = []
        for s, w in weeks.itertuples(index=False):
            test = cls[(cls["season"] == s) & (cls["week"] == w)]
            R = test["point_utc"].min() - RESULT_LAG
            tr_m = usable[(usable["season"] >= h.MARGIN_TRAIN_START) & (usable["kickoff_utc"] < R)]
            tr_c = cls[(cls["season"] >= h.MARGIN_TRAIN_START) & (cls["kickoff_utc"] < R)]
            hist = pd.DataFrame(rows)
            hist = hist[hist["kickoff_utc"] < R] if len(hist) else hist
            resid = (hist["margin"] - hist["pred_margin"]).to_numpy() if len(hist) else np.array([])
            pred, pm_, sigma = h.margin_predict(tr_m, test, resid)
            if s not in params:
                params[s] = h.tune_deep(tr_c, s)
                progress(f"  {s}: tuned xgb_deep on {p}")
            pdp = h.deep_predict(tr_c, test, params[s])
            blk = test[["gid", "season", "week", "kickoff_utc", "point_utc", "margin", "y_home_win",
                        "qb_change_home", "qb_change_away"]].copy()
            blk["pred_margin"], blk["sigma"] = pred, sigma
            blk["p_elo"], blk["p_margin"], blk["p_xgb_deep"] = test["elo_prob_home"].to_numpy(), pm_, pdp
            for m in ("elo", "margin", "xgb_deep"):
                ph = hist[f"p_{m}"].to_numpy() if len(hist) else np.array([])
                yh = hist["y_home_win"].to_numpy() if len(hist) else np.array([])
                blk[f"p_{m}_platt"] = h.platt(ph, yh, blk[f"p_{m}"].to_numpy())
            rows.extend(blk.to_dict("records"))
        out[p] = pd.DataFrame(rows)
        progress(f"  walk-forward {p}: {len(rows)} games")
    return out, params


def gate(preds: pd.DataFrame) -> dict:
    alpha = 0.05 / 4
    res = {}
    for m in ("margin", "margin_platt", "xgb_deep", "xgb_deep_platt"):
        c = ev.compare(preds, f"p_{m}", "p_elo", alpha)
        c["pass"] = bool(c["ll_ci"][1] < 0 and c["dm"]["p"] < alpha and c["brier_delta"] <= 0 and c["seasons_better"] >= 9)
        res[m] = c
    return {"family_alpha": alpha, "results": res}


# --------------------------------------------------------------------------- 3. stacking, 4. CLV

def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def stack(df: pd.DataFrame, cols: list[str], alpha: float, n_boot: int = ev.N_BOOT) -> dict:
    from sklearn.linear_model import LogisticRegression
    X, y = np.column_stack([_logit(df[c]) for c in cols]), df["y_home_win"].to_numpy(int)
    fit = lambda X_, y_: LogisticRegression(C=1e6, max_iter=1000).fit(X_, y_)  # noqa: E731
    m = fit(X, y)
    wk = (df["season"].astype(str) + "_" + df["week"].astype(str)).to_numpy()
    codes, inv = np.unique(wk, return_inverse=True)
    idx = [np.flatnonzero(inv == i) for i in range(len(codes))]
    rng = np.random.default_rng(ev.SEED)
    draws = []
    for _ in range(n_boot):
        rows = np.concatenate([idx[i] for i in rng.integers(0, len(codes), len(codes))])
        draws.append(fit(X[rows], y[rows]).coef_[0])
    draws = np.array(draws)
    lo, hi = np.quantile(draws, alpha / 2, axis=0), np.quantile(draws, 1 - alpha / 2, axis=0)
    return {"n": int(len(df)), "inputs": cols, "intercept": float(m.intercept_[0]), "ci_level": 1 - alpha,
            "weights": {c: {"w": float(w), "ci": [float(a), float(b)]} for c, w, a, b in zip(cols, m.coef_[0], lo, hi)}}


def stack_walk_forward_ll(df: pd.DataFrame, cols: list[str]) -> float:
    from sklearn.linear_model import LogisticRegression
    df = df.sort_values("kickoff_utc")
    out = []
    for (s, w), t in df.groupby(["season", "week"], sort=False):
        tr = df[df["kickoff_utc"] < t["point_utc"].min() - RESULT_LAG]
        if len(tr) < 256:
            continue
        m = LogisticRegression(C=1e6, max_iter=1000).fit(np.column_stack([_logit(tr[c]) for c in cols]), tr["y_home_win"])
        p = m.predict_proba(np.column_stack([_logit(t[c]) for c in cols]))[:, 1]
        out.append(ev._ll(t["y_home_win"].to_numpy(float), p))
    return float(np.concatenate(out).mean())


def market_at_points(data: h.Data, games: pd.DataFrame) -> pd.DataFrame:
    pts = decision_points(games).set_index("gid")
    rows = []
    for g in games.itertuples(index=False):
        r = {"gid": g.gid}
        for p in POINTS:
            r[f"mkt_{p}"] = h.market_probability(data.quotes, g.home, g.away, g.kickoff_utc, pts.at[g.gid, p])["p_home"]
        rows.append(r)
    return pd.DataFrame(rows)


def clv(preds_by_point: dict, mkt: pd.DataFrame) -> dict:
    res = {}
    for p in CLV_POINTS:
        d = preds_by_point[p].merge(mkt, on="gid")
        d = d[d[f"mkt_{p}"].notna() & d["mkt_close"].notna()]
        move = (d["mkt_close"] - d[f"mkt_{p}"]).to_numpy()
        for m in ("elo", "margin", "xgb_deep"):
            side = np.sign(d[f"p_{m}"].to_numpy() - d[f"mkt_{p}"].to_numpy())
            c = move * side
            cl = (d["season"].astype(str) + "_" + d["week"].astype(str)).to_numpy()
            nz = c[c != 0]
            res[f"{p}/{m}"] = {"games": int(len(c)), "mean_clv": float(c.mean()) if len(c) else None,
                               "ci95": ev.cluster_boot(c, cl, 0.05) if len(c) else None,
                               "positive": int((nz > 0).sum()), "negative": int((nz < 0).sum()),
                               "sign_test_p_one_sided": float(binomtest(int((nz > 0).sum()), len(nz), alternative="greater").pvalue) if len(nz) else None}
    prim = res[f"{PRIMARY_CLV_POINT}/xgb_deep"]
    prim["pass"] = bool(prim["ci95"] and prim["ci95"][0] > 0 and prim["sign_test_p_one_sided"] < 0.05)
    return {"primary": f"{PRIMARY_CLV_POINT}/xgb_deep", "results": res}
