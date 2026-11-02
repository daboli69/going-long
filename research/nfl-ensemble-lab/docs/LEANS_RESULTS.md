# Leans: results (Amendment 2, fair odds, no fees)

Rule and hashes: `docs/LEANS_PREREG.md` (Amendment 2 committed in 61730cc5 before any new number), `docs/leans_rule_v3.json`, `docs/leans_prereg_ledger.jsonl`. Raw numbers: `docs/leans_backtest.json`. Code: `lab/leans.py`, `scripts/leans_run.py`. Screen: the Leans tab, with menus for Market, Season, From week, To week and Edge size, plus a Model switch (recalibrated or raw).

Kalshi is used here as a source of fair odds, not a place to trade. Fees, bid and ask pricing and the thin-market drop from Amendment 1 are gone.

## How accurate is the market's number?

Scored on 4,331 prop strikes from 2026 week 3 on, each fit using only earlier weeks. Lower is better.

| Number | Log loss | Brier |
| --- | --- | --- |
| Market, mid of bid and ask | 0.5456 | 0.1834 |
| Market, spread taken out (chosen) | 0.5451 | 0.1833 |
| Market, recalibrated | 0.5471 | 0.1840 |
| Our model, raw | 0.5663 | 0.1911 |
| Our model, recalibrated | 0.5656 | 0.1913 |
| Model and market blended | 0.5494 | 0.1847 |

- The market beats our model on every measure. Its log loss is about 0.02 lower, which is large for a set this size.
- Taking the spread out gains 0.0005 over the plain mid (range -0.0001 to +0.0011). It cleared the 0.0005 bar in the rule by 0.00005, so the choice is on the edge and the two numbers are practically the same. The median spread is one point, so there was little vig to remove.
- Correcting the market for bias (favorite and long-shot effects) made it worse (gain -0.0015, range -0.0040 to +0.0011). The market's stated chances are already close to the true rate.
- Blending our model into the market made the market worse (gain -0.0043, range -0.0104 to +0.0017). The model adds nothing to the market's number that holds up out of sample.

## Headline test: no edge found

All leans, recalibrated model, edges against the market's fair chance.

| Measure | Value |
| --- | --- |
| Leans / effective | 1,025 / 825 |
| Win rate | 33.2% |
| Stated edge | 13.4% |
| Realized edge | +1.9%, 95% range -1.3% to +5.2% |
| Close minus lean mid | +0.3% |
| Placebo (shuffled model) | +0.8%, range -0.9% to +3.1% |
| Follow the market / random side | -1.0% / -0.1% |

The pass rule needs four things. Closing line value above zero holds (+0.3%). The placebo mean within 1 point of zero holds (+0.8%). The realized edge range includes zero, and there are 1,025 leans against the 5,064 needed, so those two fail. No edge was found.

Raw model, for comparison: realized edge +4.3% (range +1.1% to +7.5%, one-sided p 0.004) on 953 leans, 874 effective, 4,899 needed. Its range clears zero, but the raw model was not the pre-chosen headline, it was seen in the Amendment 1 run, and the sample is a fifth of the size needed. The recalibrated model, the headline, does not clear zero. Treat the raw number as a lead to check on new weeks, not a result.

Subgroups (market, size, season) are descriptive. None has a Holm-corrected p below 0.05 (lowest 0.48), so no subgroup claim stands.

## What this means

- The most useful fact for your purpose is the first table. Kalshi's 90-minute number is an accurate probability, better than our model's, and it needs no correction. Use it as the benchmark and as a read on sentiment.
- The model's disagreements with it have not paid off beyond what chance would give. About 20 weeks of data is too little to prove either way, but nothing so far says to trust the model over the market on these props.

## Concerns

- The raw model at fair odds was seen in the Amendment 1 run, so Amendment 2's reading of it is not blind. The headline stays the recalibrated model chosen earlier.
- The recalibration of the model was adopted by choice, not by test (log loss gain +0.0007, range -0.003 to +0.004).
- The choice of the spread-removed market number rests on a margin of 0.00005. Mid would give nearly identical results.
- The scored set holds only strikes that were liquid at 90 minutes. About 71% of stored quotes were not and were never scored, so the accuracy of Kalshi's thin markets is untested.
- Game totals, spreads, moneylines and touchdown props are still not testable because the model's game numbers come from the market.
- The saved week 8 live log was written under the first rule (threshold only) and holds 0 leans and 1 "no lean".
