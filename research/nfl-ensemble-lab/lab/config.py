"""Paths, seasons and the chronological evaluation protocol.

Everything the lab writes lives under LAB_ROOT so the GOING production
pipeline (repo-level data/, scripts/, api/) is never touched.
"""
from __future__ import annotations

import os
from pathlib import Path

LAB_ROOT = Path(os.environ.get("NFL_LAB_ROOT", Path(__file__).resolve().parents[1]))
DATA_DIR = LAB_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"            # downloaded source files (gitignored)
CACHE_DIR = DATA_DIR / "cache"        # normalized parquet (gitignored)
MODELS_DIR = LAB_ROOT / "models"      # versioned model bundles (gitignored)
ARTIFACTS_DIR = LAB_ROOT / "artifacts"  # out-of-sample predictions, metrics (gitignored)
SNAPSHOTS_DIR = LAB_ROOT / "snapshots"  # immutable weekly prediction snapshots (gitignored)
REPORTS_DIR = LAB_ROOT / "reports"    # Excel / CSV / JSON exports (gitignored)

# 2015 is downloaded only so 2016 games can use previous-season carryover.
CARRYOVER_SEASON = 2015
FIRST_SEASON = 2016

# Chronological protocol (see docs/METHODOLOGY.md).
DEV_SEASONS = tuple(range(2016, 2023))    # 2016-2022 development / tuning
VALIDATION_SEASONS = (2023, 2024)         # model, calibration and ensemble selection
TEST_SEASONS = (2025,)                    # untouched final test, scored once after selection
PROSPECTIVE_FROM = 2026                   # out-of-sample tracking of the live season
# Inner tuning folds use only development data: train on seasons < s, score s.
TUNING_FOLDS = (2020, 2021, 2022)
# First season that gets a walk-forward prediction (needs >= 2 prior training seasons).
WALK_FORWARD_START = 2018

RANDOM_SEED = 20260916

for _d in (RAW_DIR, CACHE_DIR, MODELS_DIR, ARTIFACTS_DIR, SNAPSHOTS_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
