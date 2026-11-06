"""Basket test (docs/BASKET_PREREG.md). python scripts/basket_run.py gate | run | freeze   (run executes once)"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import basket as K  # noqa: E402

DOCS = ROOT / "docs"
CACHE = ROOT / "data" / "cache" / "basket_teamgames.parquet"


def prepare():
    lg = K.legs()
    rec, pas, done = K.actuals()
    par = K.fit_decide(lg, rec, pas, done)
    share = {**par["share"], "pooled": par["pooled_share"]}
    tg = K.team_games(lg, rec, pas, par["cQ"], par["cR"], share)
    tg["final"] = tg["game_id"].isin(done)
    return tg, par


def slope(x, y):
    xm = x - x.mean()
    return float((xm * (y - y.mean())).sum() / (xm * xm).sum())


def final_snapshots(tg):
    f = tg.sort_values("snap").groupby(["book", "game_id", "team"]).tail(1)
    return f


def consensus(f):
    c = f.groupby(["game_id", "team", "week"]).agg(G=("G", "median"), Q=("Q", "median"), B=("B", "median"), k=("k", "median"), qb_act=("qb_act", "first"), listed_act=("listed_act", "median"), books=("book", "nunique")).reset_index()
    f = f.assign(eQ=f["qb_act"] - f["Q"], eB=f["listed_act"] - f["B"])
    e = f.groupby(["game_id", "team"]).agg(eQ=("eQ", "median"), eB=("eB", "median")).reset_index()
    return c.merge(e, on=["game_id", "team"])


def sim_power(c, par, rho, rng, reps=400):
    n = len(c)
    hits = {"Q": 0, "B": 0}
    for _ in range(reps):
        eQ = -rho * c["G"].to_numpy() + rng.standard_normal(n) * par["cQ"] * c["Q"].to_numpy()
        eB = rho * c["G"].to_numpy() + rng.standard_normal(n) * par["cR"] * c["B"].to_numpy() / np.sqrt(c["k"].to_numpy())
        for key, e, sgn in (("Q", eQ, -1), ("B", eB, 1)):
            r = stats.linregress(c["G"].to_numpy(), e)
            t = r.slope / r.stderr
            p = stats.t.sf(t, n - 2) if sgn > 0 else stats.t.cdf(t, n - 2)
            hits[key] += p < K.GATE_LEVEL
    return {k: v / reps for k, v in hits.items()}


def closing_pairs(tg):
    rows = []
    for (book, gid, team), g in tg.sort_values("snap").groupby(["book", "game_id", "team"]):
        g = g.reset_index(drop=True)
        for i in range(len(g) - 1):
            for j in range(i + 1, len(g)):
                dt = (g.loc[j, "snap"] - g.loc[i, "snap"]).total_seconds() / 3600
                if 6 <= dt <= 30:
                    rows.append((book, gid, team, g.loc[i, "g"], g.loc[j, "g"] - g.loc[i, "g"], g.loc[j, "Q"] / g.loc[i, "Q"] - 1, g.loc[j, "B"] / g.loc[i, "B"] - 1))
                    break
    return pd.DataFrame(rows, columns=["book", "gid", "team", "g0", "dg", "dQ", "dB"])


def boot_slope(df, xcol, ycol, rng, b=1000):
    ug, inv = np.unique(df["gid"].to_numpy(), return_inverse=True)
    idx = [np.where(inv == i)[0] for i in range(len(ug))]
    x, y = df[xcol].to_numpy(), df[ycol].to_numpy()
    out = []
    for _ in range(b):
        k = np.concatenate([idx[i] for i in rng.integers(0, len(ug), len(ug))])
        out.append(slope(x[k], y[k]))
    return np.array(out)


def gate():
    tg, par = prepare()
    rng = np.random.default_rng(20261106)
    f = final_snapshots(tg[tg["final"]])
    c = consensus(f[f["week"].isin(K.CONFIRM_WEEKS)])
    pr = closing_pairs(tg)
    bs = boot_slope(pr, "g0", "dg", rng, 600)
    g = {"params": par, "confirm_team_games": int(len(c)), "confirm_games": int(c["game_id"].nunique()), "sd_G_confirm": float(c["G"].std()), "all_teamgames_with_gap": int(len(tg)),
         "power_at_rho_0.25": sim_power(c, par, K.RHO, rng), "closing_pairs": int(len(pr)), "closing_games": int(pr["gid"].nunique()),
         "closing_se_kappa": float(bs.std(ddof=1)), "closing_min_detectable": float(2.8 * bs.std(ddof=1))}
    g["outcome_informative"] = bool(min(g["power_at_rho_0.25"].values()) >= 0.80)
    g["closing_informative"] = bool(g["closing_min_detectable"] <= K.KAPPA_SIZE)
    tg.to_parquet(CACHE)
    (DOCS / "basket_gate.json").write_text(json.dumps(g, indent=1, default=str))
    print(json.dumps(g, indent=1, default=str))




def referee(tg, par):
    """Descriptive: does Kalshi's quarterback median sit nearer the book's quarterback leg or the basket-implied value?"""
    from lab import coherence_lag as B
    pts = B.points()
    pts = pts[pts["gid"].str.startswith("2026") & pts["series"].isin(["KXNFLPASSYDS", "KXNFLRECYDS"]) & (pts["h"] == 3)]
    m = B.medians(pts.assign(h=3))
    q = m[m["series"] == "KXNFLPASSYDS"].rename(columns={"med": "Qk"})[["gid", "team", "Qk"]].drop_duplicates(["gid", "team"])
    r = m[m["series"] == "KXNFLRECYDS"].groupby(["gid", "team"]).agg(Bk=("med", "sum"), kk=("med", "size")).reset_index()
    k = q.merge(r, on=["gid", "team"])
    k = k[k["kk"] >= 2]
    f = final_snapshots(tg)
    c = f.groupby(["game_id", "team"]).agg(Q=("Q", "median"), Qstar=("Qstar", "median"), G=("G", "median")).reset_index().rename(columns={"game_id": "gid"})
    j = k.merge(c, on=["gid", "team"])
    if len(j) < 10:
        return {"team_games": int(len(j)), "note": "too few team-games for a descriptive comparison"}
    big = j[j["G"].abs() >= j["G"].abs().median()]
    return {"team_games": int(len(j)), "corr_book_gap_with_kalshi_sign_of_Q_minus_Qstar": float(np.corrcoef(j["G"], j["Qk"] - j["Qstar"])[0, 1]),
            "large_gap_team_games": int(len(big)), "kalshi_nearer_book_Q_share": float((np.abs(big["Qk"] - big["Q"]) < np.abs(big["Qk"] - big["Qstar"])).mean())}


def run():
    marker = ROOT / "data" / "basket" / "done.json"
    if marker.exists():
        sys.exit("Already run once. No rerun.")
    g = json.loads((DOCS / "basket_gate.json").read_text())
    tg = pd.read_parquet(CACHE)
    rng = np.random.default_rng(20261106)
    res = {"outcome_test": {"read": False, "reason": "failed the power gate"} if not g["outcome_informative"] else "see code"}
    if g["closing_informative"]:
        pr = closing_pairs(tg)
        out = {}
        for name, y in (("gap", "dg"), ("qb_line_move", "dQ"), ("basket_move", "dB")):
            bs = boot_slope(pr, "g0", y, rng, 2000)
            s = slope(pr["g0"].to_numpy(), pr[y].to_numpy())
            out[name] = {"slope": s, "ci95": [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], "one_sided_95_upper": float(np.quantile(bs, .95)), "one_sided_95_lower": float(np.quantile(bs, .05))}
        kap_hi = -out["gap"]["ci95"][0]
        kap = -out["gap"]["slope"]
        lo, hi = -out["gap"]["one_sided_95_upper"], -out["gap"]["one_sided_95_lower"]
        verdict = "gap closes" if lo > K.KAPPA_SIZE else "gap persists" if hi < K.KAPPA_SIZE else "cannot say"
        per_book = {}
        for b, d in pr.groupby("book"):
            if d["gid"].nunique() >= 15:
                per_book[b] = {"pairs": int(len(d)), "games": int(d["gid"].nunique()), "kappa": -slope(d["g0"].to_numpy(), d["dg"].to_numpy())}
        wk = tg.drop_duplicates(["game_id"]).set_index("game_id")["week"]
        pr["wk"] = pr["gid"].map(wk)
        null = []
        for _ in range(300):
            pp = pr.copy()
            pp["g0"] = pp.groupby("wk")["g0"].transform(lambda s: rng.permutation(s.to_numpy()))
            null.append(-slope(pp["g0"].to_numpy(), pp["dg"].to_numpy()))
        res["closing_test"] = {"pairs": int(len(pr)), "games": int(pr["gid"].nunique()), "kappa": kap, "kappa_one_sided_90_interval": [lo, hi], "verdict": verdict, "legs": out, "per_book_descriptive": per_book,
                               "placebo_kappa_mean": float(np.mean(null)), "placebo_kappa_sd": float(np.std(null)), "mean_abs_gap_pct": float(pr["g0"].abs().mean() * 100)}
    res["kalshi_referee_descriptive"] = referee(tg, g["params"])
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(res, indent=1, default=str))
    (DOCS / "basket_results.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))



def freeze():
    import hashlib
    from datetime import datetime, timezone
    tg, par = prepare()
    now = pd.Timestamp.now(tz="UTC")
    g = K.games().set_index("game_id")
    up = tg[~tg["final"] & (tg["game_id"].map(g["kickoff_utc"]) > now)]
    last = up.sort_values("snap").groupby(["book", "game_id", "team"]).tail(1)
    if last.empty:
        sys.exit("no unplayed games with a gap")
    week = int(last["week"].min())
    rows = [{"book": r.book, "game_id": r.game_id, "team": r.team, "snap": str(r.snap), "legs": int(r.legs), "k_receivers": int(r.k), "Q_adj": round(r.Q, 2), "B": round(r.B, 2), "Qstar": round(r.Qstar, 2),
             "gap_yards": round(r.G, 2), "gap_rel": round(r.g, 4), "qb_over_odds": r.qb_over, "qb_under_odds": r.qb_under} for r in last.itertuples()]
    rec = {"season": 2026, "week": week, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "params": par, "rows": rows,
           "note": "Gaps from the newest feed snapshot per book for unplayed games. Outcomes are scored later. Nothing is backfilled."}
    canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":"))
    rec["sha256"] = hashlib.sha256(canon(rec).encode()).hexdigest()
    out = ROOT / "data" / "basket" / "frozen"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"week_2026_{week:02d}.json"
    if path.exists():
        sys.exit(f"{path.name} already saved; write-once")
    path.write_text(json.dumps(rec, indent=1))
    with (ROOT / "data" / "basket" / "ledger.jsonl").open("a") as fh:
        fh.write(canon({"file": path.name, "sha256": rec["sha256"], "created_at": rec["created_at"], "rows": len(rows)}) + "\n")
    print({"file": path.name, "rows": len(rows), "games": int(last["game_id"].nunique()), "sha256": rec["sha256"]})


if __name__ == "__main__":
    {"gate": gate, "run": run, "freeze": freeze}[sys.argv[1]]()
