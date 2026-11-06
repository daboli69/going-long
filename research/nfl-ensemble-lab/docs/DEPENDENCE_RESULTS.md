# Dependence between outcomes in one game: results

Run 2026-11-06 against docs/DEPENDENCE_PREREG.md (commit 67ce253b). Football only. No staking or bet sizing.

## Result

The stop rule fired. For all three pair classes the power gate failed, so the 2025 held-out season was not scored and is still unseen. No test of "does a dependence model beat independence" was run, and nothing here is evidence of an edge.

## Power gate (structure only, no outcome read)

Recovery worked: a planted correlation of 0.20 came back as 0.20 in all three classes, and a planted 0 was never called significant. Power at the registered size of 0.15 was low because 2025 has few pairs per class.

| Class | 2025 games | 2025 pairs | Power at 0.15 | Games for 80% power |
|---|---|---|---|---|
| A: quarterback passing with wide receiver receiving yards | 272 | 1,345 | 0.24 | about 1,360 |
| B: quarterback passing with tight end receiving yards | 264 | 513 | 0.08 | not reached at 2,112 (power 0.67) |
| C: quarterback passing with running back rushing yards | 272 | 846 | 0.16 | about 1,360 |

Power counts a pass only when both the energy score and the variogram score are significant at 0.05/3, one-sided.

## Fit seasons (2022 to 2024), descriptive only

These are in-sample estimates on normal scores of the independent forecasts' PIT values. They were not tested against anything and are not a result.

| Class | Pairs | Correlation | 95% interval (bootstrap by game) | Family with lowest BIC |
|---|---|---|---|---|
| A | 4,100 | 0.36 | 0.33 to 0.38 | Gaussian |
| B | 1,306 | 0.32 | 0.28 to 0.37 | Gaussian |
| C | 2,556 | -0.05 | -0.09 to -0.02 | Gaussian |

Reading this carefully:
- The gate planted 0.15 as the smallest size of interest. The fit seasons point to about 0.35 for A and B, which the gate could detect (planted 0.30 was caught 92% of the time for A, 51% for B, 77% for C). The registered rule is still the rule. Changing the planted size now would be a choice made after seeing the fit seasons, so I did not.
- The fit shows the independent forecasts leave a quarterback-to-receiver link in the data. The game simulator already carries one (about 0.4 to 0.56 in `artifacts/props/dev/correlation.parquet`). Whether the simulator carries the right amount is not tested here.
- Class C is slightly negative, not positive. Teams that pass a lot run less, which is plausible, but the effect is small.

## Departures from the registration

- The gate used 100 repetitions per planted size for recovery and 100 per multiplier for the games-needed scan, and 400 for the power run, to fit the time budget.
- Both forecasts in each comparison use the same random draws (common random numbers), which lowers noise and raised power over the first rough run.
- A class must pass both scores in the gate, to match the pass rule.
- The held-out rule uses the larger of the Diebold-Mariano and bootstrap p-values. It never ran.

## Not tested and not available

- Runner with team pass attempts, and the game total with each player: no marginal forecast exists. Class C is a substitute.
- Kalshi fee comparison: nothing passed, so none was run.
- Sportsbook same-game-combination quotes: no free source with exact quotes was found, none captured.

## Concerns

- The PIT values are the stored `pit_base` of the independent baseline. I assumed they are out of sample (they sit in the eval folders) and did not re-derive them. They are not uniform (the Kolmogorov-Smirnov test rejects), which is why the fit seasons' own distribution is used to remove marginal error.
- A running back or receiver with zero yards has a tied outcome. The stored PIT values are all distinct, so a randomization step probably exists upstream. I did not check it.
- The weekly record applies the fitted copula to the newest weekly run's over probabilities, a different model from the one the copula was fitted on. This is an approximation.

## Prospective record

`python scripts/dependence_run.py freeze` saved week 9 as `data/dependence/frozen/week_2026_09.json`: 101 pairs (51 class A, 21 class B, 29 class C), hash recorded in `data/dependence/ledger.jsonl` and verified. No outcome is attached yet and no scorer exists yet.

## Next

A rerun needs about five times the games, so roughly next season. The only faster route is a new registration that changes the planted size, which Travis should decide because it was prompted by these fit-season numbers.
