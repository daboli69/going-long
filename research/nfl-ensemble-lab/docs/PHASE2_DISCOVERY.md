# Phase 2: Upset Discovery Engine (2026-10-16)

Experiment **d20261016_230432**, inputs frozen from Phase 1 model **v20261016_212540**
(champion: validation-weighted average). Artifacts: `artifacts/discovery/d20261016_230432/`
(read-only). Reproduce: `run_research.bat`, or the Research Runs page.

## Readiness gate (real data, `python -m lab.readiness`)
| Check | Result |
|---|---|
| Injury `date_modified` behaves like report times | Yes. 83–106 distinct days per season; 73–84% on Fridays; correlation with kickoff 0.9999; 99.77–100% before kickoff; none after season end. A file-processing stamp would sit on one day after the season. |
| Real-data perturbation (2022_10_ATL_CAR: score, team stats ×3+1, QB EPA, player snaps zeroed) | 0 changed cells across 721 columns for all 2,026 games at or before kickoff; 430 later games changed. |
| Missing injuries stay missing | 0 unavailable rows carry a zero load or a non-missing difference. |
| Out-of-sample predictions | 2,307 rows, 0 trained on their own or a later season. |
| Market odds | Closing consensus without timestamps: separate benchmark only, never an input, no executable-edge claims. |
| Scheduled refresh | Task present, last result 0. |

## What the engine does
For each baseline (ensemble out-of-sample probability; closing no-vig market as a benchmark), every
game is oriented to the baseline underdog. A pattern's evidence is the sum over many games of
(underdog won − baseline probability), scored with likelihood statistics and offset-logistic effects.
A single upset counts for nothing.

**Inputs:** 418 underdog-oriented pregame features. These cover efficiency and opponent strength
(blended, last-3, previous-season), ratings, pace and pass-rate tendencies, rest, home/neutral/dome,
projected-QB efficiency and uncertainty flags, and position-group injury loads plus injury ×
opponent-strength interactions (2016–2024 verified reports; missing otherwise). The baseline probability
itself is included for miscalibration searches. No travel distances exist in the free data.

**Methods (all operational):** univariate threshold subgroups; paired conditional subgroups;
miscalibration buckets crossed with context; RuleFit-style rules from bootstrapped residual trees;
symbolic expressions (sum, difference, product, ratio, square, abs, signed log); a gradient-boosted
residual model with the baseline as a fixed offset; SHAP pairwise interactions turned into paired
subgroups; k-means regimes; isolation-forest anomalies.

**Chronology (two research origins):**
| Origin | Discovery | Validation | Evaluation (untouched) |
|---|---|---|---|
| primary | 2018–2021 | 2022–2023 | 2024 |
| replication | 2018–2020 | 2021–2022 | 2023 |

2025 is diagnostic only (already inspected). 2026 counts only from predictions archived before kickoff.

**Controls:** at least 40 discovery and 25 validation games; nominal BH q reported in discovery
(nominal because the search is adaptive); the top 30 de-duplicated candidates carried forward;
Holm correction in validation; same sign required; at least half of validation seasons with the same sign;
empirical-Bayes shrinkage of effects; per-season effect strings. Adjusters: a ridge offset model on
validated patterns only, and a GBM residual scaled by a factor λ chosen on validation (0 = off).
Verdict rule (pre-declared): an adjustment is "demonstrated" only if it lowers log loss on BOTH
evaluation seasons and the primary origin's 95% CI is below zero.

## Results
| Baseline / origin | Candidates tested | Nominal discovery BH q<0.10 | Carried | **Validated** |
|---|---|---|---|---|
| ensemble / primary | 7,486 | 154 | 30 | **0** |
| ensemble / replication | 7,182 | 128 | 30 | **0** |
| market / primary | 8,224 | 898 | 30 | **0** |
| market / replication | 7,172 | 24 | 30 | **0** |

In total 30,064 candidate relationships were investigated, and **none survived independent validation**.
Many reversed sign; for example, a market-baseline rule with discovery z = +4.6 had a validation effect
of −1.31 log-odds. Injury-based candidates were searched and carried (e.g. underdog offensive
injury load plus WR injury load), and they also failed validation.

**Experimental adjustments:** the validated-pattern layer is empty, so it makes no adjustment. The GBM
residual layer's validation log loss rose with every step of λ (ensemble/primary: 0.6411 at λ=0 →
0.6819 at λ=1), so λ = 0 everywhere. **No adjustment improved log loss, Brier score or calibration in any
season**, and the original ensemble remains the primary forecast.

Baseline log loss on the evaluation seasons for reference: ensemble 0.6091 (2024), 0.6539 (2023);
closing market 0.5888 (2024), 0.6265 (2023).

**Reproducibility:** a second full run via `run_research.bat` (experiment d20261016_230826) had identical input hashes and identical counts.

**Prospective:** 0 completed games so far have a prediction archived before kickoff. Week 6 snapshots
exist and will count once those games finish.

## Software validation (synthetic; not NFL findings)
- Planted interaction (log-odds +1.3 when a > 0.4 and b ≤ −0.3): validated as "a > 0.66 AND b ≤ −0.03"
  with validation effect +0.98. The adjusted forecast lowered held-out log loss.
- Null data: 0 validated in both origins, and adjustments not demonstrated.

## Limitations
- No timestamped executable historical odds exist in the free data, so market analysis is a closing-line
  benchmark only and nothing can be called a betting edge.
- Injury history: 2016–2024 verified; 2025 missing; 2026 grows only from the lab's own pre-kickoff archives.
- Validation windows are 2 seasons (about 570 games), so real effects smaller than roughly 0.4–0.7 log-odds
  (depending on how many games a pattern covers) could be missed. A null result says "nothing large and stable", not "nothing exists".
- Evaluation seasons 2023–2024 were used in Phase 1 base-model selection (not in Phase 2).
- No coaching identity, travel distance, weather forecasts or historical starting-QB announcements are available.
