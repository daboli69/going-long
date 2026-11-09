# Packers 45, Patriots 27: luck or defect? Results

Rule: `docs/GBNE_AUDIT_PREREG.md` with Amendment 1. Code: `scripts/gbne_audit.py` (stages `game`, `gate`, `run`, `rebuild`). Numbers: `docs/gbne_game.json`, `docs/gbne_gate.json`, `docs/gbne_audit.json`.

## Verdict

**Mostly luck.** Four New England turnovers to none explain about 16 of the 20.4 points by which the result missed the frozen pregame forecast. No defect could be shown or ruled out in the forecasts themselves, because both defect tests failed their power gate. Nothing was promoted and no fix was pre-registered, since no defect showed up.

## Completed

**A. The game, from the plays.** The pregame forecast margin was Green Bay -2.4 (frozen 2026-11-05, hash re-checked). The result was Green Bay +18, a miss of 20.4 points against a forecast standard deviation of 13.4.
- Turnovers rebuilt from the plays: Maye interceptions at 14:32 of the first quarter (a deep throw, 24 air yards), 12:54 of the second (37 air yards) and 5:47 of the second (15 air yards), and a fumble lost in the third on a 4-yard completion. Green Bay had no turnovers.
- Expected turnovers from league rates (2022 to 2025, pbp only): New England 1.4 against 4 actual, Green Bay 1.1 against 0. Net turnover luck against New England: 3.7 turnovers, worth 15.9 points at the league average cost of 4.3 points a turnover. Sensitivity with team-specific season rates through Week 8: 3.5 turnovers, 14.8 points.
- Turnover-adjusted margin: Green Bay +2.1 (sensitivity +3.2). That is 4.5 points from the forecast, a third of one standard deviation.
- Without turnover plays, New England was still behind on efficiency (0.15 expected points per play against Green Bay's 0.29), driven by Love's 0.76 per dropback against Maye's -0.22. Green Bay's passing in this game was far above its season level.
- Injuries: Micah Parsons and A.J. Brown were Out in the first snapshot that has Week 9 rows (2026-11-07 11:00 UTC). The freezes were made two to three days earlier (2026-11-05), so neither could have been in them. Their effect is not quantified here.
- FTN charting (interception-worthy flags) and PFR pressure for this game are not published yet, so the charting method was not run (Amendment 1). Rerun `game` once they appear.

**B. Calibration against the closing line, 3,649 games, 2012 to 2025, walk-forward.** Gate results first: the band test (D1) is not testable for any of the three forecasts (planted-gap power 40%, 0% and 0% at 0.03; for F2 and F3 the rule cannot fire at all because they are not measurably different from the market in the band). The information test (T3) is not testable (power 20%, 17%, 13% at 0.004, against 80% required). Those readings were not made.

What is readable (overall scoring, no gate needed), model minus closing line, log loss with 98.3% interval: F1 `p_xgb_deep_platt` +0.026 (0.018 to 0.033), F2 `p_margin_platt` +0.030 (0.022 to 0.037), F3 `p_win` +0.029 (0.020 to 0.037). Brier tells the same story. No forecast beat the closing line in more than 2 of 14 seasons. In the decomposition, reliability is similar to the market's (0.0013 to 0.0026 nats against 0.0011); the gap is resolution (0.049 to 0.053 against 0.077).

Band 55 to 65%, descriptive only (not a defect call): forecast 0.598 for all three, observed favorite win rate 0.614, 0.599 and 0.626 over 1,437, 1,344 and 1,422 games, intervals all including zero. If anything the favorites in this band win slightly more than forecast, the opposite of what a Green Bay upset would suggest.

Hashed freezes scored on played games (27 games, Weeks 8 and 9, all hashes valid): log loss 0.478 for F1, 0.496 for F2 and 0.479 for the market at freeze. Too few games to separate them.

## Model Research

The stored forecasts are model-only, so being behind the closing line is expected: the line prices late news and information the models do not see. This audit shows how large the gap is (about 0.03 log loss, all in resolution), not that calibration is broken. The tests that could say whether the models' disagreements with the market ever help (T3) need many more games than exist.

## Concerns

- The 57.7% shown in the app for this game has no stored history, so it could not be audited over time. Only the three stored model forecasts were.
- The band power is low: a 0.03 gap in the band is detectable about 40% of the time at best.
- Part A treats all turnovers beyond league average as luck, though some is skill (Maye's higher interception rate, Green Bay's takeaways). The sensitivity run narrows that but does not remove it. The charting method would be better.
- The closing line is undated. The freezes were made three days before kickoff, and the line moved after them.
- Late injury news is outside every freeze.

## Needs Travis

- Whether to add an injury-aware refresh just before kickoff to the freeze, as a pre-registered change. This audit does not support it as a fix for this game.
- Permission to rerun part A with charting once FTN publishes this game.
