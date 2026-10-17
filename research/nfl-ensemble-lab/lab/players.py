"""Phase 5 player-level football intelligence.

Data: nflverse pbp (EPA, situation) joined to pbp_participation on-field player IDs
(2016-2025, ~92% of plays with full 11v11 lists), PFR snap counts (2012-2026) for
expected roles, verified pregame injury reports, FTN charting (2022-2026).

Player model: regularised adjusted plus-minus (RAPM) on per-play EPA
    EPA = situation covariates + sum(position-group effects) + sum(offensive player effects)
          + sum(defensive player effects)
  Individual effects get a strong ridge penalty and position-group effects a weak one, so a
  player with few snaps is shrunk toward his position group (hierarchical shrinkage). The model
  is refit for every (season, week) using ONLY plays from games that kicked off before that
  week's first kickoff (current season weight 1, previous 0.6, two seasons back 0.35).
  Effects are statistical associations conditional on teammates/opponents/situation, not
  causal player values; teammates who always play together cannot be separated (ridge splits
  credit), which is why features aggregate to units and lineups.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import cg

from .config import CACHE_DIR, RAW_DIR

PLAYS_CACHE = CACHE_DIR / "player_plays.parquet"
RATINGS_CACHE = CACHE_DIR / "player_ratings.parquet"
META_CACHE = CACHE_DIR / "player_model.json"
SEASON_WEIGHTS = {0: 1.0, 1: 0.6, 2: 0.35}
LAMBDA_GROUP, LAMBDA_COV = 20.0, 1.0
LAMBDA_GRID = (300.0, 1000.0, 3000.0, 10000.0, 30000.0, 100000.0)
LOW_EXPOSURE = 300          # plays; below this a player counts as low-information
GROUPS = {"QB": ("QB",), "RB": ("RB", "FB", "HB"), "WR": ("WR",), "TE": ("TE",), "OL": ("T", "G", "C", "OT", "OG", "OL", "LT", "RT", "LG", "RG"),
          "DL": ("DE", "DT", "NT", "DL", "EDGE"), "LB": ("LB", "ILB", "OLB", "MLB"), "DB": ("CB", "S", "SS", "FS", "DB", "SAF")}
POS2G = {p: g for g, ps in GROUPS.items() for p in ps}
GLIST = list(GROUPS) + ["OTH"]


# --------------------------------------------------------------------------- plays with players

def build_plays(games: pd.DataFrame, seasons: list[int], progress=print) -> pd.DataFrame:
    idm = dict(zip(games["source_game_id"], games["game_id"]))
    kick = games.set_index("game_id")["kickoff_utc"]
    home = games.set_index("game_id")["home_team"]
    parts = []
    for s in seasons:
        pp, pb = RAW_DIR / f"participation_{s}.parquet", RAW_DIR / f"play_by_play_{s}.parquet"
        if not (pp.exists() and pb.exists()):
            continue
        pbp = pd.read_parquet(pb, columns=["game_id", "play_id", "posteam", "defteam", "epa", "down", "ydstogo", "yardline_100",
                                           "score_differential", "qtr", "play_type", "two_point_attempt"])
        pbp = pbp[pbp["play_type"].isin(["pass", "run"]) & pbp["epa"].notna() & (pbp["two_point_attempt"].fillna(0) == 0)]
        part = pd.read_parquet(pp, columns=["nflverse_game_id", "play_id", "offense_players", "defense_players"])
        m = pbp.merge(part, left_on=["game_id", "play_id"], right_on=["nflverse_game_id", "play_id"], how="inner")
        m = m[(m["offense_players"].fillna("").str.count(";") == 10) & (m["defense_players"].fillna("").str.count(";") == 10)]
        m["game_id"] = m["game_id"].map(lambda g: idm.get(g, g))
        m = m[m["game_id"].isin(kick.index)]
        m["season"] = int(s)
        parts.append(m.drop(columns=["nflverse_game_id", "two_point_attempt", "play_type"]))
        progress(f"  player plays {s}: {len(m)}")
    plays = pd.concat(parts, ignore_index=True)
    plays["kickoff_utc"] = plays["game_id"].map(kick)
    plays["home_off"] = (plays["posteam"].map(lambda t: t) == plays["game_id"].map(home)).astype(float)
    from .ingest import normalize_team
    plays["posteam"] = plays["posteam"].map(normalize_team)
    plays["defteam"] = plays["defteam"].map(normalize_team)
    return plays.sort_values(["kickoff_utc", "game_id", "play_id"]).reset_index(drop=True)


def _positions() -> dict:
    if not (RAW_DIR / "players.parquet").exists():
        return {}
    p = pd.read_parquet(RAW_DIR / "players.parquet", columns=["gsis_id", "position"]).dropna()
    return {g: POS2G.get(pos, "OTH") for g, pos in zip(p["gsis_id"], p["position"])}


def design(plays: pd.DataFrame, pid: dict, pos: dict) -> tuple[sp.csr_matrix, np.ndarray, list[str]]:
    """Sparse design matrix: [off players | def players | off groups | def groups | covariates]."""
    n, P, G = len(plays), len(pid), len(GLIST)
    gidx = {g: i for i, g in enumerate(GLIST)}
    rows, cols = [], []
    gcounts_o = np.zeros((n, G))
    gcounts_d = np.zeros((n, G))
    for i, (o, d) in enumerate(zip(plays["offense_players"], plays["defense_players"])):
        for x in o.split(";"):
            rows.append(i)
            cols.append(pid[x])
            gcounts_o[i, gidx[pos.get(x, "OTH")]] += 1
        for x in d.split(";"):
            rows.append(i)
            cols.append(P + pid[x])
            gcounts_d[i, gidx[pos.get(x, "OTH")]] += 1
    Xp = sp.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, 2 * P))
    cov = [np.ones(n), plays["home_off"].to_numpy(float)]
    names = ["intercept", "home_off"]
    down = plays["down"].fillna(1).astype(int).clip(1, 4)
    for k in (2, 3, 4):
        cov.append((down == k).astype(float).to_numpy())
        names.append(f"down{k}")
    ytg = plays["ydstogo"].fillna(10).to_numpy(float)
    yl = plays["yardline_100"].fillna(50).to_numpy(float)
    sd = plays["score_differential"].fillna(0).to_numpy(float)
    for lo, hi, nm in ((0, 3, "ytg_short"), (3, 7, "ytg_mid"), (11, 99, "ytg_long")):
        cov.append(((ytg > lo) & (ytg <= hi)).astype(float) if nm != "ytg_long" else (ytg >= lo).astype(float))
        names.append(nm)
    for lo, hi in ((0, 10), (10, 20), (20, 40), (60, 80), (80, 100)):
        cov.append(((yl > lo) & (yl <= hi)).astype(float))
        names.append(f"yl_{lo}_{hi}")
    for lo, hi in ((-99, -14), (-14, -7), (7, 14), (14, 99)):
        cov.append(((sd > lo) & (sd <= hi)).astype(float))
        names.append(f"sd_{lo}_{hi}")
    q = plays["qtr"].fillna(1).to_numpy(float)
    cov.append((q == 4).astype(float))
    names.append("q4")
    C = sp.csr_matrix(np.column_stack([gcounts_o, gcounts_d] + cov))
    return sp.hstack([Xp, C]).tocsr(), np.clip(plays["epa"].to_numpy(float), -4, 4), names


class RAPM:
    """Incremental weighted ridge: sufficient statistics accumulated per week block."""

    def __init__(self, plays: pd.DataFrame, lam_ind: float, progress=print):
        self.pos = _positions()
        ids = sorted(set(";".join(plays["offense_players"]).split(";")) | set(";".join(plays["defense_players"]).split(";")))
        self.pid = {x: i for i, x in enumerate(ids)}
        self.ids = ids
        self.P = len(ids)
        self.X, self.y, self.cov_names = design(plays, self.pid, self.pos)
        self.K = self.X.shape[1]
        self.plays = plays
        pen = np.full(self.K, LAMBDA_COV)
        pen[: 2 * self.P] = lam_ind
        pen[2 * self.P: 2 * self.P + 2 * len(GLIST)] = LAMBDA_GROUP
        self.pen = pen
        self.lam = lam_ind
        # per-player cumulative exposure counts (plays) by kickoff order
        self.off_counts = self.X[:, : self.P]
        self.def_counts = self.X[:, self.P: 2 * self.P]

    def _block(self, mask):
        Xb = self.X[mask]
        return (Xb.T @ Xb).tocsr(), Xb.T @ self.y[mask]

    def fit_schedule(self, cutoffs: pd.DataFrame, progress=print) -> dict:
        """cutoffs: rows (season, week, cutoff_utc) sorted. Returns {(season, week): result}."""
        out = {}
        season_tot = {}
        kick = self.plays["kickoff_utc"].to_numpy()
        pseason = self.plays["season"].to_numpy()
        beta = np.zeros(self.K)
        for season, grp in cutoffs.groupby("season", sort=True):
            for lag in (1, 2):
                s = season - lag
                if s not in season_tot and (pseason == s).any():
                    season_tot[s] = self._block(pseason == s)
            A_part = sp.csr_matrix((self.K, self.K))
            b_part = np.zeros(self.K)
            done_until = None
            for r in grp.sort_values("cutoff_utc").itertuples(index=False):
                lo = done_until if done_until is not None else pd.Timestamp.min.tz_localize("UTC")
                new = (pseason == season) & (kick >= lo) & (kick < r.cutoff_utc)
                if new.any():
                    A_b, b_b = self._block(new)
                    A_part = A_part + A_b
                    b_part = b_part + b_b
                done_until = r.cutoff_utc
                A = A_part.copy()
                b = b_part.copy()
                for lag in (1, 2):
                    if season - lag in season_tot:
                        A = A + SEASON_WEIGHTS[lag] * season_tot[season - lag][0]
                        b = b + SEASON_WEIGHTS[lag] * season_tot[season - lag][1]
                if b.any():
                    A = A + sp.diags(self.pen)
                    M = sp.diags(1.0 / A.diagonal())
                    beta, _ = cg(A, b, x0=beta, M=M, maxiter=300, rtol=1e-6)
                    hist = (kick < r.cutoff_utc) & (pseason >= season - 2)
                    out[(int(season), int(r.week))] = self._summarize(beta, hist, r.cutoff_utc)
            progress(f"  RAPM fits for {season}: {len(grp)} weeks")
        return out

    def _summarize(self, beta, hist_mask, cutoff) -> dict:
        P = self.P
        exp_off = np.asarray(self.off_counts[hist_mask].sum(axis=0)).ravel()
        exp_def = np.asarray(self.def_counts[hist_mask].sum(axis=0)).ravel()
        off, deff = beta[:P], beta[P: 2 * P]
        G = len(GLIST)
        gro = beta[2 * P: 2 * P + G]
        grd = beta[2 * P + G: 2 * P + 2 * G]
        # data-driven replacement level per group: mean effect of low-exposure players
        repl = {}
        for g in GLIST:
            m_off = np.array([self.pos.get(x, "OTH") == g for x in self.ids]) if g not in getattr(self, "_gm", {}) else self._gm[g]
            self.__dict__.setdefault("_gm", {})[g] = m_off
            lo_o = m_off & (exp_off > 0) & (exp_off < LOW_EXPOSURE)
            lo_d = m_off & (exp_def > 0) & (exp_def < LOW_EXPOSURE)
            repl[g] = (float(off[lo_o].mean()) if lo_o.any() else 0.0, float(deff[lo_d].mean()) if lo_d.any() else 0.0)
        return {"off": off.copy(), "def": deff.copy(), "exp_off": exp_off, "exp_def": exp_def,
                "group_off": dict(zip(GLIST, gro)), "group_def": dict(zip(GLIST, grd)), "replacement": repl,
                "cutoff": cutoff}


def choose_lambda(plays: pd.DataFrame, progress=print) -> tuple[float, dict]:
    """Pick the individual-effect penalty by predicting 2018 plays from a fit on 2016-2017
    plays only (all before every evaluation season)."""
    tr = plays[plays["season"].isin([2016, 2017])]
    te = plays[plays["season"] == 2018]
    if tr.empty or te.empty:
        return 1000.0, {}
    scores = {}
    for lam in LAMBDA_GRID:
        r = RAPM(pd.concat([tr, te]), lam, progress)
        trm = (r.plays["season"] < 2018).to_numpy()
        A, b = r._block(trm)
        beta, _ = cg(A + sp.diags(r.pen), b, maxiter=400, rtol=1e-6)
        Xte = r.X[~trm]
        pred = Xte @ beta
        scores[lam] = float(np.mean((r.y[~trm] - pred) ** 2))
    best = min(scores, key=scores.get)
    progress(f"  RAPM penalty chosen on 2016-17 -> 2018 plays: {best} (MSE by lambda {scores})")
    return best, scores


# --------------------------------------------------------------------------- team-level player features

UNITS = {"QB": ("QB",), "OL": ("OL",), "SKILL": ("RB", "WR", "TE"), "DL": ("DL",), "LB": ("LB",), "DB": ("DB",)}


def snap_shares(games: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    """Per completed team-game: each player's offensive/defensive snap share (gsis ids)."""
    parts = []
    for s in seasons:
        p = RAW_DIR / f"snap_counts_{s}.parquet"
        if p.exists():
            parts.append(pd.read_parquet(p, columns=["game_id", "pfr_player_id", "team", "offense_pct", "defense_pct"]))
    sn = pd.concat(parts, ignore_index=True)
    pl = pd.read_parquet(RAW_DIR / "players.parquet", columns=["gsis_id", "pfr_id"]).dropna().drop_duplicates("pfr_id")
    sn = sn.merge(pl, left_on="pfr_player_id", right_on="pfr_id", how="inner")
    idm = dict(zip(games["source_game_id"], games["game_id"]))
    sn["game_id"] = sn["game_id"].map(lambda g: idm.get(g, g))
    from .availability import _team
    sn["team"] = sn["team"].map(_team)
    sn = sn.merge(games[["game_id", "kickoff_utc"]], on="game_id", how="inner").dropna(subset=["team"])
    return sn[["game_id", "team", "kickoff_utc", "gsis_id", "offense_pct", "defense_pct"]]


def _team_play_matrices(plays: pd.DataFrame) -> dict:
    out = {}
    pseason = plays["season"].to_numpy()
    kick = plays["kickoff_utc"].dt.tz_convert(None).to_numpy()
    for side, team_col, ids_col in (("off", "posteam", "offense_players"), ("def", "defteam", "defense_players")):
        for team, idx in plays.groupby(team_col).indices.items():
            idx = np.sort(idx)
            lists = [x.split(";") for x in plays[ids_col].to_numpy()[idx]]
            cols = {x: i for i, x in enumerate(sorted({p for l in lists for p in l}))}
            M = np.zeros((len(idx), len(cols)), dtype=bool)
            for r, l in enumerate(lists):
                M[r, [cols[p] for p in l]] = True
            out[(team, side)] = (kick[idx], pseason[idx], cols, M)
    return out


def _coplay_counts(team_plays: dict, team: str, side: str, t_cut, season: int, players: list) -> list:
    """For each list of player ids: number of the team's EARLIER plays (this and the two prior
    seasons) on which all of them were on the field together."""
    tp = team_plays.get((team, side))
    if tp is None:
        return [np.nan] * len(players)
    kick, seas, cols, M = tp
    hi = np.searchsorted(kick, np.datetime64(t_cut.tz_convert(None)), side="left")
    lo = np.searchsorted(seas[:hi], season - 2, side="left")
    out = []
    for ids in players:
        idx = [cols.get(x) for x in ids]
        if not ids or any(i is None for i in idx):
            out.append(0.0)
            continue
        out.append(float(M[lo:hi][:, idx].all(axis=1).sum()))
    return out


def build_team_player_features(games: pd.DataFrame, valid_inj: pd.DataFrame, inj_team: pd.DataFrame, seasons: list,
                               progress=print, plays_transform=None) -> pd.DataFrame:
    """One row per (game_id, team) with p5_* features, all from information before kickoff:
    expected lineup = snap shares over the team's last 4 completed games; injuries applied only
    from verified pregame reports; player values from the RAPM fit for that week."""
    plays = build_plays(games, [s for s in seasons if s >= 2016], progress=lambda m: None)
    if plays_transform is not None:
        plays = plays_transform(plays)
    plays.to_parquet(PLAYS_CACHE, index=False)
    cut = games[games["season"] >= 2016].groupby(["season", "week"])["kickoff_utc"].min().reset_index(name="cutoff_utc")
    import hashlib

    import joblib
    sig = hashlib.sha256(f"{len(plays)}|{plays['epa'].sum():.8f}|{plays['kickoff_utc'].max()}|"
                         f"{pd.util.hash_pandas_object(cut, index=False).sum()}".encode()).hexdigest()[:20]
    fit_cache = CACHE_DIR / "rapm_fits.joblib"
    cached = joblib.load(fit_cache) if fit_cache.exists() and plays_transform is None else None
    if cached and cached.get("sig") == sig:
        lam, lam_scores, fits = cached["lam"], cached["lam_scores"], cached["fits"]
        model = type("M", (), {"pos": cached["pos"], "pid": cached["pid"], "P": cached["P"]})()
        progress("  player model unchanged (no new plays): using cached weekly fits")
    else:
        lam, lam_scores = choose_lambda(plays, progress)
        model = RAPM(plays, lam, progress)
        fits = model.fit_schedule(cut, progress)
        if plays_transform is None:
            joblib.dump({"sig": sig, "lam": lam, "lam_scores": lam_scores, "fits": fits, "pos": model.pos, "pid": model.pid,
                         "P": model.P}, fit_cache)
    last_play = plays["kickoff_utc"].max()
    shares = snap_shares(games, seasons)
    by_team = {t: d.sort_values("kickoff_utc") for t, d in shares.groupby("team")}
    vi = valid_inj if len(valid_inj) else pd.DataFrame(columns=["game_id", "team", "gsis_id", "report_status"])
    out_status = {(g, t, p): s for g, t, p, s in zip(vi["game_id"], vi["team"], vi["gsis_id"], vi["report_status"])}
    inj_avail = {(g, t): a for g, t, a in zip(inj_team["game_id"], inj_team["team"], inj_team["inj_report_available"])}
    tpm = _team_play_matrices(plays)
    pos, pid = model.pos, model.pid
    rows = []
    for g in games[games["season"] >= 2016].itertuples(index=False):
        fit = fits.get((g.season, g.week))
        for team in (g.home_team, g.away_team):
            r = {"game_id": g.game_id, "team": team}
            d = by_team.get(team)
            if fit is None or d is None:
                rows.append(r)
                continue
            prior = d[d["kickoff_utc"] < g.kickoff_utc]
            last_games = prior["game_id"].drop_duplicates().iloc[-4:]
            recent = prior[prior["game_id"].isin(last_games)]
            if recent.empty:
                rows.append(r)
                continue
            sh = recent.groupby("gsis_id")[["offense_pct", "defense_pct"]].sum() / max(len(last_games), 1)
            known = inj_avail.get((g.game_id, team), 0) == 1
            out_ids = {p for p in sh.index if out_status.get((g.game_id, team, p)) in ("Out", "Doubtful")} if known else set()
            res = {}
            for side, col, coef_key, exp_key, ridx in (("off", "offense_pct", "off", "exp_off", 0), ("def", "defense_pct", "def", "exp_def", 1)):
                s = sh[col][sh[col] > 0]
                if s.empty:
                    continue
                vals, grps, expo = [], [], []
                for p in s.index:
                    gp = pos.get(p, "OTH")
                    i = pid.get(p)
                    if i is None or fit[exp_key][i] == 0:
                        v, e = fit["replacement"].get(gp, (0.0, 0.0))[ridx], 0.0
                    else:
                        v, e = fit[coef_key][i], fit[exp_key][i]
                    vals.append(v)
                    grps.append(gp)
                    expo.append(e)
                s_arr, v_arr, e_arr = s.to_numpy(), np.array(vals), np.array(expo)
                proj_v = v_arr.copy()
                for j, p in enumerate(s.index):
                    if p in out_ids:
                        gp = grps[j]
                        bench = [(s_arr[k], v_arr[k]) for k in range(len(s_arr))
                                 if grps[k] == gp and s_arr[k] < 0.5 and s.index[k] not in out_ids]
                        proj_v[j] = (np.average([b[1] for b in bench], weights=[b[0] for b in bench]) if bench
                                     else fit["replacement"].get(gp, (0.0, 0.0))[ridx])
                res[f"{side}_full"] = float(np.sum(s_arr * v_arr))
                res[f"{side}_proj"] = float(np.sum(s_arr * proj_v))
                res[f"{side}_loss"] = res[f"{side}_full"] - res[f"{side}_proj"]
                res[f"{side}_info"] = float(np.average(np.log1p(e_arr), weights=s_arr))
                res[f"{side}_lowexp"] = float(np.sum(s_arr * (e_arr < LOW_EXPOSURE)) / s_arr.sum())
                for u, gs in UNITS.items():
                    if (side == "off") == (u in ("QB", "OL", "SKILL")):
                        m = np.array([gp in gs for gp in grps])
                        res[f"unit_{u}"] = float(np.sum(s_arr[m] * proj_v[m])) if m.any() else np.nan
                ranked = list(s.sort_values(ascending=False).index)
                if side == "off":
                    def top(gset, k):
                        return [p for p in ranked if pos.get(p, "OTH") in gset and p not in out_ids][:k]
                    ol5, qb, rec = top({"OL"}, 5), top({"QB"}, 1), top({"WR", "TE"}, 3)
                    c = _coplay_counts(tpm, team, "off", g.kickoff_utc, g.season, [ol5] + [qb + [x] for x in rec])
                    res["ol_unit_coplays"] = float(np.log1p(c[0])) if len(ol5) == 5 else np.nan
                    res["qb_wr_coplays"] = float(np.log1p(np.mean(c[1:]))) if qb and rec else np.nan
                else:
                    core = [p for p in ranked if p not in out_ids][:7]
                    pairs = [[a, b] for i_, a in enumerate(core) for b in core[i_ + 1:]]
                    c = _coplay_counts(tpm, team, "def", g.kickoff_utc, g.season, pairs)
                    res["def_core_coplays"] = float(np.log1p(np.mean(c))) if pairs else np.nan
            res["inj_applied"] = int(known)
            res["n_out_removed"] = len(out_ids)
            res["model_staleness_days"] = float(max((g.kickoff_utc - last_play).days, 0))
            rows.append(r | {f"p5_{k}": v for k, v in res.items()})
    META_CACHE.write_text(json.dumps({"lambda": lam, "lambda_scores": {str(k): v for k, v in lam_scores.items()},
                                      "plays": int(len(plays)), "players": model.P, "fits": len(fits),
                                      "last_play_kickoff": str(last_play)}, indent=2))
    df = pd.DataFrame(rows)
    ftn = ftn_team_features(games, seasons)
    return df.merge(ftn, on=["game_id", "team"], how="left") if len(ftn) else df


def ftn_team_features(games: pd.DataFrame, seasons: list) -> pd.DataFrame:
    """FTN charting team tendencies (2022+), aggregated per team-game, windowed strictly pregame."""
    from .advanced import _id_map, _opp_map, _with_defense, window_features
    from .ingest import normalize_team
    idm = _id_map(games)
    parts = []
    for s in seasons:
        f, pb = RAW_DIR / f"ftn_{s}.parquet", RAW_DIR / f"play_by_play_{s}.parquet"
        if not (f.exists() and pb.exists()):
            continue
        d = pd.read_parquet(f)
        p = pd.read_parquet(pb, columns=["game_id", "play_id", "posteam"])
        d = d.merge(p, left_on=["nflverse_game_id", "nflverse_play_id"], right_on=["game_id", "play_id"], how="inner")
        d["game_id"] = d["game_id"].map(idm)
        d["team"] = d["posteam"].map(lambda t: normalize_team(t) if isinstance(t, str) else None)
        d = d.dropna(subset=["game_id", "team"])

        def num(c):
            return pd.to_numeric(d[c], errors="coerce").astype(float)
        d = d.assign(motion=num("is_motion"), play_action=num("is_play_action"), screen=num("is_screen_pass"), rpo=num("is_rpo"),
                     no_huddle=num("is_no_huddle"), out_of_pocket=num("is_qb_out_of_pocket"),
                     blitz_faced=(num("n_blitzers") > 0).astype(float), box_faced=num("n_defense_box"))
        parts.append(d.groupby(["game_id", "team"])[["motion", "play_action", "screen", "rpo", "no_huddle", "out_of_pocket",
                                                      "blitz_faced", "box_faced"]].mean().reset_index())
    if not parts:
        return pd.DataFrame(columns=["game_id", "team"])
    tg = _with_defense(pd.concat(parts, ignore_index=True), _opp_map(games[games["completed"]]),
                       {"blitz_faced": "blitz_rate", "motion": "motion_faced", "play_action": "play_action_faced"})
    return window_features(games, tg, "p5ftn_")


FTN_URL = "https://github.com/nflverse/nflverse-data/releases/download/ftn_charting/ftn_charting_{s}.parquet"


def refresh_ftn(seasons: list, live: int, progress=print) -> list:
    from . import sources
    errors = []
    for s in seasons:
        if s < 2022:
            continue
        try:
            sources.download(f"nflverse_ftn_{s}", FTN_URL.format(s=s), RAW_DIR / f"ftn_{s}.parquet",
                             max_age_hours=sources.LIVE_MAX_AGE_HOURS if s == live else None,
                             validate=sources._validate_parquet, progress=progress)
        except FileNotFoundError:
            pass
        except Exception as exc:
            errors.append(f"ftn {s}: {exc}")
    return errors
