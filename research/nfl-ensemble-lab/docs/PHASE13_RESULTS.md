# Phase 13 results: where the remaining error comes from

- **Pre-registration:** `docs/PHASE13_PREREGISTRATION.md`, commit 294685aa, made before any number here was computed.
- **Code:** `lab/phase13.py`. **Results:** `artifacts/phase13/` (local).
- **One look per test.** Nothing was promoted, and the champion, scheduler and GOING are unchanged.

## A. Error budget (2018 to 2024, 1,903 games with opening and closing lines)
| Forecast | Log loss | Brier | Reliability (lower is better) | Resolution (higher is better) |
|---|---|---|---|---|
| Champion | 0.6293 | 0.2196 | 0.0009 | 0.0294 |
| Opening line | 0.6204 | 0.2156 | 0.0007 | 0.0325 |
| Closing line | 0.6092 | 0.2107 | 0.0008 | 0.0361 |

**Noise floor**
- **Closing line:** its expected log loss if perfectly calibrated is 0.6159. Its realised loss is 0.6092, so the close sits at
  the floor.
- **Margins:** they scatter about 12.8 points around the closing spread. That much is irreducible.

**Calibration isn't the problem**
- All three forecasts are equally well calibrated.
- The champion loses on resolution, meaning how sharply it separates likely winners from likely losers.
- Recalibrating the champion walk-forward made it slightly worse (−0.002).

**Where the champion's 0.020 gap to the close comes from** (95% intervals):

| Part | Share of the gap |
|---|---|
| Modelling error against the opener | 0.011 (0.002 to 0.020) |
| Information the market absorbed after the opener | 0.011 (0.006 to 0.017) |
| Calibration | about 0 |

So the gap is about half modelling and half late information.

**Power**
- Paired per-game log-loss differences have an SD of 0.196.

| Improvement to detect | Games needed (one-sided 5%, 80% power) | About |
|---|---|---|
| 0.020 | 594 | 2 seasons |
| 0.010 | 2,376 | 9 seasons |
| 0.005 | 9,504 | 35 seasons |
| A 0.1 correlation in line-move prediction | 618 | |

**2026 by stage (descriptive, 12 to 26 games per stage):** the champion trailed the market at every stage. Final stage: 0.774
against 0.697.

## B. Information-timing audit (2018 to 2024)
| Tag | Share of games | Opening-to-closing move, tagged / untagged | Champion's gap to close, tagged / untagged |
|---|---|---|---|
| **Starting QB changed from the previous game** | 19% | **2.2 / 1.2 points** | **0.046 / 0.014** |
| Top-22 starter listed Out before kickoff | 69% | 1.5 / 1.1 | 0.022 / 0.015 |
| Top-22 starter inactive | 71% | 1.5 / 1.0 | 0.022 / 0.016 |
| Forecast wind of 15+ mph (2022 to 2024) | 4% (22 games) | 1.3 / 1.6 | 0.022 / 0.022 |

- **QB changes are the biggest reducible gap.** In those games the market moves twice as far, and the champion's loss to the
  close is three times larger.
- **The starter tags were too broad to be useful.** Defined as the top 11 on each side, they flag about 70% of games.
- **Wind adds nothing measurable,** on 22 games.

## C. Structural challenger: failed (single look, 2021 to 2024, 1,086 games)
**Ablation (2018 to 2020).** All three components were kept, but only anchoring to the opener mattered: development log loss
was 0.6167 with it and 0.6295 without. The win-total prior and the weekly rating noise each helped by less than 0.0001.

| Forecast | Log loss |
|---|---|
| Kalman challenger | 0.6254 |
| Opening line | 0.6252 |
| Phase 11 blend | 0.6255 |
| Champion | 0.6356 |
| Closing line | 0.6111 |

- **H1, challenger against champion:** −0.0102, 95% CI −0.0214 to +0.0008. Bootstrap p 0.036, Diebold-Mariano p 0.035.
  Holm-adjusted p is 0.072, so it **fails**.
- **H2, challenger against the opener:** +0.0002, p 0.57. **Fails.**
- **Why:** the fitted weight on the ratings, κ, came out between −0.08 and +0.05 in every season. The challenger is the opening
  line. Team ratings built from scores, even with market win-total priors, add nothing the opener doesn't already have.
- **Limitation, recorded honestly:** in 2021 and 2023 the optimiser barely moved the process-noise parameter from its starting
  value (q ≈ 1.0); in 2022 and 2024 it went to about 0. The conclusion doesn't depend on this, because κ ≈ 0 either way.

## D. Simulator coherence (descriptive)
**Neutral game, trained through 2023, against 2024:**

| Measure | Simulated | Real |
|---|---|---|
| Plays | 62.2 | 61.0 (+2%) |
| Yards | 350 | 336 (+4%) |
| Points | 22.9 | 22.9 |
| Points SD | 10.5 | 9.8 (slightly too wide) |

**Market-anchored team points, 2023 to 2025:** the simulator's error against actual scores (7.30 points) matches the market's
implied totals (7.21). 6% of team-games missed the implied total by more than 2 points.

**Win probability, 60 games of 2025:**
- The simulator correlates 0.96 with the close, but scores worse: log loss 0.604 against 0.577 for both the close and the
  champion.
- **Recommendation:** take game win probabilities from the market, not the simulator. Use the simulator for player
  distributions.

## E. Validation beyond us
**Line-move prediction**, the correlation of (forecast minus open) with (close minus open):
- champion 0.21;
- Kalman challenger −0.01;
- nfelo 0.53.

**nfelo against the same 1,693 games:**

| Forecast | Log loss |
|---|---|
| nfelo at open | 0.613 |
| Opening line | 0.618 |
| Champion | 0.630 |
| nfelo at close | 0.607 |
| Close | 0.609 |

**Caution on nfelo:** its line timing and data may not match the AusSportsBetting opener, so its edge over the open isn't
verified as free of lookahead.

**Prospective freeze:** challenger forecasts for 2026 are frozen in `artifacts/phase13/prospective/`. Only 1 game had an
archived DraftKings opener at freeze time, and because κ ≈ 0, tracking adds little.

## What is reducible
1. **QB changes and late news are the clearest target.** They triple the champion's error, and the market moves on them.
   A pre-registered QB-change component should be judged on line-move prediction, which needs about 618 games, not on season
   log loss.
2. **The other half of the gap is modelling against the opener.** Score-based ratings, even dynamic ones with market priors,
   don't close it. More feature or hyperparameter search is unlikely to be detectable: a 0.005 gain needs about 35 seasons.
3. **For decisions, start from the market.** Use the opener early in the week and the close when available.
4. **Simulator:** points spread is slightly too wide, and yards run about 4% high in a neutral game. It is fine for player
   distributions but not for win probability.
