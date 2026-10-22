# Tuesday drops and injury updates

Open **START_HERE.bat**. All twelve folders have been created inside:

`GOING\FantasyPoints\Inbox\All historical data from 2021-2026 week 6\`

**Week 7, Week 8, Week 9, Week 10, Week 11, Week 12, Week 13, Week 14, Week 15, Week 16, Week 17, Week 18.**

The folder number is the **week to predict**: Week 7 uses completed weeks 1–6; Week 8 uses 1–7; Week 18 uses 1–17.

## Tuesday night

1. Put the same table exports in the upcoming **Week N** folder. Normal filenames work. Full-history exports or 2026 season-to-date exports with separate weekly rows are supported; cumulative season-summary rows are not a substitute.
2. Choose **START_HERE → 3: Tuesday weekly refresh + projections**. The cached schedule selects the next unstarted week; data refresh verifies completion. Explicit week: `scripts\launchers\run_weekly_fpds.bat --week 8`.
3. The workflow checks schema/coverage, fetches authorized local market archives, refreshes free NFL data, requires the prior week to be complete and its final kickoff +24h to have passed, imports hashed copies, and builds lagged features. It refits the existing frozen shadow configurations, archives weather/inactives through the existing pipeline, writes a new revision/presentation, scores prior frozen FPDS forecasts, updates standard champion scoring and tracks archived quote comparisons. A failure stops downstream work and retains diagnostics.
4. Open **Dashboard → Research → FPDS Research → Weekly folders and injury updates** for the new game/player tables, sheet paths and prior-week results. The older Phase 10 Projections/Leans pages remain separate and are not silently replaced.

There are **37 registered tables**, not approximately 27. From Week 8 onward every table must be present in that Week folder and contain 2026 weekly rows through the previous week. Missing table names are printed. Export caps and entity gaps remain separately audited. Week 7 can bootstrap from the existing authority with only injury updates in its new folder.

2021–25 history is retained when a drop contains 2026 only. New exports replace whole observed source-week blocks, including corrections/removals; absent older weeks remain. Unknown/ambiguous identities are not guessed. Later Week folders cannot enter earlier forecasts. Ordinary tables containing forecast-week outcomes are refused; those outcomes are excluded from injury histories.

Prior frozen forecasts/simulations are **scored against actual outcomes**, never used as training labels. Revisions are scored separately without choosing a winning revision. Reports are descriptive; 2026 never tunes/selects. The report runs when you click Tuesday's workflow, not through a newly scheduled Monday-night task. Scope: saved FPDS weekly control/frozen revisions and the existing champion scorer, not every older experimental simulation package.

## Injury updates during the week

1. Put updated **injury-reports.csv** in the active Week folder. The file may contain current-week injury rows and historical rows. You may replace your downloaded copy yourself; this program never modifies/moves/deletes it and copies every imported content version privately by hash.
2. Choose **START_HERE → 6: Update this week's injuries only**. Explicit week: `scripts\launchers\update_fpds_injuries.bat --week 7`.
3. Reload FPDS Research. It shows the import date, source modification/first-observation dates, current-week row count, pregame exact-roster matches and unmatched count. No current-week rows produces a warning. No raw subscription rows are displayed.

**Injury updates are context, not adjustments to frozen probabilities.** Existing frozen configurations lack a validated mapping from live FPDS status text to forecast changes. Current-week snaps, fantasy points, yards and other outcomes never enter status context or same-week training. Only player/team/status/observation metadata are retained in private derived context. Unknown statuses/IDs stay unknown; vendor publication time remains unverified. Re-importing does not establish fresh vendor information. No forecast is rewritten or labelled injury-adjusted.

## Operations

- Existing two-hour refit deadline/kickoff exclusion; idle priority, cores minus two. Season 2026, forecast weeks 7–18 only.
- One local folder-update lock; active manual jobs block weekly updates, and folder updates block new manual jobs.
- Readiness only: `python -m lab.fpds_drop plan --week 8` (no refresh/import/fit).
- Private results: `data/cache/fpds/amendment6/weekly_workflow/weekly/…/PREVIOUS_WEEK_RESULTS.md`. Latest pointers advance only on success. Raw copies/derived context stay ignored.
- Setup's only authorized Inbox writes were creating the twelve empty directories. Existing source files remain untouched. No tasks, new algorithms, promotion, deployment, paid access or model evaluation were run during setup.
- Rollback: revert the implementation commit; keep source folders/files and all archives.
