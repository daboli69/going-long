# NBA official injury-report values: results, 2026-10-23

Protocol `docs/INJURY_PREREGISTRATION.md` was committed (43e7d42d) before any fit. One pass: 36 base fits, 22 seconds. The original ensemble and the strength shadow are unchanged.

## Result (stacked six-model ensemble, 3,690 games, 2023-24 to 2025-26)

| | Log loss | Brier | Accuracy |
|---|---:|---:|---:|
| Strength shadow inputs (control) | 0.61816 | | 67.3% |
| + official injury report | **0.61014** | -0.00289 | **67.6%** |
| Elo benchmark, same games | 0.61380 | | |

Change -0.00803, 95% interval [-0.01171, -0.00427]. Better in all three seasons (-0.0065, -0.0101, -0.0074). Relative gain 1.30%, which also clears the original project's 1% bar. **Passed.**

Every member improved: logistic -0.0064, MLP -0.0074, SVM -0.0057, random forest -0.0045, histogram boosting -0.0044, XGBoost -0.0034.

## Read this carefully

- This is the first input set that beats plain Elo by a clear margin on these seasons (0.6101 vs 0.6138). Without injuries, the strength inputs only roughly matched Elo on the shorter 2022-onward training history.
- The stacker doesn't help here. Logistic regression alone scored 0.6028, better than the stacked ensemble's 0.6101. The stacker learns from very few earlier folds, and the first test season falls back to an equal mean. The protocol fixed the stacked ensemble as the primary output, so the shadow keeps it; a stacker study is a separate question.
- One report per day, about an hour before the first game. Late games don't see later updates, in training or live.
- All three test seasons were examined in earlier studies with other inputs. This is retrospective evidence, not fresh confirmation.

## What runs now

- `nba_lab/injury_features.py` builds the values; `tests/test_injury_features.py` checks the target box, late reports, unknown teams and live-report caching.
- `docs/INJURY_SHADOW_CONFIG.json` freezes the candidate with code hashes. `nba_lab/injury_shadow.py` fetches the latest official report published by the earlier of now and first tipoff minus 1 hour, maps names, fits the six members on 2021-22 onward and stacks them with the study's out-of-fold stacker.
- If no report is out yet, every team is unknown, never healthy. The Today page warns about this. Run daily refresh in the afternoon so the report exists.
- Daily refresh (launcher option 2) and `python -m nba_lab.cli shadow-forecast` append injury-shadow forecasts. The Today page shows them, with the report link and players listed Out, in a new expander above the strength shadow.
- First archives: 11 unstarted games on 2026-10-23 (2:45 PM ET report) and 8 games on 2026-10-24. Tomorrow's slate was saved early, so 13 teams were still not submitted. Rerun tomorrow afternoon.
