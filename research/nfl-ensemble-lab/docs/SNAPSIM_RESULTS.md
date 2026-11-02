# Snap simulator: results

Rule and amendment: `docs/SNAPSIM_PREREG.md` (committed before any code, one amendment after the first check). Raw checks: `docs/snapsim_validation.json`. Code: `lab/snapfit.py` (parameters), `lab/snapsim.py` (engine), `lab/snapgame.py` (players, venue, leans, saved records). Run: `python scripts/snapsim_run.py 2026_08_CHI_SEA [--freeze]`. Screen: the Snap sim tab.

## What it does

10,000 games are played one snap at a time as vectors, with each team's own 2026 tendencies (2025 at half weight as a prior): pass and run mix by down, distance, score and time; fourth-down kick-or-go habits; pressure and blitz (FTN charting); run gaps and yards; completion, sack and interception rates for the offense and the defense; penalties by type; seconds per snap by result and game state; and the real players on each roster with their own target, carry, red-zone and efficiency shares. It does not read any betting line. Not modeled, because free data has no coverage shells or route types: man or zone and routes. Pressure, blitz rate and box count stand in.

## Tonight: Chicago at Seattle (2026_08_CHI_SEA)

Saved before kickoff in a write-once hashed file, `data/snapsim/frozen/2026_08_CHI_SEA.json` (hash c2d875ee...). The first saved run, hash 998caec0..., is kept in `data/snapsim/frozen/superseded/` and noted in the ledger: it played Jadarian Price, who the roster file lists on the reserve list for week 8. The rerun excludes anyone not on the active roster..

| | Seattle | Chicago |
| --- | --- | --- |
| Win | 75.2% | 24.8% |
| Cover (schedule file line, Seattle -3.5) | 69.0% | 31.0% |
| Over 46.5 / under | 47.5% / 52.5% (51.7% over when the simulator's scoring shortfall is added back) | |

The schedule file's line moved from 3.0 to 3.5 during the day. The screen has a ladder of nearby lines (spread 2.5 to 4.5, total 45.5 to 47.5), so Seattle -3 and the 46.5 total are there too.

- **Crowd.** Visiting offenses at Seattle false-started on 1.95% of snaps in 2015 to 2025 against 1.61% league-wide: third of 32 stadiums by raw rate, not second. After shrinking for noise the simulator uses 1.09 times the normal false-start rate for Chicago.
- **Rest.** Chicago 11 days, Seattle 8. History (2015 to 2025): 0.015 points per day of rest edge, standard error 0.098. No detectable effect; the applied adjustment is about zero.
- **Home field.** The league's average home margin, 1.7 points, is added to the final margin.
- **Charbonnet and Price.** Price is on the reserve list in the roster file (weeks 7 and 8) and has not carried since week 3, so he does not play in the simulation; his carries go to the other backs. Charbonnet is listed active for week 8 after reserve status in weeks 1 to 6. He has no 2026 carries in the play-by-play, so his role is the scenario in the pre-registration, not a measurement: 40% to 65% of the backs' carries and about 95% of his 2023 to 2025 yards per carry; The rest go to Wilson, Holani and the other backs. Seattle's win chance is 73.7% at the low end and 77.7% at the high end of that range, so the call on him moves the result by about 4 points.
- **Leans where the simulation, the matchup and the game script agree:** one, Caleb Williams passing yards under 225.

## Does the simulator match 2026?

Every 2026 game through week 8 was simulated from only the weeks before it (500 sims each).

| Per team per game | Simulated | Actual | Within the pre-set bar |
| --- | --- | --- | --- |
| Points | 21.9 | 23.0 | No (1.1 low; bar was 1.0) |
| Snaps | 61.5 | 60.4 | Yes |
| Pass rate | 60.5% | 60.4% | Yes |
| Sacks | 2.42 | 2.30 | No (+5.3%) |
| Penalties | 5.77 | 6.22 | No (-7.2%) |
| Fourth-down tries | 1.53 | 1.40 | No (+8.6%) |

Not calibrated by the rule I set. Offensive touchdowns (2.44 against 2.46), passing yards and rushing yards match. The shortfall is fewer field goals (1.70 attempts against 2.08) and more punts (4.17 against 3.42): the simulator's drives stall slightly too often and it kicks too rarely. The first run missed by 1.7 points; return touchdowns and the fourth-down fix recovered about 0.6 (Amendment 1). The totals therefore lean low, and the screen shows the over both unadjusted and with the 1.1-point per-team gap added back, a correction taken from the league's own scoring and not from the market.

Prediction check (weeks 4 to 8, 72 games, descriptive): home win log loss 0.674 for the simulator, 0.641 for the betting market, 0.693 for a coin. Cover Brier 0.262 and over Brier 0.280, both worse than the coin's 0.250. Mean error on the total 11.1 points against 10.4 for the posted line, on margin 9.2 against 8.9. The simulator does not beat the market on these games, and 72 games cannot prove an edge either way.

## Concerns

- The simulator makes Seattle a bigger favorite (about 75% to win) than the market does (about 61%). Given the check above, that gap is more likely the simulator's overconfidence or its scoring bias than information the market missed. The simulator does not include uncertainty about team strength, which makes its percentages too confident.
- It misses the calibration bar on points, sacks, penalties and fourth-down tries. Treat the percentages as a model readout, not a probability you can trust to the point.
- Coverage shells and route types are absent. Run-scheme modeling is limited to gap and direction.
- Overtime is sudden death with any score ending the game, a simplification. Timeouts are not modeled explicitly; the two-minute hurry-up behavior comes from the data.
- The leans rule (sim, matchup, game agree) is written and logged but has no track record. Earlier work found no edge for this model's prop chances against Kalshi.
- Charbonnet's ACL timeline and snap count are an assumption stated by you; the injury files show only a knee report in weeks 6 and 7.
- Seattle's 2026 depth chart is a March snapshot; injuries come from the latest report in the file.

## Where it shows up in the app

- The Snap sim tab, for any game in the week.
- Each game's Simulated game tab, under the play-by-play replay: the 10,000-game percentages, other lines, the Charbonnet scenario, leans and the player table.
- The older replay and player projections in that tab now bring back a starting back who is active this week after weeks on the reserve list. Zach Charbonnet gets 52.5% of Seattle's backs' work at 95% efficiency (the middle of the snap simulator's range, an assumption), taken from the other backs. Jadarian Price stays out while the roster file lists him on the reserve list.
