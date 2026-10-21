# Local all-model session results — 2026-10-21

Both requested fixed runs completed without failed blocks. Forecast archive completed09:33:34 Eastern; comparison completed09:55:02 Eastern. The supervisor stopped at09:55, rather than repeating identical trials until15:30. No active manual worker remains.

## Forecast output

14 week7 games; 1,446 output rows across both arms and market comparisons (not a unique-player count). Six game families and four prop families, equal averages and offensive first-TD probabilities. 10,000 distribution draws,seed17. Training years2021–2026, through completed week6; cutoff2026-10-19. New immutable forecast revision; old archives/champion unchanged.

Forecast job: `5ef33f32d6ed4d2b98372932728fb416`. Open `launch_lab.bat` → Research → FPDS Research → Saved manual run → project/complete. The local page shows individual games, players and member outputs. Source and derived subscription rows remain private.

## Matched development comparison

2022–2024 expanding walk-forward, already-examined development seasons. Both arms use identical eligibility, model parameters and NFL history windows; FPDS arm adds audited provider features. Lower loss is better; delta=FPDS minus control. Intervals are paired whole-game bootstrap95% intervals corrected for the registered family comparisons.

|Target / metric|Rows / games|NFL-only|NFL+FPDS|Delta [corrected95% CI]|Decision|
|---|---:|---:|---:|---|---|
|Winner / Brier|813 / 813|0.2345|0.2348|+0.0003 [-0.0051, +0.0066]|No demonstrated improvement|
|Spread / margin / MAE|815 / 815|10.0346|10.2758|+0.2412 [-0.0470, +0.5318]|No demonstrated improvement|
|Total / MAE|815 / 815|10.3918|10.6393|+0.2475 [-0.0043, +0.4970]|No demonstrated improvement|
|Passing yards / MAE|1528 / 807|65.5090|64.8315|-0.6775 [-2.2396, +0.8297]|No demonstrated improvement|
|Passing TDs / Poisson deviance|1528 / 807|1.0702|1.0726|+0.0024 [-0.0238, +0.0286]|No demonstrated improvement|
|Receptions / Poisson deviance|6196 / 815|1.4993|1.4877|-0.0116 [-0.0299, +0.0051]|No demonstrated improvement|
|Receiving yards / MAE|6196 / 815|24.1216|24.1230|+0.0014 [-0.2639, +0.2286]|No demonstrated improvement|
|Rushing yards / MAE|2740 / 814|24.8358|25.0616|+0.2258 [-0.1517, +0.5928]|No demonstrated improvement|
|Anytime TD / Brier|8042 / 815|0.1898|0.1923|+0.0025 [+0.0005, +0.0044]|Worse|

No combined ensemble passed the registered discovery nomination rule. Passing-yard MAE fell about1.03% and reception deviance0.77%, but corrected intervals include zero. Anytime-TD Brier worsened about1.29%, with corrected interval excluding zero. Derived first-TD log loss and Brier also worsened (secondary only).

One individual nominee: anytime-TD MLP Brier0.23104 →0.21293, improvement7.84%, delta−0.01811 [−0.02019,−0.01608], direction consistent3/3 seasons. It still trails the NFL-only equal ensemble at0.18984. This does not justify choosing it as the replacement or claiming a confirmed improvement.

Game closing benchmarks also outperformed the FPDS ensemble. Margin MAE was0.857 points worse [0.432,1.311]; total MAE0.518 points worse [0.117,0.889]. Home-winner Brier was0.02494 worse [0.01212,0.03757] versus the stored no-vig market benchmark. Prices were benchmarks only, never model inputs. No historical prop-price edge can be assessed.

Comparison job: `eb191266fa1449c1817980abe1878bb9`; 270 completed blocks,1,260 fit calls,104 distinct registered output configurations including two derived first-TD outputs. Production fit added84 fit calls using the same fixed configurations.51 paired member/ensemble comparisons; zero failed blocks. All attempted configurations remain logged; no further fitting or scoring was performed for this report.

## Limits and decision

Forecasts were produced before the comparison completed and therefore use labelled training-residual warm-up intervals, not the later out-of-fold comparison bank. Single seed; stability, coherence and scenarios remain untested. Historical exports can contain revisions and unknown publication times. No new2025 confirmation;2026 was used only for eligible prospective training, never configuration selection. No production promotion. Retain NFL-only as the comparison reference; isolated FPDS gains remain exploratory.
