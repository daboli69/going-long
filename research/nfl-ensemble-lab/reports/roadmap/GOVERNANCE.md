# Governance for the research checklist protocol (written 2026-10-30, before any run after the Step 2 failure)

This file is committed and pushed alone before Steps 1 to 7 are run again. It does not edit `PROTOCOL.md`
(commit `c78bb642`, SHA-256 of the file is recorded in every output). Where this file changes a rule, it says so.

## What the timestamps can and cannot show

`PROTOCOL.md` was pushed to GitHub in the same push as the Step 1 and Step 2 results (`93d57d54`). GitHub's
server time for that push therefore cannot show the protocol came first. Local commit times prove nothing to a third
party. What the record does show: the protocol is in git history one commit before the results, and the Step 2 failure
was reported before any later run. This file and everything below it is pushed alone, so GitHub's time for it does
precede every later run.

## Amendment rule

1. A pass condition may change only for a design flaw that does not depend on which way the result went (a check that
   is too coarse to tell pass from fail, a sample the new rules no longer allow, a method that cannot work with the
   data's structure).
2. Every change is written here and committed and pushed before the step it changes is run again.
3. The failed or superseded run stays in the record, with its file and commit. Nothing is overwritten.
4. A change may not be made because the result came out the wrong way. If a diagnostic has already shown the likely
   direction, the amendment says so.
5. Simulation counts follow the tolerance: the binomial standard error of a checked rate, evaluated at the edge of its
   band, may not exceed one quarter of the band's width.

## Amendment 1 (Step 2 condition c, simulation counts)

- Flaw: the props false-positive check used 100 simulations. A band of 0.5% to 5% is 4.5 points wide, so a quarter is
  1.125 points. At the 5% edge, 100 simulations give a standard error of 2.2 points, about twice what the rule allows.
  The check could not tell 5% from 10%.
- Change: every false-positive check in Step 2 uses at least 400 simulations (standard error 1.09 points at the 5%
  edge). Band, test, seeds and everything else are unchanged. The change applies to all four targets, not only props.
- Disclosure: the 400-simulation props diagnostic (`step2_diag_props.json`, 4.25%) was run before this amendment, so the
  direction is known. The rerun can still fail, and if it does the chain stops.
- Record: the failed run is `step2_ceiling_power.json` at commit `93d57d54`.

## Amendment 2 (sample split)

- Change: real-data runs of Steps 2 to 7 use season 2025 only (the exploratory sample). The 2026 weeks are held for the
  confirmatory analysis below. Sample floors scale to match: Step 2(b) is unchanged (at least 100 margin ladders, 100
  total ladders and 500 prop ladders within 2025), and Step 3's floor of 300 games becomes 250. No step has been run
  on the 2025-only sample yet.
- Reason: the split was requested after the protocol was written. It does not depend on any result.

## Choices fixed before the next run

| Item | Fixed choice |
|---|---|
| Exploratory sample | Season 2025, completed non-tied games. |
| Confirmatory sample | Season 2026 completed games, analyzed only after `confirmatory_rules.json` is pushed. These predictions were rebuilt by a walk-forward run on 2026-10-28, not frozen at the time. Only the week 8 files in `data/raw/archive/forecast_games` and `props_kalshi` are frozen records. |
| Small-cluster method | Intervals for a mean of paired differences or a regression coefficient use the cluster-robust t interval with clusters minus 1 degrees of freedom (week is the cluster). A null-imposed wild cluster bootstrap (Rademacher weights, 1,999 draws) is reported beside every coefficient test as a cross-check. Decisions use the t interval. Step 2's power simulations keep the protocol's percentile week bootstrap. |
| Smallest effect of interest | Winners 0.005 log loss; margin and total 1% of the mean market normal CRPS; props 1% of the mean market threshold score. The first three follow `scripts/forecast_study.py` lines 182 to 184. |
| Equivalence rule | Paired difference is model loss minus market loss. Equivalent if the 90% interval lies inside the margin; worse by more than the margin if the 90% interval's lower end is above it; better by more than the margin if its upper end is below minus the margin; otherwise undetermined. |
| Quote filters | None (base); spread (ask minus bid) at most 0.05 on both sides; volume above 0 in the used candle on at least one side; both. |
| De-vig methods | Proportional (base), power, Shin. |
| Variants | As in `PROTOCOL.md`: 8 winner columns, 3 margin, 2 total, 5 props arms. |
| Weekly looks | Lan-DeMets O'Brien-Fleming-type spending, two-sided total 0.05, information fraction = completed weeks / 18; the nominal level at each look is the increment of spent error (conservative, Bonferroni over increments). From memory, check before use. |
| Confirmatory primary | One comparison: the winner variant with the lowest 2025 mean log loss, tested by the coefficient on the model in the encompassing regression against the T-90 market. Set in `confirmatory_rules.json` before 2026 is read. |
| Seeds and versions | Real runs seed 0; rehearsal dataset i uses seed 1000 + i. Python, numpy, pandas, scipy and pyarrow versions are recorded in the step 1 output. No installs. |

## Rehearsal pass conditions (written before any rehearsal run)

Simulated worlds reuse the real data's structure (week clusters, market prices, ladder shapes). Null world: the market
equals the truth and every model variant is a noisy copy with no extra information. Planted world: the market is a noisy
copy of the truth and exactly one variant is a better copy.

| Step | Rehearsal passes if |
|---|---|
| 2 | On a null world, every false-positive check at 400 simulations is in 0.5% to 5%; the ceiling-gap interval covers the known gap in at least 90% of 100 datasets. |
| 3 | The decomposition identity holds to 1e-9, and the news term's interval covers its known value in at least 90% of 100 datasets. |
| 4 | The knowledge-time detector flags every planted leak of 24 hours or more and none of the clean tables; the beats-the-market detector has at most 5% false positives over 400 null datasets and flags at least 95% of planted leaks. |
| 5 | The t-interval test of the model coefficient has a false-positive rate between 1% and 9% over 400 null datasets (the wild bootstrap is reported); in the planted world the interval covers the known coefficient in at least 90% of 100 datasets. |
| 6 | Over 100 datasets per world, shuffled-label and time-shift placebos show a false-positive rate between 1% and 9%; junk columns reach nominal p below 0.05 in 2% to 9% of cases; the planted-edge detection rate is within 0.15 of the Step 2 power curve for the same gain. |
| 7 | The selection test (Reality Check and SPA) has a false-positive rate between 1% and 9% over 400 null datasets and rejects in at least 80% of planted datasets; probability of backtest overfitting is between 0.35 and 0.65 in the null world and below 0.25 in the planted world. |

Real data does not enter a step until its rehearsal row passes.

## Decision table

| Step | Outcome | Action |
|---|---|---|
| 2 | A false-positive check is outside its band | Stop. |
| 2 | Gap interval includes 0, or the minimum detectable gain is above the smallest effect of interest | Record "unresolved at this sample". Continue. No claim about headroom. |
| 2 | Interval excludes 0 and the minimum detectable gain is within the smallest effect | Treat the market as miscalibrated at the ceiling. Check the calibration slope and the quote filters before saying more. Continue. |
| 3 | Model worse than the market at decision time, interval excluding 0 | The model is worse at equal information. Continue to Step 5. |
| 3 | Model gap vs the market at decision time includes 0 and the news term is above 0 | The gap against close is explained by news the model could not see. Use only the matched-time design from here on. |
| 3 | Fewer than 250 games with all three prices | Stop. |
| 4 | A planted leak of 24 hours or more is not detected | Stop. |
| 4 | A real input is flagged | Drop that input. Rerun Steps 3 and 5 without it. |
| 5 | Coefficient interval includes 0 and equivalence is shown | Record "the market encompasses the model". Stop work on that target. |
| 5 | Coefficient interval includes 0 and equivalence is not shown | Record "undetermined". Do not claim an edge. |
| 5 | Coefficient interval excludes 0 | Freeze that variant as the confirmatory candidate. No promotion. |
| 6 | Any placebo rate is outside its band | Stop. |
| 7 | SPA p-value 0.05 or above | Negative result: no variant beats the market after allowing for the search. |
| 7 | PBO above 0.5 | Selection is unreliable. No variant is carried forward. |
| Price quality | A conclusion flips under a filter or de-vig method | Report it as fragile. Treat the conclusion as undetermined. |
| Label audit | Disagreement above 0.5% of labels | Stop. Reconcile first. |
| Confirmatory | The statistic crosses the look's boundary | Report as confirmed at that look. Promotion still needs the Champion/Challenger gate in `MODEL_RESEARCH.md` and Travis's approval. |
| Confirmatory | It does not | Keep accumulating weeks. Report the interval. |

A scoring improvement is not a return. Nothing here is betting advice.

## Amendment 3 (Step 7 rehearsal world), added before any rehearsal run

- Flaw: the null world above sets the market equal to the truth, so no model variant can ever tie the market.
  Reality Check and SPA test the boundary where the best variant ties the benchmark. Away from that boundary they are
  conservative, so their false-positive rate would be near 0% and miss the 1% floor for a reason that is not a defect.
- Change: the Step 7 rehearsal (selection test and probability of backtest overfitting) uses an exchangeable world:
  the market and every variant are independent noisy copies of the truth with equal noise (standard deviation 1), so
  every variant ties the market in expectation. The Step 7 false-positive band stays 1% to 9% over 400 datasets and the
  probability-of-overfitting band stays 0.35 to 0.65. Planted-world conditions are unchanged. Steps 4, 5 and 6 keep the
  market-equals-truth null world. Step 2's false-positive checks already use an exchangeable design.
- Status: no rehearsal or real run has happened since the Step 2 failure. The direction of the result is not known.

## Amendment 4 (props floor under the sample split), added before any run on the 2025 sample

- Flaw: Amendment 2 kept Step 2(b)'s floor of 500 prop ladders but applied it to season 2025 alone. I did not check how
  props split by season. The scored ladders are 191 in 13 weeks (weeks 6 to 18) for 2025 and 1,051 in 7 weeks (weeks 1 to
  7) for 2026 (`data/cache/props_kalshi/scored_ladders.parquet`). A floor of 500 cannot be met in 2025 for a reason that
  says nothing about the results.
- Change: Step 2(b)'s props floor in the exploratory sample is 150 ladders in at least 10 weeks. Props inference is
  therefore limited to what 2025 can support: 191 ladders, 13 week clusters, wide intervals. The 2026 props sample is
  larger but has 7 week clusters, which is below the protocol's 10-cluster validity rule, so confirmatory props results
  stay marked invalid until 10 weeks of 2026 exist. Margin, total and winner floors are unchanged.
- Status: no real-data step has been run on 2025 and no rehearsal has run. The direction of any result is not known.

## Amendment 5 (Step 6 placebo definitions and planted-edge strength), added before any rehearsal run

- Flaw: a smoke test on one simulated dataset (not a result about any real model) showed the shuffled-label placebo
  rejected 103 of 160 tests at the 5% level. The encompassing regression uses the outcome minus the market price as
  its dependent variable, so shuffling outcomes leaves the market price inside it and creates a model weight that is not
  zero. Rolling outcomes in time does the same. Neither placebo has a true weight of zero, so a band of 1% to 9% cannot
  be a fair test of the machinery.
- Change: (a) the label placebo replaces outcomes by independent draws from the T-90 market probability (the market is
  the truth, so the true model weight is zero by construction; real model forecasts, week clusters and prices are
  kept); (b) the time-shift placebo keeps each game's market and outcome and gives it the model forecast of another game,
  9 to 28 places away in (season, week, game) order, which is the "time-shifted features" placebo; (c) the junk
  placebo is unchanged. The bands are unchanged: rejection rate 1% to 9% for (a) and (b), the (b) interval covers 0 in at
  least 90% of shifts, junk reaches nominal significance in 2% to 9% of cases with no Benjamini-Hochberg discovery in
  at least 95% of reps.
- Planted-edge strength: rehearsal worlds use a signal scale theta = 0.8 and the planted variant has noise 0.4, which
  gives an expected log-loss gain over the market of about 0.049 per game. That is above the sample's smallest
  detectable gain from Step 2 (above 0.035), so the planted edge is detectable by design. It was chosen from the Step 2
  power results and a one-dataset smoke test, not from any real-model result.
- Status: no rehearsal and no real-data step has run since the Step 2 failure.

## Amendment 6 (after rehearsal attempt 1; no real-data step has been run), added before rehearsal attempt 2

Attempt 1 passed for Steps 3 and 4 and failed for Steps 2, 5, 6 and 7. The files are in `reports/roadmap/attempt1/` with
the code that produced them (`steps_attempt1.py`, `rehearsal_attempt1.py`). Real data has not been used by any step.

| Step | Attempt 1 result | Cause | Change |
|---|---|---|---|
| 2 | False-positive rates 4.25% to 5.75% (limit 5%); gap coverage 98% and 96% | The percentile week bootstrap is liberal with 13 to 18 clusters (nominal one-sided 2.5%, observed about 5%) | Step 2 detection becomes the lower end of the cluster-robust t interval (clusters minus 1 degrees of freedom, 95% two-sided) being above 0. Band, sample counts and seeds unchanged. |
| 5 | t-interval false positives: winners 5.2%, margin 5.5%, total 7.6%, props 11.6%; wild bootstrap 4.9%, 4.8%, 8.1%, 5.1% | The cluster t test is liberal for props at 13 clusters | Coefficient decisions use the null-imposed wild cluster bootstrap p-value below 0.05. The t interval is still reported but is not used for decisions. The 1% to 9% band applies to the wild test. This replaces the "decisions use the t interval" row of the choices table. |
| 6 | Label placebo 5.4%, time-shift 5.75%, interval covers 0 in 94%, junk 5.35%, no-discovery share 94% (needed 95%); planted edge detected 65% against 60% predicted | The "no Benjamini-Hochberg discovery in at least 95% of reps" limit equals the expected value under a correct procedure, so it fails about half the time by construction | Limit becomes 90% (standard error at 100 datasets is 2.2 points, a quarter of a 10-point band). Placebo tests use the wild p-value with 499 draws. Planted-edge detection uses the same t rule as Step 2. |
| 7 | Reality Check false positives 5.5%, 7.0%, 8.0%, 10.2%; SPA 0% everywhere and 0% rejection in the planted world; probability of overfitting 0.50, 0.68, 0.47, 0.62 | SPA code bug: the bootstrap was not centered before applying Hansen's recentering. Separately, the null probability of overfitting depends on the number of variants m: exactly 0.5 for m = 8 and m = 2, 0.6 for m = 5, and 2/3 for m = 3, so a fixed 0.35 to 0.65 band cannot hold for 3 variants. Props Reality Check is liberal at 13 clusters. | Bug fixed. The cluster bootstrap becomes Rademacher cluster multipliers. Decisions use the SPA p-value; Reality Check is reported. The null probability-of-overfitting band is the exact value for m plus or minus 0.10. False-positive band stays 1% to 9% for SPA. |

Real-data note on placebos. The label and time-shift placebos have a true model weight of zero only when the market is
calibrated. In the planted rehearsal world, where the market is noisy, the time-shift placebo rejected 39% of the time.
On real data, a time-shift placebo outside its band can therefore mean the market is miscalibrated at that sample and not
that the machinery is broken. The protocol's rule still applies: outside the band, the chain stops, and the report says
which explanation the diagnostics support.

Audit sensitivity note. In rehearsal the beats-the-market detector found a leak of 0.5 logit units in 100% of datasets,
0.2 units in 8.75% and 0.1 units in 0.25%. Subtle leaks need the structural audit (perturbation of data after the cutoff),
which Step 4 on real data uses.

Status: rehearsal attempt 2 will rerun Steps 2, 5, 6 and 7. Steps 3 and 4 passed in attempt 1 and are not rerun.

## Amendment 7 (after rehearsal attempt 2; no real-data step 2, 5, 6 or 7 has been run), added before attempt 3

Attempt 2 (files in `reports/roadmap/attempt2/`, with `steps_attempt2.py` and `rehearsal_attempt2.py`) passed Steps 5 and 6
and failed Steps 2 and 7. Steps 3 and 4 passed in attempt 1.

| Step | Attempt 2 result | Cause | Change |
|---|---|---|---|
| 2 | False positives: winners 1.25%, 1.0%; margin 5.0%, 5.25%; total 2.75%, 2.75%; props 6.5%, 7.5% (limit 5%) | The cluster-robust t interval is still liberal for margin and props at 13 to 14 clusters with heavy-tailed per-unit differences | Detection is a one-sided 2.5% null-imposed wild cluster bootstrap-t (Rademacher weights, 499 draws) on the paired mean difference, the same family of method the Step 5 decisions already use. Band, sample and seeds unchanged. |
| 7 | SPA false positives 12.8%, 10.7%, 10.0%, 25.3%; Reality Check 6.5%, 7.2%, 8.0%, 13.5%; planted rejection 41% on winners | The bootstrap divided every draw by one fixed standard error, so it ignored the sampling error of the standard error, which matters at 13 to 18 clusters. | The selection tests become studentized: each wild bootstrap draw is divided by its own cluster-robust standard error (bootstrap-t). Hansen's recentering is unchanged. Decisions use SPA; Reality Check is reported. |
| 7 (power) | Planted winners rejection 41% against a limit of 80% | My Amendment 5 claim that the 0.049 planted gain was detectable by design was wrong: at 271 games and 18 clusters the Step 2 design gives about 50% power at that gain | The Step 7 planted conditions use a stronger world (`planted_strong`: theta 1.2, planted variant noise 0.2). Step 2's detection design predicts about 97% power at its gain of about 0.116 log loss per game, from a separate calibration run. Steps 5 and 6 keep the `planted` world. |
| 6 | Passed in attempt 2 | Not applicable | Step 6's planted-edge comparison uses the Step 2 detection rule, so it is rerun with the new rule, with unchanged conditions. |

Rehearsal attempt 3 reruns Steps 2, 6 and 7. Steps 3, 4 and 5 stand. Status: no real-data run of Steps 2, 5, 6 or 7 yet.
Real Step 3 and Step 4 were run (their rehearsals had passed) and are not affected by these changes.
