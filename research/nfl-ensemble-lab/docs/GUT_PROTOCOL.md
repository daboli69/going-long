# Gut-claim checks and the quarterback refresh: rules fixed before the code ran

Written 2026-11-09, before `scripts/gut_check.py` and `scripts/qb_refresh.py` were run. Descriptive tooling; nothing feeds a freeze, a forecast or a bet.

## Part 1. Checking a hunch against the data

A claim is "A is better than B at metric M". The checker reports what the history says and how sure it is. It cannot turn a hunch into a fact: a history that agrees with the claim is a reason to keep watching, and a history that does not is a reason to doubt, nothing more.

Fixed rules:

- **Metric.** Published EPA per dropback (`qb_dropback == 1`, sacks and scrambles included). Reported twice: as is, and opponent-adjusted by subtracting the opposing defense's season mean EPA per dropback allowed, with that game left out.
- **Shrinkage.** Each quarterback is pulled toward the league mean with 250 dropbacks of prior weight (the same `QB_N0` the forecast uses). Not tuned.
- **Windows.** Two, always both: the last three seasons (2024 to 2026), and the same offense (games with the team the claim is about, 2025 to 2026).
- **Uncertainty.** Bootstrap by game, 5,000 resamples, seed 20261109, each resample draws whole games with replacement for each quarterback. Report the difference (A minus B), its 80% interval and the share of resamples where A beats B.
- **Verdict words.** Share at least 0.90 in both windows: "supported". At most 0.10 in both: "contradicted". Anything else, including the two windows disagreeing: "not distinguishable". A "supported" verdict from past data is labeled retrospective.
- **Log.** Every check appends one line to `reports/gut/claims_ledger.jsonl` with the date, the claim, the numbers and the verdict. Lines are never edited. A claim is re-run after the next 150 dropbacks of the newer quarterback; the earlier line stays.
- **Not allowed.** Choosing the window, metric or adjustment after seeing a result, or re-running a claim until it passes.

## Part 2. Quarterback refresh (the blind spot)

The freeze stays untouched. When the starting quarterback listed in the freeze is Out or Doubtful, or a different quarterback is expected, `scripts/qb_refresh.py <game_id>` writes one extra record to `reports/qb_refresh/refresh_ledger.jsonl`: the same models with the quarterback state rebuilt from the latest injury snapshot, everything else as at the freeze cutoff. It refuses to write a second record for the same game.

Scoring, after the game: log loss and Brier score of the freeze, the refresh and the Kalshi price at refresh time, over every game that has a refresh. Reading rule: the refresh counts as an improvement only if it has the lowest log loss over at least 10 refreshed games. Before that it is reported, not trusted. The refresh never replaces the freeze in any tally.
