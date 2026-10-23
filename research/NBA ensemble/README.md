# NBA Ensemble — local winners first

Double-click **START_NBA.bat**, press Enter, and open **http://localhost:8502**. NFL remains at8501 in its own folder. This NBA package never imports NFL code, forecasts or credentials. Initially the launcher can borrow the installed NFL Python *libraries* read-only; every NBA source/cache/model/archive/report lives here. No NFL environment files are modified.

## What to click

- **Today:** select a date; view six-model votes, the frozen combined win probability and disagreement. Refresh/refit/save creates new immutable archives, not replacements.
- **Model Debate:** the six predictions, real input sensitivities, disagreement, vote and ensemble comparison. This is a comparison of statistical models, not invented AI arguments. A 3–3 vote remains a tie;6–0 is not 100% probability.
- **Research & Calibration:** discovery/confirmation results, uncertainty and reliability. Read sample sizes and data caveats before trusting a percentage.
- **Data & Sources:** actual source usage, missing data and feature audit. Source availability is not proof a feature entered the model.

## New shadow outputs and individual-model tests

**Today** now includes expandable tables for the three development-qualified individual modifications and a separate **Spreads & totals** score distribution. Original six-model winner predictions remain first and unchanged. The Ridge score model projects coherent home/away points, home margin, favorite spread display, total,10/50/90ranges and its own implied win probability. That probability can disagree with the separate classifier ensemble. These are independent model projections, not sportsbook lines; no NBA market prices or advantage claims.

**Research & Calibration** shows all seven fixed individual modifications, the prespecified new stack and the score comparisons. The smaller MLP, simpler SVM and revised histogram booster passed the exploratory development gate versus their own original versions. The changed stack did not pass. Ridge passed both score-target development gates versus a simple rolling-score baseline. All used already-examined discovery; none has new independent confirmation or promotion. See docs/IMPROVEMENTS_PREREGISTRATION.md and docs/IMPROVEMENTS_RESULTS.md.

Launcher **option5** runs the fixed study, returning identical-input checkpoints; it never reopens the spent confirmation season. Changed inputs are refused under the frozen study rather than launching another search. Read saved results on the app page after future daily data changes. To generate only the new frozen shadow forecasts from current cached data: `python -m nba_lab.cli shadow-forecast`.

Launcher **option2** / the existing Today refresh button now also collects free supplemental data, refits the separately frozen shadow score/individual models and appends their forecasts. It does not rerun research. Earlier original and shadow forecasts are scored descriptively after tipoff+24h; earliest revision per game/candidate/configuration prevents duplicate counting. New shadow results are on the research page; none is used to retune settings automatically.

Automatic supplemental collection: SportsDataverse player boxes for ending-seasons2021onward, plus the official current NBA injury-report index/links. Raw files are hashed and archived; processed boxes carry a conservative available_at timestamp and identity/coverage audit. **These player boxes do not yet feed winner or prop projections.** Target-game DNP/active/starter flags are retrospective, not verified pregame availability. The injury PDF link is context only: statuses have not been parsed or applied. Props remain gated on a tested minutes/rotation model and verified availability. `python -m nba_lab.cli extra-data` runs this collector alone.

Launcher option2 runs the daily refresh → score earlier archived forecasts descriptively → earlier-game feature build → frozen configuration refit → today's unstarted-game archive. Option3 displays saved research. No research search or confirmation rerun occurs during daily refresh. Results include training/calibration cutoffs, config/model version and source hashes. Saved forecast history stays visible after games start. Results use the earliest saved revision per game, so multiple revisions do not inflate sample size; use `python -m nba_lab.cli score` to score saved forecasts without refitting.

## Bounded calibration run

Use launcher **option4**, or **Research & Calibration → Run / load bounded calibration check**. Command: `python -m nba_lab.cli calibrate`. It tests six fixed combined-probability calibrators on saved discovery predictions, with a20minute cap and an earlier stop when all six finish. No source downloads or base-model refits; completed candidates are checkpointed and a finished run is cached. Repeated clicks do not launch a broader search. Results are exploratory because discovery was already examined. This does not touch the spent confirmation season, change current forecasts or promote a model. See docs/CALIBRATION_PREREGISTRATION.md; results live in reports/calibration_v1/REPORT.md and on the research page.

An interrupted process may leave reports/calibration_v1/RUN_LOCK.json. Verify no calibration process is still running before removing that lock and resuming the same command. Changed inputs/code are refused under this protocol. A useful run finishes its fixed scientific checks; it does not spend extra hours generating simulated wins from an already calculated probability.

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

Winners were the first evaluated target; the separate shadow margin/total distribution is now implemented. Player props still require player minutes, rotations, trades and availability with historical timestamps. Those are not established by copying the NFL simulator. Props remain deferred, not fabricated.

## Verification and storage

Run `python -m pytest -q tests`. Tests use offline fixtures: target-week/future-outcome canaries,24h lag, duplicate/box consistency, calibration chronology, probability bounds, missing-data pages and archive safety. Raw data/models/reports/forecasts are ignored in Git. Human-reviewable protocol/frozen config/code are tracked; no secrets. A failed workflow stops clearly and leaves prior archives intact. Research folds checkpoint by source/config hash; confirmation output is read-only once completed.
