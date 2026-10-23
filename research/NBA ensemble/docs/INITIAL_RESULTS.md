# NBA winners v1 — 2026-10-23

Built a separate local NBA project with six calibrated algorithms, model comparison/debate, frozen ensemble selection, daily refresh/refit, immutable pregame forecasts and descriptive results tracking. Nothing promoted. NFL code, data and models unchanged.

## Evidence

Ending-year seasons: discovery2024–25 (2,460 games); untouched confirmation2026 (1,230 games,2025–26 NBA season). Train earlier seasons; calibrate on the following disjoint season; test only the next season. Ensemble stacking/weights use strictly earlier out-of-fold predictions. No hyperparameter search:6fixed configurations,24research base fits +24calibrators;6additional base fits for the operational shadow bundle. Synthetic QA fits are not research trials.

| Confirmation method | Log loss | Brier | Winner accuracy |
|---|---:|---:|---:|
| Frozen stacked ensemble |0.59908|0.20589|68.46%|
| Elo benchmark |0.60856|0.20989|67.89%|
| Logistic regression, descriptive |0.59961|0.20617|68.62%|
| Random forest, descriptive |0.60465|0.20834|68.21%|
| XGBoost, descriptive |0.60764|0.20973|67.56%|
| Histogram gradient boosting, descriptive |0.61530|0.21316|65.61%|
| RBF SVM, descriptive |0.61883|0.21404|67.56%|
| MLP, descriptive |0.66125|0.23371|60.73%|

Lower log loss/Brier is better; higher accuracy is better. Frozen ensemble confirmation log-loss delta versus Elo:-0.00948, paired-game bootstrap95%CI[-0.01825,-0.00108],2,000draws. This is a probability-loss comparison, not evidence of an advantage over market prices.

**Decision: exploratory.** The selected ensemble's discovery improvement was only0.25%, its multiplicity-corrected interval crossed zero[-0.00950,+0.00681], and it improved in only one of the two discovery seasons. It therefore failed the preregistered gate even though confirmation improved. Logistic regression was the strongest individual candidate on discovery; the MLP was weak and hit its fixed200iteration limit in every fold. No iterations or selection changes followed confirmation.

## Data and forecast status

15,639 schedule rows,28,906 team boxes; historical regular-season counts reconcile, including the shortened2020/2021 seasons.30verified NBA teams; All-Star/special teams, postponed placeholders and Cup championship finals excluded. No score-mismatch quarantines.2017–18 box detail is substantially incomplete: average prior-box count about2.6/20 versus20/20 in most later seasons. Unknown rates receive train-only median imputation; this is a limitation, not complete historical coverage.

Active model inputs: SportsDataverse ESPN schedules/team boxes, exposed by both hoopR and sportsdataverse-py. They are one shared origin. Earlier-game Elo, form, efficiency, Four Factors, rest and back-to-backs enter the model. Historical files are revised/backfilled, with a conservative tipoff+24h availability proxy; they are not authentic archived pregame snapshots. Historical playoffs and Cup finals are outside this model's target.

PBP Stats2025–26 team context was successfully archived; it is not a historical model feature. The public NBA Stats endpoint used by nba_api timed out after35seconds; no retry/bypass or fabricated fallback. The nba_api/sportsdataverse/pbpstats SDKs were not installed; dataset/direct-endpoint adapters are labelled honestly. PBP/lineup enrichment needs a separate as-of audit and incremental-value test.

The operational shadow bundle uses12,914base-training games through2026-03-06UTC and301later calibration games through2026-10-22UTC, with a24h gap before calibration. It retains the frozen discovery stacking fit.12unstarted games were archived on2026-10-23 before tipoff, with config/model hashes, source-manifest hash, creation time and both outcome-availability cutoffs. No completed2026–27 outcomes were used for selection. Today's14available outcomes enter only the permitted shadow operational refit/calibration.

## Verification and use

21offline tests passed, including actual synthetic six-member fit/calibration, leakage canaries, source schema exclusions, duplicate protection, missing-data pages and immutable prospective scoring. All four pages also rendered against the real trained bundle; feature sensitivities ran successfully. Confirmation repeat returned the saved result without fitting. No new spend, deployment, messages or NFL changes.

Double-click `START_NBA.bat`, press Enter, then open `http://localhost:8502`. Four pages: Today, Model Debate, Research & Calibration, Data & Sources. Launcher option2 updates data, scores earlier archives, refits the frozen model and saves today's forecasts. Multiple revisions never inflate the default results sample: earliest saved pregame revision per game is scored. Keep this computer awake while a manual refresh runs.

Current injury/lineup effects are **not modeled**. No betting prices were loaded. Next priorities: timestamped availability/rotation data and prospective calibration; then separately preregister spread/total distributions and player-minute/stat models. Winners first is implemented; spread/total/prop numbers have not been invented.
