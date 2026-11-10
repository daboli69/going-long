# Pre-registration: two questions from the 2026-11-09 audit

Registered 2026-11-09, before any Week 10 game. Source: `reports/model_audit/AUDIT.md` (weeks 6 to 9, 55 games). Both questions came from searching 72 slices, so they start as hypotheses. This document registers a confirmation test only. It changes no model and promotes nothing.

## Data

Only games whose evaluation row in `reports/tracker/evaluations.csv` has `origin = live` (Week 10 onward), with the latest snapshot written before kickoff. Weeks 6 to 9 are excluded because they produced the hypotheses. One row per game. Outcome y: 1 home win, 0 away win, 0.5 tie.

## Questions

- **Q1, home overrating.** Mean of (p_champion minus y) over all live games is greater than 0.
- **Q2, away favored by 3 to 7.** Same statistic, restricted to games with market spread_line in the interval (-7, -3] (the audit's bin edges, unchanged).

## Test

One-sided t-test of the mean error against 0 for each question, Holm-adjusted across the two, alpha 0.05. Also report a 95% bootstrap interval over games. One look only, at the later of: the end of Week 18, or 40 live games in the Q2 bin. No peeking before then, and no change to the bin edges, threshold or statistic.

## Outcomes

- Confirmed: the question becomes a candidate for a Champion/Challenger test in MODEL_RESEARCH.md (a correction fitted on weeks 6 to 9 only, then scored on the live games not used to fit it). It still needs to beat the champion on Brier and log loss against the market.
- Not confirmed: the question is closed and reported as noise.
- Either way, the champion stays unchanged until a challenger passes that gate.

## Tracker

Rule `ml_edge_v1` stays frozen. Its live rows and these two questions are separate: the rule asks whether betting the disagreements profits, these ask whether the probabilities are biased.
