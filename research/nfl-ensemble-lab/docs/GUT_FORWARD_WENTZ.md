# Forward test: does Wentz outperform Murray on Minnesota's offense?

Written 2026-11-09, before the first game of the window. This registers `docs/GUT_PROTOCOL.md` claim 1 as a prospective test. The frozen record is `reports/gut/forward_ledger.jsonl` (written once by `scripts/gut_forward.py freeze`, with the hash of this file).

## Two hypotheses, fixed now

- **H_gut:** Wentz is the better quarterback on this offense. Prediction for his opponent-adjusted EPA per dropback in the window: **+0.069**, his shrunk same-offense estimate (2025 to 2026, `gut_check.py`).
- **H_equal:** Wentz and Murray are about the same and Minnesota's offense is the story. Prediction: Murray's shrunk 2026 Minnesota estimate, **-0.038**.

Both numbers come from the existing ledger line of 2026-11-09 and are not changed.

## Window and data

- Every Minnesota game with kickoff after the freeze time (the first is BUF@MIN, 2026-11-09), counting only dropbacks thrown by Wentz.
- Metric: published EPA per dropback (`qb_dropback == 1`), opponent-adjusted exactly as in `scripts/gut_check.py` (defense's season mean allowed with the game left out). The mean is unshrunk; its standard error is the sample standard deviation over the square root of the dropbacks.
- Whole games only. If Wentz leaves a game, his dropbacks up to then count. If Murray returns, Murray's dropbacks are tracked in the same way for context but do not enter the test.

## Scoring

At 150, 300 and 600 cumulative Wentz dropbacks, `scripts/gut_forward.py score` reports: dropbacks, games, the mean, its standard error, and the likelihood ratio `N(mean; 0.069, se) / N(mean; -0.038, se)` (greater than 1 favors H_gut).

- **Verdict only at 600 dropbacks:** ratio at least 10 "supports H_gut"; at most 0.1 "supports H_equal"; otherwise "inconclusive". The 150 and 300 readings are descriptive and cannot be called a verdict.
- The 150-dropback mean has a standard error near 0.13 and the two predictions are 0.107 apart, so that reading can lean either way and prove nothing. Even 600 dropbacks (standard error about 0.065) separates them by only 1.6 standard errors. The likely outcome is "inconclusive", and that is an acceptable answer.
- Wentz has thrown 48 dropbacks in two 2026 games. About 8 games remain this season, so 600 dropbacks probably needs part of 2027, if he is still the starter.

## Not allowed

Changing the two predictions, dropping a game, counting dropbacks from another passer, or declaring a verdict before 600 dropbacks. The existing retrospective reading stays as logged and is not rewritten.
