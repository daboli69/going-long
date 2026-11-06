# Sportsbooks as noisy sensors of one hidden line: pre-registration

Written 2026-11-06, committed before any fused line was computed. Football only. No staking and no bet sizing anywhere in this document.

## Question

If the sportsbooks are treated as noisy sensors of one hidden line, can a method that learns each book's bias, noise and staleness without looking at results produce a better line than the median and the closing line? And does any book's gap to that fused line predict its own next move, or the result, by more than the vig?

## 1. Structural reason

Books quote different numbers for the same prop. Reasons that differ by book: how often they refresh (staleness), whether they shade toward public sides (bias), and how much they trust their own number against the market (noise). A sharp book or an exchange has a stronger reason to be accurate. A retail book may carry a stale or shaded number for hours. A plain median treats all books alike and cannot tell a stale outlier from a real signal. A weighted average with weights learned from the books' own behavior might be closer to the truth. This is the same problem as combining several noisy instruments in navigation, or several annotators in crowdsourcing.

These are reasons to look, not evidence. The a priori expectation is a small gain at best.

## 2. Inputs: what exists and what does not

Exists:
- The GOING sportsbook feed, 201 committed versions from 2026-09-09, harvested into `data/raw/archive/props`: each book's line, over and under odds (American), its own quote time and an in-play flag, for 18 books. Pick'em sites are excluded by the `dfs` flag.
- Box scores and play-by-play for 2026 (`data/raw/play_by_play_2026.parquet`), used only for the outcome tests.
- Kalshi passing-yards and receiving-yards ladders for the same players as an independent sensor that is not part of the fit.

Missing, and left missing:
- Any history before 2026-09-09.
- Quote times finer than the book's own update stamp, and the true moment a line changed. A quote's age at the snapshot (snapshot time minus its own quote time) is the only staleness measure.
- Executable prices and limits. Lines are posted numbers.
- A time series dense enough to smooth the hidden line across snapshots. Snapshots are twice a day, so the hidden line is estimated separately for each prop and snapshot. Staleness enters through a drift term.

## 3. Fixed in advance

Props: quarterback passing yards and receiving yards, full game, matched to a player id, with a team from the 2026 roster, in games that have a result when scored. A prop at a snapshot needs at least three books. Quotes older than 12 hours at the snapshot are dropped (the same rule as the other tests).

Odds-adjusted line: line + c x line x z, where z is the normal quantile of the fair over probability (power-method de-vig, probability clipped to 0.25 to 0.75), with c = 0.30 for passing yards and 0.70 for receiving yards. These two values are fixed here from general knowledge of yard variability, not from results. The same c gives the predictive scale (c x center) in every scoring below.

Model, on the log of each odds-adjusted line: log y(i,b) = log mu(i) + beta(b) + e(i,b), where i is a prop-snapshot, b a book, and e is Student-t with 4 degrees of freedom and variance sigma(b)^2 + q x age(i,b), with age in hours. beta(b) is each book's bias, sigma(b) its noise, q the drift per hour (staleness). The median book's bias is set to zero. Parameters are fitted by expectation-maximization on the decide weeks (1 to 4) of quotes only, no results, and then held fixed. The fused line for any prop-snapshot is the precision-weighted robust mean of the bias-corrected quotes under those parameters.

Benchmarks, all at the final pre-kickoff snapshot:
- Median: the median of the books' odds-adjusted lines.
- Closing line: Pinnacle's odds-adjusted line, on props Pinnacle quotes.
- Bates-Granger combination: weights proportional to 1 / mean squared relative error of each book on the decide weeks (this one uses results, so it is a supervised benchmark).

Stages: decide on weeks 1 to 4, confirm on weeks 5 to 8 (final games only). Week 9 and later are the prospective record.

Scoring, confirm stage: for each prop, each book's posted line is a question "will the result exceed this line". Predicted probability = one minus the normal probability that the result is below that line, with the center under test and scale c x center. Score by log loss, averaged within a prop, then within a game. Differences against the benchmark are tested by Diebold-Mariano and a bootstrap by game (2000 draws), one-sided, Holm across the three comparisons (fused against median, against Bates-Granger, against closing line).

Bet test, confirm stage (uses results): for each book's final quote, standardized gap d = (log y(i,b) minus log fused) / its own scale. Outlier quotes are those with |d| at or above the 75th percentile of |d| on the decide weeks. The bet takes that book's quote against the fused line: under if the book's line is above the fused line, over if below, at that book's own odds for that side. A push is dropped. Win rate is compared with the break-even rate of the odds taken. Mean (win minus break-even), averaged within game first, bootstrap by game, one-sided: passes if the lower end of the 95% interval is above 0.

Reversion test (no results needed), all weeks: for the same book and the same prop in consecutive snapshots 6 to 30 hours apart, regress the book's change in log line on minus its gap to the fused line at the earlier snapshot. The same prop at both snapshots is required, so the set of legs is matched by construction. The slope kappa is the share of the gap the book closes. "Closes" if the lower end of the one-sided 95% interval is above 0.15, "does not close" if the upper end is below 0.15. The same is reported with the median in place of the fused line, descriptive.

## 4. Gate, before any real result is read

Planted sensors: with the real structure (number of books and ages per prop-snapshot), simulate hidden lines, book biases (spread 0.01 in logs), book noises (spread of a factor of 3, centered 0.04) and drift (q such that 12 hours adds 0.035), and outcomes from the hidden line. Run the full fit.
- Recovery: correlation between estimated and planted noise of at least 0.8 across books, and bias error of at most 0.01 (root mean square, in logs).
- Power for the scoring test: share of 200 simulated confirm stages in which fused beats median at one-sided level 0.05/3. Informative only if at least 0.80. Report the number of confirm props for 80% power.
- Bet test: informative only if 2.8 times the bootstrap standard error of the mean net win rate is at most 0.03.
- Reversion test: informative only if 2.8 times the bootstrap standard error of kappa is at most 0.15.
A test that fails its gate is reported as uninformative and not read.

## 5. Checks that are not fit

- Sharp books: a priori sharp set is Pinnacle, Novig and ProphetX (a sharp book and two exchanges), the rest retail. The estimated noise of the sharp set should be lower than the retail set (one-sided Mann-Whitney).
- Kalshi: on props with a Kalshi median at the nearest hour to the final snapshot, the share where the fused line is closer to Kalshi than the median is. Sign test, one-sided.
- Placebo: assign the books' parameters to the wrong books at random (500 times) and rescore the fused-against-median comparison; it should be centered at no gain.

## 6. Cost check

Only for a result that passes. Compare the mean net win rate with each book's own hold. No stake, no sizing.

## 7. Prospective record

Each week, a write-once hashed file under `data/fusion/` with the fused line and each book's standardized gap, for unplayed games from the newest snapshot. Nothing is backfilled. A scorer is added later.

## 8. Report order and rule

Completed, Model Research, Concerns, Next, Needs Travis. If nothing beats the median and the vig, the result is "no edge found". Nothing in the app changes on this result.
