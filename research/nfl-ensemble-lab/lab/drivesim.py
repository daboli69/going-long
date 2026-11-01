"""Independent drive-level simulation of a game, built from each team's own drive record. No betting line goes in.

For every team-game the lab keeps, from games before it only: drives per game, touchdowns and field goals per drive on offense, and
what the opposing defense allows per drive (lab/phase81 drive rates). A game plays out drive by drive: each offense drive ends in a
touchdown (7 points), a field goal (3) or nothing, with probabilities from the offense's rate and the defense's rate. The home edge
and a scoring scale were fitted on 2022-2024 games (scripts/drivesim_check.py) and the result is tested against the market on 2025 and
2026 games before it is allowed to move any number.
"""
from __future__ import annotations

import json
import zlib

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from .config import CACHE_DIR

RATES = CACHE_DIR / "phase81_drive_rates.parquet"
PARAMS_PATH = CACHE_DIR / "drivesim_rule.json"
DEFAULTS = {"edge": 0.04, "scale": 1.0}


def rates() -> pd.DataFrame:
    """Per (game_id, team): own and allowed drive rates, as known before the game."""
    if not RATES.exists():
        return pd.DataFrame()

    def build():
        r = pd.read_parquet(RATES)
        out = r[["game_id", "team"]].copy()
        for new, old in (("drives", "drives"), ("td", "td_rate"), ("fg", "fg_rate"), ("def_drives", "def_drives"), ("def_td", "def_td_rate"), ("def_fg", "def_fg_rate")):
            out[new] = r[f"p8dr_blend_{old}"]
        return out.set_index(["game_id", "team"])
    return D._cached(("drive_rates",), D._mt(RATES), build)


def league_means(r: pd.DataFrame) -> dict:
    return {"td": float(r["td"].mean()), "fg": float(r["fg"].mean()), "drives": float(r["drives"].mean())}


def matchup(r: pd.DataFrame, gid: str, home: str, away: str, lg: dict | None = None) -> dict | None:
    """Drive counts and per-drive touchdown and field-goal chances for each side, or None if either team has no record."""
    if (gid, home) not in r.index or (gid, away) not in r.index:
        return None
    lg = lg or league_means(r)
    h, a = r.loc[(gid, home)], r.loc[(gid, away)]
    if h.isna().any() or a.isna().any():
        return None

    def side(off, de):
        return {"drives": float((off["drives"] + de["def_drives"]) / 2), "td": float(off["td"] + de["def_td"] - lg["td"]),
                "fg": float(off["fg"] + de["def_fg"] - lg["fg"])}
    return {"home": side(h, a), "away": side(a, h)}


def simulate(m: dict, n: int = 10_000, seed: int = 0, edge: float = DEFAULTS["edge"], scale: float = DEFAULTS["scale"]) -> tuple[np.ndarray, np.ndarray]:
    """Points for the home and away team in `n` simulated games."""
    rng = np.random.default_rng(seed)
    pts = []
    for side, sign in (("home", 1.0), ("away", -1.0)):
        s = m[side]
        drives = np.clip(np.rint(rng.normal(s["drives"], 1.2, n)), 7, 15).astype(int)
        p_td = np.clip(s["td"] * scale * (1 + sign * edge), 0.02, 0.6)
        p_fg = np.clip(s["fg"] * scale * (1 + sign * edge), 0.02, 0.35)
        u = rng.random((n, 15))
        live = np.arange(15)[None, :] < drives[:, None]
        td = ((u < p_td) & live).sum(1)
        fg = ((u >= p_td) & (u < p_td + p_fg) & live).sum(1)
        pts.append(7 * td + 3 * fg)
    return pts[0], pts[1]


def summarize(home_pts: np.ndarray, away_pts: np.ndarray) -> dict:
    m = home_pts - away_pts
    return {"p_home": float((m > 0).mean() + 0.5 * (m == 0).mean()), "margin": float(m.mean()), "total": float((home_pts + away_pts).mean()),
            "sd_m": float(m.std()), "sd_t": float((home_pts + away_pts).std()),
            "home": float(home_pts.mean()), "away": float(away_pts.mean())}


def load_params() -> dict:
    if PARAMS_PATH.exists():
        return json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    return {**DEFAULTS, "w_margin": 0.0, "w_total": 0.0, "w_win": 0.0}


def own_view(gid: str, home: str, away: str, n: int = 10_000) -> dict | None:
    """The drive simulation's own numbers for a game; None if the lab has no drive record for a team."""
    r = rates()
    if r.empty:
        return None
    m = matchup(r, gid, home, away)
    if m is None:
        return None
    par = load_params()
    h, a = simulate(m, n, zlib.crc32(gid.encode()), par["edge"], par["scale"])
    out = summarize(h, a)
    out["draws"] = (h, a)
    return out


def evidence() -> dict:
    """Aggregate results of the last scripts/drivesim_check.py run (no game rows), for the Simulated game tab."""
    path = PARAMS_PATH.parents[2] / "docs" / "drivesim_check.json"
    if not path.exists():
        return {}
    d = json.loads(path.read_text(encoding="utf-8"))
    return {"pick_accuracy": d.get("pick_accuracy", {}), "same_pick": d.get("same_pick"),
            "used": {k: v.get("used") for k, v in d.get("tests", {}).items()}}
