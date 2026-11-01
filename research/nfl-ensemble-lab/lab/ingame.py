"""In-game updating of player and game projections from the play-by-play so far.

A player's final stat is split into three parts that can each go wrong for a different reason:
  1. team volume: how many pass attempts (or rushes) the team will still run. Depends on the clock, the score (a trailing team throws) and the team's own pace.
  2. player share: the fraction of those attempts that go to him as a target (or carry). Beta-Binomial update of his pregame share by what he has seen so far.
  3. efficiency: yards per target or carry, and catch rate. Observed rate shrunk toward his pregame rate.
The pregame projection is the same model at kickoff (nothing observed), so any difference between "frozen" and "updated" comes from the update alone.
Estimated constants (`Params`) are fitted on seasons before the evaluation seasons; scripts/ingame_eval.py never fits on its test seasons.
Snaps and routes are not in any free live feed, so opportunity here means targets, carries and pass attempts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import betabinom

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GAME = 3600.0
CHECKPOINTS = (600, 1200, 1800, 2400, 3000)           # seconds elapsed at which a game is "paused" and scored
FAMILIES = {"rec": "Receiving yards", "rush": "Rushing yards", "pass": "Passing yards"}
THRESH = {"rec": 2.5, "rush": 5.0, "pass": 12.0}      # minimum pregame targets, carries, attempts per game for a player to be tracked
WINDOW = 8                                            # team games of history behind a pregame baseline
MIN_HISTORY = 4

PBP_COLS = ["game_id", "season", "week", "season_type", "qtr", "game_seconds_remaining", "posteam", "home_team", "away_team", "score_differential",
            "total_home_score", "total_away_score", "pass_attempt", "rush_attempt", "qb_kneel", "qb_spike", "complete_pass", "receiver_player_id",
            "rusher_player_id", "passer_player_id", "passing_yards", "receiving_yards", "rushing_yards", "ep", "down", "yardline_100", "spread_line",
            "total_line", "home_wp", "result", "total", "ydstogo", "posteam_timeouts_remaining", "defteam_timeouts_remaining"]


# --------------------------------------------------------------------------- history

def load_plays(seasons) -> pd.DataFrame:
    frames = []
    for s in seasons:
        d = pd.read_parquet(RAW / f"play_by_play_{s}.parquet", columns=PBP_COLS)
        frames.append(d[d["season_type"] == "REG"])
    return pd.concat(frames, ignore_index=True)


def events(plays: pd.DataFrame) -> pd.DataFrame:
    """One row per pass attempt or rush: game, team, elapsed seconds, the player involved and the yards."""
    p = plays[(plays["posteam"].notna())].copy()
    p["t"] = np.where(p["qtr"] >= 5, GAME + 1.0, GAME - p["game_seconds_remaining"])
    is_pass = (p["pass_attempt"] == 1)
    is_rush = (p["rush_attempt"] == 1) & (p["qb_kneel"].fillna(0) != 1) & ~is_pass
    out = []
    pa = p[is_pass]
    out.append(pd.DataFrame({"gid": pa["game_id"], "season": pa["season"], "week": pa["week"], "team": pa["posteam"], "t": pa["t"], "kind": "pass",
                             "passer": pa["passer_player_id"], "player": pa["receiver_player_id"], "yards": pa["receiving_yards"].fillna(0.0),
                             "pyards": pa["passing_yards"].fillna(0.0), "catch": pa["complete_pass"].fillna(0.0), "diff": pa["score_differential"],
                             "ep": pa["ep"], "down": pa["down"], "yl": pa["yardline_100"]}))
    ra = p[is_rush]
    out.append(pd.DataFrame({"gid": ra["game_id"], "season": ra["season"], "week": ra["week"], "team": ra["posteam"], "t": ra["t"], "kind": "rush",
                             "passer": None, "player": ra["rusher_player_id"], "yards": ra["rushing_yards"].fillna(0.0), "pyards": 0.0, "catch": 0.0,
                             "diff": ra["score_differential"], "ep": ra["ep"], "down": ra["down"], "yl": ra["yardline_100"]}))
    e = pd.concat(out, ignore_index=True)
    return e.sort_values(["gid", "t"], kind="stable").reset_index(drop=True)


def games_table(plays: pd.DataFrame) -> pd.DataFrame:
    g = plays.groupby("game_id").agg(season=("season", "first"), week=("week", "first"), home=("home_team", "first"), away=("away_team", "first"),
                                      spread=("spread_line", "first"), total_line=("total_line", "first"), result=("result", "first"), total=("total", "first")).reset_index()
    return g.rename(columns={"game_id": "gid"}).sort_values(["season", "week", "gid"]).reset_index(drop=True)


def _fam_rows(e: pd.DataFrame, fam: str) -> pd.DataFrame:
    """Events as (gid, team, pid, t, yards, catch) for one family; passing rows are the quarterback's attempts."""
    if fam == "rec":
        x = e[(e["kind"] == "pass") & e["player"].notna()]
        return x.assign(pid=x["player"])
    if fam == "pass":
        x = e[(e["kind"] == "pass") & e["passer"].notna()]
        return x.assign(pid=x["passer"], yards=x["pyards"])
    x = e[(e["kind"] == "rush") & e["player"].notna()]
    return x.assign(pid=x["player"])


def team_volume(e: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Per team game: pass attempts, rushes and the team's game order, plus its trailing pregame averages."""
    tv = e.groupby(["gid", "team", "kind"]).size().unstack("kind", fill_value=0).reset_index()
    tv = tv.rename(columns={"pass": "n_pass", "rush": "n_rush"})
    tv = tv.merge(games[["gid", "season", "week"]], on="gid").sort_values(["team", "season", "week"]).reset_index(drop=True)
    tv["idx"] = tv.groupby("team").cumcount()
    for k in ("n_pass", "n_rush"):
        tv["pre_" + k] = tv.groupby("team")[k].transform(lambda s: s.shift(1).rolling(WINDOW, min_periods=3).mean())
    return tv


@dataclass
class Params:
    """Constants estimated on training seasons only."""
    kappa: dict = field(default_factory=lambda: {"rec": 40.0, "rush": 40.0, "pass": 200.0})      # prior strength of a player's pregame share
    m_eff: dict = field(default_factory=lambda: {"rec": 60.0, "rush": 60.0, "pass": 100.0})      # pseudo-opportunities behind pregame efficiency
    m_catch: float = 40.0
    vol_beta: dict = field(default_factory=dict)       # kind -> OLS coefficients for remaining team attempts
    vol_theta: dict = field(default_factory=dict)      # kind -> negative binomial dispersion
    pool: dict = field(default_factory=dict)           # fam -> per-opportunity yards (sampled)
    pool_catch: dict = field(default_factory=dict)
    sigma_m: float = 13.3
    sigma_t: float = 10.0
    gamma_ep: float = 0.5
    ep_table: dict = field(default_factory=dict)       # (down, yardline bucket) -> mean expected points
    margin_beta: tuple = (1.0, 0.0)                    # remaining-margin mean = a * pregame margin * rho + b * ep term


def baselines(e: pd.DataFrame, tv: pd.DataFrame, pool: dict, pool_catch: dict, m_eff: dict, m_catch: float) -> dict[str, pd.DataFrame]:
    """Pregame baseline for every tracked player-game: per-game opportunities, share of the team's attempts, pooled-shrunk efficiency and catch rate.
    Uses only the team's previous WINDOW games, zeros included for games the player missed after his first appearance."""
    out = {}
    by_team = {t: g.sort_values("idx") for t, g in tv.groupby("team")}
    for fam in FAMILIES:
        kind_col = "n_rush" if fam == "rush" else "n_pass"
        rows = _fam_rows(e, fam)
        g = rows.groupby(["gid", "team", "pid"]).agg(O=("t", "size"), Y=("yards", "sum"), C=("catch", "sum")).reset_index()
        g = g.merge(tv[["gid", "team", "idx"]], on=["gid", "team"])
        po, pc = float(pool[fam].mean()), float(pool_catch[fam])
        recs = []
        for (pid, team), h in g.groupby(["pid", "team"]):
            tg = by_team[team]
            n = len(tg)
            O, Y, C = (np.zeros(n) for _ in range(3))
            O[h["idx"].to_numpy()], Y[h["idx"].to_numpy()], C[h["idx"].to_numpy()] = h["O"].to_numpy(), h["Y"].to_numpy(), h["C"].to_numpy()
            V = tg[kind_col].to_numpy(dtype=float)
            cO, cY, cC, cV = (np.concatenate([[0.0], np.cumsum(x)]) for x in (O, Y, C, V))
            first = int(h["idx"].min())
            gids = tg["gid"].to_numpy()
            for i in range(first + MIN_HISTORY, n):
                lo = max(0, i - WINDOW)
                w = i - lo
                o = cO[i] - cO[lo]
                if o / w < THRESH[fam]:
                    continue
                y, c, v = cY[i] - cY[lo], cC[i] - cC[lo], cV[i] - cV[lo]
                recs.append((gids[i], team, pid, o / w, o / max(v, 1.0), (y + m_eff[fam] * po) / (o + m_eff[fam]), (c + m_catch * pc) / (o + m_catch)))
        out[fam] = pd.DataFrame(recs, columns=["gid", "team", "pid", "mu_O", "share", "ypo", "cr"])
    return out


# --------------------------------------------------------------------------- team volume and score model

def vol_design(rho, pre, d):
    d = np.clip(d, -24, 24)
    return np.column_stack([rho, rho * pre, rho * d, rho * d * (1 - rho)])


def fit_volume(rows: pd.DataFrame, kind: str, params: Params) -> None:
    """rows: columns rho, pre, d, y (attempts still to come). Fitted by least squares; NB dispersion by moments."""
    X = vol_design(rows["rho"].to_numpy(), rows["pre"].to_numpy(), rows["d"].to_numpy())
    b, *_ = np.linalg.lstsq(X, rows["y"].to_numpy(), rcond=None)
    mu = np.clip(X @ b, 0.2, None)
    inv_theta = max(float(np.sum((rows["y"].to_numpy() - mu) ** 2 - mu) / np.sum(mu ** 2)), 1e-3)
    params.vol_beta[kind], params.vol_theta[kind] = b, 1.0 / inv_theta


def volume_mean(params: Params, kind: str, t: float, pre: float, d: float) -> float:
    rho = max(0.0, (GAME - t) / GAME)
    return float(max((vol_design(np.array([rho]), np.array([pre]), np.array([d])) @ params.vol_beta[kind])[0], 0.0 if rho == 0 else 0.2))


def nb_draw(rng, mean: float, theta: float, size: int) -> np.ndarray:
    if mean <= 0:
        return np.zeros(size, dtype=int)
    p = theta / (theta + mean)
    return rng.negative_binomial(theta, p, size)


# --------------------------------------------------------------------------- player update

@dataclass
class PlayerState:
    fam: str
    pre_O: float            # pregame opportunities per game (mu_O)
    pre_share: float        # pregame share of the team's attempts
    pre_ypo: float
    pre_cr: float
    O: int                  # opportunities so far
    Y: float                # yards so far
    C: float                # catches so far (receivers)
    A: int                  # team attempts so far (pass attempts, or rushes)
    t: float                # elapsed seconds
    d: float                # team score differential now
    pre_vol: float          # team pregame attempts per game of this kind
    kappa: float | None = None   # prior strength of his share; None uses the fitted constant for the family


def predict_player(p: Params, s: PlayerState, M: int = 400, seed: int = 0) -> dict:
    """Draws of the player's final yards (and receptions) given the state, plus the pieces of the update."""
    rng = np.random.default_rng(seed)
    kind = "rush" if s.fam == "rush" else "pass"
    kap = s.kappa or p.kappa[s.fam]
    sh = float(np.clip(s.pre_share, 1e-4, 0.999))
    mu_A = volume_mean(p, kind, s.t, s.pre_vol, s.d)
    A_rem = nb_draw(rng, mu_A, p.vol_theta[kind], M)
    a = sh * kap + s.O
    b = (1 - sh) * kap + max(s.A - s.O, 0)
    share_draw = rng.beta(a, b, M)
    O_rem = rng.binomial(A_rem, share_draw)
    ypo_post = (p.m_eff[s.fam] * s.pre_ypo + s.Y) / (p.m_eff[s.fam] + s.O)
    pool = p.pool[s.fam]
    ratio = ypo_post / max(pool.mean(), 1e-6)
    nmax = int(min(O_rem.max(initial=0), 70))
    if nmax > 0:
        idx = rng.integers(0, len(pool), (M, nmax))
        mask = np.arange(nmax)[None, :] < np.minimum(O_rem, nmax)[:, None]
        Y_rem = (pool[idx] * mask).sum(axis=1) * ratio
    else:
        Y_rem = np.zeros(M)
    out = {"yards": s.Y + Y_rem, "O_rem": O_rem, "share_post": a / (a + b), "mu_A": mu_A, "ypo_post": ypo_post}
    if s.fam == "rec":
        cr_post = (p.m_catch * s.pre_cr + s.C) / (p.m_catch + s.O)
        out["catches"] = s.C + rng.binomial(O_rem, float(np.clip(cr_post, 0.01, 0.99)))
        out["cr_post"] = cr_post
    return out


def role_check(p: Params, s: PlayerState) -> dict:
    """Probability the player's true share is well below or above his pregame share, given what the team has run so far."""
    kap = s.kappa or p.kappa[s.fam]
    sh = float(np.clip(s.pre_share, 1e-4, 0.999))
    a = sh * kap + s.O
    b = (1 - sh) * kap + max(s.A - s.O, 0)
    from scipy.stats import beta
    return {"share_pre": sh, "share_post": a / (a + b), "p_lower": float(beta.cdf(0.65 * sh, a, b)), "p_higher": float(1 - beta.cdf(1.5 * sh, a, b)), "attempts_seen": s.A}


def decompose(p: Params, s: PlayerState) -> dict:
    """Change in the expected final yards (updated minus pregame), split into script, role and efficiency by swapping one input at a time."""
    kind = "rush" if s.fam == "rush" else "pass"
    kap = s.kappa or p.kappa[s.fam]
    sh = float(np.clip(s.pre_share, 1e-4, 0.999))
    pre_vol = max(s.pre_vol, 1e-6)
    pool_mean = p.pool[s.fam].mean()
    zero = volume_mean(p, kind, 0.0, s.pre_vol, 0.0)
    now_vol = s.A + volume_mean(p, kind, s.t, s.pre_vol, s.d)
    share_post = (sh * kap + s.O) / (kap + s.A) if s.A > 0 else sh
    ypo_post = (p.m_eff[s.fam] * s.pre_ypo + s.Y) / (p.m_eff[s.fam] + s.O)
    base = zero * sh * s.pre_ypo
    after_script = now_vol * sh * s.pre_ypo
    after_role = now_vol * share_post * s.pre_ypo
    # expected final yards = yards already banked + expected yards to come; the share and efficiency applied to the remaining attempts only
    rem = volume_mean(p, kind, s.t, s.pre_vol, s.d)
    final_updated = s.Y + rem * share_post * ypo_post
    return {"pre": base, "updated": final_updated, "script": after_script - base, "role": after_role - after_script,
            "luck_and_efficiency": final_updated - after_role}


def window_ev(ev: pd.DataFrame, gid: str, team: str, t: float):
    x = ev[(ev["gid"] == gid) & (ev["team"] == team) & (ev["t"] <= t)]
    return x


# --------------------------------------------------------------------------- scoring rules

def crps_samples(x: np.ndarray, y: float) -> float:
    """CRPS of an ensemble: E|X - y| - 0.5 E|X - X'|."""
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    term1 = np.abs(x - y).mean()
    term2 = np.sum((2 * np.arange(1, n + 1) - n - 1) * x) / (n * n)
    return float(term1 - term2)


# --------------------------------------------------------------------------- game level

def ep_bucket(down, yl):
    return (int(down) if down == down and down else 0, int(min(max(yl, 1), 99) // 10)) if yl == yl else (0, -1)


def fit_game(plays: pd.DataFrame, games: pd.DataFrame, params: Params) -> None:
    """Expected-points table, remaining-margin spread, and how much the current drive's expected points moves the margin."""
    pl = plays[plays["down"].notna() & plays["ep"].notna() & plays["yardline_100"].notna()]
    b = pd.DataFrame({"k": [ep_bucket(d, y) for d, y in zip(pl["down"], pl["yardline_100"])], "ep": pl["ep"].to_numpy()})
    params.ep_table = b.groupby("k")["ep"].mean().to_dict()


def ep_of(params: Params, down, yl) -> float:
    return float(params.ep_table.get(ep_bucket(down, yl), 0.0))


def margin_samples(params: Params, margin_now: float, rho: float, pre_margin: float, ep_poss: float, M: int, rng) -> np.ndarray:
    """Final home margin draws: margin now, plus the pregame remaining edge, plus the drive in progress, with Brownian spread in the time left."""
    mean = margin_now + pre_margin * rho + params.gamma_ep * ep_poss
    return mean + rng.normal(0.0, params.sigma_m * np.sqrt(max(rho, 1e-6)), M)
