# Pre-registration: sparse-column guard for the scaled prop members

Registered 2026-11-11, before any Week 11 game. This registers a challenger. It changes no published number, and the champion keeps its columns until the test below is read.

## What went wrong

The Week 9 FPDS drop was the first to include running backs in the receiving tables. From 2021 through 2026 Week 8 those tables held no running back rows. For rushing yards, 159 of the 785 input columns were filled in under 1% of training rows and in over 30% of Week 10 rows.

The linear and neural members fill blanks with the training median and divide by the training spread. A column that is almost always blank has a spread near zero, so a real value at prediction time became an input up to about 5,400 standard deviations from the mean. The largest value seen in training was about 50. The neural member's mean running back prediction was 126.6 yards on one training set and 49.6 on another that differed by 47 rows. The tree members were not affected.

## Challenger

`fit_predict(..., min_coverage=0.01)` in `lab/fpds_research/models.py`. Before fitting a scaled member (linear, shrink, distribution, mlp), drop every column that is filled in fewer than 1% of that fit's training rows. Tree members keep all columns. The threshold is fixed at 0.01. Default calls are unchanged.

## Development evidence, already seen

These numbers chose the guard, so they are not a test of it.

- Week 10, neural member: mean difference per player between the two training sets was 95.5 yards without the guard and 3.2 with it.
- Eleven settled weeks (2025 Weeks 15 to 18, 2026 Weeks 3 to 9, 552 player-games), where the mismatch did not exist: mean absolute error for the linear member was 26.73 yards without and 26.73 with; for the neural member 26.74 and 26.44.
- A second guard, clipping scaled inputs to 8 standard deviations, was tried on the same data and is not registered.

## Confirmation test

- Data: 2026 Weeks 11 to 18, stats rush_yds, rec_yds and rec. Both arms are refit from the feature snapshot frozen for each week's published run, with the same training rows and weights, so the only difference is the guard.
- Primary measure: mean absolute error of the stacked projection, guard minus champion, paired by player-game, with a 95% bootstrap interval resampling games.
- Pass: the interval's upper end is below +0.5 yards for rush_yds and rec_yds and below +0.05 receptions for rec, and no guarded member prediction exceeds the highest value in its training labels.
- One look, after Week 18 settles. No change to the threshold, the stats or the measure before then.
- Also report, without a pass rule: the count of columns dropped each week, and champion member predictions above the training maximum.

## Outcomes

- Pass: the guard becomes the default for scaled members, recorded in MODEL_RESEARCH.md.
- Fail: the guard stays off and the result is reported.
- Either way this is a safety check for accuracy, not evidence of a betting edge.

## Open items, not part of the test

- With the guard on, the linear member still moved about 11 yards per player between the two Week 10 training sets. The cause is unknown.
- Some columns are filled in about 95% of training rows and blank for Week 10. The guard does not address that direction.
