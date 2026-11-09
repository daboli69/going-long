"""Packers 45, Patriots 27: luck or defect? Stages: game, gate, run, rebuild. Rule: docs/GBNE_AUDIT_PREREG.md.

    .venv\\Scripts\\python.exe scripts\\gbne_audit.py game
    .venv\\Scripts\\python.exe scripts\\gbne_audit.py gate
    .venv\\Scripts\\python.exe scripts\\gbne_audit.py run
    .venv\\Scripts\\python.exe scripts\\gbne_audit.py rebuild     # reruns game, gate and run and compares output hashes

Raw inputs only: the saved nflverse play-by-play snapshot (data/raw/gbne), FTN charting, PFR pressure, timestamped injury snapshots, archived hashed freezes,
the stored walk-forward forecasts and the closing moneylines in games.csv.
"""
from __future__ import annotations

import glob
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab.archive10 import canonical  # noqa: E402
from lab.config import RAW_DIR  # noqa: E402
from lab.ingest import normalize_team  # noqa: E402

DOCS = ROOT / "docs"
SNAP = RAW_DIR / "gbne" / "pbp_2026_snapshot.parquet"
SNAP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.parquet"
GID = "2026_09_GB_NE"
SEED = 20261108
RUNS = 200
ALPHA = 0.05 / 3
ZCI = 2.3939   # two-sided 98.33% normal quantile
FORECASTS = {"F1": "p_xgb_deep_platt", "F2": "p_margin_platt", "F3": "p_win"}
PBP_COLS = ["game_id", "play_id", "season", "week", "season_type", "qtr", "time", "posteam", "defteam", "play_type", "down", "ydstogo", "yardline_100", "desc", "epa", "wpa", "success",
            "pass", "rush", "sack", "interception", "fumble", "fumble_lost", "fumbled_1_team", "air_yards", "yards_gained", "qb_hit", "pass_location",
            "touchdown", "penalty", "total_home_score", "total_away_score", "home_team", "away_team", "qb_dropback"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plays(seasons) -> pd.DataFrame:
    parts = []
    for s in seasons:
        f = SNAP if s == 2026 else RAW_DIR / f"play_by_play_{s}.parquet"
        parts.append(pd.read_parquet(f, columns=PBP_COLS))
    return pd.concat(parts, ignore_index=True)


def _ftn(seasons) -> pd.DataFrame:
    d = pd.concat([pd.read_parquet(RAW_DIR / f"ftn_{s}.parquet", columns=["nflverse_game_id", "nflverse_play_id", "is_interception_worthy", "is_catchable_ball", "n_pass_rushers", "is_throw_away"]) for s in seasons], ignore_index=True)
    return d.rename(columns={"nflverse_game_id": "game_id", "nflverse_play_id": "play_id"})


def league_rates(seasons=(2022, 2023, 2024, 2025)) -> dict:
    """Interception share of interception-worthy passes, share of fumbles the offense loses, and the points cost of each kind of turnover."""
    p = _plays(seasons)
    p = p[p["season_type"] == "REG"]
    f = _ftn(seasons)
    j = p.merge(f, on=["game_id", "play_id"], how="inner")
    iw = j[(j["pass"] == 1) & (j["is_interception_worthy"] == True)]  # noqa: E712
    fum = p[(p["fumble"] == 1) & p["fumbled_1_team"].notna()]
    own = fum[fum["fumbled_1_team"] == fum["posteam"]]
    ints = p[p["interception"] == 1]
    lost = p[p["fumble_lost"] == 1]
    db = p[p["qb_dropback"] == 1]
    return {"seasons": list(seasons), "int_per_dropback": float((db["interception"] == 1).mean()), "iw_passes": int(len(iw)), "iw_intercepted_share": float((iw["interception"] == 1).mean()),
            "offense_fumbles": int(len(own)), "fumble_lost_share": float((own["fumble_lost"] == 1).mean()),
            "int_points_cost": float(-ints["epa"].mean()), "fumble_lost_points_cost": float(-lost["epa"].mean()),
            "all_turnover_points_cost": float(-pd.concat([ints, lost])["epa"].mean())}


def game() -> dict:
    lr = league_rates()
    p = _plays([2026])
    g = p[p["game_id"] == GID].sort_values("play_id").copy()
    f = _ftn([2026])
    g = g.merge(f, on=["game_id", "play_id"], how="left")
    out = {"snapshot_sha256": sha(SNAP), "snapshot_url": SNAP_URL, "plays": int(len(g)), "league_rates": lr}
    fin = g.iloc[-1]
    out["final"] = {"NE": int(fin["total_home_score"]), "GB": int(fin["total_away_score"])}
    out["margin_gb"] = out["final"]["GB"] - out["final"]["NE"]
    # turnovers from the plays
    t = g[(g["interception"] == 1) | (g["fumble_lost"] == 1)]
    out["turnovers"] = [{"qtr": int(r.qtr), "clock": str(r.time), "offense": r.posteam, "yardline_100": float(r.yardline_100), "down": None if pd.isna(r.down) else int(r.down),
                         "kind": "interception" if r.interception == 1 else "fumble lost", "interception_worthy": None if pd.isna(r.is_interception_worthy) else bool(r.is_interception_worthy),
                         "qb_hit_or_sack": bool((r.qb_hit == 1) or (r.sack == 1)), "air_yards": None if pd.isna(r.air_yards) else float(r.air_yards),
                         "epa": round(float(r.epa), 2), "desc": str(r.desc)[:140]} for r in t.itertuples()]
    charted = bool(g["is_interception_worthy"].notna().any())
    out["charting_available_for_game"] = charted
    prior = p[(p["season"] == 2026) & (p["season_type"] == "REG") & (p["week"] <= 8)]
    pdb = prior[prior["qb_dropback"] == 1]
    K = 300.0

    def shrunk(num, n):
        return (num + K * lr["int_per_dropback"]) / (n + K)
    off_r = {t_: shrunk(float((pdb[pdb.posteam == t_]["interception"] == 1).sum()), float((pdb.posteam == t_).sum())) for t_ in ("NE", "GB")}
    def_r = {t_: shrunk(float((pdb[pdb.defteam == t_]["interception"] == 1).sum()), float((pdb.defteam == t_).sum())) for t_ in ("NE", "GB")}
    out["season_rates_through_week8"] = {"offense_int_per_dropback": {k: round(v, 4) for k, v in off_r.items()}, "defense_takeaway_per_dropback": {k: round(v, 4) for k, v in def_r.items()}}
    exp = {}
    for team, opp in (("NE", "GB"), ("GB", "NE")):
        o = g[g["posteam"] == team]
        dbk = int(o["qb_dropback"].sum())
        fum = o[(o["fumble"] == 1) & (o["fumbled_1_team"] == team)]
        actual_int, actual_fum_lost = int(o["interception"].sum()), int(o["fumble_lost"].sum())
        e_fum = len(fum) * lr["fumble_lost_share"]
        e = dbk * lr["int_per_dropback"] + e_fum
        e_sens = dbk * (off_r[team] + def_r[opp]) / 2 + e_fum
        row = {"dropbacks": dbk, "interceptions": actual_int, "fumbles": int(len(fum)), "fumbles_lost": actual_fum_lost, "actual_turnovers": actual_int + actual_fum_lost,
               "expected_turnovers": round(e, 2), "luck_turnovers": round(actual_int + actual_fum_lost - e, 2),
               "expected_turnovers_sensitivity": round(e_sens, 2), "luck_turnovers_sensitivity": round(actual_int + actual_fum_lost - e_sens, 2)}
        if charted:
            iw = int(((o["pass"] == 1) & (o["is_interception_worthy"] == True)).sum())  # noqa: E712
            e_iw = iw * lr["iw_intercepted_share"] + e_fum
            row.update({"interception_worthy_passes": iw, "expected_turnovers_charting": round(e_iw, 2), "luck_turnovers_charting": round(actual_int + actual_fum_lost - e_iw, 2)})
        exp[team] = row
    out["turnover_luck"] = exp
    net_luck = exp["NE"]["luck_turnovers"] - exp["GB"]["luck_turnovers"]   # turnovers NE lost beyond expectation, net of GB
    cost = lr["all_turnover_points_cost"]
    out["net_luck_turnovers_against_NE"] = round(net_luck, 2)
    out["luck_points_to_GB"] = round(net_luck * cost, 2)
    out["adjusted_margin_gb"] = round(out["margin_gb"] - net_luck * cost, 2)
    net_s = exp["NE"]["luck_turnovers_sensitivity"] - exp["GB"]["luck_turnovers_sensitivity"]
    out["sensitivity"] = {"net_luck_turnovers_against_NE": round(net_s, 2), "luck_points_to_GB": round(net_s * cost, 2), "adjusted_margin_gb": round(out["margin_gb"] - net_s * cost, 2)}
    # efficiency without turnover plays
    q = g[g["play_type"].isin(["pass", "run"]) & g["epa"].notna()]
    nt = q[(q["interception"] != 1) & (q["fumble_lost"] != 1)]
    out["epa_per_play"] = {t_: {"all": round(float(q[q.posteam == t_]["epa"].mean()), 3), "without_turnover_plays": round(float(nt[nt.posteam == t_]["epa"].mean()), 3),
                                "pass": round(float(q[(q.posteam == t_) & (q["pass"] == 1)]["epa"].mean()), 3), "rush": round(float(q[(q.posteam == t_) & (q["rush"] == 1)]["epa"].mean()), 3),
                                "plays": int((q.posteam == t_).sum())} for t_ in ("NE", "GB")}
    ps = q[q["pass"] == 1]
    out["hit_or_sack_rate_on_passes"] = {t_: round(float(((ps[ps.posteam == t_]["qb_hit"] == 1) | (ps[ps.posteam == t_]["sack"] == 1)).mean()), 3) for t_ in ("NE", "GB")}
    # frozen pregame forecasts, hashes re-checked
    fr = {}
    for kind in ("forecast_games", "homewin_deep"):
        for f_ in sorted(glob.glob(str(RAW_DIR / "archive" / kind / "2026_w09_*.json"))):
            d = json.loads(Path(f_).read_text(encoding="utf-8"))
            ok = hashlib.sha256(canonical(d["content"])).hexdigest() == d["content_sha256"]
            row = next((x for x in d["content"]["games"] if x["gid"] == GID), None)
            fr[Path(f_).name[:40]] = {"hash_ok": bool(ok), "frozen_at": d["frozen_at"], "forecast": None if row is None else {k: v for k, v in row.items() if k.startswith("p_") or k in ("pred_margin", "sigma", "kalshi_p_home_at_freeze", "market_p_home_at_freeze", "fpi_p_home", "kalshi_winner_p_home", "qb_change_home", "qb_change_away")}}
    out["frozen"] = fr
    dm = [v["forecast"] for v in fr.values() if v["forecast"] and "pred_margin" in v["forecast"]]
    pre_margin_gb = -float(dm[-1]["pred_margin"])
    sigma = float(dm[-1]["sigma"])
    out["pregame_margin_gb"] = round(pre_margin_gb, 2)
    out["sigma"] = round(sigma, 2)
    out["miss_total"] = round(out["margin_gb"] - pre_margin_gb, 2)
    out["miss_after_turnover_luck"] = round(out["adjusted_margin_gb"] - pre_margin_gb, 2)
    out["within_one_sigma_after_luck"] = bool(abs(out["miss_after_turnover_luck"]) < sigma)
    # injuries by snapshot (when first known)
    rows = []
    for f_ in sorted(glob.glob(str(RAW_DIR / "archive" / "nflverse_injuries_*.parquet"))):
        t_ = re.search(r"injuries_(\d{8}T\d{6})Z", f_).group(1)
        d = pd.read_parquet(f_)
        d = d[(d["week"] == 9) & d["team"].isin(["NE", "GB"]) & (d["report_status"] == "Out")]
        rows += [{"snap": t_, "team": r.team, "player": r.full_name, "pos": r.position} for r in d.itertuples()]
    inj = pd.DataFrame(rows)
    first = inj.groupby(["team", "player", "pos"])["snap"].min().reset_index() if len(inj) else inj
    out["out_first_seen"] = first.to_dict("records")
    out["freeze_times"] = sorted(v["frozen_at"] for v in fr.values())
    path = DOCS / "gbne_game.json"
    path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("turnovers", "frozen", "league_rates")}, indent=1, default=str)[:3500])
    for x in out["turnovers"]:
        print(x)
    print(json.dumps(lr))
    return out

# --------------------------------------------------------------------------- part B

BAND = (0.55, 0.65)
GAP_MIN = 0.02


def load() -> pd.DataFrame:
    w = pd.read_parquet(ROOT / "data" / "cache" / "homewin_deep" / "walk_forward.parquet")
    f = pd.read_parquet(ROOT / "data" / "cache" / "homewin_deep" / "forecast_wf.parquet")[["gid", "p_win"]]
    g = pd.read_csv(RAW_DIR / "games.csv")
    g["gid"] = [f"{int(r.season)}_{int(r.week):02d}_{normalize_team(r.away_team)}_{normalize_team(r.home_team)}" for r in g.itertuples()]
    d = w.merge(f, on="gid", how="left").merge(g[["gid", "home_moneyline", "away_moneyline"]], on="gid", how="left")
    n0 = len(d)
    d = d[d["home_moneyline"].notna() & d["away_moneyline"].notna() & d["p_win"].notna()].copy()

    def imp(ml):
        return np.where(ml < 0, -ml / (-ml + 100.0), 100.0 / (ml + 100.0))
    ih, ia = imp(d["home_moneyline"].astype(float)), imp(d["away_moneyline"].astype(float))
    d["p_mkt"] = ih / (ih + ia)
    d["m"] = np.log(d["p_mkt"] / (1 - d["p_mkt"]))
    d["y"] = d["y_home_win"].astype(float)
    d["cl"] = d["season"].astype(str) + "_" + d["week"].astype(str).str.zfill(2)
    d = d.reset_index(drop=True)
    d.attrs["dropped"] = n0 - len(d)
    return d


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _clusters(cl):
    _, inv = np.unique(cl, return_inverse=True)
    return inv, int(inv.max()) + 1


def ratio_ci(num, den, cl, boot_n=0, rng=None, z=ZCI):
    """Mean = sum(num)/sum(den) with an interval clustered by season-week: normal when boot_n is 0, else a percentile bootstrap at 98.33%."""
    inv, k = _clusters(cl)
    a, b = np.bincount(inv, num, k), np.bincount(inv, den, k)
    est = a.sum() / b.sum()
    if boot_n:
        idx = rng.integers(0, k, (boot_n, k))
        r = a[idx].sum(1) / b[idx].sum(1)
        lo, hi = np.percentile(r, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
        return float(est), float(lo), float(hi)
    se = np.sqrt(((a - est * b) ** 2).sum()) / b.sum()
    return float(est), float(est - z * se), float(est + z * se)


def band_stats(p, pm, y, cl, boot_n=0, rng=None):
    """Favorite-oriented band gap, the market gap on the same games, and model minus market."""
    home_fav = p >= 0.5
    pf = np.where(home_fav, p, 1 - p)
    pmf = np.where(home_fav, pm, 1 - pm)
    won = np.where(home_fav, y, 1 - y)
    inb = (pf >= BAND[0]) & (pf < BAND[1])
    one = np.ones(int(inb.sum()))
    gap = ratio_ci((won - pf)[inb], one, cl[inb], boot_n, rng)
    mgap = ratio_ci((won - pmf)[inb], one, cl[inb], boot_n, rng)
    diff = ratio_ci((pmf - pf)[inb], one, cl[inb], boot_n, rng)
    return {"n": int(inb.sum()), "mean_forecast": float(pf[inb].mean()), "observed": float(won[inb].mean()), "gap": gap, "market_gap": mgap,
            "model_minus_market_gap": [-diff[0], -diff[2], -diff[1]]}


def d1_fires(bs, check_2026=None) -> bool:
    gap = bs["gap"]
    ok = (gap[1] > 0 or gap[2] < 0) and abs(gap[0]) >= GAP_MIN
    dm = bs["model_minus_market_gap"]
    ok = ok and (dm[1] > 0 or dm[2] < 0)
    if check_2026 is not None:
        ok = ok and bool(np.sign(check_2026) == np.sign(gap[0]))
    return bool(ok)


def t3_walk(d: pd.DataFrame, col: str, y_col="y", test_seasons=range(2016, 2026)) -> pd.DataFrame:
    from lab import matchup as M
    pc = np.clip(d[col].to_numpy(), 1e-4, 1 - 1e-4)
    dd = d.assign(dlogit=np.log(pc / (1 - pc)) - d["m"].to_numpy())
    out = []
    for s in test_seasons:
        tr, te = dd[dd["season"] < s], dd[dd["season"] == s]
        mu, sd = tr[["dlogit"]].mean().to_numpy(), tr[["dlogit"]].std().to_numpy()
        b = M.fit((tr[["dlogit"]].to_numpy() - mu) / sd, tr["m"].to_numpy(), tr[y_col].to_numpy())
        p = M.predict(b, (te[["dlogit"]].to_numpy() - mu) / sd, te["m"].to_numpy())
        out.append(pd.DataFrame({"season": s, "cl": te["cl"].to_numpy(), "dll": ll(p, te[y_col].to_numpy()) - ll(te["p_mkt"].to_numpy(), te[y_col].to_numpy())}))
    return pd.concat(out, ignore_index=True)


def t3_reading(r: pd.DataFrame, boot_n=0, rng=None):
    est, lo, hi = ratio_ci(r["dll"].to_numpy(), np.ones(len(r)), r["cl"].to_numpy(), boot_n, rng)
    return est, lo, hi, ("adds information" if hi < 0 else "worse than the market" if lo > 0 else "no detectable information beyond the market")


def gate():
    d = load()
    t = d[(d["season"] >= 2012) & (d["season"] <= 2025)].reset_index(drop=True)
    out = {"games": int(len(d)), "dropped_no_close_or_forecast": int(d.attrs["dropped"]), "seed": SEED, "runs": RUNS, "band": list(BAND), "gap_min": GAP_MIN}
    rng = np.random.default_rng(SEED)
    for fid, col in FORECASTS.items():
        p = t[col].to_numpy()
        pm, cl = t["p_mkt"].to_numpy(), t["cl"].to_numpy()
        home_fav = p >= 0.5
        pf = np.where(home_fav, p, 1 - p)
        inb = (pf >= BAND[0]) & (pf < BAND[1])
        res = {"band_games": int(inb.sum())}

        def fire_rate(delta):
            ptrue = np.where(inb, np.where(home_fav, p - delta, p + delta), p)   # band favorites win delta less often than forecast
            n = 0
            for _ in range(RUNS):
                y = (rng.random(len(p)) < ptrue).astype(float)
                n += d1_fires(band_stats(p, pm, y, cl))
            return n / RUNS
        res["d1_placebo_fire_rate"] = fire_rate(0.0)
        res["d1_power_by_gap"] = {str(g): fire_rate(g) for g in (0.02, 0.03, 0.04, 0.05, 0.06)}
        res["d1_planted_0.03_power"] = res["d1_power_by_gap"]["0.03"]
        pc = np.clip(p, 1e-4, 1 - 1e-4)
        dl = np.log(pc / (1 - pc)) - t["m"].to_numpy()
        z = (dl - dl.mean()) / dl.std()
        tt = (t["season"] >= 2016).to_numpy()

        def kl(b):
            pt = 1 / (1 + np.exp(-(t["m"].to_numpy() + b * z)))
            return float(np.mean((pt * np.log(pt / pm) + (1 - pt) * np.log((1 - pt) / (1 - pm)))[tt]))
        lo, hi = 0.0, 5.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if kl(mid) < 0.004 else (lo, mid)
        b = (lo + hi) / 2

        def t3_rate(ptrue):
            n = 0
            for _ in range(RUNS):
                y = (rng.random(len(t)) < ptrue).astype(float)
                r = t3_walk(t.assign(ysim=y), col, y_col="ysim")
                n += t3_reading(r)[3] == "adds information"
            return n / RUNS
        res["t3_placebo_fire_rate"] = t3_rate(pm)
        res["t3_planted_b"] = float(b)
        res["t3_planted_0.004_power"] = t3_rate(1 / (1 + np.exp(-(t["m"].to_numpy() + b * z))))
        res["d1_testable"] = bool(res["d1_placebo_fire_rate"] <= 0.07 and res["d1_planted_0.03_power"] >= 0.80)
        res["t3_testable"] = bool(res["t3_placebo_fire_rate"] <= 0.05 and res["t3_planted_0.004_power"] >= 0.80)
        out[fid] = res
        print(fid, col, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items() if k != "d1_power_by_gap"}, res["d1_power_by_gap"])
    (DOCS / "gbne_gate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def run():
    from lab import inefficiency as I
    gt = json.loads((DOCS / "gbne_gate.json").read_text(encoding="utf-8"))
    d = load()
    rng = np.random.default_rng(SEED)
    t = d[(d["season"] >= 2012) & (d["season"] <= 2025)].reset_index(drop=True)
    c26 = d[d["season"] == 2026].reset_index(drop=True)
    res = {"games_2012_2025": int(len(t)), "games_2026": int(len(c26)), "dropped": int(d.attrs["dropped"])}
    for fid, col in FORECASTS.items():
        g = gt[fid]
        r = {"gate": {k: g[k] for k in ("d1_testable", "t3_testable", "d1_planted_0.03_power", "t3_planted_0.004_power")}}
        p, pm, y, cl = t[col].to_numpy(), t["p_mkt"].to_numpy(), t["y"].to_numpy(), t["cl"].to_numpy()
        dll = ll(p, y) - ll(pm, y)
        dbr = (p - y) ** 2 - (pm - y) ** 2
        r["T1"] = {"model": I.murphy(p, y), "market": I.murphy(pm, y), "log_loss_minus_market": ratio_ci(dll, np.ones(len(t)), cl, 2000, rng),
                   "brier_minus_market": ratio_ci(dbr, np.ones(len(t)), cl, 2000, rng),
                   "seasons_model_better_than_market": int((pd.Series(dll).groupby(t["season"].to_numpy()).mean() < 0).sum()), "seasons": int(t["season"].nunique())}
        bs = band_stats(p, pm, y, cl, 2000, rng)
        if g["d1_testable"]:
            b26 = band_stats(c26[col].to_numpy(), c26["p_mkt"].to_numpy(), c26["y"].to_numpy(), c26["cl"].to_numpy())
            r["T2"] = {**bs, "gap_2026": b26["gap"][0], "n_2026": b26["n"], "defect_D1": d1_fires(bs, b26["gap"][0])}
        else:
            r["T2"] = {"read": False, "reason": "failed its gate (not testable at the registered gap)"}
            r["T2_descriptive_only"] = bs
        if g["t3_testable"]:
            w = t3_walk(d[d["season"] <= 2025], col)
            e3, l3, h3, word = t3_reading(w, 2000, rng)
            r["T3"] = {"log_loss_minus_market": [e3, l3, h3], "reading": word, "defect_D2": word == "worse than the market"}
        else:
            r["T3"] = {"read": False, "reason": "failed its gate (planted gain of 0.004 not detectable)"}
        res[fid] = r
        print(fid, col, json.dumps({k: v for k, v in r.items() if k != "T2_descriptive_only"}, default=float)[:1000])
    fz = []
    gm = pd.read_csv(RAW_DIR / "games.csv")
    gm["gid"] = [f"{int(r.season)}_{int(r.week):02d}_{normalize_team(r.away_team)}_{normalize_team(r.home_team)}" for r in gm.itertuples()]
    done = gm[gm["home_score"].notna()].set_index("gid")
    for f_ in sorted(glob.glob(str(RAW_DIR / "archive" / "homewin_deep" / "2026_w*.json"))):
        dj = json.loads(Path(f_).read_text(encoding="utf-8"))
        ok = hashlib.sha256(canonical(dj["content"])).hexdigest() == dj["content_sha256"]
        for x in dj["content"]["games"]:
            if x["gid"] in done.index and done.loc[x["gid"], "home_score"] != done.loc[x["gid"], "away_score"]:
                fz.append({"hash_ok": bool(ok), "frozen_at": dj["frozen_at"], "gid": x["gid"], "y": float(done.loc[x["gid"], "home_score"] > done.loc[x["gid"], "away_score"]),
                           **{k: x.get(k) for k in ("p_xgb_deep_platt", "p_margin_platt", "market_p_home_at_freeze", "kalshi_p_home_at_freeze")}})
    fzd = pd.DataFrame(fz)
    if len(fzd):
        fzd = fzd.sort_values("frozen_at").drop_duplicates("gid", keep="last")
        cols = [c for c in ("p_xgb_deep_platt", "p_margin_platt", "market_p_home_at_freeze", "kalshi_p_home_at_freeze") if fzd[c].notna().all()]
        res["freezes"] = {"games": int(len(fzd)), "all_hashes_ok": bool(fzd["hash_ok"].all()), "log_loss": {c: float(ll(fzd[c].astype(float).to_numpy(), fzd["y"].to_numpy()).mean()) for c in cols}}
        print("freezes", res["freezes"])
    (DOCS / "gbne_audit.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")


def rebuild():
    """Rerun game, gate and run from raw files and compare output hashes with the committed ones."""
    names = ["gbne_game.json", "gbne_gate.json", "gbne_audit.json"]
    before = {n: hashlib.sha256((DOCS / n).read_bytes()).hexdigest() for n in names}
    game()
    gate()
    run()
    after = {n: hashlib.sha256((DOCS / n).read_bytes()).hexdigest() for n in names}
    print({n: before[n] == after[n] for n in names})


if __name__ == "__main__":
    {"game": game, "gate": gate, "run": run, "rebuild": rebuild}[sys.argv[1]]()
