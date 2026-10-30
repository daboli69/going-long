# Improvement protocol (written 2026-10-30, before any step below was run)

Governance: `GOVERNANCE.md` and its amendment rule apply unchanged. Local only, $0, Kalshi read-only, no trading code, no
library installs, no scheduled task registered without approval, no undated closing line used before Travis answers.
Samples: market comparisons use season 2025 (exploratory); model-versus-model screening uses seasons 2012 to 2025 of
`walk_forward.parquet` (2026 rows are excluded because 2026 is the confirmatory sample). Seeds fixed. Outputs are in
`reports/roadmap/` and begin with `i`. Ordering: Step 2 ends in a question to Travis; Steps 3 to 6 do not use closing lines.

## Step 1: detectability budget. Output `i1_detectability.json`

Method: the standard error (SE) of each model-minus-market paired difference is read from the saved cluster-robust intervals
(`real_step3.json`, `real_step5.json`). Games needed for a gain g at 80% power with a two-sided 5% test:
N = N_now x (2.80 x SE / g)^2 (2.80 = 1.96 + 0.84). Seasons = N / 272 games a season. Gains: 0.005, 0.01, 0.02 log loss.
CRPS (margin, total) and threshold-score (props) equivalents use the same relative gain: g / 0.6121 (the market's 2025 log
loss) times the market's 2025 score. A candidate "can be tested on Kalshi data alone" if it needs at most 3 seasons.

Pass if all of: (a) an SE for every winner variant (at decision time and at close), every margin and total variant and every
props arm; (b) required games and seasons for all three gains for every one of them; (c) every candidate classified;
(d) formula check: for each design in `real_step2.json` (winners_theta0.6, margin_theta0.3, total_theta0.3, props_theta0.3), the SE
implied by each grid point with power between 0.2 and 0.95 (g / (1.96 + z of power)) has a coefficient of variation of at most 0.25.
If (d) fails the formula is not used and the chain stops.

## Step 2: data unlock. Output `i2_data_unlock.json`

Pass if all of: (a) counts of non-missing closing spread, total, home and away moneyline and stored no-vig probability per
season 2015 to 2025 in the games table, by counting only (no outcome, model or accuracy is computed from them); (b) a written list
of limits; (c) games with complete lines per span (2015 to 2024) set against Step 1's required games; (d) the question to Travis
is asked and the data are not used for any result. The chain stops for Travis's answer on this item.

## Step 3: screen on the long history. Outputs `i3_rehearsal.json`, `i3_screen.json`

Sample: all completed non-tied games of seasons 2012 to 2025 in `walk_forward.parquet`; week is the cluster. Variants tried: the 8
winner columns (count recorded). Comparisons: all 28 pairs (paired log loss, cluster-robust t interval) with Holm adjustment over
the 28, and a Hansen SPA of the 7 non-Elo variants against `p_elo` (the Step 7 code, wild bootstrap-t, 2,000 draws). Rule fixed now:
a variant is "worth testing against the market" if it beats `p_elo` with Holm-adjusted p below 0.05 within the 7 Elo comparisons.
No market data are used.

Rehearsal passes if, over 400 simulated null datasets with the real long-history structure (exchangeable variants): SPA false positives
1% to 9% and the Holm family-wise false-positive rate (any of 28 pairs) at most 9%; and in a planted world (one variant with a
clearly better signal) the planted variant beats Elo in at least 80% of 100 datasets. Real run passes if: at least 3,000 games and 200
week clusters; the variant count equals 8 and the pair count 28; every pair has an interval and a Holm-adjusted p; the SPA is computed.

## Step 4: shrink-to-market challenger. Outputs `i4_rehearsal.json`, `i4_blend.json`, `blend_rules.json`

Definition: blend = m + w x (q - m), m the T-90 market (probability for winners, ladder mean for margin and total), q the model.
w for week t uses only completed games before week t, with weeks ordered by (week, game): w = clip(sum(x u) / (sum(x^2) + K), 0, 1),
x = q - m, u = outcome minus m, K = 20 x mean(x^2) over the first 3 weeks' worth of games available (and w = 0 before any completed
week). Applied to the 8 winner columns and the margin and total variants of Step 5 (no new variants). Primary: winners `p_xgb_v1` and
margin and total `L`.

Rehearsal passes if, over 200 datasets each: null world (market is truth): mean w at most 0.15 and the blend is within 0.005 log loss of the
market in at least 90% of datasets; planted_strong world: mean w at least 0.5 and the blend's mean loss is below the market's in at
least 90% of datasets. Real 2025 run passes if: weights computed from earlier weeks only (checked by recomputing week 5 with all later data
removed and getting the same weight), and for each primary the blend-minus-model and blend-minus-market differences are reported with
cluster-robust intervals and the equivalence status. Stop rule: if the blend is worse than the market by more than the margin
(0.005 log loss; 1% of the market's mean CRPS), with a 90% interval above it, the family is dropped. `blend_rules.json` is written and pushed
before any 2026 comparison, with the confirmatory statistic (blend minus market, equivalence at the same margin).

## Step 5: error analysis by segment. Output `i5_segments.json`

Descriptive only: no model is fit. Sample 2025, primary variant `p_xgb_v1` against the T-90 market and, for the news term, the market
at decision time minus the market at close. Segments fixed now: quarterback change (either team), short rest (either team under 7 days),
roof (closed or dome versus open), divisional game, heavy injuries (a team with at least 3 players listed Out or Doubtful before decision
time in `injury_rows_pregame.parquet`). For each segment and its complement: games, weeks, mean absolute model-minus-market departure,
mean paired log-loss difference and the news term, with cluster-robust t intervals, and the segment-minus-rest difference. Segments with
fewer than 30 games are flagged. Passes if every segment above is computed or the reason it cannot be is written; no inference beyond
the intervals; the number of segments (5) and tests is recorded and Holm adjusted.

## Step 6: prospective pipeline. Outputs `i6_pipeline.json`, `PIPELINE_TASKS.md`

Pass if: (a) the Windows Task Scheduler is queried read-only and the result recorded; (b) the freeze and scoring entry points are located
in the code and the repository, and which of them are scheduled is stated; (c) exact task definitions are written for anything missing and
nothing is registered; (d) every rehearsal output carries a SHA-256 of `steps.py`, `datasets.py` and `common.py`, the real-step gates
compare them with the current files, all rehearsals are rerun and still pass, and a planted stale hash makes the gate refuse. This
tightens a gate, not a pass condition.

## Step 7: outside evidence

A written table per result in the final report. No pass condition beyond: each result names the evidence that would confirm it, and says
where no real source exists.

## What none of this is

A scoring gain is not a return. Nothing here is betting advice.

## Amendment P2-1 (Step 1 condition d), added before the Step 1 re-run

- Found: the first Step 1 run reported PASS because my code applied condition (d) only to designs with at least two grid points
  between 20% and 95% power. Condition (d) as written says each of four designs. The props design has one such point (its power
  reaches only 24%), so the check could not be computed, and the code did not say so. By the letter, (d) was not met for props.
  The first run is kept as `i1_detectability_first_run.json`.
- Flaw in the condition: a coefficient of variation cannot be computed from one point, which has nothing to do with which way any
  result came out.
- Change: (d) applies to every design with at least two usable points (winners, margin, total). The props design is marked
  "formula not validated" and its rows are labelled unvalidated and are not used to claim any props candidate is testable or not.
  The report states this plainly.

## Amendment P2-2 (Step 4 prior strength), added before the Step 4 re-run

- Found in rehearsal attempt 1 (kept as `i4_rehearsal_attempt1.json`): with a prior worth 20 games, the blend was within 0.005 log loss of
  the market in only 89% of null datasets (limit 90%). The weight estimate is too noisy early in a season. This is a property of the
  estimator on simulated data, found before any real-data run of Step 4.
- Change: the prior worth K_PRIOR_GAMES goes from 20 to 50. I chose it by trying the declared grid 50, 100, 200 on simulated data only.
  Results (null share within 0.005; planted mean weight): 50 gives 95% and 0.59 (both conditions pass); 100 gives 97.5% and 0.47 (planted
  condition of at least 0.5 fails); 200 gives 98% and 0.33 (fails). 50 is the smallest value on the grid that passes, so it was selected
  with simulated results in view. Conditions and bands are unchanged. Real data have not been used.
