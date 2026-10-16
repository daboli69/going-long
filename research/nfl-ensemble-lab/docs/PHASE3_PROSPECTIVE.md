# Phase 3: prospective validation and baseline research (2026-10-16)

## 1. Automated prospective archive (`lab/prospective.py`)
The Windows task "NFL Ensemble Lab - Data Refresh" (daily 09:00 and 18:00, catch-up when the PC
returns) runs `refresh_data.bat` → `python -m lab.cli scheduled`. That runs refresh → snapshots
→ scoring → run log. It never runs discovery or retraining.

**Cutoffs**
| Window | When | Snapshots |
|---|---|---|
| early | 30 h to 8 days before kickoff | first eligible run only |
| final | 5 min to 30 h before kickoff | new snapshot only when the inputs' content hash changed; the last one before kickoff is scored |

The 09:00/18:00 schedule gives every slot at least one final opportunity: Thursday night (Wed/Thu 18:00),
Sunday London (Sat 09:00), Sunday afternoon/evening (Sat 09:00 and 18:00, Sun 09:00), and Monday night
(Sun 18:00, Mon 09:00 and 18:00).

**Each snapshot** (`snapshots/prospective/<season>_wNN/<game_id>/<window>_<UTC>.json`, exclusive
create, read-only, listed in the append-only `ledger.jsonl`) holds:
- game, matchup, kickoff and prediction time; data cutoff (refresh, injury-file and ESPN times);
  stale flag and reason
- all six calibrated and raw probabilities, the three probability ensembles, the champion, the vote,
  the six margins and the ensemble margin
- Phase 2 experimental adjusted probabilities and signals
- shadow-challenger probabilities, if any are registered
- projected QBs and flags; injury loads by position group; final-report status; the live injury
  monitor (key players, practice status, ESPN out/IR)
- missing-data indicators; the 85-feature snapshot; model version, code commit, source-file hashes
- the market line at snapshot time, which is a timestamp-valid benchmark from now on
- a live weather forecast (Open-Meteo), for monitoring only

**Safeguards:** no snapshot within 5 minutes of or after kickoff; one early snapshot per game; no
duplicate final snapshots for unchanged inputs; stale-data flag (refresh failure or data older than
12 h); and a missing-prediction report giving a reason for each gap ("no scheduled run while the
window was open (PC off or asleep?)", "run failed: …"). Games before tracking started are labelled
as such and are never back-filled.

**Scoring** (`artifacts/prospective/metrics.json`, derived; snapshots never edited) covers accuracy,
log loss, Brier, ECE and calibration buckets; each of the six models; the market at snapshot time;
experimental adjustments; shadow challengers; ensemble margin vs actual and vs the spread at snapshot;
favorites vs underdogs; injury-report completeness; and per-week performance.

**First real run (2026-10-16 23:35 UTC):** 14 games archived (all early window). A second run
skipped all 14 as unchanged. No tracked game has finished yet, so 0 games are scored.

## 2. New pregame features (Phase 3 group, `p3_*`)
| Feature | Source / rule | Historical validity |
|---|---|---|
| Travel km, time-zone shift, body-clock kickoff hour | nfldata stadium id + static stadium coordinates and time zones (`lab/geo.py`) | Schedule facts, known in advance |
| Head-coach tenure, new-coach season, mid-season change | nfldata head coach per game | Coach identity is known before each game; tenure counts earlier games only (left-truncated at 2015) |
| Opponent-adjusted offensive and defensive EPA ratings | Ridge fit per week on games before that week's first kickoff | Same as existing ratings |
| OL lineup churn (distinct OL with ≥50% snaps over the last 4 games) | PFR snap counts | Earlier games only |

Investigated and rejected for history:
- **Weather:** Open-Meteo's historical-forecast product is stitched from short-lead model runs, so
  it is not a forecast at our cutoff. Its previous-runs archive starts in 2024, which is too short.
  Forecasts are archived live from now on.
- **Market lines:** no historical timestamps exist. From now on, lines are stored at snapshot time.
- **Backup-QB quality:** already used when the starter is projected out.

The real-data perturbation test passes with the new features (753 columns, 0 changes before the
perturbed game).

## 3. Baseline research (`python -m lab.study3`, nested tuning)
Each configuration was re-run with **nested** tuning (each season tuned only on earlier seasons).
2019–2022 is development, 2023–2024 is the previously inspected validation period, and 2025 is
diagnostic only. **There is no fresh historical holdout.**

The pre-declared gate requires beating the champion method on the 2019–2022 mean season log loss
AND on 2023–2024, with a Holm-adjusted paired-bootstrap p < 0.05 across all candidates.

| Result | Value |
|---|---|
| Candidates (4 feature configurations × 9 methods + 41 simpler model subsets) | 78 |
| Passed the gate | **0** |
| Best pooled improvement | −0.0012 log loss (XGB + RF + single-layer average), CI −0.0030 to +0.0006, 2025 +0.0012 |
| Nested champion (weighted average) | dev 0.6321, validation 0.6314, 2025 0.6351 (vs 0.6322 / 0.6315 / 0.6354 non-nested: tuning contamination was negligible) |
| Logistic regression alone | +0.0035 worse (CI excludes 0); stacking +0.0050 worse |
| Effective number of independent models | **1.19 of 6** (mean logit correlation 0.89, mean error correlation 0.988) |
| Phase 3 features | L1 selection share 0–17%: they add almost nothing beyond existing features |

**Champion unchanged:** v20261016_212540, validation-weighted average.

The six models are close to one model with different noise. A simpler subset is not reliably better
either, so nothing is changed. Any future gate-passing candidate is registered as a **shadow
challenger** (`lab.study3.register_shadow_challenger`). It is archived in every snapshot, and
promotion requires ≥ 128 scored prospective final snapshots with a paired improvement whose CI
lies below zero. Promotion is never automatic.

## 4. Phase 2 status
The discovery engine is unchanged. Its experimental adjustments are archived in each snapshot, so
future prospective validation becomes possible. Thresholds were not relaxed, and no discovery is promoted.

## Limitations
- The task runs only while you are logged in to Windows. Cutoff windows that pass entirely while the
  PC is off are permanently missed (and reported).
- Prospective evidence starts at zero and needs a full season or more to say much
  (about 270 games gives ±0.03 accuracy CIs).
- Snapshot market lines carry nfldata's line at refresh time, not an executable book price.
