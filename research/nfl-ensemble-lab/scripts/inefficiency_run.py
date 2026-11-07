"""Which markets are most inefficient, net of cost. Stages: build, gate, run (once). Rule: docs/INEFFICIENCY_PREREG.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import inefficiency as I  # noqa: E402

DOCS = ROOT / "docs"
DATA = ROOT / "data" / "inefficiency"
CACHE = ROOT / "data" / "cache" / "inefficiency_contracts.parquet"


def contracts() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_parquet(CACHE)
    d = I.all_contracts()
    d.to_parquet(CACHE)
    return d


def prepare():
    d = contracts()
    dec, con = d[d["era"] == "decide"], d[d["era"] == "confirm"]
    fit = I.fit_all(dec)
    bets = {m: I.choose(g, fit["par"][m]) for m, g in con.groupby("market") if m in fit["par"]}
    return d, dec, con, fit, bets


def gate():
    d, dec, con, fit, bets = prepare()
    out = {m: {**I.gate_market(b), "decide_n": int((dec["market"] == m).sum()), "confirm_n": int((con["market"] == m).sum()), "coef": [float(x) for x in fit["par"][m]]} for m, b in bets.items()}
    out["_pool"] = [float(x) for x in fit["pool"]]
    (DOCS / "inefficiency_gate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for m, v in out.items():
        if m != "_pool":
            print(m, {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items() if k != "coef"})


def run():
    marker = DATA / "done.json"
    if marker.exists():
        raise SystemExit("already run once (data/inefficiency/done.json)")
    g = json.loads((DOCS / "inefficiency_gate.json").read_text(encoding="utf-8"))
    d, dec, con, fit, bets = prepare()
    markets = [m for m in bets if g[m].get("informative") and g[m]["n_bets"] >= I.MIN_BETS]
    res = {"not_read": {m: ("failed its gate" if not g[m].get("informative") else "rule rarely fires") for m in bets if m not in markets}}
    # cost and Murphy for every market, no confirm outcomes needed for cost
    desc = {}
    for m, gm in d.groupby("market"):
        hold = float((gm["price_a"] + gm["price_b"] - 1).mean())
        desc[m] = {"n": int(len(gm)), "mean_overround": hold, "cost_per_random_side_bet": hold / 2, **I.murphy(gm["p"], gm["y"])}
    res["descriptive"] = desc
    # primary: confirm net per game, bootstrap by group
    by_group: dict[str, list] = {}
    for m in markets:
        by_group.setdefault(I.GROUPS[m], []).append(m)
    means, se, boots, n_bets = {}, {}, {}, {}
    for grp, ms in by_group.items():
        series = {m: I.cluster_means(bets[m], "won") for m in ms}
        idx = sorted(set().union(*[s.index for s in series.values()]), key=str)
        M = np.column_stack([series[m].reindex(idx).to_numpy() for m in ms])
        bt = I.boot(M, 2000, seed=len(grp))
        for j, m in enumerate(ms):
            means[m] = float(np.nanmean(M[:, j]))
            se[m] = float(bt[:, j].std())
            boots[m] = bt[:, j]
            n_bets[m] = int(bets[m]["bet"].sum())
    ms = list(means)
    theta, s = np.array([means[m] for m in ms]), np.array([se[m] for m in ms])
    t_obs = theta / s
    t_star = np.column_stack([(boots[m] - means[m]) / se[m] for m in ms])
    pvals = np.array([float(np.mean((boots[m] - means[m]) / se[m] >= means[m] / se[m])) for m in ms])
    rw = I.romano_wolf(t_obs, t_star)
    q = I.bh(pvals)
    if len(ms) >= 2:
        post, psd, tau2, mu = I.dl_shrink(theta, s)
    else:
        post, psd, tau2, mu = theta.copy(), s.copy(), float('nan'), float('nan')
        res['ranking'] = 'impossible: fewer than two markets passed the gate, no shrinkage or ranking'
    rows = []
    for i, m in enumerate(ms):
        lo, hi = np.percentile(boots[m], [2.5, 97.5])
        rows.append({"market": m, "bets": n_bets[m], "net": theta[i], "ci95": [float(lo), float(hi)], "se": float(s[i]), "shrunken": float(post[i]), "shrunken_sd": float(psd[i]),
                     "p_one_sided": float(pvals[i]), "p_romano_wolf": float(rw[i]), "q_bh": float(q[i]), "smallest_detectable": g[m]["smallest_detectable"], "gate_power": g[m]["power"]})
    res["primary"] = sorted(rows, key=lambda r: -r["shrunken"])
    res["tau2"], res["pooled_mean"] = float(tau2), float(mu)
    # descriptive favourite/longshot nets and halves for the game lines
    extra = {}
    for m in ms:
        c = bets[m].copy()
        fav_a = c["p"] >= 0.5
        fav_net = np.where(fav_a, c["y"] - c["price_a"], (1 - c["y"]) - c["price_b"])
        dog_net = np.where(~fav_a, c["y"] - c["price_a"], (1 - c["y"]) - c["price_b"])
        extra[m] = {"favourite_net": float(np.mean(fav_net)), "longshot_net": float(np.mean(dog_net))}
    res["extra"] = extra
    res["recalibration"] = {m: [float(x) for x in v] for m, v in fit["par"].items()}
    DATA.mkdir(parents=True, exist_ok=True)
    (DOCS / "inefficiency_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    marker.write_text(json.dumps({"done": True}), encoding="utf-8")
    print(json.dumps(res["primary"], indent=1)[:3000])
    print(res["not_read"])


def freeze():
    """Write-once hashed record of sportsbook-prop contracts for unplayed games with the rule's side. Nothing is backfilled."""
    import hashlib
    from lab import basket as BK
    d, dec, con, fit, bets = prepare()
    lg = BK.legs().sort_values("snap").groupby(["book", "game_id", "gsis_id", "stat"], as_index=False).tail(1)
    _, _, done = BK.actuals()
    lg = lg[~lg["game_id"].isin(done)].copy()
    if lg.empty:
        raise SystemExit("no unplayed games in the newest feed")
    pa, pb = BK.american_p(lg["over_odds"]), BK.american_p(lg["under_odds"])
    rows = []
    for st, key in (("pass_yds", "b_pass_yds"), ("rec_yds", "b_rec_yds")):
        m = (lg["stat"] == st).to_numpy()
        c = pd.DataFrame({"p": lg.loc[m, "p_over"].to_numpy(), "price_a": pa[m], "price_b": pb[m], "y": 0.0, "cluster": lg.loc[m, "game_id"].to_numpy()})
        ch = I.choose(c, fit["par"][key])
        for r, (_, o) in zip(ch.itertuples(), lg[m].iterrows()):
            rows.append({"market": key, "game_id": o["game_id"], "book": o["book"], "gsis_id": o["gsis_id"], "line": float(o["line"]), "price_over": float(r.price_a), "price_under": float(r.price_b), "fair_over": float(r.p),
                         "rule_side": "over" if r.side_a else "under", "rule_edge": float(r.edge), "bet": bool(r.bet), "snap": str(o["snap"])})
    wk = int(lg["week"].min())
    out = DATA / f"week_2026_{wk:02d}.json"
    if out.exists():
        raise SystemExit(f"{out.name} already frozen")
    body = json.dumps(rows, sort_keys=True)
    DATA.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"week": wk, "rows": rows, "sha256": hashlib.sha256(body.encode()).hexdigest()}), encoding="utf-8")
    print(out.name, len(rows), hashlib.sha256(body.encode()).hexdigest()[:12])


if __name__ == "__main__":
    {"build": lambda: print(contracts().groupby(["market", "era"]).size().unstack()), "gate": gate, "run": run, "freeze": freeze}[sys.argv[1]]()
