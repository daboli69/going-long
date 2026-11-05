# Tails: pre-registration (2026-11-05, before any tail result)

Question: in games that are unusually uncertain before kickoff, do margins land outside the priced range more often than the price says? Rule: `docs/tails_rule.json`. Code: `lab/tails.py`. Nothing here is advice to bet, and no stake or bet size appears anywhere.

## What exists (counted, no gaps filled)
- 7,088 regular-season games from 1999 to 2026 with a result and a closing spread (`games.csv`); 5,186 with a moneyline; every game has its starting quarterback.
- `sbr_lines`: opening and closing lines for 1,622 games, 2016 to 2021 only.
- Kalshi: history starts 2026-10-30. 6 game-winner snapshots, 3 environment files (spread and total summaries), 1 order-book file and 14 dense book files. That is far too little to price tails game by game. The priced benchmark is therefore the closing line with a normal curve.
- Official inactives with timestamps are not stored for past seasons, so an injury count is not used. The starting quarterback comes from `games.csv`, which is known by kickoff, the moment the closing line is set.

## Reconciliation (before any test)
Margin minus closing line, standard deviation: 13.17 over all 7,088 games, 13.13 for 1999 to 2005, 13.45 for 2006 to 2019, 12.63 for 2020 to 2026. Published reference near 13.9 (Stern, 1991, older seasons); 2006 to 2019 is close and the recent drop is real in our data. Share of games ending exactly 3: 15.0%, 7: 9.1%, 6: 6.0%, 10: 5.6%, 14: 4.8%.

## Model settings (set without looking at tail outcomes)
Walk-forward Elo in points with a home edge of 1.8, rating step 0.06 and carry-over 0.6 between seasons, picked from a fixed grid by margin error on 2006 to 2012. Starting-QB term: each starter's shrunk prior EPA per dropback (prior weight 300 dropbacks at 0.02); its coefficient, 12.4 points per EPA unit, is fitted on 2006 to 2019. Plain Elo and the closing line are the baselines.

## High uncertainty (known before kickoff)
- `u_qb`: either starter differs from that team's previous starter, or has fewer than 150 earlier dropbacks.
- `u_gap`: absolute gap between the Elo-plus-QB margin and the closing line at or above the 80th percentile of 2006 to 2019 (3.54 points).
- `u_any`: either.

## Tail events and tests
Event: absolute (margin minus closing line) at least 14, or at least 21. Priced rate: a normal curve with the standard deviation of unflagged 2006 to 2019 games (13.49), continuity-corrected. Six tests (three flags times two events). Statistic: observed flagged rate minus priced rate, with a bootstrap by game, one-sided. Holm correction across the six, run separately on discovery (2006 to 2019) and confirmation (2020 to 2026).

## Pass rule
A test passes only if it is Holm-significant at 5% in both stages and the observed-to-priced ratio is at least 1.15 in both. Otherwise the tab says "no mispricing found".

## Power check (counts only)
On the confirmation seasons, one-sided at 0.83% per test with 80% power, the smallest detectable rise in the tail rate is 6.3 points for `u_qb` at 14 (20% relative; 572 games), 4.5 points at 21 (35%), 7.7 and 5.5 points for `u_gap` (384 games), 5.4 and 3.9 points for `u_any` (771 games). A smaller real effect cannot be seen with this sample, and a non-pass does not prove there is none.

## Also reported, not part of the pass rule
Quantile regression of the margin around the line against a constant range (pinball loss, 90% coverage, Kupiec test), a Student-t fit against the normal, PIT deciles, and a favorite-longshot table (underdog implied against realized win rate, Wilson intervals). Ties in the favorite-longshot table count as half a win.

## Prospective record
From the week after this file is committed, each week's flags are saved in a write-once hashed file before kickoff (`data/tails/frozen/`, ledger `data/tails/ledger.jsonl`) and scored after the games. The 2026 games already played are in the confirmation stage and carry no extra weight.

## Amendment 1 (2026-11-05, written before any of the checks below was run)

Why: the first run priced tails with a spread fitted on 2006 to 2019 (SD 13.49), but the spread of margins around the line fell to 12.63 in 2020 to 2026. Part of the below-one ratios is that drift. The original rule, results and ledger line stay as committed. The original ratios are reported next to the new ones.

1. **Same-season control.** For each flag and each event, the priced rate becomes the empirical rate among unflagged games in the same season. The statistic is observed flagged hits minus the sum over seasons of (flagged games in the season times that season's unflagged rate), divided by flagged games; ratio is observed over that expected count. One-sided bootstrap by game, resampling flagged and unflagged games within each season. No normal curve and no era fit is involved, so key-number clustering is already in the control.
2. **Tail rungs.** Events: absolute margin-minus-line at least 7, 10, 14 or 21 points (tested) and at least 3 (reported only, its base rate is above 80% so a 15% rise is impossible). Family for the pass rule: 3 flags times 4 rungs = 12 tests, Holm corrected, separately in discovery (2006 to 2019) and confirmation (2020 to 2026). A test passes if Holm p is below 5% and the ratio is at least 1.15 in both stages and, in both stages, the real statistic sits above the 95th percentile of the placebo.
3. **Placebo.** 10,000 random flags per real flag, same frequency in each season, same statistic. Report the percentile of the real value.
4. **Positive control.** (a) A natural one, stated as a hypothesis not a fact: margins widen with the total line. Flag = total line in the top fifth of its season, event at least 14 points from the line, same method. (b) An injected one: multiply the margin-minus-line of the real flagged games by 1.10, 1.20 and 1.30 in 200 random draws each and report how often the method (pass rule without the placebo step) detects it. If the injected 1.20 is detected less than 80% of the time, any null result is labelled uninformative at that size and the tab says so.
5. **Dose-response.** Uncertainty score = gap / 3.54 + QB uncertainty + 0.5 if the starter changed, where QB uncertainty = 300 / (300 + the smaller of the two starters' prior dropbacks). Logistic regression of the tail event on the score with season dummies (scikit-learn, no penalty beyond a very weak one); the statistic is the score coefficient, one-sided bootstrap by game (400 draws). Targets: margin at least 14 from the line, and the actual total at least 10 points from the total line. Holm over the two targets, each stage; a target passes if significant and positive in both stages. Totals use the closing total line from `games.csv`.
6. **Rawest sources.** (a) Parse the six raw `sbr` HTML pages and compare the closing spread and total with `games.csv`; report the match rate. (b) Starting quarterback = the passer on a team's first dropback in the raw play-by-play; report agreement with `games.csv` and use the play-by-play starter in the rerun. Career dropbacks already come from play-by-play. (c) Count settled past Kalshi spread and total ladder markets through Kalshi's public historical endpoint (read-only); if any exist they are described, not used to fill gaps.
7. **Report.** `docs/TAILS_RESULTS.md` gets an addendum and the Tails tab a short "Deeper checks" section, no new tab. If nothing passes the status stays "no mispricing found". A positive control that fails makes the null uninformative, and that is stated.
8. **Prospective record.** Weekly saves continue; from week 10 each saved row also carries the continuous uncertainty score. The saved week 9 file is unchanged.


## Amendment 2 (2026-11-05, written before any ladder was fitted or tested)

Question: does Kalshi's own spread and total ladder price the width and tails of NFL results correctly? Only the Kalshi side of the data was counted before writing this; no ladder has been fitted and no outcome compared. Earlier rules, results and ledger lines stay as committed. No staking, bet sizing or recommendation text; prices are read as probabilities, fees ignored.

**Counted so far (inventory in `data/cache/kalshi/player_inventory.parquet`, matched to games).** Spread: 271 games and events in 2025 (5,619 rungs, kickoffs 2025-09-05 to 2026-01-05) and 121 in 2026 (3,274 rungs, to 2026-11-03). Total: 271 and 121 games (4,480 and 2,426 rungs). 622 rungs belong to games not yet played and are unsettled. Candlestick files already cached: 6,499 spread and 4,844 total markets; the rest are fetched read-only. Trade tape and order-book snapshots are counted when run: our own order-book archive begins 2026-10-30. Nothing before 2025-09-05 exists, and gaps stay gaps.

1. **Prices.** Source: hourly candlesticks (Kalshi's own `end_period_ts`) for every rung, and the trade tape for the six rungs per ladder whose 1-hour mid is closest to 0.5. A price at horizon h is the latest candle that ended at or before kickoff minus h, for h = 24, 3 and 1 hours; a candle older than 3 hours at that time is missing; anything after kickoff is never read. Price = mid of bid and ask when both exist; otherwise the candle's last trade. Tape check: last trade at or before the horizon against that rung's candle mid.
2. **Liquidity settings, fixed now.** L1: bid at least 0.02, ask at most 0.98, spread at most 0.10. L2: bid at least 0.02, ask at most 0.98, spread at most 0.05, 24-hour volume at least 500. Settings = 2 series x 3 horizons x 2 liquidity = 12. Every setting is reported.
3. **Audit.** Kalshi's settled result for every rung is checked against the nflverse final score (home margin or total); count mismatches and drop those games. Each fitted ladder median is compared with the closing line (spread: spread_line; total: total_line); report the median and 90th percentile of the absolute gap.
4. **One distribution per game.** Rungs become a CDF of home margin (home team wins by more than x: F(x) = 1 - p; away team: F(-x) = p) or of the total (F(x) = 1 - p for over x). Monotone constraint: weighted isotonic regression of F on x first, and count adjacent rung pairs that decrease by more than 0.01 before smoothing. Then fit a location-scale Student-t (location mu, scale sigma, degrees of freedom df between 2.5 and 60) by weighted least squares on F with weights 1 / max(F(1-F), 0.01). Tick censoring: a price at or below 0.02 is read as anywhere in [0, 0.025], at or above 0.98 as [0.975, 1], any other price as plus or minus 0.005; the residual is the distance from the model CDF to that interval. A game-horizon needs at least 5 rungs, 3 of them with price between 0.03 and 0.97; otherwise it is dropped and counted.
   **Recovery check, before any real fit is trusted.** Simulate 300 ladders per true df in {4, 8, 30} and true scale in {10, 12.5, 15} (margin) with centers drawn from -10 to 10, priced on strike sets sampled from real games, rounded to whole cents, with 0.01 noise. Pass bars: median error of log scale within 5%; df below 10 estimated for at least 80% of true df 4 ladders and above 10 for at least 80% of true df 30 ladders. If the scale bar fails, nothing downstream is reported as a result. If only the tail bar fails, the tail-weight test is labelled uninformative and the width test still runs.
5. **Tests**, run separately for each of the 12 settings and each stage.
   - *Center* (information, not mispricing): mean of |result - ladder mu| minus |result - closing line| per game, bootstrap by game; the ladder is better if the interval is below zero.
   - *Width*: implied mean absolute miss s = sigma times the Student-t mean absolute deviation for the fitted df. Realized miss m = |result - mu|. Level: mean(m) / mean(s) with bootstrap by game, null 1. Slope: OLS of log(m + 1) on log(s + 1), null slope 1 (reported; its power is expected to be low because s varies little).
   - *Tail weight*: PIT of the result under the fitted t. Share of games with PIT below 0.05 or above 0.95 (nominal 10%) and below 0.01 or above 0.99 (nominal 2%), one-sided excess, bootstrap by game. Also Kolmogorov-Smirnov uniformity of the PIT, games as units, each horizon separately because horizons for the same game are not independent.
   - Holm over the 12 settings within each test and stage.
6. **Mispricing pass rule.** Width level or tail share passes in a setting if its Holm p is below 5% in 2025 (decide) and in 2026 (confirm) with the same sign, and its real statistic lies beyond the 95th percentile of the permutation null in both. Center never counts toward the pass rule.
   **Null and split.** Permutation null: shuffle the realized results across games within the same week and stage, 2,000 times, recompute every statistic with the fits unchanged, and report the percentile of the real value. Time split: 2025 games decide, 2026 games confirm.
7. **Power.** For each stage and setting: smallest width-level error and smallest outer-5% tail-share excess detectable at 80% power (bootstrap standard error times 2.8). Plausible sizes, fixed now: width off by 15%, outer 10% share at 15%. If the confirmation stage cannot detect both, the result is labelled uninformative at those sizes, on the tab and in the results.
8. **Prospective record.** Each week, before kickoff, the current bid, ask, last price, volume and observation time of every spread and total rung is saved write-once with a hash under `data/tails/ladders/`. After the games the same fit and statistics score them. They never mix into 2025 or 2026 stages above; they are a third, forward-only sample.
9. **Report.** Addendum in `docs/TAILS_RESULTS.md`, the Deeper checks section of the Tails tab extended, no new tab. If nothing passes the status stays "no mispricing found", and a failed recovery check or low power is stated in the same place.
