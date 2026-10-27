# Frozen distribution diagnostic plan

Freeze before new diagnostic values or repair implementation. Scope remains Tuesday regular-season PRA leaders, free data, four rolling seasons per prediction. This is a single-component experiment, not a release or a feature expansion.

## Evidence tracks and calendar

1. **Reused retrospective diagnostic development:** Tuesdays 2025-10-28 through 2025-12-16 inclusive (eight dates), target season ending-year 2026, using only earlier season-to-date plus 2023–2025. Existing inspected archives are reused, never untouched. Acquire the missing 2023 support season without adding out-of-window training data.
2. **Reused retrospective diagnostic assessment:** Tuesdays 2026-01-06 through 2026-03-24 inclusive (twelve dates). Freeze date lists before running comparison; do not tune from assessment outcomes. These dates are later chronologically but are NOT an untouched holdout because their archives were previously inspected. Record no-game, incomplete-box and missing-evidence exclusions for the entire slate, never quietly grade a surviving shortlist.
3. **Genuinely prospective development:** eight Tuesdays 2026-11-03 through 2026-12-22. Actual-time pregame receipts required; future outcomes not accessed now.
4. **Genuinely prospective later evaluation:** Tuesdays 2026-12-29 through 2027-04-06. Do not access outcomes or evaluate early. All-Star/no-regular-game Tuesdays contribute no slate. The remaining season may provide fewer than 20 evaluable dates; report insufficient evidence, not an exception to rare-event validation.

The prospective schedule is a local registration only. It creates no scheduled agent, background process, data publication or betting action. No future prediction is fabricated now.

## Inputs and chronology

Preserve v1 and NBA-winner source/protocol hashes before editing anything. Record raw source URLs, hashes, retrieval/publication times and failures. Prefer raw NBA/ESPN PBP, period lineups, substitutions and official boxes; verify joins with explicit crosswalks. Reconstruct exact stints where supported. Record unmatched IDs, malformed/duplicate events, player/team stat and minute mismatches. Dead-ball/FT sequence fields are evidence, not an invitation to guess event meanings.

Retrospective diagnostics release results only after the existing 36-hour lag, restrict each origin to S−3..S, and disclose that historical source publication times are unknown. A recorded box field may be used only as **explicit postgame conditioning for a mechanism check**, never as pregame availability. An observed-minute ablation is an oracle conditional check and cannot validate minutes forecasts. Missing debut metadata is labeled unknown; do not make up rookie/second-year/established labels.

## Parameter choice and single repair

Retain the existing eight-member season-decay/half-life/prior grid. Choose diagnostic parameters on development dates only, using mean paired-slate PRA CRPS (tie: PRA MAE, then ascending grid tuple); use those same settings for all assessment variants. This choice is explicitly conditional/reused-data research, not a v1 prospective selection receipt. No assessment retuning and no independent parameter optimization for the repair.

Test the v1 implied conditional FGA variance=mean and opposing-team FGA covariance against prior measured residuals. The sole candidate repair is the **team FGA pool distribution**: replace its independent Poisson draw with recency-weighted paired empirical residuals conditional on game possessions, centered using eligible earlier data. Preserve conditional means, integer counts and nonnegativity; report rounding/clipping effects and finite empirical support. Leave FTA, player allocation, minutes, conversion, rebounds, assists and overtime unchanged. Keep v1 as an executable comparator, with an exact-equality test when the repair is disabled. Do not silently patch another discovered issue.

## Comparators and ablations

- Original v1 and the single FGA-pool repair, same field, history, priors, weights, origins and simulation budget.
- Current-season average and minutes-times-production point baselines; compare means on identical supported player/slate cohorts.
- A clearly labeled empirical whole-game block challenger preserving recorded within-game component dependence. Use exact identity support if available; any role transport must be explicit, predeclared, retain complete target field, report unsupported blocks and never claim identity-specific calibration. No missing player outcomes silently become zeros. This is a diagnostic challenger, not another production system.
- Observed-minute conditioning; fixed game pace; fixed opportunity pool diagnostic; fixed conversion probabilities; marginal-preserving independent player shuffling. These isolate assumptions and are not additional simultaneous model repairs. Keep the repaired model separate from ablations.

## Metrics and decision rule

Report per-slate PRA MAE/CRPS, mean/variance, 80% interval coverage, 90th/95th percentile exceedance frequencies, within-player P/R/A correlations, game-level dependence, observed and simulated slate maximum distributions, sole/tied/inclusive leader event Brier/log loss and reliability bins. Report Monte Carlo errors for means/probabilities/tails separately from predictive dispersion and model/parameter uncertainty. Use fixed documented seeds, 1,000 draws for diagnostic selection and 5,000 for assessment, with a second assessment seed for finite-simulation sensitivity. No tuning from that sensitivity run.

Use paired whole-slate 95% bootstrap intervals for original-minus-repaired differences. Preserve slate clustering for component/tail diagnostics and report the number of independent slates. Report verified experience and role-change strata where support exists, otherwise unknown/insufficient. A block bootstrap does not solve rare-leader or long-term serial dependence.

Select the FGA component only if development conditional variance evidence contradicts the original Poisson assumption; otherwise retain the negative result. Call a mechanism improvement supported only if its variance/tail discrepancy improves without a material mean shift. An overall predictive improvement requires genuine later pregame freezes, same-cohort CRPS/Brier evidence and uncertainty excluding no improvement, nonworsening log loss, calibration and subgroup review. Reused postgame-conditioned diagnostics alone require an **inconclusive overall prediction verdict**, even if a component discrepancy improves. Popularity/payout scenarios are preserved and excluded from model selection.
