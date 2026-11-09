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
