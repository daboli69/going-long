# Manual FPDS runs

Open `launch_lab.bat`, choose **Research → FPDS Research**, and use the controls at the top.

|Control|What it does|
|---|---|
|Run projections|Trains matched NFL-only and NFL+FPDS shadow ensembles using all eligible available years from2021 through the available completed-week cutoff, then simulates outcomes for the selected unstarted week.|
|Compare FPDS|Runs the preregistered2022–24 expanding development comparison with identical model families, parameters, samples and NFL history windows in both arms. Shows winner Brier/log loss, margin/total errors and prop losses with paired whole-game intervals.|
|Prepare data|Refreshes free NFL data, imports authoritative local exports, and builds the as-of feature store without fitting models.|

Choose **Games + props**, **Games**, or **Player props**. The week selector applies to forecasts, not the fixed development split. Expand **Simulation settings** for draw count, simulation seed, runtime budget and refresh/cache choice. No model hyperparameter search is exposed. Starts require a click; there is no scheduler or automatic research on app load. One manual job runs at a time. Refresh status manually, stop after the current block, or resume an interrupted exact job.

## Source precedence

`GOING/FantasyPoints/Inbox/All historical data from 2021-2026 week 6` is authoritative. Loose legacy exports cannot replace it because of a newer modified date. A later matching `week7`, `week8`, etc. export can update a table only if its headers match and it retains the base export's historical season/week coverage. Partial newer exports stop with a clear error instead of dropping historical seasons. Unknown loose tables are not silently added. No Inbox file is modified, moved or deleted. Earlier hashed copies remain available.

Use `scripts\launchers\import_fpds.bat` or the supported worker/manual commands below; the archived Amendment6 package remains unchanged for reproducibility. Old raw-package discovery commands are not the manual workflow. `scripts\launchers\run_fpds_research.bat` now opens the manual menu by default rather than accidentally starting another269-trial Amendment6 study.

## Commands

From this lab folder:

```bat
scripts\launchers\run_manual_fpds.bat
scripts\launchers\run_manual_fpds.bat project --week 7 --scope all --sims 10000 --seed 17
scripts\launchers\run_manual_fpds.bat project --week 8 --scope games
scripts\launchers\run_manual_fpds.bat compare --scope games --hours 2
scripts\launchers\run_manual_fpds.bat compare --scope props --hours 2
scripts\launchers\run_manual_fpds.bat prepare --week 7
scripts\launchers\run_manual_fpds.bat plan
scripts\launchers\run_manual_fpds.bat status
scripts\launchers\run_manual_fpds.bat resume --job <saved-job-id> --hours 2
scripts\launchers\run_manual_fpds.bat stop --job <saved-job-id>
```

`--no-refresh` uses the existing prepared NFL/FPDS cache only if its source selection still matches the authoritative files. A later week needs prepared player rows for that week; leave refresh enabled to create them. Missing future rows stop clearly. Forecast workers have a2h admission window before the first selected kickoff and a2h runtime cap; comparison jobs can be budgeted up to6h. Budgets stop before another model block; a current fit finishes before the next checkpoint. Use exact resume for a held data/configuration snapshot, or start a new run to incorporate fresh data.

## What is simulated

Games use all six existing lab model factories with fixed preregistered parameters and equal averaging. Props use four factories and equal averaging. These are matched shadow ensembles, not a retraining or replacement of the production champion. Parameters, recency weights and feature-window definitions match across the two arms. Full-history does not mean using every raw column: outcome-contaminated/unknown fields remain excluded and FPDS feature groups are capped and regularized.

Training includes2023–25 and completed2026 weeks where available. Source week w is usable only after its final scheduled kickoff+24h; future candidates are capped at the run's actual creation time, not their later kickoff. Last1/3/5/8 windows count played games, skipping byes. Later-week projections use today's known roster/role information and explicitly unknown future lineup/weather changes. They never use future results. All historical seasons remain in training with the lab's recency weights; older seasons are not dropped.

Simulations draw empirical residuals for yards/margin/total, Poisson counts and Bernoulli win/TD outcomes. First TD is a categorical offensive rushing/receiving scorer distribution including OTHER_PLAYERS and NO_OFFENSIVE_TD. Passing, defensive and special-teams scorers are excluded. These are distribution simulations, not the existing play-by-play simulator. Mean model prediction and simulated mean can differ after nonnegative clipping. Seeds change Monte Carlo draws, not model parameters or selection. A single seed does not establish stability.

Completed matched development runs supply earlier out-of-fold calibration/residuals to later forecasts only when code, protocol, libraries and historical input fingerprints match exactly. Otherwise training-residual warm-up is labelled and unvalidated. No old2025 simulator evaluation is run, rescored or overwritten. No new2025 confirmation is offered;2022–24 were already examined. New evidence requires truly future archives.2026 results never select configurations.

## Outputs and limits

Jobs, checkpoints, private logs and derived forecasts live under ignored `data/cache/fpds/amendment6/manual/jobs/<id>/`. Every forecast gets a new creation-time subdirectory. The page displays local derived game/prop tables and aggregate comparisons, never source CSV rows. No raw/derived subscription data is committed, pushed or uploaded. No manual job invokes git push, publishing, alerts or promotion.

Market lines enter after independent fitting, as benchmarks. Closing game lines support historical forecast-loss comparisons; historical prop prices are absent. No tradable edge or return is inferred. All forecasts remain tier C until stability, coherence, scenarios and genuine prospective validation are established. Revised/capped exports and unverified historical publication dates still limit conclusions.

`scripts\launchers\run_weekly_fpds.bat` remains the separate Amendment6 frozen archival workflow. It is preserved; use the manual page/menu above to force matched FPDS challengers for games and props rather than silently replacing its frozen control choices.
