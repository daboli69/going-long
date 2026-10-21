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


## Amendment 1 — 2026-10-19: FROZEN CONFIG and recent-data prospective fit

Reason (authorized by Travis): the league changes, so 2026 forecasts must not be trained on data older than needed. Development remains member training through 2021 and chronological 2022 evaluation only. Both structural development runs completed all 271 finished 2022 games with no errors before this freeze.

No props ensemble meets the original primary promotion/acceptance comparison because authorized 2022 market anchors and original market-scaled baseline B are unavailable. Freeze the pre-declared equal-weight ensemble as an UNPROMOTED REFERENCE for the requested prospective sheet. This is not selection of a proven winner. The weighted/stacked results and every member are retained in development artifacts; no threshold is relaxed. Full TD features remain the pre-registered default. Raw TD-ablation and first-TD diagnostics do not authorize promotion.

PRODUCTION FIT (local shadow artifacts only): refit this exact statistical configuration on seasons 2016 through the last fully completed 2026 week, including 2023–25 only AFTER this amendment is committed. Reuse lab.players.SEASON_WEIGHTS: current season 1.0, previous 0.6, older seasons at the existing oldest positive tier 0.35, retaining all older seasons. Normalize learned-member weights to unit mean. The frozen v1 play engine uses a separately stored recent structural fit with whole-game importance resampling at these weights (seed 20261019); original v1 saved fits/results remain untouched. Game-anchor coefficients/residuals stay fitted through 2021 under the games DEV-only rule.

Training cutoff today: 2026 week 5, last training game dated 2026-10-12 (last kickoff 2026-10-13T00:15Z). Every prospective archive records the actual training cutoff and frozen hash. Role inputs may use completed games in strictly earlier weeks, including partial week 6 for week-7 forecasts; they never enter same-week features or training after the fit cutoff. No 2026 outcome is scored or used to tune the configuration. Calibrators and residual-distribution recipes stay fixed from 2022. No live model registry, champion or pinned release is changed.

Optional SINGLE LOOK over 2023–25 has NOT been run. A full weekly refit plus structural comparison cannot finish before 18:15 in the remaining budget; leave it under Next, once only with this frozen configuration and saved v1 results read-only. Never invoke lab.props.evaluate eval.

The machine-readable settings below are checked against the committed file and runtime factories before any recent-player-file read.

<!-- PHASE10_FROZEN_CONFIG_START -->
{
  "frozen_at": "2026-10-19T17:34:48.299485-04:00",
  "selection": "pre-registered equal-weight reference, not a validated winner",
  "development_split": "member fit <=2021; walk-forward meta-learning 2022 only",
  "development_player_stat_rows": 8576,
  "development_games": 271,
  "primary_acceptance": "No props ensemble qualifies: required timestamp-eligible v1 and original baseline-B comparisons are unavailable. No promotion.",
  "development_results_sha256": "7cbef696e0b73efbe897203bea6d00908be9f1e08bd550c723b555a97a15a01c",
  "runtime_spec": {
    "features": [
      "hist_targets",
      "hist_carries",
      "hist_dropbacks",
      "hist_pass_yds",
      "hist_pass_tds",
      "hist_rec",
      "hist_rec_yds",
      "hist_rush_yds",
      "hist_off_td",
      "hist_air_yards",
      "hist_yac",
      "hist_deep_targets",
      "hist_explosives",
      "hist_rz_targets",
      "hist_gl_targets",
      "hist_rz_carries",
      "hist_gl_carries",
      "hist_outside_rz_td",
      "hist_long_td",
      "hist_target_share",
      "hist_carry_share",
      "hist_air_share",
      "hist_rz_target_share",
      "hist_gl_target_share",
      "hist_rz_carry_share",
      "hist_gl_carry_share",
      "hist_team_pass_td_share",
      "hist_snap_share",
      "hist_games",
      "adot",
      "yac_rate",
      "deep_target_rate",
      "outside_rz_td_rate",
      "explosive_rate",
      "long_td_rate",
      "is_qb",
      "is_rb",
      "is_wr",
      "is_te",
      "home",
      "rest",
      "dome",
      "ind_team_margin",
      "ind_total",
      "qb_quality",
      "qb_out",
      "backup_qb",
      "opp_position_yards",
      "opp_position_td",
      "opp_adjustment"
    ],
    "models": {
      "pass_yds": {
        "logreg": {
          "class": "Ridge",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__alpha": 100.0,
            "model__copy_X": true,
            "model__fit_intercept": true,
            "model__max_iter": null,
            "model__positive": false,
            "model__random_state": null,
            "model__solver": "auto",
            "model__tol": 0.0001
          }
        },
        "random_forest": {
          "class": "RandomForestRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__bootstrap": true,
            "model__ccp_alpha": 0.0,
            "model__criterion": "squared_error",
            "model__max_depth": 5,
            "model__max_features": 0.3,
            "model__max_leaf_nodes": null,
            "model__max_samples": null,
            "model__min_impurity_decrease": 0.0,
            "model__min_samples_leaf": 10,
            "model__min_samples_split": 2,
            "model__min_weight_fraction_leaf": 0.0,
            "model__monotonic_cst": null,
            "model__n_estimators": 300,
            "model__n_jobs": 7,
            "model__oob_score": false,
            "model__random_state": 20260916,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "xgboost": {
          "class": "XGBRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__objective": "reg:squarederror",
            "model__base_score": null,
            "model__booster": null,
            "model__callbacks": null,
            "model__colsample_bylevel": null,
            "model__colsample_bynode": null,
            "model__colsample_bytree": 0.6,
            "model__device": null,
            "model__early_stopping_rounds": null,
            "model__enable_categorical": false,
            "model__eval_metric": null,
            "model__feature_types": null,
            "model__gamma": null,
            "model__grow_policy": null,
            "model__importance_type": null,
            "model__interaction_constraints": null,
            "model__learning_rate": 0.03,
            "model__max_bin": null,
            "model__max_cat_threshold": null,
            "model__max_cat_to_onehot": null,
            "model__max_delta_step": null,
            "model__max_depth": 2,
            "model__max_leaves": null,
            "model__min_child_weight": 5,
            "model__missing": "nan",
            "model__monotone_constraints": null,
            "model__multi_strategy": null,
            "model__n_estimators": 150,
            "model__n_jobs": 7,
            "model__num_parallel_tree": null,
            "model__random_state": 20260916,
            "model__reg_alpha": null,
            "model__reg_lambda": 5.0,
            "model__sampling_method": null,
            "model__scale_pos_weight": null,
            "model__subsample": 0.8,
            "model__tree_method": "hist",
            "model__validate_parameters": null,
            "model__verbosity": null
          }
        },
        "mlp": {
          "class": "TorchRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__batch_size": 128,
            "model__dropout": 0.3,
            "model__hidden": [
              32,
              16
            ],
            "model__lr": 0.001,
            "model__max_epochs": 300,
            "model__patience": 20,
            "model__seed": 20260916,
            "model__val_frac": 0.15,
            "model__weight_decay": 0.001
          }
        }
      },
      "pass_tds": {
        "logreg": {
          "class": "PoissonRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__alpha": 1.0,
            "model__fit_intercept": true,
            "model__max_iter": 1000,
            "model__solver": "lbfgs",
            "model__tol": 0.0001,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "random_forest": {
          "class": "RandomForestRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__bootstrap": true,
            "model__ccp_alpha": 0.0,
            "model__criterion": "squared_error",
            "model__max_depth": 5,
            "model__max_features": 0.3,
            "model__max_leaf_nodes": null,
            "model__max_samples": null,
            "model__min_impurity_decrease": 0.0,
            "model__min_samples_leaf": 10,
            "model__min_samples_split": 2,
            "model__min_weight_fraction_leaf": 0.0,
            "model__monotonic_cst": null,
            "model__n_estimators": 300,
            "model__n_jobs": 7,
            "model__oob_score": false,
            "model__random_state": 20260916,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "xgboost": {
          "class": "XGBRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__objective": "count:poisson",
            "model__base_score": null,
            "model__booster": null,
            "model__callbacks": null,
            "model__colsample_bylevel": null,
            "model__colsample_bynode": null,
            "model__colsample_bytree": 0.6,
            "model__device": null,
            "model__early_stopping_rounds": null,
            "model__enable_categorical": false,
            "model__eval_metric": null,
            "model__feature_types": null,
            "model__gamma": null,
            "model__grow_policy": null,
            "model__importance_type": null,
            "model__interaction_constraints": null,
            "model__learning_rate": 0.03,
            "model__max_bin": null,
            "model__max_cat_threshold": null,
            "model__max_cat_to_onehot": null,
            "model__max_delta_step": null,
            "model__max_depth": 2,
            "model__max_leaves": null,
            "model__min_child_weight": 5,
            "model__missing": "nan",
            "model__monotone_constraints": null,
            "model__multi_strategy": null,
            "model__n_estimators": 150,
            "model__n_jobs": 7,
            "model__num_parallel_tree": null,
            "model__random_state": 20260916,
            "model__reg_alpha": null,
            "model__reg_lambda": 5.0,
            "model__sampling_method": null,
            "model__scale_pos_weight": null,
            "model__subsample": 0.8,
            "model__tree_method": "hist",
            "model__validate_parameters": null,
            "model__verbosity": null
          }
        },
        "mlp": {
          "class": "TorchRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__batch_size": 128,
            "model__dropout": 0.3,
            "model__hidden": [
              32,
              16
            ],
            "model__lr": 0.001,
            "model__max_epochs": 300,
            "model__patience": 20,
            "model__seed": 20260916,
            "model__val_frac": 0.15,
            "model__weight_decay": 0.001
          }
        }
      },
      "anytime_td": {
        "logreg": {
          "class": "LogisticRegression",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__C": 0.001,
            "model__class_weight": null,
            "model__dual": false,
            "model__fit_intercept": true,
            "model__intercept_scaling": 1,
            "model__l1_ratio": null,
            "model__max_iter": 5000,
            "model__multi_class": "deprecated",
            "model__n_jobs": 7,
            "model__penalty": "l2",
            "model__random_state": null,
            "model__solver": "lbfgs",
            "model__tol": 0.0001,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "random_forest": {
          "class": "RandomForestClassifier",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__bootstrap": true,
            "model__ccp_alpha": 0.0,
            "model__class_weight": null,
            "model__criterion": "gini",
            "model__max_depth": 5,
            "model__max_features": 0.3,
            "model__max_leaf_nodes": null,
            "model__max_samples": null,
            "model__min_impurity_decrease": 0.0,
            "model__min_samples_leaf": 10,
            "model__min_samples_split": 2,
            "model__min_weight_fraction_leaf": 0.0,
            "model__monotonic_cst": null,
            "model__n_estimators": 300,
            "model__n_jobs": 7,
            "model__oob_score": false,
            "model__random_state": 20260916,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "xgboost": {
          "class": "XGBClassifier",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__objective": "binary:logistic",
            "model__base_score": null,
            "model__booster": null,
            "model__callbacks": null,
            "model__colsample_bylevel": null,
            "model__colsample_bynode": null,
            "model__colsample_bytree": 0.6,
            "model__device": null,
            "model__early_stopping_rounds": null,
            "model__enable_categorical": false,
            "model__eval_metric": "logloss",
            "model__feature_types": null,
            "model__gamma": null,
            "model__grow_policy": null,
            "model__importance_type": null,
            "model__interaction_constraints": null,
            "model__learning_rate": 0.03,
            "model__max_bin": null,
            "model__max_cat_threshold": null,
            "model__max_cat_to_onehot": null,
            "model__max_delta_step": null,
            "model__max_depth": 2,
            "model__max_leaves": null,
            "model__min_child_weight": 5,
            "model__missing": "nan",
            "model__monotone_constraints": null,
            "model__multi_strategy": null,
            "model__n_estimators": 150,
            "model__n_jobs": 7,
            "model__num_parallel_tree": null,
            "model__random_state": 20260916,
            "model__reg_alpha": null,
            "model__reg_lambda": 5.0,
            "model__sampling_method": null,
            "model__scale_pos_weight": null,
            "model__subsample": 0.8,
            "model__tree_method": "hist",
            "model__validate_parameters": null,
            "model__verbosity": null
          }
        },
        "mlp": {
          "class": "TorchClassifier",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__batch_size": 128,
            "model__dropout": 0.3,
            "model__hidden": [
              32,
              16
            ],
            "model__lr": 0.001,
            "model__max_epochs": 300,
            "model__patience": 20,
            "model__seed": 20260916,
            "model__val_frac": 0.15,
            "model__weight_decay": 0.001
          }
        }
      },
      "rec": {
        "logreg": {
          "class": "PoissonRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__alpha": 1.0,
            "model__fit_intercept": true,
            "model__max_iter": 1000,
            "model__solver": "lbfgs",
            "model__tol": 0.0001,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "random_forest": {
          "class": "RandomForestRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__bootstrap": true,
            "model__ccp_alpha": 0.0,
            "model__criterion": "squared_error",
            "model__max_depth": 5,
            "model__max_features": 0.3,
            "model__max_leaf_nodes": null,
            "model__max_samples": null,
            "model__min_impurity_decrease": 0.0,
            "model__min_samples_leaf": 10,
            "model__min_samples_split": 2,
            "model__min_weight_fraction_leaf": 0.0,
            "model__monotonic_cst": null,
            "model__n_estimators": 300,
            "model__n_jobs": 7,
            "model__oob_score": false,
            "model__random_state": 20260916,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "xgboost": {
          "class": "XGBRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__objective": "count:poisson",
            "model__base_score": null,
            "model__booster": null,
            "model__callbacks": null,
            "model__colsample_bylevel": null,
            "model__colsample_bynode": null,
            "model__colsample_bytree": 0.6,
            "model__device": null,
            "model__early_stopping_rounds": null,
            "model__enable_categorical": false,
            "model__eval_metric": null,
            "model__feature_types": null,
            "model__gamma": null,
            "model__grow_policy": null,
            "model__importance_type": null,
            "model__interaction_constraints": null,
            "model__learning_rate": 0.03,
            "model__max_bin": null,
            "model__max_cat_threshold": null,
            "model__max_cat_to_onehot": null,
            "model__max_delta_step": null,
            "model__max_depth": 2,
            "model__max_leaves": null,
            "model__min_child_weight": 5,
            "model__missing": "nan",
            "model__monotone_constraints": null,
            "model__multi_strategy": null,
            "model__n_estimators": 150,
            "model__n_jobs": 7,
            "model__num_parallel_tree": null,
            "model__random_state": 20260916,
            "model__reg_alpha": null,
            "model__reg_lambda": 5.0,
            "model__sampling_method": null,
            "model__scale_pos_weight": null,
            "model__subsample": 0.8,
            "model__tree_method": "hist",
            "model__validate_parameters": null,
            "model__verbosity": null
          }
        },
        "mlp": {
          "class": "TorchRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__batch_size": 128,
            "model__dropout": 0.3,
            "model__hidden": [
              32,
              16
            ],
            "model__lr": 0.001,
            "model__max_epochs": 300,
            "model__patience": 20,
            "model__seed": 20260916,
            "model__val_frac": 0.15,
            "model__weight_decay": 0.001
          }
        }
      },
      "rec_yds": {
        "logreg": {
          "class": "Ridge",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__alpha": 100.0,
            "model__copy_X": true,
            "model__fit_intercept": true,
            "model__max_iter": null,
            "model__positive": false,
            "model__random_state": null,
            "model__solver": "auto",
            "model__tol": 0.0001
          }
        },
        "random_forest": {
          "class": "RandomForestRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__bootstrap": true,
            "model__ccp_alpha": 0.0,
            "model__criterion": "squared_error",
            "model__max_depth": 5,
            "model__max_features": 0.3,
            "model__max_leaf_nodes": null,
            "model__max_samples": null,
            "model__min_impurity_decrease": 0.0,
            "model__min_samples_leaf": 10,
            "model__min_samples_split": 2,
            "model__min_weight_fraction_leaf": 0.0,
            "model__monotonic_cst": null,
            "model__n_estimators": 300,
            "model__n_jobs": 7,
            "model__oob_score": false,
            "model__random_state": 20260916,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "xgboost": {
          "class": "XGBRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__objective": "reg:squarederror",
            "model__base_score": null,
            "model__booster": null,
            "model__callbacks": null,
            "model__colsample_bylevel": null,
            "model__colsample_bynode": null,
            "model__colsample_bytree": 0.6,
            "model__device": null,
            "model__early_stopping_rounds": null,
            "model__enable_categorical": false,
            "model__eval_metric": null,
            "model__feature_types": null,
            "model__gamma": null,
            "model__grow_policy": null,
            "model__importance_type": null,
            "model__interaction_constraints": null,
            "model__learning_rate": 0.03,
            "model__max_bin": null,
            "model__max_cat_threshold": null,
            "model__max_cat_to_onehot": null,
            "model__max_delta_step": null,
            "model__max_depth": 2,
            "model__max_leaves": null,
            "model__min_child_weight": 5,
            "model__missing": "nan",
            "model__monotone_constraints": null,
            "model__multi_strategy": null,
            "model__n_estimators": 150,
            "model__n_jobs": 7,
            "model__num_parallel_tree": null,
            "model__random_state": 20260916,
            "model__reg_alpha": null,
            "model__reg_lambda": 5.0,
            "model__sampling_method": null,
            "model__scale_pos_weight": null,
            "model__subsample": 0.8,
            "model__tree_method": "hist",
            "model__validate_parameters": null,
            "model__verbosity": null
          }
        },
        "mlp": {
          "class": "TorchRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__batch_size": 128,
            "model__dropout": 0.3,
            "model__hidden": [
              32,
              16
            ],
            "model__lr": 0.001,
            "model__max_epochs": 300,
            "model__patience": 20,
            "model__seed": 20260916,
            "model__val_frac": 0.15,
            "model__weight_decay": 0.001
          }
        }
      },
      "rush_yds": {
        "logreg": {
          "class": "Ridge",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__alpha": 100.0,
            "model__copy_X": true,
            "model__fit_intercept": true,
            "model__max_iter": null,
            "model__positive": false,
            "model__random_state": null,
            "model__solver": "auto",
            "model__tol": 0.0001
          }
        },
        "random_forest": {
          "class": "RandomForestRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__bootstrap": true,
            "model__ccp_alpha": 0.0,
            "model__criterion": "squared_error",
            "model__max_depth": 5,
            "model__max_features": 0.3,
            "model__max_leaf_nodes": null,
            "model__max_samples": null,
            "model__min_impurity_decrease": 0.0,
            "model__min_samples_leaf": 10,
            "model__min_samples_split": 2,
            "model__min_weight_fraction_leaf": 0.0,
            "model__monotonic_cst": null,
            "model__n_estimators": 300,
            "model__n_jobs": 7,
            "model__oob_score": false,
            "model__random_state": 20260916,
            "model__verbose": 0,
            "model__warm_start": false
          }
        },
        "xgboost": {
          "class": "XGBRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "model__objective": "reg:squarederror",
            "model__base_score": null,
            "model__booster": null,
            "model__callbacks": null,
            "model__colsample_bylevel": null,
            "model__colsample_bynode": null,
            "model__colsample_bytree": 0.6,
            "model__device": null,
            "model__early_stopping_rounds": null,
            "model__enable_categorical": false,
            "model__eval_metric": null,
            "model__feature_types": null,
            "model__gamma": null,
            "model__grow_policy": null,
            "model__importance_type": null,
            "model__interaction_constraints": null,
            "model__learning_rate": 0.03,
            "model__max_bin": null,
            "model__max_cat_threshold": null,
            "model__max_cat_to_onehot": null,
            "model__max_delta_step": null,
            "model__max_depth": 2,
            "model__max_leaves": null,
            "model__min_child_weight": 5,
            "model__missing": "nan",
            "model__monotone_constraints": null,
            "model__multi_strategy": null,
            "model__n_estimators": 150,
            "model__n_jobs": 7,
            "model__num_parallel_tree": null,
            "model__random_state": 20260916,
            "model__reg_alpha": null,
            "model__reg_lambda": 5.0,
            "model__sampling_method": null,
            "model__scale_pos_weight": null,
            "model__subsample": 0.8,
            "model__tree_method": "hist",
            "model__validate_parameters": null,
            "model__verbosity": null
          }
        },
        "mlp": {
          "class": "TorchRegressor",
          "params": {
            "impute__add_indicator": false,
            "impute__copy": true,
            "impute__fill_value": null,
            "impute__keep_empty_features": true,
            "impute__missing_values": "nan",
            "impute__strategy": "median",
            "scale__copy": true,
            "scale__with_mean": true,
            "scale__with_std": true,
            "model__batch_size": 128,
            "model__dropout": 0.3,
            "model__hidden": [
              32,
              16
            ],
            "model__lr": 0.001,
            "model__max_epochs": 300,
            "model__patience": 20,
            "model__seed": 20260916,
            "model__val_frac": 0.15,
            "model__weight_decay": 0.001
          }
        }
      }
    },
    "ensemble": "equal",
    "independent_members": [
      "logreg",
      "random_forest",
      "xgboost",
      "mlp",
      "sim_independent"
    ],
    "market_informed_members": [
      "logreg",
      "random_forest",
      "xgboost",
      "mlp",
      "sim_independent",
      "simulator_v1"
    ],
    "quantile_head": {
      "family": "GradientBoostingRegressor",
      "levels": [
        0.1,
        0.5,
        0.9
      ],
      "trees": 100,
      "depth": 2,
      "learning_rate": 0.05,
      "seed": 20261019
    },
    "recency_weights": {
      "current_season": 1.0,
      "previous_season": 0.6,
      "older_seasons": 0.35,
      "normalization": "unit-mean sample weights for learned members"
    },
    "structural_recent_fit": "whole-game importance resampling with these weights, seed 20261019, same count of training games",
    "training_cutoff": "all seasons 2016 through the last fully completed 2026 week; never current partial week",
    "role_feature_cutoff": "completed prior games in strictly earlier weeks; partial current-week observations may inform later-week forecasts but never training beyond its cutoff",
    "game_anchor": "independent ridge alpha300 coefficients and OOF residuals fitted <=2021; current as-of football features only",
    "probability_calibration": "Platt fitted on earlier emitted 2022 predictions; >=100 rows and both classes",
    "predictive_distribution": "equal mixture: centered 2022 OOF residuals for learned yards, Poisson rates for learned counts, structural samples",
    "simulations": 1000,
    "td_definition": "rushing/receiving TD only; first offensive TD; passing/defensive/special-teams TDs excluded"
  }
}
<!-- PHASE10_FROZEN_CONFIG_END -->

## Amendment 2 — 2026-10-20 (committed before new experiments)

Start: 06:34:55 ET; Part 1 deadline 09:04:55; hard stop 17:34:55.
Part 2 starts immediately after Part 1 and lasts eight hours, including its last
45-minute wrap-up. Its exact start/end will be recorded, never backdated.
Sixteen logical cores: use at most fourteen at idle priority; a concurrent game
longrun, only if capacity is available, receives seven and other work seven.
All work is local shadow research; no promotion, odds API, keys, spending,
messages, database writes, deployment or scheduled-task registration.

This amendment explicitly permits historical games.csv **closing lines** for
the following labelled development benchmarks/market-informed ablation only.
Closing lines are not timestamped decision-time quotes. The independent default
still excludes all market features. Prospective prices come only from fetched
origin/main:data/nfl_betting.json through the existing archive collector.

### Part 1 experiments and fixed decisions

| ID | Hypothesis / fixed configuration | Data / split | Metric / acceptance |
|---|---|---|---|
| A2-P1 | Frozen equal/weighted/stacked ensembles improve original v1 and baseline B | Run original `lab.props.evaluate dev`, 2022 only; learned fits <=2021, earlier-week 2022 meta-learning; exact game/player/stat intersection, no eligibility/outcome substitutions | Per-target paired loss vs BOTH: yards MAE, reception Poisson deviance, TD Brier/count deviance only if original outputs exist; 2,000 game-cluster bootstrap draws, seed 20261020, CI upper <0, >=100 games, Holm control. Report missing rows and v1's retrospective QB/eligibility information. Never claim all 8,576 rows if coverage differs. |
| A2-P2a | Closing-implied team points improve props with otherwise unchanged model families | Saved feature rows 2016–2021 fit, 2022 week-forward evaluation; add exactly closing_team_points=(total +/- home-margin line)/2; same four learned families, quantile heads and independent structural member | Same six primary losses vs independent equal reference; CI upper <0, >=100 games; binary log loss non-increasing; Holm. Closing-information advantage limits interpretation. No prospective configuration change. |
| A2-P2b | Earlier-season fitted convex market/independent blend improves closing benchmark | Saved REG DEV 2019–22 independent predictions. For each season fit scalar w in [0,1] by least squares on strictly earlier saved DEV seasons; first season w=0. No current-season fit | Margin/total MAE and empirical-residual CRPS primary: CI upper <0, Holm; RMSE secondary. CRPS uses earlier-season residuals for both distributions (first season not scoreable for CRPS). Report matched n, fitted w and all metrics, no retrospective selection of w. |
| A2-P3 | Recent-data refit yields an auditable week-7 revision | Committed Amendment-1 frozen config; all permitted seasons through last fully completed 2026 week, expected week 6; existing recency weights | Operational: all fits/errors documented; archive revision 2 with actual creation/cutoff/hash; preserve every revision-1 byte. No performance acceptance or selection on 2026. |
| A2-P4 | Coherence diagnostics reveal accounting gaps | Each prospective game/team; compare eligible-player sums against all-player independent structural expectations; separately flag incomplete eligibility coverage | Flag if relative gap >15% for yards/receptions or >0.5 expected TDs; near-zero denominator floor 1. Pass yards vs receive yards / completions vs receptions accounting tolerances 1 yard / .01 count. Diagnostics only, no reconciliation or probability changes. Sum ATD probabilities is expected TD scorers, not expected TD count; report this semantic difference. |
| A2-P5 | Consistent quote contracts and nonnegative intervals improve usability | Exact player IDs, full-game quotes, pregame observation times | Consensus = mode across latest unique non-DFS/non-exchange books; ties choose smallest numerical line. All books at the modal line labelled consensus; deterministic representative book alphabetically. DFS-pickem/exchange retain separate labels; other traditional lines alternate. Gaps only consensus, settlement-compatible; no-vig only with both real sides. Floor nonnegative-stat quantiles at zero. Never map Defense to a person. |
| A2-P6 | Frozen configuration transports to 2023–25 | OPTIONAL one weekly walk-forward pass; all earlier-week fits; saved original v1 results read-only, never original evaluator eval | Report all metrics/CIs once, no decisions or changes. Start only with >1 hour in Part 1 AND credible runtime estimate below remaining budget. Otherwise skip explicitly; no partial look. |

Primary multiplicity family: 22 slots: six targets x two specified benchmarks
(12), six market-feature comparisons, four blend MAE/CRPS comparisons. Missing
comparisons count as p=1. Method-specific weighted/stacked comparisons and RMSE,
pinball, calibration, first-TD and coherence are descriptive; equal is primary.
Thresholds are frozen here; nothing qualifies for production promotion.

### Part 2: eight-hour prospective investigation, not a backtest

Use the same frozen independent props fit; no tuning/selection from 2026 results.
Archive every experiment/scenario in a new run/revision directory exclusively.
Seeds: 20261020, 20261021, 20261022; 10,000 simulations/game/seed for both
independent and market anchors. Unplayed week 7 only, based on pregame inputs.

| ID | Hypothesis / fixed procedure | Data and metric | Acceptance / action |
|---|---|---|---|
| A2-B1 | Prospective Monte Carlo precision is adequate | All week-7 games, both anchors, 3 seeds; report max-min ranges of margin/total means, player medians, ATD and first-TD probabilities | Unstable if margin or total range >1 point, yard median range >5 yards, reception/pass-TD median >1 count, ATD/first-TD range >.03 absolute probability; unavailable is unknown, never stable. These are precision tolerances, not accuracy claims. |
| A2-B2 | Role/lineup scenarios expose fragile projections | Expected lineup; starting QB out; top RB out and WR1 out separately; independent margin +/-7 game-script cases. Use verified pregame injuries; remove specified role and renormalize remaining shares, use prior eligible QB replacement only, unavailable replacement => blocked scenario. Each scenario 10,000 sims, seed 20261020 | Report changes vs same-seed expected baseline; scenario-sensitive if >20% mean yards/receptions (floor 5 yards / .5 count), >.10 ATD/first-TD absolute probability, or >3 points margin/total. These interventions hold unmodelled efficiencies fixed and are scenarios, not forecasts. Learned-model means are not falsely represented as scenario-refitted. |
| A2-B3 | Timestamped refreshes maintain benchmark freshness | At Part-2 start and about +2h,+4h,+6h, final refresh within last 45 minutes: fetch main/local archive plus archived weather/inactives; only quote comparisons/stale flags update | >24h stale; unknown time unverified. New forecast distributions not fitted because of price movement. No T-90 inactive list available => report unavailable, never infer active. |
| A2-B4 | Optional additional game search yields development evidence | DEV_FOLDS only, `--dev-only`, seven cores; run only after B1/B2 CPU demand ends, terminate budget before wrap; no final holdout or registry update | Descriptive DEV results only. Recalibration acceptance remains original B1; no new search winner accepted without untouched evidence. Skip if capacity/time/usage is insufficient. |
| A2-B5/B6 | Transparent evidence ranks useful investigation spots | Consensus-only comparable quotes; rank within game by confidence tier then absolute projection/line gap divided by predictive interval width (floor 1), binary by absolute probability-price gap; no synthetic prices | Tier A requires current consensus, stable, coherent, all named member means on same side, all required scenarios available and robust, compatible settlement. B: current consensus and compatible, at least one uncertainty; C: stale/missing/nonconsensus/unknown definition. Tiers are investigation-readiness, never win probability or staking advice. Missing evidence cannot satisfy A. Explain invalidators and unvalidated methods at top of Markdown. |

Expected accounting: first offensive rushing/receiving TD in regulation only;
market settlement is unverified unless explicit source evidence matches it, so
first-TD price gaps remain unavailable. Defensive/special-teams and passing TDs
are not scoring identities for this first-scorer market. ATD counts rushing or
receiving TDs only. No ROI, profit, betting recommendation or stake is produced.

Operational failures are logged and skipped; after a second identical test
failure stop retrying it, without weakening/skipping tests. If usage becomes low,
finish the current bounded step, report and stop. Optional Streamlit view is
read-only and receives no promotion controls. Final full active suite, report,
root MODEL_RESEARCH rows, commit/push only this codex branch. No new experiments
start in Part 2's last 45 minutes; final refresh and wrap-up checks are preplanned.

## Amendment 3 - 2026-10-20 (16:13 ET session)

Local app and shadow diagnostics only. Start 16:13:27 ET; Part 1 <=17:43:27,
hard stop22:13:27; no new work after21:43:27. Existing archives remain immutable.
No original evaluator eval, holdout reuse, model promotion, spend, deployment,
messages or Windows-task registration. Baseline and fixture tests are not model
experiments. Production refits reuse the Amendment-1 frozen configuration only.

| ID | Hypothesis / procedure | Data / split | Metric and fixed acceptance |
|---|---|---|---|
| A3-UI | Cached curated local views make saved shadow outputs inspectable | Existing week-7 CSV/JSON only; fixture AppTest, no network | Filename season/week/revision/timestamp ordering, path+mtime cache, representative current consensus defaults, skew guard, five tabs, glossary/diagnostics/warnings/download; all fixture and full tests pass. Operational, no accuracy claim. |
| A3-A | Rolling player medians reveal over/under calibration and skew | Saved frozen 2022 predictions; pseudo-line = nearest half-yard/count to strictly prior player/stat games' median, minimum 3 earlier observations; no real 2022 lines implied. Learned yard probabilities use strictly earlier-week OOF residuals (>=100 rows); counts Poisson approximation; binary ATD line .5 | Per-stat P(over), observed frequency, bias observed-minus-predicted, Brier/reliability bins and outcomes above model mean/median with paired game-cluster 95% CIs, 2,000 draws seed20261020. Diagnostic adequacy only if >=100 games, abs bias<=.05 and bias CI contains0. No calibration/model selection from this diagnostic. |
| A3-B | Structural allocation with an explicit other-player remainder improves coherence and yards | Saved 2022 independent structural per-player means and team totals; eligible prior-roster rows only. Structural other fraction=max(0,1-eligible structural sum/team total); rescale eligible learned means to remaining team mass; apply same nonnegative multiplicative transform to learned predictive quantiles. Original values retained | Three yard targets: paired MAE and mean pinball(.1/.5/.9) loss deltas vs unreconciled, same exact rows; CI upper<0 for both, >=100 games, Holm family below. Conservation abs error<=1e-8. Missing structural total blocks that game; never fill from outcomes. Prospective shadow sidecar shows original/reconciled/other separately. |
| A3-C | Distinct-scorer accounting improves ATD calibration | Same saved 2022 ATD rows; target=sum of structural player P(TD>=1), not TD count. Structural other-player expected distinct-scorer mass retained. Solve capped proportional scaling of eligible ensemble probabilities to remaining target, p in[0,1]. No outcomes in scaling | Paired Brier and log-loss CIs vs current equal ensemble; >=100 games; both CI upper<0 with Holm. Reliability bins and other mass reported. Infeasible target remains flagged, never silently altered. No production acceptance. |
| A3-D | Explicit replacement assumptions complete role scenarios without invented identities | Existing 26 blocked prospective QB-out cases; prior roster/role evidence only. Anonymous replacement-level role absorbs removed QB role with team baseline efficiency fixed; RB/WR-out use existing redistribution, unknown real replacement retained | Operational conservation and explicit assumption-based/scenario-not-forecast labels; no fabricated GSIS ID, no inferred inactive/active status, no predictive accuracy claim. If simulator cannot express anonymous role safely, retain unknown and report blocked. |
| A3-E | Standalone read-only archive entry points support manual scheduling | Existing official parser/collector; no odds API. Author script only, never execute/register | Fixture CLI selection/hash path; PowerShell SupportsShouldProcess/-WhatIf, every proposed task printed, quoted absolute lab paths, every-3-hour fetch/archive and T-90 collector polling. No script execution in this session. |
| A3-F | One command safely produces an append-only weekly shadow revision | Refresh -> source archives/context -> frozen fit through last wholly completed week -> new exclusive revision -> both anchors/distributions/sheets -> coherence/three-seed structural precision -> leans; target season/week arguments, no hardcoded week7 path | Mocked phase ordering/fail-fast tests; preserve older hashes, capture creation/cutoff/config/source, no overwrite. Missing required phase/data stops clearly. Default no model selection, task registration or promotion. Runtime bounded by explicit deadline; no long live week8 fit required to establish CLI safety. |
| A3-G | Frozen transport check describes 2023-25 performance | Once-only earlier-week refits, original saved v1 results read-only; never original eval | Start only with >90min AND credible full runtime within remaining budget. No partial peek; report once, no selection. If estimated 54 refits exceed budget, defer. |
| A3-H | Prospective archive supports descriptive accountability | Only already-played week7 games with refresh-confirmed outcomes after forecast creation | n/MAE/Brier only, no decisions/tuning; if no completed week7 game, skip without scoring. |

Multiplicity family: eight A3-B/C primary slots (3 yard targets x MAE/pinball,
ATD Brier/log loss). Missing slots p=1. Holm .05; thresholds never revised after
results. A/D/E/F/H are diagnostics/operations, never proof of betting advantage.
Historical sources can be revised; no real 2022 prop-market performance claimed.
New data outputs use exclusive timestamped amendment3 directories. Existing saved
forecasts and prior reports are retained; session report is
reports/run_20261020/amendment3/REPORT.md. Root MODEL_RESEARCH receives experiment
rows at wrap; no duplicate lab tracker.

Pre-execution coverage clarification (16:23 ET, before A3-A/B/C): the original
2022 structural JSONs predate team_totals instrumentation. A3-B/C may regenerate
these same frozen independent structural simulations (1,000 draws, existing
CRC32 game seeds, fit<=2021) into an exclusive amendment3 directory to retain
all-player team totals/distinct-scorer mass. No old artifact is overwritten.
Compare regenerated eligible means to their saved counterparts; discrepancies
are logged, and that game is blocked rather than silently substituted. Outcomes
are never used to construct reconciliation/scaling targets. Thresholds unchanged.

Operational clarification before A3-D/F execution (16:41 ET): weekly defaults
use1,000 simulations (the frozen recommendation) with the three existing fixed
seeds; seed/scenario tolerances stay unchanged, so extra instability remains
visible. Explicit future-week requests prepare that scheduled week from current
as-of rosters/history, including when beyond the older nine-day automatic
horizon; training still stops at the last wholly completed week. Missing QB
history uses existing neutral no-history efficiency and position-share priors
under an anonymous assumption:ROLE:TEAM identifier, never a GSIS ID. All affected
scenario sensitivity stays unknown: assumption-based replacement, never robust
verified lineup evidence. No change to A3-A/B/C thresholds or probabilities.

A3 probability-definition addendum (16:47 ET, before exact-CDF diagnostic;
no metric results inspected and all original gates retained): A3-A's declared
mean/residual and Poisson approximations are retained as diagnostics. To test
the exact P(over) shown by the weekly app, additionally reuse
lab.props.projections10.distribution on each saved2022 row, with ONLY strictly
earlier2022 weeks supplied as the residual pool, existing saved structural
samples and the existing deterministic seed/draw count. Yards require>=100
prior-week residual rows. Synthetic rolling lines remain unchanged. Report
bias/Brier/reliability and exceedance at the published mean and the displayed
mixture median, with the same game-cluster CIs; these are descriptive, no new
selection gate. Also report paired pinball deltas for reconciled vs original
mixture quantiles, separately from the preregistered quantile-head primary
pinball metrics. No gate, split, family correction or frozen configuration is
changed, and the approximations are not silently relabelled as exact mixtures.

A3 accounting coverage addendum (17:08 ET, before score inspection): code/data
coverage inspection found58/504 prospective learned rows absent from the
structural eligibility table. Matched-row A3-B/C primary metrics and the eight
Holm gates remain unchanged. Add a separately labelled full-eligible accounting
DIAGNOSTIC: retain every learned row; compute the allocatable structural budget
from known structural eligible means only; preserve all residual team mass as
explicit other/unresolved structural-eligibility mass. Missing structural means
are not evidence of zero actual volume. Rescale ALL eligible learned weights
into this conservative budget; record missing-member counts and flag the
allocation as assumption-based where needed. Test conservation to1e-8 and
report paired2022 loss CIs descriptively; no additional accuracy acceptance or
selection gate. This supports operational accounting without silently dropping
learned players. Report both matched and full-scope samples, never substitute
one for the other. Prospective original means are never replaced.

Correct future coherence flags to compare eligible original ATD sums against
expected DISTINCT scorers. Retain the TD-count gap as explanatory reference
only; it can never itself trigger a coherence failure. Existing forecast files
and already emitted comparisons stay unchanged; a new comparison timestamp
will carry the corrected definition/full-scope shadow columns. No2026 outcome
was read to define this coverage policy; no threshold changed after results.


## Amendment 4 — 2026-10-20: local FPDS incremental value

Registered before any FPDS model fitting or outcome-based feature selection. Root ignore commit15d3967 excludes subscription sources and raw imports. No site access, raw-data publication, paid call, champion change or spent simulator eval. Deadline22:56:59 ET (start20:26:59); finish current bounded step and stop on low usage.

**Observed coverage (metadata only):**145 local CSVs; explicit weekly Receiving Advanced, Receiving Alignment/Routes Run, Rushing Advanced, Bell Cow, Efficiency and Run/Pass Report start2021. All six cover2021–23 weeks1–18; Run/Pass2024 is absent. Explicit2026 history endsweek4. Other exports are season summaries or current snapshots without an explicit week; never turn them into invented weekly history.

**Hypothesis:** previously observed FPDS role, route, alignment, efficiency and team play-tendency information improves the independent props ensemble beyond its existing features. No markets enter either arm. No feature or parameter selection using confirmation/holdout outcomes.

**New fixed split:** train2021–22 (earliest two covered seasons), chronological2023 development weeks1–18, one2024 confirmation pass PENDING/not run, most recent full season2025 UNTOUCHED for modeling. This narrowly authorizes2023 player outcomes for this development experiment, superseding the old2022-only development restriction for Amendment4 only. It does not authorize `lab.props.evaluate eval` or the separate frozen2023–25 single look.2026 is inventory/prospective context only, never selection.

**As-of:** source-week w features enter only later weeks and after the final scheduled kickoff of w plus24h. Exact normalized player-name aliases and unambiguous team/game schedule joins only; unmatched/conflicting records excluded, never guessed. Weekly records use last-eight prior observations, reset by source season. Missing values stay missing; eligible sample is identical between arms, including players without FPDS history. Season summaries and season-to-date snapshots are flagged and excluded from this historical weekly experiment. Current snapshot caches require actual import/observation time before any future decision. Historical exports were retrieved in2026: weekly features are event-time reconstructions, not verified historical publication snapshots; revisions/publication timing limit all claims. Observation-aware prospective caches retain original observation/import time and never backdate it.

**Fixed features (headers determine availability, not outcomes):** Receiving Advanced: routes/route share, target share, aDOT, air-yard share, TPRR, YPRR, YAC/REC, MTF/REC, alignment route shares, prior red-zone/end-zone targets. Alignment: routes, route shares, TPRR/YPRR by alignment. Bell Cow: snaps/snap share, carry share, routes/route share and target share. Rushing Advanced: explosive-run rate, inside-five share, success/stuff rates, missed tackles/attempt, yards after/before contact per attempt. Efficiency: YPRR, YPT, YAC/REC, missed-tackle and contact rates, explosive catch/run/play rates and yards/touch. Run/Pass: pass/rush shares for Overall, Neutral, Leading7+, Trailing7+. Exclude fantasy-point totals, rankings, current target-week outcomes and all unsupported/undated tables. Deterministic qualified header names preserve repeated column meanings. No outcome-selected feature pruning.

**Paired arms:** same frozen model factory/settings (ridge or Poisson/logistic, random forest, XGBoost, MLP), same eligibility/weights/rows/seeds; only the predeclared FPDS columns differ. Fit learned members once on2021–22, as the original development protocol did; walk forward2023 inputs and binary calibration using only earlier emitted2023 weeks (>=100 rows/both classes), with no retraining/tuning on later weeks. Use the shared independent structural member, fitted on2021–22 only,1000 sims/game and seedCRC32(game_id), role/context strictly earlier weeks. Equal average of four learned plus structural where structural identity exists; same explicit four-member fallback for BOTH arms where it does not. Save membership/coverage per row. Same100-tree/depth2/.05 quantile heads at10/50/90 for yard diagnostics; no distribution inferred from votes. No v1 spent-eval outputs rerun, altered or scored.

**Primary metrics / gates (four Holm slots, alpha.05):** rec Poisson deviance; rec_yds and rush_yds MAE; anytime_td Brier (>=1 rushing/receiving TD). For each: FPDS-minus-control loss, paired whole-game clustered bootstrap95% CI,2000 draws,seed20261020. At least200 games and300 matched rows; point improvement>=1% of control loss, upper CI<0 and Holm-adjusted one-sided centered-bootstrap p<.05. Missing/failed members or incomplete structural coverage are disclosed and cannot silently count as a passed full-ensemble gate. Results remain development-only; passing a gate only nominates a shadow challenger, never promotes. Confirmation is pending regardless of development results; missing2024 Run/Pass remains a prerequisite for complete-feature confirmation.

**Secondary diagnostics:** yard pinball10/50/90 and coverage; ATD log loss/reliability; all member losses. Grouped held-out FPDS permutation importance by the six declared table families: shuffle only feature rows within position/week with seed20261020 (team features shuffled coherently by team), hold the fitted models/calibrator and shared structural values fixed; game-clustered CIs of permuted-minus-original loss. Exploratory only, no extra acceptance gates and no confirmation tuning. A suggested minimum download set may use positive importance with lower CI>0, labelled tentative development evidence. If none qualify, state no validated useful table and give a clearly unvalidated role-based candidate set. No claims of betting returns or profit.

**Operational acceptance:** fixture tests for multi-row headers, ambiguity/deduplication, percent units, weekly cutoff, future-mutation invariance, season-summary exclusion and append-only/idempotent import. Source Inbox remains byte-identical. All row-level derivatives/models/reports with unmatched identities remain in ignored data/cache/fpds; docs share only headers/counts/coverage and aggregate metrics. Hash manifests; never overwrite imports or existing forecast archives. Stop before a step whose bounded runtime cannot fit the remaining deadline.

## Amendment 6 — 2026-10-20: full weekly FPDS shadow program

Registered before any new-data model fit or outcome-based screen. Start22:34:41 ET20October; build ends by01:34:41 ET21October, research at most7h, no new work after08:49:41, hard stop09:34:41. Raw subscription data and row-level derivatives stay ignored/local. No website, key, paid call, spent simulator eval, promotion or modification of frozen forecasts. Metadata inventory found37 exports. Body SEASON/SEA takes precedence over outer export-selector Season; round-number row caps and entity completeness are audited, not assumed complete.

**Prior exposure:**2023 was development for Amendment4.2023–25 were already examined for simulator v1;2025 is therefore NOT a pristine holdout even though these new FPDS configurations have not been selected on it. Earlier game research also examined historical DEV folds. Amendment4's proposed2024 confirmation did not run. This amendment explicitly authorizes new2022–24 discovery and exactly one frozen2025 validation pass; it never authorizes `lab.props.evaluate eval`.2026 outcomes are descriptive only, never configuration/feature selection.

**Split and clock:** expanding training starts2021; discovery target seasons2022,2023,2024. Refit at weeks1,5,9,13,17 using only outcomes available before that block's first scheduled kickoff, including earlier discovery weeks. No target-block training. Source-week w usable only after its FINAL scheduled kickoff+24h and in a strictly later week. Rolling1/3/5/8, STD and EWMA(.3) count observed games, not calendar weeks; unknown missing games remain missing. Cumulative fields require verified differencing/lagging; ambiguous cumulative units are excluded. Historical downloaded exports support event-time reconstruction only: original publication times/revisions are unverified. True prospective use additionally requires actual import time before decision. Untimestamped target-week injuries/matchup assignments, fantasy/DFS fields, rankings, current projections and all unknown fields are excluded. Exact identity/team/week mapping only; unmatched/ambiguous stay missing on the identical control/challenger sample.

**Frozen trial inventory:** docs/FPDS_AMENDMENT6_TRIALS.json is the exhaustive target-specific configuration list and ceiling; no adaptive extra trials. Each attempted configuration (including controls, derived ensembles, distribution and first-TD variants) is logged, with fit-block counts separately. Failed/skipped configurations still count if attempted. Table add-one/leave-one targets are fixed from table names, not outcomes. Families H1 receiving role(rec/rec_yds); H2 rush role(rush_yds/ATD); H3 TD paths, expected-minus-actual TD and first-TD; H4 QB/pass(pass_yds/pass_tds); H5 coverage/separation/shadow/opponent position; H6 pace/script/team margin,total,win; H7 lagged injury/on-off/lineup handling; H8 distribution, conformal intervals, hurdle/negative-binomial diagnostics and low-sample shrinkage; H9 regularized linear, histogram boosting, XGBoost, MLP and combinations. Missing/unusable feature groups are reported blocked, not substituted by invented values.

**Complexity and fixed settings:** primary models ridge(alpha100), Poisson(alpha1) or logistic(C.1); numeric median imputation/missing indicators and scaling fitted on training only. Deterministic header-semantic ranking retains at most12 numeric metrics per table (all columns are audited), primarily rolling3/8 and role-change features; maximum768 FPDS model columns selected by fixed semantic order, never validation outcomes. Other windows remain cached. HGB80iterations/depth3/l2=10; XGB100trees/depth3/learning_rate.05/reg_lambda10; MLP32hidden/max_iter100/alpha1. Seeds20261020. Equal combination of linear/HGB/XGB/MLP; weighted inverse earlier out-of-fold loss; nonnegative ridge stacking or logistic binary stacking using earlier emitted blocks only (equal fallback until100 rows). No vote counts interpreted as probabilities. Simulator-informed member here is explicitly an ANALYTICAL prior-volume/role/independent-points proxy, not a new run of the PBP simulator. Current v1/champion remain unchanged. H8 shrinks to earlier-training position mean by n/(n+4); yard intervals from earlier OOF residual quantiles (train residual fallback explicitly labelled), count negative-binomial dispersion from earlier residual moments and hurdle nonzero probability fitted on earlier data; probabilities use earlier-block Platt calibration only when>=100 rows and both classes. Distribution diagnostics cannot pass a primary mean-loss gate merely by relabelling the same mean. Recency weights follow existing lab season weights, fixed in both arms.

**Groups and diagnostics:** header-selected volume/rate/share, role changes, alignment, separation, coverage, scoring paths, pace/playcaller, QB depth/pressure, line units and lagged injuries; opponent/position adjustment estimated on training/earlier observations only. Add-one-table and leave-one-table tests use identical eligible rows, including no-history players. Held-out grouped permutation moves whole table columns together within target week/position (team context coherently by team), fitted models fixed; exploratory only. Stability selection means require discovery-season sign agreement, never column selection on2025. Canary diagnostics: raw same-week rank association flags abs(rho)>.9 with>=100 pairs, shuffled-week and shifted-week fixtures/audits must show future changes do not alter earlier features; no suspicious field may enter unlagged.

**Metrics/gates:** yards MAE(primary), pinball10/50/90,80% interval coverage; counts Poisson deviance(primary), probability log loss/reliability; ATD Brier(primary), log loss/reliability; first offensive rushing/receiving TD multiclass log loss and Brier, including eligible player, other-player and no-offensive-TD mass (passing/defensive/special-teams scorers excluded). Games margin/total MAE(primary), RMSE, empirical-residual CRPS and interval coverage; win Brier/log loss. Paired WHOLE-GAME bootstrap2000draws, seed20261020; report effect size, ordinary95% CI and familywise Bonferroni-adjusted95% CI plus Holm p by hypothesis family, disclose bootstrap tail-resolution limits. A discovery nomination needs>=200games/300player rows (games>=200), >=1% relative primary loss reduction, corrected CI upper<0, Holm p<.05, improvement in>=2of3discovery seasons; final acceptance additionally needs same direction on the SINGLE2025 validation. Otherwise exploratory/rejected; nothing promoted. At most one final configuration per target is frozen from discovery (best passing primary loss; if none, control), committed BEFORE2025 scoring; validation cannot change it.2026 descriptive scoring only after freeze. First-TD and interval diagnostics remain exploratory if adequate labels/distributions cannot be reconstructed.

**Market assessment:** historical games.csv closing spreads/totals benchmark only, excluded from independent inputs. Separate market-informed blend market+w*(independent-market), w clipped[0,1] fitted only on earlier-season OOF predictions, zero fallback; compare same games with paired CIs. Historical real prop lines are absent: pseudo-lines are the player's strictly prior rolling median rounded to half-unit; calibration diagnostics do not establish a prop edge.2026 archived real quotes only support descriptive matched comparisons and forward price tracking, with timestamps/stale>24h flags; no invented prices or return/profit claims. Prospective forecasts only for unstarted games, immutable timestamped revisions with training cutoff, import time, data/config hashes and control/challenger membership.

**Operational checks:** full file/column inventory and revision diff metadata, exact GSIS crosswalk with team/week evidence, cache fingerprint includes schema/code/source/schedule/base data. Jobs checkpoint by configuration/season/refit block, atomic pointers, exact fingerprint resume only, one validation lock, private error traces and metadata-only public status every30min. Poll long jobs no more than hourly. Any failure logged/skipped; same test twice ends that repair branch. Weekly command imports append-only exports, audits/builds features, refits frozen shadow choices only, writes new local projections/leans and descriptive results log; never replaces existing archives or promotes. No extra trial, scope expansion or threshold change after seeing results.

**Pre-fit operational clarification (2026-10-20, no Amendment6 model fit yet):** the independent frozen default is selected only among configurations without a market input. Passing blend configurations are frozen separately as market-informed comparators and may receive the same single2025 pass, never replace the independent default. Pseudo-lines use the last8 verified played NFL games median, nearest half-unit; no-snap/no-usage rows are omitted and missingness reported. Source-week team/split aggregates are explicitly means of overlapping units, never claimed as additive team totals.
**Pre-fit compatibility clarification (2026-10-20; synthetic tests only):** bundled sklearn1.5 MLP has no sample-weight support. Use the lab's existing TorchClassifier/TorchRegressor with hidden32, dropout0, weight_decay1, max_epochs100, patience15 and chronological last15% early stopping, preserving recency weights. No new-data model fit or outcome-based change preceded this compatibility fix; all269 slots and statistical gates are unchanged.
**Pre-fit baseline availability clarification:** reuse the lab's NFL player formulas but recompute them from verified offensive participation (positive snaps or pass/rush/target usage), excluding DNP observations and every source week not yet available under the final-kickoff+24h rule. Apply the existing eligibility thresholds to this reconstructed baseline before assigning identical control/challenger rows; this is not the old B3 cohort. Fixed FPDS model allocation is up to12 last3 metrics/table,4 last8,2 role changes and2 position adjustments, within the unchanged768-column ceiling; all declared windows stay cached. Fantasy/PPR/xFP, implied/Vegas/closing-price and # ranking columns are explicitly excluded. These are as-of/schema safeguards set before any new-data model fit; thresholds and269 trial slots are unchanged.
**Pre-fit entity audit correction:** current exports' native player IDs match known NFL GSIS identifiers exactly. Recognize exact existing GSIS membership, then require a unique verified source-week NFL roster team; do not assume an arbitrary vendor ID family. Verified historical teams/positions override conflicting vendor display labels, retaining raw labels and correction counts. Ambiguous weekly trade teams remain unmatched. Require an actual NFL source-week scheduled game, quarantine known opponent/shadow-team contradictions, and aggregate only verified source rows. These deterministic identity/as-of corrections use no outcome-based model selection and precede every Amendment6 real-data fit; all splits,269 slots and acceptance thresholds stay unchanged.
**Pre-fit context joins:** passing-profile tables join by the already verified pregame projected-QB GSIS ID for all teammates (and the same ID for eligible passers), allowing H4 receiver context tests. Defensive front/DB lineup means join the opponent, offensive units join the own team. Permutations preserve these team contexts. This implements the stated QB/matchup hypotheses before any new-data fit; it adds no trial or parameter choice.

## Amendment 7 — 2026-10-21: manual matched-ensemble simulations

Authorized request: the full-history subfolder supersedes legacy loose Inbox exports; manually run current/future-week simulations and test FPDS for winners, margin, total and props. This is separate shadow work. Amendment6 frozen models, results and archives stay unchanged. No real-data fit is started while implementing the controls.

**Source:** `Inbox/All historical data from 2021-2026 week 6` is authoritative. Ignore loose same/older-week exports. Later same-table week N exports replace it only with identical headers and at least its historical season/week coverage; otherwise stop. All copies and model outputs remain ignored, local and append-only.

**Hypotheses / fixed budget:** matched NFL-only versus NFL+FPDS features, with identical rows, rolling history windows, model families, recency weights, calibration and refit cadence. Targets: home win, home margin, total; passing yards/TDs, receptions, receiving/rushing yards, offensive anytime TD; derived offensive first-TD probabilities. Four unchanged Amendment6 member factories (linear, histogram boosting, XGBoost, MLP), plus equal averaging via lab.ensemble. Two arms x nine targets x five outputs =90 configurations, plus two derived first-TD outputs =92 slots. No grid or model selection. Free NFL observations receive the same last1/3/5/8, season-to-date, EWMA, change and position-adjustment window families in BOTH arms. FPDS adds the existing audited group-capped features. This isolates feature-package value within each model family more closely; provider revisions/publication timing still limit attribution. The production six-member game champion is unchanged; the new four-member ensemble is explicitly labelled shadow, not a replacement champion.

**Data / split:** all available years from2021 enter forward production fits through the last fully completed source week whose final kickoff+24h precedes creation. Historical development: expanding 2022/2023/2024, refit weeks1/5/9/13/17; these years were already examined. No new2025 confirmation or selection;2026 is never used for configuration selection. Confirmation remains genuinely future pregame archives. Current and later-week forecasts use information available NOW, with the actual horizon and training cutoff; future outcomes, weather or lineups are never invented.

**Metrics / threshold:** yards MAE and pinball10/50/90/coverage; counts Poisson deviance; binary Brier/log loss/reliability; games margin/total MAE, RMSE, empirical-residual CRPS; first TD multiclass log loss/Brier. Paired whole-game bootstrap2000 draws, seed20261021; Bonferroni intervals within15 game and30 prop comparisons, plus Holm p-values. A discovery nomination requires >=1% relative primary loss reduction, corrected interval excluding zero, >=200 games and same sign in >=2/3 seasons. No full confirmation gate is claimed from this already-examined development set. Secondary metrics and first TD do not select configurations. Repeated manual runs/seeds are logged; they are not independent evidence.

**Simulation:** conditional empirical-residual draws for yards/margin/total, labelled training-residual warm-up until earlier OOF predictions exist; Poisson count draws and Bernoulli TD/win draws. First-TD categorical draws use earlier-only no-offensive-TD/other-player priors and ATD hazards. These are distribution simulations, not the unchanged play-by-play simulator. Defaults10000 draws, user-selectable simulation seed; model seeds/parameters fixed. Market prices are read AFTER independent forecasts, as benchmarks only. Historical game closing lines may be scored; no historical prop-price edge claim. No returns, staking, promotion or deployment.

**Manual safety:** fixed discovery scope only; no holdout season selector. Forecast weeks must be unstarted, with a2h admission guard and a recorded deadline. Jobs checkpoint per block, exact-data/config resume only; one active job, low priority, cores-2. Output mode and source/data/config hashes are recorded. UI never reads source CSV rows; local projection tables contain derived shadow predictions. No automatic launch, scheduling, send, publish, upload or git push from a manual job.
