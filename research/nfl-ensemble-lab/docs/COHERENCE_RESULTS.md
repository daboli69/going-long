# Coherence between the game line and the props: results

Run 2026-11-06 against docs/COHERENCE_PREREG.md (commit 272cbed8) and its two amendments (bb4e1be5, 3de37a9d). Football only. No staking or bet sizing.

## Result

No edge found. Test A (forecasts forced to add up) could not be scored because the sample is too small. Test B (do player ladders trail the game ladders) found no lag of the size we were looking for.

## Test A: making player forecasts add up

The quarterback's passing yards should equal the sum of all his receivers' yards. Our independent forecasts do not always add up, so the plan was to shrink them toward each other using the measured error pattern, then check on 2025 whether that lowers error.

Gate, using only forecast means and counts (no outcome read):

| Group | Power with a planted effect (3% of error variance) | Games for 80% power |
|---|---|---|
| Quarterback | 0.57 | 544 |
| Receivers | 0.77 | 544 |

Both are below the 0.80 requirement, though the slopes were recovered correctly (within 25%). So neither group was scored on 2025, and 2025 is still unseen. It would take about two seasons of games.

For description only, the slopes fitted on 2022 to 2024 have the expected signs: when the quarterback's forecast is above what his receivers add up to, his actual yards tend to come in lower (slope -0.40) and the receivers' higher (slope +0.44). These are in-sample numbers and not a test.

## Test B: do the player ladders trail the game ladders

Using Kalshi's hourly prices, I asked: after a visible move in a team's implied points between 24 and 12 hours before kickoff, does the quarterback or receiver ladder keep moving toward it between 12 and 3 hours? L is that catch-up, in standard units.

Counts: player ladders exist only from 2026. The 2025 candles hold spread and total ladders but no player ladders, so the planned decide stage on 2025 had no games. Amendment 2 changed Test B to a single, unreplicated stage on 2026 weeks 1 to 8: 97 games, 953 player ladders. The minimum detectable L was 0.10 against the 0.15 of interest, so the test could see an effect of the size we cared about.

Result (one-sided 95% interval from a bootstrap by game):

| Measure | Value |
|---|---|
| L | 0.05 |
| Interval | -0.01 to 0.11 |
| Placebo (game-line moves shuffled) | mean 0.001, spread 0.035 |
| Verdict under the registered rule | no lag of the size of interest |

For description only: weeks 1 to 4 gave 0.01 and weeks 5 to 8 gave 0.10. Passing-yards ladders gave 0.15 (188 ladders) and receiving ladders 0.01 (765). The passing figure is the only number near the size of interest, but it was not registered, it is a subset, and it is not evidence. It is a lead to watch as weeks 9 onward arrive.

## What this does and does not show

- It does not show that sportsbook prop lines are slow. We hold no timestamped sportsbook player-prop lines. The 2026 sportsbook file has moneyline, spread and total only.
- It shows Kalshi's own player ladders do not trail Kalshi's game ladders by an amount we can see at this sample size. Thin ladders may be slower to update in ways a 12-to-3 hour window misses.

## Not done

- Price check against Kalshi fees and spreads: no effect to price, and the fee schedule was never readable. Not run.
- CRPS for reconciled forecasts: no stored quantile functions. Test A scored squared error of the mean instead; it was not reached.

## Concerns

- Test B is a single stage, not replicated. A positive result would have been a lead only.
- The ladder medians come from thin hourly quotes. Stale or wide quotes were filtered by a rule written before the run, but some noise remains.
- The weekly record applies slopes fitted on baseline forecasts to the newest weekly run's means, a different model. It is an approximation.
- The lag question for sportsbooks, where the game line is sharper, cannot be tested until prop lines are collected over time.

## Prospective record

`python scripts/coherence_run.py freeze` saved week 9 as `data/coherence/frozen/week_2026_09.json`: 28 team-games with the incoherence, the reconciled quarterback and receiver means, and a hash in `data/coherence/ledger.jsonl` (verified). No scorer exists yet.

## Next

Rerun Test B from week 9 onward with a registered passing-ladder subset. Collect timestamped sportsbook player-prop lines weekly if a free source exists, since that is the only way to ask the original question. Test A needs roughly two seasons of games.

## Addendum 1: the sportsbook version (Test C, Amendments 3 and 4)

Travis asked for the GOING history to be used. The GOING repository holds every committed version of the sportsbook feed from 2026-09-09. I harvested all 201 versions into the lab archive (50 new prop files and 39 new game-market files on top of the 136 already held) with `scripts/going_harvest.py`, read-only, no network.

What the history is: about 1.3 million quotes from 18 books, but only a snapshot twice a day. It is not a tick-by-tick record, and it starts in September 2026, so there is no 2025 sportsbook history. The other large GOING files (signal archive, public tracker) hold model signals and bets built from the same feed, not extra raw quotes, so they add no new line history. I did not open the private scanner journal.

Test C asks the Test B question on sportsbook consensus lines, using whole snapshots at about 40, 24 and 15 hours before kickoff. Two registered fixes happened before any result: the feed's team field is empty for every prop quote (Amendment 4, team taken from the 2026 roster).

Gate: 63 games have three usable game-line snapshots, but only 45 games and 559 player lines (481 receiving, 78 passing) also have three snapshots of a player line with at least three books. The smallest detectable L is 0.17 against the 0.15 of interest (docs/coherence_gate_C.json). That is just short, so by the registered rule Test C is uninformative and L was not read. I made no further change to the gate.

What would fix it: each week adds about 10 to 15 qualifying games. About 20 more games should bring the smallest detectable L under 0.15, so the test can be rerun after week 11 or 12. Rerunning is the same registered procedure, and it should only be done after confirming the gate again, not by loosening the snapshot window.

Concern: a snapshot sees only the quotes alive at that moment. Lines that moved twice between snapshots show only their last value. The test therefore measures changes between snapshots, not every tick.
