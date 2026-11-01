# In-game tracker v2: pre-registration

Written on 1 November 2026, before any v2 model was fitted or scored. The git commit that holds this file is the timestamp.

## What is being tested

Version 1 (the tracker in `lab/ingame.py` as committed on 1 November 2026) against version 2, which changes three things:

1. **Pregame baseline.** Built from player-level history across teams, using snap counts and participation, and leaving out games a player was inactive for. Version 1 used the last eight games of the player's current team with zeros for missed games.
2. **Share update.** The prior strength and the calibration of the pregame share are fitted by a hierarchical Bayesian model in PyMC (partial pooling by position), instead of a grid search.
3. **Win chance.** A gradient-boosted game-state model (score difference, time left, down, distance, field position, timeouts, home or away, pregame spread), calibrated with isotonic regression, instead of the Brownian-motion model.

## Data split

- Fit: seasons 2018 to 2023.
- Validation, used for design choices and the isotonic calibration: season 2024.
- Test: season 2025 and 2026 weeks 1 to 8, regular season. No parameter, feature or design choice may change after the test is run. The test seasons were also used to score version 1, so the test is not new to version 1's authors. Version 2 is built using seasons up to 2024 only.
- Prospective, exploratory only: every game from week 8 of 2026 on whose pregame projection was frozen before kickoff. Too few games to support a claim.

## Primary comparisons and the rule for "beats"

Each player stat is paused at 10, 20, 30, 40 and 50 minutes. Each game is paused at the same times.

- **Players.** Score is CRPS of the final stat for passing, rushing and receiving yards. Version 2 beats a comparator if the mean of (comparator CRPS minus version 2 CRPS), over all checkpoints, has a 95% block-bootstrap interval (resampling whole games) that is above zero, and the Diebold-Mariano test on per-game mean differences gives p below 0.05 after a Holm correction across the three stats.
- **Game.** Score is the Brier score of the home win. Version 2 beats a comparator under the same two conditions across all checkpoints.
- **Comparators.** For players: version 1, and the frozen pregame number. For the game: version 1's Brownian model, nflfastR's in-game win probability, and the frozen pregame margin.
- **Secondary, reported, not used for the rule.** Log score, reliability curves, results at each checkpoint, and the Diebold-Mariano test at each checkpoint.

If version 2 fails the rule against version 1 on a stat or on the game, version 1 stays the live default for it, and the result is reported as a failure to improve.

## Not available

- **Sportsbook in-game prices.** No free source exists, so they are not compared.
- **Routes run.** No free source gives routes. Pass snaps (pass plays a player was on the field for) stand in, and this is stated wherever it matters.
- **ESPN and Kalshi in-game prices** exist only for games recorded since 1 November 2026. They are scored on that small set and no claim is made from it.
- **Official inactive lists for past seasons.** nflverse snap counts show who did not play. For history, a tracked player with no offensive snaps in a game is treated as inactive for that game. The live tracker uses the posted list.

## Reconciliation

After each slate, every figure from the live feed is compared with the nflverse play-by-play for the same game once it is published, and mismatches are listed in `docs/ingame_replay.json`.

## Amendment 1 (1 November 2026, before the test was run)

- **Rows compared.** The player comparison with version 1 uses only player-games that both versions track and in which the player played at least one offensive snap. Version 2 cannot see a player who sat out, and version 1 counts him as a zero, so including those rows would reward version 2 for information the live tracker only has once the inactive list posts. A secondary table repeats the comparison on every row version 1 tracks, labelled as such.
- **Participation data.** nflverse participation files end in 2025, so 2026 weeks have none. Version 2 uses snap counts (which cover 2026) for the baseline. Participation is not used.
- **Efficiency shrinkage** stays a fitted constant chosen by grid search, as in version 1. Only the share update is fitted in PyMC.
- **Draws and seeds.** 400 posterior draws, 2 chains, seed 0; 300 forecast draws per player-state with a seed derived from game, player and checkpoint, identical for both versions.
