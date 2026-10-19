"""Props simulator v2 (docs/PROPS_V2_PREREGISTRATION.md): v1 plus three fixes, every value set on training seasons or 2022.

Fix 1(a) gain correction -> sim.fit_gains (training seasons, at run time); fix 1(b) per-stat mean ratios -> MEAN_CORR;
fix 2 verified calibration -> sim.calibrate_v2; fix 3 dispersion -> DISPERSION. MEAN_CORR and DISPERSION come from
`python -m lab.props.tune_v2` (2022 only, sub-models 2016-21); see artifacts/props/v2_tuning/selection.json.
"""
from __future__ import annotations

import copy

import numpy as np

from . import sim as S

DISPERSION = {"sigma_e": 0.25, "kappa_recv": 30.0, "kappa_rush": 10.0}     # 2022 tuning (selection.json, 136 games)
MEAN_CORR = {"pass_yds": 0.9402, "rush_yds": 1.0432, "rec_yds": 0.9745, "rec": 0.9653}   # 2022 actual / simulated
CLIP = (0.85, 1.05)
TUNED = True


def prepare(T1: dict, dispersion=None) -> dict:
    """v2 tables from v1's (already clock-calibrated) tables; T1 is not modified."""
    T = copy.copy(T1)
    T.pop("kappa", None)
    T.update(dispersion or DISPERSION)
    T["g_comp"], T["g_rush"] = 1.0, 1.0
    S.fit_gains(T)
    return T


def correct(x: np.ndarray, stat: str, corr=None) -> np.ndarray:
    """Fix 1(b): post-simulation per-stat mean correction (2022 ratio, clipped)."""
    return x * float(np.clip((corr or MEAN_CORR)[stat], *CLIP))
