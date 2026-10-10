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
| totals / spreads / h2h | game model | live n 452 / 346 / 191 | .277 / .260 / .237 | see repair pass | -.81 / .24 / .83 | market | see repair pass | FIXED in the repair pass below |

## Implemented
- `config/calibration_policy.json` (rollback: `active:false`), attached as data to the stat model by `scripts/build_pipeline.py`, applied in `propProbabilities` only within +/-50% of the model mean (receptions WR/TE/RB, pass yards QB). Today-ranking-v3 registered (hash refreshed before any v3 observation).
- Tracker evidence stores `model_evidence.calibration`, cohort suffix `+cal`; cards state "calibrated" vs "raw, overconfident in audits"; Today carries a probability caution.
- Production verified from the regenerated `data/history.json` (21:12Z): calibration on receptions WR 270 / RB 165 / TE 144 and pass_yds QB 48, nothing else.

## Rejected / open
- Rejected: pooled isotonic, constant shrink toward a line-position base rate off the line grid, calibrating TD markets now.
- Open: receptions Under high-confidence tail is slightly over-corrected (raw 83.4 / cal 80.8 / actual 87.4); the live receptions slope (.20) is far worse than the backtest (.82) because live lines are not model-median lines, so EV against book prices stays inflated: the 25% EV review flag remains. Passing yards needs a distribution fix; totals need investigation; game-line probabilities uncalibrated.

## Gate
READY WITH LIMITATIONS: material miscalibration remains for rec/rush yards, TD markets, totals and spreads; those probabilities are labelled raw and unreliable above about 80%.

## Repair pass (later 2026-10-09): fix the model, not just the probability
MARKET | ROOT CAUSE | CHANGE | BEFORE / AFTER | BENCHMARK | HOLDOUT | PRODUCTION STATUS

| MARKET | ROOT CAUSE | CHANGE | BEFORE / AFTER | BENCHMARK | HOLDOUT | STATUS |
| --- | --- | --- | --- | --- | --- | --- |
| totals, spreads, moneylines (NFL) | Trailing-points model has no information beyond the posted line (weight on model-minus-line -0.15 totals, -0.07 margin; RMSE 13.87 vs 13.21 and 13.62 vs 12.78 over 2,575 games, 2016-25). Live slope -0.79 [-1.49,-0.13] is real, not a settlement defect (100% of 5,805 re-grades match). | **Fixed underlying model**: posted line is the mean, SD from line residuals (`shared/game-market.js`) | Live game-line probabilities were noise-driven; now equal to the book price before vig | de-vigged moneyline Brier .2122 | 2023-25 (876 games): alt-line calibration within 2 points; ML Brier .2121; independent reviewer reproduced | **Production** (game-line EV is about minus the vig, so these lines stop surfacing as picks) |
| totals, spreads (NCAA) | Same structure; no historical lines in repo | Same anchor with SD 15 / 16 from the live 2026 sample | n/a | | not testable | **Production, weak evidence** |
| rec_tds, atd, rush_tds | Champion TD mean about 20% too high (regression to the mean under-applied); not only DNP zeros (participant-only ratio .83, .83, .88) | **Fixed underlying mean**: global factors .7853 / .8110 / .8681 (fit 2021-24) applied at build, raw kept as `lambda_raw` | Mean P(TD) .249/.333/.301 vs observed .203/.288/.268 (2023) to within 1 point | Poisson raw | Walk-forward Brier gain at P(>=1): rec_tds +.0031/+.0013/+.0036, atd +.0026/+.0007/+.0030, rush_tds +.0018/-.0002/+.0024 (2023/24/25; 2024 CIs span 0) | **Production** (rush_tds lower confidence) |
| receptions, pass_yds | see table above | recalibrated probability | | | | Production (recalibrated, not a model fix) |
| rec_yds, rush_yds | narrow yardage spread + early-season mean (k=0 ratio .65-.75 vs .97 late; stable 5 seasons) | none promoted | | | +.0006 / +.0041 | **Shadow** |
| pass_tds | none found (factor .96-.98 hurts) | none | | | | no correction |
| early-season mean (k=0) | Week-1 rows: 18% have zero targets vs 10% later, i.e. availability/role uncertainty; players who do play show ratio .96 for receptions | not corrected as a mean (books void non-participants; an unconditional mean cut would under-price players who play) | | | | **Unresolved**, documented |

Other changes: extreme-probability (>=85%, or <=15% at 4.0+ decimal) review flag next to the 25% EV flag; period/team-total game quotes withheld without a posted full-game line; first-TD scoring uses the posted line; td_shadow and first-TD recipes stay on the raw TD mean they were tuned on. A proposed settlement rule that voided all-zero player lines was **rejected** after independent review: results rows already require a snap or stat appearance and there is no snap/inactive flag to tell a zero-touch active player from an inactive one.

Remaining uncertainty: live prop edge versus prices is unproven (live model coefficient 0.21 [-0.15, 0.36] against 0.56 on the de-vigged price, 17 games); live receptions slope (.20) versus backtest (.82) is explained by line selection, not fixed; NCAA game SDs; TD factors are global, not by position (position-specific gave no reliable gain); the pass-yards distribution still needs a real fix.

## Yardage research and pass-yards promotion (2026-10-10)
Independent researcher (`research/yardage-variance/`, walk-forward fit on seasons before each test year, 2025 not used for selection):
| MARKET | ROOT CAUSE | CHANGE | BEFORE/AFTER (Brier, ladder lines, 2023/24/25) | HOLDOUT | STATUS |
| --- | --- | --- | --- | --- | --- |
| pass_yds (QB) | Champion mean loses to a plain trailing mean every year (RMSE 77.9/75.1/76.5 vs 73.5/71.4/73.8; Champion weight 0.00 in NNLS); sigma not tied to the mean | **Fixed underlying model**: equal-weight mean of modelled games, log-space regression-to-mean compression (b -0.43), sigma falling with the mean; replaces the shrink stopgap (`lognormal_refit`, policy v3) | +.0143 / +.0133 / +.0103 vs Champion | 2025 main line +.0103 [.0011,.0189]; vs deployed shrink +.0087 [.0034,.0138]; reproduced through the production function | **Production** (about 330 starter-games a year, so the main-line bound is thin) |
| rec_yds | pooled sigma too flat in the mean, free low-mass p0 | probability-level calibration only (fitted mean is not a true mean: realised/fitted .87) | +.0025 / +.0023 (2025 main +.0023 [.0005,.0040]) | small, 2024 main interval spans 0 | **Shadow** (not wired; modest gain, complex) |
| rush_yds | same, plus main-line gain zero in 2024 | | all-line +.0096, main +.0046 (2023 .0048, 2024 .0001, 2025 .0046) | borderline | **Shadow** |
| tail shape | gamma vs lognormal vs mixture | none | within .0003 | null | rejected |
| zero mass | Champion p0 .241 vs true no-target rate .117 (it absorbs low-yardage games) | logistic on activity made it worse (-.0128) | | | rejected |
The old "sigma 1.3-1.8x too narrow" claim was partly mean error: fitted sigma is 1.38x (rec), 1.67x (rush), 1.31x (pass) the Champion's. All lines are a synthetic ladder, not real posted prices; a Brier gain is not a betting return.
