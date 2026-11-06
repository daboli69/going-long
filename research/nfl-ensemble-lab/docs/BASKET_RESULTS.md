# Quarterback line against the receiver basket: results

Run 2026-11-06 against docs/BASKET_PREREG.md (commit ef2f8cab) and its Amendment 1 (044e8a85). Football only. No staking or bet sizing.

## Result

No edge found. The test of whether the gap predicts which leg is wrong could not be read: the sample is too small. The registered closing test found the gap closing at about a third per interval, but Addendum 1 shows most of that was an artifact of receivers appearing and disappearing between snapshots. Read the addendum before using any number in this document about the gap closing.

## Data

14,095 book-snapshot-game combinations with a quarterback line and at least two receiver lines, 18 books, 132 games with usable pairs of snapshots, weeks 1 to 9 of 2026. In the box scores, a team's quarterback passing yards equal its receivers' receiving yards in 95.9% of 244 team-games (average difference 0.69 yards), so the identity is sound.

Fitted on the decide weeks (1 to 4): odds-adjustment scale 0.35 for the quarterback and 1.20 for receivers (receiver yards are very noisy against their lines); share of passing yards to receivers without a line: 56%, 31%, 30%, 14% for 2, 3, 4 and 5 or more listed receivers.

## Power gate (before any outcome was read)

- Outcome test, confirm weeks 5 to 8: 101 team-games across 56 games. Power to detect that a quarter of the gap is one leg's error: 12% for the quarterback leg and 7% for the receiver leg. Not informative, not read. About 1,000 to 2,000 team-games would give 80% power, roughly ten to twenty times as many, which is about two seasons at this rate.
- Closing test: smallest detectable closing share 0.06 against the 0.15 of interest. Informative.

## Closing test (all weeks, outcome-free)

Between consecutive snapshots of the same book, 6 to 30 hours apart (13,811 pairs, 132 games):

| Measure | Value |
|---|---|
| Share of the gap closed per interval (kappa) | 0.32 (one-sided 90% interval 0.29 to 0.36) |
| Verdict under the registered rule | the gap closes |
| Which leg moves: receiver basket | +0.87 (0.70 to 1.07) per unit of gap |
| Which leg moves: quarterback line | -0.006 (-0.013 to 0.000) |
| Placebo (gaps shuffled within week) | 0.003, spread 0.007 |

All 14 books with at least 15 games show the gap closing, from 0.17 at bet365 to 0.64 at Novig (Pinnacle 0.55, FanDuel 0.25, DraftKings 0.25, Fanatics 0.20). The sharper books close more of it. The average absolute gap is 16% of the quarterback line.

Sensitivity, descriptive and not registered: with no odds adjustment at all kappa is 0.37 and the basket still does the moving; with half the adjustment scale it is 0.33. So the result does not come from the juice adjustment.

## Kalshi referee (descriptive)

182 team-games. In the 91 with a large book gap, Kalshi's quarterback median sat nearer the book's quarterback leg than the basket-implied value in every case. Kalshi agrees with the quarterback line, which supports reading the receiver legs as the ones that correct.

## What this does and does not show

- (Corrected in Addendum 1.) The registered closing test suggested receiver lines lag the quarterback line. With receiver sets matched across snapshots the effect is about a tenth as large and the later value test finds nothing.
- It does not show a bet wins. The outcome test, the one that would show which side is right in money terms, was not powered. The cost check was not run because nothing passed the outcome test.
- A large part of the 16% average gap is probably measurement: the share of passing yards to unlisted receivers is a rough estimate, and stale quotes in one leg look like a gap.

## Concerns

- Stale quotes create a gap that is not a mispricing and also create reversion. The test cannot separate a stale line from a wrong one.
- Receiver errors are very large against their lines (scale 1.2), which makes any receiver-based number noisy.
- Snapshots are twice a day and begin Sep 9, so there is no earlier season, and lines that moved between snapshots are invisible.
- The decide-stage fits use book-level rows that are not independent.
- Lines are posted numbers, not executable prices.

## Prospective record

`python scripts/basket_run.py freeze` saved week 9 as `data/basket/frozen/week_2026_09.json`: 235 book-team rows in 14 unplayed games, hash in `data/basket/ledger.jsonl`. No scorer exists yet.

## Next

Keep saving weekly. The closing share can be rechecked as games accumulate. The outcome test needs about two seasons, so it will be underpowered this year.

## Addendum 1: value of the early receiver line (Amendment 2) and a correction

Registered in e5ef6cc1 before any value was computed. The question: if a bettor had taken the early receiver price on the side the gap pointed to, would the close have been better by more than the vig?

Gate: 3,748 bets in 103 games, smallest detectable mean net value 0.007 against the 0.02 of interest. Informative.

| Measure | Value |
|---|---|
| Mean net value (closing win probability minus the early odds' break-even) | -0.046 (one-sided 95% lower end -0.050) |
| Mean gross value (closing win probability minus 0.5, no vig) | +0.0035 (lower end 0.0001) |
| Placebo, gaps shuffled within week, gross | +0.0037 (spread 0.0003) |
| Placebo, side flipped, gross | -0.0035 |
| Passes the registered rule | no |

The net value is negative for every book (from -0.027 at DraftKings to -0.116 at Novig). The tiny positive gross value is matched by the shuffled-gap placebo, so the gap does not tell us which way an individual receiver line will move. The early price is worse than the close by about the vig.

The correction: the registered closing test measured the basket as the sum of whichever receivers were listed at each snapshot. When a receiver is added or dropped between snapshots the sum jumps for reasons that have nothing to do with repricing. I checked this afterwards (post hoc, `scripts/basket_matched_check.py`): keeping only pairs where the same quarterback and the same receivers are listed at both snapshots (9,243 of 13,322 pairs), the gap closes by about 4% per interval (interval about 2.7% to 6.2%), not 32%, the quarterback line moves -0.011 and the basket +0.061. So the earlier statement that receiver lines lag the quarterback line, and the memory note that said so, were mostly an artifact of the changing receiver list. A small real closing effect may remain, but it is far too small to cover a vig. The registered result stands as registered; this corrects how it should be read.

Lesson for the next test: match the set of legs across snapshots before measuring any movement.
