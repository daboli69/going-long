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


## Amendment 1 (2026-11-02, written before any new number was produced)

Requested by the owner. All numbers after this amendment come from the code that implements it.

1. **Recalibration adopted by choice.** The original rule adopted the recalibration only if its log loss gain had a 95% range above zero. It did not pass: gain +0.0007, range -0.003 to +0.004. It is adopted anyway because the owner chose to. Every number made with it is labeled "recalibration adopted by choice, not by test". The raw-model leans stay on the screen beside the recalibrated ones.
2. **Which form.** Two walk-forward forms per stat, trained only on earlier weeks: logistic on logit(model chance) and isotonic regression. The one with the lower log loss over the test weeks (2026 week 3 onward) is used; a tie goes to logistic. Calibration by chance bucket is reported for raw, both forms and the market.
3. **Bet counts.** Each (game, player, stat) ladder becomes one lean: the strike with the largest absolute edge among strikes at or over the 5 point threshold. The game is the independent unit. The design effect is 1 + (mean leans per game - 1) times the within-game intraclass correlation of the per-lean realized edge (floored at 0). Effective bets are leans divided by the design effect. The number needed to detect a 2 point edge is the base figure times the design effect. The bootstrap resamples games.
4. **Executable prices.** An over is bought at the 90-minute ask. An under is bought at 1 minus the 90-minute bid. A lean needs both quotes present, ask above bid, and the stored `liquid90` flag. Fee per contract is 0.07 x p x (1 - p) at the price paid, the Kalshi taker formula as reported by secondary sources (I could not read Kalshi's own schedule); orders of one contract round the fee up to the cent, so the true cost is slightly higher. Realized edge after costs is the win minus the price paid minus the fee. Closing line value at executable prices is bidC - ask90 for an over and bid90 - askC for an under. The share of leans dropped for thin markets is reported.
5. **Placebo.** Within each game and stat, shuffle the model-minus-market differences across rows, rebuild the model chance as market plus the shuffled difference (clipped to 0.01 to 0.99), and rerun the same rule. 200 draws, seed 3.
6. **Headline and subgroups.** The one headline test is all leans, recalibrated model, executable prices. Market, size and season groups are descriptive; any claim about one needs a Holm-corrected one-sided bootstrap p below 0.05 across all those groups together. Weeks are descriptive only.
7. **Pass rule.** An edge is found only if all hold for the headline: realized edge after costs above zero with a game-clustered 95% range that excludes zero; closing line value at executable prices above zero; leans at or above the corrected number needed; and the placebo mean edge within 1 point of zero. Otherwise the report says no edge was found.

## Amendment 2 (2026-11-02): no fees, fair odds only

Written and hashed before any new number. The owner does not bet on Kalshi and uses it only as a read on market sentiment and fair odds, so what matters is how accurate its probabilities are and whether the model adds anything to them. Fees, bids, asks and thin-market drops answer a trading question nobody is asking, and they are removed.

1. **Fees and executable prices are retired.** No fee, no bid or ask pricing, no "dropped for thin markets" count. A lean is priced at the market chance. Amendment 1 points 4 (real prices) and the executable parts of 6 and 7 no longer apply. The Amendment 1 numbers stay in the commit history as they were reported.
2. **The market number is a fair probability.** Three candidates are built from the stored 90-minute quotes: the mid of bid and ask (`mid`); the ask side with the spread divided out, ask / (1 + ask - bid) (`devig`); and the mid corrected by a walk-forward logistic fit per stat on earlier weeks only, same scheme and first test week as the model recalibration (`calibrated`). The one used for edges is the candidate with the lowest walk-forward log loss on test weeks (2026 week 3 onward); a candidate must beat `mid` by more than 0.0005 to replace it. The stored spread is about 1 point at the median, so `mid` and `devig` are expected to be close. Before the first test week every candidate is the plain mid.
3. **Market accuracy is reported first.** Log loss, Brier score and calibration by chance bucket for the model (raw and recalibrated) and each market candidate, with a game-clustered 95% range on each difference to the plain mid.
4. **Does the model add anything.** A walk-forward logistic on the logit of the model and the logit of the chosen market number, per stat, on earlier weeks only. Its log loss gain over the market number alone is reported with a game-clustered 95% range. This is descriptive and is not a pass condition.
5. **Closing line value** is the close mid minus the lean-time mid (signed toward the lean), on raw mids whatever candidate is chosen in point 2.
6. **Headline test.** All leans, recalibrated model, edges against the chosen market number, realized edge = win minus the market chance for the side taken. Collapse to one lean per ladder, game as the independent unit, design effect, bootstrap by game, placebo (200 draws, seed 3, rebuilt against the chosen market number) and the Holm-corrected descriptive subgroups all stay as in Amendment 1. The raw model is shown beside it.
7. **Pass rule.** An edge is found only if all hold for the headline: realized edge above zero with a game-clustered 95% range that excludes zero; close-minus-lean mid above zero; leans at or above the corrected number needed; and the placebo mean edge within 1 point of zero (reachable now that no fee is charged). Otherwise the report says no edge was found.

Disclosure: the raw model at mid prices (+4.3%, range +1.1% to +7.5%) was seen in the Amendment 1 run, so this headline is not blind to that number. The headline model stays the recalibrated one chosen in Amendment 1, not the best of the two.
