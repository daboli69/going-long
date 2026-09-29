# Week 4 role and learning review — September 29, 2026

## Subsequent policy override: 80/20

At the owner's explicit request, live player-prop and team game-line baseline
distributions now give current-season observations 80% total weight and older
observations 20%, when both exist. This supersedes the unpromoted decision below.
The same policy applies to TD count fits. No current observations means an
explicit historical fallback; no historical observations means current-only.
Existing minimum samples, verified QB starts and freshness checks remain.
Fewer than five current appearances carries low sample confidence, regardless
of the assigned 80% weight. This is a product policy, not a validated accuracy
improvement. Role/coverage evidence and market prices are not artificially
reweighted. Game-model replay uses only results available before each kickoff.
Scheduled season diagnostics now compare this exact 80/20 policy to the former
equal-appearance baseline. Existing frozen predictions remain unchanged.

The current snapshot accounts for 48/48 completed NFL games. Current role,
injury and defensive-memory evidence is already separate from the historical
outcome distribution. Three weeks alone do not validate replacing all priors.

## Changes shipped

- QB full-game fits now use schedule-verified starts, not relief appearances.
  Starts outside the two-year lookback are not revived as current workloads.
  The existing minimum-five-game and stale-profile checks remain in force.
- The expected available depth-chart QB supplies receiver tendency evidence;
  cumulative team passing volume cannot select a different QB. Unknown depth
  cannot produce an alphabetical starter. Current official roster additions
  are included even if absent from the secondary roster feed.
- Each QB retains his own current-season counts and a separately labeled older
  charted target-position profile, where available. Old tendencies are research
  context only: different coaches, teammates and small samples limit transfer.
  Missing charting is unknown, never automatically non-blitz.
- Recommendation evidence exposes season sample weights and verified-start
  counts. New tracker observations freeze those fields; past records are not
  overwritten. The scheduled pipeline stores `betting.season_review` in history.
- Today minimum odds and parlay range inputs accept signed exact prices such
  as -120 on mobile; no unsigned-only keyboard or 25/50-point step restriction.

## Current-season candidate: not promoted

One candidate capped history at two game-equivalents for volume and six for TD
counts. Three current games would give 60% current weight for volume. A strict
prior-appearance replay of the available trailing archives yielded:

| Market | Observations | Existing RMSE | Candidate RMSE |
|---|---:|---:|---:|
| Pass yards | 108 | 85.210 | 86.364 |
| Rush yards | 368 | 23.419 | 23.256 |
| Receiving yards | 936 | 23.989 | 24.031 |
| Receptions | 936 | 1.738 | 1.739 |
| Pass TDs | 108 | 1.188 | 1.189 |
| Any TD counts | 1,044 | 0.4954 | 0.4947 |

These small and inconsistent changes do not justify a blanket promotion.
The live outcome fit retains equal appearance weights while current role
evidence and the QB start correction operate separately. The candidate remains
reproducible, not silently enabled. The replay is an early-season development
diagnostic, not an independent profitability claim or validation of the new QB
filter. Prospective role-matched outcomes are required for that change.

## Results-driven evaluation

The scheduled review joins frozen pregame predictions to automatic published
settlements, keeps the first exact contract across tracking groups/books, and
reports Brier error, average predicted probability, observed win rate and event
count by market. Push/void outcomes are excluded from the binary diagnostic;
win probabilities are conditioned on no push. Multiple lines in a game remain
correlated, not independent proof. No individual win or loss retunes a weight.

The current diagnostic shows overprediction in several families. Passing yards,
for example, averaged 57.3% predicted versus 48.2% observed across 197 contracts.
This identifies a calibration research priority, not a license to subtract nine
percentage points from every future passing-yard probability. Future calibration
must train on earlier games and be evaluated on later, untouched games.
