# Market lag, availability events and usage: results

Run 2026-10-29. Protocol `396af66a` with Amendments 1 and 2, power committed before each run. Files: `reports/market_news/results.json`
(SHA-256 `7480e098ca69e9cfd9fc8ea5d745a7caa0bb7124940fa764005caace2852e842`, the rerun after an Experiment B bug fix: the first run defined a team's next game by today's played status, which dropped games played since the event; Experiment A numbers are identical in both runs), `reports/usage/results.json`
(`7c394ff185de71173c6c621c6f75872a376e8f22d4b6655e12a8c0f543c99749`), `reports/usage/confirmation.json`
(`6a04e2478ab4db47639d9c50d468dd3045f9171de6c6a0fa5e87fc474a901980`).

**Step 0 status.** Codex was not reachable from this session, so **none of the six earlier studies is independently reproduced.** Every reading here is
provisional.

**Short version.**
- Availability news matters a lot for who gets targets and carries (Experiment C), and a simple rule that zeroes out players reported Out beats the naive average in both the primary period
  and the untouched confirmation season.
- Kalshi is *not* the slow venue (Experiment A). Pinnacle and the other books move toward Kalshi, and Kalshi's winner moves lead Pinnacle's by about an hour.
- Market reaction to key-player news (Experiment B) is small and noisy; there is a hint that it is larger than random, but it is not conclusive.

## Experiment C: usage before yards (history)
Availability weights (Out 0, Doubtful 0.05, otherwise 1) applied to a naive recent-share prior; log likelihood of who gets the targets and carries, in nats per target.
The preregistered first design was worse than naive on the pilot and was amended before the primary look (Amendment 1).

| | Naive | Availability | Oracle (game-day ACT list) | Gain | Interval | Share of the naive-to-oracle gap |
|---|---:|---:|---:|---:|---|---:|
| Targets, 2021 to 2023 (1,342 team-games) | -2.330 | -2.286 | -2.187 | **+0.044** | [+0.039, +0.049] | 31% |
| Carries, 2021 to 2023 | -1.468 | -1.416 | -1.281 | **+0.051** | [+0.043, +0.060] | 28% |
| **Targets, 2024 untouched confirmation** | -2.269 | -2.215 | -2.131 | **+0.056** | [+0.045, +0.072] | 40% |
| **Carries, 2024 confirmation** | -1.430 | -1.367 | -1.256 | **+0.059** | [+0.035, +0.088] | 35% |

- In the 27% of team-games where a player with at least 5% of the prior target share was reported out, the target gain is +0.147 (oracle +0.243); for carries in the 14% of games with such a player,
  the gain is +0.343.
- Gains are stable by season (targets +0.047, +0.046, +0.039 for 2021 to 2023).
- **Power rule:** the 2021 to 2023 sample (45 weeks) falls below the 75 weeks needed for a formal verdict on targets (and far below the 464 for carries), so neither result is a
  formal pass. The intervals are far from zero, and the independent 2024 season agrees, but the protocol's wording stands: **descriptive, no verdict**.
- My original availability design (using a "share when active" prior) was slightly worse than naive (-0.009 targets), a lesson in why the amendment was needed.
- **Not run:** conversion to yards, and the comparison with a market-implied mean.

## Experiment A: venue lag and convergence (2026, 120 games, hourly)
Reversion speed kappa = the fraction of a venue's deviation from the other two venues that closes within 3 hours (interval 98.3%). Pass for Kalshi needed a lower bound above 0 and kappa at least 0.10.

| Target | Kalshi | Pinnacle | Other books |
|---|---|---|---|
| Winner | +0.010 [-0.013, +0.035] | **+0.111 [+0.056, +0.201]** (half-life 18 h) | +0.091 [+0.031, +0.200] |
| Spread | -0.000 [-0.005, +0.004] | +0.085 [+0.015, +0.143] | +0.023 [+0.006, +0.060] |
| Total | -0.023 [-0.061, +0.014] | **+0.223 [+0.167, +0.300]** (half-life 8 h) | +0.105 [+0.064, +0.167] |

- **Hypothesis rejected: Kalshi does not catch up to the other venues.** Its kappa is essentially zero on all three targets, so a deviation from consensus does not predict its own later move.
  A winner permutation test calls the +0.010 above chance (p = 0.005), but it is a tenth of the effect needed.
- **The other venues move toward Kalshi.** Pinnacle and the pooled books close part of their gap within hours, most clearly on totals.
- **Lead-lag (1-hour resolution):** for winners, Kalshi's hourly change correlates most with Pinnacle's change one hour later (0.113 vs 0.016 at lag 0), so Kalshi leads by about an hour. Spreads and totals show no clear lead.
- **Settlement (winner, 93 games):** adding the Pinnacle-minus-Kalshi gap to Kalshi's price does not help predict who wins (coefficient 5.4, interval [-7.5, +20.6]).
- **Leans:** the model's "Kalshi deviation" leans move toward consensus only 7% of the time at winner (most moves are zero), so there is no usable lean on Kalshi from this.
  A lean on the *books* (they are about to move toward Kalshi) exists, but it cannot be acted on from here and was not an aim of the study.
- **Resolution limit:** the sampling interval is one hour (Kalshi candles; Pinnacle about 62 minutes). Lead and lag in minutes are **not measurable** with this data.

## Experiment B: availability events (2 weeks of ESPN snapshots)
29 key-player events (QB1, RB1, WR1 newly Out, Doubtful or on IR); 27 had market data. Reaction = change in Kalshi's home win logit over 6 hours, signed so a worse outlook for the affected team is positive.

| Event type | Events | Moved the expected way | Sign test p | Mean reaction (logit) | Placebo (random time) mean, p |
|---|---:|---:|---:|---:|---|
| QB1 | 7 | 4 | 0.50 | +0.020 | +0.020, p = 0.48 |
| RB1 | 3 | 0 | 1.00 | -0.006 | -0.002, p = 0.74 |
| WR1 | 17 | 11 | 0.17 | +0.051 | +0.009, p = 0.005 |

- **No type passes the preregistered Benjamini-Hochberg rule.** The WR1 mean reaction beats the random-time placebo, which is a hint, not a result. QB1 news produced no reaction beyond chance in this window.
- **Timing sensitivity (not preregistered):** ESPN's own report time is a median of 1 hour (90th percentile 4.2 hours) before our first snapshot saw the news, so part of the reaction happens before our event time. Using ESPN's time,
  the reaction is larger: QB1 5 of 7 (+0.084 logit), WR1 12 of 17 (+0.052), all types 17 of 27 (+0.054). This is descriptive only. It suggests the market
  reacts fast, and that dense, correctly timed capture is needed to measure it.
- Only two weeks of events exist, so this is inconclusive, not a null.

## Leans, abstention and calibration
Only the usage model and the Kalshi-deviation table were evaluated: the usage model has no abstention (its gain comes from known-out players); the venue-deviation leans do not predict.
Split conformal coverage for the prop distributions and the margin and total intervals is in `docs/FORECAST_RESULTS.md`. No conformal interval was produced here.

## Data limits and next steps
- Hourly sampling only; Codex reproduction unavailable.
- **Dense capture is built but must be run by hand.** `scripts/market_news_study.py capture --hours 6 --interval 5` polls Kalshi winner, spread and total books and trades every 5 minutes and saves the ESPN injury feed.
  Next Sunday, start it at **7:00 AM ET** for the 1:00 PM games, and again at about 12:30 PM for the 4:05 and 4:25 PM games. I have not scheduled anything.
