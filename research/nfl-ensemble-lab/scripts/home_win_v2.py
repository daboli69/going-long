"""Home-win study v2 runner. Protocol: docs/HOMEWIN_V2_PREREGISTRATION.md (18e98172, Amendment 1 98519f2f).

  python scripts/home_win_v2.py backtest            # H1-H4 in one look; writes reports/homewin_v2/results.json
  python scripts/home_win_v2.py freeze-game [--dry] # freeze each game 105-90 minutes before its kickoff

Nothing is promoted. Gate readings are provisional until an independent rebuild matches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import homewin_deep as h  # noqa: E402
from lab import homewin_eval as ev  # noqa: E402
from lab import homewin_v2 as v2  # noqa: E402
from lab.archive10 import save  # noqa: E402

MODELS = ["elo", "margin", "xgb_deep", "elo_platt", "margin_platt", "xgb_deep_platt"]


def log(msg):
    print(msg, flush=True)


def wf_data():
    data, report = h.load_all()
    report["neutral"] = h.neutral_check(data.games)
    report["leakage_weekly_nflverse"] = ev.leakage_check(data)
    log("v1 data checks passed")
    paths = v2.walk_forward_ep(2003, progress=log)
    tg, qb, cmp = v2.wf_tables(data.games, paths)
    data_wf = replace(data, team_games=tg, qb_games=qb)
    pm = v2.wf_prior_mean(data, qb)
    return data, data_wf, pm, report, cmp


def backtest(args):
    data, dw, pm, report, cmp = wf_data()
    res = {"prereg_commit": v2.PREREG_COMMIT, "amendment_1": "98519f2f", "data_checks": report, "epa_comparison": cmp,
           "qb_prior_mean_wf": pm}
    log(f"EPA wf vs nflverse: team-game corr {cmp['team_game_epa_per_play_corr']:.3f}")

    # H1: frozen v1 specs, weekly T_w, walk-forward EPA
    report["leakage_weekly_wf"] = ev.leakage_check(dw)
    f1 = h.all_week_features(dw, prior_mean=pm, progress=log)
    p1, par1 = ev.walk_forward(dw, f1, progress=log)
    p1.to_parquet(v2.CACHE / "h1_walk_forward.parquet")
    e1 = ev.evaluate(p1, dw)
    res["H1"] = {"models": e1["models"], "gate": e1["gate"], "per_season_log_loss": e1["per_season_log_loss"]}
    log("H1 done")

    # H2: per-game points
    res["leakage_points"] = v2.leakage_check_points(dw, pm)
    fp = v2.point_features(dw, pm, progress=log)
    for p, f in fp.items():
        f.to_parquet(v2.CACHE / f"features_{p}.parquet")
    pp, par2 = v2.walk_forward_points(fp, progress=log)
    for p, d in pp.items():
        d.to_parquet(v2.CACHE / f"wf_{p}.parquet")
    (v2.CACHE / "deep_params.json").write_text(json.dumps({str(k): v for k, v in par2.items()}), encoding="utf-8")
    common = set.intersection(*(set(d["gid"]) for d in pp.values()))
    voi = {}
    for p, d in pp.items():
        d = d[d["gid"].isin(common)]
        y = d["y_home_win"].to_numpy(float)
        voi[p] = {"games": int(len(d)), "qb_change_flags": int(d["qb_change_home"].sum() + d["qb_change_away"].sum()),
                  **{m: ev.metrics(y, d[f"p_{m}"].to_numpy())["log_loss"] for m in MODELS}}
    res["H2"] = {"gate_t90": v2.gate(pp["t90"]), "value_of_information": voi,
                 "models_t90": {m: ev.metrics(pp["t90"]["y_home_win"].to_numpy(float), pp["t90"][f"p_{m}"].to_numpy())
                                for m in MODELS}}
    log("H2 done")

    # H3: stacking at T-90
    t90 = pp["t90"]
    res["H3"] = {m: v2.stack(t90, ["p_elo", f"p_{m}"], alpha=0.05 / 2) for m in ("margin", "xgb_deep")}
    for m in ("margin", "xgb_deep"):
        w = res["H3"][m]["weights"][f"p_{m}"]
        res["H3"][m]["adds_value"] = bool(w["ci"][0] > 0)
        res["H3"][m]["walk_forward_stack_ll"] = v2.stack_walk_forward_ll(t90, ["p_elo", f"p_{m}"])
    res["H3"]["elo_alone_ll"] = float(ev._ll(t90["y_home_win"].to_numpy(float), t90["p_elo"].to_numpy()).mean())
    g26 = data.games[(data.games["season"] == 2026) & data.games["played"] & ~data.games["tie"]]
    mkt = v2.market_at_points(data, g26)
    m3 = t90.merge(mkt[["gid", "mkt_t90"]], on="gid").dropna(subset=["mkt_t90"])
    res["H3"]["market_stack_2026_descriptive"] = v2.stack(m3.rename(columns={"mkt_t90": "p_mkt_t90"}),
                                                          ["p_elo", "p_mkt_t90", "p_xgb_deep"], alpha=0.05) if len(m3) >= 30 else None
    log("H3 done")

    # H4: CLV
    res["H4"] = v2.clv(pp, mkt)
    res["market_coverage_2026"] = {p: int(mkt[f"mkt_{p}"].notna().sum()) for p in v2.POINTS} | {"games": int(len(g26))}
    v2.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = v2.REPORT_DIR / "results.json"
    body = json.dumps(res, indent=1, default=str)
    out.write_text(body, encoding="utf-8")
    log(f"Wrote {out} sha256 {hashlib.sha256(body.encode()).hexdigest()}")
    summarize(res)


def summarize(r):
    c = r["epa_comparison"]
    log(f"\nEPA: team-game corr {c['team_game_epa_per_play_corr']:.3f}; play corr range "
        f"{min(v['corr'] for k, v in c.items() if isinstance(v, dict)):.3f}-{max(v['corr'] for k, v in c.items() if isinstance(v, dict)):.3f}")
    for name, g in (("H1 weekly", r["H1"]["gate"]["results"]), ("H2 T-90", r["H2"]["gate_t90"]["results"])):
        log(f"\n{name} gate vs elo:")
        for m, x in g.items():
            log(f"  {m:<15} dLL {x['ll_delta']:+.5f} [{x['ll_ci'][0]:+.5f},{x['ll_ci'][1]:+.5f}] DM p={x['dm']['p']:.3f} "
                f"dBrier {x['brier_delta']:+.5f} seasons {x['seasons_better']}/{x['seasons']} -> {'PASS' if x['pass'] else 'fail'}")
    log("\nValue of information (log loss on common games):")
    for p, v in r["H2"]["value_of_information"].items():
        log(f"  {p:<6} n={v['games']} qb_flags={v['qb_change_flags']} " + " ".join(f"{m}={v[m]:.4f}" for m in MODELS[:3]))
    log("\nH3 stacks (97.5% CI):")
    for m in ("margin", "xgb_deep"):
        s = r["H3"][m]
        log(f"  elo+{m}: " + ", ".join(f"{k} {v['w']:+.3f} [{v['ci'][0]:+.3f},{v['ci'][1]:+.3f}]" for k, v in s["weights"].items())
            + f" adds_value={s['adds_value']} wf_stack_ll={s['walk_forward_stack_ll']:.4f}")
    log(f"\nH4 CLV primary {r['H4']['primary']}:")
    for k, v in r["H4"]["results"].items():
        if v["games"]:
            log(f"  {k:<16} n={v['games']} mean {v['mean_clv']:+.4f} [{v['ci95'][0]:+.4f},{v['ci95'][1]:+.4f}] "
                f"+{v['positive']}/-{v['negative']} p={v['sign_test_p_one_sided']:.3f}" + (" PASS" if v.get("pass") else ""))


def freeze_game(args):
    """Freeze each game whose kickoff is 90-105 minutes away, using T-90-trained history."""
    data, dw, pm, _, _ = wf_data()
    now = pd.Timestamp(args.now, tz="UTC") if args.now else pd.Timestamp.now(tz="UTC")
    due = dw.games[~dw.games["played"] & (dw.games["kickoff_utc"] - now <= pd.Timedelta(minutes=105))
                   & (dw.games["kickoff_utc"] - now >= h.DECISION_LEAD)]
    if due.empty:
        log("No game is 90-105 minutes from kickoff.")
        return
    hist_f = pd.read_parquet(v2.CACHE / "features_t90.parquet")
    hist_p = pd.read_parquet(v2.CACHE / "wf_t90.parquet")
    params = {int(k): v for k, v in json.loads((v2.CACHE / "deep_params.json").read_text(encoding="utf-8")).items()}
    pb = v2.PointBuilder(dw, pm)
    R = now - v2.RESULT_LAG
    f = pd.DataFrame([pb.row(g, now) for g in due.itertuples(index=False)])
    usable = hist_f[hist_f["played"] & (hist_f["kickoff_utc"] < R) & (hist_f["season"] >= h.MARGIN_TRAIN_START)]
    cls = usable[~usable["tie"]].assign(y_home_win=lambda d: d["y_home_win"].astype(int))
    hp = hist_p[hist_p["kickoff_utc"] < R]
    pred, p_m, sigma = h.margin_predict(usable, f, (hp["margin"] - hp["pred_margin"]).to_numpy())
    season = int(due["season"].iloc[0])
    p_d = h.deep_predict(cls, f, params.get(season) or h.tune_deep(cls, season))
    probs = {"elo": f["elo_prob_home"].to_numpy(), "margin": p_m, "xgb_deep": p_d}
    for m in ("elo", "margin", "xgb_deep"):
        probs[f"{m}_platt"] = h.platt(hp[f"p_{m}"].to_numpy(), hp["y_home_win"].to_numpy(), probs[m])
    for i, g in enumerate(due.itertuples(index=False)):
        mk = h.market_probability(data.quotes, g.home, g.away, g.kickoff_utc, now)
        content = {"gid": g.gid, "kickoff_utc": g.kickoff_utc.isoformat(), "point": "t90", "feature_cutoff_utc": now.isoformat(),
                   **{f"p_{m}": float(probs[m][i]) for m in probs}, "pred_margin": float(pred[i]),
                   "qb_change_home": int(f["qb_change_home"].iloc[i]), "qb_change_away": int(f["qb_change_away"].iloc[i]),
                   "market_p_home_at_freeze": mk["p_home"], "market_quote_time": mk["quote_time"],
                   **ev.fpi_projection(g.espn_event_id, g.espn_home, g.home)}
        if args.dry:
            log(f"DRY {content}")
            continue
        saved = save("homewin_v2_game", g.gid, content, {"prereg_commit": v2.PREREG_COMMIT, "frozen_at": now.isoformat(),
                                                          "code_commit": ev._git_sha()})
        if saved["new"]:
            with (v2.REPORT_DIR / "freeze_ledger.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"gid": g.gid, "frozen_at": now.isoformat(), "sha256": saved["sha256"]}) + "\n")
        log(f"Froze {g.gid}: {saved['sha256']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["backtest", "freeze-game"])
    ap.add_argument("--dry", action="store_true", help="freeze-game: print, do not archive")
    ap.add_argument("--now", help="freeze-game --dry only: pretend the current UTC time is this")
    args = ap.parse_args()
    if args.now and not args.dry:
        raise SystemExit("--now is only allowed with --dry")
    {"backtest": backtest, "freeze-game": freeze_game}[args.command](args)


if __name__ == "__main__":
    main()
