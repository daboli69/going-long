"""python scripts/linemove_run.py gate | run   (docs/LINEMOVE_PREREG.md). run executes once."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import linemove as L  # noqa: E402

DOCS = ROOT / "docs"


def holm(p):
    order = sorted(p, key=p.get)
    out, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * p[k]))
        out[k] = run
    return out


if __name__ == "__main__":
    d = L.load()
    dec, conf = d[d["season"].isin(L.DECIDE)], d[d["season"].isin(L.CONFIRM)]
    sig = L.sigma_fit(dec)
    rng = np.random.default_rng(20261106)
    if sys.argv[1] == "gate":
        g = {"games": {"decide": int(len(dec)), "confirm": int(len(conf)), "prospective_2026": int((d["season"] == 2026).sum())}, "sigma_decide": sig, "tests": L.gate(conf, sig, rng)}
        (DOCS / "linemove_gate.json").write_text(json.dumps(g, indent=1))
        print(json.dumps(g, indent=1))
    else:
        marker = ROOT / "data" / "linemove" / "done.json"
        if marker.exists():
            sys.exit("Already run once. No rerun.")
        g = json.loads((DOCS / "linemove_gate.json").read_text())["tests"]
        res, pvals = {}, {}
        for t in L.TESTS:
            if not g[t]["informative"]:
                res[t] = {"read": False, "reason": "failed the power gate"}
                continue
            b_dec, b_conf = L.coef(t, dec, sig), L.coef(t, conf, sig)
            bs = L.boot(t, conf, sig, rng, 2000)
            p = float(min(1.0, 2 * min((np.sum(bs <= 0) + 1) / 2001, (np.sum(bs >= 0) + 1) / 2001)))
            eras = {}
            for name, ss in (("2016_2017_pinnacle", [2016, 2017]), ("2018_2024_bet365", list(range(2018, 2025))), ("2025_betr", [2025])):
                s = conf[conf["season"].isin(ss)]
                eras[name] = {"n": int(len(s)), "coef": L.coef(t, s, sig)}
            res[t] = {"read": True, "decide_coef": b_dec, "confirm_coef": b_conf, "confirm_ci95": [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], "p": p, "same_sign": bool(np.sign(b_dec) == np.sign(b_conf)), "eras_descriptive": eras}
            pvals[t] = p
        full = {t: pvals.get(t, 1.0) for t in L.TESTS}
        for t, a in holm(full).items():
            if not res[t]["read"]:
                continue
            res[t]["p_holm"] = a
            res[t]["passes"] = bool(a < 0.05 and res[t]["same_sign"])
        p26 = d[d["season"] == 2026]
        res["prospective_2026_descriptive"] = {t: L.coef(t, p26, sig) for t in L.TESTS} | {"n": int(len(p26))}
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(res, indent=1))
        (DOCS / "linemove_results.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
