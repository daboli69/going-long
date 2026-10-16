# Independent review of E13 (receiver separation) and E14 (QB pressure)

Reviewed from the cloud session on `codex/fantasypoints-experiments` (tip `6c31633`). The cloud session cannot read the licensed CSVs, so
**nothing was re-run**; this review covers code, the frozen specs, and the committed aggregate results. Data-dependent re-execution is
for the local session. The registered results are preserved unchanged.

## Verified
* `python -m unittest tests.test_trend_e13_e14 tests.test_trend_research`: 33 tests pass here. They check that spec hashes match the ledger, the ledger holds aggregates only, the CLI is wired and the same-season guard raises.
* Handoff numbers match `research/trend-intelligence/ledger.json` exactly (E13 yards/g n=408, 0/2 seasons better; E14 n=78).
* **Temporal alignment:** features for season N come only from the season N-1 snapshot (`data.prior_features`), outcomes from season N (`data.outcome_frame`). `assert_no_same_season(season-1, season)` in the runner is trivially true; the real protection is that construction.
* **Player-ID joins:** frames are keyed on resolved `gsis` ids; rows with no id or a split entity are dropped, and a player appearing twice in one table is dropped entirely rather than guessed. Names are never a join key.
* **Baseline fairness:** baseline and challenger are fitted on the identical rows, with the identical ridge (`stats.Ridge`: standardized features, alpha 10, intercept unpenalized, fixed and not tuned) and the identical MAE/bootstrap path. The baseline already contains the player's own prior volume and production (E13 also routes/game and targets per route).
* **Uncertainty:** paired cluster bootstrap by player over pooled test pairs, 2000 draws; Bonferroni 97.5% for the two E13 primary comparisons, 95% otherwise.
* **Missingness:** `dropna()` removes players lacking any column; the frame is shared by baseline and challenger, so the comparison is fair, but the sample is limited to players with both separation tables (a higher-volume subset).

## Findings (none change a registered verdict)
1. **Decision rule v1, not v2.** The README says experiments registered from now on use rule v2 (`reject_requires_ci`), but E13/E14 inherited the first-wave `COMMON` rule, so REJECTED means "no point gain", not "a worthwhile gain is excluded". Re-reading the committed intervals under v2 (descriptive only, not a replacement verdict):

| Comparison | Rel. MAE change | CI of MAE delta | Best-case gain at CI edge | Seasons better | n | Registered | v2 reading |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E13 yards/g, separation overall | -1.15% | [-0.082, +0.323] | 0.8% | 0/2 | 408 | REJECTED | REJECTED |
| E13 yards/g, separation vs man/zone | -1.70% | [-0.099, +0.466] | 0.9% | 0/2 | 408 | REJECTED | REJECTED |
| E13 targets/g (secondary) | -1.55% / -1.98% | CI upper edge near +0.03/+0.04 | 0.1% | 0/2 | 408 | REJECTED | REJECTED |
| E14 passing yards/g, pressure | -4.08% | [-0.824, +3.080] | 3.1% | 1/3 | 78 | REJECTED | **INCONCLUSIVE** |
| E14 passing TD/g (secondary) | -4.72% | [-0.002, +0.035] | 0.7% | 0/3 | 78 | REJECTED | REJECTED |
| E14 quality block (descriptive) | +4.73% | [-3.571, +0.937] | 13.3% | 2/3 | 78 | INCONCLUSIVE | INCONCLUSIVE |

   E13 holds under either rule (the separation blocks add at most about 1% at the optimistic interval edge). E14 pressure on yards is underpowered, not disproved: it can exclude neither no effect nor a gain of about 3%.
2. **Registration was not a prior commit.** `registered_at` and `completed_at` are 8 seconds apart and the specs and results landed in one commit (`6c31633`), so the hash proves the specs were not edited afterwards, not that they were committed before the data was run. The local session had already inspected inventory and missingness. Treat these as procedurally registered, not independently pre-frozen.
3. **No untouched holdout exists for 2022-2025.** E13's two folds (2023->24, 2024->25) are the same WR/TE pairs and outcome (receiving yards/g) that E1, E3 and E6 already examined; E14's QB seasons overlap the 2023-25 folds of E7-E10; and 2025 is the disclosed confirmation holdout of P3-x, JP-x and P4-1. Only 2026 Weeks 6+ remain untouched. This does not invalidate a negative result for a new feature block, but it means a future positive result on these seasons would carry a forking-paths discount.
4. **Training size.** E14's first fold trains on 30 QB-seasons for an 8-feature model; with fixed alpha 10 an unhelpful added block can raise error by overfitting alone. The result rejects *this formulation at this sample size*.
5. **Selection on a future event.** Both experiments require at least 8 games in the outcome season. That conditions on a later health outcome, equally for baseline and challenger, but it is not a pregame-available filter, so these are season-level association tests, not a forecast evaluation.
6. **Spec text vs data.** The E13 spec says "about 100-150 pairs per season"; the ledger shows 199-205. Cosmetic.

## What the negatives do and do not say
They reject two season-level formulations: last season's separation scores, and last season's QB pressure/time-to-throw, as linear additions to a ridge on that player's own prior per-game production. They do not test weekly player-prop forecasting, within-season role change, separation by route type, position-specific interactions, pressure interacting with offensive-line or opponent pass rush, or any touchdown, pace or game-line use. Season-level prediction and weekly prop forecasting are different questions.

## Privacy review
* `FantasyPoints/` is already in the tracked `.gitignore` (the handoff said it was not). `StatApi/` was only in a local exclude; it is now ignored with the **anchored** pattern `/StatApi/`. An unanchored `StatApi/` would, on Windows' case-insensitive paths, also ignore `scripts/statapi/`, which is tracked application code (client, normalizer, ownership and Showdown backtests).
* No path under `FantasyPoints/`, `StatApi/` or `model_inputs/`, no `credential.json` and no SQLite file appears anywhere in Git history (`tests/test_private_data_ignores.py`). Tracked research files were checked: `research/going_score_b/panel.parquet` is built by `build.py` from public nflverse and ffopportunity caches, and `research/dfs/team-stats-2026.csv` has public nflverse columns.
* `build.py` hard-codes a local Windows path (it exposes a username in the repo); harmless but worth parameterizing later.
