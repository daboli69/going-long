# FPDS improvement study — Amendment 8

Run `20261021T204121Z`. 2022-24 previously examined discovery only; no holdout pass or2026 selection. All outputs shadow only; nothing promoted.

Completed 12 primary comparisons; 0 failed blocks. Recorded 12 member/head outputs, 50 internal fit configurations and 750 fit dispatches. The fixed ceiling is12 outputs /84 internal configurations /1500 dispatches. No grid search.

Lower loss is better. Negative delta means improvement against the named reference. Intervals are registered family-corrected paired whole-game95% intervals. A discovery nominee requires >=1% reduction, corrected interval below zero, >=200 games, two improving seasons, identical complete samples, no failed blocks and Holm p<.05. It still requires future confirmation.

Primary loss is MAE for yards/margin/total, Poisson deviance for receptions/passing TDs, and Brier for winners/anytime TD. Median quantile heads are point forecasts; they are not means.

## Best observed change per family

These are exploratory rankings within the fixed study; the complete table below includes regressions. Different rows have different references and are not automatically comparable.

|Family|Target / variant / inputs|n / games|Reference → new loss|Change|Corrected95% CI|Nominee|
|---|---|---:|---:|---:|---|---|
|strong_games|Unavailable|||||No|
|target_features|Unavailable|||||No|
|combination|Unavailable|||||No|
|opportunity|rec_yds / hierarchy / control|6196 / 815|24.12161 → 24.37722|+1.06%|[-0.07110,+0.62027]|No|
|distribution|Unavailable|||||No|

Separate opportunity-only repair of `20261021T200416Z`. The original failed blocks and original zero nominations remain unchanged; successful other families were not refitted.

Discovery nominees: 0 of 12 primary comparisons. These do not establish provider value versus the production champion or a market-price edge.

## Coherence

Opportunity outputs: maximum absolute team-minus-players-minus-other error=1.14e-13. This is an arithmetic check, not evidence of better player accuracy.

|Variant|Team-games|Mean other-player fraction|
|---|---:|---:|
|opportunity__anytime_td__control__hierarchy|1628|32.3%|
|opportunity__anytime_td__fpds__hierarchy|1628|34.9%|
|opportunity__pass_tds__control__hierarchy|1528|16.0%|
|opportunity__pass_tds__fpds__hierarchy|1528|18.8%|
|opportunity__pass_yds__control__hierarchy|1528|14.9%|
|opportunity__pass_yds__fpds__hierarchy|1528|15.5%|
|opportunity__rec__control__hierarchy|1628|38.0%|
|opportunity__rec__fpds__hierarchy|1628|38.4%|
|opportunity__rec_yds__control__hierarchy|1628|36.8%|
|opportunity__rec_yds__fpds__hierarchy|1628|37.5%|
|opportunity__rush_yds__control__hierarchy|1573|33.9%|
|opportunity__rush_yds__fpds__hierarchy|1573|33.7%|

## All primary comparisons

|Family / target / inputs / variant|Reference|n / games|Reference loss|New loss|Delta [corrected95% CI]|Improving seasons|Nominee|
|---|---|---:|---:|---:|---|---:|---|
|opportunity / pass_yds / control / hierarchy|A7/pass_yds/control|1528 / 807|65.509007|69.659916|+4.150910 [+1.546989,+7.058704]|0/3|No|
|opportunity / pass_yds / fpds / hierarchy|A7/pass_yds/fpds|1528 / 807|64.831531|71.229272|+6.397741 [+3.629584,+9.469367]|0/3|No|
|opportunity / pass_tds / control / hierarchy|A7/pass_tds/control|1528 / 807|1.070238|1.336023|+0.265785 [+0.070789,+0.593452]|0/3|No|
|opportunity / pass_tds / fpds / hierarchy|A7/pass_tds/fpds|1528 / 807|1.072635|1.555764|+0.483129 [+0.190395,+0.913433]|0/3|No|
|opportunity / rec / control / hierarchy|A7/rec/control|6196 / 815|1.499255|1.602983|+0.103729 [+0.062831,+0.141981]|0/3|No|
|opportunity / rec / fpds / hierarchy|A7/rec/fpds|6196 / 815|1.487698|1.780781|+0.293084 [+0.205094,+0.400535]|0/3|No|
|opportunity / rec_yds / control / hierarchy|A7/rec_yds/control|6196 / 815|24.121611|24.377222|+0.255611 [-0.071097,+0.620271]|0/3|No|
|opportunity / rec_yds / fpds / hierarchy|A7/rec_yds/fpds|6196 / 815|24.123020|25.100724|+0.977705 [+0.521393,+1.428622]|0/3|No|
|opportunity / rush_yds / control / hierarchy|A7/rush_yds/control|2740 / 814|24.835769|25.467353|+0.631584 [-0.023074,+1.283912]|0/3|No|
|opportunity / rush_yds / fpds / hierarchy|A7/rush_yds/fpds|2740 / 814|25.061600|25.749197|+0.687597 [-0.009744,+1.453981]|0/3|No|
|opportunity / anytime_td / control / hierarchy|A7/anytime_td/control|8042 / 815|0.189835|0.195556|+0.005721 [+0.003037,+0.008254]|0/3|No|
|opportunity / anytime_td / fpds / hierarchy|A7/anytime_td/fpds|8042 / 815|0.192292|0.204584|+0.012292 [+0.008599,+0.015837]|0/3|No|

## Distribution diagnostics

|Target / variant|80% coverage|Pinball10 /50 /90|Pseudo-line Brier|
|---|---:|---|---:|

## Limits / next

2022–2024 were already examined. No fresh2025 pass or2026 selection occurred. True prospective archives must confirm any nominee. Strong game features reconstruct verified champion-style information, not the champion fitted artifact or all advanced inputs. Last-known starters and injury flags retain uncertainty. Revised historical exports and unverified publication times remain limitations.
NB-only keeps the mean fixed; any benefit is a probability/distribution diagnostic, not a primary mean improvement. Quantile medians are evaluated as point forecasts and are not interchangeable with means. Pseudo-lines are not real prop prices. Empirical residual CRPS is unavailable for direct quantile-only heads; pinball and coverage are reported instead.
Coherent outputs retain an explicit other-player remainder. Other-player distinct-scorer counts are labelled approximations, not invented identities. Failed blocks remain retained; no incomplete family can qualify. All existing forecast archives stay unchanged.
Frozen input hashes unchanged: True. Preparation failures before this completed attempt are recorded separately in STATUS.md and retained privately. No raw or player-level subscription rows appear in this report.
