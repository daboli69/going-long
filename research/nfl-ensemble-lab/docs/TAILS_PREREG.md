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
