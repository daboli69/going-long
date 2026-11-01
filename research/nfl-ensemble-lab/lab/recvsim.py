"""A sampled receiving game: who gets targets, who catches them, and for how many yards, drawn at random the way a real game is.

An averaged game gives every player his average, so no one has a big day or an empty one. Here a team's targets in a game are a random
total (negative binomial), split among its players by a Dirichlet-multinomial (each game draws its own lumpy shares around the player's
expected share), each target is caught with the player's catch rate (plus a team-wide good-day or bad-day shift), and each catch gains
yards from a gamma curve around the player's yards per catch.

Inputs are raw play-by-play targets over the team's last six games, counted only for games the player was available (roster active,
not on the official Out or Doubtful list, not inactive), pooled toward a position prior when the record is short, and blended with
FantasyPoints target share where that tested better (lab/fpds_usage.py). `fit` chooses every constant on 2022-2024 games only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from scipy.special import gammaln

from . import avail_source as A
from . import fpds_usage as X
from . import gamecenter_data as D
from . import usage as U
import json

from .config import CACHE_DIR, RAW_DIR
from .ingest import normalize_team

WINDOW = 6
RULE_PATH = CACHE_DIR / "recvsim_rule.json"
GROUPS = ("WR", "TE", "RB")


# --------------------------------------------------------------------------- raw targets

def pass_plays(season: int) -> pd.DataFrame:
    """Every target in the season: one row per pass play with a named receiver (no sacks, spikes or two-point tries)."""
    path = RAW_DIR / f"play_by_play_{season}.parquet"
    if not path.exists():
        return pd.DataFrame()

    def build():
        c = ["week", "posteam", "play_type", "sack", "qb_spike", "two_point_attempt", "receiver_player_id", "complete_pass", "receiving_yards", "game_id"]
        p = pd.read_parquet(path, columns=c)
        p = p[(p["play_type"] == "pass") & (p["sack"] != 1) & (p["qb_spike"] != 1) & (p["two_point_attempt"] != 1) & p["receiver_player_id"].notna()].copy()
        p["team"] = p["posteam"].map(A._team)
        p = p.dropna(subset=["team"])
        p["rec"] = p["complete_pass"].fillna(0).astype(int)
        p["yds"] = np.where(p["rec"] == 1, p["receiving_yards"].fillna(0), 0.0)
        return p.rename(columns={"receiver_player_id": "pid"})[["game_id", "week", "team", "pid", "rec", "yds"]].assign(season=season)
    return D._cached(("pass_plays", season), D._mt(path), build)


def player_games(seasons) -> pd.DataFrame:
    frames = [pass_plays(s) for s in seasons]
    p = pd.concat([f for f in frames if len(f)], ignore_index=True)
    g = p.groupby(["season", "week", "team", "pid"]).agg(tgt=("rec", "size"), rec=("rec", "sum"), yds=("yds", "sum")).reset_index()
    g["group"] = g["pid"].map(U.positions()).fillna("OTHER")
    return g


# --------------------------------------------------------------------------- as-of inputs for one team-game

@dataclass
class Block:
    """One team's season: targets, catches, yards and availability by player and week."""
    weeks: list
    T: np.ndarray            # team targets by week
    pids: list
    group: list
    tgt: np.ndarray          # (players, weeks)
    rec: np.ndarray
    yds: np.ndarray
    av: np.ndarray           # 1 where the player was available that week


def blocks(seasons) -> dict:
    g = player_games(seasons)
    st = A.status_table(seasons)
    out = {}
    for (season, team), gt in g.groupby(["season", "team"]):
        weeks = sorted(gt["week"].unique())
        s = st[(st["season"] == season) & (st["team"] == team)]
        pids = sorted(set(gt["pid"]))
        wi = {w: i for i, w in enumerate(weeks)}
        pi = {p: i for i, p in enumerate(pids)}
        tgt = np.zeros((len(pids), len(weeks))); rec = tgt.copy(); yds = tgt.copy()
        for r in gt.itertuples(index=False):
            tgt[pi[r.pid], wi[r.week]] = r.tgt; rec[pi[r.pid], wi[r.week]] = r.rec; yds[pi[r.pid], wi[r.week]] = r.yds
        av = np.zeros_like(tgt)
        ok = s[(s["roster"] == "ACT") & ~s["official"].isin(["Out", "Doubtful"]) & (s["roster"] != "INA")]
        for r in ok.itertuples(index=False):
            if r.gsis_id in pi and r.week in wi:
                av[pi[r.gsis_id], wi[r.week]] = 1
        av[tgt > 0] = 1  # he caught or was thrown to, so he played
        group = [U.positions().get(p, "OTHER") for p in pids]
        out[(season, team)] = Block(weeks, tgt.sum(0), pids, group, tgt, rec, yds, av)
    return out


def out_ids(st: pd.DataFrame, season: int, team: str, week: int, variant: str, game_day: bool) -> set:
    """Players not expected to play: "official" (the old rule, official Out only) or "source" (the availability source)."""
    s = st[(st["season"] == season) & (st["team"] == team) & (st["week"] == week)]
    if variant == "official":
        return set(s.loc[s["official"] == "Out", "gsis_id"])
    bad = s["official"].isin(["Out", "Doubtful"]) | s["roster"].isin(A.HARD_ROSTER) | (s["roster"] == "DEV")
    if game_day:
        bad |= s["roster"].isin(A.GAME_DAY)
    return set(s.loc[bad, "gsis_id"])


def window(b: Block, week: int) -> dict | None:
    """Window totals before `week` for every player, or None when the team has fewer than two games on record."""
    idx = [i for i, w in enumerate(b.weeks) if w < week][-WINDOW:]
    if len(idx) < 2:
        return None
    T = b.T[idx]
    av = b.av[:, idx]
    N = (av * T[None, :]).sum(1)
    return {"N": N, "tgt": b.tgt[:, idx].sum(1), "rec": b.rec[:, idx].sum(1), "yds": b.yds[:, idx].sum(1), "muT": float(T.mean()), "idx": idx}


@dataclass
class Case:
    season: int
    week: int
    team: str
    pids: list
    group: list
    N: np.ndarray
    tgt_w: np.ndarray
    rec_w: np.ndarray
    yds_w: np.ndarray
    fp: np.ndarray            # FantasyPoints target share as of the week, NaN where absent
    muT: float
    actual_tgt: np.ndarray    # this game, pool players
    actual_rec: np.ndarray
    actual_yds: np.ndarray
    other_tgt: float          # targets to players outside the pool
    other_rec: float
    other_yds: float
    total_tgt: float
    n_recv: int               # receivers with a catch, whole team
    top_share: float
    te_share: float
    games: int = 6            # games in the window behind the shares
    t_scale: float = 1.0      # stretch on the team's expected targets for a game flow (set for games not yet played)


def make_cases(blks: dict, st: pd.DataFrame, seasons_weeks, variant: str = "source", game_day: bool = True, with_fpds: bool = True) -> list[Case]:
    cases = []
    for (season, team), b in blks.items():
        want = [(a, z) for s, a, z in seasons_weeks if s == season]
        if not want:
            continue
        for week in b.weeks:
            if not any(a <= week <= z for a, z in want):
                continue
            w = window(b, week)
            if w is None:
                continue
            out = out_ids(st, season, team, week, variant, game_day)
            wi = b.weeks.index(week)
            pool = [i for i, p in enumerate(b.pids) if w["tgt"][i] > 0 and p not in out and b.group[i] in GROUPS]
            if len(pool) < 3:
                continue
            fp = np.full(len(pool), np.nan)
            if with_fpds:
                f = X.features_asof(season, team, week)
                if len(f) and "tgt_pct" in f.columns:
                    fp = f["tgt_pct"].reindex([b.pids[i] for i in pool]).to_numpy(float)
            at, ar, ay = b.tgt[pool, wi], b.rec[pool, wi], b.yds[pool, wi]
            tot = float(b.T[wi])
            allrec = b.rec[:, wi]
            te = sum(b.rec[i, wi] for i in range(len(b.pids)) if b.group[i] == "TE")
            cases.append(Case(season, week, team, [b.pids[i] for i in pool], [b.group[i] for i in pool], w["N"][pool], w["tgt"][pool], w["rec"][pool], w["yds"][pool],
                              fp, w["muT"], at, ar, ay, tot - at.sum(), float(allrec.sum() - ar.sum()), float(b.yds[:, wi].sum() - ay.sum()), tot,
                              int((allrec > 0).sum()), float(allrec.max() / max(allrec.sum(), 1)), float(te / max(allrec.sum(), 1)), len(w["idx"])))
    return cases


# --------------------------------------------------------------------------- the model

@dataclass
class Params:
    k: float = 100.0         # team targets of evidence given to the prior when a player's record is short
    prior: float = 0.03      # share a player with no record gets
    w_fpds: float = 0.0
    eps: float = 0.06        # share of targets that go to players outside the expected group
    alpha: float = 40.0      # Dirichlet concentration: larger means games stay closer to the expected shares
    alpha_short: float = 24.0  # the same when the window holds four games or fewer: a shorter record is less certain
    alpha_mult: float = 1.0    # calibrated on training games so a whole simulated box score is as lumpy as a real one
    r_nb: float = 30.0       # dispersion of a team's total targets
    t_slope: float = 1.0     # a team's expected targets regress toward the league: expected = t_icpt + t_slope * its recent average
    t_icpt: float = 0.0
    m_c: float = 20.0
    m_y: float = 6.0
    c_g: dict = field(default_factory=lambda: {"WR": 0.62, "TE": 0.70, "RB": 0.78, "other": 0.65})
    y_g: dict = field(default_factory=lambda: {"WR": 12.5, "TE": 10.5, "RB": 7.5, "other": 10.0})
    kappa: dict = field(default_factory=lambda: {"WR": 1.6, "TE": 1.7, "RB": 1.3, "other": 1.5})
    sigma_c: float = 0.12


def expected_shares(c: Case, p: Params) -> np.ndarray:
    """Expected share of the team's targets for each pool player, plus a last entry for everyone else."""
    s = (c.tgt_w + p.k * p.prior) / (c.N + p.k)
    s = s / s.sum()
    if p.w_fpds > 0 and np.isfinite(c.fp).any():
        s = (1 - p.w_fpds) * s + p.w_fpds * X.share_from(c.fp, s)
    return np.append((1 - p.eps) * s, p.eps)


def alpha_for(c: Case, p: Params) -> float:
    return (p.alpha_short if c.games <= 4 else p.alpha) * p.alpha_mult


def dm_loglik(counts: np.ndarray, mu: np.ndarray, alpha: float) -> float:
    a = alpha * mu
    n = counts.sum()
    return float(gammaln(alpha) - gammaln(n + alpha) + np.sum(gammaln(counts + a) - gammaln(a)))


def _rates(c: Case, p: Params):
    cg = np.array([p.c_g[g] for g in c.group]); yg = np.array([p.y_g[g] for g in c.group])
    cr = (c.rec_w + p.m_c * cg) / (c.tgt_w + p.m_c)
    ypr = (c.yds_w + p.m_y * yg) / (c.rec_w + p.m_y)
    return np.clip(cr, 0.2, 0.95), np.clip(ypr, 3.0, 30.0)


def sample(c: Case, p: Params, S: int, rng: np.random.Generator) -> dict:
    """S sampled games for one team: targets, catches and yards for every pool player and for the "everyone else" bucket (last column)."""
    mu = expected_shares(c, p)
    P = len(mu)
    probs = rng.dirichlet(np.clip(alpha_for(c, p) * mu, 1e-3, None), size=S)
    mean_t = max((p.t_icpt + p.t_slope * c.muT) * c.t_scale, 5.0)
    T = rng.negative_binomial(p.r_nb, p.r_nb / (p.r_nb + mean_t), size=S)
    tgt = np.vstack([rng.multinomial(int(t), pr) for t, pr in zip(T, probs)]).astype(float)
    cr, ypr = _rates(c, p)
    cr = np.append(cr, p.c_g["other"]); ypr = np.append(ypr, p.y_g["other"])
    kap = np.array([p.kappa[g] for g in c.group] + [p.kappa["other"]])
    z = rng.normal(0, p.sigma_c, size=(S, 1))
    pc = 1 / (1 + np.exp(-(np.log(cr / (1 - cr))[None, :] + z)))
    rec = rng.binomial(tgt.astype(int), pc).astype(float)
    shape = np.where(rec > 0, kap[None, :] * rec, 1.0)
    yds = np.where(rec > 0, rng.gamma(shape, (ypr / kap)[None, :]), 0.0)
    return {"tgt": tgt, "rec": rec, "yds": np.rint(yds), "P": P}


# --------------------------------------------------------------------------- fitting on the training games

def fit(cases: list[Case], seasons_weeks_note: str = "") -> Params:
    """Choose every constant on the training cases only: pooling, FantasyPoints weight, outside share, concentration, catch and yards curves."""
    p = Params()

    def total(par: Params, only=None) -> float:
        ll = 0.0
        for c in cases:
            if only is not None and not only(c):
                continue
            mu = expected_shares(c, par)
            ll += dm_loglik(np.append(c.actual_tgt, c.other_tgt), mu, alpha_for(c, par))
        return ll
    best = None
    for k in (50, 100, 200, 400):
        for prior in (0.01, 0.02, 0.04):
            q = Params(**{**asdict(p), "k": float(k), "prior": prior})
            v = total(q)
            if best is None or v > best[0]:
                best = (v, q)
    p = best[1]
    for w in (0.0, 0.25, 0.5, 0.75):
        q = Params(**{**asdict(p), "w_fpds": w}); p = q if total(q) > total(p) else p
    for eps in (0.005, 0.01, 0.02, 0.04, 0.06, 0.09):
        q = Params(**{**asdict(p), "eps": eps}); p = q if total(q) > total(p) else p
    for a in (10, 16, 24, 36, 55, 80, 120):
        q = Params(**{**asdict(p), "alpha": float(a)}); p = q if total(q, lambda c: c.games >= 5) > total(p, lambda c: c.games >= 5) else p
    for a in (8, 12, 16, 24, 36, 55):
        q = Params(**{**asdict(p), "alpha_short": float(a)}); p = q if total(q, lambda c: c.games <= 4) > total(p, lambda c: c.games <= 4) else p
    # a team's total targets: its recent average regressed toward the league, then a negative binomial with the variance left over
    mu_t = np.array([c.muT for c in cases]); tt = np.array([c.total_tgt for c in cases])
    p.t_slope = float(np.cov(mu_t, tt)[0, 1] / mu_t.var()); p.t_icpt = float(tt.mean() - p.t_slope * mu_t.mean())
    res = tt - (p.t_icpt + p.t_slope * mu_t)
    var = max(res.var(), tt.mean() + 1.0)
    p.r_nb = float(np.clip(tt.mean() ** 2 / (var - tt.mean()), 5, 400))
    # catch rate, yards per catch and yards curve by group, from the games themselves
    t = {g: [0, 0, 0.0] for g in GROUPS}
    for c in cases:
        for j, g in enumerate(c.group):
            t[g][0] += c.actual_tgt[j]; t[g][1] += c.actual_rec[j]; t[g][2] += c.actual_yds[j]
    for g in GROUPS:
        if t[g][0] > 50:
            p.c_g[g] = t[g][1] / t[g][0]
        if t[g][1] > 20:
            p.y_g[g] = t[g][2] / t[g][1]
    best = None
    for m in (10, 20, 40, 80, 160, 320, 640):
        q = Params(**{**asdict(p), "m_c": float(m)}); ll = 0.0
        for c in cases:
            cr, _ = _rates(c, q)
            ll += float(np.sum(c.actual_rec * np.log(cr) + (c.actual_tgt - c.actual_rec) * np.log(1 - cr)))
        best = (ll, m) if best is None or ll > best[0] else best
    p.m_c = float(best[1])
    best = None
    for m in (4, 8, 16, 32, 64, 128):
        q = Params(**{**asdict(p), "m_y": float(m)}); err = 0.0
        for c in cases:
            _, ypr = _rates(c, q); mask = c.actual_rec > 0
            err += float(np.sum(((c.actual_yds[mask] / c.actual_rec[mask]) - ypr[mask]) ** 2 * c.actual_rec[mask]))
        best = (err, m) if best is None or err < best[0] else best
    p.m_y = float(best[1])
    # yards curve: match the spread of a player-game's yards per catch (gamma shape from mean and variance of per-game yards/catch scaled by catches)
    for g in GROUPS:
        vs = []
        for c in cases:
            _, ypr = _rates(c, p)
            for j, gg in enumerate(c.group):
                if gg == g and c.actual_rec[j] >= 2:
                    vs.append(((c.actual_yds[j] / c.actual_rec[j]) - ypr[j]) ** 2 * c.actual_rec[j] / ypr[j] ** 2)
        if len(vs) > 50:
            p.kappa[g] = float(np.clip(1.0 / np.mean(vs), 0.6, 6.0))
    # team good-day/bad-day catch effect: variance of the team's completion rate beyond binomial noise
    ex = []
    for c in cases:
        cr, _ = _rates(c, p)
        n = c.total_tgt
        if n < 15:
            continue
        rate = (c.actual_rec.sum() + c.other_rec) / n
        exp_rate = float((c.actual_tgt * cr).sum() + c.other_tgt * p.c_g["other"]) / n
        ex.append(((rate - exp_rate) ** 2 - exp_rate * (1 - exp_rate) / n))
    v = max(float(np.mean(ex)), 0.0)
    p.sigma_c = float(np.clip(np.sqrt(v) / 0.23, 0.0, 0.5))
    p.alpha_mult = calibrate_lumpiness(cases, p)
    return p


def calibrate_lumpiness(cases: list[Case], p: Params, grid=(1.0, 1.25, 1.5, 1.75, 2.25, 3.0)) -> float:
    """Pick the concentration multiplier whose simulated top-receiver share matches the real one on these (training) games, as long as the
    per-player central 80% ranges still hold 77% or more of the real results. The fit on target counts alone leaves games a little too lumpy."""
    sub = cases[::5]
    best = None
    for m in grid:
        q = Params(**{**asdict(p), "alpha_mult": float(m)})
        r = score(sub, q, None, S=120, seed=21)
        cov = min(r[k]["coverage80"] for k in ("tgt", "rec", "yds"))
        gap = abs(r["realism"]["top_receiver_share"]["sim"] - r["realism"]["top_receiver_share"]["real"])
        if cov >= 0.77 and (best is None or gap < best[0]):
            best = (gap, m)
    return float(best[1]) if best else 1.0


def params_dict(p: Params) -> dict:
    d = asdict(p)
    return {k: ({a: float(b) for a, b in v.items()} if isinstance(v, dict) else float(v)) for k, v in d.items()}


# --------------------------------------------------------------------------- scoring on games the fit never saw

def _gmd(X: np.ndarray) -> np.ndarray:
    """Mean absolute difference between two draws from the same forecast, by column (for CRPS)."""
    S = X.shape[0]
    Xs = np.sort(X, axis=0)
    i = np.arange(1, S + 1)[:, None]
    return (2.0 / S ** 2) * ((2 * i - S - 1) * Xs).sum(0)


def _old_method(ug: pd.DataFrame, c: Case) -> tuple[np.ndarray, np.ndarray]:
    """What the replay used before: each pool player's share of the team's catches and receiving yards over the window, times the team average."""
    u = U.usage(ug, c.season, c.team, c.week)
    if u is None:
        return np.zeros(len(c.pids)), np.zeros(len(c.pids))
    pl = u.players.set_index("pid").reindex(c.pids)
    out = []
    for stat in ("rec", "rec_yds"):
        sh = pl[f"share_{stat}"].fillna(0).clip(lower=0).to_numpy()
        out.append(sh / max(sh.sum(), 1e-9) * u.totals[stat])
    return out[0], out[1]


def team_box(rec: np.ndarray, other: np.ndarray, group: list) -> tuple:
    """Receivers with a catch, top receiver's share of catches, tight ends' share, for S sampled games at once.

    rec is (S, players); `other` is (S,) catches by everyone outside the pool, split into two pseudo-players; a quarter of them are tight ends."""
    hi, lo = np.ceil(other / 2), np.floor(other / 2)
    n = (rec > 0).sum(1) + (hi > 0) + (lo > 0)
    tot = np.maximum(rec.sum(1) + other, 1)
    top = np.maximum(rec.max(1), hi) / tot
    te = (rec[:, [j for j, g in enumerate(group) if g == "TE"]].sum(1) + 0.25 * other) / tot
    return n, top, te


def score(cases: list[Case], p: Params, ug: pd.DataFrame | None = None, S: int = 400, seed: int = 1) -> dict:
    """Coverage of the central 80% range, CRPS, point-forecast error against the old averaged numbers, and how the sampled team box scores
    look next to the real ones (averaged over every sampled game, not one)."""
    rng = np.random.default_rng(seed)
    pit = {k: [] for k in ("tgt", "rec", "yds")}
    crps = {k: [] for k in ("tgt", "rec", "yds")}
    gap = {k: [] for k in ("rec", "yds")}      # per-case mean CRPS, new minus old
    mae = {k: [] for k in ("rec", "yds")}      # per-case mean absolute error of the average forecast, new minus old
    real, sim = [], []
    for c in cases:
        s = sample(c, p, S, rng)
        P = len(c.pids)
        for name, actual in (("tgt", c.actual_tgt), ("rec", c.actual_rec), ("yds", c.actual_yds)):
            X = s[name][:, :P]
            pit[name].append((X < actual[None, :]).mean(0) + rng.random(P) * (X == actual[None, :]).mean(0))
            crps[name].append(np.abs(X - actual).mean(0) - 0.5 * _gmd(X))
        if ug is not None:
            o_rec, o_yds = _old_method(ug, c)
            for name, old, actual in (("rec", o_rec, c.actual_rec), ("yds", o_yds, c.actual_yds)):
                gap[name].append(float(crps[name][-1].mean() - np.abs(old - actual).mean()))
                mae[name].append(float(np.abs(s[name][:, :P].mean(0) - actual).mean() - np.abs(old - actual).mean()))
        n, top, te = team_box(s["rec"][:, :P], s["rec"][:, P], c.group)
        sim.append((n.mean(), top.mean(), te.mean(), s["tgt"].sum(1).mean(), s["yds"].sum(1).mean()))
        real.append((c.n_recv, c.top_share, c.te_share, c.total_tgt, float(sum(c.actual_yds) + c.other_yds)))
    out = {"cases": len(cases)}
    for name in ("tgt", "rec", "yds"):
        pits = np.concatenate(pit[name])
        out[name] = {"coverage80": float(((pits >= 0.1) & (pits <= 0.9)).mean()), "crps": float(np.concatenate(crps[name]).mean()), "player_games": int(len(pits)),
                     "pit_deciles": [float(((pits >= i / 10) & (pits < (i + 1) / 10)).mean()) for i in range(10)]}
    if ug is not None:
        rng2 = np.random.default_rng(5)
        for name in ("rec", "yds"):
            for key, arr in (("crps_gap_vs_old", gap[name]), ("mae_gap_vs_old", mae[name])):
                g = np.array(arr)
                m = g[rng2.integers(0, len(g), (2000, len(g)))].mean(1)
                out[name][key] = {"mean": float(g.mean()), "lo": float(np.percentile(m, 5)), "hi": float(np.percentile(m, 95))}
    real, sim = np.array(real), np.array(sim)
    out["realism"] = {k: {"real": float(real[:, i].mean()), "sim": float(sim[:, i].mean())} for i, k in enumerate(("receivers_with_a_catch", "top_receiver_share", "te_catch_share", "team_targets", "team_receiving_yards"))}
    return out


def future_case(blk: dict, season: int, team: str, week: int, out: set, mu_scale: float = 1.0) -> Case | None:
    """A game not yet played: the pool is every player with a target in the team's last six games who is not in `out`.
    `mu_scale` stretches the team's expected targets (expected score and game flow)."""
    b = blk.get((season, team))
    w = window(b, week) if b else None
    if w is None:
        return None
    pool = [i for i, p in enumerate(b.pids) if w["tgt"][i] > 0 and p not in out and b.group[i] in GROUPS]
    if len(pool) < 3:
        return None
    z = np.zeros(len(pool))
    return Case(season, week, team, [b.pids[i] for i in pool], [b.group[i] for i in pool], w["N"][pool], w["tgt"][pool], w["rec"][pool], w["yds"][pool],
                np.full(len(pool), np.nan), w["muT"], z, z, z, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, len(w["idx"]), mu_scale)


def blocks_cached(season: int) -> dict:
    """One season's team blocks, rebuilt only when the play-by-play, roster or injury file changes."""
    files = [RAW_DIR / f"play_by_play_{season}.parquet", RAW_DIR / f"roster_weekly_{season}.parquet", RAW_DIR / f"injuries_{season}.parquet"]
    return D._cached(("recv_blocks", season), tuple(D._mt(f) if f.exists() else 0 for f in files), lambda: blocks([season]))


def sample_game(c: Case, p: Params, rng: np.random.Generator) -> dict:
    """One sampled game for a team: targets and catches for each pool player, the yards of every catch, and the same for everyone else."""
    s = sample(c, p, 1, rng)
    P = len(c.pids)
    tgt, rec = s["tgt"][0].astype(int), s["rec"][0].astype(int)
    _, ypr = _rates(c, p)
    ypr = np.append(ypr, p.y_g["other"])
    kap = np.array([p.kappa[g] for g in c.group] + [p.kappa["other"]])
    yards = [np.rint(rng.gamma(kap[j], ypr[j] / kap[j], size=int(rec[j]))).astype(int).tolist() for j in range(P + 1)]
    return {"pids": list(c.pids), "group": list(c.group), "tgt": tgt[:P].tolist(), "rec": rec[:P].tolist(), "yards": yards[:P],
            "other": {"tgt": int(tgt[P]), "rec": int(rec[P]), "yards": yards[P]}}


def load_rule(path=RULE_PATH) -> tuple[Params | None, bool]:
    """The fitted constants and whether the model passed every gate in scripts/recvsim_check.py. (None, False) until that has run."""
    if not path.exists():
        return None, False
    d = json.loads(path.read_text(encoding="utf-8"))
    pr = d["params"]
    return Params(**{k: (dict(v) if isinstance(v, dict) else v) for k, v in pr.items()}), bool(d.get("passed"))
