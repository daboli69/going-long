"""Write-once quarterback refresh for one game. Rule: docs/GUT_PROTOCOL.md (Part 2).

    .venv/Scripts/python.exe scripts/qb_refresh.py 2026_09_BUF_MIN [--market 0.23]

Rebuilds the quarterback state from the latest injury snapshot (everything else as at the freeze cutoff) and appends one record to
reports/qb_refresh/refresh_ledger.jsonl. The record holds the component probabilities with the freeze's inputs and with the refreshed
quarterback state, computed in the same run so they are comparable; they are not the production joint p_win. Refuses a second record
for the same game. Never touches the freeze.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lab import homewin_deep as h  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("gid")
ap.add_argument("--market", type=float, default=None, help="market home win probability at refresh time")
args = ap.parse_args()
GID = args.gid
_season, _week, away, home = GID.split("_")
s, w = int(_season), int(_week)
now = pd.Timestamp.now(tz="UTC")
LEDGER = ROOT / "reports" / "qb_refresh" / "refresh_ledger.jsonl"
if LEDGER.exists() and any(json.loads(l)["gid"] == GID for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()):
    raise SystemExit(f"{GID} already has a refresh record; write-once")

data, _ = h.load_all(False)
feats = pd.read_parquet(h.CACHE / "features.parquet")
preds = pd.read_parquet(h.CACHE / "walk_forward.parquet")
params = {int(k): v for k, v in json.loads((h.CACHE / "deep_params.json").read_text(encoding="utf-8")).items()}
T = h.week_cutoff(data, s, w)
print("decision cutoff T:", T)
end = h.season_end_ratings(data.team_games[data.team_games["season"] < s])
pm = h.qb_prior_mean(data.qb_games[data.qb_games["season"] <= 2011])
values = h._qb_value(data.qb_games[data.qb_games["kickoff_utc"] < T], pm)

f0 = h.week_features(data, s, w, cutoff=T, end_ratings=end, prior_mean=pm)
f0 = f0[f0["gid"] == GID].copy()
f1 = f0.copy()
for side, team in (("home", home), ("away", away)):
    st = h.team_qb_state(data, team, s, w, now, values, pm)
    f1[f"qb_delta_{side}"] = st["qb_delta"]
    f1[f"qb_change_{side}"] = st["qb_change"]
    f1[f"qb_expected_{side}"] = st["qb_expected"]
    print(team, "QB state now:", st)
f1["qb_delta_diff"] = f1["qb_delta_home"] - f1["qb_delta_away"]
print("qb_delta_diff frozen vs now:", float(f0["qb_delta_diff"].iloc[0]), "->", float(f1["qb_delta_diff"].iloc[0]))

usable = feats[feats["played"] & (feats["kickoff_utc"] < T)]
cls = usable[~usable["tie"]].assign(y_home_win=lambda d: d["y_home_win"].astype(int))
hist = preds[preds["kickoff_utc"] < T]
resid = (hist["margin"] - hist["pred_margin"]).to_numpy()
prm = params.get(s) or h.tune_deep(cls, s)

out = {}
for name, f in (("frozen_inputs", f0), ("qb_updated", f1)):
    pred, p_margin, sigma = h.margin_predict(usable[usable["season"] >= h.MARGIN_TRAIN_START], f, resid)
    p_deep = h.deep_predict(cls[cls["season"] >= h.MARGIN_TRAIN_START], f, prm)
    pmp = h.platt(hist["p_margin"].to_numpy(), hist["y_home_win"].to_numpy(), p_margin)
    pdp = h.platt(hist["p_xgb_deep"].to_numpy(), hist["y_home_win"].to_numpy(), p_deep)
    out[name] = dict(pred_margin_home=float(pred[0]), sigma=float(sigma), p_margin=float(p_margin[0]), p_margin_platt=float(pmp[0]),
                     p_xgb_deep=float(p_deep[0]), p_xgb_deep_platt=float(pdp[0]), qb_home=f["qb_expected_home"].iloc[0], qb_change_home=int(f["qb_change_home"].iloc[0]))
print(json.dumps(out, indent=1))

rec = {"gid": GID, "refreshed_at": now.isoformat(), "cutoff_T": str(T), "market_p_home": args.market, "frozen_inputs": out["frozen_inputs"], "qb_updated": out["qb_updated"]}
LEDGER.parent.mkdir(parents=True, exist_ok=True)
with LEDGER.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec) + "\n")
print("wrote", LEDGER)
