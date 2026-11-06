# Coherence between the game line and the props: pre-registration

Written 2026-11-06, committed before any result was computed. Football only. No staking and no bet sizing anywhere in this document.

## Question

When the game line and total move, do the prop lines for that game move to match, and do player forecasts that are made to add up to the quarterback's passing total beat the same forecasts left independent?

There are two separate tests. They share a reason but not data, and each has its own gate.

## 1. Structural reason

A prop ladder has far fewer traders than the spread and total. If the game line moves on news, the people who price a passing-yards ladder have to notice the move and redo their number. Any delay means the prop still reflects the old game. On the forecast side, our player forecasts come from separate models. Nothing makes a quarterback's forecast equal the sum of what his receivers are forecast to catch, so the set can disagree with itself. If the disagreement carries information about which forecast is off, using it should lower error.

These are reasons to look, not evidence.

## 2. Inputs: what exists and what does not

Exists:
- Hourly Kalshi candles (bid and ask) for game spread ladders, game total ladders, and player ladders for passing yards, receiving yards, receptions and rushing yards: 66,821 markets over 392 games from 2025-09-05 to 2026-11-03, in `data/cache/props_kalshi/candles` and `props_kalshi_scope.parquet`.
- Per-player independent baseline forecasts (`base_mean`), the simulator's means (`sim_mean`) and actuals for 2022 to 2025 in `artifacts/props/{dev,eval}/player_games.parquet`, with positions from the phase 10 feature files.
- Team points forecasts and actuals in `artifacts/props/eval/team_points.parquet`.
- Play-by-play with players on the field in `data/cache/player_plays.parquet`.

Missing, and left missing:
- Timestamped sportsbook player-prop lines. The 2026 sportsbook quote file holds only moneyline, spread and total (142,408 rows to 2026-10-16). Sportsbook props cannot be tested for lag. The lag test uses Kalshi only, so it asks whether Kalshi's player ladders trail Kalshi's own game ladders, not whether sportsbooks trail anyone.
- Stored quantile functions for the player forecasts, so CRPS cannot be computed for reconciled forecasts. The reconciliation test scores the squared error of the forecast mean instead.
- A forecast for receivers who are not listed, which is why a remainder term is estimated (below).
- A sum-of-yards link to the game total. Points are not a sum of yards, so the game total is an input to the lag test and not a level of the add-up hierarchy.
- The Kalshi fee schedule (the PDF returned an error when read). Bid-ask spreads are measurable from the candles, so the price check uses those and does not state a fee.

## 3. Test A: reconciliation of player forecasts

Unit: one team in one game with exactly one quarterback row and at least one listed receiver (positions WR, TE, RB with a receiving-yards forecast).

Hierarchy: the quarterback's passing yards equal the sum of all receivers' yards, listed receivers plus an unlisted remainder. Forecast of the remainder = a share of the quarterback forecast, with the share estimated on the fit seasons by number of listed receivers (1, 2, 3, 4, 5 or more) as the ratio of summed actual remainder to summed actual quarterback yards.

Incoherence c = f_QB - sum of f_listed - f_remainder, with f = `base_mean`.

Estimated reconciliation (the least-squares form of MinT, with the error covariance replaced by its measured regression on c):
- Quarterback: f_QB + b_Q c, where b_Q is the slope of (actual - f_QB) on c, no intercept, fitted on the fit seasons.
- Each listed receiver: f_r + b_R c f_r / sum f_listed, where b_R is the pooled slope of (actual - f_r) on c f_r / sum f_listed.

Seasons: fit on 2022 to 2024. Hold out 2025, scored once.

Score: squared error of the mean, reconciled against unreconciled, per node group (quarterback, receivers). Game-level mean of the difference, bootstrap by game (2000 draws), Diebold-Mariano statistic, one-sided, larger of the two p-values, Holm across the two groups. A group passes at adjusted p below 0.05. The same procedure on `sim_mean` is reported as descriptive only.

Gate, before any real error is read (uses only forecast means and counts): plant errors of the form y = f + b c + noise with the noise sized so that c explains 3% of the error variance, for quarterback and receivers, using the real forecast means and team-game structure. Run the full procedure 400 times. Recovery passes if the mean estimated slope is within 25% of the planted one. Power is the share of runs with both groups significant at level 0.05/2. A group is informative only if power is at least 0.80. If the held-out sample is too small, the group is reported as uninformative and not scored. Also report the number of games for 80% power.

## 4. Test B: do player ladders trail the game ladders

Implied median of a ladder: the strike where the monotone-smoothed probability crosses 0.5, from the mid of the hourly bid and ask. A ladder is usable at an hour only if it has at least three priced strikes that bracket 0.5. Team implied points come from the total and spread medians.

Horizons: 24, 12 and 3 hours before kickoff.

Model, standardized variables, by game: move of a player's median from 12 to 3 hours = L x (move of the team's implied points from 24 to 12 hours) + P x (move of the same median from 24 to 12 hours) + error. L above zero means the prop kept catching up to a game-line move that was already visible. Players: quarterback passing yards and receiving yards pooled, errors clustered by game.

Stages: decide on 2025 games, confirm on 2026 weeks 1 to 8. Report L with a bootstrap by game.

Gate: the smallest detectable L is 2.8 times the bootstrap standard error of L in the confirm stage. The smallest size of interest is 0.15. Both come from the dispersion of the moves, never from the sign or size of L. If the smallest detectable L is above 0.15, Test B is reported as uninformative and the effect is not read.

## 5. Price check

Only if a result passes: compare the typical catch-up move, in cents of ladder price, with the bid-ask half-spread of that ladder at 3 hours. No fee is stated, because the schedule was not read. No stake, no sizing.

## 6. Prospective record

Each week, save a write-once hashed file of the quarterback and listed-receiver means from the newest weekly run, with c and the reconciled values, under `data/coherence/`. Nothing is backfilled. A scorer for outcomes is added once a week has results.

## 7. Report order and rule

Completed, Model Research, Concerns, Next, Needs Travis. If neither test passes, the result is "no edge found". Reconciliation is applied to the forecasts shown in the app only if Test A passes for a group, and only after a separate decision from Travis.

## Amendment 1 (2026-11-06, committed before Test B counts or moves are computed)

Test A's gate has already been run (power for the quarterback group 0.57, for receivers 0.77, so neither is informative on 2025; see docs/coherence_gate_A.json). This amendment fixes implementation details of Test B that section 4 left open. None of them depends on a result.

- Contracts: only ladders whose strike type is "greater" (an "over X" or "wins by over X" contract). Structured contracts are ignored.
- Quote used at a horizon: the last hourly candle ending at or before kickoff minus the horizon. It counts as a usable price only if the bid is above 0, the ask is below 1, and the ask minus the bid is at most 0.20. The price is the mid of bid and ask.
- A ladder is usable at an hour if at least three strikes have usable prices and the smoothed probability crosses 0.5 inside the strike range. Smoothing is an isotonic decreasing fit across strikes.
- Game spread: each team's "wins by over X" ladder gives a crossing only for the favorite. That team's implied margin is the crossing, the other team's is minus the crossing. Team implied points = (total median + team margin) / 2.
- Players: quarterback passing yards ladders and receiving yards ladders, pooled. A player needs a usable ladder at all three horizons and the team needs a usable total and spread at 24 and 12 hours.
- The minimum detectable L and the counts are computed for both stages before L itself is shown.
