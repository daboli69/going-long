# Model research
Reviewed: 2026-10-01; baseline code `7d33e75`. **Champion:** current production game-line and prop methods, unchanged. **Challengers:** shadow/research only. Saved diagnostics below were inspected, not rerun; no profitability claim.

Required sequence: research -> hypothesis -> backtest -> untouched out-of-sample validation -> paired Champion comparison -> accept/reject. Predeclare splits/metrics; report calibration, uncertainty, sample size and decision-time data limits.

| Hypothesis | Evidence | Test | Result | Status |
| --- | --- | --- | --- | --- |
| Opponent-adjusted, ridge-shrunk NFL team scores improve game-line projections. | Established regularization; reproducible implementation in `scripts/backtest_nfl_context.py`; saved `data/football_game_validation.json`. | Chronological week-ahead score diagnostic, 800 games, seasons 2023-2026; paired RMSE with week-cluster bootstrap. Require later untouched decision-time holdout and line-probability calibration. | Margin RMSE 13.634 -> 13.213; total 13.651 -> 13.610. Total improvement 95% interval [-0.219, 0.286] includes zero. Revised-data archive; no decision-price ROI/CLV. | Challenger; do not promote. |
| Earlier role signals improve next-game receiving-yard props. | `walk_forward_roles` in `scripts/backtest_nfl_context.py`; `data/football_role_validation.json`; earlier-outcome shrinkage, not invented uplift. | 2025 chronological next-game diagnostic, 2,160 player-games; compare baseline/role MAE. Future evaluation needs frozen pregame eligibility, real lines and calibrated probabilities. | Overall MAE 21.966 -> 22.007 (worse); retrospectively known participation and revised inputs limit interpretation. | Reject tested adjustment for promotion; retain research context only. |
| Game-balanced ridge logistic recalibration improves football probability reliability. | Established logistic calibration; `scripts/calibration_audit.mjs` trains on earlier published outcomes within cohort and excludes same game. | Existing replay/tests; next: freeze tuning, choose untouched later weeks, paired Champion/market Brier + log loss, reliability bins, game-cluster uncertainty; NFL/NCAA and games/props separate. | No new measured holdout result established by this audit; implementation/tests are not performance evidence. | Shadow Challenger; pending sufficient frozen data. |

For each new experiment, append one row with primary-source citation or reproducible artifact, cutoff/splits, acceptance threshold, metrics and decision. Accept only with stable out-of-sample benefit and no material calibration/regression harm; production promotion requires Travis's approval. Never tune repeatedly on the holdout or invent historical prices.

## Phase 10 (2026-10-19, lab shadow research)

Pre-registration: `research/nfl-ensemble-lab/docs/PHASE10_PREREGISTRATION.md`, committed as `993f938` before fitting. User Amendment 1 keeps <=2021 / 2022 development and authorizes a separately committed frozen-config recent-data refit for prospective forecasts. No promotion, spend, odds API or 2026 scoring.

| Experiment / hypothesis | Split and n | Metric vs reference (paired game-cluster 95% CI) | Result / status |
| --- | --- | --- | --- |
| B1: Earlier-fold Platt calibration of the combined champion probability improves reliability. | Saved champion `v20261016_212540`, weighted average; DEV_FOLDS 2019–22 only, n=1,100. Earlier folds only fit each calibrator; first fold unchanged. | Log-loss delta +0.003097 [-0.002313,+0.008430]; Brier delta +0.000942 [-0.001448,+0.003314], 2,000 bootstrap draws, seed 20261019. Required LL <=-0.002, CI upper <0 and non-increasing Brier. | **Rejected.** Champion unchanged. Artifacts: `artifacts/props/phase10/game_recalibration.json` and `game_recalibration_dev.parquet`. |
