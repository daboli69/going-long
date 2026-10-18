"""Phase 8.7: multi-season separation edge, NGS avg_separation as the weekly stand-in for BDB arrival separation.
Exactly as pre-registered in docs/PHASE8_7_PREREGISTRATION.md. Lab-only research; one historical look."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR, RAW_DIR
from .ingest import normalize_team
from .upsets84 import _logit, _test

OUT = ARTIFACTS_DIR / "phase87"
MIN_PRIOR = 3
DISCOVERY = (2018, 2019, 2020)
DISCOVERY_CLOSE = (2016, 2017, 2018, 2019, 2020)
CONFIRMATION = (2021, 2022, 2024, 2025)                          # 2023 examined in Phase 8.6; 2026 in progress


def team_week_sep(n: pd.DataFrame) -> pd.DataFrame:
    """Target-weighted NGS avg_separation per (season, week, team) of the offense."""
    n = n[(n["season_type"] == "REG") & (n["week"] > 0)].dropna(subset=["avg_separation", "targets"])
    n = n[n["targets"] > 0].assign(team=lambda d: d["team_abbr"].map(normalize_team))
    n = n.assign(w=n["avg_separation"] * n["targets"])
    tw = n.groupby(["season", "week", "team"]).agg(w=("w", "sum"), t=("targets", "sum")).reset_index()
    return tw.assign(off_sep=tw["w"] / tw["t"])[["season", "week", "team", "off_sep"]]


def games(g: pd.DataFrame) -> pd.DataFrame:
    g = g[(g["game_type"] == "REG") & g["home_score"].notna() & (g["home_score"] != g["away_score"])].copy()
    g["home_n"], g["away_n"] = g["home_team"].map(normalize_team), g["away_team"].map(normalize_team)
    return g


def team_games(g: pd.DataFrame, tw: pd.DataFrame) -> pd.DataFrame:
    """One row per (team, game): OffSep = own offense; DefSep = the opponent's OffSep in the same game."""
    s = tw.set_index(["season", "week", "team"])["off_sep"]
    look = lambda t: s.reindex(pd.MultiIndex.from_arrays([g["season"], g["week"], t])).to_numpy()
    sh, sa = look(g["home_n"]), look(g["away_n"])
    h = pd.DataFrame({"season": g["season"].to_numpy(), "week": g["week"].to_numpy(), "team": g["home_n"].to_numpy(), "off_sep": sh, "def_sep": sa})
    a = pd.DataFrame({"season": g["season"].to_numpy(), "week": g["week"].to_numpy(), "team": g["away_n"].to_numpy(), "off_sep": sa, "def_sep": sh})
    return pd.concat([h, a], ignore_index=True)


def team_edges(tg: pd.DataFrame) -> pd.DataFrame:
    """As-of E per (season, team, week): means over strictly earlier weeks of the same season, each needing >= MIN_PRIOR values."""
    rows = []
    for (season, t), d in tg.groupby(["season", "team"]):
        for w in range(1, int(d["week"].max()) + 2):
            prior = d[d["week"] < w]
            o, de = prior["off_sep"].dropna(), prior["def_sep"].dropna()
            e = o.mean() - de.mean() if len(o) >= MIN_PRIOR and len(de) >= MIN_PRIOR else np.nan
            rows.append({"season": season, "team": t, "week": w, "E": e, "prior_off": len(o), "prior_def": len(de)})
    return pd.DataFrame(rows)


def game_frame(g: pd.DataFrame, edges: pd.DataFrame, oof: pd.DataFrame) -> pd.DataFrame:
    from .market81 import american_to_prob, novig
    e = edges.set_index(["season", "team", "week"])["E"]
    look = lambda t: e.reindex(pd.MultiIndex.from_arrays([g["season"], t, g["week"]])).to_numpy()
    g = g.assign(E_home=look(g["home_n"]), E_away=look(g["away_n"]))
    g = g.merge(oof[["game_id", "p_weighted_average"]], on="game_id", how="left")
    hw = (g["home_score"] > g["away_score"]).to_numpy()
    pc = np.asarray(novig(american_to_prob(pd.to_numeric(g["home_moneyline"], errors="coerce")),
                          american_to_prob(pd.to_numeric(g["away_moneyline"], errors="coerce"))), float)
    fh = (g["p_weighted_average"] >= 0.5).to_numpy()              # champion favourite (primary)
    g["p_fav"] = np.where(fh, g["p_weighted_average"], 1 - g["p_weighted_average"])
    g["fav_won"] = np.where(fh, hw, ~hw).astype(float)
    g["angle"] = np.where(fh, g["E_away"] - g["E_home"], g["E_home"] - g["E_away"])
    mh = pc >= 0.5                                                # market favourite (secondary)
    g["p_close_fav"] = np.where(mh, pc, 1 - pc)
    g["mkt_fav_won"] = np.where(mh, hw, ~hw).astype(float)
    g["mkt_angle"] = np.where(mh, g["E_away"] - g["E_home"], g["E_home"] - g["E_away"])
    g.loc[g["p_weighted_average"].isna(), ["p_fav", "fav_won", "angle"]] = np.nan
    g.loc[np.isnan(pc), ["p_close_fav", "mkt_fav_won", "mkt_angle"]] = np.nan
    return g


def _run_test(d: pd.DataFrame, y: str, base: str, a: str, scale: tuple[float, float]) -> dict:
    d = d.dropna(subset=[y, base, a])
    z = ((d[a] - scale[0]) / scale[1]).to_numpy()
    t = _test(d[y].to_numpy(), _logit(d[base]), z, d["season"].to_numpy(), n_season_min=40)
    return t


def _decide(t: dict, n_seasons: int) -> dict:
    t["passes"] = bool(t["p_one_sided"] < 0.05 and t["coef_per_sd"] < 0 and t["seasons_with_predeclared_sign"] * 2 >= n_seasons)
    return t


def quintiles(d: pd.DataFrame) -> pd.DataFrame:
    d = d.dropna(subset=["angle", "p_fav", "fav_won"])
    q = pd.qcut(d["angle"], 5, labels=["favours fav most", "fav", "mid", "dog", "favours dog most"])
    return d.assign(q=q).groupby("q", observed=True).apply(lambda x: pd.Series({
        "games": len(x), "implied_upset_rate": 1 - x["p_fav"].mean(), "observed_upset_rate": 1 - x["fav_won"].mean()}),
        include_groups=False).reset_index()


def run() -> dict:
    from .specialists.baseline import load_oof
    OUT.mkdir(parents=True, exist_ok=True)
    tw = team_week_sep(pd.read_parquet(RAW_DIR / "ngs_receiving.parquet"))
    g = games(pd.read_csv(RAW_DIR / "games.csv"))
    g = g[g["season"].isin(DISCOVERY_CLOSE + CONFIRMATION)]
    tg = team_games(g, tw)
    edges = team_edges(tg)
    gf = game_frame(g, edges, load_oof())
    disc, conf = gf[gf["season"].isin(DISCOVERY)], gf[gf["season"].isin(CONFIRMATION)]
    dd = disc.dropna(subset=["angle", "p_fav"])
    scale = (float(dd["angle"].mean()), float(dd["angle"].std()))
    dc = gf[gf["season"].isin(DISCOVERY_CLOSE)].dropna(subset=["mkt_angle", "p_close_fav"])
    scale_c = (float(dc["mkt_angle"].mean()), float(dc["mkt_angle"].std()))
    res = {
        "angle_scale_discovery": {"mean": scale[0], "sd": scale[1]},
        "mkt_angle_scale_discovery": {"mean": scale_c[0], "sd": scale_c[1]},
        "coverage": gf.groupby("season").agg(games=("game_id", "size"), with_angle=("angle", lambda s: int(s.notna().sum())),
                                             with_mkt_angle=("mkt_angle", lambda s: int(s.notna().sum()))).reset_index().to_dict("records"),
        "primary_discovery": _run_test(disc, "fav_won", "p_fav", "angle", scale),
        "primary_confirmation": _decide(_run_test(conf, "fav_won", "p_fav", "angle", scale), len(CONFIRMATION)),
        "secondary_close_discovery": _run_test(gf[gf["season"].isin(DISCOVERY_CLOSE)], "mkt_fav_won", "p_close_fav", "mkt_angle", scale_c),
        "secondary_close_confirmation": _decide(_run_test(conf, "mkt_fav_won", "p_close_fav", "mkt_angle", scale_c), len(CONFIRMATION)),
    }
    res["passes"] = res["primary_confirmation"]["passes"]
    (OUT / "results.json").write_text(json.dumps(res, indent=2, default=str))
    quintiles(conf).to_csv(OUT / "confirmation_quintiles.csv", index=False)
    edges.to_csv(OUT / "team_edges.csv", index=False)
    return res


def load() -> dict:
    out = {}
    if (OUT / "results.json").exists():
        out["results"] = json.loads((OUT / "results.json").read_text())
    if (OUT / "confirmation_quintiles.csv").exists():
        out["quintiles"] = pd.read_csv(OUT / "confirmation_quintiles.csv")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
