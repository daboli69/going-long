# Which football markets are most inefficient, net of cost: results

Rule: `docs/INEFFICIENCY_PREREG.md` (committed before any number), Amendments 1 and 2. Code: `lab/inefficiency.py`, `scripts/inefficiency_run.py`. Raw numbers: `docs/inefficiency_gate.json`, `docs/inefficiency_results.json`. No staking or bet sizing anywhere.

## Verdict

No market shown to be inefficient net of cost, and the ranking cannot be made. Of 11 markets, only one (Kalshi receptions) passed the planted-gap gate, so only that one was read, and its net gap was negative. With one market there is nothing to rank or shrink.

## What was and was not testable

The gate plants a net edge of +3 points on the sides the rule would take and asks whether the estimate recovers it and detects it with 80% power. Every market recovered the planted size to within 0.01 (the pipeline works). Power is the problem.

| Market | Years or weeks | Confirm bets | Power at +0.03 | Smallest detectable net gap | Read? |
|---|---|---|---|---|---|
| Kalshi receptions | 2025 / 2026 | 2,355 | 0.82 | 0.033 | yes |
| Kalshi receiving yards | same | 1,973 | 0.78 | 0.036 | no |
| Kalshi rushing yards | same | 1,960 | 0.75 | 0.037 | no |
| Game total | 2006-15 / 2016-25 | 1,355 | 0.68 | 0.039 | no |
| Game moneyline | same | 1,191 | 0.66 | 0.044 | no |
| Sportsbook QB passing yards | 2026 weeks 1-4 / 5-8 | 1,069 | 0.62 | 0.047 | no |
| Kalshi total | 2025 / 2026 | 860 | 0.58 | 0.048 | no |
| Kalshi passing yards | same | 869 | 0.52 | 0.049 | no |
| Game spread | 2006-15 / 2016-25 | 714 | 0.52 | 0.054 | no |
| Kalshi spread | 2025 / 2026 | 347 | 0.24 | 0.093 | no |
| Sportsbook receiving yards | 2026 weeks 1-4 / 5-8 | 90 | 0.13 | 0.172 | no |

Not testable at all: Kalshi game winner (only a mid price is stored, no bid and ask at a fixed time), sportsbook markets before 2026-09-09 other than the three game markets, touchdown and team-total markets, and Kalshi fees (the fee schedule could not be fetched, so every Kalshi number is before fees and flatters Kalshi). Sportsbook limits are not in the data.

Two things drive the low power. The confirm samples are short: 2026 props cover 8 weeks, and the Kalshi sample is 107 games. The rule also fires rarely when a market is nearly calibrated: the fitted recalibration only picks a side when it beats the price paid, and for the receiving-yards books that happened on 90 contracts.

## The one market read: Kalshi receptions

Recalibrating on 2025 and buying the side the recalibration prefers at the kickoff-minus-90-minutes price, 2026 net of the spread: **-0.022, 95% interval -0.054 to +0.011**, one-sided p 0.91, before Kalshi fees. The rule does not beat its cost. The unfitted favourite rule scored -0.024 and buying the longshot +0.012, descriptive only, from the same contracts.

The first run read this same result. Amendment 2 explains why it was run twice (a zero-odds row, which turned out to be harmless), and the second run is identical.

## Cost of trading and calibration, every market (descriptive)

Overround is the sportsbook hold, or for Kalshi the ask minus bid. Reliability is the miscalibration part of log loss, in nats, over ten equal-count bins; each estimate carries a positive noise floor of about 10 / (2 x contracts), which is 0.002 or less for the big samples and larger once clustering by game is counted.

| Market | Contracts | Overround | Log loss | Reliability | Resolution |
|---|---|---|---|---|---|
| Sportsbook QB passing yards | 2,571 | 7.5% | 0.690 | 0.0090 | 0.0014 |
| Sportsbook receiving yards | 14,530 | 7.2% | 0.689 | 0.0012 | 0.0026 |
| Game spread | 2,985 | 4.2% | 0.694 | 0.0028 | 0.0024 |
| Game total | 3,100 | 4.0% | 0.694 | 0.0017 | 0.0003 |
| Game moneyline | 3,126 | 3.7% | 0.611 | 0.0016 | 0.0790 |
| Kalshi passing yards | 1,445 | 1.6% | 0.544 | 0.0029 | 0.1478 |
| Kalshi receiving yards | 4,209 | 1.5% | 0.564 | 0.0017 | 0.0870 |
| Kalshi rushing yards | 2,661 | 1.5% | 0.556 | 0.0022 | 0.1086 |
| Kalshi receptions | 2,755 | 1.3% | 0.561 | 0.0024 | 0.1009 |
| Kalshi total | 2,885 | 1.4% | 0.594 | 0.0016 | 0.0961 |
| Kalshi spread | 4,249 | 1.3% | 0.558 | 0.0014 | 0.0682 |

What this shows, and what it does not:
- Reliability is small everywhere, 0.001 to 0.003 nats except sportsbook QB passing yards at 0.009. That one is the only market with a visible calibration gap, on only 56 games of 2026 and many books quoting each game, so its effective sample is far smaller than 2,571. It is a lead, not a result, and it sits behind a 7.5% hold.
- The trading cost differs by a factor of five. A sportsbook prop costs 7 to 8 points per round trip, a game line about 4, and a Kalshi contract about 1.5 before fees. Any inefficiency in a prop market has to clear a bar that is five times higher than on Kalshi.
- Resolution is not comparable across markets: Kalshi ladders include many contracts far from 50-50 (low uncertainty per contract), and sportsbook lines are set at the median, so almost every contract sits near 50-50.

## Liquidity (from the data only)

- Kalshi: median 24-hour volume at kickoff minus 90 minutes is about 2,000 contracts for passing, receiving and rushing yards and receptions, 4,400 for totals and 5,200 for spreads; median spread 1 cent. The stored trade tape has a median of 17 to 25 fills per contract, and 86 to 90% of fills printed inside the stored bid and ask, so the stored quotes were mostly executable.
- Sportsbooks: limits and bet caps are unknown. No part of this result says a bet could be placed at the posted price.

## Lead-lag and early against close

Both were run earlier and are cited, not rerun. Sportsbook against Kalshi (`docs/TAILS_RESULTS.md`, Amendment 3): no result, because about 14 confirm games per setting is far too few. Early against close on the 20 years of lines (`docs/LINEMOVE_RESULTS.md`): a spread move does not continue after the close (-0.013 decide, +0.005 confirm, interval -0.036 to +0.046).

## Replication

The three game markets are the 20-year set, so the decide and confirm eras are the replication. They failed the gate, so nothing in them was read. The game-line decide era has only about 500 contracts per market because the stored close odds are mostly missing before 2016.

## Prospective record

`data/inefficiency/week_2026_09.json`: 1,591 sportsbook prop contracts for unplayed games, each with the price, the recalibrated side and edge, write-once with a SHA-256 hash. No scorer yet. Kalshi settles to a result in the stored file only after the game, so no Kalshi freeze is possible from this file.

## Concerns

- The answer to "which market is most inefficient" is that this data cannot say. Power is under 0.85 for every market and under 0.25 for two.
- The decide era for game lines is thin, so the recalibration leans on the prior there.
- One rule, one cost definition (price paid) and one price time (kickoff minus 90 minutes for Kalshi, the last quote for sportsbooks) were chosen. A different rule could find something this one missed.
- Sportsbook and Kalshi samples overlap in 2026 games, and the bootstrap treats them as independent.
- Kalshi fees are not included.
- Zero-yard props are counted only for players the roster lists as active, a judgement about how books void bets.

## Next

Rerun the registered gate after weeks 11 and 12, and again with the 2027 season. Passing yards at sportsbooks is the first thing to look at when it gains games, since its reliability term is the only one above noise.
