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

1. If available, put **injury-reports.csv** in the active Week folder. If the vendor publishes it after games, it is historical research context only; do not treat it as pregame evidence. You may replace your downloaded copy yourself; this program never modifies/moves/deletes it and copies every imported content version privately by hash. A CSV is optional for option 6.
2. Choose **START_HERE → 6: Update this week's injuries only**. It refreshes the existing official/ESPN/live feeds first, imports the CSV, then compares their statuses. Explicit week: `scripts\launchers\update_fpds_injuries.bat --week 7`.
3. Reload FPDS Research. It shows the import date, source modification/first-observation dates, current-week row count, pregame exact-roster matches and unmatched count, plus source agreement/conflicts/CSV-only counts by team. No current-week rows produces a warning. No raw subscription rows are displayed.

The original official injury feed remains the model-input path; ESPN and other existing monitoring feeds remain active. The combined monitoring view prefers the latest observed official report. FPDS corroborates known statuses, or supplies provisional context if official information is missing. Conflicting secondary reports stay unresolved. A newer CSV download cannot blindly override an official designation. Re-imported CSV content supersedes the previous CSV view, with every prior version retained. Existing live refreshes automatically recompute comparisons for imported, unstarted weeks; no new task is created. Failures in the supplemental comparison are private diagnostics and do not disable original refreshes. Agreement may reflect shared provider information, and rows older than24h are counted separately; agreement is not proof of freshness or independence.

**Injury updates are context, not adjustments to frozen probabilities.** Existing frozen configurations lack a validated mapping from live FPDS status text to forecast changes. Current-week snaps, fantasy points, yards and other outcomes never enter status context or same-week training. Only player/team/status/observation metadata are retained in private derived context. Unknown statuses/IDs stay unknown; vendor publication time remains unverified. Re-importing does not establish fresh vendor information. No forecast is rewritten or labelled injury-adjusted.

### NFL Meta fallback (2026-10-22)

With no CSV in the selected Week folder, option 6 retains the original feeds and tries NFL Meta, then writes the same source comparison view. It ignores any old CSV pointer for this run. Original official reports remain preferred; NFL Meta is secondary evidence, and disagreements remain visible. This does not rerun simulations or change archived projections.

Configure once from the lab folder: `.venv\Scripts\python.exe -m lab.nflmeta_injuries configure`. Enter the key at the hidden prompt, never in command arguments. Alternatively set `NFLMETA_KEY` locally. The local credential file is under ignored `data/private/`; it is not encrypted. Rotate a key shared in chat before entering its replacement. No secret is stored in tracked code or printed.

The collector checks `/usage`, allows only a reported Free plan, and requires at least one remaining request and 100 remaining rows. It requests at most 100 current-season weekly injury rows, caches for 30 minutes, refuses redirects, performs no retries, and stops on quota/auth/payment failures without upgrading or purchasing anything. A 100-row response is labelled possibly truncated. Partial/empty responses never mean everyone else is healthy. A paid-plan key is blocked pending a separate cost policy; Free supports private noncommercial research according to [pricing](https://nflmeta.org/pricing).

Append-only snapshots go to ignored `data/raw/archive/nflmeta/`. Exact normalized team/name matches on the selected week's roster resolve GSIS IDs; absent/ambiguous identities remain unmatched. Both source observation age and local retrieval age must be <=24h; source timestamps must not be in the future. Local retrieval is the earliest usable time, never a historical publication time. Missing source timestamps are excluded. See the [official OpenAPI contract](https://nflmeta.org/openapi.yaml): a date filter is explicitly not a historical as-of snapshot. No new backtest, fit, eval or promotion is performed.

## Operations

- Existing two-hour refit deadline/kickoff exclusion; idle priority, cores minus two. Season 2026, forecast weeks 7–18 only.
- One local folder-update lock; active manual jobs block weekly updates, and folder updates block new manual jobs.
- Readiness only: `python -m lab.fpds_drop plan --week 8` (no refresh/import/fit).
- Private results: `data/cache/fpds/amendment6/weekly_workflow/weekly/…/PREVIOUS_WEEK_RESULTS.md`. Latest pointers advance only on success. Raw copies/derived context stay ignored.
- Setup's only authorized Inbox writes were creating the twelve empty directories. Existing source files remain untouched. No tasks, new algorithms, promotion, deployment, paid access or model evaluation were run during setup.
- Rollback: revert the implementation commit; keep source folders/files and all archives.
