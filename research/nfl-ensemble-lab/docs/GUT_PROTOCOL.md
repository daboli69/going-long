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

Clarification, 2026-11-09, before the checker ran: the verdict uses the opponent-adjusted metric in both windows; the unadjusted numbers are reported beside it. I had already seen the unadjusted per-season EPA for Wentz and Murray (Wentz 2025 +0.04, 2026 +0.10; Murray 2024 +0.11, 2026 MIN -0.05) when writing this, so the Wentz and Murray result is disclosed as not blind.

## Results (run 2026-11-09)

### Claim: "Wentz is better than Murray for offensive EPA" (`reports/gut/claims_ledger.jsonl`)

Opponent-adjusted EPA per dropback, shrunk with 250 dropbacks, 80% interval of the difference (Wentz minus Murray):

| Window | Wentz (n) | Murray (n) | Difference | 80% interval | Share Wentz better |
|---|---:|---:|---:|---|---:|
| Last three seasons | +0.055 (269) | +0.046 (989) | +0.009 | -0.058 to +0.073 | 0.58 |
| Same offense (MIN, 2025 to 2026) | +0.069 (245) | -0.038 (185) | +0.107 | +0.049 to +0.162 | 0.99 |

Verdict: **not distinguishable**, because the windows disagree. Wentz leads clearly on the Vikings' own offense (7 games against 6), where the sample is also the smallest and is shared with a different supporting cast and schedule. Over three seasons the two are even. The unadjusted numbers lean the other way over three seasons (Murray +0.07, Wentz +0.03). The gut is a live possibility, not a finding. Next re-run after Wentz has 150 more dropbacks.

### Quarterback refresh for BUF@MIN (first record)

`reports/qb_refresh/refresh_ledger.jsonl`. With the refreshed state (Wentz expected, `qb_change` = 1) the models move Minnesota only slightly: margin model 45.2% to 44.4%, deep model 48.1% to 45.3% (market 23%). The quarterback input changes the predicted margin by 0.24 points. That is the blind spot in numbers: the model's quarterback lever is nearly flat, and it also rates Wentz slightly below Murray (shrunk value -0.018 versus +0.005 for the frozen Murray state), which is the opposite of the hunch and consistent with the three-season window above.
