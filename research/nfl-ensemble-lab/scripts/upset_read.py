"""Development read for docs/UPSET_PREREG.md. Signals use only information known before kickoff.

Implementation choices fixed before the first run, where the registration left room:
- Regular-season games only, seasons 2018 to 2025, closing spread of 1 to 7 points inclusive.
- S1 uses the feature store's opponent-adjusted ratings: rating_off_epa minus rating_def_epa.
- S2 is early-down (first and second down, run or pass) success rate, offense minus defense allowed,
  over the team's earlier games of the same season. Week 1 has no value and the signal is false.
- S3 regresses season-to-date points per game differential on std_epa_pp minus std_d_epa_pp using
  earlier seasons only (2015 onward), and flags a favourite whose residual exceeds one residual SD.
- S4 compares the projected quarterback id with the team's projected id in each of its previous three games.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab.market_gate import HOLD_RANGE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "cache" / "feature_store.parquet"
OUT = ROOT / "reports" / "upset" / "DEV_READ.json"
SEASONS = range(2018, 2026)
SEED = 20261111


def implied(odds: pd.Series) -> pd.Series:
    return pd.Series(np.where(odds < 0, -odds / (-odds + 100.0), 100.0 / (odds + 100.0)), index=odds.index)


def early_down_success() -> pd.DataFrame:
    """Per team and game: early-down success rate differential over earlier games of the same season."""
    rows = []
    for season in range(2015, 2026):
        p = pd.read_parquet(ROOT / "data" / "raw" / f"play_by_play_{season}.parquet",
                            columns=["game_id", "season_type", "week", "posteam", "defteam", "down", "pass", "rush", "success"])
        p = p[(p.season_type == "REG") & p.down.isin([1, 2]) & ((p["pass"] == 1) | (p.rush == 1)) & p.success.notna()]
        o = p.groupby(["week", "posteam"]).success.agg(["sum", "count"]).reset_index().rename(columns={"posteam": "team", "sum": "os", "count": "on"})
        d = p.groupby(["week", "defteam"]).success.agg(["sum", "count"]).reset_index().rename(columns={"defteam": "team", "sum": "ds", "count": "dn"})
        t = o.merge(d, on=["week", "team"]).sort_values(["team", "week"])
        c = t.groupby("team")[["os", "on", "ds", "dn"]].cumsum()
        t["sr_diff_through"] = c.os / c.on - c.ds / c.dn
        t["season"] = season
        rows.append(t[["season", "week", "team", "sr_diff_through"]])
    return pd.concat(rows)


def prior_value(table: pd.DataFrame, season: int, week: int, team: str) -> float:
    x = table[(table.season == season) & (table.team == team) & (table.week < week)]
    return float(x.sr_diff_through.iloc[-1]) if len(x) else np.nan


def build() -> pd.DataFrame:
    g = pd.read_parquet(STORE)
    g = g[(g.week <= 18) & g.completed.astype(bool) & g.spread_line.notna()].copy()
    _, _, g["away"], g["home"] = zip(*g.game_id.str.split("_"))
    g = g.sort_values(["season", "week", "game_id"]).reset_index(drop=True)

    # team-game long table for season-to-date points differential and quarterback history
    long = pd.concat([
        g.assign(team=g.home, pts=g.home_score - g.away_score, qb=g.home_qb_projected_id, epa=g.home_std_epa_pp - g.home_std_d_epa_pp, side="home"),
        g.assign(team=g.away, pts=g.away_score - g.home_score, qb=g.away_qb_projected_id, epa=g.away_std_epa_pp - g.away_std_d_epa_pp, side="away"),
    ])[["game_id", "season", "week", "team", "pts", "qb", "epa", "side"]].sort_values(["team", "season", "week"])
    grp = long.groupby(["team", "season"])
    long["pd_pg"] = grp.pts.transform(lambda s: s.shift().expanding().mean())
    by_team = long.groupby("team")
    for k in (1, 2, 3):
        long[f"qb_prev{k}"] = by_team.qb.shift(k)
    long["qb_same3"] = (long.qb.notna() & (long.qb == long.qb_prev1) & (long.qb == long.qb_prev2) & (long.qb == long.qb_prev3))

    # S3 residual, coefficients from earlier seasons only
    long["flatter"] = False
    for season in SEASONS:
        fit = long[(long.season < season) & long.pd_pg.notna() & long.epa.notna()]
        b, a = np.polyfit(fit.epa, fit.pd_pg, 1)
        sd = float(np.std(fit.pd_pg - (a + b * fit.epa)))
        m = long.season == season
        long.loc[m, "flatter"] = (long.loc[m, "pd_pg"] - (a + b * long.loc[m, "epa"])) > sd

    sr = early_down_success()
    key = long.set_index(["game_id", "side"])
    g = g[g.season.isin(SEASONS) & g.spread_line.abs().between(1, 7)].copy()
    ph, pa = implied(g.home_moneyline), implied(g.away_moneyline)
    g["hold"] = ph + pa - 1
    g = g[g.hold.between(*HOLD_RANGE)].copy()
    g["dog_home"] = g.spread_line < 0  # positive spread_line means the home team is favoured
    out = []
    for r in g.itertuples():
        dog, fav = ("home", "away") if r.dog_home else ("away", "home")
        net = {s: getattr(r, f"{s}_rating_off_epa") - getattr(r, f"{s}_rating_def_epa") for s in ("home", "away")}
        srd = {s: prior_value(sr, r.season, r.week, getattr(r, s)) for s in ("home", "away")}
        s1 = bool(net[dog] > net[fav])
        s2 = bool(srd[dog] > srd[fav]) if not (np.isnan(srd[dog]) or np.isnan(srd[fav])) else False
        s3 = bool(key.loc[(r.game_id, fav), "flatter"])
        s4 = bool(key.loc[(r.game_id, dog), "qb_same3"] and not key.loc[(r.game_id, fav), "qb_same3"])
        p_home = r.market_p_home_novig
        p_dog = p_home if r.dog_home else 1 - p_home
        margin_dog = r.margin if r.dog_home else -r.margin
        win = 1.0 if margin_dog > 0 else 0.5 if margin_dog == 0 else 0.0
        ats = margin_dog + abs(r.spread_line)
        out.append(dict(game_id=r.game_id, season=r.season, s1=s1, s2=s2, s3=s3, s4=s4, n_signals=s1 + s2 + s3 + s4,
                        p_dog=p_dog, win=win, cover=1.0 if ats > 0 else 0.5 if ats == 0 else 0.0))
    return pd.DataFrame(out)


def summary(x: pd.DataFrame) -> dict:
    d = (x.win - x.p_dog).to_numpy()
    rng = np.random.default_rng(SEED)
    boot = rng.choice(d, (10000, len(d))).mean(axis=1) if len(d) else np.array([np.nan])
    return {"n": int(len(x)), "win_rate": float(x.win.mean()), "market_p": float(x.p_dog.mean()), "mean_excess": float(d.mean()),
            "ci95": [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))], "share_boot_above_0": float((boot > 0).mean()),
            "cover_rate": float(x.cover.mean())}


def main() -> None:
    x = build()
    flag = x.n_signals >= 2
    res = {"registration": "docs/UPSET_PREREG.md", "seasons": [SEASONS[0], SEASONS[-1]], "read": "development only; cannot confirm",
           "flagged": summary(x[flag]), "unflagged": summary(x[~flag]), "all_underdogs_1_to_7": summary(x),
           "signal_rates": {s: float(x[s].mean()) for s in ("s1", "s2", "s3", "s4")},
           "flagged_by_season": {int(k): {"n": int(len(v)), "mean_excess": float((v.win - v.p_dog).mean())} for k, v in x[flag].groupby("season")}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
