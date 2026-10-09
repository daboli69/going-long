# E12: Expected Opportunity vs Actual Production

Status: **DESCRIPTIVE ONLY.** Registered 2026-10-09 before any model was fitted. Aggregate results only. Not a betting-return test: no odds, stakes or returns are used.

Spec: `opportunity_vs_production_spec.json` (sha256 prefix `1b492cee2a7fd53d`, printed by the study script). Code: `opportunity_vs_production_study.py`
(`python research/trend-intelligence/opportunity_vs_production_study.py CACHE_DIR OUT.json`, about 20 seconds). The registration is a committed
document, not a cryptographic timestamp. The E12 id is used here without being added to `ledger.json`, which `scripts/trend_research.py` manages.

## Question

Does a player's trailing PPR residual (actual minus ffopportunity expected, last 3 or 6 games) predict the next game or the next three games
(PPR, receptions, yards, touchdowns) after controlling for trailing workload and trailing production? Positions QB/RB/WR/TE separately.

## Design (as registered)

* Data: nflverse `stats_player_week` 2020-2025 and ffverse/ffopportunity `ep_weekly` 2020-2025 (public; `total_fantasy_points*` are PPR; checked
  against nflverse `fantasy_points_ppr`: median difference 0, mean +0.01). 31,445 player-games after the join.
* Origin = a completed game t; features use games up to t only; targets are strictly later games (next 1, mean of next 3, all three required).
* Baseline (per position, OLS, no tuning): next ~ trailing actual PPR + trailing targets, carries, attempts + trailing-12 actual PPR.
  Challenger adds trailing expected PPR (identical to adding the residual).
* Splits by season of the origin game: fit 2021-23, score 2024 (validation); refit 2021-24, score 2025 once (holdout).
* Inference: player-clustered bootstrap (2000 resamples) on the paired out-of-sample squared-error difference; Bonferroni over the 16 tests per position
  (4 outcomes x 2 horizons x 2 windows), so 99.69% intervals. Coefficients: cluster bootstrap on the dev fit.
* PREDICTIVE needs at least 1% MSE reduction in both 2024 and 2025, a holdout interval above 0, and the same residual-coefficient sign in dev and the
  refit. Everything else is DESCRIPTIVE_ONLY (interval excludes a 1% gain) or INCONCLUSIVE.

## Result

Of 64 cells (position x window x horizon x outcome), **0 meet the PREDICTIVE rule.** 31 are DESCRIPTIVE_ONLY and 33 INCONCLUSIVE. Adding the
expected-points information lowered 2025 holdout error in 44 of 64 cells, but by at most 3.8% (QB next-3 yards, interval -0.9% to +7.5%). Three RB
touchdown cells have intervals above zero (2025 gains 0.13%, 0.21% and 0.79%); they miss the 1% floor, so they are not claimed.

PPR outcomes (full table, all four outcomes, in the study output):

| Position | Window | Horizon | n dev/val/hold | 2024 MSE gain % | 2025 MSE gain % [Bonferroni 95% CI] | b_res | b_exp | Verdict |
|---|---|---|---|---|---|---|---|---|
| QB | 3 | next game | 1405/541/485 | 0.23 | 0.47 [-0.66, 1.67] | 0.153 | 0.318 | INCONCLUSIVE |
| QB | 3 | next 3 | 1381/521/368 | 0.49 | 1.61 [-2.18, 4.91] | 0.091 | 0.300 | INCONCLUSIVE |
| QB | 6 | next game | 1405/541/485 | 0.29 | 1.05 [-0.63, 3.16] | 0.167 | 0.488 | INCONCLUSIVE |
| QB | 6 | next 3 | 1381/521/368 | 1.04 | 3.07 [-3.02, 7.82] | 0.094 | 0.480 | INCONCLUSIVE |
| RB | 3 | next game | 3040/1081/962 | -0.03 | -0.31 [-0.71, 0.10] | 0.139 | 0.003 | DESCRIPTIVE_ONLY |
| RB | 3 | next 3 | 2909/1032/760 | -0.15 | -0.61 [-1.48, 0.19] | 0.087 | -0.035 | DESCRIPTIVE_ONLY |
| RB | 6 | next game | 3040/1081/962 | -0.36 | -0.59 [-1.23, 0.00] | 0.337 | 0.014 | DESCRIPTIVE_ONLY |
| RB | 6 | next 3 | 2909/1032/760 | -0.84 | -1.27 [-3.22, 0.53] | 0.275 | -0.081 | DESCRIPTIVE_ONLY |
| WR | 3 | next game | 4913/1718/1534 | -0.04 | -0.08 [-0.25, 0.08] | 0.029 | 0.134 | DESCRIPTIVE_ONLY |
| WR | 3 | next 3 | 4743/1654/1217 | -0.28 | -0.31 [-1.20, 0.45] | -0.023 | 0.203 | DESCRIPTIVE_ONLY |
| WR | 6 | next game | 4913/1718/1534 | -0.20 | -0.19 [-0.73, 0.38] | -0.039 | 0.321 | DESCRIPTIVE_ONLY |
| WR | 6 | next 3 | 4743/1654/1217 | -0.74 | -0.34 [-2.10, 1.28] | -0.035 | 0.428 | INCONCLUSIVE |
| TE | 3 | next game | 2336/882/829 | 0.08 | 0.05 [-0.71, 0.91] | -0.116 | 0.079 | DESCRIPTIVE_ONLY |
| TE | 3 | next 3 | 2266/859/648 | 0.12 | 0.12 [-0.99, 1.22] | -0.046 | 0.059 | INCONCLUSIVE |
| TE | 6 | next game | 2336/882/829 | 0.04 | 0.13 [-0.34, 0.69] | -0.085 | 0.052 | DESCRIPTIVE_ONLY |
| TE | 6 | next 3 | 2266/859/648 | 0.30 | 0.27 [-1.86, 2.31] | -0.103 | 0.094 | INCONCLUSIVE |

`b_res` is the dev-fit coefficient on the trailing residual and `b_exp` the coefficient on trailing expected PPR, both holding the controls fixed.
If production were fully persistent the two would match; if the residual were pure noise `b_res` would be near zero.

## What this means, plainly

* **Predictive:** nothing. No position, window, horizon or outcome passed the registered rule.
* **Descriptive only:** the residual as a statement about the past ("scored above/below what the workload usually produces"). That is accurate and
  useful on a chart, but it is not evidence of what happens next.
* **WR and TE:** `b_res` is about zero or negative and `b_exp` is positive, so past over/under-performance does not carry into the next games once
  workload and 12-game production are known. The expected-points signal is already largely captured by the baseline (gain at most 0.3%).
  "Regression" (buy-low on a negative residual, sell-high on a positive one) is not shown to beat the baseline: the 2025 gains for WR are negative.
* **RB:** `b_res` is positive (0.09-0.34) and `b_exp` about zero, i.e. RB production above expectation partly persists (role and efficiency) and the
  expected-points figure adds nothing beyond actual production and volume. This is the opposite of a bounce-back story, and it also fails to improve
  out-of-sample error.
* **QB:** the residual is discounted relative to expectation (`b_res` 0.09-0.17 vs `b_exp` 0.30-0.49), consistent with some regression, and the
  2025 holdout gains are the largest (1-4%), but the intervals are wide (a few hundred QB origins) and include zero. This is the only place with a
  hint worth watching; it is a hypothesis for 2026 prospective data, not a finding.
* **Touchdown residual (exploratory, cannot be PREDICTIVE):** for WR and TE the touchdown part of the residual has a negative coefficient on next
  PPR (-0.28 and -0.23 for next-3 at window 6) while the non-touchdown part is small and positive, which fits "touchdown luck mean-reverts". The
  holdout error does not improve (WR -0.7%, TE +0.8%), so this stays descriptive.
* Descriptive check (holdout, window 6, next-3 PPR): baseline error by trailing-residual tertile (low / mid / high) was QB +1.76 / +0.19 / -0.66,
  RB +0.75 / +0.73 / +0.09, WR -0.11 / -0.12 / -0.50, TE +0.36 / -0.03 / +0.48 PPR per game. Only QB shows the bounce-back ordering; differences
  were not tested for significance.

## Limitations

* ffopportunity only has rows for players with a counted opportunity; a game with none is absent from the log, so windows skip it (same for all models).
* Windows run across seasons (offseason role changes add noise equally to baseline and challenger). One validation season and one holdout season.
* The ffopportunity expected model was fitted on earlier seasons and is not retrained in-season; whether it saw any 2021-25 outcomes was not verified here.
* Linear models only; no interaction or non-linear residual effects, no matchup, injury or team-context controls. Absence of a linear
  out-of-sample gain is not proof that no signal exists, only that none was demonstrated.
* 2026 year-to-date (5 weeks) is shown on the chart as description only and was not used to fit or judge anything.
