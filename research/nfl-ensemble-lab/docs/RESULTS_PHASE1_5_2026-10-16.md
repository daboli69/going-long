# Phase 1.5: data integrity, injuries, reliability (2026-10-16)

Production model: **v20261016_212540** (85 features, default groups, no injury group).
Study artifacts: `artifacts/study_phase1_5/` (re-create with `python -m lab.study`).
2025 has already been inspected, so it is reported as a **diagnostic** holdout only and used for
no decision. All decisions below used development walk-forward 2019–2022 and validation 2023–2024.

## 1. Leakage fixes
| Issue | Fix |
|---|---|
| QB features used the actual starter (hindsight) | Pregame projected starter: previous game's starter, switched only by a verified pregame Out/Doubtful. It matches the actual starter in 88% of games (diagnostic only). A test proves rewriting actual starters changes no feature. |
| Game-day roof open/closed | Static stadium roof type (dome / retractable / outdoors). |
| Injury reports | Rows used only when available before kickoff. Coverage is decided per game kickoff. Practice-only live snapshots do not count as final. |
| Calibration chosen on validation only; isotonic overfit early seasons | Choose none/Platt over 2019–2024 mean per-season log loss; isotonic removed. |
| Champion picked on a 0.001 validation edge | 1-SE paired-bootstrap tie rule; ties broken by 2019–2024 stability. |

Re-audited and unchanged: rolling windows (as-of joins, strict `<` kickoff), ratings (fit before the
week's first kickoff), rest days, playoff/divisional flags (schedule), market lines (benchmark only),
walk-forward training (season s trained on seasons < s), calibrators/weights/stacker (earlier seasons only).
Remaining approximations: nflfastR's EPA model was fit on all seasons, and the timing of post-game
stat corrections is unknown.

## 2. Injury data
| Season | Official report rows | Usable before kickoff | Games with a verified report for both teams |
|---|---|---|---|
| 2016–2022 | 5,104–5,682 / season | 99.7–100% | 100% |
| 2023 | 5,599 | 100% | 97.5% (7 games: the nflverse 2023 file has no rows for playoff weeks 20-22) |
| 2024 | 6,215 | 99.95% | 100% |
| 2025 | 6,068 | **0** (file has no row timestamps) | 0% |
| 2026 | live | lab archive only (started 2026-10-16) | 0% so far: Friday designations not yet published |

- **Safe for historical modeling (2016–2024):** official Out/Doubtful/Questionable designations,
  snap-share-weighted position-group loads (QB, RB, WR, TE, OL, DL, LB, CB, S), starters-out counts,
  offense/defense totals, availability × opponent-strength interactions, and the projected-QB switch.
- **Live monitoring only:** ESPN injury feed (incl. IR), ESPN depth-chart QB1, nfldata listed QB,
  practice participation before the final report. These have no validated history.
- **Missing, by design:** 2025 and pre-archive 2026 injury features are NaN with `inj_available` = 0.

## 3. Does injury information help? (paired log-loss difference, injury minus no injury; negative = better)
| Method | Dev 2019–22 | Validation 2023–24 |
|---|---|---|
| Equal average | +0.0004 (−0.0017, +0.0025) | −0.0033 (−0.0066, +0.0001) |
| Weighted average | +0.0003 (−0.0019, +0.0026) | −0.0032 (−0.0066, +0.0002) |
| Random Forest | −0.0020 (−0.0045, +0.0004) | −0.0025 (−0.0058, +0.0009) |
| XGBoost | +0.0025 (−0.0009, +0.0058) | −0.0032 (−0.0069, +0.0005) |

Verdict: **not promoted.** The validation gain is small and borderline, and it does not appear on
development seasons. It also cannot be checked on 2025, which has no timestamped data. The group stays
selectable in Train Models and fully stored for Phase 2. Re-test it once the lab's own archive covers a season.

## 4. Reliability findings
- **Random Forest 2025:** its log loss (0.637–0.639) is inside its own 2018–2024 range (0.604–0.657).
  It was champion only by a 0.0014 validation edge. This was a selection-noise problem, fixed by the tie rule.
- RF regularization (min leaf 25/50/100 × max_features 0.3/0.15): dev 0.6335–0.6348, validation
  0.6289–0.6321. No meaningful difference, so tuned settings are kept.
- Compact (48 features) vs. default (85): no significant difference for any model.

## 5. Before / after (log loss; leaky Phase 1 vs. Phase 1.5)
| Method | Validation 2023–24 | Diagnostic 2025 | 2026 to date (n=79) |
|---|---|---|---|
| Champion | RF 0.6292 → **weighted avg 0.6315** | 0.6374 → 0.6354 | 0.6681 → 0.6627 |
| Equal average | 0.6315 → 0.6320 | 0.6344 → 0.6355 | 0.6567 → 0.6626 |
| Logistic Regression | 0.6348 → 0.6351 | 0.6355 → 0.6385 | 0.6480 → 0.6528 |
| Point-diff baseline | 0.6428 | 0.6363 | 0.6640 |
| Closing market | 0.6081 | 0.6070 | 0.6536 |

The combined Phase 1.5 changes (no hindsight QB, static roof, recalibration) cost about 0.0005–0.003 on
validation and 2025 for the individual models and averages, which is the honest price of the leak. The 2026 drop is larger, but at 79 games that is noise. Margin models are unchanged
in substance (validation MAE 10.17 ensemble vs. 9.84 closing spread). Nothing beats the closing market.

## 6. Phase 2 readiness
Ready, with limits. The feature store, out-of-sample probabilities, outcomes, untimestamped closing
no-vig probabilities, injury features (2016–2024 verified), missing-data indicators, provenance
columns and player-level verified injury rows are all saved (`docs/METHODOLOGY.md`, Phase 2 interface).
Limits: market odds are closing consensus without timestamps. Injury history has a gap for 2025, and
2026 depends on `refresh_data.bat` running before kickoffs.
