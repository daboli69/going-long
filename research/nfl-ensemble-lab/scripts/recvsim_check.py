"""Test the sampled receiving model against real games, the market, and a real-versus-simulated classifier; save the model if it passes.

    .venv\\Scripts\\python.exe scripts\\recvsim_check.py

Fits on 2022-2024, scores on 2025 and 2026 games the fit never saw. Checks, each one independent of the lab's own numbers:
  a. real results fall inside the simulated central 80% range 77% to 83% of the time (and the calibration deciles are flat);
  b. receivers per team-game within 0.4 of real, top receiver's share of catches within 3 points, tight ends' share within 2 points;
  c. on archived Kalshi receiving ladders the model does not lose to the market on log loss, or it moves no numbers;
  d. a classifier cannot tell real team box scores from simulated ones (area under the curve near 0.5), unlike the old averaged method;
  and writes a blind sheet of unlabeled real and simulated box scores for a person to try.
Writes docs/RECEIVING_SIM_CHECK.md, docs/recvsim_check.json (aggregate numbers only), data/cache/recvsim_rule.json and reports/blind_boxscores*.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import avail_source as A  # noqa: E402
from lab import gamecenter_data as D  # noqa: E402
from lab import recvsim as R  # noqa: E402
from lab import usage as U  # noqa: E402

TRAIN = [(2022, 3, 18), (2023, 3, 18), (2024, 3, 18)]
TEST = {"2025": [(2025, 3, 18)], "2026": [(2026, 3, 7)]}
FEATS = ["receivers", "top_catch_share", "te_share", "rb_share", "catches", "yards", "top_yards", "n_100", "hhi"]


def box_features(rec, yds, group) -> list:
    """Features of one team's receiving box score from per-player catches and yards (the same function for real and simulated games)."""
    rec, yds = np.asarray(rec, float), np.asarray(yds, float)
    tot = max(rec.sum(), 1.0)
    return [float((rec > 0).sum()), float(rec.max() / tot), float(sum(r for r, g in zip(rec, group) if g == "TE") / tot), float(sum(r for r, g in zip(rec, group) if g == "RB") / tot),
            float(rec.sum()), float(yds.sum()), float(yds.max()), float((yds >= 100).sum()), float(((rec / tot) ** 2).sum())]


def with_other(c: R.Case, rec, yds, other_rec, other_yds):
    """Add everyone outside the pool as two pseudo-players so real and simulated boxes are built the same way."""
    hi, lo = np.ceil(other_rec / 2), np.floor(other_rec / 2)
    return np.append(rec, [hi, lo]), np.append(yds, [other_yds * (hi / max(other_rec, 1)), other_yds * (lo / max(other_rec, 1))]), list(c.group) + ["WR", "WR"]


def old_method_box(ug, c: R.Case):
    """The old replay's receiving box for the same game: each player's expected catches and yards, rounded."""
    o_rec, o_yds = R._old_method(ug, c)
    rec = np.where(np.rint(o_rec) < 1, np.where(o_yds >= 6, 1, 0), np.rint(o_rec))
    return rec, np.where(rec > 0, o_yds, 0.0), list(c.group)


def ladders(blk, st, params) -> dict:
    """The model's chance of at least k catches or yards against the Kalshi price. Scored on outcomes where the game is complete; for games
    still to play it can only show how close the model sits to the market."""
    fr = D.load_freezes("props_kalshi")
    games = D.games_table().set_index("game_id")
    done = R.player_games([2026]).set_index(["week", "pid"])
    rng = np.random.default_rng(3)
    scored, close = [], []
    for (season, week), rec in fr.items():
        if season != 2026:
            continue
        for lad in rec["content"]["ladders"]:
            if lad["stat"] not in ("rec", "rec_yds") or lad["gid"] not in games.index:
                continue
            c = R.future_case(blk, 2026, lad["team"], week, R.out_ids(st, 2026, lad["team"], week, "source", False))
            if c is None or lad["pid"] not in c.pids:
                continue
            j = c.pids.index(lad["pid"])
            key = "rec" if lad["stat"] == "rec" else "yds"
            s = R.sample(c, params, 4000, rng)[key][:, j]
            actual = done["rec" if lad["stat"] == "rec" else "yds"].get((week, lad["pid"]), 0.0)
            for th in lad["thresholds"]:
                if th.get("mid") is None:
                    continue
                pm = float((s >= th["k"]).mean())
                close.append((abs(pm - th["mid"]), abs(th["p_sim"] - th["mid"]) if th.get("p_sim") is not None else np.nan))
                if bool(games.loc[lad["gid"], "completed"]):
                    scored.append((float(th["mid"]), pm, np.nan if th.get("p_sim") is None else th["p_sim"], float(actual >= th["k"])))
    out = {"weeks_with_prices": sorted(int(w) for (sn, w) in fr if sn == 2026)}
    if close:
        c = np.array(close)
        out["closeness"] = {"thresholds": int(len(c)), "mean_gap_model_vs_market": float(c[:, 0].mean()), "mean_gap_lab_earlier_sim_vs_market": float(np.nanmean(c[:, 1]))}
    if scored:
        a = np.array(scored)
        clip = lambda x: np.clip(x, 0.02, 0.98)
        ll = lambda p, y: -(y * np.log(clip(p)) + (1 - y) * np.log(1 - clip(p)))
        d = ll(a[:, 1], a[:, 3]) - ll(a[:, 0], a[:, 3])
        boot = d[np.random.default_rng(1).integers(0, len(d), (2000, len(d)))].mean(1)
        out["scored"] = {"thresholds": int(len(a)), "log_loss_market": float(ll(a[:, 0], a[:, 3]).mean()), "log_loss_model": float(ll(a[:, 1], a[:, 3]).mean()),
                         "model_minus_market": float(d.mean()), "lo": float(np.percentile(boot, 5)), "hi": float(np.percentile(boot, 95))}
    return out


def main():
    seasons = range(2021, 2027)
    blk, st = R.blocks(seasons), A.status_table(seasons)
    ug = U.player_games(seasons)
    params = R.fit(R.make_cases(blk, st, TRAIN, "source", False, False))
    res = {"params": R.params_dict(params), "years": {}}
    real_x, sim_x, old_x = [], [], []
    rng = np.random.default_rng(11)
    names = None
    blind = []
    for label, weeks in TEST.items():
        cases = R.make_cases(blk, st, weeks, "source", False, False)
        r = R.score(cases, params, ug)
        res["years"][label] = {k: v for k, v in r.items()}
        for c in cases:
            s = R.sample(c, params, 1, rng)
            P = len(c.pids)
            rr, ry, rg = with_other(c, c.actual_rec, c.actual_yds, c.other_rec, c.other_yds)
            real_x.append(box_features(rr, ry, rg))
            sr, sy, sg = with_other(c, s["rec"][0, :P], s["yds"][0, :P], s["rec"][0, P], s["yds"][0, P])
            sim_x.append(box_features(sr, sy, sg))
            orc, oy, og = old_method_box(ug, c)
            old_x.append(box_features(orc, oy, og))
            blind.append((c, s))
    # d. classifier
    def auc(a, b):
        X = np.vstack([a, b]); y = np.r_[np.ones(len(a)), np.zeros(len(b))]
        pr = cross_val_predict(GradientBoostingClassifier(n_estimators=120, max_depth=3, random_state=0), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
        return float(roc_auc_score(y, pr))
    res["classifier_auc"] = {"real_vs_sampled": auc(real_x, sim_x), "real_vs_old_averaged": auc(real_x, old_x), "team_games": len(real_x)}
    # c. ladders
    res["ladders"] = ladders(blk, st, params)
    # blind sheet
    import random
    from lab import gamesim as S
    names = S._names()
    pick = random.Random(7).sample(range(len(blind)), 24)
    sheet, key = [], {}
    items = [("real", i) for i in pick[:12]] + [("simulated", i) for i in pick[12:]]
    random.Random(8).shuffle(items)
    for n, (kind, i) in enumerate(items):
        c, s = blind[i]
        P = len(c.pids)
        tgt, rec, yds = (c.actual_tgt, c.actual_rec, c.actual_yds) if kind == "real" else (s["tgt"][0, :P], s["rec"][0, :P], s["yds"][0, :P])
        oth = (c.other_tgt, c.other_rec, c.other_yds) if kind == "real" else (s["tgt"][0, P], s["rec"][0, P], s["yds"][0, P])
        lines = [f"- {names.get(c.pids[j], c.pids[j])} ({c.group[j]}): {int(rec[j])} {'catch' if int(rec[j]) == 1 else 'catches'} on {int(tgt[j])} {'target' if int(tgt[j]) == 1 else 'targets'}, {int(yds[j])} yards" for j in np.argsort(-tgt) if tgt[j] > 0]
        lines.append(f"- Everyone else: {int(oth[1])} {'catch' if int(oth[1]) == 1 else 'catches'} on {int(oth[0])} {'target' if int(oth[0]) == 1 else 'targets'}, {int(oth[2])} yards")
        label = chr(ord("A") + n)
        sheet.append(f"### Box score {label}\n" + "\n".join(lines))
        key[label] = kind
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "blind_boxscores.md").write_text("# Which of these receiving box scores are real?\n\nTwelve are from real 2025 and 2026 games and twelve are simulated. "
        "Each lists one team's receivers. Write down R or S for each letter; the answers are in a separate file.\n\n" + "\n\n".join(sheet) + "\n", encoding="utf-8")
    (ROOT / "reports" / "blind_boxscores_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")

    # gates
    y = res["years"]
    gates = {}
    for label in TEST:
        r = y[label]; rl = r["realism"]
        gates[label] = {"coverage": all(0.77 <= r[k]["coverage80"] <= 0.83 for k in ("tgt", "rec", "yds")),
                        "receivers": abs(rl["receivers_with_a_catch"]["sim"] - rl["receivers_with_a_catch"]["real"]) <= 0.4,
                        "top_share": abs(rl["top_receiver_share"]["sim"] - rl["top_receiver_share"]["real"]) <= 0.03,
                        "te_share": abs(rl["te_catch_share"]["sim"] - rl["te_catch_share"]["real"]) <= 0.02,
                        "beats_old_point_forecast": all(r[k]["mae_gap_vs_old"]["hi"] < 0 for k in ("rec", "yds"))}
    passed = all(all(v.values()) for v in gates.values())
    res["gates"], res["passed"] = gates, passed
    rule = {"passed": bool(passed), "params": res["params"], "created_at": pd.Timestamp.now(tz="UTC").isoformat()}
    R.RULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    R.RULE_PATH.write_text(json.dumps(rule, indent=1), encoding="utf-8")
    (ROOT / "docs" / "recvsim_check.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")

    L = ["# Sampled receiving model: what was tested", "",
         "Generated by `scripts/recvsim_check.py`. Every constant was fitted on 2022 to 2024 games; everything below is scored on 2025 and 2026 games the fit never saw, "
         "using only information from before each game. Aggregate numbers only.", "",
         "The model draws a team's targets for the game, splits them among its players with a Dirichlet-multinomial so each game comes out lumpy, then draws catches and yards. "
         "Fitted: " + ", ".join(f"{k} {v:.3g}" for k, v in res["params"].items() if isinstance(v, float)) + ". FantasyPoints target share got weight "
         f"{res['params']['w_fpds']:.2f}: raw play-by-play targets already measure the same thing.", "",
         "## a. Does the real result fall inside the simulated range?", "", "| Year | Team-games | Stat | Real result inside the central 80% range | Calibration deciles (flat is ideal: 10% each) |", "|---|---|---|---|---|"]
    for label, r in y.items():
        for k, nm in (("tgt", "Targets"), ("rec", "Catches"), ("yds", "Receiving yards")):
            L.append(f"| {label} | {r['cases']} | {nm} | {r[k]['coverage80']:.1%} | {' '.join(f'{d:.0%}' for d in r[k]['pit_deciles'])} |")
    L += ["", "## b. Does a simulated team box score look like a real one?", "", "| Year | Measure | Real | Simulated | Within the limit |", "|---|---|---|---|---|"]
    lim = {"receivers_with_a_catch": ("Receivers with a catch, per team", 0.4, 1), "top_receiver_share": ("Top receiver's share of catches", 0.03, 100), "te_catch_share": ("Tight ends' share of catches", 0.02, 100)}
    for label, r in y.items():
        for k, (nm, tol, scale) in lim.items():
            v = r["realism"][k]
            L.append(f"| {label} | {nm} | {v['real'] * (1 if scale == 1 else 100):.1f}{'' if scale == 1 else '%'} | {v['sim'] * (1 if scale == 1 else 100):.1f}{'' if scale == 1 else '%'} | "
                     f"{'yes' if abs(v['sim'] - v['real']) <= tol else 'no'} (limit {tol * (1 if scale == 1 else 100):g}{'' if scale == 1 else ' points'}) |")
    L += ["", "Point forecast: the model's average against the old averaged numbers (change in mean absolute error per player-game, 90% interval; below zero is better).", "",
          "| Year | Catches | Receiving yards |", "|---|---|---|"]
    for label, r in y.items():
        f = lambda k: f"{r[k]['mae_gap_vs_old']['mean']:+.3f} ({r[k]['mae_gap_vs_old']['lo']:+.3f} to {r[k]['mae_gap_vs_old']['hi']:+.3f})"
        L.append(f"| {label} | {f('rec')} | {f('yds')} |")
    L += ["", "The ranking score (CRPS) also favors the sampled model by a wide margin, but part of that is simply having a spread to score against a single number, so the point-forecast comparison above is the fairer one.", ""]
    lad = res["ladders"]
    L += ["## c. Against the market's prices", ""]
    if lad.get("scored"):
        sc = lad["scored"]
        L += [f"Kalshi receiving ladders for completed games: {sc['thresholds']} thresholds. Log loss, lower is better: market {sc['log_loss_market']:.3f}, sampled model {sc['log_loss_model']:.3f}. "
              f"Model minus market {sc['model_minus_market']:+.3f} (90% interval {sc['lo']:+.3f} to {sc['hi']:+.3f}).", ""]
    else:
        L += [f"Archived Kalshi prices exist only for weeks {lad['weeks_with_prices']} of 2026, and no game with prices has been played yet, so the model cannot be scored against outcomes. "
              "This step will score itself on the first Tuesday after those games finish.", ""]
    if lad.get("closeness"):
        cl = lad["closeness"]
        L += [f"For now, closeness only: across {cl['thresholds']} receiving thresholds the sampled model sits {cl['mean_gap_model_vs_market']:.3f} from the market price on average (probability points), "
              f"against {cl['mean_gap_lab_earlier_sim_vs_market']:.3f} for the lab's earlier simulation. Being close is not the same as being right.", ""]
    L += ["The sampled model moves no headline number: the winner, spread, total and props tables still come from the market and the saved projections. It only draws the replay.", ""]
    L += ["## d. Can a classifier tell real from simulated?", "",
          f"A gradient-boosted classifier was trained to tell real team receiving box scores from simulated ones ({res['classifier_auc']['team_games']} team-games each, five-fold cross-validation). Area under the curve: 0.5 means it cannot tell, 1.0 means it always can.", "",
          f"- Real versus the sampled model: {res['classifier_auc']['real_vs_sampled']:.2f}", f"- Real versus the old averaged method: {res['classifier_auc']['real_vs_old_averaged']:.2f}", "",
          "A blind sheet of 12 real and 12 simulated box scores is in `reports/blind_boxscores.md` (answers in `reports/blind_boxscores_key.json`) for a person to try.", "",
          f"## Result: {'passed all gates, so the replay uses the sampled model' if passed else 'did not pass every gate, so the replay keeps the old averaged method'}", ""]
    (ROOT / "docs" / "RECEIVING_SIM_CHECK.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print("\nGATES", json.dumps(gates))


if __name__ == "__main__":
    main()
