# Phase 8.3: upset identifiers the champion hasn't seen (local lab only)

- **Pre-registration:** `docs/PHASE8_3_PREREGISTRATION.md`, pushed as 7d96249 before any metric was computed.
- **Code:** `lab/upsets83.py`. **Results:** `artifacts/phase83/`.
- **Dashboard:** Prospective Performance → Blind-spot research → "Upset identifiers (8.3)".

## Question
Do any of nine pregame metrics predict that the champion's favourite loses, **beyond the champion's own probability**?

They cover:
- luck that should regress (Pythagorean record, one-score games, fumble recoveries, turnover margin);
- scheduling spots (letdown, lookahead, road fatigue);
- the officiating crew's penalty tendency;
- coaching fourth-down aggressiveness.

All are computed strictly as-of, and a test confirms that changing a later result never alters an earlier game's metrics.

## Result: one look, 2018–2025 (2,219 games; Holm across nine)
| Metric | Games | Effect on upset chance at +1 SD (65% favourite: 34.9% baseline) | One-sided p | Holm | Seasons with predicted sign |
|---|---|---|---|---|---|
| M1 Pythagorean luck | 1,840 | 34.3% → 33.0% (*wrong direction*) | 0.87 | 1.0 | 3/8 |
| M2 One-score-game luck | 2,219 | 34.9% → 33.6% (*wrong direction*) | 0.90 | 1.0 | 3/8 |
| M3 Fumble-recovery luck | 2,219 | 34.9% → 35.0% | 0.46 | 1.0 | 4/8 |
| M4 Turnover-margin regression | 2,219 | 34.9% → 34.8% | 0.55 | 1.0 | 4/8 |
| M5 Letdown (fav won last game by 17+) | 2,219 (17% flagged) | 34.9% → 34.7% | 0.57 | 1.0 | 3/8 |
| M6 Lookahead (division game next) | 2,219 (24% flagged) | 34.9% → 34.6% | 0.64 | 1.0 | 3/8 |
| M7 Road fatigue (3rd+ straight road game) | 2,219 (0.7% flagged: 16 games) | too rare to test meaningfully | 0.77 | 1.0 | 3/8 |
| M8 Referee penalty tendency | 2,122 | 34.9% → 34.4% | 0.68 | 1.0 | 4/8 |
| M9 Underdog more aggressive on 4th down | 2,219 | 34.9% → 34.0% (*wrong direction*) | 0.80 | 1.0 | 3/8 |

Walk-forward (fitted on earlier seasons, scored on later ones), every metric made the champion's probabilities slightly
*worse*: −0.0001 to −0.0015 log loss.

## Conclusion
- **No metric passed,** so none was registered for prospective tracking, and none will be re-tried with different thresholds.
- **Luck and scheduling spots:** the classic betting-folklore signals don't add information once the champion's probability is
  accounted for. Either they were never predictive, or the champion's efficiency-based ratings already absorb them.
- **Opposite direction:** three metrics leaned the opposite way. Favourites that had been "lucky" in close games or by
  Pythagorean record won slightly *more* often. That is consistent with close-game results being partly skill. It is not
  significant.
- **This does not prove upsets are unpredictable.** It shows that these nine signals don't identify them in 2018–25.
- **What's left:** the remaining untested ideas mostly need data the lab doesn't have historically: historical weather forecasts,
  official inactives, and timestamped betting-market movement. The prospective market archive (Phase 8.1) is building the last
  of these.
