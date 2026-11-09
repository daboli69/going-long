# Quarterback rushing split: pre-registration

Written 2026-11-09 (the evening of BUF@MIN), before the model was built. Research challenger only. Nothing here changes a freeze; promotion needs Travis's approval.

## Question

Today the simulator and the props take a quarterback's rushing from his recent usage: one number for all his rushing yards (`lab/usage.py`, last six games). A quarterback's rushing yards are three different things with different drivers:

- **Designed runs** (sneaks, read options, called keepers): follow the quarterback's role and the team's run plan.
- **Scrambles** (`qb_scramble == 1`): follow dropbacks and pressure, so they rise when a team trails and throws more.
- **Kneels** (`qb_kneel == 1`): follow the lead late; they are rushes with about -1 yard each (2025: 452 kneels, mean -1.06 yards) and they count in a quarterback's official rushing yards.

Does building the total from the three parts, with game state, predict a quarterback's rushing yards better than his recent average?

## Target and data

- Target: the rushing yards of a game's starting quarterback (the passer with the most dropbacks for his team, at least 15 dropbacks), counting designed runs, scrambles and kneels, from nflverse play-by-play 2004 to 2025.
- Information: only games before the one predicted. Game state: the model's own pregame predicted margin for the quarterback's team (`walk_forward.parquet`, available 2012 on; the earlier seasons are used for fitting rates only with margin set to missing and not scored).
- Training for the state effects: seasons up to the season before each test season (expanding). Test seasons: **2022 to 2025**, scored once. 2012 to 2021 are fitting and a bug check only.

## Baseline (the current approach)

B0: the mean of the quarterback's total rushing yards in his last six games (at least three, else the league mean for starting quarterbacks).

## Challenger S (fixed)

For the starter in a game with predicted team margin `m` (clipped to plus or minus 14):

- Designed attempts: `rate_d * exp(b_d * m)`; `rate_d` is the quarterback's designed attempts per game over his last 16 games, shrunk toward the league starter mean with 6 games of weight. Yards per attempt shrunk toward the league mean with 30 attempts of weight.
- Scrambles: `rate_s * D * exp(b_s * m)`; `rate_s` is scrambles per dropback over his last 16 games, shrunk with 150 dropbacks of weight; `D` is the team's expected dropbacks (league mean 37.5 times `exp(b_D * m)`). Yards per scramble shrunk with 15 scrambles of weight.
- Kneels: `exp(a_k + b_k * m)` per game, league-wide (not per quarterback), yards per kneel the league mean in training seasons.
- Predicted yards = sum of the three. The slopes `b_*` and intercepts come from Poisson fits (log link, offset for the quarterback rate) on the training seasons only. No other tuning; the shrinkage weights above are fixed.

## Metrics and gate

Test seasons 2022 to 2025, paired by game, game-cluster bootstrap (2,000 draws, seed 20261110), deltas are S minus B0.

- Primary: root mean squared error of rushing yards. Secondary: mean absolute error, and bias (mean prediction minus mean actual).
- **S passes** only if RMSE and MAE are both lower and the RMSE delta has a 95% interval upper bound below 0.
- Subgroups reported, not gated: high-rushing quarterbacks (top quartile of designed plus scramble attempts per game over their last 16 games), and games with predicted margin above 7 (kneel games).
- Report each component alone: kneels against assuming zero kneels, so the kneel part is judged separately.

## For tonight

If S passes, report Allen's S projection beside his current projection with the model margin (BUF by 1.3 after the Wentz refresh) as primary and the market margin (BUF by 8.5) as a sensitivity. If S does not pass, report the numbers as a non-result and change nothing in the display.

## What it cannot show

A pass would improve the average error by an amount that may be small against single-game noise (a quarterback's rushing in one game has a large spread), and it says nothing about touchdowns, which are not modeled here. It does not test whether sportsbooks price the split.

## Results (run 2026-11-09, `scripts/qb_rush_split.py`, numbers in `docs/qb_rush_split_results.json`)

Test seasons 2022 to 2025, 2,164 starter-games, mean actual rushing yards 18.0. S minus B0, paired:

| | B0 (last-six average) | S (split) | Delta | 95% interval |
|---|---:|---:|---:|---|
| RMSE | 17.64 | 16.94 | -0.70 | -1.09 to -0.29 |
| MAE | 12.54 | 12.37 | -0.18 | |
| Bias | -0.17 | -0.25 | | |

**S passes the registered gate** (RMSE and MAE both lower, RMSE interval below zero). It is a small gain: about 4% of RMSE.

- Top quartile of rushing quarterbacks (541 games): RMSE delta -1.39 [-2.46, -0.32], MAE delta -1.66.
- Games with predicted margin above 7 (255 games): RMSE delta -1.38 [-2.58, -0.26].
- Kneel component alone (S against S without kneels): RMSE delta -0.004 [-0.036, +0.026], MAE delta -0.175. Kneels help the typical error, not the squared error.
- Margin barely changes the prediction for a given quarterback; most of the gain is from the three-part rates with shrinkage, not the game-state slopes. This test did not separate the split from the shrinkage (a shrunk total-yards baseline was not registered), so it cannot say how much of the gain is the split itself.

**Bias for the heavy rushers, not in the gate and found afterward:** for the top decile of prior rushing rate (224 games) the actual mean was 46.3 yards, S predicted 41.0 (-5.3) and B0 predicted 47.5 (+1.2); RMSE 29.0 against 30.6. For the top 5% (115 games): actual 48.8, S 45.1, B0 51.8. The shrinkage pulls the very best rushers toward the league, so S under-predicts them by about 4 to 5 yards on average while still scoring a lower RMSE. A less shrunk version would be a new challenger and a new registration.

## Allen, BUF@MIN (`scripts/qb_rush_split_tonight.py`)

History: his last 16 starts. Last-six average 41.2 yards.

| Margin | Designed | Scrambles | Kneels | Total |
|---|---:|---:|---:|---:|
| BUF by 1.3 (model, after Wentz refresh) | 3.0 att, 10.5 yds | 2.6 att, 23.0 yds | 0.7, -0.7 yds | 32.8 |
| BUF by 8.5 (market) | 2.9 att, 10.4 yds | 2.5 att, 22.3 yds | 0.8, -0.9 yds | 31.8 |

Given the bias above, 33 is a floor-leaning number for Allen; the backtest suggests the shrunk total runs about 5 yards low for quarterbacks like him, and the last-six average of 41 runs about a yard high. Neither is the answer; both are inputs. Nothing in the app or the simulator was changed.
