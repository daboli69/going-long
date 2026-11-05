# Tails: results

Rule and pass bar: `docs/TAILS_PREREG.md` (committed before any result, hash in `docs/tails_prereg_ledger.jsonl`). Raw numbers: `docs/tails_results.json`. Run: `python scripts/tails_run.py`. Weekly record: `python scripts/tails_freeze.py` (save before kickoff) and `python scripts/tails_freeze.py score`. Screen: the Tails tab.

## Verdict
No mispricing found. No test passed. In games flagged as uncertain, margins were not fatter-tailed than the line's own spread implies. They were thinner in both periods.

| Flag | 14+ from line, 2006 to 2019 (ratio to priced) | 14+ from line, 2020 to 2026 | 21+, 2006 to 2019 | 21+, 2020 to 2026 |
| --- | --- | --- | --- | --- |
| Quarterback change or new starter | 0.89 | 0.83 | 0.94 | 0.82 |
| Model far from the line | 0.92 | 0.81 | 0.99 | 0.77 |
| Either | 0.93 | 0.81 | 0.98 | 0.79 |

All corrected p-values are 1.0 on the one-sided test. A ratio below one also appears because the spread of margins around the line fell from 13.45 (2006 to 2019) to 12.63 (2020 to 2026), so the priced rate fitted on the earlier seasons is too high for the later ones. That is an era drift, not evidence that flagged games are safer.

## Counts and reconciliation
7,088 games with a result and closing spread (1999 to 2026), 5,186 with a moneyline, 1,622 with opening and closing lines (2016 to 2021). Kalshi history starts 2026-10-30 with a handful of ladder files, too few to price tails. Margin minus line has a standard deviation of 13.17 overall, near the published 13.9 for 2006 to 2019 (13.45). Games ending exactly on 3: 15.0%, on 7: 9.1%.

## Power
On the confirmation seasons the smallest tail-rate rise visible at 80% power is 4 to 8 points, 17% to 43% relative. A smaller real effect would be missed.

## Forecast quality (side result)
Home-win Brier 2020 to 2026, 1,736 games: closing line 0.2112, plain rating model 0.2251, rating plus starting quarterback 0.2225. The quarterback term improves the rating model by 0.0026 (95% range 0.0010 to 0.0042), a real gain. Both still trail the closing line by 0.011 to 0.014.

## Range models
Quantile regression for the 5% and 95% margin against the line: 90% coverage 92.1% on 2020 to 2026, with no flag showing a coverage failure (Kupiec p 0.26 to 0.65). Pinball loss is no better than a constant range (difference 0.002, range -0.009 to 0.013). A Student-t fit gives about 24 degrees of freedom for flagged games, essentially a normal curve. PIT deciles for flagged confirmation games are roughly flat.

## Favorite-longshot
Underdogs priced under 15% won 10.1% (implied 11.9%) in 2006 to 2019 and 7.1% (implied 12.3%, 85 games, range 3% to 15%) in 2020 to 2026. Other bins match their price. Long shots did not pay more than priced.

## Concerns
- Era drift: the 2006 to 2019 fit overstates later tails.
- No injury count and no historical Kalshi ladders, so those inputs were not tested.
- Saved week 9 before the first kickoff on 2026-11-05; the starter is the depth-chart starter that day.
- A non-pass does not prove tails are never mispriced.


## Addendum: Amendment 1 checks (2026-11-05)

Raw numbers: `docs/tails_deep_results.json`. Run: `python scripts/tails_deep_run.py`. Rule: Amendment 1 in `docs/TAILS_PREREG.md`, committed before these ran.

**Same-season control.** Comparing flagged games with unflagged games in the same season removes the era drift. Ratios of flagged to same-season unflagged tail rate, 2020 to 2026: 0.84 to 1.13 across 12 tests, against 0.77 to 0.83 with the old fitted curve for 14 and 21 points. 2006 to 2019: 0.94 to 1.05. Corrected p-values are 0.28 to 1.0, and none of the 12 tests passed. The highest was the quarterback flag at 10+ points in 2020 to 2026 (ratio 1.13, 98th percentile of random flags, corrected p 0.28), which did not clear the bar in 2006 to 2019. Rung 3 is reported only: 80% to 83% of games land 3+ points from the line, with ratios 0.98 to 1.03.

**Placebo.** Real values sit between the 17th and 98th percentile of 10,000 random same-size flags. None reaches the 95th percentile in both periods.

**Positive control.** The natural test, margins widening with the total line, was not found (ratios 0.87 to 0.92 in 2020 to 2026, 1.02 to 1.11 in 2006 to 2019; none significant), so it says nothing about the method either way. The injected test does: widening flagged margins by 10% is detected 56.5% of the time, by 20% 97%, by 30% 100%. The method has power at 20%, so a null rules out widening of about 20% or more in flagged games and does not rule out smaller effects.

**Dose-response.** The continuous score has an odds ratio per standard deviation of 0.98 (2006 to 2019) and 1.01 (2020 to 2026) for margins 14+ from the line, and 0.94 in both periods for totals 10+ from the total line. Corrected p 0.81 to 1.0. No link.

**Rawest sources.**
- Starting quarterback from raw play-by-play matches `games.csv` in 99.1% of 13,276 team-games; the rerun uses the play-by-play starter.
- Raw sbr HTML: 1,610 games parsed, 1,481 matched to `games.csv` by date and final score. Closing spread identical in 877 and within one point in 1,417; total identical in 816 and within one point in 1,460. The gap is a different book and timing, not a parsing error (median difference 0).
- Kalshi: settled spread markets, 8,623 in 350 historical events (close times 2025-08-21 to 2026-08-30) plus 3,298 in 136 current events; settled total markets 6,857 historical plus 2,449 current. These are market rungs as the public endpoint returns them. They are described, not used, and past order books or trade prices were not pulled.

**Verdict.** Nothing passed. The tab still says no mispricing found. Kalshi's settled ladder history is the largest untouched source; a test against actual alt-line prices would need a new pre-registration.


## Addendum: Amendment 2, Kalshi ladders (2026-11-05)

Raw numbers: `docs/tails_ladder_results.json`. Run: `python scripts/tails_ladder_fetch.py`, then `python scripts/tails_ladder_run.py`. Rule: Amendment 2 in `docs/TAILS_PREREG.md`, committed before any ladder was fitted.

**Counted.** Spread: 271 games in 2025 (5,619 rungs) and 121 in 2026 (3,274 rungs; 107 settled so far). Total: 271 and 121 games (4,480 and 2,426 rungs; 106 settled in 2026). Kickoffs run from 2025-09-05 to 2026-11-03, and nothing earlier exists. Every one of the 15,177 settled rungs has candlesticks. The trade tape was pulled for the six rungs per ladder nearest 0.5: 4,536 markets, 1,138,046 prints. Tape against candle mids at 1 hour before kickoff: median difference 0.5 cents, 90th percentile 1.5 cents (4,408 compared). Order books: 14 dense files and 1 prop file from 2026-10-30 to 2026-11-01, all game-winner or prop books; spread and total ladder books are archived from the weekly save forward.

**Audit.** Kalshi's settled yes or no disagreed with the nflverse final score on 3 of 15,177 rungs (3 games dropped). 738 game-horizons had no usable price (mostly the strict liquidity setting at 24 hours) and none were too thin. 3,762 ladders were fitted. 2.0% had a non-monotone price before smoothing. The fitted center sits a median 0.3 to 0.6 points from the closing line.

**Recovery check (before any real fit).** Median error in log scale was under 1% for every true tail weight. Median fitted degrees of freedom: 4.05 for true 4, 7.9 for true 8, 29.1 for true 30. 94% of true-4 ladders were fitted below 10 and 84% of true-30 ladders above 10. Both bars passed, so the width and tail tests ran.

**Results.** Nothing passed in any of the 12 settings.
- *Width* (actual miss over implied miss, 1.00 = as priced): spread 0.91 to 0.97 in 2025 and 0.88 to 0.94 in 2026; total 0.82 to 0.91 in 2025 and 1.00 to 1.09 in 2026. Spread results landed a little closer to the center than the ladder said. Smallest corrected p was 0.05 (total, 24 hours, loose) in 2025 and 1.0 for every setting in 2026.
- *Tails*: the share of games in the outer 10% of the fitted curve was 6% to 9% in 2025 and 4% to 9% in 2026 (nominal 10%); in the outer 2%, 0% to 3.3% and mostly under 2% (nominal 2%). Tails were not heavier than priced. Fitted degrees of freedom: median 4 to 9 for spreads and 5 to 22 for totals. PIT uniformity: KS p 0.13 to 0.99 in every setting except total, 24 hours, strict liquidity, 2026 (30 games, p 0.03).
- *Center*: the ladder's center was between 0.25 points closer and 0.15 points farther from the result than the closing line's (0.25 closer only in the 33-game strict 24-hour total setting), so the ladder did not add information beyond the line.

**Power.** For 2025 the smallest detectable width error was 12% to 14% (loose liquidity) and the smallest detectable outer-10% excess 4.5 to 5 points. For 2026, with 107 games, they were 19% to 20% and 5 to 8 points, and none of the 12 settings reached the 15% and 5-point sizes fixed in advance. The 2026 confirmation is therefore uninformative at those sizes. 2026 will gain games each week.

**Verdict.** No mispricing found. The ladders priced width and tails about right, or slightly wide, but the confirmation sample is too small to rule out a 15% error.
