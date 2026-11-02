# King of the End Zone v2: pre-registration

Written and committed before any 2022 to 2025 game was scored. The model code, the test script and this file are fixed by the git commit that adds them. Anything learned later goes in the Amendments section at the bottom, dated, and never changes the rule above it.

## Question

Does a play-by-play model of each player's explosive gains give a better probability that he scores the longest touchdown of a game than a plain split of expected touchdowns?

## Model (lab/kz2.py)

- History only: regular-season play-by-play from 2016, strictly before the game's week. No simulated-game output, no injuries, no market prices are used in the tested model.
- Tail fit (PyMC, NUTS, 2 chains, 400 draws after 600 tuning, seed 11): at-risk touches are carries and targets that start more than U = 15 yards from the goal. A gain beyond 15 yards is an exceedance; a touchdown is a censored exceedance. The exceedance rate is logit-normal and the tail scale is log-normal, each partially pooled position group > role (1 to 3, by average rank in team touches) > player. The Pareto shape is pooled position group > role. Players need 10 at-risk touches to be fitted; others take their group and role defaults. Window: the last 3 seasons before the game's week. Refit at weeks 1, 4, 7, 10, 13 and 16 of each season (2026: 1, 4, 7); a game uses the latest earlier fit.
- Drive simulation: 6,000 games per matchup. Drives start where league drives have started; downs and distance; carries and targets follow each player's share over the team's last 6 games (players must have touched the ball in the last 3 games; 5% of touches go to an unlisted pool); the pass rate is the team's recent rate shrunk with 100 plays of league rate; gains inside 15 yards come from the league's gains at that yard line (for the player's position group), gains beyond 15 come from the player's exceedance rate (times the opponent's explosive-play ratio over its last 7 games, shrunk with 6 pseudo-events, clipped 0.7 to 1.4) and his Pareto tail; turnovers at the league rate; a fourth down is played on with probability 0.15.
- Environment: each team's expected offensive touchdowns = league mean times its own last 8 games' ratio times the opponent's allowed ratio, each shrunk with 6 league-average games. The number of drives is scaled (base 11, bounds 4 to 22) so the simulated touchdowns match this figure.
- Other touchdowns: defense and special-teams touchdowns at the league rate and length per team. Ties for longest are split evenly.

## Test

- Games: every regular-season game of 2022, 2023, 2024 and 2025 (about 1,088).
- Confirmation: 2026 weeks 1 to 8 (finished games), run once with the same code, as a check and not part of the rule below.
- Score for a game: log of the probability given to the real longest-touchdown scorer (floor 0.002; ties averaged). Defense, special teams and players not on the roster score as the field.
- Baselines, both using the same history cut and the same field share (the share of earlier games, over 3 seasons, whose longest touchdown was a field one, at least 5%):
  - B1, the plain expected-touchdown split: each roster player weighted by his touchdowns per game over the team's last 8 games with a prior of 0.3 touchdowns in 6 games.
  - B2, the plain touch split: weighted by his carries and targets over the last 6 games.
- Development used the 2021 season only, to make the code run. No settings were tuned on 2022 or later.

## Pass rule

- P1, beats the expected-touchdown split: the mean paired difference in log score (model minus B1) over 2022 to 2025 is at least +0.03, the 95% bootstrap interval over games (10,000 resamples, seed 1) is above zero, and the difference is positive in at least 3 of the 4 seasons.
- P2, calibrated: the top pick's average stated chance is within 2 standard errors of how often top picks won (ties credited fractionally), and at most one probability bucket (0 to 2%, 2 to 5%, 5 to 10%, 10 to 20%, 20% and up) with at least 100 player-games is more than 2 standard errors from its observed rate.
- The model is shown in the app as "validated against the plain split" only if P1 and P2 both pass. Otherwise it is shown with the label "not shown to beat the baseline".
- Power: report the number of games needed to detect a 0.05 log-score gain at 80% power using the measured standard deviation of the paired differences, and whether the test has them. Report B2 and the 2026 confirmation without a pass rule.

## What this cannot show

It cannot show profit: no prices are used, and the promotion's pool, entries and payout rules are outside the data. It also uses current position labels for players, which is a small look-ahead on labels only.

## Amendments

1. 2026-11-02, after all 27 tail fits ran and before any game was scored: four fits (2022 week 10, 2024 week 16, 2025 weeks 4 and 10) had a maximum R-hat near 2.2, meaning the two chains did not agree. The pre-registration did not say what to do. Rule added: a fit with maximum R-hat above 1.05 is refit with seed 12, then 13, then 14; the last try is kept if none pass and the count is reported. The fits and their R-hat values are listed in the results. No game had been scored when this was written.
