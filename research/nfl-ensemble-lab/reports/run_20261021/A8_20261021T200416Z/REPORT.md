# FPDS improvement study — Amendment 8

Run `20261021T200416Z`. 2022-24 previously examined discovery only; no holdout pass or2026 selection. All outputs shadow only; nothing promoted.

Completed 67 primary comparisons; 178 failed blocks. Recorded 147 member/head outputs, 167 internal fit configurations and 2591 fit dispatches. The fixed ceiling is147 outputs /300 internal configurations /4500 dispatches. No grid search.

Lower loss is better. Negative delta means improvement against the named reference. Intervals are registered family-corrected paired whole-game95% intervals. A discovery nominee requires >=1% reduction, corrected interval below zero, >=200 games, two improving seasons, identical complete samples, no failed blocks and Holm p<.05. It still requires future confirmation.

Primary loss is MAE for yards/margin/total, Poisson deviance for receptions/passing TDs, and Brier for winners/anytime TD. Median quantile heads are point forecasts; they are not means.

## Best observed change per family

These are exploratory rankings within the fixed study; the complete table below includes regressions. Different rows have different references and are not automatically comparable.

|Family|Target / variant / inputs|n / games|Reference → new loss|Change|Corrected95% CI|Nominee|
|---|---|---:|---:|---:|---|---|
|strong_games|win / equal / control|813 / 813|0.23450 → 0.22724|-3.10%|[-0.01645,+0.00086]|No|
|target_features|pass_tds / equal / fpds|1528 / 807|1.07264 → 1.05908|-1.26%|[-0.02889,+0.00409]|No|
|combination|margin / stacked / fpds|815 / 815|10.27582 → 10.19570|-0.78%|[-0.17745,+0.01054]|No|
|opportunity|rush_yds / hierarchy / control|241 / 64|26.94050 → 28.26658|+4.92%|[-0.90251,+3.46369]|No|
|distribution|rush_yds / quantile / fpds|2740 / 814|24.88237 → 24.27310|-2.45%|[-1.06802,-0.12640]|No|

Discovery nominees: 0 of 67 primary comparisons. These do not establish provider value versus the production champion or a market-price edge.

## Coherence

Opportunity outputs: maximum absolute team-minus-players-minus-other error=5.68e-14. This is an arithmetic check, not evidence of better player accuracy.

|Variant|Team-games|Mean other-player fraction|
|---|---:|---:|
|opportunity__rush_yds__control__hierarchy|127|35.0%|
|opportunity__rush_yds__fpds__hierarchy|127|34.5%|

## All primary comparisons

|Family / target / inputs / variant|Reference|n / games|Reference loss|New loss|Delta [corrected95% CI]|Improving seasons|Nominee|
|---|---|---:|---:|---:|---|---:|---|
|strong_games / win / control / equal|A7/win/control|813 / 813|0.234501|0.227242|-0.007259 [-0.016452,+0.000865]|3/3|No|
|strong_games / win / fpds / equal|strong_games__win__control__equal|813 / 813|0.227242|0.226656|-0.000587 [-0.003718,+0.002246]|1/3|No|
|strong_games / margin / control / equal|A7/margin/control|815 / 815|10.034585|9.882063|-0.152523 [-0.541213,+0.227573]|3/3|No|
|strong_games / margin / fpds / equal|strong_games__margin__control__equal|815 / 815|9.882063|9.951932|+0.069869 [-0.053171,+0.201018]|1/3|No|
|strong_games / total / control / equal|A7/total/control|815 / 815|10.391796|10.507282|+0.115486 [-0.115956,+0.334187]|1/3|No|
|strong_games / total / fpds / equal|strong_games__total__control__equal|815 / 815|10.507282|10.512706|+0.005424 [-0.138571,+0.139360]|1/3|No|
|target_features / pass_yds / fpds / equal|A7/pass_yds/fpds|1528 / 807|64.831531|64.588619|-0.242912 [-1.352806,+0.923019]|2/3|No|
|target_features / pass_tds / fpds / equal|A7/pass_tds/fpds|1528 / 807|1.072635|1.059082|-0.013553 [-0.028893,+0.004092]|3/3|No|
|target_features / rec / fpds / equal|A7/rec/fpds|6196 / 815|1.487698|1.483262|-0.004436 [-0.014074,+0.006507]|2/3|No|
|target_features / rec_yds / fpds / equal|A7/rec_yds/fpds|6196 / 815|24.123020|24.116744|-0.006275 [-0.170478,+0.142545]|1/3|No|
|target_features / rush_yds / fpds / equal|A7/rush_yds/fpds|2740 / 814|25.061600|24.882371|-0.179229 [-0.426778,+0.071080]|2/3|No|
|target_features / anytime_td / fpds / equal|A7/anytime_td/fpds|8042 / 815|0.192292|0.190125|-0.002167 [-0.003428,-0.000998]|3/3|No|
|combination / win / control / weighted|A7/win/control|813 / 813|0.234501|0.234443|-0.000059 [-0.000138,+0.000036]|2/3|No|
|combination / win / control / stacked|A7/win/control|813 / 813|0.234501|0.235188|+0.000686 [-0.000649,+0.001975]|1/3|No|
|combination / win / fpds / weighted|A7/win/fpds|813 / 813|0.234834|0.234797|-0.000037 [-0.000178,+0.000115]|2/3|No|
|combination / win / fpds / stacked|A7/win/fpds|813 / 813|0.234834|0.236695|+0.001861 [+0.000247,+0.003406]|0/3|No|
|combination / margin / control / weighted|A7/margin/control|815 / 815|10.034585|10.033676|-0.000909 [-0.003540,+0.001714]|3/3|No|
|combination / margin / control / stacked|A7/margin/control|815 / 815|10.034585|10.055537|+0.020951 [-0.034567,+0.082457]|0/3|No|
|combination / margin / fpds / weighted|A7/margin/fpds|815 / 815|10.275824|10.264182|-0.011642 [-0.023685,-0.000930]|3/3|No|
|combination / margin / fpds / stacked|A7/margin/fpds|815 / 815|10.275824|10.195704|-0.080121 [-0.177446,+0.010537]|2/3|No|
|combination / total / control / weighted|A7/total/control|815 / 815|10.391796|10.391385|-0.000411 [-0.001591,+0.001003]|2/3|No|
|combination / total / control / stacked|A7/total/control|815 / 815|10.391796|10.415220|+0.023424 [-0.035527,+0.091520]|0/3|No|
|combination / total / fpds / weighted|A7/total/fpds|815 / 815|10.639280|10.623064|-0.016216 [-0.029698,-0.005685]|3/3|No|
|combination / total / fpds / stacked|A7/total/fpds|815 / 815|10.639280|10.573451|-0.065829 [-0.192732,+0.046624]|3/3|No|
|combination / pass_yds / control / weighted|A7/pass_yds/control|1528 / 807|65.509007|65.507687|-0.001319 [-0.006010,+0.004361]|2/3|No|
|combination / pass_yds / control / stacked|A7/pass_yds/control|1528 / 807|65.509007|65.455197|-0.053810 [-0.248238,+0.174103]|2/3|No|
|combination / pass_yds / fpds / weighted|A7/pass_yds/fpds|1528 / 807|64.831531|64.806623|-0.024908 [-0.070159,+0.018774]|3/3|No|
|combination / pass_yds / fpds / stacked|A7/pass_yds/fpds|1528 / 807|64.831531|64.704111|-0.127421 [-0.533383,+0.284251]|2/3|No|
|combination / pass_tds / control / weighted|A7/pass_tds/control|1528 / 807|1.070238|1.070255|+0.000018 [-0.000027,+0.000061]|1/3|No|
|combination / pass_tds / control / stacked|A7/pass_tds/control|1528 / 807|1.070238|1.073168|+0.002930 [-0.003967,+0.010124]|1/3|No|
|combination / pass_tds / fpds / weighted|A7/pass_tds/fpds|1528 / 807|1.072635|1.072447|-0.000189 [-0.000378,+0.000014]|3/3|No|
|combination / pass_tds / fpds / stacked|A7/pass_tds/fpds|1528 / 807|1.072635|1.072569|-0.000067 [-0.010153,+0.009139]|2/3|No|
|combination / rec / control / weighted|A7/rec/control|6196 / 815|1.499255|1.499215|-0.000040 [-0.000083,+0.000008]|2/3|No|
|combination / rec / control / stacked|A7/rec/control|6196 / 815|1.499255|1.497604|-0.001651 [-0.004216,+0.000726]|2/3|No|
|combination / rec / fpds / weighted|A7/rec/fpds|6196 / 815|1.487698|1.487371|-0.000326 [-0.000739,+0.000117]|3/3|No|
|combination / rec / fpds / stacked|A7/rec/fpds|6196 / 815|1.487698|1.485273|-0.002425 [-0.006145,+0.001174]|2/3|No|
|combination / rec_yds / control / weighted|A7/rec_yds/control|6196 / 815|24.121611|24.121138|-0.000473 [-0.000901,-0.000084]|3/3|No|
|combination / rec_yds / control / stacked|A7/rec_yds/control|6196 / 815|24.121611|24.078239|-0.043372 [-0.078050,-0.006190]|3/3|No|
|combination / rec_yds / fpds / weighted|A7/rec_yds/fpds|6196 / 815|24.123020|24.116007|-0.007012 [-0.012887,-0.001455]|3/3|No|
|combination / rec_yds / fpds / stacked|A7/rec_yds/fpds|6196 / 815|24.123020|24.010804|-0.112216 [-0.182302,-0.040995]|3/3|No|
|combination / rush_yds / control / weighted|A7/rush_yds/control|2740 / 814|24.835769|24.834808|-0.000961 [-0.001991,+0.000039]|3/3|No|
|combination / rush_yds / control / stacked|A7/rush_yds/control|2740 / 814|24.835769|24.892683|+0.056915 [+0.008534,+0.107707]|1/3|No|
|combination / rush_yds / fpds / weighted|A7/rush_yds/fpds|2740 / 814|25.061600|25.048811|-0.012789 [-0.025522,+0.000262]|3/3|No|
|combination / rush_yds / fpds / stacked|A7/rush_yds/fpds|2740 / 814|25.061600|24.907593|-0.154007 [-0.257902,-0.051289]|3/3|No|
|combination / anytime_td / control / weighted|A7/anytime_td/control|8042 / 815|0.189835|0.189828|-0.000007 [-0.000041,+0.000029]|3/3|No|
|combination / anytime_td / control / stacked|A7/anytime_td/control|8042 / 815|0.189835|0.189921|+0.000086 [-0.000269,+0.000452]|2/3|No|
|combination / anytime_td / fpds / weighted|A7/anytime_td/fpds|8042 / 815|0.192292|0.192017|-0.000275 [-0.000384,-0.000161]|3/3|No|
|combination / anytime_td / fpds / stacked|A7/anytime_td/fpds|8042 / 815|0.192292|0.191203|-0.001089 [-0.001756,-0.000346]|3/3|No|
|opportunity / rush_yds / control / hierarchy|A7/rush_yds/control|241 / 64|26.940500|28.266583|+1.326083 [-0.902507,+3.463694]|0/3|No|
|opportunity / rush_yds / fpds / hierarchy|A7/rush_yds/fpds|241 / 64|27.605366|29.129950|+1.524583 [-1.144620,+4.066915]|0/3|No|
|distribution / margin / fpds / quantile|strong_games__margin__fpds__equal|815 / 815|9.951932|9.990755|+0.038823 [-0.271037,+0.344689]|2/3|No|
|distribution / total / fpds / quantile|strong_games__total__fpds__equal|815 / 815|10.512706|10.597702|+0.084996 [-0.246317,+0.364567]|1/3|No|
|distribution / pass_yds / fpds / quantile|target_features__pass_yds__fpds__equal|1528 / 807|64.588619|65.132212|+0.543592 [-0.849946,+2.152944]|1/3|No|
|distribution / rec_yds / fpds / quantile|target_features__rec_yds__fpds__equal|6196 / 815|24.116744|23.659364|-0.457380 [-0.764554,-0.175212]|3/3|No|
|distribution / rush_yds / fpds / quantile|target_features__rush_yds__fpds__equal|2740 / 814|24.882371|24.273096|-0.609276 [-1.068017,-0.126399]|3/3|No|
|distribution / rec / fpds / hurdle|target_features__rec__fpds__equal|6196 / 815|1.483262|1.641863|+0.158601 [+0.106608,+0.218338]|0/3|No|
|distribution / rec / fpds / nb|target_features__rec__fpds__equal|6196 / 815|1.483262|1.483262|+0.000000 [+0.000000,+0.000000]|0/3|No|
|distribution / pass_tds / fpds / hurdle|target_features__pass_tds__fpds__equal|1528 / 807|1.059082|1.267140|+0.208058 [+0.119366,+0.301070]|0/3|No|
|distribution / pass_tds / fpds / nb|target_features__pass_tds__fpds__equal|1528 / 807|1.059082|1.059082|+0.000000 [+0.000000,+0.000000]|0/3|No|
|distribution / win / control / sigmoid|A7/win/control|813 / 813|0.234501|0.233893|-0.000609 [-0.002048,+0.000944]|1/3|No|
|distribution / win / control / isotonic|A7/win/control|813 / 813|0.234501|0.235869|+0.001367 [-0.004426,+0.008482]|2/3|No|
|distribution / win / fpds / sigmoid|A7/win/fpds|813 / 813|0.234834|0.233034|-0.001800 [-0.003648,+0.000231]|1/3|No|
|distribution / win / fpds / isotonic|A7/win/fpds|813 / 813|0.234834|0.234272|-0.000562 [-0.005584,+0.004962]|2/3|No|
|distribution / anytime_td / control / sigmoid|A7/anytime_td/control|8042 / 815|0.189835|0.189835|+0.000000 [+0.000000,+0.000000]|0/3|No|
|distribution / anytime_td / control / isotonic|A7/anytime_td/control|8042 / 815|0.189835|0.190172|+0.000337 [-0.000301,+0.001107]|1/3|No|
|distribution / anytime_td / fpds / sigmoid|A7/anytime_td/fpds|8042 / 815|0.192292|0.192292|+0.000000 [+0.000000,+0.000000]|0/3|No|
|distribution / anytime_td / fpds / isotonic|A7/anytime_td/fpds|8042 / 815|0.192292|0.192594|+0.000302 [-0.000273,+0.000972]|1/3|No|

## Distribution diagnostics

|Target / variant|80% coverage|Pinball10 /50 /90|Pseudo-line Brier|
|---|---:|---|---:|
|margin / fpds / quantile|71.2%|2.4035 / 4.9954 / 2.5278|n/a|
|total / fpds / quantile|71.5%|2.2720 / 5.2989 / 2.6915|n/a|
|pass_yds / fpds / quantile|71.4%|15.3194 / 32.5661 / 14.4420|0.23714|
|rec_yds / fpds / quantile|75.4%|3.9450 / 11.8297 / 6.4838|0.23692|
|rush_yds / fpds / quantile|73.2%|4.1203 / 12.1365 / 6.8243|0.23140|
|rec / fpds / hurdle|78.8%|0.3442 / 0.8852 / 0.4772|0.24017|
|rec / fpds / nb|87.1%|0.3123 / 0.8531 / 0.4343|0.22884|
|pass_tds / fpds / hurdle|85.4%|0.1611 / 0.4614 / 0.2412|0.23962|
|pass_tds / fpds / nb|94.8%|0.1342 / 0.4251 / 0.2086|0.22075|
|win / control / sigmoid|n/a|n/a|n/a|
|win / control / isotonic|n/a|n/a|n/a|
|win / fpds / sigmoid|n/a|n/a|n/a|
|win / fpds / isotonic|n/a|n/a|n/a|
|anytime_td / control / sigmoid|n/a|n/a|n/a|
|anytime_td / control / isotonic|n/a|n/a|n/a|
|anytime_td / fpds / sigmoid|n/a|n/a|n/a|
|anytime_td / fpds / isotonic|n/a|n/a|n/a|

## Limits / next

2022–2024 were already examined. No fresh2025 pass or2026 selection occurred. True prospective archives must confirm any nominee. Strong game features reconstruct verified champion-style information, not the champion fitted artifact or all advanced inputs. Last-known starters and injury flags retain uncertainty. Revised historical exports and unverified publication times remain limitations.
NB-only keeps the mean fixed; any benefit is a probability/distribution diagnostic, not a primary mean improvement. Quantile medians are evaluated as point forecasts and are not interchangeable with means. Pseudo-lines are not real prop prices. Empirical residual CRPS is unavailable for direct quantile-only heads; pinball and coverage are reported instead.
Coherent outputs retain an explicit other-player remainder. Other-player distinct-scorer counts are labelled approximations, not invented identities. Failed blocks remain retained; no incomplete family can qualify. All existing forecast archives stay unchanged.
Frozen input hashes unchanged: True. Preparation failures before this completed attempt are recorded separately in STATUS.md and retained privately. No raw or player-level subscription rows appear in this report.
