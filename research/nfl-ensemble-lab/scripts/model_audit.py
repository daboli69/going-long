"""Error breakdown of the frozen pre-kickoff game predictions against results.

Reads only snapshots written before kickoff (lab.tracker.latest_prekickoff_snapshots) and games.csv.
Writes reports/model_audit/AUDIT.md and audit.json. No model is changed or refit here.

A slice is called a "repeatable weakness" only if all hold: n >= 8, Holm-adjusted p < 0.10 across every
slice tested, and the bias has the same sign in the earlier and later half of the weeks. Anything else is
reported as noise. With a few dozen games nothing is expected to pass; the script says so instead of
ranking the biggest misses.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import tracker  # noqa: E402
from lab.config import LAB_ROOT, RAW_DIR, SNAPSHOTS_DIR  # noqa: E402

OUT = LAB_ROOT / "reports" / "model_audit"
RNG = np.random.default_rng(20261109)


def build() -> pd.DataFrame:
    games = pd.read_csv(RAW_DIR / "games.csv").set_index("game_id")
    rows = []
    for gid, e in tracker.latest_prekickoff_snapshots().items():
        g = games.loc[gid]
        if pd.isna(g.home_score):
            continue
        s = json.loads((SNAPSHOTS_DIR / e["path"].replace("\\", "/")).read_text(encoding="utf-8"))
        m = s.get("market_at_snapshot") or {}
        rows.append({"game_id": gid, "week": int(e["week"]), "home": g.home_team, "away": g.away_team,
                     "p_home": s["p_champion"], "margin_pred": s["margin_ensemble"],
                     "p_mkt": m.get("p_home_novig"), "spread": m.get("spread_line"),
                     "margin": g.home_score - g.away_score, "stale": bool(s.get("stale_data"))})
    d = pd.DataFrame(rows)
    d["y"] = (d.margin > 0).astype(float).where(d.margin != 0, 0.5)
    return d


def team_view(d: pd.DataFrame) -> pd.DataFrame:
    """One row per team per game, so a team's bias is measured from its own side."""
    h = d.assign(team=d.home, opp=d.away, role="home", p=d.p_home, pm=d.p_mkt, y_t=d.y, m_pred=d.margin_pred,
                 m_act=d.margin, m_line=d.spread)
    a = d.assign(team=d.away, opp=d.home, role="away", p=1 - d.p_home, pm=1 - d.p_mkt, y_t=1 - d.y,
                 m_pred=-d.margin_pred, m_act=-d.margin, m_line=-d.spread)
    return pd.concat([h, a], ignore_index=True)


def bin_label(x: pd.Series, edges: list[float]) -> pd.Series:
    return pd.cut(x, edges, include_lowest=True).astype(str)


def slice_stats(t: pd.DataFrame, by: str, label: str, metric: str) -> list[dict]:
    out = []
    early = t.week <= t.week.median()
    for k, grp in t.groupby(by):
        if len(grp) < 4:
            continue
        r = grp[metric]
        mean, se = r.mean(), r.std(ddof=1) / np.sqrt(len(r))
        p = 2 * (1 - stats.t.cdf(abs(mean / se), len(r) - 1)) if se > 0 else 1.0
        halves = [grp[early.loc[grp.index]][metric].mean(), grp[~early.loc[grp.index]][metric].mean()]
        out.append({"slice": label, "value": str(k), "n": int(len(grp)), "bias": float(mean), "se": float(se),
                    "p": float(p), "same_sign_halves": bool(np.isfinite(halves).all() and halves[0] * halves[1] > 0)})
    return out


def holm(rows: list[dict]) -> None:
    order = sorted(range(len(rows)), key=lambda i: rows[i]["p"])
    m, run = len(rows), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * rows[i]["p"]))
        rows[i]["p_holm"] = run


def paired_boot(a: np.ndarray, b: np.ndarray, n: int = 5000) -> tuple[float, float, float]:
    diff = a - b
    idx = RNG.integers(0, len(diff), (n, len(diff)))
    bs = diff[idx].mean(axis=1)
    return float(diff.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main() -> None:
    d = build()
    d = d.dropna(subset=["p_mkt", "spread"]).reset_index(drop=True)
    n = len(d)
    brier_m, brier_k = (d.p_home - d.y) ** 2, (d.p_mkt - d.y) ** 2
    ll = lambda p: -(d.y * np.log(p) + (1 - d.y) * np.log(1 - p))  # noqa: E731
    res = {"n_games": n, "weeks": sorted(d.week.unique().tolist()), "stale_games": int(d.stale.sum())}
    res["brier"] = {"model": float(brier_m.mean()), "market_novig": float(brier_k.mean()),
                    "model_minus_market": paired_boot(brier_m.to_numpy(), brier_k.to_numpy())}
    res["logloss"] = {"model": float(ll(d.p_home).mean()), "market_novig": float(ll(d.p_mkt).mean()),
                      "model_minus_market": paired_boot(ll(d.p_home).to_numpy(), ll(d.p_mkt).to_numpy())}
    res["margin_mae"] = {"model": float((d.margin - d.margin_pred).abs().mean()),
                         "market_line": float((d.margin - d.spread).abs().mean())}
    res["margin_bias_home"] = {"model": float((d.margin - d.margin_pred).mean()), "market_line": float((d.margin - d.spread).mean())}
    res["home_win_rate"] = float((d.y).mean())
    res["mean_p_home"] = float(d.p_home.mean())

    # One row per game for every slice except team, so no game is counted twice.
    d["p_err"] = d.p_home - d.y                   # positive: model rated the home side too high
    d["m_err"] = d.margin_pred - d.margin         # positive: model home margin too high
    d["p_bin"] = bin_label(d.p_home, [0, 0.35, 0.5, 0.65, 1.0])
    d["line_bin"] = bin_label(d.spread, [-30, -7, -3, 3, 7, 30])
    d["side"] = np.where(d.p_home >= 0.5, "model picks home", "model picks away")
    d["gap_bin"] = bin_label(d.p_home - d.p_mkt, [-1, -0.10, -0.05, 0.05, 0.10, 1])
    d["home_all"] = "all games (home side)"
    t = team_view(d)
    t["p_err"] = t.p - t.y_t                      # positive: model overrated the team
    t["m_err"] = t.m_pred - t.m_act
    t["week"] = t.week

    rows = []
    for metric, name in (("p_err", "win prob"), ("m_err", "margin pts")):
        for r in slice_stats(t, "team", "team", metric):
            r["metric"] = name
            rows.append(r)
        for by, lab in (("home_all", "home side overall"), ("p_bin", "home win prob range"),
                        ("line_bin", "market spread (home view)"), ("side", "model side"),
                        ("gap_bin", "model minus market home prob"), ("week", "week")):
            for r in slice_stats(d, by, lab, metric):
                r["metric"] = name
                rows.append(r)
    holm(rows)
    res["slices_tested"] = len(rows)
    res["repeatable"] = [r for r in rows if r["n"] >= 8 and r["p_holm"] < 0.10 and r["same_sign_halves"]]
    res["nominal_p05_before_holm"] = sum(r["p"] < 0.05 for r in rows)
    res["expected_by_chance"] = round(0.05 * len(rows), 1)
    res["home_bias"] = {"win_prob": float(d.p_err.mean()), "margin": float(d.m_err.mean())}

    # Model rate on the model's own underdog picks vs what the price said
    big = d[(d.p_home - d.p_mkt).abs() >= 0.05]
    pick_home = big.p_home > big.p_mkt
    won = np.where(pick_home, big.y, 1 - big.y)
    res["disagree_ge_5pts"] = {"n": int(len(big)), "model_side_win_rate": float(np.mean(won)),
                               "avg_market_prob_of_that_side": float(np.where(pick_home, big.p_mkt, 1 - big.p_mkt).mean()),
                               "avg_model_prob_of_that_side": float(np.where(pick_home, big.p_home, 1 - big.p_home).mean())}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit.json").write_text(json.dumps({"summary": res, "slices": rows}, indent=1), encoding="utf-8")
    top = sorted(rows, key=lambda r: r["p"])[:8]
    top += [r for r in rows if r["slice"] == "home side overall" and r not in top]
    top += [r for r in res["repeatable"] if r not in top]
    md = [f"# Model audit, frozen pre-kickoff game predictions",
          f"Games: {n} (weeks {res['weeks'][0]} to {res['weeks'][-1]} of 2026), stale-data snapshots: {res['stale_games']}.",
          "", "## Accuracy against the market (no-vig moneyline)",
          f"- Brier: model {res['brier']['model']:.4f}, market {res['brier']['market_novig']:.4f}; difference {res['brier']['model_minus_market'][0]:+.4f} (95% bootstrap {res['brier']['model_minus_market'][1]:+.4f} to {res['brier']['model_minus_market'][2]:+.4f}). Positive means the model is worse.",
          f"- Log loss: model {res['logloss']['model']:.4f}, market {res['logloss']['market_novig']:.4f}; difference {res['logloss']['model_minus_market'][0]:+.4f} ({res['logloss']['model_minus_market'][1]:+.4f} to {res['logloss']['model_minus_market'][2]:+.4f}).",
          f"- Margin MAE: model {res['margin_mae']['model']:.2f}, market spread {res['margin_mae']['market_line']:.2f}.",
          f"- Home margin bias (actual minus predicted): model {res['margin_bias_home']['model']:+.2f}, market {res['margin_bias_home']['market_line']:+.2f}. Home win rate {res['home_win_rate']:.3f} against mean model p_home {res['mean_p_home']:.3f}.",
          f"- Where the model and the price disagree by 5 points or more ({res['disagree_ge_5pts']['n']} games): the model's side won {res['disagree_ge_5pts']['model_side_win_rate']:.1%}; the model gave that side {res['disagree_ge_5pts']['avg_model_prob_of_that_side']:.1%}, the market {res['disagree_ge_5pts']['avg_market_prob_of_that_side']:.1%}.",
          "", "## Systematic over or under estimation",
          f"Home side: the model's mean win probability exceeded the home win rate by {res['home_bias']['win_prob']:+.3f} and its home margin exceeded the actual by {res['home_bias']['margin']:+.2f} points. Opponent slices are not tested separately: they are the mirror of the team slices for the same games.",
          "", "## Random variance or repeatable weakness",
          f"{res['slices_tested']} slices were tested (team, home side overall, projection range, spread, model side, model-minus-market gap, week). {res['nominal_p05_before_holm']} reached p < 0.05 before correction; about {res['expected_by_chance']} would by chance alone.",
          f"Slices that pass the repeatable test (n >= 8, Holm p < 0.10, same sign in both halves): **{len(res['repeatable'])}**.",
          "", "Lowest raw p-values, plus the home-side-overall rows and every slice that passed (nothing hidden):", "",
          "| metric | slice | value | n | bias | p | Holm p | same sign both halves |", "|---|---|---|---|---|---|---|---|"]
    for r in top:
        md.append(f"| {r['metric']} | {r['slice']} | {r['value']} | {r['n']} | {r['bias']:+.3f} | {r['p']:.3f} | {r['p_holm']:.2f} | {r['same_sign_halves']} |")
    md += ["", "## What passed",
           "A slice that passes is a hypothesis, not a finding: it was found by searching 72 cells on 4 weeks of games. It becomes a candidate only if it is written down now and tested on weeks that have not been played yet.",
           "", "## Reading this",
           "A positive win-prob bias means the model rated that group higher than results supported. With this few games a team-level bias is mostly noise: one result moves a team's mean by a few points.",
           "Findings only count after they hold on games the audit has not seen: the next weeks' frozen snapshots are the held-out set, and any change to the model goes through the Champion/Challenger gate in MODEL_RESEARCH.md."]
    (OUT / "AUDIT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
