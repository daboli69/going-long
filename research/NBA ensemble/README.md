# NBA Ensemble — local winners first

Double-click **START_NBA.bat**, press Enter, and open **http://localhost:8502**. NFL remains at8501 in its own folder. This NBA package never imports NFL code, forecasts or credentials. Initially the launcher can borrow the installed NFL Python *libraries* read-only; every NBA source/cache/model/archive/report lives here. No NFL environment files are modified.

## What to click

- **Today:** select a date; view six-model votes, the frozen combined win probability and disagreement. Refresh/refit/save creates new immutable archives, not replacements.
- **Model Debate:** the six predictions, real input sensitivities, disagreement, vote and ensemble comparison. This is a comparison of statistical models, not invented AI arguments. A3–3vote remains a tie;6–0is not100%probability.
- **Research & Calibration:** discovery/confirmation results, uncertainty and reliability. Read sample sizes and data caveats before trusting a percentage.
- **Data & Sources:** actual source usage, missing data and feature audit. Source availability is not proof a feature entered the model.

Launcher option2 runs the daily refresh → earlier-game feature build → frozen configuration refit → today's unstarted-game archive. Option3 displays saved research. No research search or confirmation rerun occurs during daily refresh. Results include training/calibration cutoffs, config/model version and source hashes.

## Six initial candidates

Regularized logistic regression, random forest, XGBoost, histogram gradient boosting, RBF support-vector classifier and MLP neural network. They are candidates, not asserted to be the six best NBA algorithms. Equal, earlier-OOF weighted and chronological stacked combinations are evaluated; the selected combination is frozen before a single later confirmation season. Model/correlation agreement is descriptive. No model is automatically promoted.

## Initial setup/research

The initial build is performed once. If starting a clean copy, from this folder use your NBA `.venv\Scripts\python.exe`, or the existing read-only runtime `..\nfl-ensemble-lab\.venv\Scripts\python.exe`:

```powershell
& '..\nfl-ensemble-lab\.venv\Scripts\python.exe' -m nba_lab.cli refresh
& '..\nfl-ensemble-lab\.venv\Scripts\python.exe' -m nba_lab.cli features
& '..\nfl-ensemble-lab\.venv\Scripts\python.exe' -m nba_lab.cli develop
# Review and commit docs/FROZEN_CONFIG.json BEFORE the one-pass confirmation.
& '..\nfl-ensemble-lab\.venv\Scripts\python.exe' -m nba_lab.cli confirm
& '..\nfl-ensemble-lab\.venv\Scripts\python.exe' -m nba_lab.cli train
& '..\nfl-ensemble-lab\.venv\Scripts\python.exe' -m nba_lab.cli predict
```

For a fully standalone environment: `py -3.12 -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r requirements.txt`. These are free open-source packages; no accounts/keys/paid APIs required. The launcher prefers this environment when present. Optional SDKs are not installed into NFL's environment.

## Data, as-of rules and limits

hoopR and sportsdataverse-py share SportsDataverse ESPN schedules/team boxes; they are not independent providers. These public release datasets provide the v1 winner features. All historical features are lagged using earlier games, with a conservative tipoff+24h result-availability proxy and strict decision-time audit. Historical files are revised/backfilled; this cannot establish actual historical publication availability. Prospective files retain real creation/retrieval metadata. Box mismatches/duplicates are quarantined/refused, not guessed. Season numbers use the **ending year**:2026means2025–26.

Optional context archives: `python -m nba_lab.cli context --source nba_api --season 2026` and `python -m nba_lab.cli context --source pbpstats --season 2026`. These public endpoints need no key, but servers may refuse/time out. Errors are reported. NBA Stats IDs need an explicit crosswalk; PBP Stats season totals must never become retrospective same-season features. The `pbpstats` package's possession/lineup enrichment is a later phase, not a falsely advertised v1 input. See docs/PREREGISTRATION.md for exact active features/splits/budget and links to the five requested projects.

**Current injury/lineup/rest-day decisions are NOT modeled as verified live player availability in v1.** Rest/back-to-back schedule features are included, but are not a substitute for injury reports. Current outcomes may be descriptively logged, never used to retune the frozen experiment. No NBA odds are downloaded; no market/ROI/profit claim. No deployment, alerts, database writes or paid services.

Winners are the first validated target. Spreads/totals require separate score-distribution targets/calibration; props require player minutes, rotations, trades and availability with historical timestamps. Those are not safely established by copying the NFL simulator. They remain deferred, not fabricated.

## Verification and storage

Run `python -m pytest -q tests`. Tests use offline fixtures: target-week/future-outcome canaries,24h lag, duplicate/box consistency, calibration chronology, probability bounds, missing-data pages and archive safety. Raw data/models/reports/forecasts are ignored in Git. Human-reviewable protocol/frozen config/code are tracked; no secrets. A failed workflow stops clearly and leaves prior archives intact. Research folds checkpoint by source/config hash; confirmation output is read-only once completed.
