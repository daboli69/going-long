# Leans: pre-registered rule

Written 2026-11-02 before any lean was scored. The machine-readable copy is `docs/leans_rule.json`; its SHA-256 is recorded in `docs/leans_prereg_ledger.jsonl`. Change the rule only by adding a dated amendment below.

## What a lean is

A lean is a side (over or under) on one archived Kalshi prop contract, logged when the model's probability differs from the market's by at least the edge threshold. There is no staking and no bet sizing anywhere.

- Universe: Kalshi player-prop thresholds in `data/cache/props_kalshi/scored_thresholds.parquet` (2025 weeks 6 to 18 and 2026 weeks 1 to 7), passing yards, receptions, receiving yards and rushing yards, each at a real archived strike.
- Time of the lean: 90 minutes before kickoff. Market probability at the lean is the Kalshi mid at that time (`p_market90`). The close is `p_marketC`.
- Model probability: `p_A`, the sim-based probability already stored with each row, or its recalibrated version if the fix below is adopted.
- Edge = model probability minus market probability. A lean is over when the edge is at least +0.05 and under when it is at most -0.05. Anything between is "no lean".
- Edge size: small is 5 to under 8 points, medium is 8 to under 12, large is 12 and over.

## Edge measures (all shown as percentage points)

- Stated edge: average of |model - market| over the leans.
- Realized edge: win rate of the leans minus the average market price of the side taken (market for overs, 1 - market for unders).
- Closing line value: average of (close - lean-time market) for overs and (lean-time market - close) for unders.

## The fix to test (low-end bias)

Walk-forward recalibration of `p_A`: for each test week, fit a logistic recalibration of the outcome on logit(`p_A`) per stat using only earlier weeks (2025 plus earlier 2026 weeks), starting at 2026 week 3. Adopt it only if the log loss gain over raw `p_A` over those test weeks is positive and its 95% paired bootstrap interval by game excludes zero. If it is not adopted, leans use raw `p_A`.

## Pass rule

A rule "finds an edge" only if all of these hold over all leans: realized edge above zero with a 95% paired bootstrap interval by game (10,000 draws, seed 1) that excludes zero; closing line value above zero; and the number of leans at least the number needed to detect a 2 point realized edge at 80% power. Otherwise the report says no edge was found. Calibration by probability bucket is reported for model, recalibrated model and market.

## Benchmarks

Follow the market (over when the market is above 50%, else under) and a random side (average of 200 random assignments, seed 2) on the same rows, with the same measures.

## Not covered, and why

Game totals, spreads and moneylines: the game numbers in the app come from the market, so the model has no independent probability and the edge is zero by construction. Touchdown props: no archived model probability with outcomes in a usable form. Both show on the screen as "not testable" until independent model numbers are archived.

## Disclosure

Before writing this rule I looked at overall calibration and mean edge by stat of the same rows (market log loss 0.550, model 0.566; both too low on long shots). Thresholds were set from convention, not tuned to those results.
