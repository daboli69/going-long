# NFL Ensemble Lab: start here

## Local FPDS weekly refresh (Amendment 6)

Drop the new full-history `week N` CSVs into `GOING\FantasyPoints\Inbox`, then run **`run_weekly_fpds.bat`** from this folder (`--week 8` selects a week explicitly). The Inbox is read-only to the program. It imports hashed versions, audits revisions, refreshes NFL inputs and authorized local lines, refits committed frozen shadow configurations, and prints the new private projection/leans paths. It requires the frozen discovery selection and completed single validation; failures stop clearly and preserve earlier files. Do not upload or commit the local subscription derivatives.

Without `--week`, the next future regular-season kickoff selects the target week; refreshed results determine the completed-week training cutoff. Stale completion flags cannot send the default run back to last week.

See [the FPDS runbook](docs/FPDS_RESEARCH_PROGRAM.md), [data dictionary](docs/FPDS_DATA_DICTIONARY.md) and [pre-registration](docs/PHASE10_PREREGISTRATION.md). All output remains shadow research, with no promotion or established betting edge.

The [weekly download list](docs/FPDS_WEEKLY_DOWNLOADS.md) distinguishes frozen input requirements from exploratory table importance. The [full research report](reports/run_20261020/FPDS_FULL_REPORT.md) records the single frozen confirmation and remaining limits; complete aggregate metrics are in `FPDS_A6_RESULTS.json` and `FPDS_A6_CONFIRMATION.json` beside it.

Open **`launch_lab.bat` → Section: Research → Page: FPDS Research** for aggregate coverage, errors and evidence. The page is view-only and never reads subscription rows. The weekly command prints the reviewed private presentation folder containing `projections.csv` and `leans.csv`; use that presentation rather than the intermediate computational sheets. A refit is blocked within2h of kickoff. Use **`run_weekly_fpds.bat --comparisons-only`** to refresh authorized archived prices and comparisons without changing model forecasts. Same-book pregame quote tracking is descriptive; the last archived quote is a closing proxy, not a verified actual close.

A local research lab on your Windows PC. Six machine-learning models each
forecast every NFL game. They vote, explain their reasoning, and are combined
into one calibrated probability. Everything runs on your CPU and uses free
public data. It is a research tool: it does not place bets or recommend them,
and it is not connected to the GOING website.

## First time (about 10 minutes)

1. Install **Python 3.12** from <https://www.python.org/downloads/windows/>.
   In the installer, tick **"Add python.exe to PATH"**.
2. Open this folder (`GOING\research\nfl-ensemble-lab`) and double-click
   **`setup_windows.bat`**. Wait for "Setup complete".
3. Double-click **`launch_lab.bat`**. Your browser opens the lab at
   <http://localhost:8501>. Keep the black window open while you use it.
4. In the lab:
   1. **Data Manager → Download Historical Data** (first time: about 1 minute, ~250 MB).
   2. **Train Models → Train All Six Models** (about 2–5 minutes).
   3. Open **Model Debate** or **Weekly Predictions**.

## Every week

### Finding your way around

The sidebar has a **Section** selector: Overview, This week, Insights, Models,
Research, and Data & history. Pick a section, then choose from its short **Page**
list. Every original page is still available, and each section remembers your last
page during the session. Existing direct page links still work.

### Phase 10 shadow projections and leans (local app)

Run `launch_lab.bat` from this folder, then open **Projections** or **Leans** in
the **This week** section of the sidebar. Players default to one current
representative consensus line;
Leans also hides mean/median skew flags. Tabs show games, first offensive TD,
scenarios (not forecasts), and team/player coherence. Use the glossary, slate
diagnostics, optional venue/stale toggles, and filtered CSV downloads.
The launcher opens Projections directly on loopback only, at idle priority with
two logical cores free. Use **Reload saved sheets** after a pipeline completes;
the snapshot selector also lets you inspect older weeks/revisions.

These pages read immutable `reports/projections_*.csv` / `reports/leans_*.csv`
and their diagnostic companions. Selection uses season/week, forecast revision,
and filename creation time; file mtime only invalidates the read cache. Missing
evidence remains unknown. No page render refreshes data, fits or promotes a model.

One command for a new weekly shadow revision (run from this folder):

```powershell
.\run_week_projections.bat --week 8
```

Omit `--week` to use the next week after the last wholly completed week. The
runner stops on any failed phase and prints a manifest plus sheet paths; earlier
forecasts are never replaced. This is separate from the champion workflow below.

For manually downloaded Fantasy Points exports, run `import_fpds.bat`. It reads
the sibling `GOING\FantasyPoints\Inbox` without changing it, preserves hashed
copies and creates private weekly feature caches. Read `docs/FPDS_INGEST.md` for
coverage, missing weeks and mapping counts. Subscription files and row-level
derivatives stay ignored/local. FPDS is a shadow research input; importing it
does not change the frozen weekly forecast configuration. Development findings
and the tentative weekly download list: `reports/run_20261020/FPDS_REPORT.md`.

- Double-click **`launch_lab.bat`**, open **Weekly Predictions**, click **Generate Weekly Predictions**,
  then download the Excel file. Or
- double-click **`run_weekly_predictions.bat`**: it refreshes data, predicts the next week with
  the saved models (no retraining), and opens the `reports` folder.

Retrain occasionally (for example monthly) so the models learn from new games. Old
models and old predictions are kept.

**Injury history (important):** official injury designations for 2025 onward are only usable
if this lab saved them *before* kickoff. Double-click **`refresh_data.bat`** (or schedule it
daily in Windows Task Scheduler) so each week's Friday/Saturday report gets archived in
`data/raw/archive/`. Never delete that folder; it cannot be re-downloaded with timestamps.

## Phase 7: 2026 data and QB intelligence

- **New page, Data Coverage & Gaps:** every source, what it is used for, what is missing, source health,
  and per-game gaps.
- **New live sources (monitoring only):**
  - the NFL.com official injury report
  - nflverse weekly rosters
  - Sleeper (QB depth and status)

  All three refresh automatically with the light refresh.
- **QB labels:** a QB listed Out on the official report no longer shows as a conflict. The Baltimore case
  was the official report being right.
- **New shadow challenger:** a snap-based player model (current for 2026) plus a "returning starter" QB
  rule, registered as `v20261017_142546_p7_qb_snap`. The champion is unchanged.
- **Details:** `docs/PHASE7_DATA_QB.md`.

## Phase 7.3: faster, on-time forecasts

- **Faster pregame forecasts:** about 45 seconds instead of about 3 minutes. Unchanged history is now reused
  from safe caches instead of being recomputed.
- **Timing labels:** each archived forecast records its scheduled time, actual time and whether it was on time.
- **Operations panel:** the **Live Readiness** page now has one.

After changing any lab code, run one refresh before game time so the caches are warm. Details: `docs/PHASE7_3_PERFORMANCE.md`.

## Phase 7.2: expected lineups and injuries

The **Model Debate** page has a new "Expected lineups and injuries" section for each team: starters expected out, confirmed
absences, uncertain starters with their probabilities, and the offensive line. It is analysis only: the champion and
challengers don't use it.

A pre-declared development test found the lineup features slightly helpful but not reliably so, so no new
challenger was added. Details: `docs/PHASE7_2_INJURY_LINEUPS.md`.

## Phase 7.1: what each model knew

The **Model Debate** page shows, for each game:
- the QB and injury report that the champion and each challenger used;
- what live monitoring knows now (monitoring only);
- every archived pregame forecast.

A warning appears when live news conflicts with the champion's QB assumption.

The **Live Readiness** page shows every kickoff-relative stage (archived, missed or pending) and the three-model
prospective comparison, with sample sizes.

Details: `docs/PHASE7_1_LIVE.md`.

## Live schedule (Phase 6): what runs automatically

One Windows task, **"NFL Ensemble Lab - Data Refresh"**, runs a small scheduler every 5 minutes in the
background (no window pops up, no dashboard needed). It is safe to leave on permanently. All times are
New York time and DST is handled automatically.

- **Every day:** data refresh at 6:00 AM, 9:00 AM, 12:00 PM, 3:00 PM, 6:00 PM and 9:00 PM.
- **Game days:** live refresh every 30 minutes, from 3 hours before the first kickoff to the last kickoff.
- **Each game** (follows the real kickoff, including Thursday, Monday, international and moved games):
  - early-week forecast (Tuesday noon);
  - Friday injury-report forecast (Friday 6 PM);
  - 24 hours before;
  - 3 hours before (live refresh);
  - 90 minutes (inactives);
  - 60 minutes;
  - final at 30 minutes.

Each forecast is saved once, read-only. If the PC is off or asleep when a step is due, that step is
marked **missed** (with the reason) and never filled in after kickoff. The schedule continues
automatically when the PC wakes. See **Live Readiness & Schedule** for:
- every game's data status;
- upcoming and missed events;
- source freshness;
- detected injury, QB and transaction changes.

Official game-day inactive lists are not freely available as data; the lab shows ESPN-reported
inactives (partial) and labels them that way.

`refresh_data.bat` now means "refresh now by hand" (full refresh, then one scheduler run).

**Which code the task runs:** the task should run a pinned, tested release (`releases
un_tick.pyw`),
not this development checkout, so code edits can never break a live pregame forecast. Use
`release_lab.bat release <tag>` to ship, `release_lab.bat rollback` to go back, and
`release_lab.bat status` to see which code runs. The Live Readiness page shows the same thing
("Scheduler code version"). Full procedure: `docs/RELEASES.md`.

## Automatic prospective tracking (Phase 3)

The Windows scheduled task **"NFL Ensemble Lab - Data Refresh"** runs `refresh_data.bat` daily at
9:00 and 18:00. You do not need to open the dashboard. Each run:

1. refreshes data and archives the official injury report;
2. freezes a prediction for every game kicking off in the next 8 days, written once and read-only:
   - **early** snapshot: 30 hours to 8 days before kickoff (one per game);
   - **final** snapshot: within 30 hours of kickoff (a new one only when inputs changed). The last
     one before kickoff is scored;
3. scores finished games against those frozen predictions.

**If the PC is off or asleep:** Windows runs the missed task as soon as the PC is back. A cutoff
window that passes completely while the PC is off cannot be filled in afterwards. The game is marked
**MISSED** on the **Data Freshness** page, with the reason. Predictions are never created after kickoff.
The task runs only while you are logged in to Windows.

Dashboard pages: **Prospective Performance** (unseen 2026 games only), **Prediction Archive**,
**Data Freshness** (runs, stale data, missed cutoffs), **Baseline Research** (model-improvement study).

## Overnight model research (Phase 4)

1. Double-click **`run_overnight_research.bat`**, type `8` and press Enter (or 1, 4, 12).
2. You can close that window. Research keeps running in the background at low priority, using
   about 6 of your 16 CPU threads, so the PC stays usable.
3. In the morning, open the dashboard (**`launch_lab.bat`**) → **Long-Run Research**. You'll see
   trials per model, the best version of each of the six models, and the one-time validation check.
4. To stop early: **`stop_research.bat`** or the Stop button. Completed trials are always kept. A stopped
   or interrupted job can be resumed from the same page ("Resume").

Only one research job can run at a time. Research never replaces the champion: a model that wins its
validation check can only become a *shadow challenger*, and promotion needs 128+ real future games.
The **Advanced Football Intelligence** page shows the new data (Next Gen Stats, PFR pressure and contact
stats, personnel, roster experience), matchup views, and whether those features helped.

## Player-level intelligence (Phase 5)

- **Player Intelligence** page: pick a game to see each team's projected lineup value, which players are
  out (from verified pregame injury reports) and who replaces them, unit strengths (QB, OL, receivers,
  DL, LB, secondary), how often the projected units have played together, and how much history each
  lineup has. All of it is built only from games before kickoff.
- **Model Debate** has a sixth tab, "Players, matchups & uncertainty". It shows the same context plus any
  *statistically supported* evidence that a model does better or worse in this kind of game.
- Run the Phase 5 study from **Long-Run Research** → "Phase 5 experiments" (about 40-60 minutes, background).
- No 2026 player-participation file is published yet, so player ratings for 2026 games use data through
  2025. The pages show how stale they are.

## Upset Discovery (Phase 2 research)

- Double-click **`run_research.bat`** (a few minutes). It refreshes data, runs the readiness gate,
  searches for upset/mispricing patterns, validates them on later seasons, makes experimental
  forecasts for the upcoming week, and writes `reports/NFL_Upset_Discovery.xlsx`.
- In the dashboard: **Upset Discovery** (catalog), **Upset Explorer** (one game: original vs
  experimental probability and why), **Research Validation** (did anything beat the baseline?),
  **Research Runs** (run experiments, history, settings).
- It never retrains or replaces the main models, and the twice-daily data refresh never runs it.
- Current result: about 30,000 candidate patterns tested, **none survived validation**, so the original
  ensemble stays the primary forecast. See `docs/PHASE2_DISCOVERY.md`. Nothing here is a betting edge.

## Where things are saved

| Folder | Contents |
|---|---|
| `reports/` | Excel workbooks (`NFL_Ensemble_Training_Results.xlsx`, `NFL_Weekly_Predictions_YYYY_WW.xlsx`) plus CSV/JSON copies |
| `snapshots/` | Read-only, timestamped weekly predictions. They are never overwritten. |
| `models/` | One folder per trained version; `CURRENT.json` names the active one |
| `artifacts/runs/` | Out-of-sample predictions and metrics from every training run |
| `artifacts/discovery/` | Read-only discovery experiments (inputs, config, seeds, catalog, adjusters) |
| `data/` | Downloaded source files, the pregame feature store, and `raw/archive/` (timestamped injury snapshots; keep it) |

None of these folders are committed to git.

## How to read the outputs

- **Vote (e.g. 5-1)** shows how many models picked each team. Two of the six models
  (Logistic Regression and the Single-Layer Neural Network) are mathematically the
  same kind of model, so the votes are not six independent opinions. **6-0 does not mean 100%.**
- **P(home)** is the calibrated probability from the research champion, which was chosen
  on 2023–2024 results before 2025 was ever scored.
- **Predicted margin** is an expected value, not a final-score prediction.
- **Sportsbook comparison** uses public closing lines as a benchmark only. Nothing here
  shows that betting on these forecasts would make money.

## If something goes wrong

- *"Python 3.12 or 3.11 was not found"*: install Python 3.12 and tick "Add to PATH".
- *Browser shows "can't connect"*: wait 10 seconds and refresh; check the black window for red errors.
- *"No trained models yet"*: run **Train All Six Models** first.
- Technical details: `docs/METHODOLOGY.md`, `docs/DATA_SOURCES.md`.

For developers: `.venv\Scripts\python.exe -m pytest` runs the test suite;
`python -m lab.cli refresh|train|predict|report` runs each step without the dashboard.
