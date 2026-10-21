# Six follow-up tests — Amendment9

Previously examined 2022–24 discovery; local shadow only. No new2025/2026 evaluation, promotion or forecast replacement.

|Test / target|n / games|Control → new loss|Delta [corrected95% CI]|Decision|
|---|---|---|---|---|
|matched_quantile__rec_yds__control|6196/815|24.12161 → 23.79987|-0.32174 [-0.53709,-0.09445]|exploratory nominee; prospective confirmation needed|
|matched_quantile__rec_yds__control__provider_effect|6196/815|23.79987 → 23.65936|-0.14051 [-0.31453,+0.03814]|no gate passed|
|matched_quantile__rush_yds__control|2740/814|24.83577 → 24.49717|-0.33860 [-0.67224,+0.01662]|no gate passed|
|matched_quantile__rush_yds__control__provider_effect|2740/814|24.49717 → 24.27310|-0.22407 [-0.52767,+0.04285]|no gate passed|
|residual__win__fpds|813/813|0.22724 → 0.23217|+0.00493 [-0.00119,+0.01162]|no gate passed|
|residual__margin__fpds|815/815|9.88206 → 10.08354|+0.20147 [+0.06622,+0.33441]|no gate passed|
|residual__total__fpds|815/815|10.50728 → 10.56225|+0.05497 [-0.11799,+0.22216]|no gate passed|
|soft_coherence__pass_yds__control|1528/807|65.50901 → 65.14271|-0.36629 [-1.11323,+0.45227]|no gate passed|
|soft_coherence__pass_yds__fpds|1528/807|64.83153 → 64.68438|-0.14716 [-0.95018,+0.68488]|no gate passed|
|soft_coherence__pass_tds__control|1528/807|1.07024 → 1.07312|+0.00288 [-0.00648,+0.01309]|no gate passed|
|soft_coherence__pass_tds__fpds|1528/807|1.07264 → 1.07365|+0.00101 [-0.01020,+0.01484]|no gate passed|
|soft_coherence__rec__control|6196/815|1.49925 → 1.49240|-0.00685 [-0.01679,+0.00210]|no gate passed|
|soft_coherence__rec__fpds|6196/815|1.48770 → 1.48887|+0.00117 [-0.01047,+0.01395]|no gate passed|
|soft_coherence__rec_yds__control|6196/815|24.12161 → 23.94757|-0.17404 [-0.26371,-0.08258]|no gate passed|
|soft_coherence__rec_yds__fpds|6196/815|24.12302 → 23.99158|-0.13144 [-0.24690,-0.01162]|no gate passed|
|soft_coherence__rush_yds__control|2740/814|24.83577 → 24.62888|-0.20689 [-0.38696,-0.04979]|no gate passed|
|soft_coherence__rush_yds__fpds|2740/814|25.06160 → 24.73855|-0.32305 [-0.51316,-0.12321]|exploratory nominee; prospective confirmation needed|
|soft_coherence__anytime_td__control|8042/815|0.18984 → 0.18992|+0.00008 [-0.00056,+0.00071]|no gate passed|
|soft_coherence__anytime_td__fpds|8042/815|0.19229 → 0.19242|+0.00013 [-0.00078,+0.00104]|no gate passed|
|conformal__rec_yds__fpds|6196/815|104.28783 → 103.85296|-0.43488 [-0.64123,-0.22558]|no gate passed|
|conformal__rush_yds__fpds|2740/814|109.44554 → 108.71795|-0.72759 [-1.23306,-0.21546]|no gate passed|
|probability__win__control|813/813|0.23450 → 0.23457|+0.00007 [-0.00003,+0.00017]|no gate passed|
|probability__win__fpds|813/813|0.23483 → 0.23490|+0.00007 [-0.00005,+0.00018]|no gate passed|
|probability__anytime_td__control|8042/815|0.18984 → 0.19502|+0.00519 [+0.00359,+0.00687]|no gate passed|
|probability__anytime_td__fpds|8042/815|0.19229 → 0.19661|+0.00432 [+0.00311,+0.00565]|no gate passed|

Losses: MAE for yards/margin/total; Poisson deviance for counts; Brier for probabilities; interval score for conformal. Negative delta improves.

Interval calibration preserves medians; width changes do not improve MAE. Shrunk probabilities are new probabilities, not vote agreement.

blocked: stored calibration/config choices selected on later examined seasons; strict earlier-OOF A8 control tested as labelled surrogate

Target audit: {"created_at": "2026-10-21T22:12:25.714789+00:00", "seasons": [{"season": 2021, "reg_rows": 26102, "full_rows": 26102, "overtime_games": 23, "changed_targets": {"pass_yds": 36, "pass_tds": 7, "rec": 84, "rec_yds": 84, "rush_yds": 51, "anytime_td": 4}}, {"season": 2022, "reg_rows": 26016, "full_rows": 26016, "overtime_games": 20, "changed_targets": {"pass_yds": 30, "pass_tds": 1, "rec": 72, "rec_yds": 71, "rush_yds": 52, "anytime_td": 1}}, {"season": 2023, "reg_rows": 26112, "full_rows": 26112, "overtime_games": 14, "changed_targets": {"pass_yds": 19, "pass_tds": 3, "rec": 36, "rec_yds": 35, "rush_yds": 30, "anytime_td": 2}}, {"season": 2024, "reg_rows": 26121, "full_rows": 26121, "overtime_games": 16, "changed_targets": {"pass_yds": 21, "pass_tds": 5, "rec": 43, "rec_yds": 43, "rush_yds": 39, "anytime_td": 4}}], "candidate_rows": 13219, "candidate_exact_observation_missing": 845, "missing_but_same_player_game_on_other_team": 10, "unresolved_missing": 835, "definition": "regular-time v overtime-inclusive; still excludes kneels/spikes/two-point plays; not official settlement validation", "decision": "target mismatch verified if changes>0; no targets, IDs or old forecasts changed; official box-score/kneel settlement audit remains necessary"}

Trials: {"outputs": ["conformal__rec_yds__fpds", "conformal__rush_yds__fpds", "matched_quantile__rec_yds__control", "matched_quantile__rush_yds__control", "probability__anytime_td__control", "probability__anytime_td__fpds", "probability__win__control", "probability__win__fpds", "residual__margin__fpds", "residual__total__fpds", "residual__win__fpds", "soft_coherence__anytime_td__control", "soft_coherence__anytime_td__fpds", "soft_coherence__pass_tds__control", "soft_coherence__pass_tds__fpds", "soft_coherence__pass_yds__control", "soft_coherence__pass_yds__fpds", "soft_coherence__rec__control", "soft_coherence__rec__fpds", "soft_coherence__rec_yds__control", "soft_coherence__rec_yds__fpds", "soft_coherence__rush_yds__control", "soft_coherence__rush_yds__fpds"], "fit_calls": 129, "heads": ["matched_quantile__rec_yds__control/quantile_0.1", "matched_quantile__rec_yds__control/quantile_0.5", "matched_quantile__rec_yds__control/quantile_0.9", "matched_quantile__rush_yds__control/quantile_0.1", "matched_quantile__rush_yds__control/quantile_0.5", "matched_quantile__rush_yds__control/quantile_0.9", "residual__margin__fpds/ridge_residual", "residual__total__fpds/ridge_residual", "residual__win__fpds/ridge_residual"]}

Failed blocks: 0; summary failures: 0; inputs unchanged: True.

Previously examined 2022-24 discovery only. No 2025 or2026 evaluation, no new holdout use, no eval command, no new forecasts, no prices as features. Revised historical FPDS remains a limitation. Any nomination requires future prospective confirmation. No historical prop price-edge claims. Failed blocks logged/skipped, never retried or dropped silently; incomplete family cannot qualify.
