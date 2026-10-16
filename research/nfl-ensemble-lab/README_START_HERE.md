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

## Where things are saved

| Folder | Contents |
|---|---|
| `reports/` | Excel workbooks (`NFL_Ensemble_Training_Results.xlsx`, `NFL_Weekly_Predictions_YYYY_WW.xlsx`) plus CSV/JSON copies |
| `snapshots/` | Read-only, timestamped weekly predictions. They are never overwritten. |
| `models/` | One folder per trained version; `CURRENT.json` names the active one |
| `artifacts/runs/` | Out-of-sample predictions and metrics from every training run |
| `data/` | Downloaded source files and the pregame feature store |

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
