"""Saved record of the calibration behind Amendment 7: Step 2's detection design at the stronger planted world (written after review found no file for it)."""
import sys
from steps import *
from steps import _power_curve
ds = real_dataset(2025)
W = ds["winners"]; codes, k = codes_of(W); L0 = logit(W.p_t90.to_numpy(float))
def mk(th):
    def f(sB, r):
        n = len(L0); z = r.standard_normal(n); yy = (r.random(n) < sigmoid(L0 + th * z)).astype(float)
        return ll(sigmoid(L0 + th * (z + r.standard_normal(n))), yy) - ll(sigmoid(L0 + th * (z + sB * r.standard_normal(n))), yy)
    return f
res = header("planted_strong_calibration")
for th in (0.8, 1.2, 1.6):
    cur = _power_curve(mk(th), codes, k, [1.0, 0.2], 300, seed=3)
    res[f"theta_{th}"] = [{"sB": c["sB"], "expected_gain": c["expected_gain"], "power": c["power_one_sided_2.5pct"]} for c in cur]
write("planted_strong_calibration.json", res)
print(json.dumps({k_: v for k_, v in res.items() if k_.startswith("theta")}, indent=1))
