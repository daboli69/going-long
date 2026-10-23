# NBA individual models and score distributions — 2026-10-23

Freeze before fitting. This is a separate shadow experiment; never change original frozen configuration, base-model code, operational winner bundle, confirmation reports or forecast archives. $0 spend, local low-priority CPU (cores minus2), no paid services/keys/odds/deployment/NFL changes. Owner: Codex. User authorized testing individual-model hypotheses, then supported score/prop work and free automated data collection. End after fixed work; no open-ended search.

## Data, chronology and limitations

Use existing lagged game feature store and schedules/team boxes. Model inputs are pregame only, using completed games strictly after tipoff+24h. Game IDs and target rows must match saved initial OOF outputs. Ending-season2023 is stacking warmup; discovery2024/2025 are the same already-examined2460games. Each target trains2016through target-2 and calibrates on target-1. No re-scoring2026confirmation, no2026–27outcomes for selection. There is no remaining independent historical validation claimed. Any apparent improvement is exploratory until genuinely new prospective evidence. Historical sources are revised backfills; initial2017–18box gaps remain a limitation.

New optional features: last20completed-game opponent-adjusted margin (own margin plus opponent's pregame last20margin), attack residual (own ORtg minus opponent's pregame last20DRtg), defense residual (own DRtg minus opponent's pregame last20ORtg), home-away differences. Opponent context is taken from that historical game's pregame row; own box stats/results are released only at+24h. No current-game outcome, season-final rating or retrospective injury joins. Unknown history remains NaN, never zero. Fixed feature-group definitions; no per-column selection on discovery.

## Winner hypotheses and exact trial budget

Seven fixed challengers,3chronological folds each:21final base fits/21sigmoid calibrators, plus3internal neural-network optimization sequences. Reuse saved original6member and stacked OOF outputs as identical-row controls, never refit those controls. One prespecified new stacked combination, without searching ensemble methods. No additional settings after results.

| ID | Hypothesis | Fixed change |
|---|---|---|
| logistic_adjusted | Earlier opponent strength adds information | Original logistic C1 plus three opponent-adjusted difference features |
| logistic_recent | Recent seasons transfer better | Original logistic C1; exponential sample weights,2ending-season half-life, training only |
| random_forest_simple | Simpler trees reduce noise |150trees,depth6,min_leaf40,sqrt features; retain20game rolling differences and schedule/Elo,drop5/10windows |
| xgboost_regularized | Shallower regularized boosting generalizes |300trees,depth2,lr.03,min_child_weight10,lambda10,subsample.9,colsample.9;original inputs |
| hist_native_missing | Preserve unknown inputs and simplify leaves | StandardScaler preserving NaN,no imputer;150iterations,7leaves,min_leaf40,l2=10;original inputs |
| svm_simple | Less redundancy and smoother boundary help | Same reduced20game feature group as forest;C.5,gamma.02,RBF |
| mlp_small | Resolve non-convergence without extra complexity | One32unit hidden layer,alpha.1,Adam; internal validation is the last training season,earlier seasons fit preprocessing/network; max400epochs,patience20,min_delta1e-4. Freeze best epoch,then refit preprocessing/network on all allowed training seasons for exactly that many epochs; external following-season sigmoid calibration remains disjoint. |

The new stacked combination always uses logistic_adjusted,random_forest_simple,xgboost_regularized,hist_native_missing,svm_simple,mlp_small. Warmup2023falls back to equal mean; target2024stacking uses only2023OOF, target2025uses2023/2024OOF. It is not assembled after looking at which modifications win. logistic_recent stays a separate ablation.

Primary winner metric log loss; Brier,accuracy,reliability and warnings secondary. Paired whole-game bootstrap2000draws,seed20261023; Bonferroni across8comparisons(7individual+1stacked),familywise95%. Individual controls are their own original family; composite control is original stacked. Exploratory gate:>=1%relative log-loss reduction,corrected CI<0,both discovery seasons improving,Brier no worse. No automatic adoption even on a pass. Record per-model failures,optimizer epochs,fit counts,all trials and uncertainty.

## Spreads/totals: fixed new targets, not copied winner probabilities

Full-game home margin=home score-away score; total=home+away, including overtime. No market prices used; no market-superiority claim. Use the same eligible target games, train/calibrate/test chronology, source cutoffs and revised-data caveats. Inputs include both teams' pregame20game scoring,allowed,pace,efficiency/Four Factors,rest and Elo,plus the three opponent-adjusted differences. No odds or realized target box data.

Controls: earlier-training league mean; structural rolling score estimate home=(home prior20points+away prior20allowed)/2 and away analog. Bias correction and empirical uncertainty use the disjoint calibration season for every method. Two learned joint candidates: standardized median-imputed Ridge(alpha10), and two HistGradientBoostingRegressors(max_iter150,max_leaf_nodes7,min_samples_leaf40,l2=10,early_stopping=False). Each predicts margin and total; derived home/away scores are coherent within that score model. No assumption they must agree with the separate classifier ensemble.

Two discovery folds2024/2025,2learned configurations,8scalar-regressor fits. Evaluate MAE,RMSE,empirical-distribution CRPS,bias,10/50/90interval coverage and descriptive margin-based win Brier. Empirical paired margin/total residuals from calibration preserve their observed covariance; integrate the full empirical distribution rather than repeat Monte Carlo draws. At least300calibration games. Paired-game bootstrap2000draws; Bonferroni across4learned-model/target comparisons. Exploratory gate per target:>=1%MAE reduction versus structural rolling control,corrected CI<0,both seasons improve,CRPS no worse. A joint candidate qualifies only if both targets pass. Freeze one joint method by lowest average normalized margin/total MAE among qualified candidates; if none qualify, retain the structural method as the default and show learned variants only as rejected exploratory comparisons.

## Prospective operation and free data

Freeze score configuration before operational refit. Separate shadow-only score bundle uses available completed games with the last300calibration games (entire boundary block),and a strict24h embargo before calibration; no selection on current-season results. Archive only unstarted games in new immutable score forecast folders,including creation time,training/calibration availability cutoffs,config/model/data hashes,intervals and method. Never replace winner forecasts or invent market lines. Daily/manual refresh may refit this frozen shadow score configuration and append a new revision,not rerun research.

Automatically collect available public SportsDataverse player-game box exports,with hashed archives,coverage/schema/key/duplicate reports. Do not fit or advertise player props yet: projected minutes,rosters and timestamped availability need an audited prerequisite. Archive official NBA injury-report index metadata/links with retrieval/report timestamps,context only; do not backfill current availability into historical models or claim unparsed reports adjust forecasts. No paid PBP Stats tracking pages or blocked NBA Stats bypass. New data schema/coverage audits may precede fits; no outcomes are screened to expand this budget.

## Checkpoints and deliverables

Checkpoint complete per-candidate folds; identical-input completed work returns cached outputs. Fingerprint code/config/data,refuse altered completed runs. Log failures and skip; never weaken tests. Record an unchanged-operational-model/archive hash audit. Add local UI results and score projections within existing navigation and reuse START_NBA.bat. Tests: future-outcome/opponent-context canaries,chronological optimization/calibration,missing data,identical samples,empirical CRPS/coverage,score coherence,immutable revisions and no confirmation reads. Root MODEL_RESEARCH.md/PROGRESS.md get concise metadata only. No promotion.

Primary references: https://scikit-learn.org/stable/modules/neural_networks_supervised.html ; https://xgboost.readthedocs.io/en/stable/parameter.html ; https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html ; https://github.com/sportsdataverse/sportsdataverse-py ; https://official.nba.com/nba-injury-report-2026-27-season .
