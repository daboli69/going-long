"""Deep home-win model runner. Protocol: docs/HOMEWIN_DEEP_PREREGISTRATION.md (commit 741a13e7).

  python scripts/home_win_deep.py backtest   # data checks, leakage check, walk-forward 2012+, gate report
  python scripts/home_win_deep.py freeze     # catch up new weeks, then archive next week's predictions
  python scripts/home_win_deep.py score      # score archived freezes against final results

All data is fetched automatically (nfldata API, ESPN API, nflverse play-by-play, lab injury
archive, GOING quote history). Nothing is promoted by this script.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import homewin_deep as h  # noqa: E402
from lab import homewin_eval as ev  # noqa: E402

FEATS = h.CACHE / "features.parquet"
PREDS = h.CACHE / "walk_forward.parquet"
PARAMS = h.CACHE / "deep_params.json"


def _load(refresh: bool):
    data, report = h.load_all(refresh)
    report["neutral"] = h.neutral_check(data.games)
    report["leakage"] = ev.leakage_check(data)
    print(f"Data checks passed: {report['scores']['played']} played games score-matched to ESPN; "
          f"neutral flags compared on {report['neutral']['compared']} games; leakage check unchanged on "
          f"{len(report['leakage']) - 1} weeks (negative control detected).", flush=True)
    return data, report


def _features(data, rebuild_from: int | None = None) -> pd.DataFrame:
    if FEATS.exists() and rebuild_from is not None:
        old = pd.read_parquet(FEATS)
        new = h.all_week_features(data, first_season=rebuild_from)
        f = pd.concat([old[old["season"] < rebuild_from], new], ignore_index=True)
    else:
        f = h.all_week_features(data)
    f.to_parquet(FEATS)
    return f


def coverage(data, feats) -> dict:
    """Per season: team-games with any injury row timestamped before T_w, and QB changes flagged."""
    inj = data.injuries[data.injuries["available_at"].notna()]
    out = {}
    for s, g in data.games[data.games["season"] >= h.EVAL_START].groupby("season"):
        covered = 0
        for (w, T), gw in g.groupby(["week", "decision_utc"]):
            teams = set(gw["home"]) | set(gw["away"])
            seen = set(inj.loc[(inj["season"] == s) & (inj["week"] == w) & (inj["available_at"] < T), "team"])
            covered += len(teams & seen)
        f = feats[feats["season"] == s]
        out[int(s)] = {"team_games": 2 * len(g), "with_pre_decision_injury_rows": covered,
                       "qb_change_flags": int(f["qb_change_home"].sum() + f["qb_change_away"].sum())}
    return out


def _save(preds, params):
    preds.to_parquet(PREDS)
    PARAMS.write_text(json.dumps({str(k): v for k, v in params.items()}), encoding="utf-8")


def backtest(args):
    data, report = _load(args.refresh)
    feats = _features(data)
    preds, params = ev.walk_forward(data, feats)
    _save(preds, params)
    res = ev.evaluate(preds, data) | {"data_checks": report, "coverage": coverage(data, feats),
                                      "inactives_archived": int(len(data.inactives)), "deep_params": params}
    ev.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = ev.REPORT_DIR / "backtest.json"
    out.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    summarize(res)
    print(f"Wrote {out}")


def summarize(res):
    print(f"\nWalk-forward {res['window']} (log loss, Brier, accuracy, AUC, ECE):")
    for m, r in res["models"].items():
        print(f"  {m:<16} {r['log_loss']:.4f}  {r['brier']:.4f}  {r['accuracy']:.3f}  {r['roc_auc']:.4f}  {r['ece']:.4f}  n={r['n']}")
    print(f"\nGate vs elo (Bonferroni alpha {res['gate']['family_alpha']:.4f}; primary {res['gate']['primary']}):")
    for m, c in res["gate"]["results"].items():
        print(f"  {m:<16} dLL {c['ll_delta']:+.5f} [{c['ll_ci'][0]:+.5f}, {c['ll_ci'][1]:+.5f}]  DM p={c['dm']['p']:.4f}  "
              f"dBrier {c['brier_delta']:+.5f}  seasons {c['seasons_better']}/{c['seasons']}  -> {'PASS' if c['pass'] else 'fail'}")
    for col, block in res["vs_market"].items():
        print(f"\nvs {col} (descriptive, 95% CI, n={block['market']['n']}): market LL {block['market']['log_loss']:.4f}")
        for m in ev.MODELS:
            c = block[m]
            print(f"  {m:<16} dLL {c['ll_delta']:+.4f} [{c['ll_ci'][0]:+.4f}, {c['ll_ci'][1]:+.4f}]")


def freeze(args):
    data, _ = _load(True)
    if not PREDS.exists():
        raise SystemExit("Run `backtest` once first.")
    live = int(data.games.loc[data.games["played"], "season"].max())
    feats = _features(data, rebuild_from=live)
    params = {int(k): v for k, v in json.loads(PARAMS.read_text(encoding="utf-8")).items()}
    preds, params = ev.walk_forward(data, feats, prior_preds=pd.read_parquet(PREDS), prior_params=params)
    _save(preds, params)
    saved = ev.freeze(data, feats, preds, params)
    if not saved.get("games"):
        print(saved)
        return
    print(f"Froze {len(saved['games'])} games, {saved['season']} week {saved['week']}: sha256 {saved['sha256']} "
          f"({'new' if saved['new'] else 'identical content already archived'})")
    for g in saved["games"]:
        p = g["p_margin_platt"]
        pick, pp = (g["home"], p) if p >= 0.5 else (g["away"], 1 - p)
        m = g["market_p_home_at_freeze"]
        mk = "n/a" if m is None or np.isnan(m) else f"{m:.1%}"
        fpi = "n/a" if g.get("fpi_p_home") is None else f"{g['fpi_p_home']:.1%}"
        print(f"  {g['away']} @ {g['home']}: margin_platt {g['home']} {p:.1%} -> {pick} ({pp:.1%}); "
              f"elo {g['p_elo']:.1%}; market {mk}; FPI {fpi}")


def score(args):
    data, _ = h.load_all(True)
    s = ev.score_freezes(data)
    if s.empty:
        print("No archived freezes have completed games yet.")
        return
    y = s["y_home_win"].to_numpy(float)
    print(f"Prospective record: {len(s)} games from {s['file'].nunique()} freezes")
    for m in ev.MODELS:
        r = ev.metrics(y, s[f"p_{m}"].to_numpy())
        print(f"  {m:<16} LL {r['log_loss']:.4f}  Brier {r['brier']:.4f}  acc {r['accuracy']:.3f}")
    for col in ("market_p_home_at_freeze", "fpi_p_home"):
        sub = s[s[col].notna()]
        if len(sub):
            r = ev.metrics(sub["y_home_win"].to_numpy(float), sub[col].to_numpy(float))
            print(f"  {col:<24} LL {r['log_loss']:.4f}  n={r['n']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["backtest", "freeze", "score"])
    ap.add_argument("--refresh", action="store_true", help="re-fetch cached completed seasons")
    args = ap.parse_args()
    {"backtest": backtest, "freeze": freeze, "score": score}[args.command](args)


if __name__ == "__main__":
    main()
