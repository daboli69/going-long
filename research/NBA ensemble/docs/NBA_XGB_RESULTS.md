# NBA home-win XGBoost study: results

Protocol: `docs/NBA_XGB_PREREGISTRATION.md` (committed before any fitting). Frozen configuration: `docs/NBA_XGB_FROZEN.json`
(committed before any 2025 or 2026 outcome was scored). Code: `nba_xgb/`. Artifacts: `research_nba_xgb/`.

## Bottom line

XGBoost did not beat the simpler models. On the 2,459 final-test games (2025 and 2026 seasons):

| Model | Log loss | Brier | Accuracy | AUC | Calib. slope |
|---|---|---|---|---|---|
| Elo, uncalibrated formula | 0.6042 | 0.2085 | 0.675 | 0.730 | 1.07 |
| Calibrated Elo (baseline 1) | 0.6032 | 0.2081 | 0.678 | 0.730 | 1.12 |
| Regularized logistic (baseline 2) | **0.5996** | **0.2066** | 0.681 | 0.734 | 1.04 |
| XGBoost | 0.6038 | 0.2079 | 0.679 | 0.733 | 1.13 |

Paired log-loss difference (negative favours the first model), date-clustered bootstrap, 4000 draws:

| Comparison | Pooled | 95% interval | 97.5% interval | 2025 | 2026 |
|---|---|---|---|---|---|
| XGBoost minus Elo | +0.0006 | -0.0027, +0.0038 | -0.0032, +0.0042 | -0.0001 | +0.0012 |
| XGBoost minus logistic | +0.0042 | +0.0011, +0.0073 | +0.0007, +0.0078 | +0.0064 | +0.0021 |
| Logistic minus Elo | -0.0037 | -0.0068, -0.0006 | -0.0072, -0.0001 | -0.0065 | -0.0009 |

The 7-day moving-block bootstrap gives the same conclusions. Regularized logistic is the best model and its edge over
XGBoost is credible in the pooled data, though not in 2026 alone. Its edge over Elo is credible pooled but not in 2026
alone. XGBoost versus Elo is a statistical tie.

## Answers to the seven questions

1. **Does XGBoost outperform Elo?** No. The pooled difference is +0.0006 log loss (worse), with an interval that includes zero.
2. **Does XGBoost outperform logistic regression?** No. It is worse by 0.0042, and the interval excludes zero.
3. **Is any improvement statistically credible?** There is no XGBoost improvement. The only credible gap is logistic over XGBoost and over Elo, and neither holds in both seasons separately.
4. **Which signals add information?** Elo strength and recency-weighted net rating both do (dropping recent net rating costs +0.0023 XGBoost / +0.0034 logistic log loss, interval above zero). Rest and back-to-back flags are small but consistently help logistic by about 0.0017 (interval includes zero). Opponent-adjusted ridge ratings added nothing beyond Elo plus recency: the preregistered development rule dropped them, and adding them back on test changes nothing credible. Splitting offence and defence, four-factor nets, and games-played gave no credible gain.
5. **Are probabilities calibrated?** Mostly, with caveats. Logistic and Elo are close (intercepts +0.04 and +0.03, slopes 1.04 and 1.12 mean slightly under-confident). XGBoost has intercept -0.06 and slope 1.13, and over-states low-probability games: in the 0 to 0.3 bin it predicts 0.26 while 18.7% of home teams won (289 games). Bins near 0.6, 0.7 and 0.8 are within roughly two standard errors for all models, but each bin holds only 250 to 450 games.
6. **Is performance stable across seasons?** Differences are small relative to season-to-season swings. Season log loss ranges 0.597 to 0.647 for every model (2021 to 2026), driven by the season, not the model. XGBoost beat logistic only in 2022 and was worse in 2021, 2023, 2024, 2025 and 2026 (2022 was a development fold).
7. **Largest unresolved uncertainties:** see the limits section below.

## Why XGBoost cannot win here

- Development search (30 configurations, folds 2020 to 2023) picked a **depth-1 model** (stumps; an additive model). Deeper trees were worse on development folds, so the shallow rule applied.
- SHAP on the test models: each feature's contribution is almost a straight line in the feature (R squared 0.91 to 0.97 for Elo and recency, 1.0 for back-to-back flags). Stumps have no interactions. A depth-3 variant put only about 12% of its attribution on interactions and still lost to logistic by 0.0037 (interval +0.0015 to +0.0057).
- At test time, depth 2, 3, 4 and 6 variants were all worse than logistic (+0.0024 to +0.0061) and none beat stumps by a credible margin. Nonlinear interactions in these features carry no detectable signal at about 12,000 training games.
- Ratings are summaries already built to be near-linear in win probability, so the information left for trees to find is small.

## Ablations (test seasons, frozen hyperparameters, uncalibrated models so features are isolated)

Frozen features: Elo difference, recent net difference, rest difference, two back-to-back flags, home court. Baseline XGBoost 0.6038, logistic 0.6008.

| Change | XGBoost change in loss (95% interval) | Logistic change |
|---|---|---|
| Drop Elo | -0.0003 (-0.0023, +0.0017) | +0.0016 (-0.0001, +0.0033) |
| Drop recency | +0.0023 (+0.0003, +0.0044) | +0.0034 (+0.0012, +0.0057) |
| Drop schedule/rest | +0.0004 (-0.0014, +0.0020) | +0.0017 (-0.0006, +0.0039) |
| Add opponent-adjusted off/def | +0.0000 | +0.0009 |
| Replace with adjusted net only | +0.0009 | +0.0007 |
| Add offence/defence recency split | -0.0005 (-0.0011, +0.0001) | -0.0005 |
| Add four factors | +0.0007 | -0.0002 |
| Add games played | +0.0004 | 0.0000 |
| Elo only | +0.0071 | +0.0051 |
| Adjusted only | +0.0083 | +0.0088 |
| Recency only | +0.0049 | +0.0033 |

Elo and recency overlap heavily: removing Elo alone changes nothing credible for XGBoost, and Elo plus recency equals the full set. Two
information sources in total (long memory plus recent form) carry nearly all the signal.

## Sensitivity (test seasons; XGBoost minus logistic, uncalibrated; positive means XGBoost worse)

All settings give XGBoost worse than logistic by +0.001 to +0.004; the interval excludes zero in most (all but 3- and 5-season training windows, elo_plain, elo_k30). **No setting makes XGBoost better than logistic.** XGBoost versus calibrated Elo ranges from -0.0053 to +0.0020 depending on the Elo variant, and that swing comes mostly from how weak the Elo variant is, so it is not an XGBoost effect.

- Recency half-life 10, 20, 40, 80, 160 games: logistic loss 0.6016, 0.6010, 0.6008, 0.6009, 0.6010. Flat above about 20 games, so the "best" decay is poorly identified.
- Season-start prior: n0 = 5 gives logistic 0.5994, n0 = 20 gives 0.6008, n0 = 40 gives 0.6024; no carry-over (rho = 0) gives 0.5997. Less prior carry-over helped on test, while the fit period preferred rho = 0.5. This is a small shift that the preregistered fit did not predict; it is not adopted.
- Elo variants: plain (no margin) 0.6100, K = 10 0.6080, K = 30 0.6032, carry 0.5 0.6017, carry 0.9 0.6065 (calibrated Elo; frozen is 0.6034). Margin-of-victory updating helps clearly.
- Training window: 3 seasons 0.6045, 5 seasons 0.6044, all seasons 0.6038 (XGBoost). Excluding 2020 and 2021: 0.6039. Longer windows help slightly.
- Lag of 2 days instead of 1: losses move by 0.0004 or less. The one-day availability assumption does not drive the results.
- Early season (games played by the lesser team < 10, n = 311): all models 0.608 to 0.609. 10 to 29 games (n = 606): Elo 0.631, logistic 0.622, XGBoost 0.628. 30 or more games (n = 1542): 0.592, 0.591, 0.593. The gap between models sits in the middle of the season.

## Calibration choices (selected on fold 2024 only)

Platt scaling chosen for calibrated Elo and logistic; none for XGBoost. Isotonic regression was worst for all three. Calibration of XGBoost
did not help at 2024, so its test calibration is the raw one.

## Historical coverage audit

- Sources: ESPN schedule and team box-score parquet files (SportsDataverse), seasons 2015 to 2027, all retrieved 2026-10-23 except three snapshots of 2027 (10-23, 10-24, 10-26). No play-by-play, no substitution data and no historical roster data exist in the archive, so those were not used. The brief's "start from play-by-play" could not be met; team box scores are the most granular records available.
- 14,480 scheduled regular-season games including the unplayed 2027 schedule (13,206 verified labelled games in 2016 to 2026), 30 teams every season, 82 games per team in full seasons (2020: 64 to 75; 2021: 72). Shortened seasons 2020 (1,059) and 2021 (1,080) are present.
- Four games are quarantined (box components or scores disagree): 400578620 (2015), 400900132 (2017), 400975285 (2018), 401704652 (2025, POR vs NO). They stay in the schedule for rest days but out of ratings and labels.
- ESPN team-turnover figures are missing for all of 2018, so turnovers use the player-turnover field in every season. This lowers possession counts by about 0.7 per team-game compared with official box totals.
- 2020 games on or after 2020-07-30 (91 games) are treated as neutral. 2021 attendance limits and 2020 hiatus effects on home advantage are not modelled.
- Verification done: schedule score equals box points for every labelled game; points equal 2 x FGM + 3PM + FTM for both teams; the two teams' possession estimates differ by 2.3 on average. **Not done:** comparison with independently published totals from NBA.com or Basketball-Reference, because they were not fetched. League pace in this construction runs 96.4 (2015) to 102.8 (2020); readers can compare it with published values.
- Timestamps: event time is the game's Eastern date. Publication time is unknown for every historical row. Our retrieval time is 2026-10-23, years after the events. The modelled prediction cutoff is 06:00 ET on game day with results from earlier dates only. Whether ESPN had published each box by then is unproven, so the backtest shows what was computable under that rule, not what was live.
- Player availability, final lineups and injuries were not used. No historical injury timestamps pass the project's availability standard.

## Strict replay and leakage evidence

- `nba_xgb.cli replay` rebuilds features for every test date from a copy of the data in which all results dated on or after that day are removed, then applies the frozen season bundle. All 4,916 and 4,920 prediction rows matched the batch run (max difference 3e-16; max feature difference 6e-14). Replay files were written (read-only, hashed) before any outcome joined them.
- 14 automated tests (`tests/test_nba_xgb_leakage.py`) cover: corrupting every later result does not change earlier features; deleting the future schedule changes nothing; lag boundaries; cutoff before tipoff; postponed games; overtime; season-transition Elo regression; duplicate boxes; walk-forward training windows; immutability of forecast files. A mutation test confirms the checks have power: with a deliberate same-day leak (lag 0) the perturbation is detected. An earlier draft of two tests used cut dates outside the synthetic season and was vacuous; this was found by the mutation check and fixed.
- Independent evaluation: `nba_xgb/independent_eval.py` imports nothing from the package. It rebuilt outcomes from the raw archive files, matched all 2,459 games across all four models with zero duplicates, zero probabilities outside (0,1), zero cutoffs at or after tipoff. The only source games without predictions are four All-Star exhibition games per season (non-NBA teams) plus the quarantined game. Its metrics match the model-side numbers.

## Evidence requirements

| Requirement | Status |
|---|---|
| No detected future-information leakage | Met for the tests run (perturbation, replay equality). Cannot rule out historical revision of ESPN files. |
| Exact reproducibility | Replay equals batch to 1e-16. Training uses a fixed seed. A full second-machine rerun was not done. |
| Stronger out-of-sample scores than declared baselines | **Not met** for XGBoost. Met only by logistic regression over Elo. |
| Credible improvement over more than one period | **Not met** for XGBoost. |
| No major unexplained miscalibration | Partly met: XGBoost is overconfident toward low-probability games (0.26 predicted, 0.19 observed). |
| No reliance on final-test data for selection | Met: freeze commit precedes test scoring; calibrators for 2026 use 2025 outcomes only after that season is complete. The sensitivity and ablation tables are reports, not selections. |

## Largest unresolved uncertainties and limits

1. Historical publication times are unverified; every claim is conditional on the stated cutoff rule.
2. About 2,459 test games detect differences of about 0.003 to 0.004 log loss at best. A smaller true XGBoost advantage cannot be excluded.
3. 2025 and 2026 are not virgin seasons for the wider project (disclosed in the preregistration). Another project's earlier work used them with different models.
4. Engine parameters were fitted on 2016 to 2021, so training-row features before 2022 are mildly optimistic. Test seasons are unaffected.
5. Player availability is the largest missing basketball signal and the most likely route to a real nonlinear gain (star absence interacts with team strength). It needs timestamped pregame injury data, which the project has only for 2026-27.
6. Single frozen configuration per model family; the logistic baseline got C = 0.003 (heavy shrinkage), which is a tuned baseline.

## Reproduce

```
.venv\Scripts\python.exe -m nba_xgb.data                  # canonical tables (hash-locked)
.venv\Scripts\python.exe -m nba_xgb.fit_engine            # engine parameters, 2016-2021 only
.venv\Scripts\python.exe -m nba_xgb.develop               # development folds, freezes docs/NBA_XGB_FROZEN.json
.venv\Scripts\python.exe -m nba_xgb.cli final             # one-pass test predictions (refuses to overwrite)
.venv\Scripts\python.exe -m nba_xgb.cli replay --season 2025   # and 2026
.venv\Scripts\python.exe -m nba_xgb.cli compare
.venv\Scripts\python.exe nba_xgb\independent_eval.py research_nba_xgb\replay_predictions_2025.csv research_nba_xgb\replay_predictions_2026.csv
.venv\Scripts\python.exe -m nba_xgb.analysis              # ablations, sensitivity, SHAP
.venv\Scripts\python.exe -m nba_xgb.cli daily --date YYYY-MM-DD   # daily forecasts (refresh the archive first)
.venv\Scripts\python.exe -m pytest tests/test_nba_xgb_leakage.py
```

The sample daily forecast for 2026-10-29 (`research_nba_xgb/daily/`) used an archive whose last results are from 2026-10-26, so it is missing
2026-10-27 and 2026-10-28 results. It is a pipeline demonstration, not a usable forecast. No 2027 game outcomes are scored here.
