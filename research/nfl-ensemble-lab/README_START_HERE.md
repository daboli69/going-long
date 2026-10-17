# NFL Ensemble Lab: start here

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
