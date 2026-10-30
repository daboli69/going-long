"""Experiment C: usage before yards (docs/MARKET_NEWS_PREREGISTRATION.md, commit 396af66a). All local.

  python scripts/usage_study.py pilot      # 2018-2020: power only
  python scripts/usage_study.py run        # primary look 2021-2023
  python scripts/usage_study.py confirm    # untouched 2024 confirmation (only after the primary result is committed)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab import forecast_core as fc  # noqa: E402
from lab import homewin_eval as ev  # noqa: E402
from lab.config import LAB_ROOT, RAW_DIR  # noqa: E402
from lab.ingest import normalize_team  # noqa: E402

OUT = LAB_ROOT / "reports" / "usage"
HALF_LIFE, LOOKBACK, MIN_SAME_SEASON = 4.0, 6, 3
AVAIL_W = {"Out": 0.0, "Injured Reserve": 0.0, "Doubtful": 0.05}
SESOI, A2 = 0.005, 0.05 / 2


def log(m):
    print(m, flush=True)


def load_counts(seasons):
    parts = []
    cols = ["game_id", "season", "week", "season_type", "posteam", "pass_attempt", "rush_attempt", "receiver_player_id", "rusher_player_id",
            "qb_scramble", "qb_kneel", "two_point_attempt"]
    for s in seasons:
        p = pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=cols)
        p = p[(p["season_type"] == "REG") & p["posteam"].notna() & (p["two_point_attempt"] != 1)].copy()
        p["posteam"] = p["posteam"].map(normalize_team)
        t = p[(p["pass_attempt"] == 1) & p["receiver_player_id"].notna()].groupby(["season", "week", "posteam", "receiver_player_id"]).size().rename("tgt")
        c = p[(p["rush_attempt"] == 1) & p["rusher_player_id"].notna() & (p["qb_scramble"] != 1) & (p["qb_kneel"] != 1)] \
            .groupby(["season", "week", "posteam", "rusher_player_id"]).size().rename("car")
        t.index.names = c.index.names = ["season", "week", "team", "pid"]
        parts.append(pd.concat([t, c], axis=1).fillna(0).reset_index())
    return pd.concat(parts, ignore_index=True)


def load_active(seasons):
    act = defaultdict(set)
    for s in seasons:
        r = pd.read_parquet(RAW_DIR / f"roster_weekly_{s}.parquet", columns=["week", "team", "gsis_id", "status"])
        r = r[(r["status"] == "ACT") & r["gsis_id"].notna()]
        for (w, t), g in r.groupby(["week", "team"]):
            try:
                act[(s, int(w), normalize_team(t))] = set(g["gsis_id"])
            except ValueError:
                pass
    return act


def load_reports(seasons, kickoff):
    """{(season, week, team): {gsis_id: status}} using only rows with date_modified strictly before that team's kickoff."""
    rep = {}
    for s in seasons:
        d = pd.read_parquet(RAW_DIR / f"injuries_{s}.parquet", columns=["season", "week", "team", "gsis_id", "report_status", "date_modified"])
        d["team"] = d["team"].map(lambda x: normalize_team(x) if isinstance(x, str) else None)
        d["dm"] = pd.to_datetime(d["date_modified"], utc=True, errors="coerce")
        d = d.dropna(subset=["team", "gsis_id", "dm"])
        for (w, t), g in d.groupby(["week", "team"]):
            ko = kickoff.get((s, int(w), t))
            if ko is None:
                continue
            g = g[g["dm"] < ko].sort_values("dm").drop_duplicates("gsis_id", keep="last")
            rep[(s, int(w), t)] = dict(zip(g["gsis_id"], g["report_status"]))
    return rep


def kickoff_map():
    G = fc.games_frame()
    out = {}
    for r in G.itertuples(index=False):
        out[(int(r.season), int(r.week), r.home)] = r.kickoff_utc
        out[(int(r.season), int(r.week), r.away)] = r.kickoff_utc
    return out


def probs(prior, avail, p_other):
    z = {i: prior[i] * avail.get(i, 1.0) for i in prior}
    tot = sum(z.values())
    if tot <= 0:
        return None
    return {i: (1 - p_other) * v / tot for i, v in z.items()}, p_other


def ll(realized, pr):
    """Multinomial log likelihood of realized counts; non-candidates go to the 'other' bucket."""
    p, p_other = pr
    out, other = 0.0, 0.0
    for i, n in realized.items():
        if i in p:
            out += n * np.log(max(p[i], 1e-12))
        else:
            other += n
    return out + other * np.log(max(p_other, 1e-12))


def evaluate(eval_seasons):
    seasons_all = list(range(min(eval_seasons) - 1, max(eval_seasons) + 1))
    counts = load_counts(seasons_all)
    kick = kickoff_map()
    act = load_active(seasons_all)
    reports = load_reports(seasons_all, kick)
    by = {k: g for k, g in counts.groupby(["season", "week", "team"])}
    team_games = defaultdict(list)
    for (s, w, t) in sorted(by):
        team_games[t].append((s, w))
    rows = []
    for t, games in team_games.items():
        for gi, (s, w) in enumerate(games):
            if s not in eval_seasons or gi < LOOKBACK:
                continue
            prev = games[gi - LOOKBACK:gi]
            if sum(1 for (ps, _) in prev if ps == s) < MIN_SAME_SEASON:
                continue
            wts = np.array([0.5 ** ((LOOKBACK - 1 - k) / HALF_LIFE) for k in range(LOOKBACK)])
            row = {"season": s, "week": w, "team": t}
            for stat in ("tgt", "car"):
                tot_k = np.array([by[(ps, pw, t)][stat].sum() for (ps, pw) in prev], float)
                if tot_k.min() == 0:
                    continue
                cand = {i for (ps, pw) in prev for i in by[(ps, pw, t)].loc[by[(ps, pw, t)][stat] > 0, "pid"]}
                share = {i: np.array([float(by[(ps, pw, t)].set_index("pid")[stat].get(i, 0.0)) for (ps, pw) in prev]) / tot_k for i in cand}
                active = {i: np.array([1.0 if i in act.get((ps, pw, t), set()) else 0.0 for (ps, pw) in prev]) for i in cand}
                cand_sum = sum(share.values())
                p_other = float((wts * (1 - cand_sum)).sum() / wts.sum())
                p_other = min(max(p_other, 0.005), 0.5)
                s0 = {i: float((wts * share[i]).sum() / wts.sum()) for i in cand}
                s1 = {}
                for i in cand:
                    aw = wts * active[i]
                    s1[i] = float((aw * share[i]).sum() / aw.sum()) if aw.sum() > 0 else s0[i]
                cur = by.get((s, w, t))
                if cur is None:
                    continue
                realized = dict(zip(cur["pid"], cur[stat]))
                n = float(sum(realized.values()))
                if n == 0:
                    continue
                rep = reports.get((s, w, t), {})
                a1 = {i: AVAIL_W.get(rep.get(i), 1.0) for i in cand}
                a2 = {i: 1.0 if i in act.get((s, w, t), set()) else 0.0 for i in cand}
                p0, p1, p2 = probs(s0, {}, p_other), probs(s1, a1, p_other), probs(s1, a2, p_other)
                p1b, p2b = probs(s0, a1, p_other), probs(s0, a2, p_other)          # Amendment 1: availability weights on the naive prior
                if p0 is None or p1 is None or p2 is None or p1b is None or p2b is None:
                    continue
                row[f"n_{stat}"] = n
                row[f"ll0_{stat}"], row[f"ll1_{stat}"], row[f"ll2_{stat}"] = ll(realized, p0) / n, ll(realized, p1) / n, ll(realized, p2) / n
                row[f"ll1b_{stat}"], row[f"ll2b_{stat}"] = ll(realized, p1b) / n, ll(realized, p2b) / n
                rep_ = rep   # Amendment 3: Doubtful arms on the naive prior
                a_d1 = {i: (0.0 if rep_.get(i) in ("Out", "Injured Reserve") else 1.0) for i in cand}
                a_d0 = {i: (0.0 if rep_.get(i) in ("Out", "Injured Reserve", "Doubtful") else 1.0) for i in cand}
                pd1, pd0 = probs(s0, a_d1, p_other), probs(s0, a_d0, p_other)
                if pd1 is not None and pd0 is not None:
                    row[f"lld1_{stat}"], row[f"lld0_{stat}"] = ll(realized, pd1) / n, ll(realized, pd0) / n
                row[f"dbt_{stat}"] = bool(any(rep_.get(i) == "Doubtful" and s0[i] >= 0.05 for i in cand))
                row[f"n_out_{stat}"] = int(sum(1 for i in cand if a1[i] < 1))
                row[f"news_{stat}"] = bool(any(a1[i] < 1 and s0[i] >= 0.05 for i in cand))          # a candidate with >= 5% prior share is reported out
            if "ll0_tgt" in row or "ll0_car" in row:
                rows.append(row)
    return pd.DataFrame(rows)


def wdiff(df, a, b, n):
    d = df[[a, b, n]].dropna()
    w = d[n].to_numpy()
    return df.loc[d.index], ((d[a] - d[b]).to_numpy() * w / w.mean())


def summarize(df, label):
    res = {"label": label, "team_games": int(len(df)), "weeks": int(df[["season", "week"]].drop_duplicates().shape[0])}
    cl = lambda x: (x["season"].astype(str) + "_" + x["week"].astype(str)).to_numpy()  # noqa: E731
    for stat, name in (("tgt", "C1_targets"), ("car", "C2_carries")):
        sub, d = wdiff(df, f"ll1b_{stat}", f"ll0_{stat}", f"n_{stat}")
        sub2, d2 = wdiff(df, f"ll2b_{stat}", f"ll0_{stat}", f"n_{stat}")
        subA, dA = wdiff(df, f"ll1_{stat}", f"ll0_{stat}", f"n_{stat}")
        news = sub[f"news_{stat}"].astype(bool).to_numpy()
        ci = ev.cluster_boot(d, cl(sub), A2)
        res[name] = {"n": int(len(d)), "mean_ll_naive": float(sub[f"ll0_{stat}"].mean()), "mean_ll_availability": float(sub[f"ll1b_{stat}"].mean()),
                     "mean_ll_oracle": float(sub[f"ll2b_{stat}"].mean()), "gain_vs_naive": float(d.mean()), "ci": ci, "ci_level": 1 - A2,
                     "secondary_active_prior_arm_gain": float(dA.mean()), "secondary_active_prior_arm_ci": ev.cluster_boot(dA, cl(subA), A2),
                     "news_games": {"share": float(news.mean()), "n": int(news.sum()), "gain": float(d[news].mean()) if news.any() else None,
                                    "ci": ev.cluster_boot(d[news], cl(sub)[news], A2) if news.sum() > 30 else None,
                                    "oracle_gain": float(d2[news].mean()) if news.any() else None},
                     "improves": bool(ci[0] > 0), "material": bool(ci[0] > 0 and d.mean() >= SESOI), "oracle_gain": float(d2.mean()),
                     "share_of_oracle_gap_captured": float(d.mean() / d2.mean()) if d2.mean() > 0 else None,
                     "games_with_a_reported_out_player": float((sub[f"n_out_{stat}"] > 0).mean())}
        by_s = pd.Series(d).groupby(sub["season"].to_numpy()).mean()
        res[name]["by_season_gain"] = {int(k): float(v) for k, v in by_s.items()}
    return res


def doubtful(args):
    """Amendment 3: Doubtful weight 0 / 0.05 vs the lab's rule (1.0), 2021-2024."""
    df = evaluate(range(2021, 2025))
    df.to_parquet(OUT / "doubtful_frame.parquet")
    alpha = 0.05 / 4
    cl = lambda x: (x["season"].astype(str) + "_" + x["week"].astype(str)).to_numpy()  # noqa: E731
    res = {"prereg": "396af66a Amendment 3", "decision_rule": "both stats: pooled D0-D1 98.75% CI > 0 and each of 2021-2023, 2024 positive", "stats": {}}
    ok = True
    for stat, name in (("tgt", "targets"), ("car", "carries")):
        d = df.dropna(subset=[f"lld1_{stat}", f"lld0_{stat}", f"ll1b_{stat}"]).copy()
        w = d[f"n_{stat}"].to_numpy()
        gain = lambda a, b: (d[a] - d[b]).to_numpy() * w / w.mean()  # noqa: E731
        g0, g05 = gain(f"lld0_{stat}", f"lld1_{stat}"), gain(f"ll1b_{stat}", f"lld1_{stat}")
        early = (d["season"] <= 2023).to_numpy()
        r = {"team_games": int(len(d)), "games_with_doubtful_candidate": float(d[f"dbt_{stat}"].mean()),
             "D0_minus_D1": {"pooled": float(g0.mean()), "ci": ev.cluster_boot(g0, cl(d), alpha), "2021_2023": float(g0[early].mean()), "2024": float(g0[~early].mean())},
             "D05_minus_D1": {"pooled": float(g05.mean()), "ci": ev.cluster_boot(g05, cl(d), alpha), "2021_2023": float(g05[early].mean()), "2024": float(g05[~early].mean())},
             "doubtful_games_only_D0_minus_D1": float(g0[d[f"dbt_{stat}"].to_numpy()].mean()) if d[f"dbt_{stat}"].any() else None}
        r["passes"] = bool(r["D0_minus_D1"]["ci"][0] > 0 and r["D0_minus_D1"]["2021_2023"] > 0 and r["D0_minus_D1"]["2024"] > 0)
        ok &= r["passes"]
        res["stats"][name] = r
        log(f"{name}: games with a Doubtful candidate {r['games_with_doubtful_candidate']:.1%}; D0-D1 pooled {r['D0_minus_D1']['pooled']:+.5f} {r['D0_minus_D1']['ci']} "
            f"(21-23 {r['D0_minus_D1']['2021_2023']:+.5f}, 24 {r['D0_minus_D1']['2024']:+.5f}); D05-D1 {r['D05_minus_D1']['pooled']:+.5f}; Doubtful-games-only {r['doubtful_games_only_D0_minus_D1']} -> passes {r['passes']}")
    res["adopt_doubtful_as_unavailable"] = bool(ok)
    body = json.dumps(res, indent=1, default=str)
    (OUT / "doubtful.json").write_bytes(body.encode("utf-8"))
    log(f"adopt: {ok}. Wrote reports/usage/doubtful.json sha256 {hashlib.sha256(body.encode()).hexdigest()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["pilot", "run", "confirm", "doubtful"])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.command == "doubtful":
        return doubtful(args)
    if args.command == "pilot":
        from props_market_power import mde, week_arrays
        df = evaluate(range(2018, 2021))
        df.to_parquet(OUT / "pilot_frame.parquet")
        rng = np.random.default_rng(0)
        avail = int(evaluate_weeks(range(2021, 2024)))
        out = {"prereg": "396af66a", "pilot_team_games": int(len(df)), "available_weeks_primary": avail, "comparisons": {}}
        for stat, name in (("tgt", "C1_targets"), ("car", "C2_carries")):
            sub, d = wdiff(df, f"ll1b_{stat}", f"ll0_{stat}", f"n_{stat}")
            d0 = d - d.mean()
            s, c = week_arrays(sub, d0)
            row = {"pilot_mean_gain": float(d.mean()), "sd": float(d.std()), "sesoi": SESOI, "mde_by_weeks": {}}
            for W in sorted({avail, 40, 90, 150}):
                row["mde_by_weeks"][str(W)] = mde(s, c, W, A2, -1, rng, hi=0.2)
            m = row["mde_by_weeks"][str(avail)]
            row["decidable_now"] = bool(m <= SESOI)
            row["N_weeks"] = int(np.ceil(avail * (m / SESOI) ** 2)) if m > SESOI else avail
            out["comparisons"][name] = row
            log(f"{name}: pilot gain {d.mean():+.4f} MDE({avail})={m:.4f} SESOI={SESOI} N={row['N_weeks']} decidable_now={row['decidable_now']}")
        body = json.dumps(out, indent=1)
        (OUT / "power.json").write_bytes(body.encode("utf-8"))
        log(f"Wrote reports/usage/power.json sha256 {hashlib.sha256(body.encode()).hexdigest()}")
        return
    seasons = range(2021, 2024) if args.command == "run" else [2024]
    df = evaluate(seasons)
    res = summarize(df, "primary 2021-2023" if args.command == "run" else "untouched confirmation 2024")
    pw = json.loads((OUT / "power.json").read_text(encoding="utf-8"))["comparisons"]
    for k in ("C1_targets", "C2_carries"):
        res[k]["verdict_allowed"] = bool(pw[k]["decidable_now"])
        log(f"{k}: naive {res[k]['mean_ll_naive']:.4f} availability {res[k]['mean_ll_availability']:.4f} oracle {res[k]['mean_ll_oracle']:.4f} | gain {res[k]['gain_vs_naive']:+.4f} "
            f"[{res[k]['ci'][0]:+.4f},{res[k]['ci'][1]:+.4f}] captured {res[k]['share_of_oracle_gap_captured']} verdict_allowed={res[k]['verdict_allowed']}")
    name = "results.json" if args.command == "run" else "confirmation.json"
    body = json.dumps(res, indent=1, default=str)
    (OUT / name).write_bytes(body.encode("utf-8"))
    log(f"Wrote reports/usage/{name} sha256 {hashlib.sha256(body.encode()).hexdigest()}")


def evaluate_weeks(seasons):
    G = fc.games_frame()
    return G[G["season"].isin(list(seasons)) & G["played"]][["season", "week"]].drop_duplicates().shape[0]


if __name__ == "__main__":
    main()
