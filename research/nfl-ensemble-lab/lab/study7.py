"""Phase 7 development-only challenger test (no hyperparameter search, no validation seasons).

Pre-declared before results:
  candidates  = champion feature groups + {QB v2} / + {snap model} / + {both}
  models      = each family's champion hyperparameters, unchanged
  ensemble    = equal-weight mean of the six families (champion weights came from 2023-24)
  rule        = log-loss gain > 0 on 2019-21 (mean of seasons) AND gain >= 0 on 2022
Qualifying candidates may become frozen shadow challengers; nothing is promoted.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import metrics as M
from .config import ARTIFACTS_DIR
from .features import P7_QB, P7_SNAP
from .longrun import DEV_FOLDS, FAMILIES, _prepare_data, champion_family_config, evaluate_config

OUT = ARTIFACTS_DIR / "phase7"
SEL, CHECK = (2019, 2020, 2021), 2022
CANDIDATES = {"qb_v2": [P7_QB], "snap_model": [P7_SNAP], "qb_v2+snap_model": [P7_QB, P7_SNAP]}


def run(threads: int = 4, progress=print) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    data, groups = _prepare_data()
    preds = {}
    for fam in FAMILIES:
        base = champion_family_config(fam)
        for name, extra in ({"champion": []} | CANDIDATES).items():
            cfg = base | {"groups": list(base["groups"]) + [g for g in extra if g in groups]}
            r = evaluate_config(data, fam, cfg, groups, DEV_FOLDS, threads)
            preds[(fam, name)] = r["preds"]
        progress(f"  {fam}: evaluated champion + {len(CANDIDATES)} candidates")
    ref = preds[(FAMILIES[0], "champion")]
    y = {s: ref[s]["y"] for s in DEV_FOLDS}
    rows, per_family = [], []
    ens = {name: {s: np.mean([preds[(f, name)][s]["p"] for f in FAMILIES], axis=0) for s in DEV_FOLDS}
           for name in ["champion", *CANDIDATES]}
    ll = {name: {s: M.log_loss(y[s], e[s]) for s in DEV_FOLDS} for name, e in ens.items()}
    for name in CANDIDATES:
        g_sel = float(np.mean([ll["champion"][s] - ll[name][s] for s in SEL]))
        g_chk = float(ll["champion"][CHECK] - ll[name][CHECK])
        rows.append({"candidate": name, "groups_added": ", ".join(CANDIDATES[name]), "gain_2019_21": g_sel,
                     "gain_2022_check": g_chk, **{f"ll_{s}": ll[name][s] for s in DEV_FOLDS},
                     "qualifies": bool(g_sel > 0 and g_chk >= 0)})
        for f in FAMILIES:
            fl = {s: M.log_loss(y[s], preds[(f, "champion")][s]["p"]) - M.log_loss(y[s], preds[(f, name)][s]["p"]) for s in DEV_FOLDS}
            per_family.append({"candidate": name, "family": f, "gain_2019_21": float(np.mean([fl[s] for s in SEL])),
                               "gain_2022_check": float(fl[CHECK])})
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "dev_challenger_test.csv", index=False)
    pd.DataFrame(per_family).to_csv(OUT / "dev_challenger_by_family.csv", index=False)
    champ = {f"ll_{s}": ll["champion"][s] for s in DEV_FOLDS}
    (OUT / "dev_challenger_test.json").write_text(json.dumps({"rule": "gain_2019_21 > 0 and gain_2022 >= 0",
                                                              "champion_equal_weight": champ,
                                                              "results": rows}, indent=2))
    oof = pd.DataFrame({"season": np.concatenate([[s] * len(y[s]) for s in DEV_FOLDS]),
                        "game_id": np.concatenate([ref[s]["game_id"] for s in DEV_FOLDS]),
                        "home_win": np.concatenate([y[s] for s in DEV_FOLDS]),
                        **{f"{f}|{n}": np.concatenate([preds[(f, n)][s]["p"] for s in DEV_FOLDS])
                           for f in FAMILIES for n in ["champion", *CANDIDATES]}})
    oof.to_parquet(OUT / "dev_oof.parquet", index=False)
    return {"results": res, "champion": champ}


def load() -> dict:
    p = OUT / "dev_challenger_test.csv"
    if not p.exists():
        return {}
    out = {"results": pd.read_csv(p)}
    if (OUT / "dev_challenger_by_family.csv").exists():
        out["by_family"] = pd.read_csv(OUT / "dev_challenger_by_family.csv")
    return out
