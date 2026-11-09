"""Check lab/epnet.py against the effects PR 618 reports (rule: docs/EPNET_ROBUST_RULE.md). Read-only; writes docs/epnet_check.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import epnet  # noqa: E402

SEASON = 2026


def main():
    vt = epnet.v_table()
    d = epnet.season_net(SEASON, vt)
    recon = float((d["ep"] - d["ep_old_recon"]).abs().max())
    td, fg = d[d["td_play"]], d[d["fg_play"]]
    passes = d[(d["pass_attempt"] == 1) & (d["play_type"] == "pass") & d["passer_id"].notna() & d["epa"].notna() & d["epa_net"].notna()]
    g = passes.groupby("passer_id").agg(n=("epa", "size"), old=("epa", "mean"), new=("epa_net", "mean"))
    g = g[g["n"] >= 100]
    g["shift"] = g["new"] - g["old"]
    sp = float(g["old"].rank().corr(g["new"].rank()))
    out = {"season": SEASON, "recon_max_abs_err_ep": round(recon, 6),
           "mean_ep_old": round(float(d["ep"].mean()), 3), "mean_ep_net": round(float(d["ep_net"].mean()), 3),
           "mean_ep_diff": round(float((d["ep_net"] - d["ep"]).mean()), 3),
           "td_value_mean": round(float(td["after_net"].abs().mean()), 3), "td_n": int(len(td)),
           "fg_value_mean": round(float(fg["after_net"].abs().mean()), 3), "fg_n": int(len(fg)),
           "passers": int(len(g)), "max_abs_epa_pass_shift": round(float(g["shift"].abs().max()), 3), "mean_abs_epa_pass_shift": round(float(g["shift"].abs().mean()), 3),
           "spearman_epa_pass": round(sp, 4), "v_table": vt.round(3).to_dict("records")}
    checks = {"1 mean ep diff in [-0.55,-0.25]": -0.55 <= out["mean_ep_diff"] <= -0.25,
              "2 td value in [5.6,6.1]": 5.6 <= out["td_value_mean"] <= 6.1,
              "3 fg value in [1.8,2.3]": 1.8 <= out["fg_value_mean"] <= 2.3,
              "4 passer shift <= 0.10 and spearman >= 0.98": out["max_abs_epa_pass_shift"] <= 0.10 and sp >= 0.98}
    out["checks"] = checks
    out["reproduces_pr"] = all(checks.values())
    (ROOT / "docs" / "epnet_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "v_table"}, indent=1))


if __name__ == "__main__":
    main()
