# NBA combined-probability calibration — 2026-10-23

Frozen before this experiment. Separate from the initial protocol: do not modify its frozen configuration, historical results, operational bundle or saved forecasts. $0 spend, local CPU at low priority, no network, no NFL changes, no promotion. Owner: Codex. User requested a useful bounded run rather than spending compute past diminishing returns.

## Hypothesis and fixed budget

H1: chronological post-calibration of the already frozen stacked winner probability improves probability error versus that same probability without post-calibration. Exactly six candidates: sigmoid/Platt logistic calibration on log-odds (C1,max_iter1000), or isotonic regression (out_of_bounds=clip), each using the most recent300,600or1200 available earlier games. No base-model refits or hyperparameter search. No seeds/repeated fits selected for better results. Maximum20minutes; finish fewer configurations if necessary, checkpoint each completed candidate, never expand the grid. Stop when the grid finishes even if time remains. Resume only identical input/config hashes. Log failures and skip, never silently replace a member or weaken tests.

## Data and chronology

Use saved six-model stacked out-of-fold predictions from ending-seasons2023,2024,2025 only. No source refresh and no2026confirmation files/outcomes.2023 is earlier calibration history. Evaluate2024and2025 discovery (2,460 games expected); these seasons were already examined during initial development, so this is exploratory reuse of development data, not a fresh independent validation.

Refit the post-calibrator at each UTC calendar-month boundary, with only outcomes available strictly before that boundary under tipoff+24h. Each evaluated game receives a probability before its own decision time. At least the full specified window is required; otherwise fail the candidate rather than score a different sample. Rolling windows count games, not calendar weeks. Target predictions remain out of sample with respect to their post-calibrator. Guard with future-outcome canary tests and explicit cutoff assertions. Different earlier-season base models generated the saved OOF probabilities; drift across those models is a limitation.

## Metrics, selection and stopping

Same game IDs for every candidate/control. Log loss primary; Brier, accuracy and fixed0.1 reliability bins secondary. Paired whole-game bootstrap2,000draws, seed20261023; Bonferroni correction across six candidates gives familywise95%intervals for log-loss and separately Brier comparisons. This does not correct initial-development selection or make reused discovery independent. Report mean effects and per-season direction.

Exploratory acceptance requires >=1% pooled log-loss reduction, corrected log-loss CI strictly below zero, improvement in both discovery seasons, and mean Brier no worse. Otherwise reject for adoption. Select the lowest pooled log loss among accepted candidates, alphabetical tie-break; if none pass retain the existing forecast method. Even a pass is shadow-only, pending a genuinely new prospective test. Do not re-score or tune against the already-spent2025–26 confirmation season; no new independent historical holdout is claimed.2026–27 outcomes are not used to choose candidates.

## Deliverable

One saved report with actual trial count, elapsed time, calibration-fit count, per-season scores, corrected intervals, reliability bins, failures and decision. Expose the report and repeatable bounded command through the existing local app/launcher, without adding another BAT file. Repeating the command returns completed cached output rather than searching again. No simulated possession, spread/total or player-prop model exists in this winners-only version: repeated Bernoulli samples would add numerical noise to a directly computed win probability. Extra simulation count cannot repair missing injuries/lineups, biased inputs or calibration.
