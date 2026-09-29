# Results-driven safeguards — September 29, 2026

The live 80/20 projection policy is preserved. This change does not retrospectively
rewrite probabilities, delete losing selections, or claim a validated betting edge.

## Calibration

`scripts/calibration_audit.mjs` evaluates one simple shadow model: logistic
intercept/temperature recalibration, with a ridge prior favoring the original
probabilities. Each game has equal total training weight so multiple props and
alternate lines cannot dominate the fit. At least ten earlier games are required.
Training only uses automatic binary settlements published before the original
forecast timestamp, never merely before its kickoff. Refunds are excluded from
binary diagnostics and probability is conditioned on no refund.

Training and display separate legacy, role-aware equal-weight, and current 80/20
cohorts. An 80/20 policy with zero current games remains an 80/20-policy fallback,
not a legacy prediction. Historical current-only samples are not mislabeled as
the new policy. First observations remain immutable within each cohort.

Current legacy replay (Brier, lower is better):

| NFL market | Later contracts | Games | Original | Shadow |
|---|---:|---:|---:|---:|
| Receiving yards | 392 | 17 | .2498 | .2447 |
| Rushing yards | 167 | 17 | .2785 | .2643 |
| Receptions | 196 | 17 | .2285 | .2342 |
| Passing yards | 117 | 17 | .2639 | .2519 |
| Passing TDs | 33 | 17 | .2521 | .2614 |
| Anytime TD | 107 | 16 | .1567 | .1501 |

This is a chronological development diagnostic, not an independent profitability
claim. Improvement is inconsistent and the current 80/20 cohort has no settled
calibration evidence yet. Nothing is promoted into live pricing. New predictions
freeze a shadow estimate when same-cohort training supports one.

New records also freeze same-book two-sided references where available. Historic
records lacking those prices have no reconstructed devig benchmark. Paired raw,
shadow, and book error are compared on the identical available subset.

## Workload and recommendation framing

New forecasts retain expected attempts, carries and targets, the projected stat,
season weights and QB role evidence. New settlements retain actual opportunity
counts. The report decomposes signed error into volume and efficiency components
only when both denominators are observed and positive. This is an algebraic
diagnostic, not proof that an input caused an outcome. No old workload forecasts
are reconstructed using later knowledge.

Cards and Results use “model-screened research,” not validated-value language.
Sample size alone no longer earns a “Higher” confidence label. Existing no-stake
trust safeguards remain. The full research population stays available.

## Settlements

The former 90-second kickoff match rejected real games when sportsbook kickoff
times drifted several minutes. Matching now requires one unique official matchup
on the same Eastern calendar date. Ambiguous games and predictions captured after
the official kickoff remain ineligible. Missing player appearances/statistics are
not inferred to be zero and book-specific void rules are not invented.

The initial rebuild reconciled 98 tracker records, including 23 model-screened
selections. Remaining unresolved counts are published with reasons: 25 model-
screened selections, 69 records across groups, lack player participation/results.
Previously frozen predictions and existing settlements were not changed.

## Price observations and automation

The existing `Refresh Going Long data` workflow runs at 10:20 and 22:20 UTC daily,
as well as manual dispatch and relevant code pushes. It freezes/grades the tracker
and produces these reports automatically. No personal computer or browser is
required; no extra paid API requests were introduced.

The collector also emits compact quote-only rows for same-book, same-player,
same-market, same-line, same-side observations. Quotes must be observed before
kickoff, later than the frozen prediction, and no more than ten minutes old at
capture. Near-kickoff labeling additionally requires the quote itself to be within
ten minutes of kickoff. Duplicate observations and post-kickoff backfills are
rejected. Two-sided references are required for a devigged price-movement metric.

The twice-daily schedule cannot guarantee actual closing prices. Zero qualifying
samples in the initial rebuild is reported as zero, not invented coverage. A
higher-frequency pre-kickoff capture would require a separately budgeted feed
cadence change. Same-game correlations and book-specific settlement rules remain
limitations.
