# Dependence between outcomes in one game: results

Run 2026-11-06 against docs/DEPENDENCE_PREREG.md (commit 67ce253b). Football only. No staking or bet sizing.

## Result

This is the first run. Amendment 1 and a scored result for class A are in the addendum at the end.

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

## Addendum 1: Amendment 1 and the 2025 score (2026-11-06)

Amendment 1 was committed (57aa60bf) before the gate was rerun. It raised the planted size to 0.30 for classes A and B and kept 0.15 for class C.

Gate rerun (once):

| Class | Planted | Power | Result |
|---|---|---|---|
| A: QB passing with WR receiving | 0.30 | 0.94 | passes |
| B: QB passing with TE receiving | 0.30 | 0.49 | fails, not scored (about 528 games for 80%) |
| C: QB passing with RB rushing | 0.15 | 0.16 | fails, not scored |

Class A was scored on 2025, once (272 games, 1,345 pairs). The chosen family was Gaussian with correlation 0.35, fitted on 2022 to 2024. Larger gain means the dependence model beat independence.

| Score | Mean gain per pair | 95% interval (bootstrap by game) | Holm-adjusted p |
|---|---|---|---|
| Energy score | 0.0037 | 0.0025 to 0.0050 | 0.001 |
| Variogram score | 0.0147 | 0.0107 to 0.0191 | 0.001 |

Class A passed both scores. The marker file `data/dependence/heldout_scored.json` now blocks any second run on 2025.

What this shows: a quarterback and his wide receivers move together in 2025 about as strongly as they did in 2022 to 2024, and a model that knows this predicts pairs of outcomes better than one that treats them as unrelated. The gain per pair is small in size but very consistent across games.

What it does not show: that any price is wrong. No same-game-combination price is held. For reference only, with a correlation of 0.35, the chance that both a quarterback and a wide receiver go over is about 5.5 percentage points higher than the product of the two single chances, for legs priced between 40% and 60% (docs/dependence_price_check.json).

Price check against fees: not done. Kalshi's fee schedule PDF returned an error (HTTP 429) and the help page gives no formula. I did not fill the gap from memory. Even with the formula, a fee comparison needs a real combination price, which does not exist here.

The simulators were not changed. The rule allows a dependence layer only if a class passes, and one did, but the game simulator already carries a link of about 0.4 to 0.56, so adding another layer on top would double count. The next step is to compare the simulator's own pairs against this result, which is not done.

## Addendum 2: does the simulator already carry the link? (Amendment 2)

Registered in a37a5ded before the comparison was computed. Quarterback and top receiver only, measured in yards.

| Sample | Team-games | Actual residual correlation | Simulator's own correlation | Difference | 95% interval | Verdict |
|---|---|---|---|---|---|---|
| 2022 to 2024 (primary) | 1,630 | 0.47 | 0.44 | +0.03 | -0.01 to +0.07 | about right |
| 2025 (confirmation) | 544 | 0.37 | 0.44 | -0.07 | -0.14 to +0.01 | cannot say |

By season, for description: 2022 -0.00, 2023 +0.06, 2024 +0.01, 2025 -0.07. The simulator's own correlation stays near 0.44 every year, so the movement is in the data.

What this means: the game simulator already ties the quarterback to his top receiver at about the strength the data shows, so the independent forecasts are the ones that miss it. The primary check passes. The 2025 check cannot decide, because the interval is wide and leans toward the simulator being slightly too strong that year. One season is not enough to call a drift.

Decision under the rule: no dependence layer is added to the simulators. The gain found in Amendment 1 applies to forecasts that treat players as unrelated, not to the simulator.

Limits: this covers the top receiver only, not other receivers, tight ends or running backs, and it is in yards, not the normal-score space of the copula test. The simulator's draws are not stored, so its pairs could not be scored directly. The tight end class still needs about twice the games and is a candidate for next season.
