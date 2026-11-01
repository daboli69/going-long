"""Does knowing who is on injured reserve (and other roster absences) improve what the lab predicts? Tested model by model on games the fit never saw.

    .venv\\Scripts\\python.exe scripts\\availability_check.py

Four tests, each against the old rule that only the official report's "Out" counts:
  A. who plays: four rules scored on regular players in 2025 games, at the Friday report and on game day;
  B. the sampled receiving model: how likely the real target split is when the pool follows each rule (2025 and 2026);
  C. winners: whether the missing-production feature predicts margin errors left by the market and by the lab's own model;
  D. props: whether the saved prospective props projections still list players the roster shows out.
Writes docs/AVAILABILITY_CHECK.md and docs/availability_check.json (aggregate numbers only). Local files only, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import avail_source as A  # noqa: E402
from lab import gamecenter_data as D  # noqa: E402
from lab import recvsim as R  # noqa: E402
from lab import usage as U  # noqa: E402

TRAIN = [(2022, 3, 18), (2023, 3, 18), (2024, 3, 18)]
TEST = {"2025": [(2025, 3, 18)], "2026": [(2026, 3, 7)]}


def boot(d: np.ndarray, draws: int = 2000, seed: int = 9) -> dict:
    idx = np.random.default_rng(seed).integers(0, len(d), (draws, len(d)))
    m = d[idx].mean(1)
    return {"games": int(len(d)), "diff": float(d.mean()), "lo": float(np.percentile(m, 5)), "hi": float(np.percentile(m, 95))}


# --------------------------------------------------------------------------- B: receiving model likelihood by availability rule
def test_b(blk, st, params) -> dict:
    out = {}
    for label, weeks in TEST.items():
        sets = {"official Out only (old rule)": R.make_cases(blk, st, weeks, "official", False, False),
                "availability source, Friday": R.make_cases(blk, st, weeks, "source", False, False),
                "availability source, game day": R.make_cases(blk, st, weeks, "source", True, False)}
        keyed = {k: {(c.season, c.team, c.week): c for c in v} for k, v in sets.items()}
        common = set.intersection(*[set(v) for v in keyed.values()])
        ll = {k: np.array([R.dm_loglik(np.append(v[key].actual_tgt, v[key].other_tgt), R.expected_shares(v[key], params), R.alpha_for(v[key], params)) for key in sorted(common)])
              for k, v in keyed.items()}
        base = ll["official Out only (old rule)"]
        out[label] = {"team_games": len(common), "mean_loglik": {k: float(v.mean()) for k, v in ll.items()},
                      "vs_old": {k: boot(v - base) for k, v in ll.items() if not k.startswith("official")}}
    return out


# --------------------------------------------------------------------------- C: winners
def team_features(blk, st, ug, season, team, week, variant, game_day):
    b = blk.get((season, team))
    w = R.window(b, week) if b else None
    if w is None:
        return np.nan, np.nan
    out = R.out_ids(st, season, team, week, variant, game_day)
    tot = max(w["tgt"].sum(), 1.0)
    lost = sum(w["tgt"][i] for i, p in enumerate(b.pids) if p in out) / tot
    u = U.usage(ug, season, team, week)
    qb_out = 0.0
    if u is not None:
        q = u.players[u.players["att"] > 0].assign(v=lambda x: x["att"] * x["n"])
        if len(q):
            qb_out = float(q.sort_values("v").iloc[-1]["pid"] in out)
    return lost, qb_out


def test_c(blk, st) -> dict:
    ug = U.player_games(range(2021, 2027))
    G = D.games_table()
    G = G[(G["game_type"] == "REG") & G["completed"] & (G["season"] >= 2022) & (G["week"] >= 3)].dropna(subset=["spread_line"])
    wf = pd.read_parquet(D.CACHE_DIR / "homewin_deep" / "forecast_wf.parquet")[["gid", "mu_m"]].rename(columns={"gid": "game_id"})
    G = G.merge(wf, on="game_id", how="left")
    rows = []
    variants = {"official Out only (old rule)": ("official", False), "availability source, Friday": ("source", False), "availability source, game day": ("source", True)}
    for g in G.itertuples():
        row = {"season": g.season, "game_id": g.game_id, "margin": g.home_score - g.away_score, "market": g.spread_line, "model": g.mu_m}
        for name, (v, gd) in variants.items():
            h = team_features(blk, st, ug, g.season, g.home_team, g.week, v, gd)
            a = team_features(blk, st, ug, g.season, g.away_team, g.week, v, gd)
            row[name + "|lost"], row[name + "|qb"] = h[0] - a[0], h[1] - a[1]
        rows.append(row)
    F = pd.DataFrame(rows).dropna()
    out = {}
    for base_name in ("market", "model"):
        res = {}
        for name in variants:
            X = F[[name + "|lost", name + "|qb"]].to_numpy()
            y = (F["margin"] - F[base_name]).to_numpy()
            tr = (F["season"] <= 2024).to_numpy()
            beta = np.linalg.lstsq(np.column_stack([X[tr], np.ones(tr.sum())]), y[tr], rcond=None)[0]
            coef_boot = []
            rng = np.random.default_rng(2)
            for _ in range(500):
                ix = rng.choice(np.flatnonzero(tr), tr.sum())
                coef_boot.append(np.linalg.lstsq(np.column_stack([X[ix], np.ones(len(ix))]), y[ix], rcond=None)[0][:2])
            cb = np.array(coef_boot)
            res[name] = {"coef_lost_share_points": [float(beta[0]), float(np.percentile(cb[:, 0], 5)), float(np.percentile(cb[:, 0], 95))],
                         "coef_qb_out_points": [float(beta[1]), float(np.percentile(cb[:, 1], 5)), float(np.percentile(cb[:, 1], 95))], "tests": {}}
            for label in ("2025", "2026"):
                te = (F["season"] == int(label)).to_numpy()
                pred = np.column_stack([X[te], np.ones(te.sum())]) @ beta
                new, old = (y[te] - pred) ** 2, y[te] ** 2
                res[name]["tests"][label] = {**boot(new - old), "mse_old": float(old.mean()), "mse_new": float(new.mean())}
        out[base_name] = res
    out["games"] = int(len(F))
    return out


# --------------------------------------------------------------------------- D: props pipeline
def test_d(st) -> dict:
    prev = D.preview_table()
    if prev.empty:
        return {}
    s = st[st["season"] == D.SEASON][["week", "team", "gsis_id", "roster", "official"]].drop_duplicates(["week", "team", "gsis_id"])
    p = prev[["game_id", "week", "team", "pid"]].drop_duplicates().rename(columns={"pid": "gsis_id"})
    p["team"] = p["team"].map(A._team)
    m = p.merge(s, on=["week", "team", "gsis_id"], how="left")
    flagged = m["roster"].isin(A.HARD_ROSTER | A.GAME_DAY) | m["official"].isin(["Out", "Doubtful"])
    return {"weeks": sorted(int(w) for w in m["week"].unique()), "player_rows": int(len(m)), "listed_but_out_by_roster_or_report": int(flagged.sum()),
            "by_status": m.loc[flagged, "roster"].fillna("official report").value_counts().to_dict()}


def main():
    seasons = range(2021, 2027)
    blk, st = R.blocks(seasons), A.status_table(seasons)
    tr = R.make_cases(blk, st, TRAIN, "source", True, False)
    params = R.fit(tr)
    result = {"A": A.rule_scores(), "B": test_b(blk, st, params), "C": test_c(blk, st), "D": test_d(st)}
    (ROOT / "docs" / "availability_check.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")

    L = ["# Roster absences (injured reserve and others): what they change", "",
         "Generated by `scripts/availability_check.py`. Every test compares against the old rule, which counts only the official report's \"Out\". "
         "Fits use 2022 to 2024; scores are on 2025 and 2026 games the fit never saw. Aggregate numbers only.", "",
         "Timing: the official report and the weekly roster are weekly snapshots without time stamps inside the week. Official statuses are treated as known "
         "from the Friday report, roster injured reserve, released and retired as known from the start of the week, and \"inactive\" only on game day.", "",
         "## A. Who plays", "", f"Regular players (in at least 3 of their team's last 4 games), 2025: {result['A']['player_weeks']} player-weeks, {result['A']['played_share']:.1%} played. "
         "Log loss: lower is better. \"Expected but absent\" counts player-weeks the rule said would play and did not.", "",
         "| Decision time | Rule | Log loss | Expected but absent | Change in log loss vs old rule (90% interval) |", "|---|---|---|---|---|"]
    for tm, res in result["A"]["timings"].items():
        for n, v in res.items():
            vs = v.get("vs_R0")
            L.append(f"| {'Friday' if tm == 'friday' else 'Game day'} | {n} | {v['log_loss']:.3f} | {v['expected_but_absent']} | " + (f"{vs['diff']:+.3f} ({vs['lo']:+.3f} to {vs['hi']:+.3f})" if vs else "baseline") + " |")
    L += ["", "## B. The sampled receiving model", "",
          "Average log-likelihood of each team's real target split when the pool of expected players follows each rule. Higher is better.", "",
          "| Year | Team-games | Rule | Average log-likelihood | Gain over old rule (90% interval) |", "|---|---|---|---|---|"]
    for label, v in result["B"].items():
        for k, ll in v["mean_loglik"].items():
            g = v["vs_old"].get(k)
            L.append(f"| {label} | {v['team_games']} | {k} | {ll:.2f} | " + (f"{g['diff']:+.2f} ({g['lo']:+.2f} to {g['hi']:+.2f})" if g else "baseline") + " |")
    L += ["", "## C. Winners", "",
          f"{result['C']['games']} games from 2022 to 2026. The feature is the home team's missing share of recent targets minus the away team's, plus whether each team's starting quarterback is out. "
          "It is fitted to the margin each forecast got wrong (actual minus forecast) on 2022 to 2024, then scored on 2025 and 2026. A gain means squared error fell; the interval is 90%.", ""]
    for base_name, label in (("market", "the betting market's spread"), ("model", "the lab's own model margin")):
        L += [f"Against {label}:", "", "| Rule | Points of margin per 10 points of missing target share | Points for a starting quarterback out | Year | Squared error before | After | Change (90% interval) |", "|---|---|---|---|---|---|---|"]
        for name, r in result["C"][base_name].items():
            for yr, t in r["tests"].items():
                L.append(f"| {name} | {0.1 * r['coef_lost_share_points'][0]:+.2f} ({0.1 * r['coef_lost_share_points'][1]:+.2f} to {0.1 * r['coef_lost_share_points'][2]:+.2f}) | "
                         f"{r['coef_qb_out_points'][0]:+.2f} ({r['coef_qb_out_points'][1]:+.2f} to {r['coef_qb_out_points'][2]:+.2f}) | {yr} | {t['mse_old']:.1f} | {t['mse_new']:.1f} | {t['diff']:+.2f} ({t['lo']:+.2f} to {t['hi']:+.2f}) |")
        L.append("")
    d = result["D"]
    if d:
        L += ["## D. Props", "", f"Saved prospective props projections for weeks {d['weeks']}: {d['player_rows']} player rows, {d['listed_but_out_by_roster_or_report']} listed for a player the roster or report shows out "
              f"({json.dumps(d['by_status'])}).", ""]
    (ROOT / "docs" / "AVAILABILITY_CHECK.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
