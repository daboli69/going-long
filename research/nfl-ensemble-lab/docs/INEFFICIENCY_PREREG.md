# Which football markets are most inefficient, net of cost: pre-registration

Written 2026-11-06, committed before any calibration number or gap is computed. Football only. No staking and no bet sizing anywhere in this document.

## Question

Across the markets we have data for, which are the most inefficient, measured net of what it costs to trade them, and how sure can we be about the ranking? Ranking many markets and reporting the best raw gap would mostly report luck, so the ranking uses shrunken estimates and corrects for having looked at all of them.

## 1. Structural reason

Markets differ in how much attention, capital and information they get. Game lines are heavily traded and should be the tightest. Player props and thin exchange ladders have less capital behind them and many more prices to keep right, so a larger gap is plausible there. The cost of trading also differs: a sportsbook charges a hold on every price, an exchange charges a spread and fees. A gap that is smaller than the cost is not an exploitable inefficiency. This is a reason to look, not evidence. The a priori expectation, given every earlier test in this lab, is that no market beats its cost.

## 2. Inputs: what exists and what does not

| Market | Data | Result source | Price paid | Eras |
|---|---|---|---|---|
| Game spread | aussportsbetting close line and close odds on both sides, 2006 to 2025 | scores | the quoted odds of the side taken | decide 2006-2015, confirm 2016-2025 |
| Game total | close total and close over and under odds | scores | quoted odds | same |
| Moneyline | close home and away odds | scores | quoted odds | same |
| Sportsbook QB passing yards | GOING feed, final pre-kickoff quote per book and prop, 18 books, pick'em sites excluded | play-by-play | quoted odds | decide weeks 1-4, confirm weeks 5-8 of 2026 |
| Sportsbook receiving yards | same | play-by-play | quoted odds | same |
| Kalshi spread, total | `data/cache/props_kalshi/quotes.parquet`, bid and ask at kickoff minus 90 minutes | settled result | ask for yes, one minus bid for no | decide 2025, confirm 2026 |
| Kalshi passing yards, receiving yards, receptions, rushing yards | same file | settled result | same | same |

Not testable, and left that way:
- Kalshi game winner: only a mid price is stored, no bid and ask at a fixed time, so a cost cannot be computed.
- Any sportsbook market before 2026-09-09 other than the three game markets.
- Touchdown, first-touchdown and team-total markets: no settled price history with a cost in the stored data.
- Fees on Kalshi: the fee schedule could not be fetched, so Kalshi results are before fees and flatter Kalshi.
- Limits and bet-size caps for any sportsbook: not in the data.

## 3. Fixed in advance

**Contract.** One binary question at one posted price: home covers, over, a player passes a threshold. Pushes are dropped. The cluster for all resampling is the game.

**Fair probability.** Power-method de-vig of the two sides for sportsbook markets; for Kalshi, the mid of the quoted bid and ask. Prices are the cost to buy each side: American odds converted to implied probability for sportsbooks, ask for yes and one minus bid for no on Kalshi. Kalshi contracts need both a bid and an ask, ask minus bid at most 0.10, and the lab's own `liquidC` flag; others are descriptive.

**Rule (primary).** Recalibration of each market's fair probability by logistic regression of the outcome on logit(fair probability), giving intercept b and slope a, fitted on that market's decide era only. The coefficients are shrunk toward the pooled fit of all markets' decide data with a normal prior of standard deviation 0.2 on each coefficient, so thin markets lean on the pool. A contract is bought on the side whose recalibrated probability exceeds the price paid; if neither does, no bet. The sides are chosen without any confirm-era outcome.

**Net gap.** On the confirm era, the mean over bets of (outcome of the side taken minus price paid), averaged within game first. This already includes the market's hold, spread and rounding. The 95% interval is a bootstrap by game (2000 draws). A market with fewer than 100 bets in the confirm era is reported as "rule rarely fires" and its gap as unread.

**Murphy decomposition.** For every market, on all eras together and descriptive: log loss of the fair probability split into uncertainty, resolution and reliability (calibration error) over ten equal-count bins. Reliability is the part that is miscalibration; resolution is how much the price separates outcomes.

**Cost of trading.** Per market: average hold (sportsbook) or average spread (Kalshi), and the mean net of buying every contract on both sides at its price. No result is needed for this number.

**Ranking.** Empirical-Bayes shrinkage (DerSimonian-Laird between-market variance) of the confirm net gaps, normal-normal, gives a shrunken estimate and interval per market. The ranking is by shrunken estimate. Multiplicity is handled by Romano-Wolf stepdown on one-sided bootstrap statistics across all markets read, with Benjamini-Hochberg on the one-sided bootstrap p-values as a second view. The best raw gap is not the headline.

**Liquidity and limits.** From the data only: Kalshi 24-hour volume and the stored trade tape (`data/cache/props_kalshi/trades`: fills per contract and fill size), and for sportsbooks the number of books quoting. Sportsbook limits are not in the data and are listed as unknown.

## 4. Gate, before any real outcome is read

Planted gap: for each market, take the confirm-era contracts and the sides the rule picks (no confirm outcome is used), and simulate outcomes so that the side taken wins with probability price plus 0.03, which is a net edge of exactly +0.03. Run the full estimate 200 times.
- Recovery: mean estimated net within 0.01 of +0.03.
- Power: share of runs whose one-sided 95% bound is above 0 must be at least 0.80.
- Also report the smallest detectable net gap: 2.8 times the bootstrap standard error.
A market that fails either is "not testable" and its confirm result is not read, and it does not enter the ranking.

## 5. Lead-lag, early against close

- Sportsbook against Kalshi: the registered test in `docs/TAILS_PREREG.md` Amendment 3 (`docs/leadlag_results.json`) was run on hourly Kalshi candles and book quotes. It is cited, not rerun, because the raw quotes are the same ones.
- Early against close: the 20-year open-to-close tests in `docs/LINEMOVE_RESULTS.md`, cited, not rerun.
- Fills: for Kalshi contracts with a trade tape, the share of fills that occurred inside the stored bid and ask (`trades_check.parquet`), as a descriptive check that the stored quotes are executable.

## 6. Replication

The three game markets are the 20-year set, so the decide and confirm split is the replication. In addition the confirm era is reported in two halves (2016-2020 and 2021-2025), descriptive. Props are prospective: each week a write-once hashed file under `data/inefficiency/` records every contract, its price, its recalibrated probability and the side the rule would take, for unplayed games. Nothing is backfilled. A scorer is added later.

## 7. Report order and rule

Completed, Model Research, Concerns, Next, Needs Travis. If no market beats its cost after the multiplicity correction, the result is "no market shown to be inefficient net of cost", with the table of what was and was not testable. Nothing in the app changes on this result.

## Amendment 1 (2026-11-06, committed before any gap or calibration number is computed)

Implementation details left open in sections 3 and 4. None depends on a result.
- Side A is the home side for spread and moneyline, over for totals and sportsbook props, yes for Kalshi. The fair probability is for side A.
- Sportsbook game lines use decimal close odds, so the price of a side is one over its odds. Spread uses the Home and Away Line Odds Close columns, total the Over and Under Close columns, moneyline the Home and Away Odds Close columns. Ties and pushes are dropped.
- Sportsbook props: one contract per book, game, player and stat, using the book's last pre-kickoff quote. A player with no yards in the play-by-play counts as zero only if the 2026 weekly roster lists the player as ACT that week; otherwise the contract is dropped, because the book would likely void it. Games count as final when play-by-play reaches zero seconds.
- The pooled calibration used as the prior centre is a logistic fit of the outcome on logit(fair probability) over all markets' decide data, each market weighted equally. The prior standard deviation is 0.2 on the slope and on the intercept, applied around the pooled coefficients.
- Kalshi contracts use bid90 and ask90 (kickoff minus 90 minutes), mid as the fair probability. Ties between sides are not an issue.
- Net gap is the mean over games of the within-game mean net; the bootstrap resamples games. Markets drawn from one source share the same resampled games (the three game-line markets; the six Kalshi series). The sportsbook-prop and Kalshi samples are resampled independently of each other and of the game lines, which ignores their overlap in 2026 games.
- The gate uses a cluster-robust normal standard error of the mean over games for its 200 simulated runs, not a bootstrap, for speed. The real run uses the bootstrap.
- Murphy bins are ten equal-count bins of the fair probability. Terms are in nats of log loss.
- The between-market variance for shrinkage is the DerSimonian-Laird estimate, truncated at zero, using the bootstrap standard errors.
- The size used in the gate is a net edge of 0.03.

## Amendment 2 (2026-11-06, a defect found after the first run, committed before the rerun)

The first run read the k_receptions confirm result (net -0.022, interval -0.054 to +0.011) and no other market. After it, the descriptive table showed an infinite overround for the game-total market. Cause: one 2006-2015 total row has a zero over odds, which makes a price of infinity and a NaN fair probability. A single NaN made the pooled calibration fit return its starting values (slope 1, intercept 0) without fitting, so the "pooled" prior centre was not a pooled fit, and the game-total market's own fit was also unfitted.
Fix, which uses no outcome: drop any contract whose price is not finite or whose decimal odds are at or below 1, and make the fit stop with an error on non-finite input instead of returning a start value. The gate and the run are repeated in full on the corrected data. The first-run files are kept as `*_run1_superseded.json`. The rerun reads confirm results for whatever markets pass the repeated gate, which means the k_receptions confirm result is read a second time; this is disclosed in the results. No other rule changes.

### Correction to Amendment 2 (2026-11-06, written after the repeated gate)

The cause stated above was wrong. The zero-odds row is a 2025-09-28 game, which is in the confirm era, so it never entered any decide-era fit. The pooled prior and every market's fit were unaffected: the repeated gate matches the first gate in every field except one game-total confirm count (2,596 became 2,595), and the fitted coefficients are the same. The row only produced an infinite value in the descriptive overround table. The cleaning rule and the non-finite-input error stay in place as harmless safeguards. The repeated run reads the same k_receptions confirm result a second time.
