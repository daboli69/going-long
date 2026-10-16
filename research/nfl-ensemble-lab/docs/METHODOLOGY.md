# Methodology

## Unit and targets
One row per NFL game (regular season and playoffs, 2016 onward; 2015 only for carryover).
- Winner target `home_win` (ties excluded from winner training and metrics).
- Margin target `margin = home_score - away_score` (ties included).

## Pregame features (`lab/features.py`)
Per team per completed game, play-by-play is aggregated (offensive plays = pass/run,
no two-point tries). Each team row also carries a defensive mirror (`d_*`) from the
opponent's offense in that game.

Windows, attached **as of kickoff** with `merge_asof(..., allow_exact_matches=False)`:
`std` (season to date), `l3`/`l5` (last 3/5 games, may cross seasons), `prev` (full
previous season), and `blend = (n*std + 3*prev)/(n+3)`.

Additional features:
- Opponent-adjusted ridge ratings of point margin and EPA/play margin, fit per (season, week)
  on games before that week's first kickoff (previous season weighted 0.35).
- Starting-QB efficiency: the listed starter's last 600 dropbacks of QB EPA, shrunk toward -0.05
  with k=150. QB-change flag. Log career dropbacks.
- Context: home field / neutral, week, playoff, divisional, dome, rest days, short week, off bye.
- Matchups: home minus away for every window and stat, plus offense-vs-defense combinations.

The full catalog (source, formula, availability) is written to `data/cache/feature_catalog.csv`
and shown in the Data Manager. Default model input: 78 features in six groups (selectable).

**Known caveat:** historical QB identity is the starter recorded by nflverse. That is almost
always announced pregame, but late scratches are a small source of hindsight.

## Leakage tests (`tests/test_features.py`)
Changing one game's score, team stats and QB EPA must leave every feature of every game
at or before that kickoff byte-identical, and must change later games. Season-to-date resets
at season boundaries. `l3` equals the hand-computed mean of the three prior games.

## Models (`lab/models.py`)
| # | Winner model | Margin model |
|---|---|---|
| 1 | Logistic Regression (L2, standardized) | Ridge linear regression |
| 2 | XGBoost | XGBoost regressor |
| 3 | Decision Tree (depth / leaf / ccp pruning) | Decision Tree regressor |
| 4 | Random Forest (300 trees, depth- and leaf-limited) | Random Forest regressor |
| 5 | Feedforward NN (PyTorch, 2 hidden ReLU layers, dropout, weight decay, early stopping) | same, MSE |
| 6 | Single-layer NN (one linear layer + sigmoid, weight decay, early stopping) | single linear layer, MSE |

Imputation and scaling are fit inside each pipeline on training rows only. Neural-network
early stopping uses the chronologically last 15% of training rows. Fixed seeds and
deterministic PyTorch make the networks reproducible.

**Model 6 vs model 1:** a single linear layer + sigmoid trained with cross-entropy and L2
is the same statistical model as regularized logistic regression. Only the optimizer differs.
Their agreement is expected and is never treated as independent confirmation.

## Chronological protocol (`lab/training.py`)
1. **Tuning**: small grids per model; each config trains on seasons < s and is scored on
   s ∈ {2020, 2021, 2022}; lowest mean log loss (winner) or MAE (margin) wins.
2. **Walk-forward**: every season from 2018 on is predicted by models fit on all completed
   seasons before it. These out-of-sample predictions are saved (`oof_predictions.parquet`).
3. **Calibration**: none / Platt / isotonic per model. The calibrator for season s is fit on
   out-of-sample predictions from seasons < s. The method is chosen on 2023–2024.
4. **Ensembles**: majority vote (3-3 broken by equal average and flagged), equal average,
   skill-weighted average (weights ∝ max(0, ln 2 − log loss) on earlier seasons), and logistic
   stacking on logits fit on earlier seasons only.
5. **Champion**: lowest validation (2023–2024) log loss among the six models and three
   probability ensembles. Written to `selection.json` before the 2025 test season is scored.
6. **Production**: all models refit on every completed game as a new version. Historical
   results stay under `artifacts/runs/<version>/`.

Development-split metrics for 2020–2022 share seasons with tuning and are optimistic.
Read validation, test and prospective results instead.

## Metrics
Accuracy, Brier, log loss, expected calibration error, 10-bucket calibration tables,
95% game-level bootstrap intervals, season-by-season tables. Margin: MAE, RMSE,
winner accuracy of the margin sign, compared with the closing spread. Baselines: home-field
prior, and a one-step point-differential logistic model.

## Explanations (`lab/explain.py`)
Local (this game): coefficient × standardized value (LR, single-layer), TreeSHAP (XGBoost),
Saabas path attribution (RF), literal decision path + leaf win rate (DT), occlusion-to-mean
(feedforward NN, approximate). Global: permutation importance on the first validation season
using a model trained only on earlier seasons. Explanations describe the uncalibrated model.

## Weekly snapshots (`lab/weekly.py`)
Each run writes `snapshots/<season>_wNN/<UTC timestamp>_<model version>.json|.parquet`,
opened with exclusive-create mode and then marked read-only. Each file records the
source-file hashes and model version used. Games already kicked off are flagged as
retrospective.

## Phase 2 interface (not built)
The upset-discovery work should read, without rebuilding anything:
- `data/cache/feature_store.parquet`: pregame features + outcome + closing no-vig probability.
- `artifacts/runs/<version>/oof_predictions.parquet`: walk-forward raw and calibrated
  probabilities for all six models, all ensembles, the baselines, margins, split label and
  training window.
- `snapshots/`: prospective predictions frozen before kickoff.
Residual targets must be built from the out-of-sample columns only (`p_*`), never from
production-model predictions on games those models were trained on.
