# Phase 8: independent football specialists and ensemble diversity

**Branch:** `codex/nfl-ensemble-lab`. The pre-registration (`docs/PHASE8_PREREGISTRATION.md`) was committed and pushed as b35f618
at 17:27 UTC, **before any specialist existed**. Every specialist and comparison below is exactly as pre-registered. Deviations
are listed at the end.

**Result in one line:** six specialists were built and evaluated. None adds reliable information beyond the champion, no
combination met the standard, and **no new challenger was registered.** The champion, the six models, both challengers and
all archives are unchanged.

## 1. Live scheduler isolation
This is handled in a separate linked session ("Run NFL lab scheduler from a pinned release copy"). It is building
`lab/release.py`, `scripts\launchers\release_lab.bat` and `docs/RELEASES.md`: a pinned release copy with its own cache slot, tests, pre-warm and
rollback.
- **Current state:** the real Windows task still points at the development checkout.
- **Why it isn't switched:** a cross-session message relaying approval to switch it was blocked by the permission system, so
  the switch needs Travis's approval in that session.
- **Precautions here:** this phase only added new files (`lab/specialists/`, tests, docs) plus one dashboard section. None of
  them is imported by the scheduler.

## 2. Diversity baseline (frozen walk-forward predictions, 2018–2026; `lab/specialists/baseline.py`)
| Measure | Value |
|---|---|
| Effective independent models: predictions / errors | **1.21 / 1.02** of 6 |
| Effective models after removing team strength (rating difference) | 1.75 |
| Partial correlations given rating | 0.39–0.96; decision tree least similar, logistic regression and single-layer net 0.955 |
| Games where all six were wrong / at least five wrong | 537 / 690 of 2,298 |
| Confident unanimous calls (all six >70% one way) | 250 games, wrong 20% vs about 19% implied: calibrated, not overconfident |
| Disagreement level by favourite band or game type | flat (std ≈ 0.05 everywhere) |
| Disagreement beyond the ensemble probability (development, likelihood-ratio test) | p = 0.024. Positive interaction: the ensemble is slightly *under*-confident when models disagree. Small effect, one test, not acted on |

**Development metrics (2018–22, 1,365 games):**

| | Log loss | Brier | Accuracy | Margin MAE |
|---|---|---|---|---|
| Weighted ensemble | 0.6282 | 0.2191 | 64.6% | 10.15 |
| Individual models | 0.630–0.652 | | | |

**Conclusion:** the six models are different algorithms reading the same 85 features. Their variety is almost entirely
in how they shape the rating signal, not in different information.

## 3–4. The six specialists (`lab/specialists/core.py`)
Shared rules for every specialist:
- **Walk-forward:** for each target season s, fitted on seasons before s, with imputation and scaling fitted inside the window.
- **Calibration:** Platt scaling on its own earlier out-of-fold predictions.
- **Abstention** when its inputs are missing.
- **Rating guard:** a structural check rejects any rating column, verified to be used 0 times across 150 inputs.
- **Explanations:** per-game signals are recorded.

| Specialist | Unique information | Inputs | Mechanism |
|---|---|---|---|
| A availability | who is expected to play | 69: lineup counts, starters out/confirmed, uncertainty, OL continuity, QB v1/v2 flags, verified injury counts | L2 logistic; abstains without verified reports (22%: 2025 and early 2026) |
| B matchup | unit-vs-unit interactions | 24: standardised sums **and products** of offence vs opposing defence (pass, rush, explosive, sack, third down, red zone, PFR pressure and run blocking, NGS separation and CPOE) | gradient-boosted trees, depth 3 |
| C form/change | change not yet in season ratings | 19: last-3 minus season-blend shifts, snap-distribution change, QB, coach and OL changes | L2 logistic |
| D environment | rest, travel, roof, division | 17 (no weather: historical forecasts aren't recoverable, and actual weather is post hoc) | L2 logistic |
| E drive simulation | possessions × drive outcomes | 12 as-of drive rates from play-by-play (TD/FG per drive, drives per game, offence and defence) | log5 opponent adjustment and home edge; Monte Carlo of 4,000 games giving P(win), margin and total distributions |
| F situational | champion miscalibration in situations | 9: champion out-of-fold logit interacted with favourite band, early season, QB uncertainty, disruption, extreme matchup | L2 logistic correction; available from 2019 |

## 5. Standalone evaluation (`artifacts/phase8/standalone.csv`)
Log loss, with incremental information given the champion probability tested by a likelihood-ratio test:

| | Development 2018–22 | 2023–25 (exposed) | Correlation with champion (dev) | Incremental p (dev / exposed) |
|---|---|---|---|---|
| Champion | 0.628 | 0.633 | n/a | n/a |
| Home-win-rate baseline | 0.691 | 0.688 | n/a | n/a |
| A availability | 0.691 | 0.683 | 0.20 | 0.43 / 0.43 |
| B matchup | 0.677 | 0.656 | 0.61 | 0.26 / 0.69 |
| C form/change | 0.694 | 0.684 | 0.08 | 0.39 / 0.62 |
| D environment | 0.694 | 0.688 | 0.10 | 0.49 / 0.78 |
| E drive simulation | 0.646 | 0.640 | 0.87 | 0.88 / 0.18 |
| F situational | 0.642 | 0.635 | 0.94 | 0.75 / 0.44 |

- **Different predictions:** A, C and D are genuinely different (correlation 0.08–0.27) but carry **no** predictive information
  (they sit at the home-rate baseline).
- **E** is the only standalone forecaster of real quality: 0.646 log loss, 62.5% accuracy, 10.5-point margin MAE against the
  champion's 10.15. But it correlates 0.87 with the champion, so it mostly re-derives team strength from drives.
- **F** makes the champion slightly *worse*: its situational corrections don't generalise.
- **Error correlations** (0.94–0.99) are reported in the CSV, but for weak models they are dominated by the outcome itself. The
  incremental test is the meaningful measure of complementary information.

## 6. Combination experiment: the pre-registered 8 comparisons (`artifacts/phase8/experiment.csv`)
**Setup:**
- **Baseline R:** the recalibrated champion.
- **S_k:** the champion plus specialist k (logistic regression, L2 C = 1).
- **SELECTED:** the specialists whose S_k gained on development, which turned out to be only C.
- **STACK:** all six specialists (C = 0.3).

Gain = log loss of R minus log loss of the candidate. Development is 1,100 games (2019–22).

| Comparison | Dev gain [95% CI] | Holm p | 2023–25 check gain | Qualifies |
|---|---|---|---|---|
| S_A | −0.0013 [−0.0030, +0.0003] | 1.0 | −0.0013 | no |
| S_B | −0.0003 [−0.0014, +0.0008] | 1.0 | −0.0003 | no |
| S_C | +0.0004 [−0.0005, +0.0014] | 1.0 | −0.0002 | no |
| S_D | −0.0015 [−0.0024, −0.0006] | 1.0 | +0.0001 | no |
| S_E | −0.0020 [−0.0042, +0.0002] | 1.0 | −0.0002 | no |
| S_F | −0.0021 [−0.0064, +0.0023] | 1.0 | −0.0003 | no |
| SELECTED (C) | +0.0004 [−0.0005, +0.0014] | 1.0 | −0.0002 | no |
| STACK (all) | **−0.0066** [−0.0116, −0.0015] | 1.0 | −0.0001 | no |

- **Calibration control:** walk-forward recalibration (R) is itself *worse* than the raw champion in development (0.6354 vs 0.6322),
  because it is fitted on small early samples. So no specialist beats the raw champion either. Small "gains" here would have been
  calibration artifacts.
- **Shared-error games:** every combination gains on the games where all six models were wrong (+0.005 to +0.010) and loses on
  the rest. That is the signature of shrinking toward 50%, not of correcting shared mistakes. None improves overall.
- **Stability:** gains by season swing between −0.019 and +0.0035 with no consistent sign (`experiment_by_season.csv`).
- **Brier score** moves the same way as log loss in every comparison.

## 7. Overfitting controls
- The hypotheses, inputs, metrics and the 8 comparisons were fixed before any result.
- Development and check windows were separated chronologically, and 2023–25 is labelled research-exposed.
- Holm correction covers m = 8. The SELECTED combination is acknowledged to be optimistically selected on development data;
  it failed anyway.
- No specialist was tuned to 2023–25.
- Every attempt, including failures, is recorded in the challenger registry under `considered` (`phase8_specialists`).

## 9. Specialist debate (dashboard)
On the Model Debate page, a collapsed "Specialist debate (experimental)" section shows, for each game:
- each specialist's probability, or its abstention;
- its main signals (coefficient × standardised value, or the most unusual inputs for trees, explicitly labelled as associations);
- its historical correlation with the champion, and its incremental-information p-value;
- the drive simulation's margin and total distributions (10th–90th percentiles).

It is kept apart from official and tracked forecasts. Specialist F abstains for upcoming games, because it needs the champion's
out-of-fold probability.

## 10–11. Challenger rules and operations
- **Challengers:** no candidate qualified, so nothing was registered. The registry still tracks exactly the champion plus the
  Phase 5 and Phase 7 challengers.
- **Runtime:** specialist training runs offline in about 17 s and never in the live path. Outputs are written only to
  `artifacts/phase8/`.

## Answers
1. **Is the live scheduler isolated?** Not yet. A pinned release is being built in a linked session, but the real task still
   runs the development checkout and the switch needs Travis's approval (section 1). This phase avoided editing anything the
   scheduler imports.
2. **How independent are the six models?** Barely: about 1.2 effective models for predictions and 1.0 for errors.
3. **Which specialists were implemented?** All six: A–F.
4. **What unique information does each use?** See the table in section 3–4.
5. **Which specialists produce meaningfully different predictions?** A, C and D (correlation 0.08–0.27), B partly (0.6–0.8).
   E and F are near-duplicates (0.87–0.97).
6. **Which make different errors?** By the incremental test, none carries complementary information. Raw error correlations are
   dominated by the outcome.
7. **Which are useful despite lower standalone accuracy?** None demonstrated.
8. **Does any specialist beat the recalibrated champion on log loss or Brier score?** No. The only positive point estimate
   (C, +0.0004) has a CI that includes 0 and reverses on 2023–25.
9. **Which combinations improve the ensemble?** None. The constrained stack is significantly worse.
10. **How stable are the results across seasons?** There is no consistent sign by season.
11. **What data limitations prevent stronger conclusions?**
    - 2025 has no verified injury timing, so A abstains.
    - 2026 has no play participation.
    - There are no historical weather forecasts.
    - The historical seasons are design-exposed or research-exposed.
    - About 270 games per season limit power: a true gain of 0.001 log loss is undetectable with this sample.
12. **Was a new challenger justified?** No.
13. **Are the original champion, challengers and archives unchanged?** Yes. See the test, leakage and integrity results in the
    commit message.
14. **What should Phase 8.1 investigate?**
    - Information the market has and the models don't. The closing market was right in 15% of the shared misses, and the line is
      available pregame; it should be a timestamp-verified feature only if historical pregame lines can be recovered.
    - Prospective-only evaluation of E's margin and total distributions as a separate scoring product.
    - Whether *any* information source can move log loss by more than about 0.003. That's the minimum detectable effect here.

## Deviations from the pre-registration
- Per-game signal strings were added after the first run. Predictions were unchanged.
- A missing forbidden-column guard in D was found by a new test and fixed structurally. Specialist predictions were
  bit-identical before and after, because no rating column was ever present among D's inputs.
- Nothing else deviated.
