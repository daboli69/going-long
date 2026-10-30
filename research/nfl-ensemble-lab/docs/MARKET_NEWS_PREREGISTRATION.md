# Where the market is slow and where news changes usage: pre-registration

Written 2026-10-29, after six earlier studies and before any quantity in this study was computed. Local only, $0, read-only
Kalshi data, no trading or order code, no new sports. No new model family. Nothing is promoted. No scheduled task, no library
install and no undated closing line is used without Travis's approval.

**Question.** (A) Which venue is slow, and does its gap to the others close? (B) When a key player is newly ruled out, does the market
move the way the news implies, and how fast? (C) How much of next game's target and carry distribution can pre-game availability
information predict?

## Step 0: verification gate
`docs/CODEX_REPRODUCTION_REQUEST.md` lists six studies for an independent rebuild. **Codex is not reachable from this session** (the visible
peer sessions are NBA, Gmail, a prop-simulation prompt and GOING Missions; none is identifiable as Codex, and messaging unrelated sessions would be an
unauthorized action). Status: **none of the six is independently reproduced.** All earlier conclusions stay provisional, and every
reading below carries the label "provisional".

## Data actually available (real sampling intervals)
- **Kalshi:** hourly candles for winner, spread and total (2025 week 5 to 2026 week 8) and for prop ladders. Trade prints and order books are
  collected only from 2026-10-29 on and are sparse so far. **Not 5-minute data.**
- **Pinnacle and other books** (GOING quote history, 2026 only): about 82 quotes per game over about 109 hours, **median 62 minutes between
  quote times**. Not 5-minute data.
- **ESPN injury feed:** 245 snapshots from 2026-10-16T21:03Z, each entry with its own report time. Two weeks of history.
- **nflverse injury reports 2016 to 2024:** every row carries `date_modified`. The 2025 and 2026 files have none and are excluded
  from any availability-timestamp claim.
- **Roster status** (ACT, INA, ...) by team-week, play-by-play, snap counts and participation for 2016 onward.
- **Official inactives:** none archived. **Weather:** archived from 2026-10-19.

## Experiment A: venue lag and convergence (2026 window, hourly grid)
- **Venues:** Kalshi (K), Pinnacle (P), and the median of the other books (O, GOING quotes excluding Pinnacle).
- **Targets:** winner (logit of the de-vigged home win probability), spread (home margin median, points), total (points). Kalshi's spread and total
  values are the median of the monotone (isotonic) ladder built from every market's latest hourly mid with ask - bid <= 0.10.
- **Grid:** each hour on the hour (UTC) from kickoff minus 48 hours to kickoff minus 1 hour. A venue's value at t uses only quotes with
  `quote_time <= t` (and, for GOING quotes, `committed_at <= t`), or a Kalshi candle ending at or before t.
- **Deviation:** dev_v(t) = x_v(t) - mean of the other two venues at t.
- **Convergence:** change D = x_v(t + 3h) - x_v(t) regressed on dev_v(t) (OLS with intercept); kappa_v = -slope. Half-life = 3 * ln(0.5) / ln(1 - kappa)
  hours for 0 < kappa < 1. Standard errors by a game-clustered bootstrap (1,000 draws, seed 0).
- **Lead-lag:** the correlation of 1-hour changes of K with P's 1-hour changes at lags -3 to +3 hours, pooled. Resolution is one hour, which is the real
  sampling interval; minute-level lead is **not measurable** with this data.
- **Settlement (winner, descriptive):** logistic regression of the home win on logit(K) and (logit(P) - logit(K)) at the last grid hour before T-90.
- **Lean and abstention:** lean = |dev_K| >= 1.5 sigma, with sigma the pooled SD of dev_K. A risk-coverage table at thresholds 0, 0.5, 1, 1.5 and 2 sigma
  reports coverage, the share of 3-hour moves toward consensus, and the mean signed convergence.
- **Placebo:** permute dev_K across games within the same hours-to-kickoff slot (200 permutations, seed 0), recompute kappa_K, permutation p-value.
- **Family A1:** kappa_K for the three targets, alpha = 0.05 / 3. *Passes* if the interval's lower bound is above 0 and kappa_K >= SESOI 0.10.

## Experiment B: availability events (descriptive until enough events)
- **Key players:** QB1, RB1 and WR1 of each team, by season-to-date offense snaps from `snap_counts_2026` for games before the event (prior-season snaps in week 1).
- **Event:** a key player appears with status Out, Doubtful or Injured Reserve in an ESPN snapshot and was not in that group in the player's previous snapshot.
  The first snapshot (2026-10-16) is not used to create events. Event time = that snapshot's retrieval time (the ESPN entry date is recorded too).
  Only events at least 6 hours before the team's next kickoff are used.
- **Reaction:** change in Kalshi winner logit (home) from the event hour to +6 hours, signed so that the team's worsened prospects are positive.
- **Tests:** the share of events moving in the expected direction (one-sided sign test) and the mean signed reaction, by event type (QB, RB1, WR1). Benjamini-Hochberg false-discovery control
  across the three types. Placebo: the same statistic at a random start time inside the same game's pregame window (200 draws, seed 0).
- **Power:** MDE for the mean signed reaction as a function of the number of events, from the SD of 6-hour winner-logit changes in pregame windows.
  SESOI = 0.05 logit. The weeks needed follow from the observed event rate.

## Experiment C: usage before yards (history 2016 to 2024, availability timestamped)
- **Quantities:** per team-game, each player's share of targets (pass attempts with a receiver) and of carries (designed rushes), from play-by-play.
- **Candidates:** players with at least one target or carry in the team's previous 6 games, plus an "other" bucket whose probability is the EWMA
  share of non-candidates.
- **Models** (no fitted parameters; EWMA half-life 4 games):
  - **A0 naive:** probability proportional to the player's EWMA share over the last 6 team games, counting games missed as zero.
  - **A1 availability-aware:** the same EWMA over the player's own active games (roster status ACT), multiplied by an availability weight from the latest injury report with
    `date_modified` before kickoff (Out 0, Doubtful 0.05, anything else 1), renormalized across candidates.
  - **A2 oracle (ceiling):** like A1 but using the game-day ACT list.
- **Score:** multinomial log likelihood of realized counts, per target (or carry); per team-game difference A1 - A0, week-cluster bootstrap.
  SESOI = 0.005 nats per target.
- **Split:** pilot 2018 to 2020 (for power only), primary look 2021 to 2023, **untouched confirmation 2024**, analyzed only after the primary results are committed.
  2025 is excluded (no timestamps).
- **Families:** C1 targets, C2 carries; alpha = 0.05 / 2. C3 (descriptive): the share of the A0-to-oracle gap that A1 captures.
- **Not run, by design:** conversion to yards (deferred, as instructed), the comparison with a market-implied mean (a player ladder gives no team target total to
  turn into a share), and conformal intervals for shares (no interval is produced).

## Power (first, by simulation, committed before the primary run)
Effect-injection on the real clustered data. A: the bootstrap SE of kappa_K gives MDE = (z(1 - alpha / 2) + z(0.8)) * SE; weeks needed =
available weeks * (MDE / SESOI)^2. B: the MDE as a function of event count. C: pilot differences (2018 to 2020), whole weeks resampled, a known improvement
injected, 300 resamples, 500 bootstrap draws, seed 0. **Decidable now** = MDE(available) <= SESOI. **Prospective only** = weeks needed <= 150. Otherwise **not decidable**.

## Proof
The market's own later price (the convergence tests) is the fast judge; Kalshi settlements and realized outcomes are the slow one. Placebos for every
claimed effect. Dense capture (`scripts/market_news_study.py capture`) and sealed weekly freezes with GitHub's commit time as the clock. The 2024 confirmation for C. Codex's
rebuild before any gate counts (not yet available). Results and freezes go on the Streamlit page.

## Amendment 1 (2026-10-29, after the Experiment C pilot on 2018 to 2020, before any 2021 to 2023 result)
The pilot (used for power only) showed that the preregistered availability arm **A1 does worse than the naive prior** (-0.013 nats per target) because its
"share when active" prior, not the availability weights, is the problem. A diagnostic arm that applies only the availability weights to the naive prior did better:
| Arm (pilot 2018 to 2020, gain over A0 in nats per target) | all team-games | games with a reported-out candidate (>= 5% prior share, 27% of games) |
|---|---:|---:|
| A1 (preregistered: active-game prior x availability weights) | -0.013 | +0.102 |
| **A1b (naive prior x availability weights)** | **+0.046** | **+0.153** |
| A2 oracle (active-game prior x game-day ACT list) | +0.136 | +0.204 |
| A2b oracle on the naive prior | +0.116 | +0.180 |

Carries show the same pattern (A1 +0.005, A1b +0.061 overall; +0.396 and +0.410 in news games). **Change:** the primary arm for C1 and C2 becomes
**A1b**; A1 is reported as a secondary, descriptive arm; the oracle for C3 is A2b. Games with a reported-out candidate are reported as a descriptive subgroup.
SESOI stays 0.005 nats per target, alpha 0.05 / 2, and the 2024 confirmation stays untouched until the primary result is committed.

### Power for Experiment C after Amendment 1 (`reports/usage/power.json`, SHA-256 `c03e46dbe997be742c4387f8a8da12ba55ea79163b5d166da48e2e31ceb23637`)
Pilot 2018 to 2020: 1,248 team-games. Available weeks for the primary look: 54 (2021 to 2023).

| Comparison | Pilot gain | MDE at 54 weeks | SESOI | Weeks needed | Class |
|---|---:|---:|---:|---:|---|
| C1 targets, A1b vs A0 | +0.0462 | 0.0059 | 0.005 | 75 | not decidable at 54 weeks (boundary case); the pooled 2021 to 2024 sample (about 72 weeks) is nearly enough |
| C2 carries, A1b vs A0 | +0.0592 | 0.0146 | 0.005 | 464 | not decidable |

**Consequence fixed now.** The 2021 to 2023 primary look is **descriptive** (verdict not allowed by the power rule). A verdict on C1 is allowed only on the pooled
2021 to 2024 sample once it reaches 75 weeks. C2 gets no verdict. The pilot gain is far above the MDE, so the descriptive interval is expected to exclude zero
by a wide margin; that does not change the classification.

## Amendment 2 (2026-10-29, before any Experiment A or B quantity was computed)
- **Experiment A clock.** The GOING quote snapshots were committed about every 3.4 hours, so enforcing `committed_at <= t` would make Pinnacle and the other books
  update only at commit times and create a false lag against Kalshi's hourly candles. A is a description of the **venues' own clocks**, not a tradable forecast,
  so a venue's value at hour t uses `quote_time <= t` (staleness cap 24 hours; Kalshi candles 3 hours). The `committed_at` rule is dropped for A and applies to nothing here.
- **Winner series.** Kalshi's winner value is the hourly home mid divided by the sum of the home and away mids (logit scale).
- **Experiment B.** Event reaction uses the existing hourly Kalshi winner series (history file built 2026-10-29); events with no market data in the window are counted and excluded. The lab's
  update is reduced to the **direction** test; magnitude regressions wait for prospective data.
