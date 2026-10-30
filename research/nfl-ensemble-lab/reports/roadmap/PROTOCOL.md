# Research checklist protocol (written 2026-10-30, before any step below was run)

Scope: winners, spreads (margin), totals and player props. Local only, $0, Kalshi read-only, no trading code, no
sportsbook closing lines (no timestamps, so not used without asking). No library installs: numpy, pandas, scipy only.
Each step has a pass condition and an output file. A pass condition is about whether the step was valid, not whether the
result was good. If a step fails, the chain stops and the failure is reported.

## Fixed definitions

- Market price for a game: the last Kalshi hourly candle with `ts <= cutoff` (candle `ts` is Kalshi's `end_period_ts`,
  read from `lab/kalshi.py` lines 155-167), home and away mids de-vigged to sum to 1. Three cutoffs: the model's own
  decision time (`decision_utc`), T-90 minutes before kickoff (the lab's `LEAD`), and close (the last candle at or before
  kickoff).
- Scores: log loss for winners; normal CRPS (closed form) for margin and total; the lab's threshold score
  (sum of squared errors over ladder thresholds) for props.
- Week is the cluster. All intervals resample whole (season, week) groups, 2,000 draws (500 inside simulations), seed 0.
- Variants tried (the full count that Step 7 corrects for): winners = the 8 existing walk-forward columns `p_elo`,
  `p_xgb_v1`, `p_margin`, `p_xgb_deep` and their four `_platt` versions; margin and total = `L` (the joint model),
  `naive`, and the Elo-implied mean for margin; props = the existing scored arms `K`, `A`, `base`, `K_v1`, `A_v1`.
  No new model is fit in this protocol. Nothing outside this list may be added without a new protocol.

## Steps

| # | Step | Output file | Pass condition |
|---|---|---|---|
| 1 | Hash every input and the code that reads it | `step1_inputs.json` | Every listed input exists and has a SHA-256; the protocol hash and git HEAD are recorded; any input modified since the earlier winner-ceiling run (`q1_winner_ceiling.json`) is listed. |
| 2 | Ceiling and power per target | `step2_ceiling_power.json` | (a) Winner ceiling and calibration computed with a week-clustered interval; (b) margin and total ceilings from at least 100 game ladders each, props from at least 500 ladders; (c) in the power simulation, the false-positive rate for "model beats market" at the null is between 0.5% and 5% (one-sided, nominal 2.5%); (d) the smallest detectable gain at 80% power is reported for each target with the sample used. Results are marked conditional on "the market is the truth". |
| 3 | Matched-time comparison | `step3_matched_time.json` | At least 300 winner games have a market price at decision time, at T-90 and at close, and the decomposition `model - close = (model - market at decision) + (market at decision - market at close)` holds to 1e-9. Margin and total are compared at T-90 only (the cached ladders have no earlier point); that limit is recorded. |
| 4 | Point-in-time audit with planted leaks | `step4_point_in_time.json` | (a) The lab's existing perturbation audit passes on its four weeks and its negative control fires; (b) planted leaks are detected: feature cutoff late by 24 hours, 72 hours and 8 days (all must be detected), 1 hour and 6 hours (detection reported, not required), and corrupted Kalshi candles after the cutoff plus 1 hour (must be detected); (c) clean runs are never flagged; (d) each of the six inputs gets a status: tested clean, tested and leaking, or not testable with the reason. |
| 5 | Market as the null | `step5_encompassing.json` | Bootstrap converged in at least 98% of draws; effective sample size (games divided by the week design effect) is at least 100 for the winner tests; every coefficient has a 95% week-clustered interval. |
| 6 | Placebos and caps | `step6_placebos.json` | (a) Shuffled-label false-positive rate of the Step 5 test is between 1% and 9% (nominal 5%, two-sided); (b) the time-shifted placebo interval covers 0 in at least 90% of shifts; (c) junk columns reach nominal p < 0.05 in 2% to 9% of cases and BH discoveries are 0 in at least 95% of reps; (d) planted edges are detected within 0.15 of the rate Step 2 predicts for the same gain; (e) a written stop condition and variant cap per question is recorded. |
| 7 | Selection correction | `step7_selection.json` | White's Reality Check and Hansen's SPA are computed over every variant in the list above (the count is recorded and must equal the list); probability of backtest overfitting is computed with the stated number of week blocks; a family with fewer than 10 week clusters is computed but marked invalid. |

## Stop conditions and caps per question

| Question | Stop condition | Variant cap |
|---|---|---|
| Winners | Stop and record a negative result if the model's weight in the encompassing regression has a 95% interval containing 0 at the sample reached (the market already holds what the model knows). | 8 (the existing columns) |
| Spreads and totals | Stop if the model's CRPS is worse than the ladder's at T-90 with an interval excluding 0, or the interval is wider than the smallest detectable gain. | 3 for margin, 2 for total |
| Props | Stop if fewer than 10 week clusters exist (the interval is then not trustworthy), or if the market ladder beats every arm. | 5 (the existing arms) |
| Point-in-time | Stop the whole chain if a planted 24-hour leak is not detected. | 0 new tests beyond Step 4 |

## What each result is not

A scoring improvement is not a return. Ceilings computed from market prices assume the market is the truth and are not
hard limits. Nothing here uses undated closing lines. Results from this lab are provisional until rebuilt by someone
else (`docs/VERIFICATION.md`).
