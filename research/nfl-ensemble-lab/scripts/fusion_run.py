"""Fusion tests (docs/FUSION_PREREG.md). python scripts/fusion_run.py gate | run | freeze   (run executes once)"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import basket as K  # noqa: E402
from lab import fusion as F  # noqa: E402

DOCS = ROOT / "docs"


def holm(p):
    order = sorted(p, key=p.get)
    out, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * p[k]))
        out[k] = run
    return out


def prepare():
    q = F.quotes()
    books = sorted(q["book"].unique())
    dec = q[q["week"].isin(F.DECIDE_WEEKS)].reset_index(drop=True)
    par = F.fit(F.encode(dec, books))
    rec, pas, done = K.actuals()
    q = q.merge(rec, on=["game_id", "gsis_id"], how="left").merge(pas, on=["game_id", "gsis_id"], how="left")
    q["actual"] = np.where(q["stat"] == "pass_yds", q["pas"], q["rec"])
    q["actual"] = q["actual"].fillna(0.0)
    q["final_game"] = q["game_id"].isin(done)
    return q, books, par


def final_rows(q):
    key = ["game_id", "gsis_id", "stat"]
    last = q.groupby(key)["snap"].transform("max")
    f = q[q["snap"] == last].sort_values("age", ascending=False).drop_duplicates(key + ["book"], keep="last")
    return f.reset_index(drop=True)


def centers(f, books, par, bg_w):
    """Per prop: fused, median, pinnacle, bates-granger centers (all in yards) at the final snapshot."""
    o = F.encode(f.assign(pid_key=f["game_id"] + "|" + f["gsis_id"] + "|" + f["stat"]), books)
    m, d = F.fused(o, par)
    f = f.assign(d=d, m_prop=m[o.prop], prop=o.prop)
    g = f.groupby("prop")
    props = g.agg(game_id=("game_id", "first"), stat=("stat", "first"), actual=("actual", "first"), final_game=("final_game", "first"), week=("week", "first"),
                  median=("y", "median"), nb=("book", "nunique")).reset_index()
    props["fused"] = np.exp(m[props["prop"]])
    pin = f[f["book"] == "pinnacle"].groupby("prop")["y"].first()
    props["pinnacle"] = props["prop"].map(pin)
    w = f["book"].map(bg_w).fillna(0.0)
    props["bg"] = (f.assign(wy=f["y"] * w, w=w).groupby("prop").apply(lambda x: x["wy"].sum() / max(x["w"].sum(), 1e-12))).reindex(props["prop"]).to_numpy()
    return f, props


def question_losses(f, props, name):
    ctr = props.set_index("prop")[name]
    c = f["stat"].map(F.C_FUSION).to_numpy()
    center = f["prop"].map(ctr).to_numpy()
    out = (f["actual"].to_numpy() > f["line"].to_numpy()).astype(float)
    push = f["actual"].to_numpy() == f["line"].to_numpy()
    ll = F.crps_free_logloss(center, f["line"].to_numpy(), c, out)
    ll[push | np.isnan(center)] = np.nan
    return ll


def game_level(f, ll):
    d = pd.DataFrame({"prop": f["prop"], "game": f["game_id"], "ll": ll}).dropna()
    return d.groupby(["game", "prop"])["ll"].mean().groupby("game").mean()


def dm_boot(a, b, rng, nboot=2000):
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    g = (j.iloc[:, 1] - j.iloc[:, 0]).to_numpy()  # loss of benchmark minus loss of fused; positive = fused better
    se = g.std(ddof=1) / np.sqrt(len(g))
    t = g.mean() / se
    pdm = float(stats.norm.sf(t))
    mu = np.array([g[rng.integers(0, len(g), len(g))].mean() for _ in range(nboot)])
    pb = float((np.sum(mu <= 0) + 1) / (nboot + 1))
    return {"games": int(len(g)), "mean_gain": float(g.mean()), "dm_t": float(t), "p_dm": pdm, "p_boot": pb, "p": max(pdm, pb), "ci95": [float(np.quantile(mu, .025)), float(np.quantile(mu, .975))]}


def bg_weights(f_dec_final, books):
    w = {}
    for b, d in f_dec_final.groupby("book"):
        e = (((d["actual"] - d["y"]) / d["y"]) ** 2).mean()
        w[b] = 1 / e if e > 0 else 0.0
    return w


def planted(struct_obs, rng, B):
    """Hidden lines, biases, noises and drift planted on the real structure."""
    beta = rng.normal(0, 0.01, B); beta -= np.median(beta)
    sig = 0.04 * 3.0 ** rng.uniform(-1, 1, B)
    q = 0.035 ** 2 / 12
    mu = rng.uniform(np.log(30), np.log(250), struct_obs.P)
    s = np.sqrt(sig[struct_obs.book] ** 2 + q * struct_obs.age)
    ly = mu[struct_obs.prop] + beta[struct_obs.book] + rng.standard_t(F.NU, len(struct_obs.ly)) * s
    return F.Obs(ly, struct_obs.book, struct_obs.prop, struct_obs.age, B), {"beta": beta, "sigma": sig, "q": q}, mu


def gate():
    q, books, par = prepare()
    rng = np.random.default_rng(20261106)
    B = len(books)
    dec = q[q["week"].isin(F.DECIDE_WEEKS)].reset_index(drop=True)
    so = F.encode(dec, books)
    rec_err, rec_corr = [], []
    first_fit = None
    for i in range(20):
        po, tp, _ = planted(so, rng, B)
        fp = F.fit(po)
        if i == 0:
            first_fit, first_planted = fp, tp
        bb = fp["beta"] - np.median(fp["beta"])
        rec_err.append(float(np.sqrt(np.mean((bb - tp["beta"]) ** 2)))); rec_corr.append(float(np.corrcoef(fp["sigma"], tp["sigma"])[0, 1]))
    recovery = {"corr_sigma_mean": float(np.mean(rec_corr)), "rms_beta_mean": float(np.mean(rec_err)), "ok": bool(np.mean(rec_corr) >= 0.8 and np.mean(rec_err) <= 0.01)}
    f = final_rows(q[q["final_game"] & q["week"].isin(F.CONFIRM_WEEKS)])
    f = f.assign(prop=pd.factorize(f["game_id"] + "|" + f["gsis_id"] + "|" + f["stat"])[0])
    co = F.Obs(np.zeros(len(f)), f["book"].map({k: i for i, k in enumerate(books)}).to_numpy(), f["prop"].to_numpy(), f["age"].to_numpy(), B)
    cstat = f.groupby("prop")["stat"].first().map(F.C_FUSION).to_numpy()
    cgame = f.groupby("prop")["game_id"].first().to_numpy()

    def power(k):
        wins = 0
        sims = 200 if k == 1 else 80
        for _ in range(sims):
            ly_all, tp, mu = planted(F.Obs(np.zeros(len(f) * k), np.tile(co.book, k), np.concatenate([co.prop + i * co.P for i in range(k)]), np.tile(co.age, k), B), rng, B)
            m_f, _d = F.fused(ly_all, first_fit)
            P = ly_all.P
            ymed = np.exp(pd.Series(ly_all.ly).groupby(ly_all.prop).median().to_numpy())
            cc = np.tile(cstat, k); gg = np.concatenate([[f"{g}#{i}" for g in cgame] for i in range(k)])
            actual = np.exp(mu) * (1 + cc * rng.standard_normal(P))
            line = np.exp(ly_all.ly)
            c_q = cc[ly_all.prop]; ob = (actual[ly_all.prop] > line).astype(float)
            lf = F.crps_free_logloss(np.exp(m_f)[ly_all.prop], line, c_q, ob); lm = F.crps_free_logloss(ymed[ly_all.prop], line, c_q, ob)
            d = pd.DataFrame({"g": gg[ly_all.prop], "p": ly_all.prop, "gain": lm - lf}).groupby(["g", "p"])["gain"].mean().groupby("g").mean().to_numpy()
            t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
            wins += stats.norm.sf(t) < 0.05 / 3
        return wins / sims
    pw = {str(k): {"confirm_props": int(f["prop"].nunique() * k), "power": float(power(k))} for k in (1, 2, 4)}
    # bet-test and reversion gates from quote structure only
    fq, props = centers(final_rows(q), books, par, {b: 1.0 for b in books})
    dec_f = fq[fq["week"].isin(F.DECIDE_WEEKS)]
    thr = float(dec_f["d"].abs().quantile(0.75))
    conf_f = fq[fq["final_game"] & fq["week"].isin(F.CONFIRM_WEEKS)]
    out = conf_f[conf_f["d"].abs() >= thr]
    n, m = len(out), float(out.groupby("game_id").size().mean())
    se_bet = 0.5 * np.sqrt((1 + (m - 1) * 0.1) / max(n, 1))
    pairs = reversion_pairs(q, books, par)
    bs = boot_slope(pairs, "gap", "dly", rng, 600)
    g = {"fit": {"sigma_by_book": dict(zip(books, map(float, par["sigma"]))), "beta_by_book": dict(zip(books, map(float, par["beta"]))), "q_per_hour": par["q"]},
         "recovery": recovery, "scoring_power": pw, "confirm_props": int(f["prop"].nunique()), "confirm_games": int(f["game_id"].nunique()),
         "bet": {"threshold_abs_d": thr, "outlier_bets": int(n), "games": int(out["game_id"].nunique()), "se_structure": float(se_bet), "informative": bool(2.8 * se_bet <= 0.03)},
         "reversion": {"pairs": int(len(pairs)), "games": int(pairs["game"].nunique()), "se_kappa": float(bs.std(ddof=1)), "informative": bool(2.8 * bs.std(ddof=1) <= 0.15)}}
    g["scoring_informative"] = bool(recovery["ok"] and pw["1"]["power"] >= 0.80)
    (DOCS / "fusion_gate.json").write_text(json.dumps(g, indent=1))
    (ROOT / "data" / "cache").mkdir(parents=True, exist_ok=True)
    json.dump({"beta": par["beta"].tolist(), "sigma": par["sigma"].tolist(), "q": par["q"], "books": books, "thr": thr}, open(ROOT / "data" / "cache" / "fusion_params.json", "w"))
    print(json.dumps({k: v for k, v in g.items() if k != "fit"}, indent=1))


def slope(x, y):
    xm = x - x.mean()
    return float((xm * (y - y.mean())).sum() / (xm * xm).sum())


def reversion_pairs(q, books, par):
    o = F.encode(q, books)
    m, _ = F.fused(o, par)
    qq = q.assign(gap=q["ly"].to_numpy() - m[o.prop]).sort_values("snap")
    rows = []
    for (b, gid, pid, st), g in qq.groupby(["book", "game_id", "gsis_id", "stat"]):
        if len(g) < 2:
            continue
        s, gp, ly = g["snap"].to_numpy(), g["gap"].to_numpy(), g["ly"].to_numpy()
        for i in range(len(g) - 1):
            for j in range(i + 1, len(g)):
                dt = (s[j] - s[i]) / np.timedelta64(1, "h")
                if 6 <= dt <= 30:
                    rows.append((b, gid, gp[i], ly[j] - ly[i])); break
    return pd.DataFrame(rows, columns=["book", "game", "gap", "dly"])


def boot_slope(df, x, y, rng, b=1000):
    ug, inv = np.unique(df["game"].to_numpy(), return_inverse=True)
    idx = [np.where(inv == i)[0] for i in range(len(ug))]
    xv, yv = df[x].to_numpy(), df[y].to_numpy()
    out = []
    for _ in range(b):
        k = np.concatenate([idx[i] for i in rng.integers(0, len(ug), len(ug))])
        out.append(slope(xv[k], yv[k]))
    return np.array(out)


def run():
    marker = ROOT / "data" / "fusion" / "done.json"
    if marker.exists():
        sys.exit("Already run once. No rerun.")
    gate_ = json.loads((DOCS / "fusion_gate.json").read_text())
    q, books, par = prepare()
    rng = np.random.default_rng(20261106)
    res = {}
    allf = final_rows(q)
    fq, props = centers(allf, books, par, bg_weights(allf[allf["final_game"] & allf["week"].isin(F.DECIDE_WEEKS)], books))
    conf = fq["final_game"] & fq["week"].isin(F.CONFIRM_WEEKS)
    cf, cp = fq[conf], props[props["final_game"] & props["week"].isin(F.CONFIRM_WEEKS)]
    if gate_["scoring_informative"]:
        ll = {n: game_level(cf, question_losses(cf, cp, n)) for n in ("fused", "median", "bg", "pinnacle")}
        cmp_ = {}
        for n in ("median", "bg"):
            cmp_[n] = dm_boot(ll["fused"], ll[n], rng)
        pin_props = cp[cp["pinnacle"].notna()]
        cfp = cf[cf["prop"].isin(pin_props["prop"])]
        cmp_["pinnacle"] = dm_boot(game_level(cfp, question_losses(cfp, cp, "fused")), game_level(cfp, question_losses(cfp, cp, "pinnacle")), rng)
        adj = holm({k: v["p"] for k, v in cmp_.items()})
        for k in cmp_:
            cmp_[k]["p_holm"] = adj[k]; cmp_[k]["passes"] = bool(adj[k] < 0.05)
        res["scoring"] = cmp_
    else:
        res["scoring"] = {"read": False, "reason": "failed recovery or power gate"}
    if gate_["bet"]["informative"]:
        thr = gate_["bet"]["threshold_abs_d"]
        b = cf[cf["d"].abs() >= thr].copy()
        under = b["d"] > 0
        win = np.where(under, b["actual"] < b["line"], b["actual"] > b["line"]).astype(float)
        push = (b["actual"] == b["line"]).to_numpy()
        odds = np.where(under, b["under_odds"], b["over_odds"])
        be = K.american_p(odds)
        d = pd.DataFrame({"game": b["game_id"].to_numpy(), "net": win - be, "win": win, "be": be})[~push]
        gm = d.groupby("game")["net"].mean().to_numpy()
        mu = np.array([gm[rng.integers(0, len(gm), len(gm))].mean() for _ in range(2000)])
        res["bet"] = {"bets": int(len(d)), "games": int(len(gm)), "win_rate": float(d["win"].mean()), "mean_break_even": float(d["be"].mean()), "mean_net": float(gm.mean()), "net_one_sided_95_lower": float(np.quantile(mu, .05)), "passes": bool(np.quantile(mu, .05) > 0)}
    else:
        res["bet"] = {"read": False, "reason": "failed the structure gate"}
    if gate_["reversion"]["informative"]:
        pr = reversion_pairs(q, books, par)
        bs = boot_slope(pr, "gap", "dly", rng, 2000)
        k = -slope(pr["gap"].to_numpy(), pr["dly"].to_numpy())
        lo, hi = -float(np.quantile(bs, .95)), -float(np.quantile(bs, .05))
        res["reversion"] = {"pairs": int(len(pr)), "games": int(pr["game"].nunique()), "kappa": k, "one_sided_90": [lo, hi], "verdict": "closes" if lo > 0.15 else "does not close" if hi < 0.15 else "cannot say"}
    from lab import coherence_lag as B
    pts = B.points()
    pts = pts[pts["gid"].str.startswith("2026") & pts["series"].isin(["KXNFLPASSYDS", "KXNFLRECYDS"]) & (pts["h"] == 3)]
    km = B.medians(pts)
    km = km.assign(stat=np.where(km["series"] == "KXNFLPASSYDS", "pass_yds", "rec_yds")).rename(columns={"gid": "game_id", "pid": "gsis_id", "med": "kalshi"})[["game_id", "gsis_id", "stat", "kalshi"]]
    j = props.merge(allf.drop_duplicates(["game_id", "gsis_id", "stat"])[["game_id", "gsis_id", "stat", "prop"]].assign(), on=["game_id", "stat"], how="left") if False else None
    pk = fq.drop_duplicates(["game_id", "gsis_id", "stat"])[["game_id", "gsis_id", "stat", "prop"]].merge(props[["prop", "fused", "median"]], on="prop").merge(km, on=["game_id", "gsis_id", "stat"])
    closer = (pk["kalshi"] - pk["fused"]).abs() < (pk["kalshi"] - pk["median"]).abs()
    nz = int(((pk["kalshi"] - pk["fused"]).abs() != (pk["kalshi"] - pk["median"]).abs()).sum())
    res["kalshi_check"] = {"props": int(len(pk)), "fused_closer_share": float(closer.mean()), "binomial_p_one_sided": float(stats.binomtest(int(closer.sum()), max(nz, 1), 0.5, alternative="greater").pvalue),
                           "mean_abs_gap_fused": float((pk["kalshi"] - pk["fused"]).abs().mean()), "mean_abs_gap_median": float((pk["kalshi"] - pk["median"]).abs().mean())}
    s = pd.Series(dict(zip(books, par["sigma"])))
    sharp = s[s.index.isin(F.SHARP)].to_numpy(); retail = s[~s.index.isin(F.SHARP)].to_numpy()
    res["validity"] = {"sigma_by_book": s.round(4).to_dict(), "sharp_sigma_mean": float(sharp.mean()), "retail_sigma_mean": float(retail.mean()),
                       "mann_whitney_p_sharp_lower": float(stats.mannwhitneyu(sharp, retail, alternative="less").pvalue), "beta_by_book": dict(zip(books, np.round(par["beta"], 4).tolist())), "q_per_hour": par["q"]}
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(res, indent=1, default=str))
    (DOCS / "fusion_results.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


def freeze():
    q, books, par = prepare()
    g = K.games().set_index("game_id")["kickoff_utc"]
    up = q[~q["final_game"] & (q["game_id"].map(g) > pd.Timestamp.now(tz="UTC"))]
    if up.empty:
        sys.exit("no unplayed games")
    f = final_rows(up)
    fq, props = centers(f, books, par, {b: 1.0 for b in books})
    week = int(props["week"].min())
    rows = [{"game_id": r.game_id, "stat": r.stat, "fused_line": round(float(r.fused), 2), "median_line": round(float(r.median), 2), "books": int(r.nb)} for r in props.itertuples()]
    gaps = [{"game_id": r.game_id, "gsis_id": r.gsis_id, "stat": r.stat, "book": r.book, "line": r.line, "std_gap": round(float(r.d), 3)} for r in fq.itertuples()]
    rec = {"season": 2026, "week": week, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "props": rows, "book_gaps": gaps,
           "note": "Fused lines and standardized book gaps for unplayed games. Outcomes are scored later. Nothing is backfilled."}
    canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":"))
    rec["sha256"] = hashlib.sha256(canon(rec).encode()).hexdigest()
    out = ROOT / "data" / "fusion" / "frozen"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"week_2026_{week:02d}.json"
    if path.exists():
        sys.exit(f"{path.name} already saved; write-once")
    path.write_text(json.dumps(rec))
    with (ROOT / "data" / "fusion" / "ledger.jsonl").open("a") as fh:
        fh.write(canon({"file": path.name, "sha256": rec["sha256"], "created_at": rec["created_at"], "props": len(rows)}) + "\n")
    print({"file": path.name, "props": len(rows), "book_gaps": len(gaps), "sha256": rec["sha256"]})


if __name__ == "__main__":
    {"gate": gate, "run": run, "freeze": freeze}[sys.argv[1]]()
