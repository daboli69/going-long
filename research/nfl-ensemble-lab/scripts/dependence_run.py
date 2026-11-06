"""Dependence test (docs/DEPENDENCE_PREREG.md). Stages, in order:
  python scripts/dependence_run.py gate CLASS   structure only, no outcome is read
  python scripts/dependence_run.py merge        combine the class gate files
  python scripts/dependence_run.py fit          descriptive fit-season estimates
  python scripts/dependence_run.py freeze       weekly write-once joint probabilities for unplayed games
  python scripts/dependence_run.py score        held-out 2025, once, informative classes only
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import dependence as D  # noqa: E402

DOCS = ROOT / "docs"


def holm(p: dict) -> dict:
    order = sorted(p, key=p.get)
    out, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * p[k]))
        out[k] = run
    return out


def stage_fit(pairs, a):
    refs = {s: D.ecdf_ref(a, s) for s in ("pass_yds", "rec_yds", "rush_yds")}
    res = {}
    for cls, (s1, s2, _) in D.CLASSES.items():
        f = pairs[(pairs["cls"] == cls) & pairs["season"].isin(D.FIT_SEASONS)]
        u, v = D.to_u(f["p1"], refs[s1]), D.to_u(f["p2"], refs[s2])
        fits = D.fit_all(u, v)
        res[cls] = {"pairs": int(len(f)), "team_games": int(f.groupby(["game_id", "team"]).ngroups), "chosen": fits["chosen"],
                    **{k: {"par": list(fits[k]["par"]), "ll": fits[k]["ll"], "bic": float(fits[k]["bic"])} for k in ("gaussian", "t", "clayton")}}
    return res, refs


def stage_score(pairs, refs, gate):
    rng = np.random.default_rng(20261106)
    res, p_all = {}, {}
    for cls, (s1, s2, _) in D.CLASSES.items():
        if not gate[cls]["informative"]:
            res[cls] = {"scored": False, "reason": "failed the power or recovery gate"}
            continue
        f = pairs[(pairs["cls"] == cls) & pairs["season"].isin(D.FIT_SEASONS)]
        t = pairs[(pairs["cls"] == cls) & (pairs["season"] == D.TEST_SEASON)]
        ev = D.evaluate(D.to_u(f["p1"], refs[s1]), D.to_u(f["p2"], refs[s2]),
                        np.stack([D.z_of(D.to_u(t["p1"], refs[s1])), D.z_of(D.to_u(t["p2"], refs[s2]))], 1), t["game_id"].to_numpy(), rng)
        row = {"scored": True, "family": ev["family"], "par": list(ev["fits"][ev["family"]]["par"]), "games": int(len(ev["g_es"])), "pairs": int(len(t))}
        for k in ("es", "vs"):
            g = ev["g_" + k]
            tstat, pdm = D.dm_p(g)
            pb, ci = D.boot_p(g, rng)
            row[k] = {"mean_loss_gain": float(g.mean()), "dm_t": tstat, "p_dm": pdm, "p_boot": pb, "boot_ci95": list(ci), "p_used": max(pdm, pb)}
            p_all[f"{cls}:{k}"] = max(pdm, pb)
        res[cls] = row
    adj = holm(p_all) if p_all else {}
    for key, v in adj.items():
        cls, k = key.split(":")
        res[cls][k]["p_holm"] = v
    for cls, r in res.items():
        if r.get("scored"):
            r["passes"] = bool(r["es"]["p_holm"] < 0.05 and r["vs"]["p_holm"] < 0.05)
    return res


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "gate":
        cls = sys.argv[2]
        pairs, _ = D.load_pairs()
        out = D.gate(pairs, cls, np.random.default_rng(20261106 + list(D.CLASSES).index(cls)))
        (DOCS / f"dependence_gate_{cls}.json").write_text(json.dumps(out, indent=1))
        print(cls, json.dumps({k: out[cls][k] for k in ("power_at_0.15_both_scores", "recovery_ok", "informative", "games_for_80pct_power")}))
    elif st == "merge":
        g = {}
        for c in D.CLASSES:
            g.update(json.loads((DOCS / f"dependence_gate_{c}.json").read_text()))
        (DOCS / "dependence_gate.json").write_text(json.dumps(g, indent=1))
        for c, v in g.items():
            print(c, "power", v["power_at_0.15_both_scores"], "recovery_ok", v["recovery_ok"], "informative", v["informative"], "games for 80%", v["games_for_80pct_power"])
    elif st == "fit":
        pairs, info = D.load_pairs()
        a = D.load_marginals()
        res, _ = stage_fit(pairs, a)
        (DOCS / "dependence_fit.json").write_text(json.dumps({"inputs": info, "fit": res}, indent=1))
        for c, v in res.items():
            print(c, v["pairs"], v["chosen"], "rho", round(v["gaussian"]["par"][0], 3), "t", [round(x, 3) for x in v["t"]["par"]], "clayton", round(v["clayton"]["par"][0], 3))
    elif st == "freeze":
        from lab import dependence_week as W
        print(W.freeze(), W.verify())
    elif st == "score":
        marker = ROOT / "data" / "dependence" / "heldout_scored.json"
        if marker.exists():
            sys.exit("The 2025 held-out season was already scored once. No rerun.")
        gate = json.loads((DOCS / "dependence_gate.json").read_text())
        if not any(v["informative"] for v in gate.values()):
            sys.exit("No pair class passed the gate. The held-out season stays unscored.")
        pairs, _ = D.load_pairs()
        a = D.load_marginals()
        _, refs = stage_fit(pairs, a)
        res = stage_score(pairs, refs, gate)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(res, indent=1))
        (DOCS / "dependence_results.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
