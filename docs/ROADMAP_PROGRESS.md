# GOING roadmap progress

The implementation follows `PRODUCT_AUDIT_2026-09-14.md`. This is a progress ledger, not a claim that the roadmap is complete.

## Released

- **P0.1, football trust presentation — `2bab955`:** raw historical probabilities remain available for research; unusually large model-price disagreement receives a review label; unvalidated historical estimates no longer display suggested stakes. Signals uses the same disagreement rule. First TD research carries a trust label. Vercel reported success and the live page contained the policy. Forty-eight targeted JavaScript tests and the production build passed. Cross-sport trust-policy consolidation is still pending.
- **P0.2, baseball outcome retry — hr-board `cdee62e`:** final games require both team boxscores; missing player statistics remain retryable. Confirmed bench nonparticipation needs corroborating roster/batter data and reconciled team appearances. Older grader records are revisited. The live GOING baseball snapshot serves grader version 2. Frozen-record and grading tests passed. Full football/period/parlay settlement coverage is still pending.

## Additional releases

- **P0.3, football game-history time boundary:** results enter team histories and residual estimates only after their publication timestamp, or a documented 12-hour fallback after kickoff where no timestamp exists. Equal-cutoff results are excluded. Team histories remain ordered by game time when a result arrives late. Tests cover distinct teams with overlapping kickoffs and verify that unavailable future results cannot change the later forecast. This fallback is not proof of exact historical publication times, particularly for suspended or exceptionally delayed games.

- **Requested interruption, King of the Endzone — `f88733b`:** confirmed DET–BUF offer, complete 31-candidate research field, shared returner/D/ST and tied winners, historical touchdown-distance competition, immutable first pregame forecast and pending-result grading. Five Python tests, UI tests and production build passed. Vercel reported success; live rankings and expandable evidence verified. Individual sportsbook selections and game-day roles are not independently confirmed; estimates remain unvalidated.

## Current increment

- **P0.4, odds request deadlines and saved-price recovery:** provider requests share a 40-second budget, with an 18-second per-request limit. Failed refreshes retain the last successful in-memory response for up to 24 hours, explicitly labeled as saved and preserving quote timestamps. A 15-minute failure backoff prevents repeated failed calls. This cache is per running server instance, not durable account-wide storage. No polling frequency increase is introduced.

## Remaining sequence

Complete P0 trust consistency, recording/settlement coverage, replay input availability, and odds deadlines/freshness. Then implement the full opportunity/evidence contract, unified discovery/navigation, graphical Results, Parlay Lab compatibility, and account-wide cost controls. Model additions and controlled learning follow prospective validation. Commercial data rights, account-level operational checks and subscription scope remain launch prerequisites.

Every independently released increment must include focused tests, a push, and verification of the actual delivery path. A Vercel release does not by itself restart the PC scanner.
