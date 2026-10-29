# Live in-game pricing: does the market overreact? Pre-registration frozen 2026-10-29, before any model-versus-Kalshi comparison

Question: can the NBA Ensemble price NBA moneylines, spreads and totals during a game from the state of the game alone (Model A), does pregame
closing-line information add to that (Model B), and is a live Kalshi price ever far enough from the model's fair price to give a positive expected
return after fees? The hypothesis to falsify: the live market sometimes overreacts to in-game developments.
No order is placed or simulated. Historical "returns" below are quote-based, not fills.

## State of the work at the time of writing (what has been looked at)

- Looked at: model fits and their log loss, Brier and calibration against **game outcomes** on 2022-2025 and on 2026 up to 2026-01-31 (development), including two structural changes
  made while looking (Student-t errors; lead-dependent drift and variance, which fixed over-confidence at the extremes). Closing-line information from the ESPN-embedded pregame spread was
  compared with the independent model on the same development states.
- Not looked at: any comparison between a model price and a Kalshi in-game price, any Kalshi pregame close inside the development or final windows, and any state from 2026-02-01 onward.
- Historical Kalshi data are collected (moneyline 1-minute quotes for the 2025-26 regular season; spread and total history exists but is not part of this test).

## Data and timing

| Item | Source | Event time | Publication / collection time | Limits |
|---|---|---|---|---|
| Game state | ESPN play-by-play (SportsDataverse release), wall-clock stamp per event | event wall-clock (repaired running maximum) | file retrieved 2026-10-28 | Stamp delay vs real time unknown; lag sensitivity reported; games with a >10 min inversion or >6 h span excluded |
| Kalshi in-game moneyline | `GET /historical/markets/{ticker}/candlesticks`, 1-minute bid/ask/last | candle end time (exchange time) | retrieved 2026-10-29 | Bid/ask closes, not fills; no order-book depth history; thin-minute carry-forward |
| Kalshi pregame close | last candle ending at or before the first play-by-play event | candle end | same | After a game starts, no pregame price exists |
| Closing spread (ESPN-embedded) | play-by-play files | unknown | unknown | Used only for Model B training (2022-2024) as the closing-line input |
| Lineups | reconstructed stints (2021 onward) | event | derived | 94% of states have a lineup |
| Ratings | weekly RAPM refits using games dated before the refit | refit day | derived | Noisy (55-60% reliability) |
| Sportsbook live quotes | **not available** | | | No free historical source; the page accepts manually typed quotes only |

## Models (all fitted by maximum likelihood on training data only)

Regulation final margin = current margin + D, D ~ Student-t(nu_m) with mean `a1*mu*x + am*m*x + aL*L*x` (x = remaining regulation share, L = on-court lineup rating difference),
scale `sqrt((exp(p0)+exp(p1)*x) * (1 + av*(|m|/10)^2*x))`. Remaining regulation total ~ Student-t(nu_t) around a linear function of x, x*T_pre, x*pace surprise and a late-game term,
with variance exp(q0)+exp(q1)*x, and a residual correlation rho with the margin. A regulation tie goes to overtime with its own margin and total distributions. Moneyline, spread and total probabilities are
read from the same joint distribution.

- Model A: `mu` from the independent pregame prior (ridge on Elo, recent net rating, rest, back-to-back and availability features; walk-forward). No market input. Variants: base prior, availability prior, on-court lineup term.
- Model B: `mu` replaced by the closing line. B_ESPN uses the ESPN-embedded closing spread. **B_K uses the Kalshi pregame mid, converted by mu = sigma_g * Phi^-1(p)** with sigma_g the margin scale fitted on 2022-2024 spread-to-outcome data, so no parameter is fitted on Kalshi.
- Model C: the Kalshi in-game quote (vig-normalised midpoint of the two winner contracts), benchmark only.

## Windows (fixed now)

| Window | Dates | Use |
|---|---|---|
| Training | seasons 2022-2024 for the structure; the final-test model is refit once on all data before 2026-02-01 | fitting |
| Development | 2025 season and 2026-10-21 to 2026-01-31 | all design choices, lag choice, calibration checks, stratified exploration |
| **Final test** | **2026-02-01 to the end of the 2025-26 regular season** | evaluated once after the freeze commit; no model change afterwards |
| Prospective | 2026-27 season, captured live | descriptive until at least 500 games |

States are sampled every 2 minutes of wall-clock time during regulation. Overtime states are not priced.

## Hypotheses and decision rules

H1 (information). In the final window, `P(home win) = logistic(a + b_k * logit(C) + b_m * logit(B_K))` has **b_m > 0** (one-sided, alpha 0.05, standard errors clustered by game). Supplement: paired log-loss difference C minus B_K with a game-clustered bootstrap.
H2 (overreaction). Let `d = logit(C) - logit(B_K)`. (a) In the H1 regression, `b_m > 0` means the closing-informed structural model carries information the live price lacks; that is the regression form of overreaction (or under-use of the pregame close), and (b_k, b_m) are reported together.
(b) Correction: regress the change in `logit(C)` over the next 10 minutes on `d`; reversion means a negative coefficient. (c) Economics: at each state where the conservative expected value of the better side of the Kalshi winner contract is positive, take the ask (or the NO price = 1 - bid), hold to
settlement, subtract the fee; report mean net return per contract with a game-clustered 95% interval. One signal per game per side per period of 10 minutes, to limit overlap.
H3 (closing line). Paired log-loss difference B_ESPN minus A and B_K minus A, development and final windows.

**Overreaction is "supported" only if** (i) b_m > 0 with the interval excluding 0 in the final window, **and** (ii) the quote-based net return per contract (H2c) is positive with its 95% interval excluding 0 in the final window, **and** (iii) the sign holds
in each calendar third of the final window. Otherwise: "not demonstrated". A positive result is described as a property of quoted bid/ask in historical candles, never as historical profit.

Conservative probability and target price (derived, not tuned): `p_low = p - 1 * SE`, where SE combines parameter uncertainty (game bootstrap, 40 refits, SD of the model probability by remaining-time bucket) and a calibration slack equal to the root-mean-square calibration error by probability bin on the development window.
The highest acceptable price is the highest cent price at which `p_low - price - fee >= 0` (YES) or `(1 - p_high) - price - fee >= 0` (NO). The Kalshi taker fee is `ceil(0.07 * contracts * P * (1-P))` to the cent (secondary sources; the official page could not be fetched).
For sportsbook-style odds: EV = p_win * profit - p_loss with exact pushes on whole-number lines; minimum American odds solve EV = 0 at `p_low`.

## Metrics

Log loss, Brier, calibration (reliability table, slope and intercept), CRPS of the margin distribution, coverage of the 50% and 90% margin intervals, game-clustered bootstrap (4,000 draws) for every paired difference; stratification by quarter, deficit, remaining time, favourite/underdog (pregame close), size of the move since the close.
Multiple strata are descriptive and not used to select a rule.

## Verification

Tests for fees, EV, push handling, minimum prices, monotonicity of spread probabilities and agreement between simulation and the closed form (`tests/test_fair_value.py`); timestamp-alignment sensitivity (lag 0, 30, 60 seconds, chosen on development only);
a check that no state uses a later event than its quote minute; the final window evaluated once.

## Not claimed

No sportsbook live-odds test (no data). No spread or total market test on Kalshi in this pass (history exists; not collected). No profitability claim from candle bid/ask. No claim about player props: Kalshi lists them, this pass prices none.
