"""pull / replay / score stages for scripts/props_kalshi.py (protocol commit 31af0b08)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import binomtest, chisquare

from props_kalshi import EMPTY_INJ, _scored_weeks, _write, actual_stats, ladder_crps, log
from lab import homewin_deep as h
from lab import homewin_eval as ev
from lab import homewin_v2 as v2
from lab import kalshi as K
from lab import props_kalshi as pk
from lab.props import game as G
from lab.props import weekly as W


def _games():
    games, _ = h.load_games()
    return games, W.load_games()


def pull(args):
    games, gcsv = _games()
    sw = _scored_weeks(gcsv)
    keep = set(zip(sw["season"], sw["week"]))
    scope = pk.scope_markets(games)
    meta = games.set_index("gid")[["season", "week", "home", "away"]]
    scope = scope.join(meta, on="gid")
    scope = scope[[(s, w) in keep for s, w in zip(scope["season"], scope["week"])]].copy()
    lad = scope["series"].isin(list(pk.LADDERS))
    scope.loc[lad, "pid"] = pd.concat([pk.player_ids(scope[lad & (scope["season"] == s)], s) for s in sorted(scope["season"].unique())])
    log(f"scope markets {len(scope)} ({lad.sum()} ladder thresholds) in {scope['gid'].nunique()} games")
    rows = []
    for i, m in enumerate(scope.itertuples(index=False)):
        ms = pd.Series(m._asdict())
        c = pk.candles(ms)
        t90, cl = pk.quote_at(c, m.kickoff - pk.LEAD), pk.quote_at(c, m.kickoff)
        rows.append({"ticker": m.ticker, "series": m.series, "gid": m.gid, "season": m.season, "week": m.week, "team": m.team,
                     "pid": ms.get("pid"), "player": m.player, "stat": m.stat, "threshold": m.threshold, "strike": m.strike,
                     "result": m.result, "historical": m.historical, "kickoff": m.kickoff,
                     **{f"{k}90": v for k, v in t90.items()}, **{f"{k}C": v for k, v in cl.items()}})
        if i and i % 2000 == 0:
            log(f"  candles {i}/{len(scope)}")
    q = pd.DataFrame(rows)
    q.to_parquet(pk.CACHE / "quotes.parquet")

    # trades for liquid ladder thresholds: does the last print before T-90 sit inside that candle's book?
    tr = []
    for m in q[q["liquid90"] & q["series"].isin(list(pk.LADDERS))].itertuples(index=False):
        t = pk.trades(pd.Series({"ticker": m.ticker, "historical": m.historical}), m.kickoff - pk.LEAD)
        if not t:
            tr.append({"ticker": m.ticker, "n": 0, "inside": np.nan})
            continue
        last = max(t, key=lambda x: x.get("created_time", ""))
        px = K._f(last.get("yes_price_dollars", last.get("yes_price")))
        px = px / 100 if px is not None and px > 1 else px
        tr.append({"ticker": m.ticker, "n": len(t), "inside": float(m.bid90 - 0.005 <= px <= m.ask90 + 0.005) if px is not None else np.nan})
    pd.DataFrame(tr).to_parquet(pk.CACHE / "trades_check.parquet")
    log(f"trades checked for {len(tr)} liquid markets")

    # game environments at T-90
    hist = pd.read_parquet(h.CACHE / "kalshi_history.parquet")
    env = []
    for gid, d in scope[scope["series"].isin(pk.ENV)].groupby("gid"):
        r = meta.loc[gid]
        ko = d["kickoff"].iloc[0]
        P = ko - pk.LEAD
        wp = K.probability(hist[hist["gid"] == gid], gid, P)["p_home"] if (hist["gid"] == gid).any() else np.nan
        e = pk.game_environment(d, r["home"], r["away"], P, wp)
        env.append({"gid": gid, "season": r["season"], "week": r["week"], "kalshi_p_home": wp, **e})
    pd.DataFrame(env).to_parquet(pk.CACHE / "env.parquet")
    log(f"environments: {len(env)} games, {pd.DataFrame(env)[['margin', 'total']].notna().all(1).sum()} with both medians")


def replay(args):
    games, gcsv = _games()
    env = pd.read_parquet(pk.CACHE / "env.parquet").set_index("gid")
    out = pk.CACHE / "replay"
    out.mkdir(parents=True, exist_ok=True)
    for season, wks in _scored_weeks(gcsv).groupby("season"):
        R = None
        for w in wks["week"]:
            path = out / f"{season}_w{int(w):02d}.parquet"
            if path.exists():
                continue
            wk = gcsv[(gcsv["season"] == season) & (gcsv["week"] == w)].sort_values("game_id")
            envs = {}
            for r in wk.itertuples(index=False):
                if r.game_id not in env.index or env.loc[r.game_id, ["margin", "total"]].isna().any():
                    continue
                m, t = env.loc[r.game_id, "margin"], env.loc[r.game_id, "total"]
                envs[r.game_id] = {"K": ((t + m) / 2, (t - m) / 2),
                                   "A": ((r.total_line + r.spread_line) / 2, (r.total_line - r.spread_line) / 2)}
            if not envs:
                continue
            R = R or pk.Replayer(int(season), gcsv)
            log(f"replay {season} week {int(w)}: {len(envs)} games")
            R.week(int(w), wk, envs, EMPTY_INJ, log=log).to_parquet(path)


def _probs(sim_rows: pd.DataFrame, ks: np.ndarray) -> np.ndarray:
    q = sim_rows[G.QCOLS].to_numpy(float)[0]
    return np.array([pk.p_at_least(q, k) for k in ks])


def score(args):
    games, gcsv = _games()
    q = pd.read_parquet(pk.CACHE / "quotes.parquet")
    sim = pd.concat([pd.read_parquet(p) for p in sorted((pk.CACHE / "replay").glob("*.parquet"))], ignore_index=True)
    act = pd.concat([actual_stats(s) for s in sorted(q["season"].unique())]).rename(columns={"game_id": "gid"})
    lad = q[q["series"].isin(list(pk.LADDERS)) & q["pid"].notna()].copy()
    res = {"prereg": pk.PREREG, "label": "one look; provisional until Codex reproduces; nothing promoted"}

    # settlement cross-check (all ladder thresholds with a yes/no result and an official stat)
    chk = lad[lad["result"].isin(["yes", "no"])].merge(act, left_on=["gid", "pid", "stat"], right_on=["gid", "pid", "stat"], how="left")
    chk["kalshi_yes"] = chk["result"] == "yes"
    for col in ("actual_full", "actual_reg"):
        ok = chk[col].notna()
        agree = (chk.loc[ok, col] >= chk.loc[ok, "threshold"]) == chk.loc[ok, "kalshi_yes"]
        res[f"settlement_vs_{col}"] = {"compared": int(ok.sum()), "agree": float(agree.mean()), "disagree": int((~agree).sum()),
                                       "no_official_stat": int((~ok).sum())}
    dis = chk[chk["actual_full"].notna() & ((chk["actual_full"] >= chk["threshold"]) != chk["kalshi_yes"])]
    res["settlement_disagreements_examples"] = dis[["ticker", "player", "stat", "threshold", "actual_full", "result"]].head(25).to_dict("records")
    res["non_binary_settlements"] = int((~lad["result"].isin(["yes", "no"])).sum())
    tc = pd.read_parquet(pk.CACHE / "trades_check.parquet")
    res["trades_check"] = {"markets": int(len(tc)), "with_trades_24h": int((tc["n"] > 0).sum()),
                           "last_print_inside_book": float(tc["inside"].mean())}

    rows, thr = [], []
    for (gid, pid, stat), d in lad.groupby(["gid", "pid", "stat"]):
        d = d[d["liquid90"] & d["result"].isin(["yes", "no"])].sort_values("threshold")
        if len(d) < 3:
            continue
        s = sim[(sim["gid"] == gid) & (sim["pid"] == pid) & (sim["stat"] == stat)]
        need = {("K", "v2"), ("A", "v2"), ("K", "base"), ("K", "v1"), ("A", "v1")}
        have = set(zip(s["arm"], s["version"]))
        if not {("K", "v2"), ("A", "v2"), ("K", "base")} <= have:
            continue
        ks = d["threshold"].to_numpy(float)
        yes = (d["result"] == "yes").to_numpy(float)
        w = 1 / np.clip((d["ask90"] - d["bid90"]).to_numpy(float), 0.01, None)
        m90 = pk.isotonic_survival(ks, d["mid90"].to_numpy(float), w)
        okC = d["midC"].notna().all()
        mC = pk.isotonic_survival(ks, d["midC"].to_numpy(float), w) if okC else np.full(len(ks), np.nan)
        P = {"K": _probs(s[(s["arm"] == "K") & (s["version"] == "v2")], ks), "A": _probs(s[(s["arm"] == "A") & (s["version"] == "v2")], ks),
             "base": _probs(s[(s["arm"] == "K") & (s["version"] == "base")], ks), "market90": m90, "marketC": mC}
        for v in ("K", "A"):
            if (v, "v1") in have:
                P[f"{v}_v1"] = _probs(s[(s["arm"] == v) & (s["version"] == "v1")], ks)
        season, week = int(d["season"].iloc[0]), int(d["week"].iloc[0])
        rows.append({"gid": gid, "pid": pid, "stat": stat, "season": season, "week": week, "n_thr": len(ks),
                     **{f"crps_{k_}": (ladder_crps(v_, yes) if not np.isnan(v_).any() else np.nan) for k_, v_ in P.items()}})
        for j in range(len(ks)):
            thr.append({"gid": gid, "pid": pid, "stat": stat, "season": season, "week": week, "k": ks[j], "y_home_win": int(yes[j]),
                        "kickoff_utc": d["kickoff"].iloc[j], "point_utc": d["kickoff"].iloc[j] - pk.LEAD,
                        "raw90": d["mid90"].iloc[j], "rawC": d["midC"].iloc[j], **{f"p_{k_}": v_[j] for k_, v_ in P.items()}})
    L, T = pd.DataFrame(rows), pd.DataFrame(thr)
    L.to_parquet(pk.CACHE / "scored_ladders.parquet")
    T.to_parquet(pk.CACHE / "scored_thresholds.parquet")
    res["scored"] = {"ladders": int(len(L)), "thresholds": int(len(T)), "games": int(L["gid"].nunique()),
                     "weeks": int(L[["season", "week"]].drop_duplicates().shape[0]), "by_stat": L["stat"].value_counts().to_dict()}
    log(f"scored ladders {len(L)}, thresholds {len(T)}, weeks {res['scored']['weeks']}")

    from lab import homewin_sim as sm
    a3 = 0.05 / 3
    G_ = {"K_vs_base": sm.paired(L, "crps_K", "crps_base", a3), "K_vs_market90": sm.paired(L, "crps_K", "crps_market90", a3),
          "A_vs_K": sm.paired(L, "crps_A", "crps_K", a3)}
    for k_, v_ in G_.items():
        v_["pass"] = bool(v_["ci"][1] < 0)
    G_["K_vs_base"]["primary"] = True
    G_["A_vs_K"]["note"] = "A uses undated games.csv lines (possible look-ahead); descriptive"
    res["G"] = G_
    res["descriptive_crps_means"] = {c.replace("crps_", ""): float(L[c].mean()) for c in L if c.startswith("crps_")}
    lo = lambda p, y: -(y * np.log(np.clip(p, 1e-6, 1 - 1e-6)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1 - 1e-6)))  # noqa: E731
    res["threshold_log_loss"] = {c.replace("p_", ""): float(lo(T[c], T["y_home_win"]).mean()) for c in T if c.startswith("p_") and T[c].notna().all()}

    St = T.rename(columns={"p_market90": "p_mkt", "p_K": "p_sim"})
    res["S"] = v2.stack(St, ["p_mkt", "p_sim"], alpha=0.05)
    res["S"]["pass"] = bool(res["S"]["weights"]["p_sim"]["ci"][0] > 0)

    C = T.dropna(subset=["raw90", "rawC"])
    move = (C["rawC"] - C["raw90"]).to_numpy()
    cl = (C["season"].astype(str) + "_" + C["week"].astype(str)).to_numpy()
    res["C"] = {}
    for src in ("K", "base", "A"):
        side = np.sign(C[f"p_{src}"].to_numpy() - C["raw90"].to_numpy())
        c = move * side
        nz = c[c != 0]
        res["C"][src] = {"n": int(len(c)), "mean_clv": float(c.mean()), "ci95": ev.cluster_boot(c, cl, 0.05),
                         "toward": int((nz > 0).sum()), "away": int((nz < 0).sum()), "zero_moves": int((move == 0).sum()),
                         "sign_p_one_sided": float(binomtest(int((nz > 0).sum()), len(nz), alternative="greater").pvalue) if len(nz) else None}
    k_ = res["C"]["K"]
    k_["pass"] = bool(k_["ci95"][0] > 0 and k_["sign_p_one_sided"] < 0.05)

    # PIT of the realized full-game stat within the simulator and base distributions (descriptive)
    pit = {}
    rng = np.random.default_rng(0)
    for src, arm, ver in (("K", "K", "v2"), ("A", "A", "v2"), ("base", "K", "base")):
        u = []
        for r in L.itertuples(index=False):
            a = act[(act["gid"] == r.gid) & (act["pid"] == r.pid) & (act["stat"] == r.stat)]
            s = sim[(sim["gid"] == r.gid) & (sim["pid"] == r.pid) & (sim["stat"] == r.stat) & (sim["arm"] == arm) & (sim["version"] == ver)]
            if a.empty or s.empty:
                continue
            qv = s[G.QCOLS].to_numpy(float)[0]
            y = float(a["actual_full"].iloc[0])
            lo_, hi_ = np.interp(y - 0.5, qv, G.LEVELS, 0, 1), np.interp(y + 0.5, qv, G.LEVELS, 0, 1)
            u.append(lo_ + rng.random() * (hi_ - lo_))
        hist_ = np.histogram(u, bins=10, range=(0, 1))[0]
        pit[src] = {"n": len(u), "hist": hist_.tolist(), "chi2_p": float(chisquare(hist_).pvalue) if len(u) else None}
    res["pit"] = pit
    _write("results.json", res)
    for k_, v_ in res["G"].items():
        log(f"G {k_}: {v_['mean_a']:.4f} vs {v_['mean_b']:.4f} delta {v_['delta']:+.4f} [{v_['ci'][0]:+.4f},{v_['ci'][1]:+.4f}] -> {'PASS' if v_['pass'] else 'fail'}")
    s_ = res["S"]["weights"]
    log(f"S: market {s_['p_mkt']['w']:+.3f} [{s_['p_mkt']['ci'][0]:+.3f},{s_['p_mkt']['ci'][1]:+.3f}] sim {s_['p_sim']['w']:+.3f} "
        f"[{s_['p_sim']['ci'][0]:+.3f},{s_['p_sim']['ci'][1]:+.3f}] -> {'PASS' if res['S']['pass'] else 'fail'}")
    for src, c in res["C"].items():
        log(f"C {src}: n={c['n']} mean {c['mean_clv']:+.4f} [{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] {c['toward']}/{c['away']} p={c['sign_p_one_sided']:.3f}")
    log(f"settlement agreement full {res['settlement_vs_actual_full']['agree']:.4f} reg {res['settlement_vs_actual_reg']['agree']:.4f}; "
        f"trades last print inside book {res['trades_check']['last_print_inside_book']:.3f}; PIT {[(k_, v_['chi2_p']) for k_, v_ in pit.items()]}")
