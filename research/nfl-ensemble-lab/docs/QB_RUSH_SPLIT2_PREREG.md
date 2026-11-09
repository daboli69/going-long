# Quarterback rushing split, less shrunk: pre-registration

Written 2026-11-09, before any version below was built. Follows `docs/QB_RUSH_SPLIT_PREREG.md` and its results.

## Disclosure that shapes the design

The 2022 to 2025 seasons were already used once to score the first split (S), and the finding that S runs about 5 yards low for the heaviest rushers came from looking at those same games. A new challenger scored on 2022 to 2025 therefore cannot count as an untouched test. This registration uses 2012 to 2021 for the only selection, reports 2022 to 2025 as a confirmation with that caveat, and makes the **prospective 2026 weeks** the real test.

## Question

Does less shrinkage toward the league average fix the low bias for heavy rushers without hurting everyone else, and how much of S's gain over the last-six average comes from the split itself rather than from shrinkage?

## Versions

- **B0:** last-six-game mean of total rushing yards (unchanged).
- **B1 (new control):** the quarterback's total rushing yards per game over his last 16 starts, shrunk toward the league starter mean with 6 games of weight. No split, no game state. This isolates what shrinkage alone does.
- **S:** the first split, shrinkage weights as registered (designed rate 6 games, designed yards per attempt 30 attempts, scramble rate 150 dropbacks, yards per scramble 15 scrambles).
- **S2:** the same model with all four shrinkage weights multiplied by a single factor `f`.

## Selection (the only place anything is chosen)

`f` is chosen from {1.0, 0.5, 0.25} by the lowest pooled RMSE over the **2012 to 2021** walk-forward test seasons (each season fit on earlier seasons only, as before). Ties go to the larger `f`. No other parameter is changed. 2022 to 2025 are not looked at for selection.

## Evaluation

1. **Confirmation, 2022 to 2025** (contaminated, as disclosed): S2 against S, B1 and B0 on RMSE, MAE and bias, paired game-cluster bootstrap (2,000 draws, seed 20261110). Also the top-decile rushing-rate subgroup, with bias.
2. **Prospective, the real test:** regular-season 2026 games from Week 10, the quarterback who starts each team's game (scored on the actual starter), with predictions for B0, B1, S and S2 frozen before the week's first kickoff (`scripts/qb_rush_freeze.py <week>` writes a write-once record to `reports/qb_rush/ledger.jsonl`, including the model margin used). Scored once after Week 18 on at least 150 starter-games; fewer than that means no verdict.

## Gate

S2 is a "Challenger, recommend review" only if all hold: in the confirmation, S2 has lower RMSE than S and than B1, MAE no worse than S, and the top-decile bias is closer to zero than S's; and in the prospective test S2 has RMSE below B0 and S with the paired 95% interval on the RMSE difference against B0 below zero. Failing either leaves the champion (the current usage-based projection) unchanged. Promotion needs Travis's approval.

## What it cannot show

It says nothing about touchdowns, and about 240 starter-games is a small prospective sample against single-game rushing noise (standard deviation near 17 yards), so it can miss a real gain of a yard or less. The split's own contribution is read from S against B1, not assumed.

## Freeze script

`scripts/qb_rush_freeze.py` must exist and be tested before Week 10 kicks off (Sunday 2026-11-15). If it is not ready, the prospective window starts at the first week it is.

## Results (run 2026-11-09, `scripts/qb_rush_split2.py`, numbers in `docs/qb_rush_split2_results.json`)

Deviation from the registration: the development window ran 2013 to 2021, because 2012 has no earlier season with a model margin to fit the state slopes on. Nothing else changed.

**Selection (development, pooled RMSE):** f = 1.0: 15.673; f = 0.5: 15.453; **f = 0.25: 15.401** (selected); controls B1 15.798, B0 15.982. The best value sits at the edge of the registered grid, so an even lower f might do better; that is not tested here.

**Confirmation on 2022 to 2025 (2,164 games; contaminated, as disclosed):**

| | RMSE | MAE | Bias | Top-decile bias (224 games) |
|---|---:|---:|---:|---:|
| B0 last-six mean | 17.64 | 12.54 | -0.17 | +1.2 |
| B1 shrunk total, no split | 17.11 | 12.19 | -1.51 | -8.2 |
| S (first split) | 16.94 | 12.37 | -0.25 | -5.4 |
| **S2 (f = 0.25)** | **16.84** | **12.20** | +0.40 | **+1.7** |

All four confirmation conditions hold (RMSE below S and below B1, MAE no worse than S, top-decile bias closer to zero). The sizes are small, and two of the differences are inside the noise:
- S2 against S: RMSE -0.11 [-0.30, +0.08]. Not separable from S.
- S2 against B1: RMSE -0.27 [-0.56, +0.01]. The interval touches zero.
- S2 against B0: RMSE -0.81 [-1.15, -0.47].
- The split's own contribution, S against the shrinkage-only control B1: RMSE -0.16 [-0.28, -0.05] but MAE +0.17. A small gain in squared error and a small loss in average error, so the split itself is a minor part of the story; most of the improvement over the last-six average comes from shrinking a longer history.

**Status:** S2 is a candidate, not a result. The gate needs the prospective 2026 test (frozen predictions from Week 10, scored after Week 18, at least 150 starter-games). `scripts/qb_rush_freeze.py` is written and dry-run on Week 9; run it with `--write` before Week 10's first kickoff.

**Allen, BUF@MIN, S2:** BUF by 1.3: designed 3.3 att / 12.0 yds, scrambles 2.7 att / 25.3 yds, kneels 0.7 / -0.7 yds, **total 36.5**; BUF by 8.5: total 35.2. (S: 32.8 and 31.8; last-six average 41.2.)
