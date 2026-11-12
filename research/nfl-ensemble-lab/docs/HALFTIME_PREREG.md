# Halftime model: pre-registration

Written on 11 November 2026, before the model was scored on any test game. The git commit that holds this file is the timestamp. Code: `lab/halftime.py`.

## Question

At halftime of an NFL game, can a model built on free data forecast the second half better than a simple rule? Second half includes overtime, the way sportsbooks settle second-half bets.

Targets:

- **Game:** second-half total points and second-half home margin.
- **Player:** second-half receiving yards, receptions and rushing yards.

## Data and split

nflverse play-by-play, regular season only. One row per game and one row per player-game, built only from plays in quarters 1 and 2, the pregame closing spread and total, and each player's earlier games.

- Fit: 2012 to 2022.
- Validation, used for design choices and for the spread of outcomes around each forecast: 2023 and 2024.
- Test: the 2025 regular season. One look, after this file is committed. No feature, setting or rule may change after it.
- Second holdout: 2026 Weeks 1 to 9, left unscored. The first draft of this file put these weeks in the test; the owner asked for the test on 2025, and the change was made before any test game was scored.
- Prospective: 2026 Week 10 onward, forecasts frozen at halftime.

## Model and comparator

- Player model: gradient-boosted trees (scikit-learn `HistGradientBoostingRegressor`) with Poisson loss.
- Game model: ridge regression on all game features. Boosted trees were tried first and lost to the simple rule on the validation seasons (second-half total 7.77 against 7.58 points of error), so ridge was chosen there, before any test game was scored.
- Comparator ("simple rule"): a linear regression on the pregame number and the first-half number alone. For games that is the closing total (or spread) and first-half points (or margin). For players it is the player's trailing average and the first-half stat.

## Rule for "beats"

For each of the five targets, the score is mean absolute error on the test games. The model beats the simple rule if the mean of (rule error minus model error) has a 95% bootstrap interval above zero, resampling whole games, with a Holm correction across the five targets. Reported as well, not used for the rule: root mean squared error, results by season, and how often the model's "over" calls of 55% or more came true against a line set at the simple rule's forecast.

## What a pass does and does not mean

A pass means the model reads the first half better than a two-number rule. It does **not** show a betting edge. A sportsbook's halftime line is a far stronger opponent than the simple rule, and no historical halftime sportsbook prices are on disk. The repository holds live prices for 13 games recorded on 1 November 2026 and nothing earlier. No return, win rate against a book or edge is claimed from this test.

## Sportsbook prices, when they arrive

Halftime lines go in `data/raw/halftime_lines/*.csv` with the columns `game_id, book, captured_at_utc, market, player_id, line, over_price, under_price`. Markets: `h2_total`, `h2_spread_home`, `h2_rec_yds`, `h2_rec`, `h2_rush_yds`. A live full-game line captured at halftime may be converted by subtracting the first-half figure, and must be flagged as converted. A price test needs its own pre-registration before those prices are compared with outcomes: the stake rule, the minimum edge, the cost assumption and the sample size are to be fixed there, on data the model has not seen.

## Validation results (2023 and 2024), not evidence

These seasons shaped the design, so they do not count as a test. Mean absolute error, model against simple rule: second-half total 7.52 against 7.58 points; second-half margin 7.12 against 7.10; receiving yards 13.02 against 13.48; receptions 0.99 against 1.03; rushing yards 11.89 against 12.41. The game targets show no gain worth the name. The player targets show a small one.

## Known limits

- The spread of outcomes around each forecast is taken from the validation seasons, so "over" rates measured on those seasons flatter the model. Player outcomes are skewed, so a line set at an average sits above the typical outcome and "under" calls against it win often. Neither says anything about a sportsbook line.

- A player hurt in the first half is not labelled in free play-by-play. Time since the player's last first-half touch is the only stand-in.
- Rushing yards below zero are set to zero for the Poisson fit.
- Routes and snaps by half are not available free; targets and carries stand in.
- Second-half touchdowns and first-touchdown markets are out of scope for this version.
