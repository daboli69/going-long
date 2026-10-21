# Local FPDS research and weekly runbook

The subscription Inbox is read-only. No website, API, account or key is used. Raw exports, unmatched identities, exact crosswalks, features, fitted models and forecast rows stay in ignored `data/raw/fpds/` and `data/cache/fpds/`. Git contains code, headers/counts/coverage and aggregated metrics only. All models are shadow challengers; the champion, v1 and earlier forecasts are unchanged.

## Weekly use

1. Put the newly downloaded full-history CSVs into `GOING\FantasyPoints\Inbox`. Keep the same table title and append `week 7`, `week 8`, or `Weeks 1-8` before `.csv`. The original historical folder stays in place. The importer copies; it never moves/deletes/edits Inbox files.
2. From this lab folder run `run_weekly_fpds.bat` (or `run_weekly_fpds.bat --week 8`). It requires a committed frozen Amendment6 configuration and the completed single validation pass. A failure stops the pipeline and retains a new partial revision; it never falls back to a different configuration.
3. The command prints the new private revision directory. Open its `projections.csv`, `game_projections.csv`, `leans.csv`, `leans.md` and `FORECAST.json`. Source and training cutoffs, creation time, hashes and model membership are retained. These are local subscription derivatives: do not upload/commit them. Investigation-readiness defaults to C where stability, coherence or scenario checks are unvalidated.

The weekly pipeline fetches origin/main without switching branches, archives only the authorized committed market file, refreshes free NFL inputs, imports/audits the full-history drops, prepares a new private base feature snapshot, updates the FPDS feature store and refits frozen shadow choices through completed games whose source-week final kickoff+24h precedes the decision. Weather/inactives are archived context only. It writes a new immutable revision, never a deployment, notification, champion pointer or model promotion.

## Research commands

Use the included environment at idle priority, leaving2 logical cores free:

```
.venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_research ingest
.venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_research audit
.venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_research features
.venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_research screen
.venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_research walkforward --phase discovery --resume --deadline 2026-10-21T12:49:41Z
.venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_research report
```

`run_fpds_research.bat` runs import/audit/features/screen and discovery. `screen` runs preregistered leakage diagnostics only; it adds no model configurations. The exact269 target-specific trial slots are in `FPDS_AMENDMENT6_TRIALS.json`. No parameter search beyond that inventory is allowed. Before a validation command, commit the discovery-selected `FPDS_AMENDMENT6_FROZEN.json`; then run `walkforward --phase validation --resume` once. Resume reuses exact configuration/season/block checkpoints under the same registration/data/code fingerprint; changing that fingerprint cannot silently reuse a frozen validation. A validation lock records the frozen hash.2025 was previously examined for the old simulator and is not a pristine holdout.2026 is descriptive only.

## Provenance and feature definitions

- Raw copies are named by SHA256 beneath `data/raw/fpds/amendment6/<table>/`. Import manifests preserve source path, file size, original modified time, export-through marker, import time and first observation time. Latest working views point at the highest export-through week, then modified time/hash. Identical input snapshots are idempotent.
- `REVISION_LOG.json` compares unique overlapping entity/weeks by qualified column, reporting changed-value counts and mean/max absolute numeric revision. Added/deleted entity/weeks are counted. An initial or identical snapshot cannot establish the frequency of earlier vendor revisions.
- Body `SEASON`/`SEA` overrides a conflicting outer `Season` export selector. Malformed/calendar/summary rows are reported. Future2026 weeks beyond the file marker are excluded. A round-number row count flags a possible export cap; observing every week does not establish complete player coverage.
- Players resolve by exact unique full-name aliases plus source-week roster/team evidence. Unambiguous positive native vendor-ID anchors may extend an exact GSIS crosswalk only with the same source-week team check. Ambiguous IDs/names stay unmatched. Receiver and defender identities are distinct. `Defense` is never assigned a GSIS player ID. Trades and position changes retain their actual source-week/team context; no future matchup is guessed.
- Source statistics from week w are unavailable until its final scheduled kickoff+24h, and cannot predict week w. Historical reconstructed joins obey that clock but cannot verify original vendor publication times or revisions. True prospective joins also require an actual pre-decision import timestamp. Missing history remains missing on identical eligible control/challenger rows.
- Last1/3/5/8 features average observed played-game rows, skipping byes. STD averages reset by season. EWMA uses alpha.3 across observed games. Role change is last1 minus last3. Position adjustment subtracts the same completed source-week/position cohort mean; no target-week outcomes. Native weekly splits or lineup combinations are overlapping units, so their numeric aggregates are explicitly arithmetic means, never invented team totals.
- At most12 header-selected metrics/table are cached with every window; a fixed equal table allowance limits model inputs to768 FPDS columns. Semantic priority reserves scoring paths (xTD/i5/i20/end-zone), role shares, depth/efficiency and matchup/pace metrics. No individual-column validation selection. Game models add earlier team means to the lab's independent NFL-only inputs; spreads/totals/odds remain benchmarks.
- Unknown cumulative units, undated target-week injury/shadow assignments, fantasy points, DFS values, projections, rankings and unknown text are excluded. A verified games>1 flag blocks treating a cumulative table as individual games. Historical injury-table usage changes can be tested; causal on/off effects and actual target-week replacements are not identified by these weekly exports alone.
- Analytical structural proxies use historical volume/role and independent game points. They are labelled proxies, not the unchanged play-by-play simulator. Counts use Poisson/hurdle heads with earlier training dispersion diagnostics; yard intervals use earlier emitted residual quantiles, with a labelled training-residual warm-up. First TD means the first regulation offensive rushing/receiving scorer, plus other-player and no-offensive-TD classes; passing, defensive and special-teams scorers are excluded.
- Pseudo-lines are the last8 verified played NFL games' median rounded to a half-unit. They test probability calibration, not a historical prop-price edge. Real market comparisons use only games.csv closing lines or timestamped authorized2026 quote archives. Current means quote age<=24h; unknown/future/in-play quotes do not become verified consensus comparisons.

## Reports and safety

`FPDS_DATA_DICTIONARY.md` covers every file/column; `FPDS_COLUMN_COVERAGE.json` gives nonmissing cell counts per column/season/week. Public run reports contain aggregates only. Private errors never print source rows. Research status is written every30min by the worker; inspect a long-running worker no more than once an hour. Every attempt and fit block is logged. The initial discovery is capped by its explicit deadline; no new task starts in the final45min before09:34:41 ET21October.

Qualified shadow evidence requires the preregistered corrected discovery gate, sign agreement across at least2of3seasons and the same direction in the single frozen2025 pass. Retrospective truncation/revision/publication risks and previous holdout exposure remain limitations even if a statistical gate passes. Forecast error improvement is not a betting-return claim or proof of a tradable price edge.
