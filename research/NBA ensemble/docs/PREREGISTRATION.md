# NBA winners v1 — frozen 2026-10-23 before model fitting

Travis explicitly authorizes this separate local NBA project. No NFL imports, data, model changes or promotion; $0 new spend, no accounts/keys/odds APIs, deployment, messages or database writes. Owner: Codex (data/model/UI/QA). Deliver a usable six-member winner ensemble, evidence-based comparison, chronological evaluation, immutable prospective archives, one launcher and source health reporting. Spreads/totals/props are deferred until their separate targets and validations exist.

## Data and target

SportsDataverse ESPN season-ending years 2015–2027, schedules + team box scores. hoopR and sportsdataverse-py expose this same data, not two independent sources. Regular season only (season_type=2), full-game winner including overtime; no ties. 2015 warmup, model training begins2016. Quarantine duplicate/wrong-team/score-inconsistent box scores. Log missing seasons/tables, never invent replacements. First inspect schema/coverage, not model outcomes.

Pre-fit source-audit clarification: ESPN's season_type2 also includes special events/postponed placeholders. Require both IDs in its verified NBA team directory; exclude cancelled/postponed events and explicitly labelled NBA Cup/In-Season Tournament championship games (not regular-season standings games). Other Cup rounds remain regular-season games. This is target/schema correction before any fit, not outcome-based model selection.

Historical sources are today's revised/backfilled files, not retained historical pregame snapshots. Reconstruct all features from strictly earlier games, conservatively usable24h after scheduled tipoff; this is an availability proxy, not a verified publication timestamp. Prospective archives retain real retrieval/creation/cutoff metadata. No target-game scores, target-game boxes, current-season aggregates computed with later games, odds, final lineups or injury backfills as features. Future games use information available at run time, never their future results. Insufficient history(<10 eligible prior games per team) is flagged/excluded from validation. Known scheduled rest/back-to-backs are calendar context. Live injury data is context-only unless timestamped historical features receive a separate gate.

Inputs: home/neutral status, rest and back-to-back, games in prior4days, season-start regression in Elo, earlier win rate/margin, rolling5/10/20-game scoring/pace/efficiency and Four Factors (eFG, turnovers, offensive rebounds, free-throw rate), home-away differences. Fixed Elo K20/home advantage65/season retention0.75; it is a simple benchmark, not tuned. Four-Factor box scores must belong to that earlier completed game; missing boxes are reported, not treated as zero. Team IDs use verified ESPN IDs; NBA Stats IDs are a separate namespace requiring an explicit crosswalk. PBP Stats season totals are context-only, never joined retroactively into earlier game features.

## Six fixed candidates; no hyperparameter search

1. LogisticRegression C1, max_iter1000.
2. RandomForest150trees, max_depth8, min_samples_leaf20, max_features=sqrt.
3. XGBoost200trees, depth3, learning_rate0.05, subsample0.9, colsample0.9, reg_lambda5.
4. HistGradientBoosting150iterations, max_leaf_nodes15, l2_regularization5, early_stopping=False.
5. RBF SVC C1/gamma=scale, probability=False; separate chronological sigmoid calibration.
6. MLP(64,32), alpha0.01, max_iter200, early_stopping=False.

CPU only; seed20261023. Median imputation and standardization fit on training only. Every member gets a sigmoid calibrator fitted on the following, disjoint season. No random cross-validation or random validation split. Warnings/failures logged; an incomplete six-member fit is not shown as a complete ensemble.

## Splits and budget

Warmup OOF target2023: train2016–2021, calibrate2022. Discovery targets2024/2025: train through target-2, calibrate target-1, score target only. Base algorithms, equal mean, earlier-OOF log-loss-skill weighted mean, earlier-OOF logistic stacking. For each target, weights/stacking see OOF outcomes only from strictly earlier target seasons; no stacking on same-fold fitted predictions. First OOF fold falls back to equal mean; report fallback. At most6fixed model configurations,24base fits across four target seasons,24calibrators, and3ensemble types; track actual fit attempts/checkpoints. No algorithm is called best before results.

Select the final ensemble type on pooled discovery2024–25 log loss only, tie-break alphabetical. Freeze docs/FROZEN_CONFIG.json with the selection/data/config hashes and commit BEFORE confirmation. Confirmation2026(2025–26 NBA season), one pass only, unchanged selected method; do not select/tune on it. Cache completed outputs and refuse a changed-data confirmation under this protocol. Score all members descriptively on that same pass, never switch the selected method based on it. Season2027(2026–27) is prospective/descriptive only.

## Metrics and gate

Same eligible games for all candidates and simple benchmarks (Elo, earlier-training home-win frequency). Primary log loss; Brier, accuracy, reliability bins and sample size secondary. Paired whole-game bootstrap2000draws, seed20261023; no betting returns. Discovery candidate-vs-Elo intervals Bonferroni-correct for9candidate outputs (six members + three ensembles), familywise95%. Qualification requires >=1%log-loss improvement, corrected interval strictly below0, improvement in both discovery seasons, and same direction plus95%CI below0 on confirmation. Otherwise exploratory/rejected, no promotion. No market superiority claim without genuine timestamp-matched prices; none are requested/ingested in v1.

After freezing and the single confirmation, an explicitly labelled production-style SHADOW refit may use all then-completed eligible games: last300games for calibration, all earlier games for base fitting, frozen OOF weights/stacker and selected ensemble. Record training/calibration game/date cutoffs and source/config hashes. Forecast only unstarted games; refuse saving after kickoff. Current historical reports retain original splits even after refit. Do not rerun research on every daily refresh.

## Primary references

- https://github.com/sportsdataverse/hoopR/blob/main/R/load_nba.R
- https://github.com/sportsdataverse/sportsdataverse-py/blob/main/sportsdataverse/nba/nba_loaders.py
- https://github.com/swar/nba_api (NBA Stats endpoint schemas; public API access can fail)
- https://pbpstats.readthedocs.io/en/latest/ (possession/lineup derivation)
- https://api.pbpstats.com/docs (site API, not an independent provider from pbpstats)
- https://scikit-learn.org/stable/modules/calibration.html (disjoint calibration data)

Optional NBA Stats and PBP Stats connectors archive free public responses for audits/future feature work. They are not silently counted as active winner features in this fixed v1 experiment. Future lineup/PBP integrations require their own pregame provenance and incremental-value test.
