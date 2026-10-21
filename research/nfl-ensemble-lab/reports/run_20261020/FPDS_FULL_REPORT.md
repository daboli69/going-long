# FPDS full report — Amendment 6

**Completed:** append-only importer, column dictionary/coverage, exact GSIS/team/week joins, games-played rolling feature store and resumable fixed-budget program. 269/269 configurations attempted; 4 failed/skipped. Single frozen2025 pass: pending.2026 is descriptive only. All models remain shadow; no promotion.

**Data:** 37 files / 37 tables / 210,146 weekly rows; 5,270 identity/join-excluded rows (not unique players). Exact known GSIS IDs and verified historical roster teams are used; display-label conflicts are counted, never guessed. 27 possible export caps; five separation tables start2022. Overlap revisions observed in this import: 0; pre-download revision frequency remains unknown. Historical publication times are unverified. Strict later-week/final-kickoff+24h joins and future-mutation/shifted/shuffled canaries enforced. See dictionary and aggregate JSON for full coverage.

**What data improved what:** lowest relative discovery loss per family below is a selected, exploratory display; corrected intervals and all trials remain in FPDS_A6_RESULTS.json. Acceptance also requires the frozen validation direction. H3 first-TD/scoring is offensive regulation only; H7 undated target-week injury/shadow effects are unavailable.

|Family / displayed configuration|n / games|Control → new loss|Delta [family-corrected95% CI]|Seasons agreeing / decision|
|---|---:|---|---|---|
|H1: rec / add / linear|6196 / 815|1.547 → 1.533|-0.01359 [-0.02383, -0.00337]|3/3; Rejected / exploratory; no full gate|
|H2: rush_yds / add / linear|2740 / 814|25.62 → 25.23|-0.3872 [-0.73, -0.04233]|3/3; Rejected / exploratory; no full gate|
|H3: rec / family / linear|6196 / 815|1.547 → 1.564|+0.01693 [+0.002427, +0.03013]|0/3; Rejected / exploratory; no full gate|
|H4: pass_tds / add / linear|620 / 330|1.022 → 1.009|-0.01267 [-0.04266, +0.01615]|2/3; Rejected / exploratory; no full gate|
|H5: rec_yds / add / linear|2037 / 271|24.44 → 24.36|-0.07482 [-0.2889, +0.1386]|1/3; Rejected / exploratory; no full gate|
|H6: rec_yds / add / linear|2037 / 271|24.44 → 24.33|-0.1093 [-0.4195, +0.1724]|1/3; Rejected / exploratory; no full gate|
|H7: rec_yds / add / linear|2037 / 271|24.44 → 24.33|-0.104 [-0.3102, +0.09998]|1/3; Rejected / exploratory; no full gate|
|H8: pass_tds / all / shrink|620 / 330|1.022 → 1.056|+0.03436 [-0.01721, +0.0878]|1/3; Rejected / exploratory; no full gate|
|H9: rec / all / stacked|6196 / 815|1.547 → 1.512|-0.0344 [-0.05828, -0.0126]|2/3; Rejected / exploratory; no full gate|

**Recommended changes:** No new model change has passed the complete preregistered gate; keep the control. Positive table permutation is tentative reliance, not proof of independent value.

**Edge assessment:** real historical game closing lines are benchmark-only; their paired forecast-loss comparisons are in the aggregate JSON. Historical prop prices do not exist here: pseudo-lines test calibration only.2026 archived quotes support small-sample descriptive comparisons and forward tracking. No tradable price edge is established.

**Concerns:**269-slot search/multiple testing; finite2000-draw bootstrap tail resolution; possible export truncation/selection; unverified historical publication/revisions; unmatched identities; overlapping unit means; earlier2023 development and old simulator2023–25 exposure.2025 is not a pristine holdout. Structural proxies are analytical, not v1 simulations. Training-residual interval warm-up is labelled. Causal on/off effects and current replacement assumptions are not identified by the exports.

**Next angles:** preregister uncapped coverage and real pregame publication snapshots; compare exposure-normalized role changes, timestamped injury/replacement features and true prospective calibration on matched quote contracts. No further trials on2025.

**Needs Travis / weekly:** download the same full-history tables with trailing `week N`, retain them in Inbox, run `run_weekly_fpds.bat`. Outputs stay in ignored private revision folders; do not share subscription derivatives. Review missing/capped coverage before relying on apparent improvements.


**Stopped at usage limit:** included allowance exhausted. Account-reported existing credits decreased40.48053→7.52892; no new purchase/API/subscription was initiated, but this session cannot be claimed$0. No2025 confirmation,2026 descriptive scoring or new weekly FPDS forecast was started. These remain Next. Discovery attempted269 configurations:265 complete/4 checkpoint-related failures retained/skipped.

**Final checks:** 349 passed, 1 skipped, 522 warnings in 325.23s (0:05:25). No model promotion. Existing champion/forecasts unchanged.

**Needs Travis:** resume only with included allowance available; commit/check the discovery-frozen configuration before the SINGLE2025 pass, then descriptive2026 and run_weekly_fpds.bat. Open launch_lab.bat → Research → FPDS Research for saved aggregate results. Weekly minimum download selection remains provisional until frozen confirmation; keep original37-table history, require every table referenced by the frozen configuration, and review27 possible export caps/five separation tables lacking2021.2026 source files coverweeks1–6; player/join gaps remain.

**Interpretation:** any gain combines new data and shorter-window representation versus the8-game lab baseline; matched-window free-NFL controls and verified vendor definitions/publication times are future preregistered work. H7 covers lagged usage/lineup proxies; true on/off and current replacement effects remain unvalidated.
