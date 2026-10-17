# Phase 8 pre-registration: independent football specialists

**Written 2026-10-17, before any specialist was built or any specialist result was computed.** It is committed separately, so the
git history proves the order. Anything below that changes after results are seen must be reported as a
deviation in the final report.

## Data exposure (honest status)
- **Development seasons 2016–2022** were used to design features over seven phases. They are **design-exposed**.
- **2023–2025** were inspected repeatedly (validation looks, error analyses), so they are **research-exposed**. They are not
  pristine holdouts, and results on them are reported as a "check", never as validation.
- **Only future, immutably archived 2026 games** are clean prospective evidence.
- **Champion out-of-fold (OOF) predictions** exist from 2018. The champion's ensemble weights and calibration were chosen on
  2023–24, so its 2023–24 OOF probabilities are mildly optimistic for the champion.

## Common protocol (every specialist)
- **Walk-forward:** for each target season s in 2018–2026, fit on seasons 2016..s−1 only. Preprocessing (imputation,
  scaling) is fitted inside that window. Calibration uses Platt scaling fitted on the specialist's own earlier OOF predictions.
- **Inputs:** only pregame, as-of columns from the feature store (whose leakage gate covers them), plus new as-of drive tables
  built with strict "kickoff before" joins.
- **Never used as inputs:** actual starters, game-day weather, closing odds, results or play participation after the cutoff.
- **Abstention:** a specialist returns no prediction when its required inputs are missing (e.g. no verified injury report).
  Combinations then fall back to the recalibrated champion for that game.
- **Standalone metrics:** log loss (primary), Brier score, accuracy, calibration (10-bin ECE), margin MAE where a margin is
  produced, correlation of predictions and of errors with the champion, and partial association with the outcome given
  the champion probability.

## Specialists (hypothesis, then feature boundary; no specialist may use the champion's rating-margin difference)
| ID | Hypothesis | Allowed inputs | Mechanism |
|---|---|---|---|
| A availability | Who is expected to play adds information beyond team form | Phase 7.2 lineup counts (missing snaps, starters out, confirmed out, uncertainty, OL continuity), QB v1/v2 flags, verified injury counts | L2 logistic regression; abstains without a verified report for both teams |
| B matchup | Specific unit-vs-unit interactions matter beyond totals | Pass and rush offense vs opponent defense, pressure vs protection, separation, explosive rate vs explosive allowed, early-down vs early-down (products and differences of standardized unit stats) | Gradient-boosted trees, depth ≤ 3, strong regularization |
| C form/change | Genuine change shows up as shrunk recent-vs-baseline shifts and personnel or coaching changes | (last 3 − season blend) for EPA and success rate with n/(n+k) shrinkage, QB change flags, coach change, snap-distribution change, OL churn | L2 logistic regression |
| D environment | Rest, travel, time zone, roof, division and home field add little beyond ratings | rest days, travel km, time-zone shift, body clock, dome/roof, division game, neutral site, week | L2 logistic regression (no weather: historical forecasts are not recoverable) |
| E drive simulation | Scoring built from drives (pace × drive outcomes) gives differently shaped errors | As-of shrunk team rates: drives per game, TD/FG/empty share of drives, points per drive, for offense and defense allowed | Opponent-adjusted drive-outcome probabilities, then a Monte Carlo score distribution (P(win), margin, total), then Platt calibration |
| F situational residual | The champion is miscalibrated in identifiable situations | Champion OOF logit (offset), favorite size band, early season (week ≤ 4), QB uncertainty, lineup disruption, extreme matchup | Logistic correction with the champion logit as an offset, fitted only on earlier seasons' OOF; strong L2 |

## Combination experiment (exactly these 8 comparisons, all against the recalibrated champion)
- **Baseline:** R = logistic regression of the outcome on logit(champion OOF), fitted walk-forward on earlier OOF seasons.
- **For each specialist k in A–F:** S_k = logistic regression on [logit(champion), logit(specialist k), abstain indicator]
  with L2 penalty (C = 1), walk-forward. That's 6 comparisons.
- **Selected combination:** champion + every specialist whose S_k improved the 2019–22 pooled log loss. That's 1 comparison.
- **Constrained stack:** all six specialists plus the champion, with L2 (C = 0.3). That's 1 comparison.
- **First stacking season:** 2019 (needs at least one earlier OOF season). Development window **2019–2022**; check window **2023–2025**.
- **Also reported, not tested:** champion alone, the six-model equal average, and every specialist alone.

## Decision rule (fixed now)
A combination **qualifies** only if all of these hold:
1. pooled 2019–22 log-loss gain over R is > 0, with a Holm-adjusted (m = 8) one-sided paired bootstrap p < 0.05;
2. the 2023–25 check gain is ≥ 0;
3. the gain is not explained by calibration alone (the gain over R is the test, and R is already recalibrated);
4. the specialist's live inputs are available for upcoming games.

At most **one** new frozen prospective challenger may be registered. It would be the qualifying combination with the
largest dev gain. It is evaluated only on future archived games, with Holm correction across all tracked challengers and
the 128-game minimum. If nothing qualifies, nothing is registered and the negative result is reported.

## Not allowed
- Tuning specialists against 2023–2025.
- Adding specialists or combinations after seeing results without reporting them as deviations.
- Changing the champion, the six models, either existing challenger, or any archive.
