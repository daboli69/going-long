"""Drive-level game simulator. Frozen protocol: docs/HOMEWIN_SIM_PREREGISTRATION.md (commit 067e5583)."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
from scipy.stats import chisquare, kstest, norm

from . import homewin_deep as h
from . import homewin_eval as ev
from .config import LAB_ROOT, RAW_DIR

PREREG_COMMIT = "067e5583"
CACHE = h.CACHE / "sim"
REPORT_DIR = LAB_ROOT / "reports" / "homewin_sim"
CLASSES = ["TD", "FG", "MISSED_FG", "PUNT", "TURNOVER", "DOWNS", "SAFETY", "OPP_TD", "END_HALF"]
CIX = {c: i for i, c in enumerate(CLASSES)}
OFF_PTS = np.array([7, 3, 0, 0, 0, 0, 0, 0, 0])
DEF_PTS = np.array([0, 0, 0, 0, 0, 0, 2, 7, 0])
KEEP_BALL = CIX["OPP_TD"]
N_SIMS = 10_000
MARGINS = np.arange(-80, 81)
TOTALS = np.arange(0, 121)
NFLVERSE_MAP = {"Touchdown": "TD", "Field goal": "FG", "Missed field goal": "MISSED_FG", "Punt": "PUNT", "Turnover": "TURNOVER",
                "Turnover on downs": "DOWNS", "Safety": "SAFETY", "End of half": "END_HALF", "Opp touchdown": "OPP_TD"}
PBP = ["game_id", "play_id", "season", "week", "season_type", "home_team", "away_team", "posteam", "defteam", "game_half",
       "down", "yardline_100", "half_seconds_remaining", "play_type", "td_team", "field_goal_result", "safety",
       "interception", "fumble_lost", "first_down", "posteam_score", "defteam_score", "fixed_drive_result"]


# --------------------------------------------------------------------------- 1. drives from raw plays

def _norm(s):
    return s.map(lambda x: h.normalize_team(x) if isinstance(x, str) and x else None)


def season_drives(season: int) -> pd.DataFrame:
    p = pd.read_parquet(RAW_DIR / f"play_by_play_{season}.parquet", columns=PBP)
    p = p[p["season_type"] == "REG"].sort_values(["game_id", "play_id"]).reset_index(drop=True)
    for c in ("home_team", "away_team", "posteam", "defteam", "td_team"):
        p[c] = _norm(p[c])
    scored = p["td_team"].notna() | p["field_goal_result"].eq("made") | p["safety"].eq(1)
    # a kickoff, or any score on the previous play, separates drives even when the same team keeps the ball
    p["sep"] = (p["play_type"].eq("kickoff") | scored.shift(fill_value=False)).cumsum()
    d = p[p["down"].between(1, 4) & p["posteam"].notna() & p["yardline_100"].notna() & p["half_seconds_remaining"].notna()].copy()
    new = ((d["game_id"] != d["game_id"].shift()) | (d["game_half"] != d["game_half"].shift())
           | (d["posteam"] != d["posteam"].shift()) | (d["sep"] != d["sep"].shift()))
    d["drive"] = new.cumsum()
    d["opp_td"] = d["td_team"].notna() & (d["td_team"] == d["defteam"])
    d["off_td"] = d["td_team"].notna() & (d["td_team"] == d["posteam"])
    g = d.groupby("drive")
    first, last = g.head(1).set_index("drive"), g.tail(1).set_index("drive")
    dr = pd.DataFrame({
        "game_id": first["game_id"], "season": first["season"], "week": first["week"], "game_half": first["game_half"],
        "home_team": first["home_team"], "away_team": first["away_team"], "off": first["posteam"], "def": first["defteam"],
        "start_yl": first["yardline_100"], "start_sec": first["half_seconds_remaining"],
        "score_diff": first["posteam_score"] - first["defteam_score"], "first_play": first["play_id"],
        "nflverse_result": first["fixed_drive_result"]})
    opp_td, off_td, saf = g["opp_td"].max(), g["off_td"].max(), g["safety"].max().eq(1)
    fg = last["field_goal_result"]
    to = last["interception"].eq(1) | last["fumble_lost"].eq(1)
    downs = last["down"].eq(4) & ~last["first_down"].eq(1) & ~last["play_type"].isin(["punt", "field_goal"])
    key = dr[["game_id", "game_half"]]
    dr["last_in_half"] = ~key.duplicated(keep="last")
    cls = np.select([opp_td, off_td, saf, fg.eq("made"), fg.isin(["missed", "blocked"]), to, last["play_type"].eq("punt"),
                     downs, dr["last_in_half"]],
                    ["OPP_TD", "TD", "SAFETY", "FG", "MISSED_FG", "TURNOVER", "PUNT", "DOWNS", "END_HALF"], "OTHER")
    dr["cls"] = cls
    gh = dr.groupby(["game_id", "game_half"])
    dr["next_sec"] = gh["start_sec"].shift(-1)
    dr["dur"] = (dr["start_sec"] - dr["next_sec"].fillna(0)).clip(lower=0)
    dr["next_yl"] = gh["start_yl"].shift(-1)
    dr["first_in_half"] = ~key.duplicated(keep="first")
    return dr.reset_index(drop=True)


def all_drives(games: pd.DataFrame, first: int = 2002) -> tuple[pd.DataFrame, dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    from . import sources
    man = sources.load_manifest()
    parts = []
    for s in range(first, h.v1.current_season() + 1):
        path = CACHE / f"drives_{s}_{man[f'nflverse_pbp_{s}']['sha256'][:12]}.parquet"
        if not path.exists():
            season_drives(s).to_parquet(path)
        parts.append(pd.read_parquet(path))
    dr = pd.concat(parts, ignore_index=True)
    ids = dict(zip(zip(games["season"], games["week"], games["home"], games["away"]), games["gid"]))
    dr["gid"] = [ids.get(k) for k in zip(dr["season"], dr["week"], dr["home_team"], dr["away_team"])]
    meta = games.set_index("gid")[["kickoff_utc", "neutral"]]
    dr = dr.dropna(subset=["gid"]).join(meta, on="gid")
    dr["off_home"] = (dr["off"] == dr["home_team"]).astype(int)
    chk = dr[dr["nflverse_result"].notna()]
    mapped = chk["nflverse_result"].map(NFLVERSE_MAP)
    agree = mapped == chk["cls"]
    report = {"drives": int(len(dr)), "other_dropped": int((dr["cls"] == "OTHER").sum()),
              "agreement_overall": float(agree.mean()),
              "agreement_by_season": {int(k): float(v) for k, v in agree.groupby(chk["season"]).mean().items()},
              "agreement_by_class": {k: float(v) for k, v in agree.groupby(chk["cls"]).mean().items()},
              "class_share": {k: float(v) for k, v in dr["cls"].value_counts(normalize=True).items()}}
    return dr, report


# --------------------------------------------------------------------------- 2. drive-outcome model



def _situ(yl, sec, sd, off_home, neutral, baseline=False):
    yl = np.asarray(yl, float)
    b = np.minimum((yl // 10).astype(int), 9)
    cols = [np.eye(10)[b], (yl / 100)[:, None], np.asarray(off_home, float)[:, None]]
    if not baseline:
        sec = np.asarray(sec, float)
        tb = np.digitize(sec, [30, 120, 300])
        s = np.clip(np.asarray(sd, float), -21, 21) / 7
        cols += [np.eye(4)[tb], s[:, None], np.abs(s)[:, None], np.asarray(neutral, float)[:, None]]
    return np.hstack(cols)


class DriveModel:
    def __init__(self, teams, baseline=False):
        self.teams, self.baseline = list(teams), baseline
        self.tix = {t: i for i, t in enumerate(self.teams)}

    def X(self, df):
        S = _situ(df["start_yl"], df["start_sec"], df["score_diff"], df["off_home"], df["neutral"], self.baseline)
        if self.baseline:
            return S
        k = len(self.teams)
        o, d = np.zeros((len(df), k)), np.zeros((len(df), k))
        o[np.arange(len(df)), df["off"].map(self.tix).to_numpy()] = 1
        d[np.arange(len(df)), df["def"].map(self.tix).to_numpy()] = 1
        return np.hstack([S, o, d])

    def fit(self, train: pd.DataFrame, R: pd.Timestamp):
        from sklearn.linear_model import LogisticRegression
        age = (R - train["kickoff_utc"]).dt.total_seconds() / 86400
        w = 0.5 ** (age / 240)
        y = train["cls"].map(CIX).to_numpy()
        self.m = LogisticRegression(C=1.0, max_iter=2000).fit(self.X(train), y, sample_weight=w)
        full = np.zeros((len(CLASSES), self.m.coef_.shape[1]))
        full[self.m.classes_] = self.m.coef_
        icpt = np.full(len(CLASSES), -30.0)
        icpt[self.m.classes_] = self.m.intercept_
        self.W, self.b = full, icpt
        return self

    def proba(self, df):
        z = self.X(df) @ self.W.T + self.b
        z -= z.max(1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(1, keepdims=True)


# --------------------------------------------------------------------------- 3. pace model and simulator

class Pace:
    def __init__(self, train: pd.DataFrame, season: int):
        t = train[train["next_yl"].notna() & train["cls"].isin(CLASSES)]
        t = t.assign(bin=np.minimum((t["start_yl"] // 10).astype(int), 9), c=t["cls"].map(CIX))
        self.pool = {k: (g["dur"].to_numpy(), g["next_yl"].to_numpy()) for k, g in t.groupby(["c", "bin"]) if len(g) >= 20}
        self.cpool = {k: (g["dur"].to_numpy(), g["next_yl"].to_numpy()) for k, g in t.groupby("c")}
        end = train[train["cls"] == "END_HALF"]
        self.end_dur = end["dur"].to_numpy() if len(end) else np.array([30.0])
        ko = train[train["first_in_half"] & train["game_half"].isin(["Half1", "Half2"])]
        cur = ko[ko["season"] == season]
        self.kick = (cur if len(cur) >= 50 else ko[ko["season"] == season - 1] if (ko["season"] == season - 1).sum() >= 50 else ko)["start_yl"].to_numpy()

    def sample(self, rng, c, yl):
        dur, nxt = np.zeros(len(c)), np.full(len(c), 75.0)
        b = np.minimum((yl // 10).astype(int), 9)
        for (ci, bi) in set(zip(c.tolist(), b.tolist())):
            m = (c == ci) & (b == bi)
            src = self.pool.get((ci, bi)) or self.cpool.get(ci)
            if ci == CIX["END_HALF"] or src is None:
                dur[m] = rng.choice(self.end_dur, m.sum())
                continue
            j = rng.integers(0, len(src[0]), m.sum())
            dur[m], nxt[m] = src[0][j], src[1][j]
        return dur, nxt


def _seed(gid: str) -> int:
    return int(hashlib.sha256(gid.encode()).hexdigest()[:8], 16)


def simulate(model: DriveModel, pace: Pace, home: str, away: str, neutral: int, season: int, gid: str,
             n: int = N_SIMS) -> dict:
    rng = np.random.default_rng(_seed(gid))
    sc = np.zeros((n, 2))
    first_recv = rng.integers(0, 2, n)

    def half(recv, seconds, ot=False):
        off = recv.copy()
        yl = rng.choice(pace.kick, n).astype(float)
        sec = np.full(n, float(seconds))
        live = np.ones(n, bool) if not ot else (sc[:, 0] == sc[:, 1])
        poss = np.zeros((n, 2))
        for _ in range(80):
            if not live.any():
                break
            i = np.flatnonzero(live)
            o = off[i]
            df = pd.DataFrame({"start_yl": yl[i], "start_sec": sec[i],
                               "score_diff": np.where(o == 0, sc[i, 0] - sc[i, 1], sc[i, 1] - sc[i, 0]),
                               "off_home": (o == 0).astype(int), "neutral": neutral,
                               "off": np.where(o == 0, home, away), "def": np.where(o == 0, away, home)})
            p = model.proba(df)
            c = (p.cumsum(1) < rng.random((len(i), 1))).sum(1).clip(0, len(CLASSES) - 1)
            op = OFF_PTS[c] - (1 if ot else 0) * (c == CIX["TD"])
            sc[i, o] += op
            sc[i, 1 - o] += DEF_PTS[c]
            poss[i, o] += 1
            dur, nxt = pace.sample(rng, c, yl[i])
            sec[i] -= dur
            yl[i] = nxt
            off[i] = np.where(c == KEEP_BALL, o, 1 - o)
            end = (c == CIX["END_HALF"]) | (sec[i] <= 0)
            if ot:
                unequal = sc[i, 0] != sc[i, 1]
                both = (poss[i, 0] > 0) & (poss[i, 1] > 0)
                end |= unequal & (both | np.isin(c, [CIX["TD"], CIX["SAFETY"], CIX["OPP_TD"]]))
            live[i[end]] = False

    half(first_recv, 1800)
    half(1 - first_recv, 1800)
    if (sc[:, 0] == sc[:, 1]).any():
        half(rng.integers(0, 2, n), 600 if season >= 2017 else 900, ot=True)
    margin, total = sc[:, 0] - sc[:, 1], sc.sum(1)
    mp = np.bincount(np.clip(margin, -80, 80).astype(int) + 80, minlength=len(MARGINS)) / n
    tp = np.bincount(np.clip(total, 0, 120).astype(int), minlength=len(TOTALS)) / n
    return {"p_home": float((margin > 0).mean() + 0.5 * (margin == 0).mean()), "p_tie": float((margin == 0).mean()),
            "margin_pmf": mp, "total_pmf": tp, "median_margin": float(np.median(margin)), "median_total": float(np.median(total))}


# --------------------------------------------------------------------------- 4. scoring helpers

def rps(pmf: np.ndarray, support: np.ndarray, y: float) -> float:
    return float(((np.cumsum(pmf) - (support >= y)) ** 2).sum())


def normal_pmf(mu: float, sd: float, support: np.ndarray) -> np.ndarray:
    p = norm.cdf((support + 0.5 - mu) / sd) - norm.cdf((support - 0.5 - mu) / sd)
    return p / p.sum()


def rand_pit(pmf: np.ndarray, support: np.ndarray, y: float, rng) -> float:
    k = int(np.clip(y, support[0], support[-1]) - support[0])
    F = np.cumsum(pmf)
    lo = F[k - 1] if k > 0 else 0.0
    return float(lo + rng.random() * pmf[k])


# --------------------------------------------------------------------------- walk-forward

def run_weeks(games: pd.DataFrame, drives: pd.DataFrame, base: pd.DataFrame, seasons: range, n: int = N_SIMS,
              progress=print, R_shift: pd.Timedelta = pd.Timedelta(0)) -> tuple[pd.DataFrame, pd.DataFrame]:
    """base: per gid, v2-style normal margin (pred_margin, sigma) and p_elo, built before each game's point."""
    teams = sorted(set(drives["off"]) | set(drives["def"]))
    play = games[games["played"] & games["season"].isin(seasons)]
    grows, drows = [], []
    rng_pit = np.random.default_rng(0)
    for (s, w), wk in play.groupby(["season", "week"]):
        R = wk["kickoff_utc"].min() - h.DECISION_LEAD - pd.Timedelta(hours=4) + R_shift
        tr = drives[(drives["kickoff_utc"] < R) & drives["season"].between(s - 3, s) & drives["cls"].isin(CLASSES)]
        model, basem = DriveModel(teams).fit(tr, R), DriveModel(teams, baseline=True).fit(tr, R)
        pace = Pace(tr, s)
        tot = games[games["played"] & (games["kickoff_utc"] < R) & games["season"].between(s - 2, s)]
        tmu, tsd = float((tot["score_home"] + tot["score_away"]).mean()), float((tot["score_home"] + tot["score_away"]).std())
        wd = drives[drives["gid"].isin(wk["gid"]) & drives["cls"].isin(CLASSES)]
        if len(wd):
            y = wd["cls"].map(CIX).to_numpy()
            pm, pb = model.proba(wd)[np.arange(len(wd)), y], basem.proba(wd)[np.arange(len(wd)), y]
            drows.append(pd.DataFrame({"gid": wd["gid"].to_numpy(), "season": s, "week": w, "ll_model": -np.log(np.clip(pm, 1e-12, 1)),
                                       "ll_base": -np.log(np.clip(pb, 1e-12, 1))}))
        for g in wk.itertuples(index=False):
            sim = simulate(model, pace, g.home, g.away, int(g.neutral), s, g.gid, n)
            b = base.loc[g.gid] if g.gid in base.index else None
            margin, total = g.score_home - g.score_away, g.score_home + g.score_away
            row = {"gid": g.gid, "season": s, "week": w, "kickoff_utc": g.kickoff_utc, "tie": bool(g.tie),
                   "y_home_win": g.y_home_win, "margin": margin, "total": total, "p_sim": sim["p_home"], "p_tie": sim["p_tie"],
                   "median_margin": sim["median_margin"], "median_total": sim["median_total"],
                   "rps_sim": rps(sim["margin_pmf"], MARGINS, margin), "crps_sim": rps(sim["total_pmf"], TOTALS, total),
                   "crps_base": rps(normal_pmf(tmu, tsd, TOTALS), TOTALS, total),
                   "pit_margin": rand_pit(sim["margin_pmf"], MARGINS, margin, rng_pit),
                   "pit_total": rand_pit(sim["total_pmf"], TOTALS, total, rng_pit),
                   "p_key37": float(sim["margin_pmf"][np.isin(np.abs(MARGINS), [3, 7])].sum())}
            if b is not None:
                row |= {"p_elo": float(b["p_elo"]), "rps_base": rps(normal_pmf(b["pred_margin"], b["sigma"], MARGINS), MARGINS, margin)}
            grows.append(row)
        if w == 1:
            progress(f"  sim {s}")
    return pd.DataFrame(grows), pd.concat(drows, ignore_index=True)


def pilot_baseline(feats_t90: pd.DataFrame, games: pd.DataFrame, seasons: range) -> pd.DataFrame:
    """v2-style normal margin for pilot seasons: margin_predict on earlier rows (in-sample sigma), elo at T-90."""
    rows = []
    usable = feats_t90[feats_t90["played"]]
    for (s, w), wk in feats_t90[feats_t90["season"].isin(seasons) & feats_t90["played"]].groupby(["season", "week"]):
        R = wk["point_utc"].min() - pd.Timedelta(hours=4)
        tr = usable[(usable["season"] >= h.MARGIN_TRAIN_START) & (usable["kickoff_utc"] < R)]
        pred, _, sigma = h.margin_predict(tr, wk, np.array([]))
        rows.append(pd.DataFrame({"gid": wk["gid"], "pred_margin": pred, "sigma": sigma, "p_elo": wk["elo_prob_home"]}))
    return pd.concat(rows).set_index("gid")


def paired(df: pd.DataFrame, a: str, b: str, alpha: float) -> dict:
    d = (df[a] - df[b]).to_numpy(float)
    cl = (df["season"].astype(str) + "_" + df["week"].astype(str)).to_numpy()
    wk = pd.Series(d).groupby(cl).mean()
    return {"n": int(len(d)), "mean_a": float(df[a].mean()), "mean_b": float(df[b].mean()), "delta": float(d.mean()),
            "ci": ev.cluster_boot(d, cl, alpha), "ci_level": 1 - alpha, "sd_week_mean": float(wk.std(ddof=1)), "weeks": int(len(wk))}


def mde(sd_w: float, weeks: int, alpha: float) -> float:
    return float((norm.ppf(1 - alpha / 2) + norm.ppf(0.8)) * sd_w / np.sqrt(weeks))


def weeks_needed(sd_w: float, sesoi: float, alpha: float) -> int:
    return int(np.ceil(((norm.ppf(1 - alpha / 2) + norm.ppf(0.8)) * sd_w / sesoi) ** 2))


def pit_test(u: np.ndarray) -> dict:
    hist = np.histogram(u, bins=10, range=(0, 1))[0]
    return {"hist": hist.tolist(), "chi2_p": float(chisquare(hist).pvalue), "ks_p": float(kstest(u, "uniform").pvalue)}


def market_lines(games: pd.DataFrame) -> pd.DataFrame:
    """Latest pre-kickoff (and committed pre-kickoff) median home spread and total per game from GOING quotes."""
    q = pd.read_parquet(h.CACHE / "going_quotes.parquet")
    rows = []
    for g in games.itertuples(index=False):
        x = q[(q["home"] == g.home) & (q["away"] == g.away) & ((q["commence_time"] - g.kickoff_utc).abs() < pd.Timedelta(hours=36))
              & (q["quote_time"] < g.kickoff_utc) & (q["committed_at"] < g.kickoff_utc)]
        r = {"gid": g.gid}
        for mkt, side, col in (("spreads", "home", "spread_home"), ("totals", "Over", "total_line")):
            y = x[(x["market"] == mkt) & (x["side"] == side)].sort_values("quote_time").groupby("book").tail(1)
            r[col] = float(y["point"].median()) if len(y) else np.nan
        rows.append(r)
    return pd.DataFrame(rows)
