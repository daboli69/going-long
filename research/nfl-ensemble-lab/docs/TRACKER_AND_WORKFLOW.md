# Model audit, performance tracker and daily workflow

Written 2026-11-09. Nothing here changes a prediction formula. The model's numbers come only from the frozen snapshots in `snapshots/prospective/`.

## What exists now

| Piece | File | What it does |
|---|---|---|
| Error audit | `scripts/model_audit.py` | Compares every frozen pre-kickoff game forecast with the result. Writes `reports/model_audit/AUDIT.md` and `audit.json`. |
| Tracker | `lab/tracker.py`, `scripts/track.py` | Append-only record of picks and results, flat 1 unit. Files in `reports/tracker/`. |
| Tests | `tests/test_tracker.py` | Odds math, idempotent selection, post-kickoff snapshots ignored, drawdown, tamper detection. |

## First audit (55 games, weeks 6 to 9 of 2026)

- The model is worse than the no-vig moneyline. Brier 0.2205 against 0.1960, a difference of +0.0245 with a 95% bootstrap interval of +0.0074 to +0.0424. Log loss agrees. Margin error is 9.84 points against 9.03 for the spread.
- It leans toward the home side. Mean home probability is 0.559; home teams won 45.5% of these games. The gap (+0.104) is not significant (p = 0.10). Treat it as a question, not a finding.
- Where the model and the price differ by 5 points or more (31 games), the model's side won 35.5%. The model gave that side 53.9% and the market 44.7%. When they disagree, the market has been the better guide.
- 72 slices were tested (team, home side, projection range, spread, model side, model-minus-market gap, week). 13 reached p < 0.05 before correction, and about 3.6 would by chance. One passed the stricter test (n at least 8, Holm p under 0.10, same sign in both halves): home teams when the market has the away team favored by 3 to 7 points, where the model overrated the home side by 0.32 in win probability (15 games). It was found by searching, so it is a hypothesis. It needs to be written down and tested on weeks not yet played before anyone acts on it.
- Team-level results (PHI, CHI, BAL) rest on 4 games each. They show how little four games say about a team.

## Tracker rules

- The rule is `ml_edge_v1`, frozen in `lab/tracker.py` and hashed into every row. Bet the side where the model's win probability beats the no-vig market probability by 5 points or more, at the snapshot's moneyline, 1 unit flat. The 5-point threshold was chosen before any result was scored and has not been tuned. Changing any part of the rule produces a new rule id and the old rows keep the old one.
- `evaluations.csv` gets one row for every pre-kickoff game, qualified or not, so no losing game can be dropped later. `settlements.csv` gets a row when the game is final. Neither file is edited or sorted. Each evaluation row holds a hash of the row before it, and `track.py verify` fails if any row was changed.
- A snapshot written after kickoff is ignored. A played game with no pre-kickoff snapshot is listed by `verify` as unrecorded. Stale-data snapshots and missing odds are flagged on the row.
- Reported: win rate, ROI per unit, cumulative units, maximum drawdown, open picks.

Current record (rule `ml_edge_v1`, 56 games evaluated, 32 qualified, 31 settled, 1 open): 11 wins, win rate 35.5%, -6.18 units, ROI -19.9% per unit, maximum drawdown -11.39 units.

Read that number with two limits in mind. First, all 56 rows are marked `backfill`: the rule was written after those snapshots existed, so they are not a clean test of the rule. The first clean sample starts with rows marked `live`, from Week 10. Second, 31 bets cannot separate skill from luck in either direction. Judge the model on hundreds of `live` rows, and on the Brier and log-loss comparison with the market, which uses all games.

## Data limits you should know

- The odds in each snapshot are the nfldata consensus line, not a named sportsbook. The sportsbook column says `nfldata_consensus`. A per-book record needs a source the lab does not have at no cost, so none was invented.
- Games before 2026-10-18 (88 played games in Weeks 1 to 5) predate the snapshot system. They are listed as outside the record, not scored.
- The audit covers game winner and margin. A player-level and market-level breakdown for props needs the weekly previews in `artifacts/props/prospective/preview/` joined to box-score actuals. That join is not built yet.

## Daily workflow

Most of this already runs on the owner's PC. The additions are marked.

1. **Refresh.** `lab.cli refresh` pulls updated statistics; `lab.scheduler tick` runs every 5 minutes and writes snapshots at fixed windows before kickoff (early, 24 hours, 90 minutes, 60 minutes, final). If the refresh fails, the snapshot is written with `stale_data` set instead of silently using old data.
2. **Freshness.** `data/source_health.jsonl` records each source's last successful check. Sources with a daily limit are served from cache (the Sleeper entry already shows "cached (daily limit)").
3. **Projections.** The scheduler runs the frozen champion and stores the snapshot with a content hash.
4. **Market comparison.** The snapshot records the line and odds at that moment. No network call is made by the tracker. It uses no paid API.
5. **Selection (added).** `scripts/track.py select` records every pre-kickoff game under the frozen rule.
6. **Settlement (added).** After games finish and `games.csv` is refreshed, `scripts/track.py settle`, then `report`.
7. **Alerts (added, manual until scheduled).** `scripts/track.py verify` exits with an error if the chain is broken, a snapshot is after kickoff, or a settlement has no pick. Stale and missing-odds rows are listed. Add it to the Windows task that runs the tick if you want it automatic; I did not register any task.

Admin and public stay separate. Refresh, select and settle run only from the local scripts and Windows tasks. The Streamlit pages and the Vercel site only read files; none of them can trigger a refresh or write the tracker. If the tracker CSVs are ever shown publicly, publish a read-only copy, not the working folder.

Expensive calls are bounded by design: the tracker makes none, Kalshi history is cached under `data/cache`, and the scheduler skips a snapshot that already exists.

## Needs your decision

- Whether to run the daily steps as a scheduled task (5 and 6 above).
- Whether to register the home-overestimate and "away favored by 3 to 7" questions as pre-registered challengers. Neither is accepted. Both need weeks 10 onward.

## Changes after the 2026-11-10 pipeline audit

- `scripts/track.py report` now quotes live rows only. Backfill rows (weeks 6 to 9) stay in the files and print in a separate block marked descriptive.
- The report opens with the market gate from `scripts/market_gate.py`. On 933 walk-forward games from 2023 onward the champion's log loss is 0.0237 worse than the closing price, 95% interval +0.0114 to +0.0361. Until that interval sits below zero the champion is not a price signal and rule `ml_edge_v1` is a record, not a strategy.
- Every result is labelled as priced at the nfldata consensus line. The report also re-prices settled bets at the best named-book moneyline in `data/raw/market/going_quotes.parquet` when a quote is under 30 minutes old at snapshot time. That archive ends on 2026-10-16, so no bet is priced this way today.
- The gate drops odds rows with hold outside 0.5% to 8% (one row, 2020_01_LV_CAR) and reports 2016 to 2022 and 2023 onward separately.
