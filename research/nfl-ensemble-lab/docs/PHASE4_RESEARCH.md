# Phase 4: advanced football intelligence and long-run model research (2026-10-17)

## 1. New historical data (all free nflverse-data releases, downloaded and cached automatically)
| Source | Seasons | What it adds | Limits |
|---|---|---|---|
| `pbp_participation` | 2016–2025 | personnel (11 / heavy), box counts, nickel/dime faced, blitz (5+ rushers), pressure, time to throw | pressure and time to throw cover about 40% of plays before 2018; man/zone only 2023+ (unused); no 2026 file yet, so 2026 games use 2025 tendencies |
| `nextgen_stats` (weekly) | 2016–2026 | CPOE, time to throw, aggressiveness, air-yards differential, RYOE, rush efficiency, stacked-box rate, separation, YAC over expected, cushion | player-weeks below NGS volume thresholds are absent (about 80% game coverage in 2016) |
| `pfr_advstats` (weekly) | 2018–2026 | pressured/blitzed/hit rates, bad throws, drops, yards before/after contact, broken tackles, defensive pressure/blitz and missed-tackle rates | missing before 2018 (kept as missing) |
| `snap_counts` + `players` | 2012–2026 | snap-weighted OL and defensive experience (season − rookie season), depth (players ≥25% snaps), returning-snap share | experience uses a static rookie season |
| lab ratings (derived) | 2016–2026 | strength of schedule faced | – |

Investigated but not used:
- FTN charting: 2022+ only.
- Depth charts 2016–2024: no publication timestamps.
- Weekly roster status: game-day inactives are not pregame information.
- ESPN QBR: redundant with EPA.
- FiveThirtyEight Elo: discontinued, and its QB adjustment used actual starters.
- Kaggle, PFF, SIS: login or subscription required, not accessed.
- Historical weather: observations or short-lead analyses only.

Every value is aggregated per team-game and used only for **later** games: a strictly-pregame
as-of join with season blend and last-5 windows, plus a defensive mirror (what each defense allowed).

**New features:** 94 per-team columns, giving **100 model-eligible features** in six groups (personnel
& pressure 22, NGS 28, PFR 26, roster 16, schedule 2, matchups 6). The feature store now has 1,073 columns.

**Leakage:** the real-data perturbation gate now also scrambles every new source for the target game.
0 of 1,041 columns changed for the 2,026 games at or before it; 713 later games changed.

## 2. Did the new features help? (`python -m lab.study4`, nested tuning, Phase 3 gate)
**0 of 72 candidates passed** (each group added to the champion features, all of Phase 4, and
"everything", × 9 methods).
- **All Phase 4 groups together:** significantly *worse* (pooled +0.0036 log loss, CI +0.0003 to +0.0069).
- **"Everything":** dev +0.0054, validation −0.0042, pooled +0.0020 (not significant).
- **Best single additions** (advanced matchups, schedule strength): within ±0.001, i.e. noise.
- **2026 to date:** some groups look slightly better, but at 79 games that is noise and not used.

## 3. Long-run research engine (`lab/longrun.py`)
- **Search:** Optuna TPE per family with median pruning across folds. Families searched: Logistic
  Regression, XGBoost, Decision Tree, Random Forest, MLP and Single-layer NN.
- **Search space:** feature-group selection, in-fold top-k feature filter, calibration (none/Platt), and
  family hyperparameters / architecture (MLP layers and widths).
- **Allocation:** every family is guaranteed at least 10% of trials; the rest goes to families whose best
  score is still improving.
- **Objective:** walk-forward dev folds 2019–2022. Filter and calibration are fit inside each fold.
  A test proves predictions don't change when that season's outcomes are flipped.
- **Validation:** checked once per finished job on 2023–24 (plus 2025 diagnostic). Every look is logged,
  and the significance level is 0.05 ÷ looks.
- **Process:** a detached background process with a lock against duplicate jobs, below-normal priority
  (default 6 of 16 threads), and a memory guard (pauses below 2 GB free).
- **Control:** pause / continue / stop via a control file; resume keeps all completed trials (SQLite study).
- **Monitoring:** live status of CPU, memory, trials, pruning, best per family and ETA.

**Real 1-hour run (job lr20261017_000704):** 2,114 trials, all six families (341–360 each), 0 errors.
- **Interruption (real):** Windows/OneDrive briefly locked the status file and the job stopped as
  "crashed" at 50 minutes. I made file writes retry and then resumed the job; all completed trials were kept.
- **Bug found and fixed:** Optuna stores pruned trials' partial (first-fold) scores, and they had been
  treated as full results. Only completed trials now count, and a regression test was added. This made
  validation look #2 invalid. The corrected check is look #3 (level 0.0167); the first look was my own
  12-trial smoke test.

| Family | Dev (optimised) champion → best | Validation 2023–24 Δ vs champion version | 2025 diag. Δ | Dev→val gap |
|---|---|---|---|---|
| Logistic Regression | 0.6358 → 0.6341 | −0.0027 (CI −0.010, +0.004) | −0.0024 | −0.002 |
| XGBoost | 0.6328 → 0.6310 | +0.0024 | 0.0000 | +0.005 |
| Decision Tree | 0.6560 → 0.6448 | −0.0059 (CI −0.018, +0.007) | −0.0063 | +0.005 |
| Random Forest | 0.6340 → 0.6337 | **+0.0094 (CI excludes 0: worse)** | +0.0084 | +0.006 |
| MLP | 0.6382 → 0.6307 | +0.0112 | +0.0074 | **+0.018** |
| Single-layer NN | 0.6367 → 0.6288 | +0.0026 | +0.0021 | +0.010 |

**No family passed.** The search found configurations that look better on the seasons it searched,
but those gains shrink or reverse on validation (the MLP most of all). That is overfitting to the
search seasons, and exactly what the protocol is designed to catch. More search time did not produce
a stronger challenger.

## 4. Champion
Unchanged: **v20261016_212540, validation-weighted average.** Phase 3 showed the six models behave
like about 1.2 independent models. No feature group, ensemble variant or optimised configuration has
beaten it under honest chronological evaluation. A future winner can only become a shadow challenger
(tracked in every prospective snapshot) until 128+ prospective games show an improvement.

## 5. Debate and discovery
- **Model Debate:** shows each model's net attribution by football factor (opponent-adjusted strength,
  efficiency, recent form, QB, availability, travel/schedule, coaching, NGS, pressure, roster), which factor
  separates the voting blocs, an explicit note when models agree, and shadow-challenger probabilities.
  All of this comes from the models' own attributions.
- **Discovery:** now sees 523 features (Phase 3/4 included).
  - Experiment look #3 (level 0.0167): 33,856 candidates tested and **0 validated**. The smallest
    Holm-adjusted p was 0.69, so the stricter level made no difference.
  - Phase 4 features made up 15–20 of each 30 carried candidates, and all failed.

## 6. Remaining opportunities
- **Prospective evidence:** the archive (Phase 3) is the only genuinely independent test left; let it grow.
- **Data gaps:** a 2026 participation file once nflverse publishes it; FTN charting once it spans more seasons.
- **Player-level modelling:** for example, replacement-player efficiency from participation player IDs.
  This needs careful as-of handling.
- **Market lines at the forecast cutoff:** now being collected in snapshots, enabling an honest market
  comparison after a season.
- **Validation budget:** further long-run jobs should be finalized sparingly. Each look raises the bar.
  Consider holding validation until a candidate already looks strong prospectively.
