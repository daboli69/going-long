# Phase 10 local archives

## Amendment 3: reviewable scheduler script and weekly command

Launch the local app with `launch_lab.bat`, then choose **Projections** or
**Leans**. Generate a fresh append-only shadow revision with
`run_week_projections.bat --week 8` (omit week to use the next week after the
last wholly completed week). `--plan` prints the planned slate/cutoff without
refreshing or fitting. Default runtime cap is150 minutes; `--max-minutes` changes
the operational budget, never model parameters. Default simulations are1,000
with three fixed seeds; unstable outputs stay flagged. Explicit future-week
features use only observations available now, so distant lineup uncertainty
remains. The original forecast and reconciled accounting remain side by side.

The standalone T-90 command is:
`.venv\Scripts\python.exe -m lab.low_priority -m lab.inactives10 collect`.
Outside T-90 it reports no due games and fetches no official lists.

**No task has been created or script executed by Codex.** Travis can review:

```powershell
.\scripts\register_archive_tasks.ps1 -WhatIf
```

The script prints each proposed action and creates two interactive-user tasks
only when Travis runs it without `-WhatIf`: daily quotes repeating every3 hours
(git fetch main, then remote-main archive), and daily inactive polling every5
minutes (collector only retrieves inside T-90). Actions run hidden, at idle
Python priority with two logical cores free, with no elevated privileges.
Review names/actions in Task Scheduler afterward; these are local archives,
not publishing/notification jobs. Runtime task registration remains unverified.

All paths below are inside `research/nfl-ensemble-lab`. Nothing is deployed, no
Windows tasks are created by this work, and no odds API is contacted. The game
champion and simulator v1 numerical outputs remain unchanged by default.

## Collection and provenance

| Archive | Collector | Immutable content and time |
|---|---|---|
| `data/raw/archive/market/going_*.json` | `python -m lab.phase10_archive --history` (one-time recovery); `--remote-main` (latest fetched main) | Full-game spreads/totals/moneylines plus period quotes; book, source quote time, kickoff, generated_at, commit observation time, content SHA-256. Raw quoted-team spread sign is preserved. |
| `data/raw/archive/props/going_*.json` | Same command | Passing yards/TDs, receptions, receiving/rushing yards, anytime/first TD where actually present; exact existing player-map identity, unmatched names and unsupported markets reported. |
| `data/raw/archive/weather/open_meteo_*.json` | `lab.prospective.fetch_weather` | Full response for **every** Open-Meteo pull, forecast_retrieved_at and hourly valid_time, requested coordinates, content SHA-256. Context only. |
| `data/raw/archive/inactives/official_*.json` | `lab.inactives10.collect` | Complete scoped official NFL lists, publication/observation times and source hash, reusing only the read-only topdown parser/retriever. No notifier/update path is invoked. |

JSON files are created exclusively and made read-only. Identical market/prop
content is deduplicated; generated/retrieval times alone do not create a new
quote file. Files already archived are never changed or deleted. Weather saves
each pull even if content is unchanged. Hashes cover normalized content; provenance
is outside that hash. Git history is read oldest first so first observation is
retained. A new collector can recover a later previously unseen history blob.

T1 requires **both** source quote time and independently recorded file/commit
observation time before kickoff, with quote time <= observation. An old embedded
quote read today is not retroactively verified. Unknown timestamps stay unverified;
no T2 opening/T3 closing class is invented. Existing Phase 8.1 T2/T3 source readers
are unchanged, but Phase 10 never calls them. A quote older than 24 hours at the
decision is labelled `stale`; unknown or future times are not called current.
DFS lines retain their DFS label and absent prices remain null. No odds/ROI is
fabricated, and no closing-line fallback fills missing GOING quotes.

Freshest-copy procedure, without switching branches:

```powershell
git fetch origin main
.venv\Scripts\python.exe -m lab.phase10_archive --remote-main
```

The collector uses `git show origin/main:data/nfl_betting.json`; it never checks
out that file or fetches automatically. The post-forecast scheduler hook archives
the last fetched copy, then weather and official inactives in the T-90 window.
The old automatic ESPN odds request is replaced by this local-file hook. This is
development code only: the pinned release is not updated or activated here.

## Shadow projections after the committed freeze

```powershell
# Fit the frozen statistical configuration with permitted recent data.
.venv\Scripts\python.exe -m lab.props.ensemble.production --threads 7
# Fit recent structural tables and archive unstarted games in the prepared horizon.
.venv\Scripts\python.exe -m lab.props.ensemble.structural --season 2026 --production --sims 1000
# Archive combined forecasts and write weekly CSV/Markdown sheets.
.venv\Scripts\python.exe -m lab.props.weekly projections
```

The first command refuses to read 2023–25 player data until Amendment 1 and its
runtime settings are committed. It trains through the last **fully completed**
2026 week; a partial week is excluded. The recent fit is a local shadow artifact,
not a champion promotion or a deployment. Every prospective JSON records the
training cutoff date, frozen configuration hash, revision and pregame creation
time. Existing forecast files are reused without alteration. The independent
ensemble never includes the market-anchored member; that member appears only in
the separately labelled market-informed comparison.

`run_weekly_predictions.bat` writes these sheets after the existing winner report.
CSV/Markdown work with the lab environment alone. A local Artifact Tool runtime
can also export `.xlsx` using `scripts/projections_xlsx.mjs` when
`NFL_LAB_ARTIFACT_NODE` names its Node executable and `NFL_LAB_ARTIFACT_WORKSPACE`
names a directory with a `node_modules` junction to the provided runtime. No
package download or service is used by the exporter. The CSV retains every
book-line comparison; the first-TD Excel view deduplicates player/game rows so
its categorical probabilities can be summed without counting books twice.

The first-TD target is the first offensive rushing/receiving TD in regulation.
Archived quote rows do not establish matching settlement rules, so first-TD
price-probability gaps are unavailable. Binary anytime-TD forecasts likewise
cannot price multi-TD count thresholds such as 1.5. Derived reports suppress
these comparisons; append-only correction records preserve the original
immutable forecasts and the reason for each display correction.

Yard intervals include an explicit quantile-head view and an equal-member mixture
view. Learned-member predictive samples use centered 2022 out-of-fold residuals
for yards and Poisson rate approximations for counts; structural distributions
come from simulated plays. These are experimental distribution assumptions,
not a guarantee of calibrated coverage. Probability pushes are separate from
strict over/under/cover events. Member agreement is descriptive, never a probability.

## Exact Windows Task Scheduler steps (manual review required)

1. Keep the existing pinned forecast task as-is until the development changes are
   reviewed and a tested release is explicitly approved.
2. Open **Task Scheduler → Create Task**. Name it `NFL Lab - Local Quote Archive`.
   Select **Run only when user is logged on**; leave highest privileges unchecked.
3. **Triggers → New → Daily**, start 06:00 local, repeat every **5 minutes** for
   **1 day**, enabled. A local-only quote archive does not refresh the Git remote;
   use the explicit fetch procedure above when a fresh committed file is needed.
4. **Actions → New → Start a program**. Program:
   `C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\nfl-ensemble-lab\.venv\Scripts\pythonw.exe`.
   Arguments: `-m lab.phase10_archive --remote-main`.
   Start in: `C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\nfl-ensemble-lab`.
5. **Conditions:** choose power/wake settings appropriate to this PC. **Settings:**
   allow on-demand runs, run when a scheduled start is missed, stop after 4 minutes,
   and **Do not start a new instance** when already running.
6. After explicit approval of a tested release containing this scheduler hook,
   use the existing forecast-task release procedure in `docs/RELEASES.md`. Its
   post-forecast hook handles A1–A3 and inactives. Do not point the live forecast
   task at a changing development checkout. No task is registered by this document.

## 2026 personnel and pressure

`pbp_participation` ends in 2025. Phase 4 personnel features therefore carry the
2025 team mean in the `blend` columns and the last five available pre-kickoff
observations (normally late 2025) in `l5`. `lab.advanced.window_features` sets
current-season count to zero when the last source season differs, then uses the
previous-season mean; missing history stays missing. These values do not represent
observed 2026 personnel. Phase 5 participation
RAPM likewise stops there. Phase 7's separate snap-based player model uses 2026 PFR
snap counts with prior seasons weighted 0.6/0.35 (`lab.snap_model`). PFR pressure
and available FTN rows have their own source coverage; absence must not be
reported as zero pressure. Phase 10's learned props exclude routes/participation
and weather where a validated history is unavailable, and report missing feature
fractions in `artifacts/props/phase10/feature_provenance.json`.

Measured column coverage is saved in `reports/run_20261019/phase4_2026_coverage.csv`.
PFR pressure and NGS, when published for 2026, use strictly prior-game expanding
means blended with three prior-season games of weight (`BLEND_K=3`), plus last-five
windows. A nonmissing personnel value is therefore not proof of 2026 participation.
