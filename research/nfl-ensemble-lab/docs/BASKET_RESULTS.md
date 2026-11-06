# Quarterback line against the receiver basket: results

Run 2026-11-06 against docs/BASKET_PREREG.md (commit ef2f8cab) and its Amendment 1 (044e8a85). Football only. No staking or bet sizing.

## Result

No edge found. The test of whether the gap predicts which leg is wrong could not be read: the sample is too small. The test of whether the market closes the gap could be read, and it found that it does. The receiver lines move toward the quarterback line, and the quarterback line stays put.

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

- Receiver lines lag the quarterback line. An early gap predicts a move toward it, so a receiver line seen early in the week tends to be a worse number than the one that closes. That is a lead about line movement, not a profit.
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
