"""Luck-adjusted team strength test, raw files to every reported number (docs/LUCK_ADJUSTED_PREREGISTRATION.md and Amendment 1).

    .venv\\Scripts\\python.exe scripts\\luck_run.py checks   # reference checks and the leak canary (no tuning, nothing from 2012 on is scored)
    .venv\\Scripts\\python.exe scripts\\luck_run.py tune     # settings chosen on 2008 to 2011 only, writes docs/luck_tuned.json
    .venv\\Scripts\\python.exe scripts\\luck_run.py test     # the one look at 2012 week 1 to 2026 week 8; refuses to run unless luck_tuned.json is committed and unchanged
    .venv\\Scripts\\python.exe scripts\\luck_run.py all      # checks, tune and test in one go (the clean-copy rebuild runs this)

Set LUCK_DATA to a data folder to read from (a clean checkout has no data of its own). --out sets where the JSON files go (default docs/).
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import luck_elo as LE  # noqa: E402
from lab import luck_eval as EV  # noqa: E402
from lab import luck_strength as LS  # noqa: E402

LAMS = [40.0, 100.0, 250.0, 600.0, 1500.0]       # Amendment 1: the registered 5, 15 and 40 are far below the natural scale
HALF = [8.0, 16.0, 32.0, np.inf]
KS = [100.0, 300.0, 1000.0]
QS = [0.0, 0.01, 0.03, 0.1]
RHOS = [0.5, 0.65, 0.8, 0.95]
ELO_K, ELO_REV, ELO_HFA = [10.0, 15.0, 20.0, 30.0], [0.25, 1 / 3, 0.5], [40.0, 55.0, 70.0]
TUNE_SEASONS = (2008, 2011)
TEST_FROM = 2012
NEAR_TIE_SE = 0.1


def jnum(x):
    return None if x is None else (str(x) if isinstance(x, float) and np.isinf(x) else x)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key_of(g: pd.DataFrame) -> pd.Series:
    """The lab's game key (season_week_away_home with current team codes)."""
    return g["season"].astype(str) + "_" + g["week"].astype(str).str.zfill(2) + "_" + g["away"] + "_" + g["home"]


# --------------------------------------------------------------------------- checks


def run_checks(out: Path) -> dict:
    res = {}
    # 1. Elo: rebuilt independently, compared with the lab's saved Elo
    wf = pd.read_parquet(LS.DATA / "cache" / "homewin_deep" / "forecast_wf.parquet")
    g = LE.load_games(regular_only=True, since=1999, neutral_rule="lab")
    h = LE.elo_history(g)
    h["key"] = key_of(g)
    m = wf.merge(h, left_on="gid", right_on="key")
    d = (m["p_elo"] - m["p_home"]).abs()
    g2 = LE.load_games(regular_only=True, since=1999, neutral_rule="stadium_id")
    h2 = LE.elo_history(g2)
    h2["key"] = key_of(g2)
    m2 = wf.merge(h2, left_on="gid", right_on="key")
    d2 = (m2["p_elo"] - m2["p_home"]).abs()
    res["elo_reproduction"] = {"games": int(len(m)), "max_gap_lab_neutral_rule": float(d.max()), "games_gap_over_1e6": int((d > 1e-6).sum()),
                               "max_gap_stadium_id_rule": float(d2.max()), "games_gap_over_1e3_stadium_id_rule": int((d2 > 1e-3).sum()),
                               "explanation": "the lab marks a game neutral when the stadium name differs from the team's usual one; Seattle's rename in 2020 made its last four home games neutral there"}
    # 2. closing line against the nflverse pregame win probability in each game's first play
    rows = []
    for s in range(TEST_FROM, LS.LAST + 1):
        p = pd.read_parquet(LS.RAW / f"play_by_play_{s}.parquet", columns=["game_id", "season_type", "play_id", "vegas_home_wp"])
        p = p[p["season_type"] == "REG"].sort_values(["game_id", "play_id"])
        rows.append(p.groupby("game_id").head(1))
    f = pd.concat(rows)
    gm = pd.read_csv(LS.RAW / "games.csv")[["game_id", "season", "spread_line", "home_score", "away_score"]]
    m3 = f.merge(gm, on="game_id")
    m3 = m3[m3["spread_line"].notna() & m3["vegas_home_wp"].notna() & m3["home_score"].notna()].copy()
    m3["margin"] = m3["home_score"] - m3["away_score"]
    sd = {s: (float(np.std(m3[m3.season < s].margin - m3[m3.season < s].spread_line)) if s > TEST_FROM else 13.3) for s in m3.season.unique()}
    m3["p_line"] = norm.cdf(m3["spread_line"] / m3["season"].map(sd))
    dd = (m3["vegas_home_wp"] - m3["p_line"]).abs()
    res["closing_line_vs_nflverse_pregame_wp"] = {"games": int(len(m3)), "mae": float(dd.mean()), "median_abs_gap": float(dd.median()),
                                                  "games_gap_over_0.3": int((dd > 0.3).sum()), "mae_excluding_those": float(dd[dd <= 0.3].mean()),
                                                  "corr_with_spread_sign": float(np.corrcoef(m3["spread_line"], m3["margin"])[0, 1]),
                                                  "explanation": "nflverse maps spread to win probability with a steeper curve than a normal fitted to earlier seasons' results; "
                                                                 "the games over 0.3 have the first-play value on the wrong side (nflverse data defect)"}
    # 3. as-of rule and the leak canary on the tuning panel (no play from 2012 on is read)
    P = LS.Panel(last_season=TUNE_SEASONS[1])
    res["asof_rule"] = LS.check_asof(P)
    res["canary_asof_own_batch"] = {k: v for k, v in LS.check_asof(P, P.g_batch).items() if k != "violating_games"}
    adj = P.adjusted(300.0)
    nbar = P.plays_per_game()
    rid = LS.ridge_weekly(P, adj, [250.0], 16.0)[250.0]
    ks = LS.kalman_strength(P, adj, rid, 250.0, 0.01, 0.8, nbar)
    b0 = int(np.searchsorted(P.batch_season, TUNE_SEASONS[0]))
    ev = P.g_season >= TUNE_SEASONS[0]
    base = LS.score_maps(P, ks["xm"], ks["xt"], 16.0, b0)
    can = LS.score_maps(P, ks["xm"], ks["xt"], 16.0, b0, canary=P.y_m.copy())
    ok = ev & np.isfinite(base["mu_m"])
    res["canary_crps"] = {"without": float(EV.crps(P.y_m[ok], base["mu_m"][ok], base["sd_m"][ok]).mean()),
                          "with_final_margin_as_a_feature": float(EV.crps(P.y_m[ok], can["mu_m"][ok], can["sd_m"][ok]).mean())}
    res["canary_flagged"] = bool(res["canary_asof_own_batch"]["violations"] > 0 and res["canary_crps"]["with_final_margin_as_a_feature"] < 0.5 * res["canary_crps"]["without"]
                                 and res["asof_rule"]["violations"] == 0)
    (out / "luck_checks.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


# --------------------------------------------------------------------------- tuning


def _near_best(rows: list[dict], arrays: list[np.ndarray], key) -> int:
    scores = np.array([r["crps"] for r in rows])
    ib = int(scores.argmin())
    near = []
    for i, a in enumerate(arrays):
        d = a - arrays[ib]
        se = d.std(ddof=1) / np.sqrt(len(d)) if i != ib else 0.0
        if d.mean() <= NEAR_TIE_SE * se or i == ib:
            near.append(i)
    return max(near, key=lambda i: key(rows[i])), len(near), ib


def tune(out: Path) -> dict:
    P = LS.Panel(last_season=TUNE_SEASONS[1])
    nbar = P.plays_per_game()
    b0 = int(np.searchsorted(P.batch_season, TUNE_SEASONS[0]))
    ev = (P.g_season >= TUNE_SEASONS[0]) & (P.g_season <= TUNE_SEASONS[1])
    res = {"seasons": list(TUNE_SEASONS), "games": int(ev.sum())}

    def grid(luck: bool):
        rows, arrays = [], []
        ks_list = KS if luck else [0.0]
        for k in ks_list:
            adj = P.adjusted(k, luck=luck)
            for H in HALF:
                rid = LS.ridge_weekly(P, adj, LAMS, H)
                for lam in LAMS:
                    for q, rho in itertools.product(QS, RHOS):
                        st = LS.kalman_strength(P, adj, rid[lam], lam, q, rho, nbar)
                        sm = LS.score_maps(P, st["xm"], st["xt"], H, b0)
                        ok = ev & np.isfinite(sm["mu_m"])
                        if ok.sum() != ev.sum():
                            continue
                        c = EV.crps(P.y_m[ok], sm["mu_m"][ok], sm["sd_m"][ok])
                        rows.append({"k": k, "lam": lam, "H": H, "q": q, "rho": rho, "crps": float(c.mean()),
                                     "crps_total": float(EV.crps(P.y_t[ok], sm["mu_t"][ok], sm["sd_t"][ok]).mean())})
                        arrays.append(c)
        return rows, arrays

    for name, luck in (("new", True), ("same_plays_no_luck_removal", False)):
        rows, arrays = grid(luck)
        # more shrinkage wins a near tie: larger lambda, larger k, smaller q, smaller rho, then longer memory
        pick, n_near, ib = _near_best(rows, arrays, lambda r: (r["lam"], r["k"], -r["q"], -r["rho"], r["H"]))
        best = rows[pick]
        edge = {"lam": best["lam"] in (LAMS[0], LAMS[-1]), "H": best["H"] in (HALF[0], HALF[-1]),
                "k": best["k"] in (KS[0], KS[-1]) if luck else None, "q": best["q"] in (QS[0], QS[-1]), "rho": best["rho"] in (RHOS[0], RHOS[-1])}
        top = sorted(rows, key=lambda r: r["crps"])[:8]
        res[name] = {"combinations": len(rows), "chosen": {a: jnum(b) for a, b in best.items()}, "best_raw": {a: jnum(b) for a, b in rows[ib].items()},
                     "near_ties": n_near, "chosen_on_grid_edge": edge, "top8": [{a: jnum(b) for a, b in r.items()} for r in top]}
    # margin-aware Elo control
    g = LE.load_games(regular_only=True, since=1999, until=TUNE_SEASONS[1])
    rows, arrays = [], []
    for K, rev, hfa in itertools.product(ELO_K, ELO_REV, ELO_HFA):
        h = LE.elo_history(g, k=K, hfa=hfa, revert=rev)
        gap = P.games[["game_id"]].merge(h[["game_id", "gap"]], on="game_id", how="left")["gap"].to_numpy()
        sm = LS.score_maps(P, gap, np.zeros(P.G), np.inf, b0)
        ok = ev & np.isfinite(sm["mu_m"])
        c = EV.crps(P.y_m[ok], sm["mu_m"][ok], sm["sd_m"][ok])
        rows.append({"K": K, "revert": rev, "hfa": hfa, "crps": float(c.mean())})
        arrays.append(c)
    pick, n_near, ib = _near_best(rows, arrays, lambda r: (-r["K"], r["revert"], -r["hfa"]))
    res["elo"] = {"combinations": len(rows), "chosen": rows[pick], "best_raw": rows[ib], "near_ties": n_near,
                  "top5": sorted(rows, key=lambda r: r["crps"])[:5]}
    (out / "luck_tuned.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


# --------------------------------------------------------------------------- the one look


def frozen_commit(path: Path) -> str:
    """The commit holding `path`, after checking it is tracked and unchanged since. Raises if not."""
    run = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if run("ls-files", "--error-unmatch", rel).returncode != 0:
        raise SystemExit(f"{rel} is not committed: commit the tuned settings before the test look.")
    if run("diff", "--quiet", "HEAD", "--", rel).returncode != 0:
        raise SystemExit(f"{rel} differs from its commit: the tuned settings must stay as committed.")
    return run("log", "-1", "--format=%H", "--", rel).stdout.strip()


def evaluate(out: Path, tuned_path: Path) -> dict:
    tuned = json.loads(tuned_path.read_text(encoding="utf-8"))
    committed = ROOT / "docs" / "luck_tuned.json"
    commit = frozen_commit(committed)
    if tuned_path.resolve() != committed.resolve() and sha256_of(tuned_path) != sha256_of(committed):
        raise SystemExit("the tuned settings rebuilt in this run differ from the committed docs/luck_tuned.json")
    num = lambda x: float("inf") if x == "inf" else float(x)
    new, ctl = tuned["new"]["chosen"], tuned["same_plays_no_luck_removal"]["chosen"]
    P = LS.Panel(last_season=LS.LAST)
    nbar = P.plays_per_game()
    b08 = int(np.searchsorted(P.batch_season, TUNE_SEASONS[0]))

    def run_strength(luck, k, lam, H, q, rho):
        adj = P.adjusted(k, luck=luck)
        rid = LS.ridge_weekly(P, adj, [lam], H)[lam]
        st = LS.kalman_strength(P, adj, rid, lam, q, rho, nbar)
        return LS.score_maps(P, st["xm"], st["xt"], H, b08)

    f_new = run_strength(True, num(new["k"]), num(new["lam"]), num(new["H"]), num(new["q"]), num(new["rho"]))
    f_ctl = run_strength(False, 0.0, num(ctl["lam"]), num(ctl["H"]), num(ctl["q"]), num(ctl["rho"]))
    e = tuned["elo"]["chosen"]
    gE = LE.load_games(regular_only=True, since=1999)
    hE = LE.elo_history(gE, k=e["K"], hfa=e["hfa"], revert=e["revert"])
    gap = P.games[["game_id"]].merge(hE[["game_id", "gap"]], on="game_id", how="left")["gap"].to_numpy()
    f_elo = LS.score_maps(P, gap, np.zeros(P.G), np.inf, b08)
    # the current score model, as saved
    wf = pd.read_parquet(LS.DATA / "cache" / "homewin_deep" / "forecast_wf.parquet")
    pk = key_of(P.games)
    A = pd.DataFrame({"key": pk}).merge(wf, left_on="key", right_on="gid", how="left")
    played = P.games["played"].to_numpy()
    tie = (P.y_m == 0)
    mask = played & ~tie & (P.g_season >= TEST_FROM) & A["mu_m"].notna().to_numpy()
    n_expected = int((wf["played"] & ~wf["tie"].astype(bool)).sum())
    assert int(mask.sum()) == n_expected, f"evaluation set {int(mask.sum())} games, saved model {n_expected}"
    y, yt = P.y_m[mask], P.y_t[mask]
    weeks = np.array([f"{s}-{w:02d}" for s, w in zip(P.g_season[mask], P.batch_week[P.g_batch[mask]])])
    seas = P.g_season[mask]
    fc = {"new": f_new, "elo": f_elo, "same_plays": f_ctl,
          "current": {"mu_m": A["mu_m"].to_numpy()[mask], "sd_m": A["sd_m"].to_numpy()[mask], "mu_t": A["mu_t"].to_numpy()[mask], "sd_t": A["sd_t"].to_numpy()[mask]}}
    for kname in ("new", "elo", "same_plays"):
        fc[kname] = {a: b[mask] for a, b in fc[kname].items()}
    # B has no total model of its own: its total is the weekly weighted mean (intercept only), which score_maps gives with xt = 0
    loss, win = {}, (y > 0).astype(float)
    pw = {}
    for name, f in fc.items():
        loss[name] = {"margin": EV.crps(y, f["mu_m"], f["sd_m"]), "total": EV.crps(yt, f["mu_t"], f["sd_t"])}
        p = norm.cdf(f["mu_m"] / f["sd_m"])
        pw[name] = p
        loss[name]["logloss"] = EV.logloss(p, win)
        loss[name]["brier"] = EV.brier(p, win)
    res = {"tuned_commit": commit, "tuned_sha256": sha256_of(tuned_path), "games": int(mask.sum()), "weeks": int(len(np.unique(weeks))),
           "chosen": {"new": new, "same_plays": ctl, "elo": e}, "code_files": {f: sha256_of(ROOT / f) for f in ("lab/luck_strength.py", "lab/luck_eval.py", "lab/luck_elo.py", "scripts/luck_run.py")}}
    res["means"] = {n: {m: float(v.mean()) for m, v in d.items()} for n, d in loss.items()}
    cmp_ = {}
    for ref, cid in (("current", "C1"), ("elo", "C2"), ("same_plays", "C3")):
        d = loss["new"]["margin"] - loss[ref]["margin"]
        cmp_[cid] = {"vs": ref, "metric": "margin_crps", **EV.week_bootstrap(d, weeks), "dm": EV.diebold_mariano(d, weeks), "seasons": EV.season_wins(loss["new"]["margin"], loss[ref]["margin"], seas)}
    for ref in ("current", "elo"):
        for m in ("total", "logloss", "brier"):
            d = loss["new"][m] - loss[ref][m]
            cmp_[f"S_{m}_vs_{ref}"] = {"vs": ref, "metric": m, **EV.week_bootstrap(d, weeks), "dm": EV.diebold_mariano(d, weeks)}
    res["comparisons"] = cmp_
    hp = EV.holm({"C1": cmp_["C1"]["dm"]["p"], "C2": cmp_["C2"]["dm"]["p"]})
    res["holm_adjusted_dm_p"] = hp
    res["calibration"] = {n: {"margin_cov80": EV.coverage80(y, f["mu_m"], f["sd_m"]), "total_cov80": EV.coverage80(yt, f["mu_t"], f["sd_t"]),
                              "pit_margin": EV.pit_hist(y, f["mu_m"], f["sd_m"]), "brier_decomposition": EV.brier_decomposition(pw[n], win)} for n, f in fc.items()}
    res["placebo_vs_current"] = EV.placebo(fc["new"]["mu_m"], fc["new"]["sd_m"], y, loss["current"]["margin"], weeks, seas)
    # M1: blend with the closing line, weights fitted on earlier seasons only
    games_csv = pd.read_csv(LS.RAW / "games.csv").set_index("game_id")
    spread = games_csv.loc[P.games["game_id"], "spread_line"].to_numpy(float)
    have = np.isfinite(spread) & played & (P.y_m != 0)
    sd_line = {}
    for s in range(TUNE_SEASONS[0], LS.LAST + 1):
        prior = have & (P.g_season < s)
        sd_line[s] = float(np.std(P.y_m[prior] - spread[prior])) if prior.sum() > 200 else 13.3
    sdl = np.array([sd_line.get(s, 13.3) for s in P.g_season])
    p_line = norm.cdf(spread / sdl)
    p_new_all = norm.cdf(f_new["mu_m"] / f_new["sd_m"])
    blend_rows, w_by_season = [], {}
    p_blend = np.full(P.G, np.nan)
    mu_blend = np.full(P.G, np.nan)
    for s in range(TEST_FROM, LS.LAST + 1):
        fit = have & np.isfinite(p_new_all) & (P.g_season >= TUNE_SEASONS[0]) & (P.g_season < s)
        w = EV.best_blend_weight(p_line[fit], p_new_all[fit], (P.y_m[fit] > 0).astype(float))
        # margin-scale weight by least squares on the same earlier games
        dmu = (f_new["mu_m"] - spread)[fit]
        wm = float(np.clip((dmu * (P.y_m[fit] - spread[fit])).sum() / (dmu * dmu).sum(), -0.5, 1.5))
        w_by_season[s] = {"logit_weight": w, "margin_weight": wm, "games_fit": int(fit.sum())}
        cur = (P.g_season == s)
        p_blend[cur] = 1 / (1 + np.exp(-(EV.logit(p_line[cur]) + w * (EV.logit(p_new_all[cur]) - EV.logit(p_line[cur])))))
        mu_blend[cur] = spread[cur] + wm * (f_new["mu_m"][cur] - spread[cur])
    mm = mask & have & np.isfinite(p_blend)
    wk_m = np.array([f"{s}-{w:02d}" for s, w in zip(P.g_season[mm], P.batch_week[P.g_batch[mm]])])
    wl = (P.y_m[mm] > 0).astype(float)
    d_ll = EV.logloss(p_blend[mm], wl) - EV.logloss(p_line[mm], wl)
    d_cr = EV.crps(P.y_m[mm], mu_blend[mm], sdl[mm]) - EV.crps(P.y_m[mm], spread[mm], sdl[mm])
    res["M1_closing_line"] = {"games": int(mm.sum()), "weights_by_season": {int(k): v for k, v in w_by_season.items()},
                              "mean_logit_weight": float(np.mean([v["logit_weight"] for v in w_by_season.values()])),
                              "logloss_blend_minus_line": EV.week_bootstrap(d_ll, wk_m), "margin_crps_blend_minus_line": EV.week_bootstrap(d_cr, wk_m),
                              "line_logloss": float(EV.logloss(p_line[mm], wl).mean()), "line_margin_crps": float(EV.crps(P.y_m[mm], spread[mm], sdl[mm]).mean()),
                              "new_alone_logloss_same_games": float(EV.logloss(p_new_all[mm], wl).mean())}
    # the acceptance rule
    half_mde = 0.035
    c1, c2 = cmp_["C1"], cmp_["C2"]
    crit = {"1_C1_C2_ci_below_zero_after_holm_and_gain_ge_0.035":
            bool(c1["hi"] < 0 and c2["hi"] < 0 and max(hp.values()) < 0.05 and -c1["mean"] >= half_mde and -c2["mean"] >= half_mde),
            "2_logloss_not_worse_than_current_by_more_than_0.002": bool(cmp_["S_logloss_vs_current"]["hi"] < 0.002 and cmp_["S_brier_vs_current"]["mean"] <= 0.0),
            "3_coverage_margin_and_total_75_to_85": bool(all(0.75 <= res["calibration"]["new"][k] <= 0.85 for k in ("margin_cov80", "total_cov80"))),
            "4_better_than_current_in_9_of_15_seasons": bool(c1["seasons"]["better_in"] >= 9),
            "5_placebo_no_gain_and_canary_flagged": bool(res["placebo_vs_current"]["mean_diff"] >= 0 and json.loads((out / "luck_checks.json").read_text(encoding="utf-8"))["canary_flagged"])}
    res["acceptance"] = {"criteria": crit, "challenger": bool(all(crit.values()))}
    # per-game forecasts for the record (local, not committed)
    cache = LS.DATA / "cache" / "luck"
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"game_id": P.games["game_id"].to_numpy()[mask], "season": seas, "week": weeks, "y_m": y, "y_t": yt,
                  **{f"{n}_{k}": f[k] for n, f in fc.items() for k in ("mu_m", "sd_m", "mu_t", "sd_t")}}).to_parquet(cache / "forecasts_test.parquet")
    (out / "luck_results.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["checks", "tune", "test", "all"])
    ap.add_argument("--out", type=Path, default=ROOT / "docs")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.stage in ("checks", "all"):
        r = run_checks(a.out)
        print(json.dumps(r, indent=1)[:3000])
    if a.stage in ("tune", "all"):
        r = tune(a.out)
        print(json.dumps({k: (v if k in ("seasons", "games") else v.get("chosen")) for k, v in r.items()}, indent=1))
    if a.stage in ("test", "all"):
        r = evaluate(a.out, a.out / "luck_tuned.json")
        print(json.dumps({k: r[k] for k in ("games", "means", "comparisons", "acceptance") if k in r}, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
