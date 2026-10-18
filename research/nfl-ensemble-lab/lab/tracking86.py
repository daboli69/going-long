"""Phase 8.6: Big Data Bowl 2026 tracking (2023) - arrival separation edge, NGS proxy check.
Exactly as pre-registered in docs/PHASE8_6_PREREGISTRATION.md. Lab-only; competition data never leaves data/raw/kaggle/."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from scipy import stats

from .config import ARTIFACTS_DIR, RAW_DIR
from .ingest import normalize_team
from .upsets84 import _logit, _test

OUT = ARTIFACTS_DIR / "phase86"
BDB = RAW_DIR / "kaggle" / "nfl-big-data-bowl-2026-analytics"
MIN_PRIOR = 3


def provenance() -> dict:
    files = []
    for d in (BDB, RAW_DIR / "kaggle" / "nfl-big-data-bowl-2026-prediction"):
        for f in sorted(d.glob("*.csv")):
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 22), b""):
                    h.update(chunk)
            files.append({"file": f"{d.name}/{f.name}", "bytes": f.stat().st_size, "sha256": h.hexdigest()})
    return {"source": "Kaggle NFL Big Data Bowl 2026 (analytics + prediction), manual download by Travis",
            "terms": "competition rules: local research only, no redistribution", "files": files}


def arrival_separation(inp: pd.DataFrame, out: pd.DataFrame) -> pd.DataFrame:
    """One row per play: distance from the targeted receiver to the nearest tracked defender at the last output frame."""
    roles = inp.drop_duplicates(["game_id", "play_id", "nfl_id"])[["game_id", "play_id", "nfl_id", "player_side", "player_role"]]
    last = out[out["frame_id"] == out.groupby(["game_id", "play_id"])["frame_id"].transform("max")]
    last = last.merge(roles, on=["game_id", "play_id", "nfl_id"], how="left")
    tr = last[last["player_role"] == "Targeted Receiver"][["game_id", "play_id", "x", "y"]]
    de = last[last["player_side"] == "Defense"][["game_id", "play_id", "x", "y"]]
    j = tr.merge(de, on=["game_id", "play_id"], suffixes=("_r", "_d"))
    j["dist"] = np.hypot(j["x_r"] - j["x_d"], j["y_r"] - j["y_d"])
    return j.groupby(["game_id", "play_id"], as_index=False)["dist"].min().rename(columns={"dist": "sep"})


def plays() -> pd.DataFrame:
    sup = pd.read_csv(BDB / "supplementary_data.csv")
    sup = sup[(sup["season"] == 2023) & (sup["play_nullified_by_penalty"] != "Y")]
    seps = []
    for w in range(1, 19):
        inp = pd.read_csv(BDB / f"input_2023_w{w:02d}.csv", usecols=["game_id", "play_id", "nfl_id", "player_side", "player_role"])
        out = pd.read_csv(BDB / f"output_2023_w{w:02d}.csv")
        seps.append(arrival_separation(inp, out))
    p = sup.merge(pd.concat(seps), on=["game_id", "play_id"])
    p["off"] = p["possession_team"].map(normalize_team)
    p["def"] = p["defensive_team"].map(normalize_team)
    return p


def team_edges(p: pd.DataFrame) -> pd.DataFrame:
    """As-of E = OffSep - DefSep over strictly earlier 2023 weeks (>= MIN_PRIOR games), per (team, week)."""
    off = p.groupby(["week", "game_id", "off"])["sep"].mean().rename("off_sep").reset_index().rename(columns={"off": "team"})
    de = p.groupby(["week", "game_id", "def"])["sep"].mean().rename("def_sep").reset_index().rename(columns={"def": "team"})
    tg = off.merge(de, on=["week", "game_id", "team"], how="outer").sort_values("week")
    rows = []
    for t, d in tg.groupby("team"):
        for w in range(1, 19):
            prior = d[d["week"] < w]
            e = (prior["off_sep"].mean() - prior["def_sep"].mean()) if len(prior) >= MIN_PRIOR else np.nan
            rows.append({"team": t, "week": w, "E": e, "prior_games": len(prior)})
    return pd.DataFrame(rows), tg


def game_frame(edges: pd.DataFrame) -> pd.DataFrame:
    from .market81 import american_to_prob, novig
    from .specialists.baseline import load_oof
    g = pd.read_csv(RAW_DIR / "games.csv")
    g = g[(g["season"] == 2023) & (g["game_type"] == "REG") & g["home_score"].notna() & (g["home_score"] != g["away_score"])].copy()
    g["home_n"], g["away_n"] = g["home_team"].map(normalize_team), g["away_team"].map(normalize_team)
    e = edges.set_index(["team", "week"])["E"]
    g["E_home"] = e.reindex(pd.MultiIndex.from_arrays([g["home_n"], g["week"]])).to_numpy()
    g["E_away"] = e.reindex(pd.MultiIndex.from_arrays([g["away_n"], g["week"]])).to_numpy()
    g = g.merge(load_oof()[["game_id", "p_weighted_average"]], on="game_id", how="left")
    fh = (g["p_weighted_average"] >= 0.5).to_numpy()
    hw = (g["home_score"] > g["away_score"]).to_numpy()
    g["p_fav"] = np.where(fh, g["p_weighted_average"], 1 - g["p_weighted_average"])
    g["fav_won"] = np.where(fh, hw, ~hw).astype(float)
    g["angle"] = np.where(fh, g["E_away"] - g["E_home"], g["E_home"] - g["E_away"])
    pc = np.asarray(novig(american_to_prob(pd.to_numeric(g["home_moneyline"], errors="coerce")),
                          american_to_prob(pd.to_numeric(g["away_moneyline"], errors="coerce"))), float)
    g["p_close_fav"] = np.where(fh, pc, 1 - pc)                 # close for the CHAMPION favourite (T2)
    return g.dropna(subset=["angle", "p_weighted_average"])


def ngs_proxy(tg: pd.DataFrame) -> dict:
    n = pd.read_parquet(RAW_DIR / "ngs_receiving.parquet")
    n = n[(n["season"] == 2023) & (n["season_type"] == "REG") & (n["week"] > 0)].dropna(subset=["avg_separation", "targets"])
    n["team"] = n["team_abbr"].map(normalize_team)
    n["w"] = n["avg_separation"] * n["targets"]
    tw = n.groupby(["team", "week"]).agg(w=("w", "sum"), t=("targets", "sum")).reset_index()
    tw["ngs_sep"] = tw["w"] / tw["t"]
    j = tg.dropna(subset=["off_sep"]).merge(tw, on=["team", "week"])
    r, p = stats.pearsonr(j["off_sep"], j["ngs_sep"]) if len(j) > 10 else (np.nan, np.nan)
    return {"team_weeks": int(len(j)), "pearson_r": float(r), "p": float(p), "adequate_proxy": bool(r >= 0.5)}


def coverage_profile(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    p["man"] = p["team_coverage_man_zone"].astype(str).str.upper().str.contains("MAN")
    d = p.groupby("def").agg(plays=("sep", "size"), man_rate=("man", "mean"), sep_allowed=("sep", "mean")).rename_axis("team")
    o = p.groupby(["off", "man"])["sep"].mean().unstack()
    o.columns = ["off_sep_vs_zone" if not c else "off_sep_vs_man" for c in o.columns]
    return d.join(o.rename_axis("team")).reset_index().round(3)


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "provenance.json").write_text(json.dumps(provenance(), indent=2))
    p = plays()
    edges, tg = team_edges(p)
    g = game_frame(edges)
    z = ((g["angle"] - g["angle"].mean()) / g["angle"].std()).to_numpy()
    t1 = _test(g["fav_won"].to_numpy(), _logit(g["p_fav"]), z, g["week"].to_numpy() // 6, n_season_min=40)   # sign by 6-week thirds
    t1["passes"] = bool(t1["p_one_sided"] < 0.05 and t1["coef_per_sd"] < 0)
    g2 = g.dropna(subset=["p_close_fav"])
    z2 = ((g2["angle"] - g["angle"].mean()) / g["angle"].std()).to_numpy()
    t2 = _test(g2["fav_won"].to_numpy(), _logit(g2["p_close_fav"]), z2, g2["week"].to_numpy() // 6, n_season_min=40)
    res = {"plays_with_separation": int(len(p)), "median_separation_yd": float(p["sep"].median()),
           "games_tested": int(len(g)), "T1_beyond_champion": t1, "T2_beyond_close": t2, "P1_ngs_proxy": ngs_proxy(tg)}
    (OUT / "results.json").write_text(json.dumps(res, indent=2, default=str))
    coverage_profile(p).to_csv(OUT / "coverage_profile.csv", index=False)
    edges.to_csv(OUT / "team_edges.csv", index=False)
    return res


def load() -> dict:
    out = {}
    if (OUT / "results.json").exists():
        out["results"] = json.loads((OUT / "results.json").read_text())
    if (OUT / "coverage_profile.csv").exists():
        out["coverage"] = pd.read_csv(OUT / "coverage_profile.csv")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
