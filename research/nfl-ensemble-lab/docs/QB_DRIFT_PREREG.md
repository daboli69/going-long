# Quarterback talent drift: pre-registration

Written 2026-11-09, before the model was built. Descriptive and research only; nothing feeds a freeze, a forecast or the app.

## Why

The Wentz versus Murray check could not use "prime Wentz" fairly, because a quarterback's level changes over a career. Averaging all years treats a 2019 season as if it were 2026. The champion input and the registered challenger C2 handle this crudely (C2 was the one consistent lead). A local-level model lets true talent move from game to game and lets the data say how fast.

## Model

For each quarterback, true EPA-per-dropback talent `theta` follows a random walk between games: `theta_g = theta_(g-1) + w`, `w ~ Normal(0, q)`. Each game's observed mean EPA over `n` dropbacks is `Normal(theta_g, s2 / n)`, `s2` the league variance of EPA per dropback. The start is the early-career prior mean of `homewin_deep` with the weight of 250 dropbacks (`QB_N0`), so with `q = 0` the model is exactly the champion's shrunk average. A Kalman filter gives the current talent estimate and its uncertainty; `q = 0` is the champion.

## `q` is chosen once, without the test period

Grid fixed now (standard deviation of the talent change per game, in EPA per dropback): 0, 0.005, 0.01, 0.02, 0.04. The value with the best predictive log-likelihood of next-game EPA on **2003 to 2015** games is kept. It is not revisited.

## Validation (before it is used on any claim)

- Test period **2016 to 2025**, walk-forward: each game is predicted from the filter state before it. Compare with `q = 0` (the champion) and with the C2 recency weighting (half-life one season, prior 250).
- Metric: dropback-weighted squared error of next-game EPA per dropback, and predictive log-likelihood. Paired difference, game-cluster bootstrap, 2,000 draws, seed 20261110.
- **Passes** only if the squared error delta against `q = 0` has a 95% interval upper bound below 0 and log-likelihood is higher. If it fails, the model is not used to judge Wentz or Murray, and that is reported.
- Also report the chosen `q`, and the same comparison restricted to quarterbacks with a gap of 10 or more games or a team change since their previous game.

## The Wentz and Murray reading

Only if validation passes: the filtered talent of each quarterback as of now (end of Week 9, 2026), with a posterior difference (Wentz minus Murray), its 80% interval and the probability that Wentz is higher, plus a per-season table of each quarterback's filtered talent so the path (2022 to 2026) is visible. Raw EPA only (the long history needed to fit `q` has no opponent adjustment); the opponent-adjusted check in `docs/GUT_PROTOCOL.md` stays separate. Verdict words follow the gut protocol: 0.90 and above "supported", 0.10 and below "contradicted", otherwise "not distinguishable".

## Not allowed

Changing the grid, the test period or the metric after seeing a result, or fitting `q` for Wentz or Murray on their own games.

## What it cannot show

It uses only EPA from games played. It does not know about age, injuries, a new offense or a new supporting cast beyond what shows up in results, and it cannot say how Wentz will do against Buffalo tonight.

## Results (run 2026-11-09, `scripts/qb_drift.py`, numbers in `docs/qb_drift_results.json`)

Fit period 2003 to 2015, predictive log-likelihood of next-game EPA per dropback (higher is better): q = 0: -4,023; 0.005: -4,124; 0.01: -4,279; 0.02: -4,514; 0.04: -4,864. The best value is **q = 0, no drift**, which is the champion's static shrunk average. Validation requires q above 0, so **it fails and the model is not used.** A bug in my output code (a call that only works on tables) crashed the first run after the fit step; it was fixed and the run repeated with no change to any rule or number.

Test period 2016 to 2025 (6,499 quarterback-games), dropback-weighted squared error of next-game EPA per dropback: q = 0 0.10786, C2 recency weighting 0.10784. The difference is 0.00002 with a 95% interval of -0.0007 to +0.0007. Games after a long gap or a team change (465): identical, since q = 0.

- This also takes the shine off C2 from `docs/QB_LEVER_PREREG.md`. Its small margin gain there does not show up here at the quarterback-game level, so I treat it as noise.
- Reading: at the game level, a quarterback's EPA per dropback is so noisy (standard deviation about 1.6 per dropback) that a changing talent level cannot be detected, and allowing it makes predictions worse. That does not prove talent is constant; it says this data cannot see the change.
- Wentz versus Murray, filtered talent as of now, shown for completeness and **not used** (validation failed): Wentz +0.020 (sd 0.025), Murray +0.043 (sd 0.026), difference -0.023 (80% interval -0.069 to +0.023), probability Wentz higher 0.26. This is the same static average as before, not new evidence.
