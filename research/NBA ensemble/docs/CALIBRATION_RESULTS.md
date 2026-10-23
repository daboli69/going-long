# NBA bounded calibration result — 2026-10-23

**Decision: retain the existing forecast method.** Six fixed candidates completed,84monthly calibrator fits on the same2,460development games. No base-model refits, new downloads, confirmation evaluation, forecast replacement or promotion. There is no benefit to using the rest of the20minute cap after the fixed work finishes.

| Method | Log loss | Brier | Accuracy | Log-loss delta vs control [corrected95%CI] |
|---|---:|---:|---:|---|
| Existing stacked control |0.61483|0.21343|65.85%|reference|
| Platt,300earlier games |0.61454|0.21273|66.26%|-0.00029[-0.00665,+0.00667]|
| Platt,600earlier games |0.61436|0.21286|66.34%|-0.00047[-0.00682,+0.00577]|
| Platt,1200earlier games |0.61781|0.21438|65.85%|+0.00297[-0.00269,+0.00931]|
| Isotonic,300earlier games |0.70097|0.21672|65.37%|+0.08614[+0.03891,+0.14452]|
| Isotonic,600earlier games |0.68996|0.21705|64.84%|+0.07513[+0.03061,+0.12451]|
| Isotonic,1200earlier games |0.67033|0.21626|65.37%|+0.05550[+0.01856,+0.10105]|

Lower probability losses are better. Best candidate by the fixed primary metric was Platt600, but its relative log-loss reduction was only about0.08%, its interval crossed zero and it improved only one of two development seasons. It failed the >=1%gate. The isotonic variants worsened log loss; no extra tuning or candidate expansion followed these results.

Chronology: saved2023OOF probabilities supplied earlier calibration history;2024/2025ending-seasons were scored month by month. Each fit used outcomes available strictly before the month's first instant, with the conservative tipoff+24h rule. Paired whole-game bootstrap2,000draws; Bonferroni across6candidates. These are reused development seasons, **not fresh independent validation**. The spent2025–26 confirmation and prospective2026–27 outcomes were excluded from the run. Operational models and saved forecasts retained their original hashes.

Four candidates checkpointed before a transient Windows/OneDrive STATUS.json replacement error. It was logged; the unchanged command resumed the final two, without repeating completed fits. The result's0.45second elapsed field describes the successful resumed invocation only; earlier computation time was not retained. Total end-to-end task time includes preregistration, implementation, tests and recovery; no claim of hours of simulation compute is made.27offline tests passed before the real run; final verification is recorded in the root trackers.

Use existing `START_NBA.bat` option4 or **Research & Calibration → Run / load bounded calibration check**. Command:`python -m nba_lab.cli calibrate`. A completed run returns cached results. Metrics, corrected intervals and reliability bins appear on the research page; detailed machine output is reports/calibration_v1/RESULT.json. This is calibration of directly calculated winner probabilities, not a possession/game-score simulator. Injuries/lineup changes remain unmodeled. Nothing promoted.
