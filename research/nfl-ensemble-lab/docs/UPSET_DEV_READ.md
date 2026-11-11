# Upset test: development read, 2018 to 2025

Run 2026-11-11 from `scripts/upset_read.py`, following `docs/UPSET_PREREG.md`. Output is in `reports/upset/DEV_READ.json`. This read cannot confirm anything. It changes no model and publishes no pick.

## Result

The sample is 1,631 regular-season games with a closing spread of 1 to 7 points and a hold between 0.5% and 8%.

| Group | Games | Underdog win rate | Market probability | Excess | 95% interval | Cover rate |
|---|---|---|---|---|---|---|
| Flagged (2 or more signals) | 336 | 45.8% | 40.9% | +0.049 | -0.003 to +0.102 | 55.2% |
| Unflagged | 1,295 | 36.7% | 37.1% | -0.004 | -0.030 to +0.022 | 51.3% |
| All underdogs | 1,631 | 38.6% | 37.9% | +0.007 | -0.017 to +0.031 | 52.1% |

The flagged mean is above zero, but the interval includes zero. The registration needs an interval above zero before the idea counts as a hypothesis, so that bar is not met. The read is inconclusive.

## By season (flagged games)

| Season | Games | Excess |
|---|---|---|
| 2018 | 41 | +0.036 |
| 2019 | 43 | +0.135 |
| 2020 | 37 | +0.119 |
| 2021 | 40 | +0.136 |
| 2022 | 47 | +0.029 |
| 2023 | 41 | -0.072 |
| 2024 | 41 | +0.023 |
| 2025 | 46 | +0.001 |

Almost all of the excess comes from 2019 to 2021. The last three seasons average close to zero.

## How often each signal fired

S1 (opponent-adjusted EPA lead) 23.9% of games, S2 (early-down success lead) 33.5%, S3 (favourite's record flatters it) 10.7%, S4 (quarterback continuity) 13.2%.

## Choices made before the first run

The registration left some details open. These were fixed in the script's header before it ran, and the script ran once.

- Regular season only.
- S1 uses the feature store's opponent-adjusted ratings, offense minus defense. Those ratings can carry information from the previous season early in the year.
- S2 uses first and second down runs and passes from earlier games of the same season. It is not opponent-adjusted, and it is false in Week 1.
- S3 fits points differential on EPA differential using earlier seasons only.
- S4 compares the projected quarterback with the team's previous three games.

## Limits

- The S4 quarterback field in historical rows has not been checked against what was known before kickoff. If it holds the actual starter, S4 leaks late news the market also had, which would not inflate the result but would make the live version differ.
- The market probability comes from the nfldata consensus line, not a price at a named book. A 4.9 point excess before the bookmaker's margin is not a return.
- These seasons have been examined many times in this project.

## What happens next

No variants are tried. Flagged games from 2026 Week 11 onward can still be logged at no cost for the registered single look, but nothing is claimed until then.
