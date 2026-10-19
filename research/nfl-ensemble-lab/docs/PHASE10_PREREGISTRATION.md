# Phase 10 pre-registration — 2026-10-19

Committed before implementation, fitting or examination of new experiment results. All configurations are shadow only. The game champion and props simulator v1 stay unchanged. No spending or odds services; quotes come only from GOING/data/nfl_betting.json and its git history.

## Data, time and common rules

Props member fitting uses regular seasons 2016–2021 only. Development is chronological 2022 weeks; weights, stacking and probability calibration for week w use out-of-fold predictions from strictly earlier 2022 weeks only (minimum 100 rows and two classes for binary fitting). No 2023–25 player outcomes may be loaded for fitting, tuning, selection, or scoring. 2026 is forecast-only and never influences selection. Features use strictly earlier weeks and verified pregame injury rows; retrospective rosters/starters are excluded as features. Weather is excluded from fitted features without pregame archives. Missing feature sources are reported, never substituted with future observations. Games use lab.longrun DEV_FOLDS only; no validation/test look or automatic challenger registration.

All comparisons use identical eligible rows. Report n, paired mean loss differences and 2,000 game-cluster bootstrap resamples (seed 20261019) with percentile 95% CIs. No ROI/CLV without matched real prices and settlements. Fewer than 100 games means inconclusive. Multiple configurations: Holm correction for primary improvement claims. No changed thresholds after results. Failures are recorded and skipped; a test failing twice is not retried again.

## Frozen experiments B1–B6

| ID | Hypothesis / configurations | Data and split | Primary metric and acceptance |
|---|---|---|---|
| B1 | Recalibrating combined game probabilities improves champion; longrun family search uses existing grids | Existing DEV_FOLDS only; calibration fitted on earlier folds | Log loss decrease >=0.002, paired CI upper bound <0; Brier non-increasing. Do not invoke a longrun path that scores later validation/test folds. |
| B2 | Independent football-only ridge margin/total forecasts are useful against mean baseline; compare market-anchored simulator and closing benchmark | Games trained on seasons before each DEV fold; cutoff <=2021 for prospective shadow fit | MAE and CRPS lower than league-mean baseline with CI upper <0; 80% coverage in [0.75,0.85]. Market comparison descriptive, unequal information for T3. Report RMSE, bias, cover/over Brier and push rate. |
| B3 | Multi-family props ensemble improves simulator v1 and baseline B | Fit <=2021; walk-forward 2022 only | Per-target paired primary loss CI upper <0 versus both baselines: yards MAE + reported pinball 10/50/90; counts Poisson deviance; binary Brier with non-increasing log loss. Compare equal, earlier-week weighted, earlier-week stacked. No pooled metric across incompatible units. |
| B4 | Non-red-zone scoring features improve TD probabilities over red-zone-only | Same 2022 chronological rows, fixed logistic model for ablation | Anytime-TD Brier decrease >=0.001 and paired CI upper <0; report log loss/reliability. First-TD multiclass log loss and Brier descriptive, offensive rush/receive scorers plus no such TD only. |
| B5 | Simulator precision stabilizes with more samples | Fixed first 8 eligible 2022 games, seeds 20261019 and +1; 250/1000/2000 simulations | Recommend smallest count with median absolute 10/50/90 quantile change <=2 yards (yards), <=0.5 counts, relative to 2000; report runtime, coverage and PIT. Incomplete runs yield no recommendation. |
| B6 | Retain at most two passing shadow configurations and archive next unplayed 2026 week | Only passing B1–B4 rules; prospective archive before kickoff around 18:00 | No promotion. No passing/fully tested configuration => no validated challenger. Forecast artifacts explicitly experimental if validation incomplete. |

## Fixed model specifications and outputs

Yards: lab.models ridge, random forest, XGBoost and MLP using the first existing grid point (no grid search); quantile gradient boosting at 0.10/0.50/0.90, 100 trees, depth 2, learning rate .05. Counts: Poisson GLM alpha=1, XGBoost count:poisson (depth 2, 150 trees, learning rate .03), random forest and MLP with predictions clipped >=0. Binary anytime TD: lab.models logistic, XGBoost, random forest, MLP first grid points. Anytime TD means >=1 rushing or receiving TD, excludes passing/defensive/special-teams TDs. Structural members: v1 and independently anchored simulator, fitted <=2021. Only actually available members may be included, each listed explicitly; incomplete structural inputs are reported.

Equal averaging imports shared ensemble code. Validation weights use inverse earlier-week target loss (binary uses shared log-loss skill weighting); stacking uses shared binary logit stacker or nonnegative ridge for continuous/count targets. Binary Platt calibration only on earlier-week ensemble predictions. Warm-up falls back to equal average, uncalibrated, explicitly labelled. Vote agreement is descriptive only. Intervals from the quantile head are labelled as that head, not claimed to be calibrated ensemble intervals. Market-informed ablation adds archived pregame implied team points only if timestamp-eligible history exists; otherwise blocked. Default inputs exclude every market column.

Independent game anchor: ridge home margin and total on explicitly selected football-only features; residual distribution learned <=2021, transformed to >=0 team targets; no market columns or listed actual starting QB. Market anchors are side-by-side benchmarks only. First-TD ensemble reweighting multiplies structural player probabilities by ensemble anytime probability / structural anytime probability, preserving no-offensive-TD mass, then normalizes.

## Deadline and rollback

Implementation clarification (2026-10-19 17:03, before any recent-player-file read):
market-anchored v1 is a structural member only of the explicitly labelled
market-informed variant. It cannot enter independent averages, weights, stacking,
features or intervals. The independent structural member uses only football
anchors. This enforces the original market-benchmark rule; thresholds and splits
are unchanged. No authorized 2022 quote history means the historical v1 benchmark
and implied-points feature ablation are blocked rather than filled with closing
lines from another source.

Start 16:35 local; build budget shortened to preserve research and 18:30–19:00 wrap-up. Check clock each step. Prioritize A1–A3 > A5 > A4 > A6 > A7 > A8. Stop starting new work at 18:30. Generated archives are never deleted. Revert code commits to roll back; champion/simulator v1 remain unchanged. Commit/push this branch only, roughly every 45 minutes. No Windows scheduled tasks are created.
