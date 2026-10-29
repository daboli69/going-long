# Is the availability signal real, and does it survive the market? Pre-registration (frozen 2026-10-28 before any of the analyses listed under "Not yet run")

Question: after accounting for what a market benchmark already knew, does official injury-report availability information improve pregame NBA
home-win probabilities, and does any nonlinear model add to a regularized linear one? Nothing else.
Closing probabilities are a scoring benchmark and an encompassing-test partner only, never a feature.

## What has already been seen (so the reader can discount it)

- Earlier studies (`docs/NBA_XGB_RESULTS.md`, `docs/NBA_AVAIL_RESULTS.md`) scored the seasons 2025 and 2026 for team-strength and availability models, including
  ablations, a market-spread comparison and a Bayesian effect check. Those seasons are **seen**. Retrospective results on them are exploratory.
- Everything in the first 20 percent of this phase (collector fix, source audit, timing ledger, rating reliability, power simulation) was run before this document; none of it scored
  a win probability. Their results are quoted below.
- Design choices for everything listed under "Not yet run" may use only seasons up to 2024. **The confirmatory sample is the live 2026-27 regular season**, scored once at the end.

## Sources and what could not be obtained (checked 2026-10-28, `research_nba_xgb/SOURCE_PROBES_20261028.json`)

| Source | Result | Timing evidence | Status |
|---|---|---|---|
| Official injury-report PDFs, every version | Obtained for 2021-22 to 2025-26 (about 18 versions per game day, 1.17M rows) and for 2026-27 days to date | File name and header stamp; `available_at` precedes tipoff in every checked row | Used |
| ESPN play-by-play (SportsDataverse release) | 2016-2027 downloaded, lineups reconstructed for 2021 onward | Per-event wall clock; file retrieved 2026-10-28 | Used; 2019-2020 not reconstructable |
| NBA CDN play-by-play, boxscore, schedule (cdn.nba.com) | HTTP 403 Access Denied with browser-style headers | none | **Blocked from this network** |
| NBA game-rotation, play-by-play V3, boxscore V3 (stats.nba.com) | Read timeout on three endpoints | none | **Blocked from this network** |
| Pregame inactive and starter announcements | Not reachable (same NBA hosts) | none | **Not obtained** |
| Raw timestamped closing lines | No free, timestamped, licensed archive for 2022-2026 found. The SBR archive is gone; The Odds API needs a key and a paid tier for history; ESPN scoreboard, summary and core APIs return no odds for upcoming games | none | **Not obtained** |
| ESPN pregame spread embedded in the play-by-play files | Present for every 2022-2026 game | **Capture time unknown** | Approximate benchmark only |
| Arena locations and official schedule | Schedule in the canonical table; arena coordinates not collected | schedule file stamps | Schedule only |
| Wayback CDX | Reachable (snapshots of the official injury index page exist) | snapshot stamps | Used as a time witness |

Consequence: "survives the market" cannot be settled with a verified closing line. Any statement below that uses the ESPN spread is stated as "survives an approximate
benchmark of unknown capture time". If that spread was captured before late injury news, a positive result partly reflects a stale benchmark, not model skill.

## Facts already established in this phase

- Timing ledger (`research_nba_xgb/TIMING_LEDGER_SUMMARY.json`, 6,149 games 2022-2026): for 65.3% of games a newer injury-report version existed by that game's own tipoff than the one in force an hour before the
  day's first tipoff (mean 2.7 newer versions); 30.5% of games had at least one status change; **14.2% had a rotation player move between "may play" and "unlikely to play" (13.8% newly out)**.
  The share is 20.4% for 9-10 pm tips and 2.4% for tips by 2 pm. The earlier availability study used the first-tipoff version for every game, so it did not see these late changes.
- Rating reliability (`RATING_RELIABILITY.json`): single-season ridge ratings, split by game parity, half-to-half correlation 0.37-0.43, Spearman-Brown reliability 0.54-0.61 (2022-2026). They are about 55-60% signal.
- Power simulation (`POWER_SIMULATION.json`, 400 replicates per cell, Diebold-Mariano with Newey-West variance on daily means, alpha 0.0167, date resampling):

| True log-loss gap | 1,230 games (live season) | 2,459 games (2025+2026) | 3,689 games | 5,000 games |
|---|---|---|---|---|
| 0.0026 | 9% | 11% | 18% | 20% |
| 0.0051 | 24% | 46% | 67% | 79% |
| 0.0098 | 77% | 97% | 100% | 100% |
| 0.0141 | 98% | 100% | 100% | 100% |

  Rejection rate at a true gap of zero: 1.5% to 3% (nominal 1.67%), so the test is correctly sized. By interpolation, 80% power needs a true gap of about **0.011 for 1,230 games, 0.008 for 2,459, 0.007 for 3,689
  and 0.005 for 5,000**. These supersede the 0.0045 figure in `docs/NBA_AVAIL_PREREGISTRATION.md`, which used a normal approximation at alpha 0.05 without the Bonferroni level or the date clustering.
  The XGBoost-versus-logistic simulation gives the same picture (0.32 power at a gap of 0.0045 with 2,459 games).

## Primary hypothesis (one)

H1. Let `z_m` be the logit of the market benchmark and `z_a` the logit of the frozen availability logistic model that uses, for each game, the last injury-report version published at least 60 minutes
before that game's own tipoff. In the encompassing regression `P(home win) = logistic(alpha + b_m * z_m + b_a * z_a)`, **b_a > 0**.

- Test: Wald test on b_a with standard errors clustered by game date, one-sided, alpha 0.05, plus the out-of-sample comparison "market + availability stack (fitted on earlier seasons) versus market alone" with Diebold-Mariano (Harvey small-sample correction), one-sided, alpha 0.05.
- Data: confirmatory = 2026-27 live games, one test at the end of the regular season, no interim looks and no stopping rule. Exploratory = 2025 and 2026 retrospective games.

Decision rules (written before looking):

| Outcome | Reading |
|---|---|
| b_a > 0, Wald and DM both significant, same sign in each retrospective season | "Availability adds information beyond the approximate benchmark" (retrospective, exploratory). Upgraded to confirmed only if the live test also passes. |
| Interval for b_a includes zero | "No evidence that availability adds information beyond the benchmark." Report the detectable effect from the power table (about 0.008 for 2,459 games, about 0.011 for the live season) and say smaller effects are not excluded. |
| b_a < 0 significantly | "The model is noisier than the benchmark; availability does not help on top of it." |
| Retrospective seasons disagree in sign or the live sample disagrees with the retrospective one | Inconclusive; no claim. |

## Secondary hypotheses (reported, never used to rescue H1)

- H2, nonlinearity. Fitted on seasons up to 2024 only with the same features as the linear model: a GAM with pairwise interactions, an Explainable Boosting Machine, and XGBoost
  (`binary:logistic`, depth 1 to 4, monotone constraints, pre-registered search of at most 30 configurations, early stopping by log loss on a chronological validation season).
  A nonlinear model "adds" only if the `arch` superior-predictive-ability test (null: no alternative beats the regularized logistic) gives p < 0.05 and the best alternative also leads in both retrospective seasons.
  Interaction audit: Friedman's H for every feature pair in the XGBoost model and the pairwise terms of the EBM; "no nonlinearity detected" requires H below 0.05 for all pairs and an EBM pairwise gain under 0.001 log loss.
- H3, timing. The availability logistic with own-tipoff versions beats the same model with first-tipoff versions (DM, one-sided, 0.05).
- Model confidence set (`arch`, 90% level) across all models, including the market benchmark.
- Robustness: a Bayesian state-space team strength model (numpyro) with the availability term added, reported next to the frequentist estimate.

## Not yet run (the content of this phase after the document)

1. Game features rebuilt on own-tipoff injury versions with late-change indicators.
2. Player ratings from possession-level data with box-score priors. Allowed only if split-half reliability on 2022-2024 beats the 0.54-0.61 of the current ratings; otherwise the current ratings stay.
3. The play-probability and expected-minutes model scored walk-forward by status and reason using own-tipoff versions.
4. The GAM, EBM, XGBoost searches, the encompassing regression, SPA, model confidence set, Bayesian robustness and ablations.
5. Live forecasts issued per game at its own tipoff minus 60 minutes, hashed daily and timestamped with OpenTimestamps. Live odds capture is attempted daily (ESPN endpoints) and an empty result is recorded.

## Splits

Design: seasons up to 2024 (ratings penalty and prior weight on 2023; model hyperparameters and calibration on 2024 with fits on 2022-2023; refit annually). Seen: 2025, 2026. Confirmatory: 2026-27 live.

## Verification

Randomized-outcome test, planted-leak mutation tests for ratings, history and timing, and day-by-day replay, each asserting that it compared a non-zero number of items. A written specification reimplemented by a separate agent
without access to the primary code. A person outside the project reproducing one day's forecast from the specification.
