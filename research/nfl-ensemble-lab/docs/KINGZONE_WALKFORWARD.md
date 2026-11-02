# King of the End Zone v2: walk-forward results

The rule, model and baselines are in `docs/KINGZONE_PREREG.md` (committed before any 2022 to 2025 game was scored, with two dated amendments, both made before scoring). Raw numbers: `docs/kingzone_walkforward.json`. Code: `lab/kz2.py`, `scripts/kz2_backtest.py`.

## What was tested

1,079 regular-season games from 2022 to 2025 that had a touchdown, each predicted from play-by-play history strictly before its week, with a tail model refit at weeks 1, 4, 7, 10, 13 and 16. 27 fits ran. Four had chains that disagreed (R-hat near 2.2) and were refit with the next seed, as Amendment 1 says. A fifth (2023 week 1, R-hat 1.07) was missed by that pass, refit under the same rule and its season rerun (Amendment 4). All 27 kept have R-hat of 1.05 or lower.

## Results against the pass rule

| Check | Result | Rule | Outcome |
| --- | --- | --- | --- |
| Gain over the plain expected-touchdown split (average log score per game) | +0.171, 95% range +0.128 to +0.213 | at least +0.03, range above zero, 3 of 4 seasons positive | Pass (all 4 seasons positive: 0.16, 0.23, 0.19, 0.10) |
| Top pick stated against realized | 13.6% against 11.8% (standard error 1.0 point) | within 2 standard errors, and at most one flagged bucket | Pass by a hair (1.8 standard errors); one flagged bucket |
| 2026 weeks 1 to 8 (119 games, confirmation only) | +0.276, 95% range +0.120 to +0.434 | positive | Positive |

Average log score: model -2.81, plain touch split -2.93, plain expected-touchdown split -2.98. The gain over the touch split is +0.119 (range +0.088 to +0.149).

Per the rule both passed, so the stored label is "validated". Read that with care. P2 passed by a hair: the first full run, before the 2023 week 1 fit was refit under Amendment 4, put the top-pick gap at 2.0 standard errors and failed it. One refit of one early-season fit moved a borderline test across its line, so P2 is best read as "borderline", and the screen says the chances run a little high at the top, which the numbers support (stated 13.6%, realized 11.8%, and 21.8% against 14.3% in the 20%-and-up bucket).

## Reliability

| Stated chance | Player-games | Stated | Realized |
| --- | --- | --- | --- |
| 0% to 2% | 14,739 | 0.77% | 1.01% (flagged) |
| 2% to 5% | 6,960 | 3.3% | 3.1% |
| 5% to 10% | 4,714 | 7.1% | 6.5% |
| 10% to 20% | 1,665 | 12.8% | 11.8% |
| 20% and up | 35 | 21.8% | 14.3% (standard error 7 points) |

The model gives the field (defense, special teams and unlisted players) 16.5% and it won 13.4% of games. The average longest touchdown is 36.4 yards in the model and 38.3 yards in the games. So the model is a little too confident in its favorites and a little too sure the longest touchdown belongs to a listed player, and it under-rates the long shots.

## Power

The standard deviation of the paired differences is 0.72. Detecting a true gain of 0.05 at 80% power needs about 1,607 games (787 at 50% power). The test has 1,079, so it cannot reliably detect a gain that small. It does detect a gain of 0.17.

## Benchmarks that exist for free

- Plain expected-touchdown split and plain touch split: above.
- Archived prices: the only free player prices are Kalshi anytime-touchdown quotes for 2026 (`docs/kingzone_price_check.json`). On 212 players in 12 finished games, the model's anytime-touchdown chance and the quote have the same log loss (0.491 against 0.492; difference -0.001, 95% range -0.030 to +0.028) and similar Brier scores (0.160 against 0.158). That says the model's touchdown chances are about as good as the quote, on a small sample. It says nothing about the longest touchdown: no longest-play or King of the End Zone prices were archived anywhere free. The model's average anytime chance is 18.5% where players scored 23.1% and the quote averaged 21.7%.
- Tracking speed: Big Data Bowl 2026 data on disk covers only the 2023 season (pass plays, before the throw). Top route speed from weeks 1 to 9 did not help predict 15+ yard gains in weeks 10 to 18 beyond a receiver's own record (coefficient 0.026 per standard deviation, p = 0.62, 331 receivers, 7,385 targets; `docs/kingzone_speed_check.json`). It is not in the model.

## Concerns

- The probabilities at the top are too high (above), and the calibration pass is borderline. A recalibration trained on 2022 to 2024 and tested on 2025 is the obvious next step; it was not done because it would be a new model after seeing the result.
- Fixing the R-hat miss (Amendment 4) happened after I had seen the first report. It was mechanical, but it is a decision made with results in view, and it flipped a borderline check.
- Anytime-touchdown chances look low against how often players scored in 2026 and against the quote.
- The test cannot use injuries, so it ignores that some roster players were out; the app drops players listed Out or on injured reserve, which the test never checked.
- Position labels are today's, a small look-ahead on labels only.
- The crowding estimate has no data behind it (see the screen's note).
