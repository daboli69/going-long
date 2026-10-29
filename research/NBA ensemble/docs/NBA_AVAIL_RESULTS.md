# Does knowing who plays beat knowing team strength? Results

Protocol: `docs/NBA_AVAIL_PREREGISTRATION.md` (committed before win-probability scoring with player features).
Frozen configuration: `docs/NBA_AVAIL_FROZEN.json` (committed before the 2025 and 2026 test predictions were written).
Code: `nba_xgb/` (`pbp.py`, `rapm.py`, `availability.py`, `avail_study.py`, `avail_analysis.py`, `avail_replay.py`, `avail_daily.py`, `independent_eval.py`).

## Short answer

Yes for logistic regression, no for XGBoost. On the 2,459 retrospective test games (2025 and 2026), adding expected player availability and
player quality to a team-strength logistic model lowers log loss by 0.0120. XGBoost does not add to that: with the same features it is worse than the
logistic model by 0.0069. The result is real in the sense of a pre-registered, leakage-tested, independently reimplemented pipeline, but
2025 and 2026 are not clean seasons (see limits), so the live 2026-27 season is the confirmation still to come.

## Model comparison on identical games (log loss, lower is better)

| Model | 2025+2026 | 2025 | 2026 | Brier | AUC | Calib. slope |
|---|---|---|---|---|---|---|
| ESPN-spread benchmark (not a feature) | 0.5758 | | | 0.1968 | 0.761 | 1.01 |
| Logistic with availability | **0.5885** | 0.5931 | 0.5839 | 0.2018 | 0.748 | 0.95 |
| XGBoost with availability | 0.5954 | 0.5998 | 0.5909 | 0.2044 | 0.741 | 1.02 |
| Logistic, team strength only | 0.6004 | 0.6038 | 0.5971 | 0.2069 | 0.733 | 1.08 |
| Calibrated Elo | 0.6035 | 0.6097 | 0.5973 | 0.2081 | 0.730 | 1.09 |
| XGBoost, team strength only | 0.6046 | 0.6096 | 0.5995 | 0.2083 | 0.732 | 1.16 |

Team-strength features: Elo, recency-weighted net rating, rest, back-to-back flags, home court. Availability features: full-health player quality,
availability shortfall, missing rotation minutes (all from play-by-play ratings and the official injury report).

## Pre-registered comparisons (paired log-loss difference, negative favours the first model)

Date-clustered bootstrap, 4,000 draws, 98.3% intervals (Bonferroni for three primary comparisons); Diebold-Mariano with Newey-West variance on daily means.

| Comparison | Pooled difference | 98.3% interval | DM p | 2025 | 2026 | Credible by the pre-registered rule |
|---|---|---|---|---|---|---|
| (1) Logistic with availability minus logistic base | -0.0120 | -0.0183, -0.0056 | 0.002 | -0.0107 | -0.0132 | Yes |
| (2) XGBoost with availability minus logistic with availability | +0.0069 | +0.0016, +0.0122 | 0.010 | +0.0068 | +0.0070 | Yes, XGBoost is worse |
| (3) XGBoost with availability minus calibrated Elo | -0.0081 | -0.0156, -0.0001 | 0.075 | -0.0098 | -0.0064 | No (DM fails; the gain is the availability features) |
| Logistic with availability minus Elo | -0.0150 | -0.0223, -0.0074 | <0.001 | -0.0166 | -0.0134 | Yes |
| XGBoost with availability minus XGBoost base | -0.0092 | -0.0162, -0.0019 | 0.053 | -0.0098 | -0.0086 | Not under the DM threshold |
| Logistic with availability minus ESPN-spread benchmark | +0.0126 | +0.0046, +0.0207 | <0.001 | +0.0113 | +0.0139 | Benchmark is better |

Credible = interval excludes zero, DM p < 0.0167, same sign in both seasons. Pairs (1) and (2) meet it. In 2025 alone the DM p for (1) is 0.068 and
for (2) is 0.067, so single-season significance is not shown; the power statement in the protocol (about 0.0045 minimum detectable difference) applies.

## Answers

1. **Does XGBoost beat Elo?** Only because it gets availability features: XGBoost with availability beats Elo by 0.0081, but not credibly (DM p = 0.075), and
   the same XGBoost without availability does not (+0.0011 worse than Elo).
2. **Does XGBoost beat logistic regression?** No. Worse by 0.0069 with availability and 0.0042 without, both credible by interval.
3. **Is any gain credible and stable?** The availability gain for logistic is: -0.0107 (2025) and -0.0132 (2026). The Bayesian hierarchical check puts the
   availability-shortfall coefficient at 0.164, 0.161, 0.162, 0.174 across 2023 to 2026 (between-season SD 0.054, R-hat 1.005, effective sample size above 1,000).
4. **Which availability signals carry information?** The availability shortfall (who is expected not to play): removing it costs +0.0095 log loss in logistic
   (95% interval +0.0056, +0.0133; both seasons). Full-health player quality adds +0.0025 (interval +0.0000, +0.0052). Missing rotation minutes is bundled
   with the shortfall. Once player ratings are present, Elo adds nothing (change -0.0001), recency +0.0009 and rest +0.0012 (neither interval excludes zero).
   Opponent-adjusted efficiency does not help (+0.0011 worse).
   The gain is concentrated where it should be: in the third of games with the largest availability gap the gain is 0.0234, versus 0.0069 and 0.0084 in the other thirds.
5. **Calibration.** Reliability term of the Brier score: 0.0007 (logistic with availability), 0.0001 (XGBoost with availability), 0.0012 (logistic base). Slopes:
   0.95 (logistic with availability, slightly over-confident), 1.02 (XGBoost with availability). The probability-of-playing model is well calibrated:
   Out 0.2% observed vs 0.3% predicted, Doubtful 1.8% vs 2.6%, Questionable 49.2% vs 47.9%, Probable 91.6% vs 91.3%.
6. **Stability.** See question 3. Both test seasons agree in sign for every pre-registered comparison.
7. **Unproven:** see limits.

## The play-probability model (walk-forward, fitted on earlier seasons)

Log loss on player-games: 0.311 (2023), 0.306 (2024), 0.303 (2025), 0.293 (2026), against 0.45 to 0.43 for a status-rate lookup and 0.68 for a constant.
"Questionable" is a coin flip (49% played), "Doubtful" is almost always out (2%), "Probable" plays 92%. Reason matters: see `docs/NBA_AVAIL_PLAYMODEL_EVAL.json`.

## Coverage and timing audit

| Source | Coverage | Timing evidence | Limits |
|---|---|---|---|
| ESPN play-by-play (SportsDataverse release) | 2016-2027 downloaded and hashed; reconstructed lineups used for 2021-2027 | Per-event `wallclock` exists; the file itself was retrieved 2026-10-28 | 2019 and 2020 fail reconstruction in 30% of games; not used |
| Reconstruction quality (2021+) | 98.9% to 99.6% of games reconstructed per season; final score matches in 99.92% of reconstructed games; 99.92% of player-games within 1 minute of ESPN box minutes | n/a | 4 to 14 games per season dropped |
| Official NBA injury report PDFs | 2021-22 to 2025-26: 816 game days, 1,631 PDFs, every game day covered | File name and header time are publisher stamps; `available_at` precedes tipoff for every row | Later games on a day see the same early report; unmatched player rows 0% to 1.5% by season |
| ESPN player boxes | 2021-2027 | tipoff + 24 h proxy | Revised retrospective copies |
| Team box scores | 2015-2027 | as in the previous study | Cross-check only |
| NBA CDN and stats.nba.com | Blocked from this machine | n/a | Not used |
| ESPN pregame spread (in the play-by-play files) | all test games | capture time unknown | Benchmark only, never a feature |
| Free closing moneylines; public Elo history for 2025-26 | Not found (538 shut down) | n/a | Comparison not done |

Times per record: event time = game date (ET); publication time = injury `available_at` (publisher stamp) and, for results, the next-day rule;
retrieval time = October 2026 for all history; prediction cutoff = first tipoff of the ET day minus 60 minutes.
No historical publication time can be proven for ESPN box scores or play-by-play. Claims are limited to "computable from this archive under the stated rule".

## Verification

- **Randomized-outcome leakage test** (`tests/test_nba_avail_leakage.py`): every outcome-bearing table dated on or after a refit day (results, player minutes,
  stint points and possessions) is scrambled; features for more than 500 earlier games match to 1e-9. A power check confirms later features do respond.
- **Mutation tests**: a planted same-day history leak and a planted same-day ratings leak are both detected.
- **Independent reimplementation** from a written specification (`docs/NBA_AVAIL_FEATURE_SPEC.md`) by a separate agent that was barred from reading the primary code
  or outputs: 4,919 of 4,919 games produced, all four features agree with the primary run to within 1e-11 (correlation 1.0). The agent's code reads only the permitted raw inputs.
  What this does and does not show: it shows the code implements the specification without bugs. It cannot show the specification is sound; the specification came
  from the same author. It shares the parsed injury table and the ESPN player-box cache with the primary run, so those parsers are not independently verified.
  The agent listed 12 specification ambiguities (`research_nba_xgb/second_impl/AMBIGUITIES.md`); none changed a result.
- **Independent evaluation** (`nba_xgb/independent_eval.py`): imports nothing from the package, rebuilds outcomes from the raw archive, matches all 2,459 games
  across all models, zero probabilities outside (0,1), zero cutoffs at or after tipoff. Outputs: `research_nba_xgb/AVAIL_INDEPENDENT_EVAL.json`, `AVAIL_VS_MARKET_EVAL.json`.
- **Day-by-day replay**: `nba_xgb/avail_replay.py` replays 327 game dates in 2025 and 2026. For every weekly rating refit the design is rebuilt from stints dated before that day only
  (112,073 player ratings compared, maximum difference 3.6e-14). For every game date all results, player boxes and later schedule are hidden and the candidates and features
  are rebuilt; 2,459 of 2,459 games compared, maximum feature difference 3e-12, refit days identical (`research_nba_xgb/AVAIL_REPLAY_CHECK.json`).
  The first version of this check was vacuous: its weekly grid started on a different weekday than the batch grid, so no ratings were compared and features differed by up to 2.7.
  That was a flaw in the check, not in the pipeline. I fixed the grid and added an assertion that fails when nothing is compared.

## Limits and unresolved uncertainty

1. **2025 and 2026 are not clean.** The earlier team-strength study already scored them, and its ablations ran there. The availability design was fixed before player features
   touched any win outcome, but the research group has seen those seasons. Only the live 2026-27 season can confirm.
2. **Power.** 2,459 games detect about 0.0045 at 80% power; a true 0.003 effect needs about 5,600 games. The availability effect (0.012) is far above this;
   the XGBoost-minus-logistic gap (0.007) is above it too; smaller effects, in either direction, are not excluded.
3. **Short history for the new features.** Player features exist only from 2023 (injury reports start in 2021-22; the first season is needed to fit the play model).
   The development fold (2024) had one season of availability-labelled training rows; fold 2025 had two; fold 2026 had three. XGBoost may be starved of data that logistic does not need.
4. **Publication times for ESPN data are unproven**, and 2019-2020 play-by-play could not be reconstructed, so ratings start in 2021.
5. **Rating quality.** Ridge RAPM on about five seasons is noisy; unrated players are treated as average (0), which flatters fringe players.
6. **Benchmark.** The ESPN spread benchmark is approximate (capture time unknown, a spread converted to a probability on earlier seasons), not a verified closing moneyline,
   and it is better than every model here by at least 0.0126. Availability closes about half of the 0.025 gap between team-strength logistic and this benchmark; the rest is unexplained.
7. **Realized minutes were not a better signal than expected minutes.** The "oracle" diagnostic using actual minutes scored 0.5928 against 0.5884 for expected availability:
   it is not an upper bound, because realized minutes depend on game flow.
8. Hyperparameters for the availability logistic sit at the edge of the grid (C = 0.003).
9. Day-by-day replay used the batch candidate table for seasons before the replayed one (they cannot depend on dates inside the later season).

## Live 2026-27 forecasts

`python -m nba_xgb.avail_daily --date YYYY-MM-DD` refreshes the inputs, rebuilds everything as of that moment, and writes an immutable, hashed forecast
(`research_nba_xgb/live/forecast_<date>.csv`, listed in `live/MANIFEST.csv`). It refuses to run after the day's first tipoff minus 60 minutes unless `--late` is passed,
and then labels the file LATE. Forecasts must be committed before tipoff to count. 

**Status: no live forecast has been issued yet.** The script `nba_xgb/avail_daily.py` is written but has not been run end to end. Refreshing schedules, boxes and ESPN files worked, but
`nba_lab.injury_reports collect --start 2027 --end 2027` did not finish within its 30-minute limit and was stopped; the existing injury cache was left unchanged.
Tonight's games (2026-10-28) started too soon to be forecast legitimately. The next possible pregame forecast is 2026-10-29: first tipoff 8:00 pm ET, so the cutoff is 7:00 pm ET.
Until live forecasts exist and are scored, nothing in this document counts as confirmation.

## Reproduce

```
.venv\Scripts\python.exe -m nba_xgb.pbp                 # stints (2019-2027; only 2021+ used)
.venv\Scripts\python.exe -m nba_xgb.rapm                # ratings and tuning
.venv\Scripts\python.exe -m nba_xgb.availability        # play model, candidates, features
.venv\Scripts\python.exe -m nba_xgb.avail_study freeze  # development fold, writes docs/NBA_AVAIL_FROZEN.json
.venv\Scripts\python.exe -m nba_xgb.avail_study test    # one-pass test predictions (refuses to overwrite)
.venv\Scripts\python.exe -m nba_xgb.avail_analysis
.venv\Scripts\python.exe -m nba_xgb.market_benchmark
.venv\Scripts\python.exe -m nba_xgb.bayes_check
.venv\Scripts\python.exe nba_xgb\independent_eval.py research_nba_xgb\avail_batch_predictions_2025_2026.csv --pairs "logit_avail:logit_base,xgb_avail:logit_avail,xgb_avail:elo_cal"
.venv\Scripts\python.exe -m nba_xgb.avail_replay
.venv\Scripts\python.exe -m pytest tests/test_nba_xgb_leakage.py tests/test_nba_avail_leakage.py
```
