"""Improvement protocol Step 3: screen the 8 winner variants against each other on seasons 2012 to 2025. No market data used.
Usage: python i3_screen.py rehearsal | real   (conditions: PROTOCOL2.md)"""
import sys
from itertools import combinations
from steps import *

MODE = sys.argv[1]
res = header(f"i3_{MODE}")
wf = pd.read_parquet(HW / "walk_forward.parquet")
wf = wf[(wf.season <= 2025)].dropna(subset=WIN_VARIANTS + ["y_home_win"]).reset_index(drop=True)
wf["wk"] = wf.season.astype(str) + "_" + wf.week.astype(int).astype(str).str.zfill(2)
PAIRS = list(combinations(WIN_VARIANTS, 2))
OTHERS = [v for v in WIN_VARIANTS if v != "p_elo"]


def holm(p):
    p = np.asarray(p, float); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for r, i in enumerate(o):
        run = max(run, (m - r) * p[i]); adj[i] = min(run, 1.0)
    return adj


def screen(df, rng, B=2000):
    y = df.y_home_win.to_numpy(float); codes, k = codes_of(df)
    L = {v: ll(df[v].to_numpy(float), y) for v in WIN_VARIANTS}
    pairs = []
    for a, b in PAIRS:
        c = cl_mean(L[a] - L[b], codes, k)            # positive: a is worse than b
        pairs.append({"a": a, "b": b, **c, "p": float(2 * tdist.sf(abs(c["mean"] / c["se"]), k - 1))})
    adj = holm([p["p"] for p in pairs])
    for p, q in zip(pairs, adj): p["p_holm"] = float(q)
    D = np.column_stack([L["p_elo"] - L[v] for v in OTHERS])    # positive: variant beats Elo
    sp = spa_rc(D, codes, k, rng, B)
    elo_p = []
    for j, v in enumerate(OTHERS):
        c = cl_mean(D[:, j], codes, k); elo_p.append({"variant": v, **c, "p": float(2 * tdist.sf(abs(c["mean"] / c["se"]), k - 1))})
    adj7 = holm([e["p"] for e in elo_p])
    for e, q in zip(elo_p, adj7): e["p_holm"] = float(q); e["worth_testing"] = bool(q < 0.05 and e["mean"] > 0)
    return {"pairs": pairs, "vs_elo": elo_p, "spa": sp, "n_games": int(len(df)), "clusters": int(k), "mean_log_loss": {v: float(L[v].mean()) for v in WIN_VARIANTS}}


if MODE == "rehearsal":
    def sim(world, rng, th=0.8):
        L0 = logit(wf.p_elo.to_numpy(float)); n = len(L0); z = rng.standard_normal(n)
        d = wf[["wk"]].copy(); d["y_home_win"] = (rng.random(n) < sigmoid(L0 + th * z)).astype(float)
        for v in WIN_VARIANTS:
            s = 0.4 if (world == "planted" and v == "p_xgb_deep") else 1.0
            d[v] = sigmoid(L0 + th * (z + s * rng.standard_normal(n)))
        return d
    fw = spa_fp = 0
    N0 = 400
    for i in range(N0):
        r = screen(sim("exch", np.random.default_rng(1000 + i)), np.random.default_rng(i), B=500)
        fw += any(p["p_holm"] < 0.05 for p in r["pairs"]); spa_fp += r["spa"]["p_spa"] < 0.05
    det = 0
    for i in range(100):
        r = screen(sim("planted", np.random.default_rng(5000 + i)), np.random.default_rng(i), B=500)
        det += [e for e in r["vs_elo"] if e["variant"] == "p_xgb_deep"][0]["worth_testing"]
    res.update({"datasets_null": N0, "holm_family_wise_false_positive": fw / N0, "spa_false_positive": spa_fp / N0, "planted_detection_rate": det / 100, "games": int(len(wf)), "clusters": int(wf.wk.nunique())})
    res["conditions"] = {"spa_fp_1_to_9": 0.01 <= spa_fp / N0 <= 0.09, "holm_fwer_le_9": fw / N0 <= 0.09, "planted_ge_80": det / 100 >= 0.80}
    res["PASS"] = bool(all(res["conditions"].values()))
    write("i3_rehearsal.json", res); print("I3 REHEARSAL", "PASS" if res["PASS"] else "FAIL", json.dumps(res["conditions"]), res["holm_family_wise_false_positive"], res["spa_false_positive"], res["planted_detection_rate"])
else:
    assert json.load(open(OUT / "i3_rehearsal.json"))["PASS"], "Step 3 rehearsal has not passed"
    r = screen(wf, np.random.default_rng(SEED), B=2000)
    res.update(r)
    res["variants_counted"] = len(WIN_VARIANTS); res["pairs_counted"] = len(PAIRS); res["spa_candidates"] = len(OTHERS)
    res["worth_testing_against_market"] = [e["variant"] for e in r["vs_elo"] if e["worth_testing"]]
    res["checks"] = {"games_ge_3000": r["n_games"] >= 3000, "clusters_ge_200": r["clusters"] >= 200, "counts_8_28": res["variants_counted"] == 8 and res["pairs_counted"] == 28,
                     "every_pair_has_interval_and_holm_p": all("lo" in p and "p_holm" in p for p in r["pairs"]), "spa_computed": "p_spa" in r["spa"]}
    res["PASS"] = bool(all(res["checks"].values()))
    write("i3_screen.json", res); print("I3 REAL", "PASS" if res["PASS"] else "FAIL", json.dumps(res["checks"]))
