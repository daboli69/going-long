# Phase 6.1: what the 10-hour research job learned (job lr20261017_025949)

- **Job:** stopped at 9.3 h of a 10 h budget, 7,141 trials (1,107–1,254 per family), 6 threads.
- **Evidence used:** the saved Optuna studies, trial history and the job's one validation look (#4,
  level 0.0125). Nothing was re-optimised.
- **How selections were made** (`python -m lab.analyze_longrun lr20261017_025949`): development
  seasons only. 2023–2025 numbers below come from the job's existing look and are labelled.

## 1. Best configuration per model (development walk-forward 2019–2022)
| Model | Best dev log loss (champion version) | Key settings | Feature groups (count) |
|---|---|---|---|
| Logistic Regression | 0.6288 (0.6358) | L2, C = 0.0042, top-40 filter | 7: ratings, recent form, offense-vs-defense, injuries, PFR pressure, participation personnel, Phase 5 player model |
| XGBoost | 0.6306 (0.6328) | 590 depth-1 trees, lr 0.008, gamma 3.3, top-20, Platt | 11 incl. NGS, PFR, roster, player model + continuity |
| Decision Tree | 0.6422 (0.6560) | depth 7, min leaf 79, entropy, top-20, Platt | 10 incl. NGS, schedule strength, player model + continuity |
| Random Forest | 0.6273 (0.6340) | 500 trees, depth 13, leaf 11, max_features 0.05, top-80 | 11 incl. player model + continuity, FTN |
| MLP | 0.6250 (0.6382) | 1 hidden layer of 11, dropout 0.37, lr 0.00018, Platt | 7: ratings, recent form, QB, offense-vs-defense, personnel, schedule, player model |
| Single-layer NN | 0.6243 (0.6367) | weight decay 0.015, lr 0.00015, top-40, Platt | 10 incl. context, Phase 3 travel/coaching, PFR, roster, FTN, player model |

**Job's validation look (2023–24; 2025 diagnostic) vs each family's champion version:**

| Model | Δ 2023–24 | Δ 2025 |
|---|---|---|
| Logistic Regression | +0.0014 | +0.0068 |
| XGBoost | +0.0007 | +0.0091 |
| Decision Tree | **−0.0082** (CI −0.020, +0.004; Holm p 0.60) | +0.0014 |
| Random Forest | −0.0017 | +0.0059 |
| MLP | −0.0014 | +0.0113 |
| Single-layer NN | **−0.0046** (CI −0.016, +0.007; Holm 1.0) | +0.0066 |

None passed. **Every family's best configuration was worse than its champion version on 2025.**

## 2. Gain or noise? (development-only check)
Each family's best trial was picked on 2019–21, then checked on 2022, which played no part in the pick:

| Model | Gain 2019–21 (picked) | Gain 2022 (unseen) |
|---|---|---|
| Logistic Regression | +0.0122 | −0.0131 |
| XGBoost | +0.0051 | −0.0111 |
| Decision Tree | +0.0199 | −0.0047 |
| MLP | +0.0184 | −0.0025 |
| Random Forest | +0.0083 | +0.0013 |
| Single-layer NN | +0.0152 | +0.0029 |

Four of six reverse. Random Forest and Single-layer NN keep about 15–20% of their gain. The validation
improvements for the Single-layer NN (−0.0046) and Decision Tree (−0.0082) are within noise
(CIs include 0), and both were worse on 2025. **This is predominantly selection noise.**

## 3. Ensemble replacement (development-only)
- **Setup:** out-of-fold dev predictions for the champion and overnight version of every family; all
  64 keep/replace combinations × 2 weightings (equal, walk-forward skill weights), ranked on 2019–21
  and checked on 2022.
- **All six replaced:** +0.0126 on 2019–21 → −0.0053 on 2022. The best combination (five replaced)
  went +0.0127 → −0.0026; the best single swap (MLP) +0.0042 → −0.0002.
- **Across the 128 combinations:** the 2019–21 gain and 2022 gain correlate **−0.45**. Only 16% of
  combinations that improved 2019–21 also improved 2022.
- **Diversity:** effective independent models are 1.22 for the champion versions and **1.16** for the
  overnight versions. Each overnight model correlates 0.75–0.97 with its champion version. The improved
  models converged on similar inputs and add no new independent information.
- **Pre-declared rule** (improve 2019–21 and hold on 2022, evaluated for the best single swap, best
  combination and all six): **no candidate qualified, so no new challenger was registered.** The
  considered candidates and their reasons are stored in the challenger registry.
- **Margin models** were not part of the overnight search, so they are unchanged.

## 4. What it learned about football information
- **Present in essentially all strong trials of every model:** opponent-adjusted ratings, recent form
  (last 3/5), the Phase 5 player model, and participation personnel & pressure.
  - **Most enriched** relative to all trials: personnel & pressure (+0.30), PFR pressure/contact (+0.15),
    schedule strength (+0.12).
  - These shares partly reflect the search concentrating on what scored well, so they are not
    independent evidence. Given section 2, they show what fits 2019–21, not what generalises.
- **Rarely chosen:** "Efficiency differences (blended season)" (0% of top trials; the champion's core
  group), volume/pace, NGS, Phase 3 travel/coaching, advanced matchups.
- **Phase 5 player model** appeared in 100% of top trials, but none of those configurations beat the
  champion out of sample. That matches Phase 5's own result (gains in 2019–24, losses in 2025).
- **Feature-selection stability:** the selected groups differed widely between families with similar
  scores (7–11 groups, different mixes). There is no single stable combination.

## 5. Diminishing returns
Each family was within about 0.001 of its final development best by trial 300 (Logistic Regression's
best came at trial 244 of 1,146). Improvements after trial 600 were ≤ 0.0007, and section 2 shows that
even large development gains do not transfer. **Further broad optimisation is very unlikely to help.**

## 6. Next research priority
Fresh, independent evidence rather than more searching of 2016–2025:
1. Let the Phase 6 prospective archive accumulate. That decides the Phase 5 player-continuity hypothesis
   and the 10 frozen upset hypotheses.
2. Improve the inputs the models lack: 2026 participation data (stale player ratings), timely final
   injury reports, and a pregame market line as a benchmark.
3. Treat any future long-run job as exploratory. Each validation look raises the bar (now 0.05/5 for the
   next one).

## Tooling added
- `lab/analyze_longrun.py` covers per-job analysis: top trials, group frequency and enrichment,
  hyperparameters, the selection-noise check, improvement curves, prediction and error correlations,
  version metrics and the ensemble combinations.
- The Long-Run Research page shows all of it in plain language ("Analyze this job").
- Prospective challengers are evaluated with Holm correction across all tracked challengers. "Supported"
  requires 128+ games and is never an automatic promotion.
- The registry keeps an audit trail of considered-but-rejected candidates.
