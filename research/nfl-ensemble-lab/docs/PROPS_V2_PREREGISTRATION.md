# Player-props simulator v2 and the 2026 prospective stage: pre-registration (local lab only)

**Written 2026-10-18, before any v2 code, tuning run or v2 result existed.** It builds on `docs/PROPS_PREREGISTRATION.md`
(with Amendment A) and on v1's single 2023–25 look (commit 19069d6, PASSED: CRPS 13.30 vs 13.96, p = 0.0005). Nothing here
touches the champion game model, the challengers, the pinned scheduler or GOING.

## Why v2
The 2023–25 look found three defects (`docs/PROPS_SIMULATOR.md`, "Known defects"):
1. means run 4–8% high (passing +8%, rushing +5%, receptions +6%, receiving +4%);
2. `calibrate()` returns the points from before its last update, so 10.7% of games miss the implied total by more than 2;
3. receptions and receiving yards are too wide (80% coverage 0.89 / 0.85), passing and rushing too narrow (0.74 / 0.75).

**Data rule for every fix:** values are set on training seasons (2016 through the season before the one simulated) or on the
2022 development season only. 2023–25 results are never used, re-scored or re-run. v1 stays frozen exactly as evaluated.

## The three fixes (procedures fixed now; the resulting values are recorded in `docs/PROPS_SIMULATOR.md` once tuned)
### Fix 2: verified calibration (`calibrate_v2`)
- Same secant search on per-offense efficiency scalars, same common random numbers, 8 iterations.
- After **every** update the game is re-simulated, so the final step is checked like the others.
- The returned scalars are the evaluated iterate with the smallest max(|home miss|, |away miss|).
- Reported: the share of games whose verified miss exceeds 2 points.

### Fix 1: overprojection (two steps, in this order)
- **(a) Training-season gain correction.** After the clock fit, at neutral strength (e = 0), the simulator's yards per completion
  and yards per carry are compared with the training seasons' real values. Two multipliers (`g_comp`, `g_rush`) scale
  completion and carry gains outside the red zone (red-zone gains stay exact empirical draws). This runs for 2 rounds, and then
  the red-zone boost is refitted so neutral points still match training points per team.
- **(b) 2022 per-stat mean correction.** In the 2022 tuning run below, each stat gets a ratio r_k = mean actual / mean
  simulated over eligible player-games. That ratio, clipped to [0.85, 1.05], multiplies v2's simulated samples for that stat
  (passing, rushing and receiving yards, receptions). This is a transparent post-simulation layer:
  - the QB = receivers identity still holds within the simulation;
  - the archived quantiles are scaled.

### Fix 3: per-stat dispersion
- Two share-noise concentrations replace v1's single κ = 30: `kappa_recv` for targets, `kappa_rush` for carries. These
  combine with the team-efficiency noise `sigma_e`.
- **Grid** (18 points):
  - sigma_e ∈ {0.15, 0.25, 0.35}
  - kappa_recv ∈ {30, 60, 120}
  - kappa_rush ∈ {10, 30}
- **Tuning run (2022 only):**
  - Sub-models fitted on 2016–21.
  - Every second 2022 regular-season game in (week, game_id) order, with lines, and 1,000 simulations per grid point.
  - Calibration is done once per sigma_e value with `calibrate_v2`.
- **Selection rule:**
  1. For every grid point, compute its step-(b) ratios and apply them.
  2. Pick the point with the lowest pooled mean CRPS. CRPS is computed from 99 quantiles, the same estimator as the
     prospective test below.
  3. Ties within 0.5% go to the point whose four 80% coverages are closest to 0.80 (sum of absolute gaps).
- Everything else is v1 unchanged: sub-models, bins, shares, red zone, clock, eligibility.

## The 2026 prospective stage
### Weekly archive (`python -m lab.props.weekly`, run by Travis by hand; not scheduled, the pinned scheduler is unchanged)
- **Games.** The default is the earliest 2026 regular-season week that still has unplayed games. The command takes only games
  whose kickoff (games.csv `gameday` + `gametime`, US Eastern) is still in the future and that have both a spread and a
  total. Games that have started are skipped and never archived late.
- **Pregame inputs only:**
  - games.csv spread and total, recorded in the archive.
  - The QB listed in games.csv `home_qb_id` / `away_qb_id`, falling back to the team's most recent starter.
  - As-of shares and offsets built from 2025 and 2026 play-by-play of earlier weeks only.
  - Sub-models fitted on 2016–2025.
- **Availability (recorded per team):**
  1. Once that team's game-day inactives for that week are published (any INA rows), the ACT roster is used, as in v1.
  2. Otherwise: that week's ACT roster minus players listed Out on the official injury report. Doubtful and Questionable
     players stay in.
  3. With no roster rows for that week: the latest earlier week's ACT roster minus Out.

  Fallbacks 2 and 3 are less informed than v1's rule (late scratches are missed). Each archived game records which rule each
  team used.
- **Output.** Per game, `artifacts/props/prospective/<season>_w<week>/<game_id>.parquet` holds rows for every eligible
  player-stat (v1 eligibility rules) with:
  - v1, v2 and baseline B: mean plus quantiles 1%–99%;
  - a JSON sidecar with the inputs, availability rules, calibrated points, code commit, UTC creation time and the parquet's
    SHA-256.
- **Immutability.** Files are created exclusively, so an existing game file is never overwritten. A re-run only adds games
  that were not archived yet and have not kicked off.
- **Score step** (`python -m lab.props.weekly score`). For archived games that are final and whose play-by-play is present, it
  writes `artifacts/props/prospective/scores/<game_id>.parquet` once. Actual regulation stats come from play-by-play, with the
  same definitions as v1. A player who did not play (not ACT on the final roster and no play-by-play rows) is excluded from
  every version alike.

### Prospective test (one look, after week 18 of 2026 is scored)
- **Primary:** v2 vs v1 mean CRPS over all scored eligible player-game-stats. CRPS is estimated from the 99 archived
  quantiles: 2 × the mean pinball loss over levels 1%–99%, identical for both versions. Significance comes from a one-sided
  game-cluster bootstrap (2,000 resamples). **v2 replaces v1 as the props simulator only if its CRPS is lower with p < 0.05.**
  With fewer than 100 scored games, the result is reported as inconclusive and v1 stays.
- **Secondary (reported, not decisive):**
  - v2 and v1 each vs baseline B;
  - by-stat CRPS, mean bias and 50% / 80% coverage;
  - the calibration-miss rate;
  - the comparison restricted to games where both teams used the ACT rule.
- **Interim numbers on the dashboard** are descriptive only. They do not stop, extend or change the test, and nothing is
  re-tuned on 2026.

## Limits
- **No betting claim.** There are no prop odds, so this measures distribution quality only.
- **Data refresh.** The weekly command uses whatever data the last refresh left in `data/raw`. Missing play-by-play for earlier
  weeks shrinks the as-of history, and the archive records how many 2026 games it had.
- **Starters.** The listed QB is assumed to start. A wrong guess hurts v1 and v2 alike.
