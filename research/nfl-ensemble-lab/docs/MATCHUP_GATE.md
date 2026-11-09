# Matchup features against the closing line: gate result, 2012 to 2025

Rule: `docs/MATCHUP_PREREG.md` with Amendments 1 and 2. Code: `lab/matchup.py`, `scripts/matchup_run.py gate` and `diagnostic`. Raw numbers: `docs/matchup_gate.json`, `docs/matchup_gate_diagnostic.json`. The first gate on 2022 to 2025 is kept in the files with the suffix `_2022_2025`. No challenger-minus-champion result was computed or read.

## Verdict

Neither hypothesis is testable on the available history, so no outcome comparison will be read. With 3,649 games over 14 test seasons, the planted-effect check fired the pass rule in 29.5% of runs for H1 (efficiency) and 33.0% for H2 (turnovers), against the 80% required. Amendment 2 said there would be no third window change, and there is none.

## Numbers

| | H1 efficiency | H2 turnovers |
|---|---|---|
| Games scored, 2012 to 2025 | 3,649 | 3,649 |
| Smallest detectable effect from the placebo (2.8 x spread) | 0.0011 | 0.0006 |
| Planted gain 0.004: gain recovered | 0.0032 | 0.0034 |
| Planted gain 0.004: pass rule fires | 29.5% | 33.0% |
| Planted gain 0.008: pass rule fires (descriptive) | 80.5% | 76.5% |
| Testable | no | no |

First gate for comparison (2022 to 2025, 1,084 games): 24% and 27% at 0.004, 46.5% and 54.5% at 0.008. The longer window helped, mostly at the larger gain.

## What binds now

At a planted gain of 0.004, three conditions of the pass rule fail often (`docs/matchup_gate_diagnostic.json`, H1 / H2): the interval below zero holds in 60.5% / 56.5% of runs, the 11-of-14-seasons-better condition in 44% / 38.5%, and the 0.002 minimum gain in 75.5% / 79%. Brier no worse holds in 97.5% / 100%. The seasons condition is the strictest part of the rule: each season has only about 270 games, and a true gain of 0.004 is too small to show up in the same direction in 11 of 14 single seasons.

The pass rule can reliably catch a gain of about 0.008 log loss, twice the registered size. An improvement that large over a closing line would be a very big result, so the rule as registered is sensitive only to effects well above what I expect.

## Disclosed limits

- Moneyline coverage is complete from 2010 and partial before (2007 has 255 of 256 games, 2008 has 185, 2009 has 242). Games missing a moneyline are dropped.
- Early test seasons train on few seasons (2012 trains on five).
- The planted signal uses only the first feature of each hypothesis, so the H1 power for its two-feature fit may be a little overstated.
- The placebo spread understates the real sampling spread, because shuffled features are shrunk to about zero. The planted-effect check is the binding one.

## Next

The prospective record is the remaining route. From Week 10, a write-once hashed file under `data/matchup/` would record each week's features and both challenger probabilities before kickoff, and be read after 60 or more games. At about 270 games a season that is a descriptive check, not a test of a 0.004 gain. Any new registered rule with a looser seasons condition would be a new pre-registration, made knowing this result, and should be reported as such.
