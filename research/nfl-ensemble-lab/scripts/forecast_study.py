"""Joint score model study runner. Protocol: docs/FORECAST_PREREGISTRATION.md (commit 94e455cc). All local.

  python scripts/forecast_study.py pilot    # tau on 2008-2011, 2009-2011 pilot, power -> reports/forecast/{tuning,power}.json
  python scripts/forecast_study.py run      # one look: families L, K, T, leans, conformal, coherence (after power is committed)
  python scripts/forecast_study.py freeze   # sealed weekly freeze for winners, spreads, totals (props freeze: props_kalshi_collect.py)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab import forecast_core as fc  # noqa: E402
from lab import homewin_deep as h  # noqa: E402
from lab import homewin_eval as ev  # noqa: E402
from lab import kalshi as K  # noqa: E402
from lab import props_kalshi as pk  # noqa: E402
from lab.config import CACHE_DIR, LAB_ROOT  # noqa: E402

CACHE = CACHE_DIR / "props_kalshi"
OUT = LAB_ROOT / "reports" / "forecast"
QC = [f"q{k:02d}" for k in range(1, 100)]
R_, B_, SEED = 300, 500, 0


def log(m):
    print(m, flush=True)


def write(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    body = json.dumps(obj, indent=1, default=str)
    (OUT / name).write_bytes(body.encode("utf-8"))
    log(f"Wrote reports/forecast/{name} sha256 {hashlib.sha256(body.encode()).hexdigest()}")


# --------------------------------------------------------------------------- shared data

def winner_prices(games: pd.DataFrame, point: str = "90") -> dict:
    hist = pd.read_parquet(h.CACHE / "kalshi_history.parquet")
    by = {g: d for g, d in hist.groupby("gid")}
    k = games.set_index("gid")["kickoff_utc"]
    out = {}
    for gid, d in by.items():
        if gid in k.index:
            P = k[gid] - (pk.LEAD if point == "90" else pd.Timedelta(0))
            out[gid] = K.probability(d, gid, P)["p_home"]
    return out


def naive_week(G: pd.DataFrame, wk: pd.DataFrame) -> dict:
    s = int(wk["season"].iloc[0])
    R = fc.week_cutoff(wk)
    tr = G[G["played"] & (G["kickoff_utc"] < R) & (G["season"] >= s - 2)]
    w = 0.5 ** ((R - tr["kickoff_utc"]).dt.total_seconds().to_numpy() / 86400 / fc.HALF_LIFE)
    w = w / w.sum()
    out = {}
    for k_, y in (("m", (tr["score_home"] - tr["score_away"]).to_numpy(float)), ("t", (tr["score_home"] + tr["score_away"]).to_numpy(float))):
        mu = float((w * y).sum())
        out[k_] = (mu, float(np.sqrt((w * (y - mu) ** 2).sum())))
    return out


def kalshi_window(G: pd.DataFrame):
    """Ladder tables at T-90 and the games' outcomes for the Kalshi window."""
    q = pd.read_parquet(CACHE / "quotes.parquet")
    q = q[q["series"].isin(["KXNFLSPREAD", "KXNFLTOTAL"])]
    wp = winner_prices(G)
    lad = fc.ladder_tables(q, G, wp, "90")
    return lad, wp


def thin_frame() -> pd.DataFrame:
    sim = pd.concat([pd.read_parquet(p) for p in sorted((CACHE / "replay").glob("*.parquet"))], ignore_index=True)
    sim = sim[sim["arm"] == "K"]
    v2 = sim[sim["version"] == "v2"].drop_duplicates(["gid", "pid", "stat"]).set_index(["gid", "pid", "stat"])
    base = sim[sim["version"] == "base"].drop_duplicates(["gid", "pid", "stat"]).set_index(["gid", "pid", "stat"])
    from props_kalshi import actual_stats
    act = pd.concat([actual_stats(s) for s in (2025, 2026)]).rename(columns={"game_id": "gid"})
    act = act.dropna(subset=["actual_full"]).drop_duplicates(["gid", "pid", "stat"]).set_index(["gid", "pid", "stat"])["actual_full"]
    idx = v2.index.intersection(base.index).intersection(act.index)
    y = act.loc[idx].to_numpy(float)
    Q2, Qb = v2.loc[idx, QC].to_numpy(float), base.loc[idx, QC].to_numpy(float)
    q = pd.read_parquet(CACHE / "quotes.parquet")
    q = q[q["series"].isin(list(pk.LADDERS)) & q["pid"].notna()]
    cnt = q.groupby(["gid", "pid", "stat"]).agg(n_any=("ticker", "size"), n_liq=("liquid90", lambda s: int(s.astype(bool).sum())))
    f = pd.DataFrame(index=idx).join(cnt).fillna(0)
    group = np.where(f["n_liq"] >= 3, "liquid", np.where(f["n_any"] > 0, "thin", "none"))
    meta = v2.loc[idx, ["season", "week"]]
    out = pd.DataFrame({"gid": [i[0] for i in idx], "pid": [i[1] for i in idx], "stat": [i[2] for i in idx], "season": meta["season"].to_numpy(),
                        "week": meta["week"].to_numpy(), "group": group, "y": y, "l_v2": fc.pin_crps(Q2, y), "l_base": fc.pin_crps(Qb, y),
                        "q10": Q2[:, 9], "q90": Q2[:, 89]})
    scale = out.groupby("stat")["l_base"].transform("mean")      # Amendment 1: per-stat scaled difference
    out["d_rel"] = (out["l_v2"] - out["l_base"]) / scale
    out["base_rel"] = out["l_base"] / scale
    return out


# --------------------------------------------------------------------------- pilot and power

def pilot(args):
    from props_market_power import mde, week_arrays
    G = fc.games_frame()
    tun = fc.tune_tau(G)
    log(f"tuned tau_n={tun['tau_n']} tau_s={tun['tau_s']}: {tun['grid']}")
    write("tuning.json", tun)
    pf = fc.walk_forward(G, tun["tau_n"], tun["tau_s"], range(2009, 2012))
    log(f"pilot predictions: {len(pf)} games, {pf[['season', 'week']].drop_duplicates().shape[0]} weeks")
    rng = np.random.default_rng(SEED)
    wk_total = int(G[(G["season"] >= 2012) & G["played"]][["season", "week"]].drop_duplicates().shape[0])
    out = {"prereg": fc.PREREG, "tuning": {k: v for k, v in tun.items() if k != "grid"}, "evaluation_weeks_long_history": wk_total, "comparisons": {}}

    def add(name, df, d, sesoi, alpha, avail_weeks, sign=-1):
        d0 = d - d.mean()
        s, c = week_arrays(df, d0)
        row = {"sd_pooled_difference": float(d.std()), "observed_mean_difference_proxy": float(d.mean()), "sesoi": float(sesoi), "alpha": alpha,
               "available_weeks": int(avail_weeks), "mde_by_weeks": {}}
        for W in sorted({avail_weeks, 40, 90, 150, 400}):
            row["mde_by_weeks"][str(W)] = mde(s, c, W, alpha, sign, rng)
        m_av = row["mde_by_weeks"][str(avail_weeks)]
        row["decidable_now"] = bool(m_av <= sesoi)
        row["N_weeks"] = int(np.ceil(avail_weeks * (m_av / sesoi) ** 2)) if m_av > sesoi else int(avail_weeks)
        row["prospective_only"] = bool((not row["decidable_now"]) and row["N_weeks"] <= 150)
        out["comparisons"][name] = row
        log(f"{name:<34} MDE({avail_weeks})={m_av:.4f} SESOI={sesoi:.4f} N={row['N_weeks']} decidable_now={row['decidable_now']}")

    # L family proxies from the pilot (2009-2011)
    pn = pf[~pf["tie"].astype(bool)]
    mod_m = fc.crps_normal(pf["y_m"], pf["mu_m"], pf["sd_m"])
    el_m = fc.crps_normal(pf["y_m"], pf["elo_mu"], fc.SD0)
    nv_m = fc.crps_normal(pf["y_m"], pf["naive_m_mu"], pf["naive_m_sd"])
    mod_t = fc.crps_normal(pf["y_t"], pf["mu_t"], pf["sd_t"])
    nv_t = fc.crps_normal(pf["y_t"], pf["naive_t_mu"], pf["naive_t_sd"])
    a4 = 0.05 / 4
    add("L1_margin_vs_elo_normal", pf, np.asarray(mod_m - el_m), 0.01 * float(np.mean(el_m)), a4, wk_total)
    add("L2_margin_vs_naive", pf, np.asarray(mod_m - nv_m), 0.01 * float(np.mean(nv_m)), a4, wk_total)
    add("L3_total_vs_naive", pf, np.asarray(mod_t - nv_t), 0.01 * float(np.mean(nv_t)), a4, wk_total)
    yw = (pn["y_m"] > 0).astype(float).to_numpy()
    add("L4_winner_logloss_vs_elo", pn, fc.log_loss_vec(pn["p_win"].to_numpy(), yw) - fc.log_loss_vec(pn["p_elo"].to_numpy(), yw), 0.005, a4, wk_total)

    # K family proxies: Elo-normal margin / naive total shifted toward Kalshi at b = 0.2
    G2 = fc.games_frame()
    lad, wp = kalshi_window(G2)
    gi = G2.set_index("gid")
    nv = {}
    for (s, w), wk in G2.groupby(["season", "week"]):
        if (s, w) >= (2025, 5):
            nv[(s, w)] = naive_week(G2, wk)
    rows_m, rows_t, rows_w = [], [], []
    for (gid, tgt), L in lad.items():
        r = gi.loc[gid]
        if not r["played"]:
            continue
        muK = fc.ladder_median(L)
        if np.isnan(muK):
            continue
        sw = (int(r["season"]), int(r["week"]))
        if tgt == "margin":
            mu_p = float(fc.SD0 * norm.ppf(np.clip(r["elo_prob_home"], 1e-4, 1 - 1e-4)))
            y = (r["margin"] > L["c"].to_numpy()).astype(float)
        else:
            mu_p = nv[sw]["t"][0]
            y = (r["total"] > L["c"].to_numpy()).astype(float)
        delta = 0.2 * (mu_p - muK)
        d = fc.ladder_crps(fc.shifted(L, delta), y) - fc.ladder_crps(L["p_iso"].to_numpy(), y)
        (rows_m if tgt == "margin" else rows_t).append({"gid": gid, "season": sw[0], "week": sw[1], "d": d, "base": fc.ladder_crps(L["p_iso"].to_numpy(), y)})
        if tgt == "margin" and r["margin"] != 0:
            yw1 = float(r["margin"] > 0)
            pa, pb = float(fc.shifted(L, delta, np.array([0.5]))[0]), float(fc.shifted(L, 0.0, np.array([0.5]))[0])
            rows_w.append({"gid": gid, "season": sw[0], "week": sw[1], "d": float(fc.log_loss_vec(pa, yw1) - fc.log_loss_vec(pb, yw1))})
    a3 = 0.05 / 3
    weeks_k = int(pd.DataFrame(rows_m)[["season", "week"]].drop_duplicates().shape[0])
    dm, dt, dw = pd.DataFrame(rows_m), pd.DataFrame(rows_t), pd.DataFrame(rows_w)
    add("K1_margin_ladder_vs_kalshi", dm, dm["d"].to_numpy(), 0.01 * float(dm["base"].mean()), a3, weeks_k)
    add("K2_total_ladder_vs_kalshi", dt, dt["d"].to_numpy(), 0.01 * float(dt["base"].mean()), a3, weeks_k)
    add("K3_winner_logloss_vs_kalshi", dw, dw["d"].to_numpy(), 0.005, a3, weeks_k)

    # T family: replayed v2 vs base, by group
    tf = thin_frame()
    for gname, label in (("thin", "T1_thin_props_v2_vs_base"), ("none", "T2_no_market_props_v2_vs_base"), ("liquid", "T3_liquid_props_v2_vs_base")):
        g = tf[tf["group"] == gname]
        wks = int(g[["season", "week"]].drop_duplicates().shape[0])
        if len(g) > 50:
            add(label, g, g["d_rel"].to_numpy(), 0.01, a3, wks)
    out["groups"] = tf["group"].value_counts().to_dict()
    write("power.json", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["pilot", "run", "freeze"])
    args = ap.parse_args()
    if args.command == "pilot":
        pilot(args)
    else:
        import forecast_study_run as R
        {"run": R.run, "freeze": R.freeze}[args.command](args)


if __name__ == "__main__":
    main()
