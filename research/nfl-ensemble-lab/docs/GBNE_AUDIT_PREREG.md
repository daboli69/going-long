# Packers 45, Patriots 27: luck or defect? Pre-registration

Written 2026-11-08, committed before any calibration number in part B is computed. Football only, $0, no Codex, nothing promoted, no staking.

## Question

Was the ensemble's miss on Packers 45, Patriots 27 (Week 9) mostly luck, or does it point to a defect that can be found and fixed? This is not an upset predictor. One game is the case study and the forecast pipeline is what gets audited.

## Disclosures

- The final score, Maye's four turnovers, and a first look at season-to-date efficiency were seen before this document was written. Part A is descriptive because of that. Part B uses no number from that game.
- No calibration, log-loss or reliability number for any model in part B has been computed. The model files were opened only to check column names, row counts and the join to closing lines (3,756 of 3,757 walk-forward games join).
- "The ensemble" here means the lab's stored home-win forecasts, because they are the ones with a history: `p_xgb_deep_platt`, `p_margin_platt` (the two contenders in the home-win deep study) and `p_win` (the joint score model in `forecast_wf.parquet`). The probability shown in the app for this game (57.7%) has no stored history before the 2026 freezes and cannot be audited over time. The three forecasts are audited separately; no blend is built.
- The closing line is the undated closing moneyline in `data/raw/games.csv`, no-vig by proportional removal. The earlier study rules said not to use an undated closing line without approval. This request names the closing line as the benchmark and is taken as that approval for this audit only.

## A. This game, from the plays

All inputs are raw files: `play_by_play_2026` (all columns, public nflverse snapshot saved with its SHA-256 under `data/raw/gbne/`), `ftn_2026` charting, `pfradv_pass_2026` pressure, timestamped injury snapshots in `data/raw/archive/nflverse_injuries_*`, and the frozen pregame forecasts in `data/raw/archive/forecast_games/` and `homewin_deep/` (content hashes re-checked against the ledger).

1. **Turnovers rebuilt from plays.** Each interception and fumble: quarter, clock, field position, pressure, whether FTN marks the pass as interception-worthy, the play description, and EPA.
2. **League rates, 2022 to 2025 regular season, same sources.** The share of interception-worthy passes that are intercepted, the share of all fumbles that the offense loses, and the average EPA of an interception and of a lost fumble.
3. **Expected turnovers for each side** = interception-worthy passes thrown times the league interception share, plus fumbles times the league lost share. Turnover luck for a side = actual minus expected turnovers.
4. **Turnover-luck-adjusted margin** = actual margin minus (net turnover luck in turnovers times the league average points cost of a turnover, from the EPA in step 2).
5. **Knowable versus luck.** Pregame forecast margin from the frozen files, then adjusted margin, then the rest. Injury statuses known at the freeze time versus at kickoff come from the timestamped snapshots; an injury first appearing after the freeze is labelled "not knowable at the freeze".
6. **Reading rule (descriptive).** "Mostly luck" if the adjusted margin is within one forecast standard deviation (the frozen `sigma`) of the pregame forecast margin and part B finds no defect. Otherwise the answer is "not mostly luck" and the remaining gap is described.

## B. Calibration audit against the closing line

**Sample.** `data/cache/homewin_deep/walk_forward.parquet` (walk-forward out-of-sample, each week predicted from earlier data only), 2012 to 2025 for the tests and 2026 weeks played by the file's date as a separate check. Tied games dropped, games without a closing moneyline dropped and counted.

**Forecasts audited:** F1 `p_xgb_deep_platt`, F2 `p_margin_platt`, F3 `p_win`. Alpha is 0.05 divided by 3 for each, so intervals are 98.33%.

**T1, overall.** Per forecast and for the market on the same games: log loss, Brier, and the Murphy decomposition (ten equal-count bins of the forecast: uncertainty, resolution, reliability). Paired difference to the market by game, bootstrap by season-week (2,000 draws, seed 20261108).

**T2, the 55 to 65% band.** Games where the forecast's favorite has probability in [0.55, 0.65). Calibration gap = observed share of favorites that won minus mean forecast probability for them. The same games' market gap uses the market's probability for the same side. Intervals by the same bootstrap.

**Defect D1 (band miscalibration)** is declared for a forecast only if all hold: the 2012 to 2025 gap interval excludes zero; the model gap minus the market gap interval excludes zero; the 2026 point estimate has the same sign; the gap is at least 0.02 in size.

**T3, information beyond the market.** Logistic regression of the home win on a constant, the market log-odds m and d = logit(forecast) minus m, fit on earlier seasons only, scored on each later season. Test seasons 2016 to 2025 (four training seasons to start), 2026 separate. Ridge penalty 1.0 on the d coefficient only. Statistic: log loss of this model minus the market, pooled, per game. Reading: "adds information" if the 98.33% interval is wholly below zero; "worse than the market" if wholly above; otherwise "no detectable information beyond the market". Only the last two outcomes bear on a defect: **D2** is "worse than the market".

**Gate, run before any real reading.** Each rule is run on simulated outcomes using the real games and the real forecasts, 200 runs, normal interval clustered by season-week.
- D1 placebo: outcomes simulated from the forecast itself. The rule must fire in at most 7% of runs.
- D1 planted: outcomes simulated so that favorites in the band win 0.03 less often than forecast. The rule must fire in at least 80% of runs. The smallest gap with 80% power is also reported (0.02, 0.03, 0.04, 0.05, 0.06).
- T3 placebo: outcomes from the market itself. "Adds information" must fire in at most 5% of runs.
- T3 planted: outcomes from the market log-odds plus b x d, with b set so the average expected log-loss gain over the market is 0.004. The "adds information" reading must fire in at least 80% of runs.
A test that fails its planted check is "not testable" and its real reading is not made.

## C. If a defect shows up

At most one fix is pre-registered, in a separate dated document committed before it is tested, with a placebo and planted-effect gate. If no defect shows up, nothing is proposed.

## D. What would show the result is right

The closing line and settled outcomes; seasons nobody tuned on (2012 to 2025 are walk-forward; 2026 is a separate check); the hashed freezes for Weeks 8 and 9, whose content hashes are re-computed and scored on games played after the freeze; and a scripted rebuild (`scripts/gbne_audit.py rebuild`) that regenerates every number from the raw files and compares output hashes.

## E. Report order

Completed, Model Research, Concerns, Next, Needs Travis. If the answer is "mostly luck", say so in the first line.

## Amendment 1 (2026-11-08, committed before any part B number and before the fallback figures of part A are computed)

The FTN charting and PFR pressure files for this game are not published yet. The nflverse releases, re-pulled today, hold week 9 only for Jacksonville at Baltimore (`data/raw/gbne/ftn_2026_snapshot.parquet`). Step 3 of part A cannot use interception-worthy flags. A first run with the flags missing counted them as zero and produced an expected-turnover figure that is wrong, so that output is discarded.
- **Fallback, used while charting is missing:** expected turnovers for a side = its dropbacks times the 2022 to 2025 league interception rate per dropback, plus its fumbles times the league share of fumbles lost. No charting is used.
- **Sensitivity (reported next to it):** the interception rate per dropback is replaced by the average of the offense's season-to-date rate and the opposing defense's takeaway rate through Week 8, each shrunk toward the league rate with weight n/(n+300) dropbacks.
- The cost of a turnover is the 2022 to 2025 average EPA lost on an interception or lost fumble (about 4.3 points), unchanged.
- When the charting for this game is published, the `game` stage reruns with the interception-worthy method of step 3 and both results are reported. The reading rule in step 6 uses the fallback now and is revisited then.
