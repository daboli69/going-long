# Calibration audit and release gate (2026-10-09)

Independent reproduction: Auditor A (live tracker, `research/calibration/A`), Auditor B (point-in-time backtest 2021-25, `research/calibration/B`), QA (`research/calibration/QA`, `tests/qa_calibration_wiring.cjs`).

## The reported figures
Reproduced exactly (n 5,066, Brier .254, base rate .477, skill -.018; 94% bin won 72%). The audit itself was flawed: it pooled anytime TD (base rate .21) with props (.5), double counted (4,332 rows share game/player/market with another row; one row per contract leaves n 2,203), and mixed a winner's-curse group (`best_model`, selected on disagreement with price). Per-market, per-side skill is -.066. Against the de-vigged market (940 rows) the model's skill is -.042. All 5,805 settlements regrade correctly (127 zero-filled DNP rows are a minor defect). Only 4 weeks / 157 games: intervals are wide.

## Root causes
1. Main-line props carry almost no edge over the book price (backtest main-line skill -7% to +9%); live slopes .1-.65, totals anti-informative (-.8).
2. Overconfident tails: 2025 backtest slopes .60-.84; predictions above .85 are alternate or low lines, 88% Unders live, won 72% vs 94% stated; hit rates track the book price, not the model.
3. Mean bias early season (k=0: +17% receptions, +46% receiving TDs); TD means 15-27% high.
4. Distributions too narrow (yardage sigma 1.3-1.8x too small; receptions overdispersed, NB phi about .2).
5. Selection bias in the tracked groups.

## Table (2025 holdout, fit 2021-23, selection 2024, scored once; deploy parameters refit 2021-24)
| MARKET | MODEL VERSION | N (holdout) | ORIGINAL BRIER | NEW BRIER | CAL. SLOPE raw to new | BENCHMARK | HOLDOUT | DECISION |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| receptions | champion-v2 + cal-b-2026.10.09-v1 (Platt) | 20,063 | .1635 | .1610 | .82 to 1.06 | per-line base rate | +.0025 [.0017,.0033] | **PROMOTED** (QA: ship with changes done) |
| pass_yds | champion-v1 + shrink | 4,401 | .1670 | .1653 | .70 to 1.01 | trailing mean (model is worse than it) | +.0016 [.0009,.0024] | **PROMOTED** (stopgap; distribution fix pending) |
| rec_yds | champion-v2 | 26,892 | .2163 | .2158 | .84 to .98 | per-line base rate | +.0006 | SHADOW |
| rush_yds | champion-v1 | 8,486 | .2200 | .2160 | .60 to 1.05 | per-line base rate | +.0041 (fails main-line check) | SHADOW |
| pass_tds | champion-v2 | 1,354 | .1994 | n/a | .94 | per-line base rate | none needed | no correction |
| rush_tds | champion-v2 | 776 | .2034 | .1992 | .50 to .61 | | +.0042 (2024 CI spans 0) | SHADOW |
| rec_tds | champion-v2 | 2,152 | .1640 | .1606 | .76 to 1.37 | | +.0034 | SHADOW |
| atd | champion-v2 | 2,077 | .2067 | .2030 | .66 to 1.13 | | +.0037 | SHADOW |
| totals / spreads / h2h | game model | live n 452 / 346 / 191 | .277 / .260 / .237 | none | -.81 / .24 / .83 | market | not tested | UNFIXED, flagged |

## Implemented
- `config/calibration_policy.json` (rollback: `active:false`), attached as data to the stat model by `scripts/build_pipeline.py`, applied in `propProbabilities` only within +/-50% of the model mean (receptions WR/TE/RB, pass yards QB). Today-ranking-v3 registered (hash refreshed before any v3 observation).
- Tracker evidence stores `model_evidence.calibration`, cohort suffix `+cal`; cards state "calibrated" vs "raw, overconfident in audits"; Today carries a probability caution.
- Production verified from the regenerated `data/history.json` (21:12Z): calibration on receptions WR 270 / RB 165 / TE 144 and pass_yds QB 48, nothing else.

## Rejected / open
- Rejected: pooled isotonic, constant shrink toward a line-position base rate off the line grid, calibrating TD markets now.
- Open: receptions Under high-confidence tail is slightly over-corrected (raw 83.4 / cal 80.8 / actual 87.4); the live receptions slope (.20) is far worse than the backtest (.82) because live lines are not model-median lines, so EV against book prices stays inflated: the 25% EV review flag remains. Passing yards needs a distribution fix; totals need investigation; game-line probabilities uncalibrated.

## Gate
READY WITH LIMITATIONS: material miscalibration remains for rec/rush yards, TD markets, totals and spreads; those probabilities are labelled raw and unreliable above about 80%.
