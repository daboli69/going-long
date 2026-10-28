# NBA home-win XGBoost study: protocol frozen 2026-10-28, before any model fitting

Question: can XGBoost extract persistent predictive information from pregame NBA history that a properly built
Elo or regularized logistic model cannot? Home-win probability only. No spreads, totals, props, odds or betting.
No sportsbook data is used. Owner of the code: this study (`nba_xgb/`); it does not import or alter `nba_lab/`.

## Disclosures made before fitting

1. The existing project (`nba_lab`, docs/PREREGISTRATION.md) used 2024-25 as discovery and 2026 as a spent
   confirmation season for different models. This study uses its own protocol and its own pipeline. I did not read the
   earlier results documents. The seasons 2025 and 2026 are still not virgin for the research group as a whole.
2. After building the engine I ran one smoke test with un-tuned default engine settings: an in-sample logistic fit
   of each single strength feature plus home court over 2016-2026 (log loss about 0.619 Elo, 0.626 adjusted net,
   0.620 recent net; constant 0.685). That run touched the later seasons. No design choice below depends on it.
3. Historical files are today's revised copies of ESPN data, all retrieved on 2026-10-23 (2027 files on three dates).
   Real publication times of historical boxes are unknown, so a conservative proxy is used (below). Any claim is
   limited to "would have been computable from this archive under the stated availability rule".

## Data and point-in-time rule

- Games: regular-season ESPN games, seasons 2015-2027 (ending year), both teams in the official 30-team directory,
  postponed/cancelled and NBA Cup championship games removed. Result verified when the schedule score equals the box
  points for both teams and points = 2*FGM + 3PM + FTM for both teams. Unverified games are quarantined: kept in the
  schedule (for rest days) but excluded from ratings and from labelled rows.
- Game date is the America/New_York calendar date of tipoff. The result of a game dated d may be used only for games
  dated >= d + lag. Primary lag = 1 day (prediction cutoff 06:00 ET on game day). Sensitivity: lag = 2.
  Events: game date (event time); archive retrieval time (our obtain time; publication time unknown); cutoff (06:00 ET).
- 2020 games on or after 2020-07-30 (Orlando restart) are treated as neutral-site (home_court = 0).
- Possessions = FGA + 0.44 FTA - OREB + TOV, averaged over both teams for the game. TOV = player turnovers (`turnovers`);
  the ESPN `total_turnovers` field is missing for whole seasons, so team turnovers are excluded everywhere for consistency.
- 2015 is warm-up only. Labelled games: 2016-2026 (+ 2027 descriptive replay).

## Strength engines (all parameters fitted without any season after 2021)

- A. Elo: K, home advantage, season carry-over, margin-of-victory multiplier on/off. Fitted by minimizing log loss on 2016-2021.
- B. Opponent-adjusted efficiency: ridge on points per 100 possessions with team offence, opponent defence, home term,
  season intercepts; current season weight 1, previous season weight kappa, older dropped; ridge penalty lambda
  (= noise variance / team-variance, the empirical-Bayes shrinkage). lambda, kappa fitted on 2016-2021.
- C. Recency: per-game exponential decay with half-life h (games), prior pseudo-games n0, carry-over rho (prior = rho x
  previous-season final estimate). h, n0, rho fitted on 2016-2021.
- Engine parameters are fixed after that fit and reused for all later seasons.

## Features

CORE (frozen): elo_diff, adj_off_diff, adj_def_diff, recent_net_diff, rest_diff, b2b_home, b2b_away, home_court.
Extension groups for ablation only: adj_net_diff (redundancy), recent_off/def split, four-factor nets, gp_min.
Player availability is not used: no verified pregame availability exists in the archive before the 2026-27 season, and
final lineups, actual minutes and retrospective player impact are never used.

## Splits (chronological only; expanding window; annual refit before each season)

- Fold F trains on seasons 2016..F-1 and predicts season F.
- Development folds F = 2020, 2021, 2022, 2023: all hyperparameters, feature-group pruning and the XGBoost-vs-shallow rule.
- Calibration-method selection: fold 2024 (calibrators fitted on out-of-sample predictions of earlier folds, scored on 2024).
- FINAL TEST: folds 2025 and 2026, run once after freezing `docs/NBA_XGB_FROZEN.json`. 2027 games through the data cutoff
  are a descriptive replay, not evidence.
- Test-season outcomes never enter selection of features, hyperparameters, calibrators or engine parameters.

## Models

- Baseline 1 calibrated Elo: logistic(alpha + beta * elo_diff + gamma * home_court), refit per fold on training seasons.
- Baseline 2 L2 logistic on CORE (standardized), C from {0.001,0.003,0.01,0.03,0.1,0.3,1,10} by pooled dev log loss.
- XGBClassifier objective binary:logistic, eval_metric logloss, tree_method hist, seed 20261028. 30 random configurations
  (seeded) from depth {1,2,3,4,6}, learning_rate {0.01,0.03,0.05}, min_child_weight {5,20,50}, subsample {0.6,0.8,1},
  colsample_bytree {0.6,0.8,1}, reg_lambda {1,10,50}, reg_alpha {0,0.5,2}; rounds chosen from 25..800 by staged pooled
  dev log loss (the early-stopping analogue; no test or calibration data). Shallow rule: a configuration with depth > 3 is
  chosen only if it beats the best depth <= 3 configuration by >= 0.0005 log loss in at least 3 of 4 dev folds.
- Pruning: a CORE group whose removal lowers pooled dev log loss by >= 0.0002 is dropped from the final feature set.

## Evaluation

Primary: log loss on identical games. Also Brier, accuracy, ROC AUC, calibration intercept (offset model) and slope,
reliability tables. Paired per-game differences with date-clustered bootstrap (resample game dates with replacement,
within season blocks, 4000 draws, seed 20261028) and a 7-day moving-block bootstrap as robustness. Two primary
comparisons (XGB vs Elo, XGB vs logistic) so 97.5% intervals are reported alongside 95%.
"Credible improvement" = paired interval for loss difference excludes 0 in the pooled test seasons AND the point
estimate has the same sign in each test season. No universal accuracy threshold is used.

Evidence requirements are those in the task statement; each is reported pass/fail with its evidence in
`docs/NBA_XGB_RESULTS.md`. A null result for XGBoost is an acceptable outcome.

Sensitivity analyses (reported, never used for selection): half-life, Elo variants, n0 (season-start uncertainty),
small-sample strata (games played < 10 / 10-29 / >= 30), training-window length (3, 5, all seasons), lag = 2,
excluding 2020-21 from training.
