# Game lines (totals, spreads, moneylines): audit and structural fix (2026-10-09)

## Finding
The live totals slope of -0.81 was real, not a settlement defect. Re-grading (audit A) matched 100% of 5,805 settlements; side direction is correct (Over/Under and Home/Away are complements). De-duplicated to one record per game/side, game-clustered bootstrap: totals slope -0.79, 90% CI [-1.49, -0.13] (n 240 rows / 148 games); spreads 0.09 [-0.40, 0.61]; moneylines 0.83 [0.36, 1.37].

## Root cause: the game model carries no information beyond the posted line
`build_game_models` is a trailing-12-game points-for/against average. Backtested through the production function on 2,575 NFL regular-season games 2016-2025 against the closing lines in nflverse `games.csv` (public data):

| | Model | Closing line |
|---|---|---|
| Total RMSE | 13.87 | **13.21** |
| Margin RMSE | 13.62 | **12.78** |
| Regression of (actual - line) on (model - line), totals | weight **-0.15** (se 0.07) | |
| same, margin | weight **-0.07** (se 0.06) | |

Every disagreement with the line (SD 3.7 points on totals, 4.1 on margin) is noise. The "edge" the app displayed on game lines was that noise, scored as EV. The effect is similar early (weeks 1-5) and late.

## Fix (Fixed underlying model)
`shared/game-market.js` (market-anchor-v1): mean = posted line, SD = residual of outcomes around the line. NFL total SD 13.46, margin SD 13.26 (fit 2016-22). Untouched holdout 2023-25 (876 games): predicted vs actual P(total > line+k): k=-7 .699/.719, -3.5 .603/.605, +3.5 .397/.378, +7 .301/.292; margin analogues within 2 points; moneyline from the anchored spread Brier .2124 vs de-vigged book moneyline .2122 (base rate .2481). NCAA has no historical line file in the repo; SD 15 (totals) and 16 (margin) come from the live 2026 sample (102 totals, 97 spreads: observed 14.7 and 15.5), a weak estimate flagged as such.

Applied to: game quotes, GOING Picks game legs, period models (scaled by the pipeline's own fractions). Raw trailing-average values stay in `model.anchored.raw_*` and the pipeline output. Kill switch: `globalThis.GOING_GAME_ANCHOR=false` or `POLICY.active=false`.

## Consequence for the product
Game-line probabilities now equal the market's, so game-line EV is about minus the vig and these lines stop appearing as recommendations. That is the honest result: no demonstrated game-line edge. Raw trailing-average projections remain only as descriptive context.
