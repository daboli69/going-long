# Dependence between outcomes in one game: pre-registration

Written 2026-11-06, committed before any dependence was estimated. Football only. No staking and no bet sizing anywhere in this document.

## Question

The lab forecasts each player prop on its own. Do the outcomes inside one game move together in a way those separate forecasts miss, and by how much? This tests dependence only. It does not test whether any price is wrong.

## 1. Structural reason

A same-game combination (several legs from one game sold as one bet) cannot be priced from single-leg prices alone. Whoever sells it has to assume how the legs move together. The simplest assumption is a flat adjustment, or independence with an extra margin. If the true dependence differs by pair (a quarterback and his receiver, a runner and the passing volume), a flat assumption is wrong in a predictable direction for some pairs and the other direction for others. The buyers of these products are mostly casual bettors, so there is less pressure to correct it than in a single-game line.

This is a reason to look, not evidence. We hold no same-game combination prices, so this test can show better joint calibration. It cannot show a betting edge.

## 2. Raw inputs: what exists and what does not

Exists:
- Independent per-player marginal forecasts with outcomes and a probability-integral-transform value (PIT, the outcome's position inside its own forecast distribution), column `pit_base`, in `artifacts/props/dev/player_games.parquet` (2022) and `artifacts/props/eval/player_games.parquet` (2023 to 2025). Stats: passing yards, receiving yards, receptions, rushing yards.
- Player positions from `artifacts/props/phase10/features.parquet` and `features_production.parquet`.
- Team points forecasts and actuals in `artifacts/props/eval/team_points.parquet`.
- Raw Kalshi single-market prints and order books, and raw sportsbook quotes for 2026 only.

Missing, and left missing:
- A marginal forecast for team pass attempts. The pair "runner with team pass attempts" is therefore not tested. A substitute pair, rush yards with quarterback passing yards, is tested instead and is labelled as a substitute.
- A marginal forecast distribution for the game total. The pairs "game total with each player" are not tested.
- Any same-game combination price from Kalshi or a sportsbook. None is cached and none is invented.
- Quantile functions for the marginals. Scoring is therefore done in PIT space (below), which scores the dependence given the marginals, not the marginals themselves.

## 3. Fixed in advance

Unit: one team in one game. Variables per player-game: the stored `pit_base`.

Normal scores: for each stat, the PIT values of the fit seasons define an empirical distribution function F. Every player-game, fit or held-out, becomes u = F(pit_base), clipped to [1/(n+1), n/(n+1)], and z = Phi^-1(u). The marginals are not uniform (they are mildly miscalibrated), so this step removes marginal error before dependence is measured. Held-out values use the fit-season F only.

Pairs tested (all within one team and one game):
- A: quarterback passing yards with a wide receiver's receiving yards.
- B: quarterback passing yards with a tight end's receiving yards.
- C: quarterback passing yards with a running back's rushing yards (substitute for team pass attempts).

Only players with a known position are used. Counts excluded for missing positions are reported.

Copula families, fitted per pair class by maximum likelihood on the pooled fit data: Gaussian (one correlation), t (correlation, degrees of freedom from {4, 8, 16}), Clayton (one parameter, lower-tail dependence). The family with the lowest BIC on the fit seasons is the only one tested on held-out data. The others are reported as descriptive.

Seasons: fit on 2022, 2023 and 2024. Hold out 2025, scored once. No rerun after seeing the score.

## 4. Power gate and recovery, before any real dependence is estimated

Using only the count structure of the data (how many pairs each game has, never an outcome):
- Simulate normal scores with a planted Gaussian correlation, run the full procedure (fit family, score on a simulated 2025 with the real structure), and repeat 400 times.
- Recovery: planted correlations 0, 0.10, 0.20, 0.30, 0.50. Pass if the mean estimated correlation is within 0.03 of the planted value for 0.20 and the rate of a false significant result at 0 is at most 0.07.
- Power: planted correlation 0.15, the smallest size of interest. A pair class is informative only if power at one-sided level 0.05/3 is at least 0.80.
- Also report the number of held-out games that would give 80% power at 0.15.
- A class that fails the gate is not scored on 2025 and is reported as uninformative. If all fail, the held-out season stays unscored and the work stops.

Fit-season estimates (correlations, family choice) are descriptive and are reported whether or not the gate passes.

## 5. Scoring (only for informative classes)

Forecast: for each pair observation, 400 seeded draws of (z1, z2) from the chosen copula, and from the independence model (standard normal, no correlation).
- Energy score: E||X - y|| - 0.5 E||X - X'||.
- Variogram score with p = 0.5 on the pair.
- Loss difference d = independence score minus copula score. Positive means the copula is better.
- Average d within each game, then test across games: block bootstrap by game (2000 draws) and a Diebold-Mariano statistic on the game-level means. One-sided.
- Holm correction across the classes and the two scores that were scored.

A class passes only if its Holm-adjusted p is below 0.05 for both scores.

## 6. Price check (only if something passes)

Compute, for typical over and over legs of the passing pair, the joint probability under the copula against the product of the single-leg probabilities, in cents. Compare with Kalshi's published fee schedule read at run time. If the schedule cannot be read, say so. No stake, no sizing, no expected return.

## 7. Prospective record

Each week, save the fitted dependence parameters and, for each team-game pair that has two published over lines, the single-leg probabilities and the joint probabilities under independence and under the chosen copula, in a write-once hashed file (`data/dependence/`). Nothing is backfilled. Outcomes are added by a later scoring command. Sportsbook same-game-combination quotes are captured only if a free source with an exact quote is found. None has been identified, so none is captured.

## 8. Report order and rule

Completed, Model Research, Concerns, Next, Needs Travis. If nothing beats independence, the result is "no edge found" and the simulators are left unchanged. A dependence layer may be added to the existing simulators only if a class passes both the gate and the held-out score.
