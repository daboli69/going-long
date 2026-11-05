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
