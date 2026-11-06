# Sportsbooks as noisy sensors of one hidden line: results

Run 2026-11-06 against docs/FUSION_PREREG.md (commit d161b4d7) and Amendment 1 (18c8c998). Football only. No staking or bet sizing.

## Result

No edge found. The method worked as a method (it recovers planted sensor errors), but the sample cannot tell whether the fused line beats the median, and two of its validity checks did not come out the way the idea predicts.

## Gate (before any real result was read)

| Part | Result | Verdict |
|---|---|---|
| Recovery of planted book noise and bias | correlation 0.99, bias error 0.0013 in logs | passes |
| Power to show fused beats median on outcomes | 0.0 at 742 confirm props, 0.01 at 1,484, 0.0 at 2,968 | uninformative, not read |
| Bet test (outlier quote against the fused line) | smallest detectable win-rate edge 0.069 against 0.03 of interest (1,278 outlier bets in 57 games) | uninformative, not read |
| Reversion test | smallest detectable closing share 0.079 against 0.15 | informative |

The scoring test has essentially no power because a better center moves the over and under probability by a tiny amount, compared with the spread of real results. Even at four times the props the planted gain was not detectable.

## What could be read

Fitted on the decide weeks, quotes only:
- Drift from staleness is tiny: q = 8e-7 per hour in log variance, so a 12-hour-old quote adds about 0.3% of noise. Staleness is not the main source of disagreement between books.
- Book noise (log units): the lowest are Fliff 0.004, FanDuel 0.009, Caesars 0.010, Hardrock 0.010, Pinnacle 0.011, ProphetX 0.015. The highest are Novig 0.090 and Bet365 0.048. Novig also carries the largest bias, -1.6%.

Validity checks that were not fit:
- Sharp books should be less noisy than retail. They were not: the sharp set (Pinnacle, Novig, ProphetX) averaged 0.039 against 0.022 for retail, p = 0.67 in the direction the idea needs. Novig, an exchange with jumpy quotes, drives that. So the learned reliabilities do not reproduce the ranking we would expect, and I would not trust the fused weights as a sharpness measure.
- Kalshi: the fused line is closer to the Kalshi median than the plain median is in 53.7% of 1,016 props (p = 0.009), but the average miss is 1.103 yards against 1.116, a 1% difference. Statistically detectable, practically nothing.

Reversion (all weeks, same book and same prop at both snapshots, so the set of legs is matched by construction): 88,295 pairs in 134 games. A book closes 49% of its gap to the fused line between snapshots 6 to 30 hours apart (one-sided 90% interval 0.45 to 0.54). By the registered rule the gap closes. Part of this is mechanical: a quote's noise that does not persist will look like reversion in any regression of this kind.

## Cost check (post hoc, not registered, outcome-free)

`scripts/fusion_cost_check.py`: for 17,582 outlier quotes in 133 games, bet against the book's line at its own odds and value the bet against the fused line at that book's next snapshot. The gross value is +5.0 percentage points over a coin flip. The break-even rate of the odds those quotes carry is 54.9% (average hold 8.8%). Net value is -0.002 (95% interval -0.005 to +0.001). The books that post outlier lines also post worse prices, and the gap closing is paid for by the vig. Nothing is left.

## Not done

- The scoring test and bet test were not read because they failed their gates.
- The placebo that mislabels books was not run because the scoring test was not read.

## Concerns

- The fused line is built from the same quotes it is meant to improve, so the reversion result and the cost check use a target that the quotes themselves shape.
- The odds adjustment uses fixed scales (0.30, 0.70) chosen before the run.
- Only 8 weeks, twice-daily snapshots.
- Novig's large noise suggests exchange quotes are not comparable to retail quotes in this model.

## Prospective record

`python scripts/fusion_run.py freeze` saved week 9 as `data/fusion/frozen/week_2026_09.json` (fused lines for unplayed props and each book's standardized gap), hash in `data/fusion/ledger.jsonl`. No scorer exists yet.

## Next

Nothing here points to an edge. The vig on outlier quotes consumes the gap. A rerun of the scoring test needs far more props than a season supplies, so it is not worth waiting for.
