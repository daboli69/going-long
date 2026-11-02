# Snap simulator: pre-registration (2026-11-02)

Written and hashed before the simulator is built or run. First game: 2026_08_CHI_SEA, Monday night, kickoff 8:15 pm Eastern, Seattle -3, total 46.5, Chicago on 11 days rest and Seattle on 8 (from `data/raw/games.csv`). Nothing in this file is a prediction yet. No staking or sizing anywhere.

## What it is

A play-by-play Monte Carlo simulator, 10,000 games per matchup, run as vectors so every game advances one snap at a time together. State per game: score, quarter, clock, down, distance, field position, possession, timeouts. Seed from the game id, so a rerun gives the same numbers. It is independent of the market: nothing in it reads a spread, total or moneyline. Those are used only afterward, to turn simulated scores into cover and over percentages and to judge the simulator.

## Inputs (all free, all from the repo)

- Play-by-play 2026 through the week before the game, and 2025 as a prior, weighted at half. Parameter = (n x observed + m x prior) / (n + m) where the prior is the league value and m is 60 plays for rates and 150 for yardage means, using 2025 plays at half weight inside n.
- FTN 2026 charting for pass rushers and blitzers, play action, motion, screens, no-huddle and box count.
- Per team and situation, estimated from play-by-play: pass rate (down, distance, score margin, time); 4th-down go, kick and punt habits relative to the league in the same situations; run direction and gap mix with yards by gap; sack rate on both sides (the pressure link) and quarterback hits; completion, interception and yards per completion on both sides; fumbles; penalties per snap by type for offense and defense; seconds per snap by play type and result (clock stops on incompletions and out of bounds), pace, the hurry-up when trailing late, and timeouts used.
- Offense and defense factors combine as: offense value + defense value - league value, on the logit scale for rates and as a ratio for yards.
- Not available at $0: coverage shells, man or zone, and route types. They are not modeled. Pressure, blitz rate and box count stand in for the defensive scheme.

## Players

Targets, carries and touchdown opportunities are shared out by each team's 2026 usage blended with 2025, with players the injury report lists as out removed and their shares redistributed. The play-by-play carries the real yards to the real player.

Seattle running backs, per the owner: Zach Charbonnet starts, Jadarian Price is the first-round rookie, Kenneth Walker is gone. Charbonnet has no 2026 carries yet. His base rate is his 2023 to 2025 per-carry yards and role from play-by-play, shrunk to the running-back average. Because he is returning from a knee injury and the files do not show the injury type, his workload and efficiency are scenario draws, labeled as assumptions, not measured: in each simulated game his share of Seattle running-back carries is drawn uniformly from 0.40 to 0.65, Price gets 55% of the remainder and the rest go to the other backs by their 2026 shares, and his per-carry yards are multiplied by a draw from a normal distribution with mean 0.95 and standard deviation 0.07. The report also shows the results with those draws fixed at the low end (share 0.40, multiplier 0.88) and the high end (share 0.65, multiplier 1.02).

## Venue and rest

- Crowd: the false-start rate per offensive snap for visiting offenses at Seattle, 2015 to 2025 (play-by-play `penalty_type` false start), against visiting offenses elsewhere, shrunk toward 1 with an empirical-Bayes variance across stadiums. The multiplier is applied to the visiting offense's false-start rate in the simulator. Its rank among stadiums is reported as measured, not assumed.
- Rest: margin minus the closing spread regressed on home rest minus away rest, 2015 to 2025, rest days capped at 14. The estimate with its 95% interval is reported; the applied value is the point estimate shrunk by its own variance, added to the final margin. If the interval includes zero, the applied value is small and says so.
- Home field: the mean home margin 2015 to 2025 over rating-neutral teams (the mean of result), added to the margin and reported separately. Crowd false starts are in the snaps; the league home margin is a single number added at the end. The overlap is stated.

## Outputs per game

Win percentage for each team; cover percentage for the closing spread (push shown); over percentage for the closing total (push shown); score ranges; each player's simulated distribution for passing yards, completions, receptions, receiving yards, rushing yards, carries and anytime touchdown; the scenario results; the adjustments with their sizes.

## Checks, fixed now

- V1, calibration: sim every 2026 game played through week 8, each using only earlier weeks, 2,000 sims each. Compare mean points per team, plays per team, pass rate, sacks, penalties and fourth-down attempts per team with the actual 2026 means. The simulator is called calibrated if each is within 5% (points within 1.0). Misses are reported, not tuned away silently; any change after seeing V1 gets a dated amendment.
- V2, prediction: weeks 4 to 8, walk-forward, 2,000 sims. Log loss of the simulated home win probability against the devigged closing moneyline, and the Brier score of the cover and over percentages against 0.5. Descriptive only; about 56 games cannot prove an edge.
- V3, prospective: the pre-kickoff output for each game is saved write-once with a hash and scored after the game.

## Leans: sim, matchup and game must all agree

For each player prop with a market line and market chance in the app (Kalshi), a lean exists only if all three point the same way:
1. Sim: the simulated chance of reaching the line differs from the market chance by 5 points or more.
2. Matchup: the opposing defense allows that position's stat at a rate at least 5% above (over) or below (under) the league, shrunk, from 2026 play-by-play.
3. Game: the simulated volume for that stat's category (pass attempts for passing and receiving props, rushing attempts for rushing props) is at least 3% above (over) or below (under) the team's 2026 per-game average.
Leans are logged write-once and hashed, and scored after the game. Earlier work found no edge when this model's prop chances were compared to Kalshi's; the agreement filter is untested and is presented as such.

## Pass rule for the simulator

None is claimed beyond V1: the simulator is "calibrated" or it is not. V2 and the leans carry no claim of an edge until a pre-registered sample says so.

## Amendment 1 (2026-11-02, after the first V1 and V2 run, before using any output)

The first run (600 sims per game, 120 games) failed V1: points per team 21.3 against 22.9 actual (the bar is 1.0), sacks +5.3%, penalties -7.2%, fourth-down tries +10%. A diagnostic against the same plays showed offensive touchdowns, passing yards, rushing yards and snaps matching, and field-goal attempts 18% low with punts 20% high, so the miss traces to the fourth-down choice and to scoring the simulator did not model. Changes, all fixed before the next run and none tuned on the V2 outcomes:
1. The fourth-down kick-or-go model gets nonlinear field-position terms (the square of field position and indicators for inside the 30 and inside the 45), because a straight line in field position cannot separate field-goal range from punt range.
2. Return touchdowns are added with league rates from 2025 and 2026 play-by-play: on interceptions, lost fumbles, punts and kickoffs, the receiving or defending team scores with the league probability.
3. Only false starts take the crowd multiplier; other own-team pre-snap penalties moved to the live class. (A defect found in testing: the multiplier was applying to every pre-snap penalty.)
4. V2 used a wrong moneyline-to-probability formula for favorites in the check script; fixed. This does not touch the simulator.
The V1 bar, seeds and sample sizes are unchanged. Sacks within 5% and penalties within 5% remain pass conditions and are reported even if they fail.
