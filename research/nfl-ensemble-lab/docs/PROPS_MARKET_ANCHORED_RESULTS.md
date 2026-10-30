# Market-anchored player props: results

Run 2026-10-29. Protocol `7964284b`, power and pass rules `4909f1ba` (committed before any fit), one look.
`reports/props_market/results.json`, SHA-256 `961ca2431208fe9abf9ae266b0d25551711321fad714c1dd334ca518eece7646`.
History is reused, so every number below is **descriptive**. Only prospective freezes can pass anything, and every reading
stays provisional until Codex reproduces it. Nothing is promoted.

## What was scored
The walk-forward correction needs 500 earlier thresholds per stat before it can be fitted. That consumed the first 14 of the 20
weeks, so **only 762 ladders (4,344 thresholds) in 6 weeks were scored**, not the 20 weeks the power analysis assumed. Scaling
the power result for 6 weeks puts the M1 minimum detectable effect near 0.010, roughly the size of the smallest effect of interest
(0.00998). That is a rough estimate from scaling, not a rerun. The fitted blend weight b stayed small: 0.0 to 0.41 by week and
stat, with the last-week values 0.00 (passing yards), 0.19 (receptions), 0.25 (receiving yards) and 0.17 (rushing yards).

## Results (ladder CRPS, lower is better)

| Model | Mean ladder CRPS | Mean log score |
|---|---:|---:|
| Kalshi market at T-90 | 1.0467 | 0.5459 |
| Corrected (b between 0 and 1) | 1.0474 | 0.5467 |
| Existing stack (walk-forward) | 1.0500 | 0.5473 |
| Simulator alone | 1.0908 | 0.5680 |

| Comparison | Difference | 98.33% interval | Rule result |
|---|---:|---|---|
| M1 corrected vs market (primary) | +0.0007 | [-0.0037, +0.0051] | **does not improve** (game-cluster interval [-0.0093, +0.0096]) |
| M2 corrected vs simulator | -0.0434 | [-0.0610, -0.0246] | improves and material |
| M3 corrected vs existing stack | -0.0026 | [-0.0067, +0.0003] | does not improve |
| L1 log score vs market | +0.0008 | [-0.0017, +0.0024] | does not improve |
| L2 log score vs simulator | -0.0212 | [-0.0265, -0.0135] | improves |
| L3 log score vs existing stack | -0.0005 | [-0.0023, +0.0009] | does not improve |

**Placebo:** shuffling simulator probabilities across players within each game, stat and threshold (200 permutations, 67% of
thresholds shufflable) gives a mean placebo delta of +0.0020 and a 5th percentile of +0.0002. The real delta is +0.0007,
permutation p = 0.12. **M1 is not credible**, which the protocol fixed in advance as the cutoff for taking an effect seriously.

## What this means
- **Out of sample, the simulator added nothing measurable to Kalshi.** The market scored 1.0467 and the corrected forecast
  1.0474. The earlier study's "stack pass" (weight 0.196) used weights fitted on all 20 weeks. Fitted only on earlier weeks,
  the same blend is slightly worse than the market (1.0500). So that pass was partly in-sample, and I should have said so
  when I reported it.
- **Anchoring to the market still beats using the simulator alone** by about 4% (M2, M3-style comparison), which is why
  the correction is worth keeping as a safe way to use the simulator.
- **This is inconclusive, not proof of no effect.** Six scored weeks can detect only effects near the smallest size of
  interest, and the in-sample blend gain was about 0.003.
- Passing yards got b = 0: the data never asked for any simulator weight there.

## Coherence (descriptive; nothing patched)
- **Ladder exceedance** (simulator minus market, summed over each ladder's thresholds): receiving yards **-0.131**
  [-0.176, -0.093], a clear gap in which the simulator puts less probability on high receiving yardage; passing yards -0.028,
  receptions -0.031, rushing yards -0.011, all with intervals that include zero.
- **Pass-yard identity:** the sum of eligible receivers' mean receiving yards over the QB's mean passing yards has a median of
  0.77 (quartiles 0.69 and 0.84) across team-games. That is below 1, as expected, because only eligible receivers are listed,
  and it says nothing about whether the shortfall is the right size.
- **Not testable with public Kalshi data:** market-implied same-game correlations, and team-total ladder agreement (about
  3,000 more candle pulls, deferred).

## Cost (descriptive, not a return)
Across 4,344 thresholds: median bid/ask spread 0.010, median cost to cross one side (half-spread plus the quadratic fee)
0.0194, median absolute model-minus-market edge 0.0103. The model's edge exceeds the cost on **33.6%** of thresholds
(1,460). Marked at the posted T-90 quote and net of the fee, those averaged **+0.0008 per contract, interval [-0.0167,
+0.0209]**. Fills, depth, size and slippage are not modeled. There is no measurable edge after cost.

## Missing data
- Availability at T-90 was not timestamped historically, so the information-event test (E) and availability features
  could not be run. Collection and weekly freezes start now.
- Historical order books do not exist. Trade prints exist for liquid markets only.
- The official fee-schedule PDF was blocked (HTTP 429). The 0.07 coefficient is verified only through Kalshi's worked example.
