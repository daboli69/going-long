# Leans: results (Amendment 1)

Rule and hashes: `docs/LEANS_PREREG.md` (Amendment 1 committed in fb0b8aa8 before any new number), `docs/leans_rule_v2.json`, `docs/leans_prereg_ledger.jsonl`. Raw numbers: `docs/leans_backtest.json`. Code: `lab/leans.py`, `scripts/leans_run.py`. Screen: the Leans tab, with menus for Market, Season, From week, To week and Edge size, plus switches for Price (executable or mid) and Model (recalibrated or raw).

## What changed from the first run

- **Recalibration adopted by choice, not by test.** Walk-forward log loss on 4,331 test rows: raw 0.5663, logistic 0.5656, isotonic 0.5770, market 0.5456. Logistic wins the pre-written choice rule. Its gain over raw is +0.0007 (range -0.003 to +0.004). Isotonic is clearly worse than raw (gain -0.0107, range -0.0190 to -0.0033). The market is still better than any version of the model.
- **One lean per ladder.** 3,672 threshold-passing rows collapse to 1,036 leans (recalibrated) and 958 (raw), across 168 games.
- **Effective bets.** Leans from one game move together a little (intraclass correlation 0.051), so the design effect is 1.27 and the 1,036 leans are worth about 819 independent ones. About 5,122 leans are needed to detect a 2 point realized edge; the first run said 4,060.
- **Real prices.** An over is bought at the 90-minute ask, an under at 1 minus the bid, with a fee of 7% x price x (1 - price) per contract.

## Headline test: no edge found

All leans, recalibrated model, executable prices.

| Measure | Value |
| --- | --- |
| Leans / effective | 1,036 / 819 |
| Win rate | 32.6% |
| Stated edge | 13.5% |
| Realized edge before fees | +1.2% |
| Realized edge after costs | -0.2%, 95% range -3.4% to +3.1% |
| Closing line value at executable prices | -1.2% |
| Placebo (shuffled model) after costs | -1.2%, range -3.0% to +1.0% |
| Follow the market / random side, same prices | -3.1% / -2.1% |

All four pass conditions fail: the range includes zero, closing line value is negative, there are far fewer leans than the 5,122 needed, and the placebo is not within 1 point of zero. The recalibrated model's realized edge after costs sits inside the placebo's range, so it cannot be told apart from a lean with no information.

Raw model, for comparison: +2.1% after costs (range -1.2% to +5.3%), closing line value -1.3%. At mid prices the raw model reads +4.3% (range +1.1% to +7.5%), which clears zero, but a mid price cannot be traded: the ask, the bid and the fee take about two points of it, and the executable range includes zero.

Subgroups (market, size, season) are descriptive. No group has a Holm-corrected p below 0.05 (all are 1.0), so no subgroup claim stands.

## Thin markets

0% of leans were dropped. The scored set already holds only contracts that were liquid 90 minutes before kickoff and have a bid and an ask (all 6,614 rows). Of the 62,987 quotes stored, about 71% lack the liquid flag and were never scored, so thin markets are excluded before the leans, not by them.

## Concerns

- The placebo condition (within 1 point of zero) cannot be met after costs: a lean with no information loses roughly the fee, about 1.4 points. The condition was mis-specified. It does not change the verdict, since the other three conditions fail too, but a better test is whether the real edge sits above the placebo's range. It does not.
- The fee formula is from secondary reports of Kalshi's schedule; I could not read Kalshi's own document. One-contract orders round the fee up to the cent, so true cost is a little higher.
- Fills are assumed at the displayed 90-minute bid or ask for any size. The `liquid90` flag is as stored; I did not verify how it was defined.
- Raw-model results at mid prices were looked at in the first run; the executable and clustered numbers are new.
- Game totals, spreads, moneylines and touchdown props are still not testable because the model has no independent probability for them.
- Live leans: the saved week 8 log holds 0 leans and 1 "no lean". It is still written under the first rule's threshold, not collapsed or priced at the ask.
