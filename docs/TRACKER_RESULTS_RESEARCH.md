# Public tracker results audit and future calibration experiment

Manual review on October 4, 2026. Public NFL/NCAA ledger only. Champion unchanged; no fitting, promotion, or registered Today-v1/ABBEYS holdout inspection. Personal bets, browser Score observations and DFS cohorts are outside this analysis.

## Reproduce

`node research/tracker-results/audit.cjs` reads only the committed public tracker (the segmented `data/public_tracker/` store, rehydrated so its hash equals the former single file's; see docs/TRACKER_STORE.md) and `data/results.json`, emits their SHA-256 hashes, and uses the tracker generation timestamp as its explicit as-of time. An optional ISO timestamp argument changes that cutoff. `node --test tests/tracker-results-audit.test.cjs` verifies settlement identity, midnight dates, refunds, missing participation, duplicates and leakage exclusions.

Numbers below describe the **02:05 ET October 5 manual-session snapshot**, refreshed using free public final results: tracker SHA-256 `90a681425907492b7c271dfb688b35fcbbd5c1fa65ed83046943c6e2d1d8e5c6`; results SHA-256 `d1d02faed4b430ab553e96fbc6ae644d9ace6afc33884a3ade930913b0982788`. The later refresh adds 14 Sunday-night game-market settlements and six previously unmatched Hawai‘i records. Player appearance logs can still lag; these are not complete player-market totals. No predictions were added or rewritten.

## Coverage and data quality

- First actual pregame capture: September 20, 2026 at 10:07 AM Eastern. The season's earlier results are available, but four weeks of prospective model recommendations are not. NFL capture includes September 20 onward; NCAA game dates begin September 24. Earlier recommendations cannot be backfilled from winners.
- 5,352 prediction records reduce to 4,984 first-captured equivalent contracts within model cohort/tracking group. There are 368 duplicate-equivalent records caused by vendor kickoff drift, including the Hawai‘i midnight boundary. All records remain preserved. Books, related markets and repeated model cohorts are not independent trials.
- October 4 NFL: 14 recorded games, 14 published finals, all 14 finals have at least one frozen prediction. Missing player participation remains pending, never zero/loss. October 3 NCAA: 46 recorded games out of 51 published finals. Houston/UCF, Clemson/Miami, North Dakota State/Wyoming, Massachusetts/Eastern Michigan and South Alabama/UL Monroe have no frozen prediction. Their finals are visible as untracked coverage, not retroactive bets.
- Exclusions: 315 unique selections lack usable player results; no completed matchup remains unmatched. Before the Sunday-night final, independent public-history inspection found 33 missing player/date pairs on completed games: every profile ID existed, but none had a matching appearance date. Sunday-night props now await logs as well. This does not establish an inactive/void or permit a zero fill. No duplicate record IDs, orphan settlements, future-input timestamps, capture-after-official-kickoff failures or inconsistent grades were detected by this bounded check. Hashes and timestamps cannot prove every underlying historical input's event-time availability.
- All 4,990 selections carry source/input hashes. Only 793 carry a frozen two-way reference; 4,191 lack it. Best Value has **zero** observations, so no performance assertion is possible.
- Sample confidence is frozen as `low` for 843 player selections and absent for 4,141 selections; readiness labels are not frozen. Historical hit rate cannot reconstruct performance by today's confidence label. Game evidence and player sample confidence are different constructs.

## Hypothetical $100 results

Each selection risks $100: a win earns `$100 × (decimal odds − 1)`, a loss loses $100, and refund returns the stake with $0 profit. ROI divides profit by all settled turnover, including refunded stakes. This represents research performance at saved prices, not actual bets, available limits or achievable portfolio returns. Correlated markets, different cohorts and tracking groups overlap; never sum the following rows.

| Cohort / Model-screened group | Settled | Games | Profit | ROI | Conditional forecast / observed win rate | Brier |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| NFL legacy | 1,517 | 46 | −$5,463.09 | −3.60% | 57.66% / 48.84% | 0.2441 |
| NFL role-aware before 80/20 | 70 | 14 | +$223.93 | +3.20% | 56.27% / 51.43% | 0.2439 |
| NFL current 80/20 | 624 | 15 | −$1,268.83 | −2.03% | 59.82% / 49.11% | 0.2595 |
| NCAA legacy | 251 | 94 | −$2,956.26 | −11.78% | 59.48% / 44.90% | 0.2749 |
| NCAA current 80/20 | 152 | 45 | −$1,433.30 | −9.43% | 58.68% / 46.67% | 0.2667 |

October 4 NFL across recorded model cohorts: 767 settled selections, −$434.18, −0.57% ROI. October 3 NCAA: 222 settled selections, −$2,753.67, −12.40% ROI. These mixed-cohort daily descriptions do not validate the current policy. They will change when additional participation logs appear.

**What merits more investigation:** NFL legacy receptions (+3.11%, 303 selections/41 games) and spreads (+4.14%, 46/24) have positive descriptive ROI. Current-cohort NFL spreads (+44.22%, 24/13), ATD (+55.65%, 42/14) and NCAA moneyline (+24.39%, 20/20) also show positive samples. Small groups, longshot prices and multiple comparisons make these unsuitable for a confidence upgrade; current NFL ATD still overforecasts (35.04% probability versus 30.95% wins).

**What is failing in the observed sample:** Current NFL passing yards (−25.67%, 61/13), rushing yards (−10.51%, 114/14) and receiving yards (−7.26%, 213/14), and NCAA totals (−19.83%, 69/35) are priority calibration/usage hypotheses. Current model-screened forecasts exceed observed win rates by roughly 11–12 percentage points overall. NFL has only 15 current-policy game clusters; thousands of correlated contracts do not supply thousands of independent examples.

On identical paired current-policy selections with frozen two-way prices, NFL Champion Brier is 0.2644 versus reference 0.2475 (435 contracts/15 games). The game-balanced Champion-minus-reference difference is +0.0143, descriptive normal 95% interval [−0.0113, +0.0399]. NCAA is 0.2739 versus 0.2526 (106/40), game-balanced difference +0.0237 [−0.0029, +0.0502]. Lower Brier is better. These are exploratory intervals, not adjusted for repeated teams/weeks or multiple subgroup searches. The reference is the recorded same-book devigged pair, not a guaranteed closing market. Price movement is not guaranteed CLV.

## Preregistration: tracker-calibration-v1 (future shadow only)

**Hypothesis:** For current-80-20 recommendations, a fixed convex mixture of Champion and contemporaneous same-book devigged probability reduces overconfidence and improves proper scoring. Existing evidence motivates this future test but is not its holdout. This creates a new research experiment, without modifying existing experiments or live recommendations.

**Locked definition:** On each eligible first-captured contract let `qC = pChampion / (1 − push)` and `qM = reference.win / (reference.win + reference.loss)`. Challenger conditional probability is `qH = 0.5 × qC + 0.5 × qM`; unconditional win probability is `(1 − push) × qH`. Coefficient 0.5 is fixed without fitting. League/market families remain separate; no pooling across model revisions, Score/DFS or other experiments. Primary families are NFL passing/rushing/receiving yards and NCAA totals. NFL receptions/spreads and NCAA spreads/moneyline are secondary descriptive families only.

**Cutoffs and splits (Eastern):** October 4 and all observations before October 6, 00:00 are development diagnostics. Shadow collection begins October 6, 00:00; October 6–November 2 is the preregistered chronological development/reproducibility period. November 3, 00:00–November 16, 23:59:59 is the untouched prospective holdout. Registered evaluation is November 17 at 12:00, only for officially settled eligible entries. No outcome aggregate from the holdout is read before evaluation. No missed-slot replay, opportunistic extension, refitting or new coefficients under this version. This document alone does not activate another collector or automation.

**Eligibility:** current-80-20 cohort and best_model group, full-game contract, strictly pregame capture and inputs, finite captured decimal odds >1, quote observed no more than five minutes before capture, exact same-book/line two-way frozen reference, unique normalized game/date/player/market/side/line/rules, unambiguous public final and participating player where applicable. Push/void entries remain in turnover/coverage but are excluded from conditional binary scoring. Missing results stay missing. Record exclusions and paired eligibility/settlement shares. Any model/provenance change creates a separate version/cohort, never a silent combination.

**Evaluation and acceptance:** Compare identical holdout samples for Champion, Challenger and frozen reference. A primary family needs at least 200 paired decisive contracts, 30 distinct games, two distinct holdout slate weeks, and ≥90% settlement coverage among eligible completed contracts. Report paired Brier/log loss, reliability bins, game-balanced metrics and 10,000 deterministic game-cluster bootstrap paired intervals (seed 20261004). For each of four primary families use a 98.75% interval to conservatively account for four comparisons. Accept for further review only if Challenger Brier improves by ≥0.005 versus both Champion and reference, both paired intervals lie below zero, log loss does not worsen by >0.01 versus either, and calibration gap does not worsen. If requirements fail or samples are insufficient, record reject/insufficient; do not relax or extend v1. ROI is secondary descriptive output only; no profitability claim from this sample or uncertain prices.

**Status and labels:** Preregistered proposal; shadow capture/evaluation implementation remains future work. No experiment execution or live probability change in this session. A passing result still requires Travis's model-promotion approval and broader validation. Useful present labels can distinguish readiness, research candidates, unavailable prices and well-documented evidence while preserving honest low sample confidence. Four calendar weeks cannot justify labeling an unvalidated edge as high confidence.
