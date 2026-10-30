# Joint score model: results

Run 2026-10-29. Protocol `94e455cc`, Amendment 1 and power `db086e43` (committed before the main run), one look.
`reports/forecast/results.json`, SHA-256 `41fc3cacdbaa2ebb8bd3aa29237af1c06789d90a3ec0b8db77f5a7ac3ed55b29`.
Nothing is promoted. Power classified only one comparison (L1) as decidable from history, so **everything else here is
descriptive**, and every reading stays provisional until Codex reproduces it.

**Short version.** The new model is a much better projection than a naive baseline for margins and totals, but it is **no better than
Elo for margins and it adds nothing to Kalshi**. Its leans against the market are not informative. The right way to use it today
is to follow Kalshi (or Pinnacle) and treat the model as a calibrated fallback where no market exists.

## The model
Two closed-form Gaussian regressions (margin from team net strength plus home field, total from team scoring level) with decayed observations,
the residual correlation between them (mean 0.03, so margin and total are nearly independent), and predictive uncertainty that includes
parameter uncertainty. Tuning of the shrinkage (margin 4.0, total 3.0) used 2008 to 2011 only. P(win), the spread and the total all come
from the same distribution. PyMC, NumPyro, MAPIE and scoringrules are not installed, and this is the exact posterior those would sample.

## History, 2012 week 1 to 2026 week 8 (3,770 games, 250 weeks)

| Comparison (CRPS, lower is better) | Difference | Interval | Status |
|---|---:|---|---|
| **L1 margin: model 7.507 vs Elo-normal 7.475** | **+0.032** | [-0.030, +0.094] | **decidable: does not improve** (better in 8 of 15 seasons) |
| L2 margin: model vs naive 8.046 | -0.539 | [-0.657, -0.420] | descriptive: far better than naive |
| L3 total: model 7.673 vs naive 7.816 | -0.144 | [-0.217, -0.064] | descriptive: better than naive |
| L4 winner log loss: model 0.6388 vs Elo 0.6332 | +0.0056 | [-0.0002, +0.0114] | descriptive: no better than Elo |

The L1 result is the only history verdict the protocol allows: **the model does not beat an Elo-based normal margin**. The naive
baseline is weak, so beating it says little.

## Against the market (Kalshi window: 2025 week 5 to 2026 week 8)
Fitted on earlier weeks only, so 14 weeks were scorable (214 margin and 211 total games).

| Comparison (ladder CRPS) | Difference | Interval | Notes |
|---|---:|---|---|
| K1 margin: corrected vs Kalshi 3.075 | 0.0000 | [0, 0] | the fitted weight b was **0.000 in every week**: the model never earned any influence |
| K2 total: corrected vs Kalshi 1.936 | +0.0044 | [+0.0004, +0.0090] | slightly **worse** than Kalshi (mean b = 0.047) |
| K3 winner log loss: corrected vs Kalshi | 0.0000 | [0, 0] | same as K1 |

Model alone, scored on the same ladders: margin 3.300 vs Kalshi 3.075 (7% worse); total 2.026 vs 1.937 (5% worse). The placebo
(shuffling the model's forecasts across games within each week) is uninformative for margins because the correction is always zero, and
for totals the real result (+0.0044) is no better than chance (permutation p = 0.68). Per the protocol, K-family verdicts need
25 to 54 prospective weeks; none is allowed from this history.

**Pinnacle check (2026, 106 games, descriptive).** Kalshi's median is within 0.21 points (margin) and 0.35 points (total) of
Pinnacle's line on average, and their errors against the outcomes are nearly identical (margin MAE 9.50 vs 9.49; total MAE 10.52 vs 10.55). The
model alone is worse (10.02 and 10.93). That supports using Kalshi as the benchmark.

## Leans
- **Margin:** there are no leans to evaluate, since the correction was always zero.
- **Total:** bigger disagreements with the market did worse, not better. The Spearman rank correlation between lean size and ladder-CRPS gain is
  -0.168 [-0.290, -0.013], and the gain is negative in every bin (-0.0004, -0.0015, -0.0085, -0.0136 from the smallest to the largest). The realized
  deviation does not follow the model's direction. **The model should abstain: its leans against the market carry no signal.**

## Calibration (80% intervals, descriptive)
- **Margin and total, 2012 to 2026:** the raw Gaussian intervals cover 78.9% and 79.4%; split conformal intervals cover 79.7% and 80.9%. Both are
  within about 1 point of 80%.
- **Props (replayed simulator, 80% interval q10 to q90):** liquid ladders raw 82.3% and conformal 81.2%; thin ladders raw 84.8% and
  conformal 80.8%; players with no Kalshi market raw 81.7% but conformal **72.6%** (201 rows). Pooling calibration scores across groups
  makes the no-market group's intervals too narrow, so conformal calibration should be done per group.

## Props against a naive baseline (scaled quantile-loss CRPS, descriptive)
The v2 simulator beat the naive recent average by about 2% on thin ladders (-0.0200 [-0.0497, +0.0077], 2,171 player-stats) and 4% on liquid
ones (-0.0389 [-0.0765, +0.0106], 1,234), with intervals that include zero. For players with no Kalshi market (322) it is no
different (+0.0036 [-0.0906, +0.0714]). These need 131 to 1,534 weeks to settle, so this is a descriptive picture only.

## Coherence
Kalshi's own winner price and the winner probability implied by its spread ladder disagree by 1.7 cents on average (the winner price is higher by
1.2 cents), and by more than 2 cents in 27% of games across 314 games. The model's own P(win), spread and total agree by construction.
Whether that cross-market gap is tradable was not tested. Team-total ladder coherence and a Kalshi-normal comparator were not run.

## Missing data and limits
- No timestamped historical availability, so availability, weather and referee features could not be used in any fit.
- Pinnacle exists for 2026 only. No undated closing lines were used.
- Power says the K family needs 25 to 54 weeks (K3, K2, K1) and all prop comparisons need 131 or more weeks.
- Not run: the Kalshi-normal comparator, team-total coherence, and per-season conformal coverage.
