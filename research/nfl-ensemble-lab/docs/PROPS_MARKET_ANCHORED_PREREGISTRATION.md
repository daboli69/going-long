# Market-anchored player props: pre-registration

Written 2026-10-29, after reading Kalshi's public contract terms and fee documentation and after the earlier Kalshi props
study (`docs/PROPS_KALSHI_RESULTS.md`), and before any model in this study was fit. Local only, $0, read-only Kalshi
data, no trading or order code, no new sports. Nothing is promoted. No scheduled task is added without Travis's approval.

**Question.** What do the lab's simulator and availability data add to Kalshi's own prop prices at kickoff minus 90
minutes (T-90)?

**Reuse disclosure.** The history backtest below uses the same 20 weeks and 6,654 thresholds that the earlier study scored.
That study already found a simulator blend weight near 0.2, so these history numbers are **descriptive**. Only the
prospective freezes can pass anything.

## Contract and fee facts (read 2026-10-29)
- **Settlement (`FOOTBALLENTITYSTAT` terms):** the underlying is the official league attribution. **Overtime counts** unless the
  market says otherwise. A player must take at least one play, or all of his contracts settle at "the last fair price as
  determined by the Exchange". Those markets are excluded from scoring. League stat corrections after the game **do not
  change** the contract; revisions after expiration are ignored.
- **Fee:** the entity-stat series use Kalshi's `quadratic` fee type with multiplier 1. Kalshi's worked example (price
  $0.055, fee $0.003638) matches **fee per contract = 0.07 x price x (1 - price)**, paid by takers. The official fee-schedule
  PDF returned HTTP 429, so the 0.07 coefficient is verified only through that example.
- **Order book:** `/markets/{ticker}/orderbook` is public and needs no signing. Historical books are not available.

## 0. Power (computed first, committed before any model fit)
Semi-parametric simulation using the real correlation structure. For each comparison, take the observed per-ladder (or
per-threshold) paired differences from the 20 scored weeks. Resample **whole weeks** with replacement to build samples of W
weeks (games stay intact inside their week), subtract a known improvement delta from every difference, and run the same
week-cluster bootstrap test (2000... see below) at the comparison's alpha. Power = share of 300 resamples whose upper bound
is below 0. **MDE(W)** = smallest delta with power >= 0.80, on a grid. Bootstrap draws per test: 500.

Proxy differences, used only to estimate variance structure: corrected = a logit blend with b = 0.2 between market and
simulator (the earlier stack weight); existing stack = the earlier two-weight logistic stack.

| Comparison | Metric | alpha | SESOI |
|---|---|---:|---:|
| M1 corrected vs market (primary) | ladder CRPS | 0.05/3 | 1% of the market's mean ladder CRPS |
| M2 corrected vs simulator | ladder CRPS | 0.05/3 | same |
| M3 corrected vs existing stack | ladder CRPS | 0.05/3 | same |
| L1-L3 | per-threshold log score, same three | 0.05/3 | 0.005 |
| E information events | CLV difference, corrected minus naive base, event games only | 0.05 | 0.005 |

For E the event rate is unknown, so MDE is reported for event rates 3%, 5%, 10% and 20% of games, assigning events to
random games and injecting delta into the event games' differences. For each comparison, report the MDE for the 20 scored
weeks and for W = 40, 60, 90 and 150, and **N_weeks** = smallest W with MDE <= SESOI.
**Decidable now** = MDE(20) <= SESOI. **Prospective only** = N_weeks <= 150 (about 9 seasons). Otherwise **not decidable**.
Committed: no verdict on a comparison before its N_weeks of frozen data.

## 1. Rawest data, collected prospectively (read-only; manual commands)
`scripts/props_kalshi_collect.py`:
- Kalshi trade prints (price, size, taker side, time) for every NFL player-prop market with 24-hour volume above zero, for
  games kicking off in the next 4 days.
- Order-book snapshots, with the capture time stored, for those markets. Capture points are three: kickoff minus
  3 hours, 90 minutes and 30 minutes, each with a 15-minute tolerance. Anything outside a window is stored as unlabeled.
- Official inactives through `lab.inactives10.collect` at T-90, and injury reports through `lab.availability`
  (its archive keeps its own retrieval times).
- All archives use `lab.archive10.save` (write-once, SHA-256).
- Report what could not be collected. Historical books and inactives before 2026-10-29 do not exist.

## 2. Market-anchored correction (per stat, walk-forward)
For a threshold with market price m (mid of the latest candle at T-90) and simulator probability q (K arm, v2):

`p = sigmoid( logit(m) + b * ( logit(q) - logit(m) ) )`, with **b in [0, 1]** per stat.

b is fit by penalized logistic loss (L2 penalty 10 * b^2, offset logit(m)) on all earlier scored thresholds of that stat, with
a minimum of 500 training thresholds. Weeks without enough history use b = 0. Every compared model is scored only on weeks
where the correction is fitted. Comparators: the market alone (b = 0), the simulator alone (b = 1), and the **existing
stack**: a pooled two-weight logistic regression on logit(m) and logit(q), refit walk-forward on the same earlier rows.
Prospective extension: availability features known at T-90 (key player Out or Doubtful, QB change) are logged
with every freeze. They are not part of the history fit, because the replay had no timestamped availability. A later
protocol amendment must preregister any feature before it is used.

## 3. Information events (prospective only)
An **event** is a game where a QB, RB1 or WR1 (by prior-season snaps) on either team appears as Out or Doubtful in an
injury or inactive record observed after the previous Kalshi candle used for the T-90 price. The test is the mean CLV
difference, corrected minus naive base, on event games (CLV = move from T-90 to the close, signed by the model's side;
timing refined with trade prints). Passes if the 95% game-and-week-cluster CI is above 0 and the one-sided sign test has
p < 0.05. Not run on history, because no timestamped availability was archived.

## 4. Coherence (descriptive; failures are reported, not patched)
- **Ladder exceedance bias:** for each liquid ladder, sum over its thresholds of P(X >= k): simulator minus market, by stat.
- **Pass-yard identity:** within each simulated team-game, the sum of eligible receivers' mean receiving yards against the
  QB's mean passing yards. Eligible receivers are a subset, so the ratio should sit at or below 1.
- **Not testable with public Kalshi data:** market-implied same-game correlations (no joint markets) and team-total ladder
  agreement (would need about 3,000 more candle pulls; deferred).

## 5. Cost (descriptive; no trading code)
For each scored threshold, the cost to cross the book is the half-spread plus the fee 0.07 * a * (1 - a) at the traded
side's price. Report the share of thresholds where |corrected - market| exceeds that cost, and the mean of
(outcome - price) on those thresholds **marked at the posted T-90 quote**, with a cluster CI. This is not a return:
fills, depth, size and slippage are not modeled.

## Scoring and placebo
- Ladder CRPS = sum over a ladder's liquid thresholds of (p - y)^2. Per-threshold log score as a second metric.
- Bootstrap: 2000 draws, seed 0, clustered by (season, week). Games are nested inside weeks, so this covers within-game
  and within-week correlation. A game-level cluster interval is reported as a sensitivity check.
- Bonferroni m = 3 within each of the M and L families.
- **Placebo:** within each (game, stat, threshold value) group with two or more players, shuffle the simulator
  probabilities across players, refit and score walk-forward, 200 permutations (seed 0). The real M1 delta is credible only
  if it lies below the 5th percentile of the placebo distribution. Report the permutation p-value.

## Proof
- Kalshi settlements are the outcome source; players with no snap are excluded.
- **Weekly freeze** (`scripts/props_kalshi_collect.py freeze`): simulator quantiles (K arm), the fitted b, corrected
  probabilities, the Kalshi ladder with bid, ask and volume at the same instant, and availability features, saved
  write-once with SHA-256 in the pushed ledger.
- **Reproduction:** Codex rebuilds this study and the four earlier ones (deep home-win, v2, drive simulator, Kalshi
  props) from their protocol documents. The requests and expected numbers are in `docs/CODEX_REPRODUCTION_REQUEST.md`.
  Gate readings stay provisional until the numbers match.
- No promotion without the Champion/Challenger gate and Travis's approval.
