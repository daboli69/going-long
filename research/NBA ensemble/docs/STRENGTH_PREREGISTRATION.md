# NBA strength features: preregistration, 2026-10-23

Written and committed before any candidate below was fitted or scored. Travis asked Claude to find and test improvements to the six-model winner ensemble on past seasons, so that results don't wait for 2026-27 games. Original frozen configuration, models and forecasts stay unchanged. No odds, paid services or deployment.

## Why these three

The six members all read the same 38 inputs: a win/loss Elo plus 5/10/20-game box-score averages. That design has three blind spots.

1. **Margin and schedule strength.** The Elo ignores margin, and rolling averages ignore who the opponent was. Margin-based ratings are the standard stronger NBA baseline.
2. **Travel.** Rest days are modeled; distance, time-zone changes and Denver/Utah altitude are not.
3. **Who is actually playing.** Team averages can't see a star's absence or a trade. Player boxes are already archived (2020-21 onward) but feed nothing.

## Features (code: `nba_lab/strength.py`)

All are home minus away, built only from games released at tipoff + 24 h, strictly before the decision time, the same rule as `features.py`.

- `diff_mov_elo`: FiveThirtyEight-style margin Elo. K 20, home edge 100, multiplier `((|margin|+3)^0.8)/(7.5+0.006*winner_elo_diff)`, 75% carryover between seasons.
- `diff_ridge_net`: ridge regression of capped (±30) home margin on team ratings plus a home term. Game weights halve every 45 days, ridge penalty 5, no reset between seasons.
- `diff_travel_1000km`, `diff_tz_shift`, `altitude_home`: great-circle distance and absolute standard-time-zone change from each team's previous game venue; altitude flag when Denver or Utah hosts. Neutral sites have unknown location. The 2020 Orlando restart is treated as neutral at Orlando.
- `diff_roster_gmsc`: for players who played in the team's latest released game, a shrunk per-minute Game Score (150 replacement minutes at 0.22 per minute, last 40 games for any team) times their average minutes over the team's last 5 released games, scaled to 240 minutes.
- `diff_absent_gmsc`: value of players averaging at least 20 minutes over the team's last 10 released games who did not play in the latest one.

The roster features use only boxes of earlier, released games. They never see the target game's lineup or injury report, so they can't capture same-day scratches.

## Design

Same six fixed member configurations (`models.py`), median imputation, standardization and per-member sigmoid calibration. Each test season: train through season-2, calibrate on season-1, score the season. The stacker uses only earlier out-of-fold predictions of the same configuration; the first season falls back to the equal mean, as in the original engine.

- Study A, test seasons 2019-2026 (about 8,600 games), training from 2016: `control`, `rating`, `travel`, `rating_travel`.
- Study B, test seasons 2023-2026, training from 2021 (player boxes start there): `control_b`, `roster`, `all` (rating + travel + roster). Both use the same restricted rows, so the comparison is fair.

Seasons 2024-2026 were already examined in earlier studies, while 2019-2022 were never reported as test targets. Results are reported for both groups. This is retrospective evidence, not a fresh confirmation.

## Gate

Five comparisons: rating, travel and rating_travel vs control; roster and all vs control_b. Primary metric: stacked-ensemble log loss on pooled test games. Paired whole-game bootstrap, 2,000 draws, seed 20261023, Bonferroni alpha 0.05/5.

A candidate passes when (a) the corrected interval for log-loss change is entirely below zero, (b) it improves in at least 75% of test seasons (6 of 8 in A, 3 of 4 in B), and (c) Brier is no worse. The original 1% relative-loss threshold is reported but not required. It was set against Elo, and an added input to an already-fitted ensemble shouldn't be held to the same bar. That choice is made here, before results.

A passing candidate may become a separately labelled shadow forecast. It does not replace the frozen ensemble; promotion stays Travis's call after prospective 2026-27 evidence. Budget: 7 configurations, 264 base fits, 264 calibrators, no hyperparameter search, no reruns with changed constants after seeing results.
