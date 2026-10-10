# DFS validation and fixes, 2026-10-10

Evidence base: the private stat-api archive (read-only; aggregates only are reported here, nothing is copied or served) and one frozen pregame replay (`tests/fixtures/dfs-pregame-20261004.json.gz` with the 10/04 main-slate DraftKings CSV, run by `scripts/dfs_headless.cjs`). Claims below are limited to what was measured. **No tournament-profitability claim is made or enabled anywhere; the archived Showdown backtest of build styles (55 contests) had mean ROI of -53% to -56% for every style, with no reliable difference.**

## A. Lineup ownership

Statistics that were being confused:

| Statistic | Definition | What the app showed |
|---|---|---|
| Player ownership `o_i` | % of contest lineups holding player i | per player, ok |
| Sum of player ownership `A` | sum of `o_i` over the 9 (Classic) or 6 (Showdown) slots, percentage points | "Total own" |
| Field-typical sum | mean of `A` over a contest's lineups = `sum_i o_i^2 / 100` (exact identity, verified within 2% on 73 contests) | not shown |
| Probability of a specific lineup / expected duplicates | needs a joint lineup model | not shown for Classic (see below) |

Cause of "47% vs 125-181%": the displayed number was the raw sum of the salary-only model's per-player ownership. That model is right on average per player but shrunk toward the mean, so any sum built from it is too low. On the 10/04 main slate the real contest's field lineups held a mean sum of 144 (p10-p90 103-187, top 1% mean 127); the optimizer lineups showed 51 (the model's own field-typical sum was 59-99 depending on pool definition). Two contributors, in order of size: (1) shrinkage (model field-typical 99 vs real 144 on the same 261 rostered players); (2) pool definition: the app annotates every CSV row (24 teams, 629 rows, scrubs included) while the contest used 16 teams, which diluted the 900% slot total (model field-typical 58 vs 99). Restricting by AvgPointsPerGame>0 was tested and made per-player error worse, so it was not adopted; use the CSV of the actual contest.

Fix (`shared/dfs-classic-field.js`, `shared/dfs-classic-ui.js`, `scripts/dfs_ownership_calibration.py`): the raw sum is now labelled "Sum of player ownership (model)"; if the private model file carries a `lineup_calibration` block the UI also shows the expected realised sum, an 80% range and the typical field lineup; without the block it says the raw sum runs a quarter to a third low. Calibration `A_hat = exp(a) * sq^b * (1 + s*(clamp(P/sq) - 1))` with `P` = model lineup sum, `sq` = model field-typical sum.

Held-out (fit on the 48 earliest of 73 archived Classic contests, 2021-01..2024-12; scored on the 25 latest, 2025-01..2026-10, 970,748 lineups): mean absolute lineup error 81.7 -> 41.5 points; field-level bias -28% -> -6% (mean abs 9.8%); 80% of realised lineup sums fall within 0.85-1.34 of the estimate. On 10/04 the calibrated expectation for the optimizer lineups is about 124 against a real field mean of 144 and top-1% mean of 127. **Limits:** within one contest the model sum ranks lineups poorly (correlation 0.17), so the calibration fixes the level, not the ordering. Top-1% lineups' sums were 1.02x the field mean on average (sd .10): no evidence that winners are low-owned.

Expected duplicates (Classic): not provided. A product-of-ownership model ranked actual copies at Spearman 0.18 on later contests (0.50 even with true ownership); contest-level duplication varies from 2% to 78% of lineups with slate size. Showdown keeps its existing validated duplication-decile model.

## B. Correlation

Existing QB/receiver/bring-back/teammate table (`data/dfs_correlations.json`, 2021-23 fit, 2024-25 check) was kept: QB~WR1 .33, QB~TE1 .21, QB~opp_QB .13, WR~WR and RB~WR about 0. New (this work): D/ST, which had none. Estimated from 662 archived team-games (role by salary rank, players who played), normal-score correlations, fit (<=2024, n=492) / validation (>=2025, n=170):

| D/ST vs | fit | validation | used (all-games, shrunk n/(n+50)) |
|---|---|---|---|
| opposing QB | -.48 | -.53 | -.453 |
| opposing RB1 | -.27 | -.27 | -.253 |
| opposing WR1 / WR2 / WR3 | -.22/-.15/-.14 | -.18/-.23/-.13 | -.186/-.153/-.125 |
| opposing TE1 | -.11 | -.08 | -.094 |
| own RB1 | +.12 | +.12 | +.109 |
| own QB/WR1/TE1 | ~0 | ~0 | 0 |
| opposing D/ST | -.13 | +.04 | 0 (unstable) |

D/ST sd is 5.9 (fit) / 5.8 (validation) points; the app used 0.42 x projection (about 2.6). Now 5.8. Implemented in `shared/dfs-sim.js` (`DST_CROSS`, `DST_SD`, role `DST`). This is an expected-impact model: it changes lineup variance, so ceiling objectives pay for pairing a D/ST against your own offence; mean objectives are unaffected and nothing is banned. The previous `balanced` build had a blanket -1.25 point penalty per opposing player; it is now a pure mean maximiser (as its UI text states). Reproduce: `scripts/dfs_correlation_estimates.py`.

## C. Build styles

Classic UI: Best DFS = mean; Measured ceiling = mean + 1.28 SD of the lineup (correlated); Tournament research = observed-spread proxy; Throne unchanged. The result now carries `vsBest` and the status line says "identical to Best DFS" or how many players differ and what projection was given up. On 10/04: measured changed 1 player (0.4 projected points); tournament was identical (no observed-spread data for the pool, falls back to projection). Generic builder (`shared/football-dfs.js`): balanced = mean; floor = mean - 1.28 SD; measured = mean + 1.28 SD; ceiling = mean + 2.33 SD; best/lowdup/leverage use the private Showdown field model only on Showdown slates, otherwise they fall back to measured and the result `reason` says so; every build also reports when its top roster is simply the highest-projection roster found. On the 10/08 TB@DAL Showdown replay the seven styles gave seven distinct five-lineup portfolios but five distinct top lineups. Reproduce: `node scripts/dfs_headless.cjs --csv ... --showdown --field ...`. Weights (lambda .5, gamma .05) are the pre-2025 choices; none has shown a reliable ROI difference.

## D. Projection backtest

GOING's historical pregame projections were not archived, so the only true replay is 10/04 (frozen inputs). Findings:
- Omitted terms (interceptions, lost fumbles, 2-pt): actual DK points minus core points computed from the same logged stat line: QB -0.52 (se .07, n=187, before 2026-01-15) and -0.68 (se .22, n=25, later); RB/WR/TE 0.00 +/- .02 (n=1,350). **Applied: QB -0.52** in `shared/dfs-evidence.js` (`ADJUSTMENTS.qbTurnovers`; rollback: `enabled:false` or `adjustments:false`). Nothing is applied to RB/WR/TE.
- 10/04 replay, 215 usable players: GOING MAE 5.14, RMSE 7.21, bias -0.36, vs the site AvgPointsPerGame baseline MAE 5.32, RMSE 7.47, bias -0.33. By position bias: RB -1.2, WR -0.6, TE +0.2, QB +0.3, DST +0.8. Not inflated overall.
- But by value quartile (projection per $1,000): top quartile over-projected by +3.05 (se 1.14), second quartile -3.16 (se .97). The optimizer concentrates on the top quartile (winner's curse): the two 10/04 rosters projected 175 and scored 139 and 127. One slate: no shrinkage was fitted or applied; the UI now says the total is optimistic.
- A trailing 5-game mean proxy (not GOING's model) realised 0.68-0.83 of its value by position in 2025 slates but 0.84-1.04 in 2026 (includes inactive/zero rows): unstable, so no multiplicative correction.
Reproduce: `scripts/dfs_projection_backtest.py`.

## E. Touchdown Throne staleness

`data/dfs_team_touchdowns.json` is produced only by `research/dfs/build-team-budgets.py`, an offline reproducer (needs a saved CSV, SHA receipt and explicit timestamps). No workflow step calls it, and `.github/workflows/data.yml` neither builds it nor lists it in the commit `paths` array. It was committed once (2026-10-03, e5fd2b8) and `shared/dfs-team-evidence.js` refuses snapshots older than 36 hours. New `scripts/dfs_team_touchdowns.py` is the scheduled caller (fail-closed, atomic write). **Required workflow edit (not in this engineer's files):** in `data.yml`, add after the "Build settlement observations" step (it reads `data/results.json`): `- name: Refresh DFS team touchdown evidence` / `continue-on-error: true` / `run: python scripts/dfs_team_touchdowns.py`, and add `data/dfs_team_touchdowns.json` to the `paths` array in "Commit generated snapshots". The consumer also gates `releaseUpdatedAt` at 36 hours, so a NFLverse release not touched for 36 hours still blocks Throne.

## F. Sunday 10/11 slate

No `DKSalaries*.csv` in Downloads contains 10/11/2026 (dates present: 09/20, 10/04, 10/05, 10/08). Not run.


## Independent re-verification correction (2026-10-10)
The first harness run did not load `shared/dfs-correlations.js`, so lineup correlations were zero and "Measured changed 1 player, 0.4 points" described that harness, not production. With the correlations loaded (as production does), on the 10/04 slate Best, Measured and Tournament all return the same roster (projection 175.1, SD 26.6, 90th percentile 209.3); the UI says so through `vsBest`. Classic styles can therefore coincide on a slate; Showdown styles differ (4-7 distinct top lineups across 7 styles with the private field model). The Touchdown Throne gate no longer treats nflverse release age as staleness (it republishes only after games finish): our own retrieval must be under 36 hours and the release under 8 days. Sums of player ownership are shown in points, not percent.
