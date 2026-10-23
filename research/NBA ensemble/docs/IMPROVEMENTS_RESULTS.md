# NBA hypotheses and score projections - 2026-10-23

Completed: seven fixed individual-model tests, one prespecified stack, separate margin/total models, free player-box/injury-index collectors, new immutable shadow forecasts and descriptive result tracking. Original winner configuration/model/forecasts unchanged; nine original protected hashes verified. Nothing promoted.

## Winner changes: same 2,460 discovery games

| Candidate | Log loss old -> new | Delta [corrected95%CI] | Better seasons | Decision |
|---|---|---|---:|---|
| logistic_adjusted | 0.60829 -> 0.60828 | -0.00001 [-0.00029,+0.00028] | 1/2 | Rejected by fixed gate |
| logistic_recent | 0.60829 -> 0.60872 | +0.00042 [-0.00188,+0.00250] | 1/2 | Rejected by fixed gate |
| random_forest_simple | 0.61525 -> 0.61422 | -0.00103 [-0.00505,+0.00263] | 1/2 | Rejected by fixed gate |
| xgboost_regularized | 0.61562 -> 0.61235 | -0.00327 [-0.00609,-0.00044] | 2/2 | Rejected by fixed gate |
| hist_native_missing | 0.62293 -> 0.61637 | -0.00656 [-0.01137,-0.00148] | 2/2 | Exploratory development pass |
| svm_simple | 0.62824 -> 0.62018 | -0.00806 [-0.01433,-0.00208] | 2/2 | Exploratory development pass |
| mlp_small | 0.66078 -> 0.61294 | -0.04784 [-0.06191,-0.03318] | 2/2 | Exploratory development pass |
| new_stacked | 0.61483 -> 0.61363 | -0.00120 [-0.00386,+0.00137] | 2/2 | Rejected by fixed gate |

The smaller MLP, simpler SVM and revised histogram booster improved their own original versions. Original logistic regression still had lower discovery log loss than those modified members. XGBoost improved with a corrected interval below zero but fell short of the fixed1%effect threshold. The new stacked ensemble did not pass. Bundled changes do not identify which individual component caused an improvement.

## Separate score distributions: no market prices

| Model / target | MAE | MAE delta vs rolling [corrected95%CI] | CRPS | 10-90coverage | Decision |
|---|---:|---|---:|---:|---|
| rolling / margin | 11.334 | +0.000 [+0.000,+0.000] | 8.083 | 78.2% | Control |
| rolling / total | 14.956 | +0.000 [+0.000,+0.000] | 10.507 | 79.8% | Control |
| ridge / margin | 11.024 | -0.310 [-0.445,-0.174] | 7.892 | 78.5% | Exploratory development pass |
| ridge / total | 14.775 | -0.181 [-0.287,-0.070] | 10.407 | 79.8% | Exploratory development pass |
| hist / margin | 11.131 | -0.203 [-0.353,-0.052] | 7.966 | 77.9% | Exploratory development pass |
| hist / total | 15.028 | +0.072 [-0.089,+0.235] | 10.622 | 79.6% | Rejected by fixed gate |

Ridge passed both score targets: margin MAE improved2.74%,total MAE1.21%,both seasons improving. It is the frozen shadow score method. Home+away points equal total; home-away equals margin. Empirical paired calibration residuals supply uncertainty,without needless Monte Carlo sampling. The score model win probability is separate from the classifier ensemble. This does not establish superiority to sportsbook lines.

## Data, cutoffs and limits

Protocol165fcfc preceded every fit. Discovery ending-seasons2024/2025are reused development;2023OOF warms stacking. No2025-26confirmation re-evaluation or2026-27outcome selection. No new independent validation claimed. Fixed gates:>=1%primary-loss reduction,corrected CI below zero,both seasons improve; winner Brier/score CRPS no worse. Bonferroni8winner comparisons/4score comparisons,paired whole-game bootstrap2000draws. Corrections apply within this study,not the full history of repeated research.

Actual research:7winner configurations,21final base fits/21calibrators plus3internal neural optimization sequences;2learned score configurations/8scalar-regressor fits. Selected MLP epochs9/13/26,with stopping at29/33/46epochs,none hitting400cap. Winner research took23.8s;score research2.0s on this PC. Extra operational refits are separate from research counts.

Free supplemental data:189,445player-box rows across7,246season-games,ending-seasons2021-2027.34,574missing-minute rows are marked DNP;81marked-played rows still lack minutes.33missing/invalid player IDs excluded without guessing;zero wrong-team rows after validation. Float-formatted integer IDs normalized exactly;fractional IDs rejected. DNP/active/starter box flags are retrospective and never treated as pregame availability. Player data is a props prerequisite,not an active model input yet.

Official NBA injury index/links archived automatically with real retrieval/report times;PDF statuses are not parsed or applied. Source: https://official.nba.com/nba-injury-report-2026-27-season . Player exports: https://github.com/sportsdataverse/sportsdataverse-py . Historical data remains revised/backfilled with a conservative+24h availability proxy;2017-18team-box gaps remain unresolved.

Frozen configurations34f526f/4adeafc preceded operational shadow fitting. Twelve unstarted games received Ridge score forecasts and36per-member shadow rows. Training12,914games/calibration301,availability cutoffs recorded;neural epochs frozen26from discovery. Original winner archives preserved. New shadow results track only genuinely pregame archives after+24h,earliest revision per game/candidate/config. No current-season retuning.

QA:50offline tests passed,including chronological optimization,opponent/future canaries,source identities,CRPS,score coherence,immutable revisions,descriptive scoring and mocked daily orchestration. Actual Today/Research/Sources pages rendered with real artifacts. One test caught nullable invalid-team IDs missing from audit counts;implementation fixed,test unchanged,and failure logged. Full live daily refresh was not rerun to preserve the original winner bundle;new collector/refit/archive components ran successfully and orchestration was mocked.

## What to click / next

Open START_NBA.bat ->1 -> Today: expand individual shadows and Spreads & totals. Research & Calibration shows comparisons;Data & Sources shows coverage. Option2 refreshes data,scores earlier archives,refits frozen original/shadow models and appends forecasts. Option5 runs the frozen research only on identical inputs;option3 shows this report. CLI: python -m nba_lab.cli shadow-forecast or extra-data or score. No new BAT files added.

Props remain unimplemented. Next prerequisite is a historical minutes/rotation model with audited DNP eligibility,trade/roster handling and verified pregame availability. Current injury reports still do not change predictions. Keep new winner/score versions shadow-only while collecting genuinely prospective evidence.
