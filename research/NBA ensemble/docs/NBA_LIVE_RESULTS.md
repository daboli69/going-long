# Live in-game pricing and the overreaction hypothesis: results

Protocol: `docs/NBA_LIVE_PREREGISTRATION.md` (committed and timestamped before any model-versus-Kalshi comparison).
Frozen models: `docs/NBA_LIVE_FROZEN.json` (committed and timestamped before the final window was opened; its SHA-256 `e1459942...d2ca` is the value that was stamped and the value present when the final run started).
Code: `nba_xgb/` (`live_state`, `live_model`, `fair_value`, `live_value`, `live_value_page`, `live_market`, `live_final`, `kalshi`, `kalshi_inplay`, `live_collector`). Nothing was pushed, deployed or traded; no order was placed or simulated.

## Verdict

**The hypothesis that the live Kalshi market overreacts, in a way a trader could exploit, is not supported.** On the untouched final window (2026-02-01 to 2026-04-12, 488 games, 32,480 two-minute states), Kalshi's own in-game price was better than every model I built, and the models added no information once the price was known. Buying at the quoted ask whenever the closing-informed model showed a positive expected value after fees and an uncertainty margin lost 2.4 cents per contract on average (95% interval −4.9 to +0.1 cents). Before fees it lost 1.2 cents. A nine-point swing in a quoted spread is not a nine-point pricing error, and in the one worked example below the model thought the market had under-moved, not over-moved; the final-window evidence says the model is not the party to trust.

What is demonstrated, what is not, and the evidence for each follow.

## 1. Where the previous session stopped

Recovered from the repository, not from memory: last pushed commit `f569dd22` (availability study); local commits `9e3b7efd` (market phase 1) and later; uncommitted `nba_xgb/kalshi.py` whose only run was a six-game test. The "not yet run" list in `docs/NBA_MARKET_PREREGISTRATION.md` (own-tipoff injury features, box-score-prior ratings, GAM/EBM/XGBoost searches, the pregame encompassing regression, SPA/MCS, Bayesian state-space) was **not** resumed in this pass: the new objective replaced it, and those items remain open. The only handoff file in the repository (`updates/.../NEXT_RESEARCH_TASK.md`) belongs to Codex's separate player-minutes work and was left alone. Existing uncommitted files were not touched; changes to `app.py` are one radio entry, one branch and a one-clause banner edit.

## 2. Data audit

| Item | Coverage | Timestamps | Integrity | Limits |
|---|---|---|---|---|
| ESPN play-by-play (SportsDataverse), seasons 2022-2026 | 6,102 games with 140,346 two-minute training snapshots | per-event wall clock | scores match box in 99.92%; wall clock non-decreasing in 99% of steps; games with a >10 min inversion or >6 h span excluded | stamp delay vs real time unknown; **sharp alignment found**: correlation of 1-minute changes in the Kalshi mid and in the model probability peaks at lag 0 (0.74; 0.37 at −30 s; 0.50 at +30 s), chosen on development data |
| Kalshi NBA game-winner markets | 2,426 markets (both sides of about 1,213 games) for the 2025-26 regular season, 519,153 one-minute rows, raw responses archived with hashes | exchange candle time | bid/ask closes of 1-minute candles; carried forward through quiet minutes | not fills; no order-book depth history (settled books are empty) |
| Kalshi spread / total / props history | exists (spread ≈16.9k markets and total ≈14.8k from Oct 2025; team totals and half-game markets from Feb 2026; player props from Nov 2025) | same | not collected in this pass | not evaluated |
| Pregame priors (expected margin, total) | all labelled games | walk-forward by season | margin RMSE 12.9-14.5 by season, against 12.5-13.9 for the ESPN-embedded closing spread (measured: the spread is only 0.4-0.7 points better) | the embedded spread is not a sharp line (capture time unknown), so Model B's closing information is a modest upgrade, and the Kalshi pregame close is the better-timed one |
| On-court lineups | 94% of states | reconstructed stints | validated against ESPN box minutes (99.9% within a minute) | live lineups are not available from the scoreboard feed |
| Historical sportsbook live quotes | **not available** (no free source) | | | no sportsbook claim is made |

Times kept apart: event time (play-by-play wall clock), publication/collection time (Kalshi history retrieved 2026-10-29; ESPN files 2026-10-28), forecast time (state minute), execution time (assumed equal to the candle minute; a two-minute-late sensitivity is reported).

## 3. The model (Model A, independent of any market)

Final regulation margin = current margin + D, with D ~ Student-t. Mean = `a1*mu*x + am*m*x + aL*L*x`, scale `sqrt((exp(p0)+exp(p1)x)(1 + av(|m|/10)^2 x))`, x = share of regulation left, mu = pregame expected margin (ridge on Elo, recent net rating, rest, availability), L = on-court lineup rating difference. Total = current points + a Student-t remainder tied to pregame total, pace surprise and a late-game term; overtime is a mixture; margin and total share one joint distribution, so moneyline, spread and total prices are consistent. 200,000 draws per state keep simulation error at or below 0.001 in probability and it is reported separately from parameter uncertainty (bootstrap SD ≤ 0.6 points of probability) and calibration slack (RMS 1.4-1.5 points).

Two things were found while developing, on development data only. (1) A plain Gaussian random walk was over-confident at the extremes (a predicted 3% happened 4.9% of the time). The cause was not tail weight but **mean reversion in leads**: the fitted lead-dependent drift is −0.48 per unit of lead per share of game remaining, so a 13-point halftime lead is expected to shrink by about 3.5 points. With it, development calibration is on the diagonal. (2) On-court lineups add information to the independent model (−0.0025 log loss) but nothing once a closing line is used (+0.0001).

## 4. Evidence: independent versus closing-line-informed versus market

Log loss on identical states, lower is better; bootstrap resamples games.

| Window | Kalshi in-game price (C) | Model A (independent) | Model B_K (closing-informed) | A − C | B_K − C | b_m in the encompassing regression |
|---|---|---|---|---|---|---|
| Development, 697 games to 2026-01-31 (design only; exploratory) | 0.4725 | 0.4776 (availability prior) | 0.4724 | +0.0052 [−0.0025, +0.0132] | −0.0001 [−0.0040, +0.0043] | +0.51 (se 0.16) with b_k = 0.43 (se 0.19) |
| **Final, 488 games, 32,480 states (one pass)** | **0.3591** | 0.3725 | 0.3642 | **+0.0134 [+0.0034, +0.0233]** | **+0.0051 [+0.0005, +0.0097]** | **−0.007 (se 0.29), one-sided p = 0.51**; b_k = 1.23 (se 0.34) |

The encouraging development signal (the model carried independent information) did not replicate. That is a result about the design process as much as about the market: a model tuned on one window found structure that was not there out of sample.

Supporting findings (all development-window, exploratory unless stated):
- Pregame information is worth much less than the live state: Model A beats a pregame-only price by 0.149 log loss, and beats a state-only logistic by 0.032.
- Closing-line information improves the independent model (B_ESPN − A = −0.0107 [−0.0159, −0.0059]; B_ESPN − A with availability = −0.0055 [−0.0094, −0.0014]); Kalshi's own pregame close and the ESPN-embedded spread are equally good closing inputs (B_K − C = −0.0001, B_ESPN − C = −0.0003). Kalshi therefore duplicates the existing closing-line information; its extra value is the in-game price.
- Final window, by quarter and by distance from the close, Kalshi is better in every stratum, including the largest moves (>2 logit units from the close: Kalshi 0.0983, B_K 0.1027).
- Final window distributional calibration of B_K: the 50% and 90% margin intervals contain 50.9% and 89.7% of outcomes. Both Kalshi and the models were somewhat under-confident in this window (for example 96.6% predicted, 98.4% observed for the top bin), the opposite tilt from the development window, so there is no stable bias to exploit.

## 5. The market-correction and economic tests (final window)

| Test | Result |
|---|---|
| H2b: does the gap between price and model predict the market's own move over the next 10 minutes? | coefficient −0.077 (p = 3e-12), n = 30,040. The market does move toward the model's value afterwards. This is a diagnostic only: the model's lead-dependent drift predicts how scores evolve, and prices follow the score. It is not evidence of a profitable overreaction. |
| H2c: buy the better side at the ask (or NO at 1 − bid) when the conservative EV of B_K is positive, one signal per game per side per 10 minutes, hold to settlement, net of the Kalshi fee | 1,800 signals in 467 games: **−0.0238 per contract (95% interval −0.0485 to +0.0011)**; the model had predicted +0.0322 |
| Same signals before fees (exploratory) | −0.0121 [−0.0367, +0.0128]; mean fee 0.0117 |
| At the signal-time midpoint, no fee (exploratory upper bound for patient execution) | −0.0071 [−0.0318, +0.0179] |
| Executed one 2-minute step late (exploratory) | −0.0331 [−0.0579, −0.0090]; the price moved 0.95 cents against the trade |
| Where the loss sits | negative in every third of the window (−0.4, −3.8, −3.0 cents), on both sides (−2.4 cents each) and in every remaining-time bucket (−0.9 to −4.1 cents) |
| Why | on the signalled states the model said 53.0%, the outcome happened 42.8% of the time, and the average price paid was 44.0%: the largest disagreements between model and price are mostly model error |

Maximum drawdown over the 1,800 signals: 46.7 contracts (about 0.026 per signal). These are quote-based figures from candle bid/ask. They are not historical betting profit and say nothing about depth or fills.

By the pre-registered rule, overreaction is supported only if the model adds information (b_m > 0, interval excluding zero), the quote-based net return is positive with an interval excluding zero, and the sign holds in each third of the window. None holds, so it is **not demonstrated**.

## 6. Mathematical target prices and the worked example

For a YES contract at ask `a` with probability `p` and fee `f(a)`: EV = p − a − f(a); for NO at `1 − bid`: EV = (1 − p) − (1 − bid) − f. The Kalshi taker fee used is `ceil(0.07 × contracts × P(1−P))` to the cent (confirmed only from secondary sources; the official fee-schedule URL returned 404 and the schedule must be confirmed). The conservative probability is `p − 1·SE`, where SE combines parameter uncertainty and calibration slack, both measured, neither tuned. The highest acceptable price is the highest cent at which conservative EV is non-negative; below it the quote is theoretical. For sportsbook-style odds, EV = P(win)·profit − P(loss) with exact pushes on whole-number lines; fair and worst-acceptable American odds are solved from the same probabilities. The page accepts a hand-typed sportsbook quote; none is fetched.

Worked example (frozen B_K; Knicks home, closed −4.5; Detroit leads by 13 at halftime, 46-59; total prior 224):

| Bet | P(win) | Fair odds |
|---|---|---|
| Knicks moneyline | 24.4% | +310 |
| Knicks +4.5 (the live line) | 39.2% | +155 |
| Detroit −4.5 (live line) | 60.8% | −155 |
| Knicks −4.5 (the original line) | 13.6% | +635 |
| Knicks +7.5 | 51.1% | −105 |

The model's expected final margin is −7.1 for the Knicks: the −13 on the board, plus +2.4 from the pregame prior, plus +3.5 from the average shrinkage of leads. Its fair live line is therefore about Knicks +7, so a live Detroit −4.5 would be a 9-point move that the model considers *smaller* than the lead justifies (about 11.5 points). Highest Kalshi YES price still positive after fees and the uncertainty margin: 21 cents on the Knicks moneyline, 36 cents on Knicks +4.5. Given section 5, this is a statement about the model, not about the market.

## 7. Kalshi integration assessment

- **Supported and implemented:** the NBA game winner (`KXNBAGAME`), full-game spread (`KXNBASPREAD`, half-point strikes "team wins by more than X": no pushes) and total (`KXNBATOTAL`, "Over X.5"), valued from the same joint distribution. A "Knicks +4.5" bet maps to buying NO on "Detroit wins by more than 4.5". The moneyline settles on the official final result including overtime; postponements within 48 hours remain open.
- **Exists but not implemented:** team totals, quarter and half winners, spreads and totals (history from Feb 2026), and player props (points, rebounds, assists, threes, steals, blocks, PRA and combinations, double and triple-double, first basket, points leader, head-to-head; history from Nov 2025). Props stay with the independent player projections; Kalshi is an optional comparison only, and no synthetic prop market was created.
- **Data access:** all market data used is public and unauthenticated; the API key supplied in the request was neither needed nor written anywhere. Settled markets before 2026-08-30 live in a historical store; live endpoints hold later ones. One-minute candles carry bid, ask, last and volume; executed trades are available historically; order-book depth exists only for open markets (so the prospective collector records it).
- **Execution facts:** the moneyline book is liquid (tick 1 cent, thousands of contracts at the top for tonight's games). Fee is highest near 50 cents; at 100 contracts and a 50-cent price the taker fee is 1.75 cents, which is larger than the whole conservative edge the model usually claimed.
- **Does Kalshi add independent information?** As a pregame close, no: it matches the ESPN-embedded spread. As an in-game price, it dominates the models tested here.

## 8. The Live Value page

`Live Value` in the sidebar (`nba_xgb/live_value_page.py`, hooked into `app.py`). Three tabs. **Live games**: ESPN state with its retrieval time, the saved pregame priors, the Kalshi pregame close from today's capture, Model A and B fair prices, and a table of the moneyline, spread and total contracts with fair probability, model SE, bid/ask, EV per contract, conservative EV, the highest price still positive, a status (ACTIONABLE only with a fresh two-sided quote, a regulation state, a pregame close, and positive conservative EV; otherwise THEORETICAL or NO EDGE; "insufficient data" when priors or models are missing), plus a manual sportsbook-quote box. **Historical replay**: any recorded 2026 game with a minute slider, labelled as replay and as in-sample or out-of-sample for the frozen models. **Method and evidence**: this verdict and the pre-registration. Overtime is not priced; live lineups are not available from the scoreboard feed and are set to neutral. A page-level smoke test found and fixed a real bug (an expander nested inside an expander).

Prospective infrastructure, started and verified on the real feeds: `live_collector.py` (ESPN state and Kalshi moneyline book depth, plus the three spread and total strikes nearest 50%, every minute, hash-chained, read-only) is running for tonight's three games and idles until 90 minutes before the 8:00 pm ET tip; `run_pregame.py` is scheduled for 6:15 pm ET to refresh sources, collect the injury report and write the immutable pregame forecast (now including expected margin and total) before the 7:00 pm cutoff. Neither has produced output yet.

## 9. Tests

`tests/test_fair_value.py` (fees, EV identities, pushes, minimum prices, monotone spread probabilities, simulation versus closed form), `tests/test_live_value.py` (clock arithmetic, overtime and pre-tip handling, contract definitions, Knicks-style consistency, no look-ahead in state lookup, uncertainty floor, statuses), `tests/test_live_value_page.py` (the page inside the real app with mocked feeds, no ACTIONABLE without a pregame close, graceful missing data), plus the earlier leakage, verification-gate and availability tests.

## 10. Limits and what remains unproven

- 488 final-window games is small: the quote-based interval (−4.9 to +0.1 cents) does not exclude a very small positive return. The claim is "no evidence of an exploitable overreaction", not "none exists".
- Only the Kalshi moneyline was tested against history. Kalshi spreads and totals, team totals, half-game markets and props have history and were not evaluated. No sportsbook live quote exists in any free source, so no sportsbook claim is made.
- Prices are candle bid/ask, not fills; depth, queue position and latency are unobserved.
- The model is a calibrated statistical model of the remaining game. It is not a possession-level simulation, and it ignores live foul trouble, bonus status and intentional-foul regimes except through the late-game total term. A more detailed model was not justified by this evidence and was not built.
- Priors are weak (margin RMSE ≈ 14; the embedded closing spread is only about 0.5 points better), and player-availability and lineup information is limited to what the injury reports and ESPN feeds supply. Regular season only; playoffs untested.
- The prospective 2026-27 sample is empty so far. Until it has at least 500 games it is descriptive.
- The pregame-model items listed in section 1 remain unfinished.
