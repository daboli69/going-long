# Kalshi player props: results

Run 2026-10-29. Protocol `31af0b08`, power `60b72455` (committed before the scored replay), one look.
`reports/props_kalshi/results.json`, SHA-256 `fa3181879c4368cce3d2c2a35c0fab7290d774bb8296f9487b7d8262aa405b14`.
All local, read-only Kalshi data, no trading code. Reused history, and **every gate reading is provisional until Codex
rebuilds it from the protocol**. Nothing is promoted.

## What was scored
- 179 games with a scorable ladder (2025 weeks 5-18 and 2026 weeks 1-7), 20 scored weeks.
- 1,242 player-stat ladders and 6,654 thresholds, each liquid at kickoff minus 90 minutes (the step-0 filter) and settled
  yes or no. By stat: receiving yards 474, receptions 295, rushing yards 266, passing yards 207.
- Both simulator arms ran the lab's existing v2 simulator as of each week, using only earlier seasons and earlier
  weeks. Arm K takes the game total and spread from Kalshi at T-90, and arm A takes `games.csv`'s undated lines.

## Data checks
- **Settlement:** Kalshi's yes/no matched the official full-game stat on 99.91% of 49,687 thresholds (47
  disagreements). Against regulation-only stats the agreement drops to 99.43% (281 disagreements), which shows Kalshi
  settles on the whole game **including overtime**. Nothing was edited.
- **Excluded:** 538 non-binary (scalar) settlements, and 1,238 thresholds with no official stat.
- **Trades:** 11,135 liquid markets had their raw prints pulled (11,128 traded in the prior 24 hours). The last print
  sat inside that candle's bid/ask 86.9% of the time.
- **Game environments:** all 314 games had a Kalshi margin and total median at T-90.

## Results

| Family | Comparison | Result | Interval | Verdict |
|---|---|---|---|---|
| G (primary) | ladder CRPS, K 1.0286 vs base 1.0707 | -0.0421 | [-0.0937, +0.0190] 98.3% | **fail** (interval includes zero) |
| G | K vs market at T-90 (0.9978) | +0.0309 | [+0.0063, +0.0513] | **fail**: the market is significantly better |
| G | A vs K | +0.0010 | [-0.0017, +0.0029] | fail: no difference |
| S | stack weight on the simulator (market 0.745) | +0.196 | [+0.051, +0.378] 95% | **pass** |
| C | K: mean CLV T-90 to close | +0.0009 | [+0.0005, +0.0015], 1,906 toward vs 1,687 away | pass by the rule, but see below |

Lower CRPS is better. The market at the close scores 0.9934, and market at T-90 beats the simulator in all four stats:

| Stat | Naive base | Simulator K | Market T-90 | Market close |
|---|---:|---:|---:|---:|
| Passing yards | 1.077 | 1.016 | 0.991 | 0.988 |
| Rushing yards | 1.203 | 1.164 | 1.103 | 1.109 |
| Receiving yards | 1.099 | 1.071 | 1.043 | 1.038 |
| Receptions | 0.902 | 0.848 | 0.834 | 0.820 |

## What this means
- **The simulator beats the naive recent-average baseline by about 4% on ladder CRPS, but not by enough to be
  confident.** The interval includes zero, and the pilot said this backtest could only detect effects of about 0.030.
- **The market is better.** Kalshi at T-90 beats the simulator by 0.031 (3%), and the gap is statistically clear.
- **The simulator still carries a little information the market lacks.** In the stack, its weight is 0.196 with an
  interval above zero. In practice that means a small blend weight on top of a market-dominated forecast. The market
  keeps the large share (0.745).
- **The CLV pass is real but tiny.** The mean move toward the simulator's side is 0.0009 in probability, less than a
  tenth of a cent on a contract. Arm A, which has no Kalshi inputs, shows nearly the same (+0.0008). The naive base
  control is +0.0004 and not significant. With a median bid/ask spread of 0.03, no drift this size is tradable. No
  returns were measured.
- **Using the Kalshi total and spread as the game environment (the ensemble-improvement step) did not change
  accuracy:** K and A differ by 0.001 [-0.0017, +0.0029]. Its value is that it removes a possible look-ahead in the
  current inputs, not that it improves projections.
- **Calibration:** the simulator's probability-integral-transform histogram is acceptably flat (K p = 0.26, A p = 0.07),
  while the naive base is badly off, piling up in the top bin (p = 3.5e-9).

## Power and what comes next
History MDE is 0.030 against a smallest effect of interest of 0.014. A prospective verdict on family G needs **90 frozen
weeks**, which is not reachable this decade. The stack and CLV questions are better powered. A weekly props freeze that
captures Kalshi ladders and the K-arm distributions is not built yet.

## Missing data
- Kalshi prop ladders exist only from October 2025, so there are 20 scored weeks.
- No official inactives are archived, so availability is the game-week roster minus injury-report Out.
- About three-quarters of player-prop thresholds fail the liquidity filter. Receiving yards and receptions are the
  thinnest series.
