"""Tails: do margins land outside the priced range more often in high-uncertainty games? Rule in docs/TAILS_PREREG.md and docs/tails_rule.json."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RULE = ROOT / "docs" / "tails_rule.json"
OUT = ROOT / "data" / "tails"
RELOCATED = {"STL": "LA", "OAK": "LV", "SD": "LAC"}
HFA, SIGMA0 = 1.8, 13.5
PRIOR_N, PRIOR_MEAN = 300, 0.02
GRID_K, GRID_CARRY = (0.03, 0.06, 0.09), (0.6, 0.75, 0.9)
SELECT_SEASONS = (2006, 2012)


def rule() -> dict:
    return json.loads(RULE.read_text())


def load_games() -> pd.DataFrame:
    g = pd.read_csv(RAW / "games.csv")
    g = g[(g["game_type"] == "REG")].copy()
    for c in ("home_team", "away_team"):
        g[c] = g[c].replace(RELOCATED)
    g["date"] = pd.to_datetime(g["gameday"])
    return g.sort_values(["date", "game_id"]).reset_index(drop=True)


def inventory() -> dict:
    g = load_games()
    p = g[g["result"].notna() & g["spread_line"].notna()]
    sbr = pd.read_parquet(RAW / "market" / "sbr_lines.parquet")
    arch = RAW / "archive"

    def snaps(d):
        fs = sorted((arch / d).glob("*"))
        stamps = []
        for f in fs:
            try:
                stamps.append(json.loads(f.read_text()).get("archived_at"))
            except Exception:
                pass
        return {"files": len(fs), "first": min([s for s in stamps if s], default=None), "last": max([s for s in stamps if s], default=None)}

    return {"games_with_result_and_closing_line": int(len(p)), "seasons": [int(p["season"].min()), int(p["season"].max())],
            "games_with_moneyline": int(p["home_moneyline"].notna().sum()), "games_with_starting_qb": int(p["home_qb_id"].notna().sum()),
            "sbr_open_and_close_games": int(len(sbr)), "sbr_seasons": [int(sbr["season"].min()), int(sbr["season"].max())],
            "kalshi_snapshots": {d: snaps(d) for d in ("kalshi", "props_kalshi", "props_kalshi_books", "dense_books")},
            "note": "Kalshi history starts 2026-10-30. Spread and total ladder snapshots number a handful, so Kalshi cannot supply per-game tail prices; the closing line is the priced benchmark."}


def reconcile() -> dict:
    g = load_games()
    g = g[g["result"].notna() & g["spread_line"].notna()]
    e = g["result"] - g["spread_line"]
    out = {"all": {"games": int(len(e)), "sd_margin_minus_line": float(e.std()), "mean": float(e.mean())}}
    for name, (a, b) in {"1999_2005": (1999, 2005), "2006_2019": (2006, 2019), "2020_2026": (2020, 2026)}.items():
        m = g["season"].between(a, b)
        out[name] = {"games": int(m.sum()), "sd_margin_minus_line": float(e[m].std())}
    r = g["result"].abs()
    out["key_numbers_share_of_games_pct"] = {str(k): round(float((r == k).mean() * 100), 2) for k in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14)}
    out["published_reference"] = "Stern (1991) puts the standard deviation of NFL margin around the point spread near 13.9."
    return out


def qb_table(g: pd.DataFrame) -> pd.DataFrame:
    """Per game, each starter's shrunk prior value (EPA per dropback before the game) and prior dropbacks. Starters come from games.csv."""
    frames = []
    for s in sorted(g["season"].unique()):
        f = RAW / f"play_by_play_{s}.parquet"
        if not f.exists():
            f = RAW / "history" / f"play_by_play_{s}.parquet"
        p = pd.read_parquet(f, columns=["game_id", "qb_dropback", "epa", "passer_player_id"])
        p = p[(p["qb_dropback"] == 1) & p["passer_player_id"].notna() & p["epa"].notna()]
        frames.append(p.groupby(["game_id", "passer_player_id"]).agg(n=("epa", "size"), s=("epa", "sum")).reset_index())
    pb = pd.concat(frames).merge(g[["game_id", "date"]], on="game_id").sort_values("date")
    pb["cn"] = pb.groupby("passer_player_id")["n"].cumsum() - pb["n"]
    pb["cs"] = pb.groupby("passer_player_id")["s"].cumsum() - pb["s"]
    pb["val"] = (pb["cs"] + PRIOR_N * PRIOR_MEAN) / (pb["cn"] + PRIOR_N)
    return pb.set_index(["game_id", "passer_player_id"])[["val", "cn"]]


def _qb_cols(g: pd.DataFrame, qb: pd.DataFrame) -> pd.DataFrame:
    for side in ("home", "away"):
        idx = list(zip(g["game_id"], g[f"{side}_qb_id"]))
        j = qb.reindex(idx)
        g[f"{side}_qb_val"] = np.where(j["val"].isna(), PRIOR_MEAN, j["val"])
        g[f"{side}_qb_n"] = np.where(j["cn"].isna(), 0, j["cn"])
    last = {}
    ch_h, ch_a = [], []
    for r in g.itertuples():
        for side, lst in (("home", ch_h), ("away", ch_a)):
            t, q = getattr(r, f"{side}_team"), getattr(r, f"{side}_qb_id")
            lst.append(bool(t in last and last[t] != q))
        last[r.home_team], last[r.away_team] = r.home_qb_id, r.away_qb_id
    g["qb_changed"] = np.array(ch_h) | np.array(ch_a)
    return g


def elo_margins(g: pd.DataFrame, k: float, carry: float) -> np.ndarray:
    """Pre-game expected margin (home minus away) in points from a walk-forward rating."""
    r, out, season = {}, np.zeros(len(g)), None
    for i, row in enumerate(g.itertuples()):
        if row.season != season:
            r = {t: carry * v for t, v in r.items()}
            season = row.season
        m = r.get(row.home_team, 0.0) - r.get(row.away_team, 0.0) + HFA
        out[i] = m
        if not np.isnan(row.result):
            d = k * (row.result - m)
            r[row.home_team] = r.get(row.home_team, 0.0) + d
            r[row.away_team] = r.get(row.away_team, 0.0) - d
    return out


def build() -> tuple[pd.DataFrame, dict]:
    """Games from 1999 with walk-forward Elo, Elo plus starting-QB term, and the pre-game uncertainty inputs. Settings fixed by the rule or chosen on 2006-2012 margin error only."""
    R = rule()
    g = load_games()
    g = g[g["result"].notna() & g["spread_line"].notna() | (g["season"] == R["upcoming_season"])].reset_index(drop=True)
    g = _qb_cols(g, qb_table(g[g["result"].notna()]))
    sel = g["season"].between(*SELECT_SEASONS) & g["result"].notna()
    best = None
    for k in GRID_K:
        for c in GRID_CARRY:
            m = elo_margins(g, k, c)
            mae = float(np.abs(g.loc[sel, "result"] - m[sel]).mean())
            if best is None or mae < best[0]:
                best = (mae, k, c)
    _, k, c = best
    g["elo"] = elo_margins(g, k, c)
    g["dqb"] = g["home_qb_val"] - g["away_qb_val"]
    disc = g["season"].between(*R["discovery"]) & g["result"].notna()
    x, y = g.loc[disc, "dqb"].to_numpy(), (g.loc[disc, "result"] - g.loc[disc, "elo"]).to_numpy()
    beta = float((x * y).sum() / (x * x).sum())
    g["elo_qb"] = g["elo"] + beta * g["dqb"]
    g["gap"] = (g["elo_qb"] - g["spread_line"]).abs()
    g["e"] = g["result"] - g["spread_line"]
    q80 = float(g.loc[disc, "gap"].quantile(R["gap_quantile"]))
    g["u_qb"] = g["qb_changed"] | (np.minimum(g["home_qb_n"], g["away_qb_n"]) < R["new_qb_dropbacks"])
    g["u_gap"] = g["gap"] >= q80
    g["u_any"] = g["u_qb"] | g["u_gap"]
    return g, {"elo_k": k, "elo_carry": c, "qb_beta_points_per_epa": beta, "gap_threshold": q80}


def power(g: pd.DataFrame, fitted: dict) -> dict:
    """Counts only: how big a tail-rate gap each flag could detect on the confirmation seasons. Uses no margins in flagged games beyond the reference spread."""
    R = rule()
    disc = g["season"].between(*R["discovery"]) & g["result"].notna()
    conf = g["season"].between(*R["confirmation"]) & g["result"].notna()
    ref = g[disc & ~g["u_any"]]
    sigma = float(ref["e"].std())
    za = stats.norm.ppf(1 - 0.05 / R["n_tests"])
    zb = stats.norm.ppf(0.8)
    out = {"reference_sigma": sigma, "alpha_per_test": 0.05 / R["n_tests"], "flags": {}}
    for f in ("u_qb", "u_gap", "u_any"):
        for T in R["tail_thresholds"]:
            p0 = expected_tail(sigma, T)
            n = int(g.loc[conf, f].sum())
            d = float((za + zb) * np.sqrt(p0 * (1 - p0) / max(n, 1)))
            out["flags"][f"{f}_{T}"] = {"flagged_discovery": int(g.loc[disc, f].sum()), "flagged_confirmation": n, "expected_rate": p0, "smallest_detectable_rate_increase": d, "relative": d / p0}
    return out


def expected_tail(sigma: float, T: float) -> float:
    return float(2 * (1 - stats.norm.cdf((T - 0.5) / sigma)))


def freeze_rule_hash() -> str:
    return hashlib.sha256(RULE.read_bytes()).hexdigest()
