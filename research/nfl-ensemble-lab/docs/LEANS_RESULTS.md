# Leans: results

Rule and hashes: `docs/LEANS_PREREG.md`, `docs/leans_rule.json`, `docs/leans_prereg_ledger.jsonl` (committed in 60426ad5 before any lean was scored). Raw numbers: `docs/leans_backtest.json`. Code: `lab/leans.py`, `scripts/leans_run.py`. Screen: the Leans tab.

## What was scored

6,614 archived Kalshi prop thresholds (passing yards, receptions, receiving yards, rushing yards) from 175 games in 2025 and 2026. Each row has the model chance, the Kalshi mid 90 minutes before kickoff, the close and the real result. A lean is logged when the two chances differ by 5 points or more.

## Result: no edge found

| Measure | Value |
| --- | --- |
| Leans / no lean | 3,563 / 3,051 |
| Win rate | 45.6% |
| Stated edge | 12.5% |
| Realized edge | +2.2%, 95% range -0.5% to +4.9% |
| Closing line value | +0.15% |
| Leans needed to detect a 2 point edge | about 4,060 |
| Follow the market, same rows | -1.7% |
| Random side, same rows | -0.0% |

The realized edge range includes zero, the closing line value is close to zero, and the pass rule needs both to be positive with enough leans. It is not met. No market type, season or size group meets it either. The only range that clears zero is the large-edge group (+4.9%, range +0.5% to +9.3%), and it fails the closing line and bet-count conditions. It is also one of several groups looked at, so it is more likely noise than an edge.

## Low-end bias fix

Both the model and the market give long shots too little chance. The model said 17% and 21% happened; the market said 17% and 20% happened. A recalibration trained only on earlier weeks changed the model's log loss by +0.0007 (range -0.003 to +0.004), so it was not adopted. The market's log loss (0.546) beats the model's (0.566) either way. The shared pattern suggests the low-end miss comes from how skewed player stats are, not only from our shrinkage; I did not isolate the cause further.

## Saved player results

Only weeks 6 to 8 of 2026 have stored forecasts, so those are all that can be saved (543 player rows). Earlier weeks have no stored pre-game player projections and were not rebuilt, because a rebuild would use today's information.

## Concerns

- Rows on one player's ladder are not independent bets, and the bet-count estimate ignores that, so the real number needed is higher.
- Prices are Kalshi mid prices. The cost of crossing the spread is not subtracted, which flatters every lean.
- Game totals, spreads, moneylines and touchdown props could not be tested. The app's game numbers come from the market, so the model has no independent probability, and no archived touchdown model probabilities exist.
- Before writing the rule I looked at overall calibration of the same rows (disclosed in the pre-registration).
- Live leans: only one prop line is archived for games that have not started this week, and it is inside the threshold, so the saved week 8 log holds zero leans and one "no lean".
