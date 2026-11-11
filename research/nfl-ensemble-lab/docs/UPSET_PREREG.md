# Pre-registration: can underlying metrics flag underdogs the market underrates?

Registered 2026-11-11, before any Week 11 game and before any upset test was run. This document registers a test. It changes no model and promotes nothing.

## What is already known

- The champion's win probability loses to the closing price in every out-of-sample season since 2019 (`reports/market_gate/GATE.json`).
- Betting the side where the champion disagrees with the market by 5 points or more lost 0.062 units per bet on 1,158 walk-forward games, and the model was wrong more often as the gap grew (audit finding F5).

So "model minus market" is not an upset signal. This test asks a narrower question with signals that do not come from the champion.

## Question

Among games where the closing spread makes one team an underdog by 1 to 7 points, does the underdog win more often than its no-vig closing probability when the pre-game metrics below favour the underdog?

## Signals (fixed now, all as-of kickoff, from the existing feature store)

- S1: underdog leads in opponent-adjusted EPA per play, offense minus defense, season to date.
- S2: underdog leads in early-down success rate differential, season to date.
- S3: favourite's point differential exceeds what its EPA differential predicts by more than one standard deviation (record flatters the favourite).
- S4: underdog's projected starting quarterback is the same player as in its last three games and the favourite's is not.

Flag = at least 2 of the 4 hold. No weights, no tuning, no other signals. Thresholds above are the only ones.

## Test

- Statistic: mean of (underdog win minus closing no-vig underdog probability) over flagged games. One-sided, alternative greater than 0.
- Development read: seasons 2018 to 2025, reported with a bootstrap interval over games. These seasons have been used many times, so this read can close the question but cannot confirm it.
- Confirmation: flagged games from 2026 Week 11 onward, one look at the later of the end of the 2026 regular season or 60 flagged games. Odds rows with hold outside 0.5% to 8% are excluded.
- Also reported, not tested: flagged underdogs against the spread, and the same statistic for unflagged underdogs.

## Outcomes

- Development mean at or below 0: closed, reported as no signal. No variants are tried.
- Development mean above 0 with an interval above 0: it becomes a hypothesis and waits for the 2026 confirmation sample. Nothing is published as a pick before then.
- Sample size warning: at about 4 flagged games a week the confirmation sample cannot reach 60 this season. A positive development read will most likely stay unconfirmed until 2027.
