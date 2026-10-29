"""Drive-level game simulator runner. Protocol: docs/HOMEWIN_SIM_PREREGISTRATION.md (067e5583).

  python scripts/home_win_sim.py pilot      # 2009-2011 pilot -> power (commit before backtest)
  python scripts/home_win_sim.py backtest   # one look, 2012 to latest week
  python scripts/home_win_sim.py freeze     # archive next week's full distributions before the first kickoff
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import homewin_deep as h  # noqa: E402
from lab import homewin_eval as ev  # noqa: E402
from lab import homewin_sim as sm  # noqa: E402
from lab import homewin_v2 as v2  # noqa: E402
from lab.archive10 import save  # noqa: E402

SESOI = {"drive_ll": 0.005, "win_ll": 0.005, "rel": 0.005}


def log(m):
    print(m, flush=True)


def _write(name, obj):
    sm.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    body = json.dumps(obj, indent=1, default=str)
    (sm.REPORT_DIR / name).write_bytes(body.encode("utf-8"))
    log(f"Wrote {name} sha256 {hashlib.sha256(body.encode()).hexdigest()}")


def pilot(args):
    data, _ = h.load_all()
    drives, drep = sm.all_drives(data.games)
    log(f"drives {drep['drives']}, nflverse agreement {drep['agreement_overall']:.4f}, OTHER {drep['other_dropped']}")
    f90 = pd.read_parquet(v2.CACHE / "features_t90.parquet")
    seasons = range(2009, 2012)
    base = sm.pilot_baseline(f90, data.games, seasons)
    g, d = sm.run_weeks(data.games, drives, base, seasons, progress=log)
    gw = g[~g["tie"]]
    out = {"prereg_commit": sm.PREREG_COMMIT, "pilot_seasons": "2009-2011", "drive_rebuild": drep}
    hist_weeks = int(data.games[(data.games["season"] >= 2012) & data.games["played"]][["season", "week"]].drop_duplicates().shape[0])
    fams = {"D_drive_ll": (sm.paired(d, "ll_model", "ll_base", 0.05), 0.05, SESOI["drive_ll"]),
            "G_margin_rps": (sm.paired(g, "rps_sim", "rps_base", 0.025), 0.025, None),
            "G_total_crps": (sm.paired(g, "crps_sim", "crps_base", 0.025), 0.025, None),
            "W_win_ll": (sm.paired(gw.assign(a=ev._ll(gw["y_home_win"].astype(float), gw["p_sim"]),
                                              b=ev._ll(gw["y_home_win"].astype(float), gw["p_elo"])), "a", "b", 0.025), 0.025, SESOI["win_ll"])}
    for k, (p, alpha, ses) in fams.items():
        ses = ses if ses is not None else SESOI["rel"] * p["mean_b"]
        out[k] = {"sd_week_mean": p["sd_week_mean"], "sesoi": ses, "history_weeks": hist_weeks,
                  "history_mde": sm.mde(p["sd_week_mean"], hist_weeks, alpha),
                  "prospective_mde_by_weeks": {n: sm.mde(p["sd_week_mean"], n, alpha) for n in (1, 4, 8, 17, 34)},
                  "N_weeks": sm.weeks_needed(p["sd_week_mean"], ses, alpha)}
        log(f"{k}: sd_week {p['sd_week_mean']:.5f} SESOI {ses:.5f} history MDE {out[k]['history_mde']:.5f} N {out[k]['N_weeks']} weeks")
    _write("power.json", out)


def backtest(args):
    data, rep = h.load_all()
    rep["neutral"] = h.neutral_check(data.games)
    pm = h.qb_prior_mean(data.qb_games[data.qb_games["season"] <= 2011])
    rep["v2_point_leakage"] = v2.leakage_check_points(data, pm)
    drives, drep = sm.all_drives(data.games)
    rep["sim_leakage"] = leakage(data, drives)
    log("checks passed")
    w90 = pd.read_parquet(v2.CACHE / "wf_t90.parquet").set_index("gid")[["pred_margin", "sigma", "p_elo"]]
    g, d = sm.run_weeks(data.games, drives, w90, range(2012, h.v1.current_season() + 1), progress=log)
    g.to_parquet(sm.CACHE / "games.parquet")
    d.to_parquet(sm.CACHE / "drive_scores.parquet")
    res = {"prereg_commit": sm.PREREG_COMMIT, "data_checks": rep, "drive_rebuild": drep}

    res["D"] = sm.paired(d, "ll_model", "ll_base", 0.05)
    res["D"]["pass"] = res["D"]["ci"][1] < 0
    res["G"] = {"margin_rps": sm.paired(g.dropna(subset=["rps_base"]), "rps_sim", "rps_base", 0.025),
                "total_crps": sm.paired(g, "crps_sim", "crps_base", 0.025)}
    for k in res["G"]:
        res["G"][k]["pass"] = res["G"][k]["ci"][1] < 0

    gw = g[~g["tie"]].dropna(subset=["p_elo"]).sort_values("kickoff_utc").copy()
    gw["y_home_win"] = gw["y_home_win"].astype(int)
    platt = []
    for (s, w), wk in gw.groupby(["season", "week"], sort=False):
        hist = gw[gw["kickoff_utc"] < wk["kickoff_utc"].min()]
        platt.append(pd.Series(h.platt(hist["p_sim"].to_numpy(), hist["y_home_win"].to_numpy(), wk["p_sim"].to_numpy()), index=wk.index))
    gw["p_sim_platt"] = pd.concat(platt)
    alpha = 0.05 / 2
    res["W"] = {}
    for m in ("p_sim", "p_sim_platt"):
        c = ev.compare(gw, m, "p_elo", alpha)
        c["pass"] = bool(c["ll_ci"][1] < 0 and c["dm"]["p"] < alpha and c["brier_delta"] <= 0 and c["seasons_better"] >= 9)
        c["metrics"] = ev.metrics(gw["y_home_win"].to_numpy(float), gw[m].to_numpy())
        res["W"][m] = c
    res["W"]["elo_metrics"] = ev.metrics(gw["y_home_win"].to_numpy(float), gw["p_elo"].to_numpy())
    res["S"] = v2.stack(gw, ["p_elo", "p_sim"], alpha=0.05)
    res["S"]["pass"] = res["S"]["weights"]["p_sim"]["ci"][0] > 0

    key = np.isin(g["margin"].abs(), [3, 7]).astype(float)
    cl = (g["season"].astype(str) + "_" + g["week"].astype(str)).to_numpy()
    res["descriptive"] = {
        "key_3_7_actual": float(key.mean()), "key_3_7_predicted": float(g["p_key37"].mean()),
        "key_3_7_diff_ci95": ev.cluster_boot((key - g["p_key37"]).to_numpy(), cl, 0.05),
        "tie_actual": float(g["tie"].mean()), "tie_predicted": float(g["p_tie"].mean()),
        "pit_margin": sm.pit_test(g["pit_margin"].to_numpy()), "pit_total": sm.pit_test(g["pit_total"].to_numpy()),
        "mc_se_p_home_max": float(np.sqrt(0.25 / sm.N_SIMS))}
    g26 = data.games[(data.games["season"] == 2026) & data.games["played"]]
    ml = sm.market_lines(g26).merge(g[["gid", "median_margin", "median_total", "margin", "total"]], on="gid")
    ml = ml.dropna(subset=["spread_home", "total_line"])
    res["market_2026"] = {"games": int(len(ml)),
                          "mae_sim_vs_market_margin": float((ml["median_margin"] + ml["spread_home"]).abs().mean()),
                          "mae_sim_vs_market_total": float((ml["median_total"] - ml["total_line"]).abs().mean()),
                          "mae_actual_margin": {"sim": float((ml["margin"] - ml["median_margin"]).abs().mean()),
                                                "market": float((ml["margin"] + ml["spread_home"]).abs().mean())},
                          "mae_actual_total": {"sim": float((ml["total"] - ml["median_total"]).abs().mean()),
                                               "market": float((ml["total"] - ml["total_line"]).abs().mean())}}
    _write("results.json", res)
    summarize(res)


def leakage(data, drives, season=2024, week=9):
    wk = data.games[(data.games["season"] == season) & (data.games["week"] == week)]
    R = wk["kickoff_utc"].min() - h.DECISION_LEAD - pd.Timedelta(hours=4)
    bad = drives.copy()
    late = bad["kickoff_utc"] >= R
    rng = np.random.default_rng(1)
    for c in ("cls", "dur", "next_yl"):
        bad.loc[late, c] = rng.permutation(bad.loc[late, c].to_numpy())
    base = pd.DataFrame({"pred_margin": 0.0, "sigma": 13.5, "p_elo": 0.5}, index=wk["gid"])
    cols = ["p_sim", "rps_sim", "crps_sim", "median_margin"]
    a = sm.run_weeks(wk, drives, base, range(season, season + 1), n=2000, progress=lambda m: None)[0][cols]
    b = sm.run_weeks(wk, bad, base, range(season, season + 1), n=2000, progress=lambda m: None)[0][cols]
    if not np.allclose(a.to_numpy(), b.to_numpy()):
        raise h.DataCheckError("simulator LEAKAGE: outputs changed when post-cutoff drives were corrupted")
    sh = pd.Timedelta(days=8)
    a8 = sm.run_weeks(wk, drives, base, range(season, season + 1), n=2000, progress=lambda m: None, R_shift=sh)[0][cols]
    b8 = sm.run_weeks(wk, bad, base, range(season, season + 1), n=2000, progress=lambda m: None, R_shift=sh)[0][cols]
    if np.allclose(a8.to_numpy(), b8.to_numpy()):
        raise h.DataCheckError("simulator leakage negative control not detected")
    return {"week": f"{season}_w{week}", "unchanged": True, "negative_control_detected": True}


def summarize(r):
    d = r["D"]
    log(f"\nD drives: model {d['mean_a']:.4f} vs base {d['mean_b']:.4f} delta {d['delta']:+.5f} [{d['ci'][0]:+.5f},{d['ci'][1]:+.5f}] n={d['n']} -> {'PASS' if d['pass'] else 'fail'}")
    for k, x in r["G"].items():
        log(f"G {k}: sim {x['mean_a']:.4f} vs base {x['mean_b']:.4f} delta {x['delta']:+.4f} [{x['ci'][0]:+.4f},{x['ci'][1]:+.4f}] -> {'PASS' if x['pass'] else 'fail'}")
    for m in ("p_sim", "p_sim_platt"):
        c = r["W"][m]
        log(f"W {m}: LL {c['metrics']['log_loss']:.4f} (elo {r['W']['elo_metrics']['log_loss']:.4f}) dLL {c['ll_delta']:+.5f} "
            f"[{c['ll_ci'][0]:+.5f},{c['ll_ci'][1]:+.5f}] DM p={c['dm']['p']:.3f} seasons {c['seasons_better']}/{c['seasons']} -> {'PASS' if c['pass'] else 'fail'}")
    s = r["S"]["weights"]
    log(f"S stack: elo {s['p_elo']['w']:+.3f} [{s['p_elo']['ci'][0]:+.3f},{s['p_elo']['ci'][1]:+.3f}] sim {s['p_sim']['w']:+.3f} "
        f"[{s['p_sim']['ci'][0]:+.3f},{s['p_sim']['ci'][1]:+.3f}] -> {'PASS' if r['S']['pass'] else 'fail'}")
    x = r["descriptive"]
    log(f"key 3/7 actual {x['key_3_7_actual']:.4f} predicted {x['key_3_7_predicted']:.4f}; ties {x['tie_actual']:.4f} vs {x['tie_predicted']:.4f}")
    log(f"PIT margin chi2 p {x['pit_margin']['chi2_p']:.3f} {x['pit_margin']['hist']}; total chi2 p {x['pit_total']['chi2_p']:.3f} {x['pit_total']['hist']}")
    log(f"market 2026: {r['market_2026']}")


def freeze(args):
    data, _ = h.load_all(True)
    drives, _ = sm.all_drives(data.games)
    now = pd.Timestamp.now(tz="UTC")
    up = data.games[~data.games["played"] & (data.games["kickoff_utc"] > now)]
    if up.empty:
        log("no upcoming games")
        return
    s, w = up.sort_values("kickoff_utc").iloc[0][["season", "week"]]
    wk = up[(up["season"] == s) & (up["week"] == w)]
    R = min(now, wk["kickoff_utc"].min() - h.DECISION_LEAD) - pd.Timedelta(hours=4)
    tr = drives[(drives["kickoff_utc"] < R) & drives["season"].between(s - 3, s) & drives["cls"].isin(sm.CLASSES)]
    teams = sorted(set(drives["off"]) | set(drives["def"]))
    model, pace = sm.DriveModel(teams).fit(tr, R), sm.Pace(tr, int(s))
    kal = ev.kalshi_now(data.games)
    games = []
    for g in wk.itertuples(index=False):
        sim = sm.simulate(model, pace, g.home, g.away, int(g.neutral), int(s), g.gid)
        games.append({"gid": g.gid, "kickoff_utc": g.kickoff_utc.isoformat(), "p_home": sim["p_home"], "p_tie": sim["p_tie"],
                      "median_margin": sim["median_margin"], "median_total": sim["median_total"],
                      **kal.get(g.gid, {"kalshi_p_home_at_freeze": None}),
                      # string keys: the archive hash must survive a JSON round trip
                      "margin_pmf": {str(int(m)): round(float(p), 5) for m, p in zip(sm.MARGINS, sim["margin_pmf"]) if p > 0},
                      "total_pmf": {str(int(t)): round(float(p), 5) for t, p in zip(sm.TOTALS, sim["total_pmf"]) if p > 0}})
        log(f"  {g.away} @ {g.home}: P(home) {sim['p_home']:.1%}, median margin {sim['median_margin']:+.0f}, total {sim['median_total']:.0f}")
    saved = save("homewin_sim", f"{int(s)}_w{int(w):02d}", {"season": int(s), "week": int(w), "results_cutoff_utc": R.isoformat(),
                                                            "games": games},
                 {"prereg_commit": sm.PREREG_COMMIT, "code_commit": ev._git_sha(), "frozen_at": now.isoformat()})
    if saved["new"]:
        sm.REPORT_DIR.mkdir(parents=True, exist_ok=True)
        with (sm.REPORT_DIR / "freeze_ledger.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"season": int(s), "week": int(w), "games": len(games), "frozen_at": now.isoformat(),
                                 "sha256": saved["sha256"]}) + "\n")
    log(f"Froze {len(games)} games: {saved['sha256']} ({'new' if saved['new'] else 'already archived'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["pilot", "backtest", "freeze"])
    args = ap.parse_args()
    {"pilot": pilot, "backtest": backtest, "freeze": freeze}[args.command](args)


if __name__ == "__main__":
    main()
