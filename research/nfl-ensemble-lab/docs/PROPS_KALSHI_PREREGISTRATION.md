# Kalshi player props: pre-registration, step 0 (inventory and liquidity)

Written 2026-10-29, after listing which Kalshi series and markets exist (tickers, counts, open and close dates) and
before reading any price, spread, volume or trade. Read-only public data, $0, no trading code. Steps 1-5 are
preregistered below (written after Travis chose "go" on 2026-10-29, before any replay, fit or price beyond step 0).

## Inventory already observed (no prices)
`data/cache/kalshi/player_inventory.parquet`. Per-game player ladders: KXNFLRECYDS (22,595 markets, 331 events),
KXNFLREC (16,633 / 269), KXNFLRSHYDS (11,214 / 326), KXNFLPASSYDS (5,825 / 350), KXNFLANYTD (5,482 / 285), KXNFLPASSTDS
(1,832 / 238), plus attempts, completions, interceptions, combined yards and ladder/escalator variants. Game environment:
KXNFLTOTAL (9,283 / 471), KXNFLSPREAD (11,897 / 471), KXNFLTEAMTOTAL. *Correction (same day, from the step-0 run):* the
yardage and reception ladders also cover **2025 from October onward**. About 10,000 archived markets carry no close
time, and the first inventory's date summary skipped them.

## Liquidity filter (fixed now)
A threshold market is **liquid at a point P** if its latest hourly candle ending at or before P has:
- yes bid >= 0.02 and yes ask <= 0.98;
- ask - bid <= 0.05;
- volume summed over the 24 candles ending at or before P >= 500 contracts.

A player-stat ladder is liquid at P if at least 3 of its thresholds are liquid. **P = kickoff minus 90 minutes**
(decision time).

## Measurement
- **Sample:** regular-season games only (matched through the KXNFLGAME event code). Up to 400 markets per series, seed
  0, from KXNFLRECYDS, KXNFLREC, KXNFLRSHYDS, KXNFLPASSYDS, KXNFLANYTD, KXNFLPASSTDS, KXNFLTOTAL and KXNFLSPREAD.
  Candles come from the 48 hours before kickoff.
- **Report:** per series, the spread and 24-hour volume distribution at P, the share of liquid markets with a Wilson 95%
  interval, and the estimated number of liquid ladders per game. Also record each series' settlement rules text from
  the market's `rules_primary` / `rules_secondary`.
- **Thin rule:** per-game props are **too thin** for steps 1-5 if, for every yardage or reception series, fewer than
  25% of sampled markets are liquid at P, or fewer than 2 liquid ladders per game are expected. Then stop and report.

## Step 0 results (2026-10-29, `scripts/kalshi_props_step0.py`, `reports/kalshi/props_step0.json`)
Liquid at kickoff minus 90 minutes (bid >= 0.02, ask <= 0.98, spread <= 0.05, 24-hour volume >= 500), 400 sampled
markets per series:

| Series | Games | Liquid share [Wilson 95%] | Median spread | Median 24-hour volume | Estimated liquid markets per game |
|---|---:|---|---:|---:|---:|
| KXNFLPASSYDS | 309 | 28% [24%, 33%] | 0.03 | 116 | 5.1 |
| KXNFLRSHYDS | 305 | 26% [22%, 30%] | 0.02 | 84 | 7.7 |
| KXNFLRECYDS | 310 | 21% [17%, 25%] | 0.03 | 18 | 12.4 |
| KXNFLREC | 254 | 21% [17%, 25%] | 0.03 | 0 | 12.4 |
| KXNFLPASSTDS | 219 | 32% [28%, 37%] | 0.02 | 218 | 2.6 |
| KXNFLANYTD | 270 | 39% [35%, 44%] | 0.04 | 550 | 7.5 |
| KXNFLTOTAL | 392 | 44% [39%, 48%] | 0.02 | 291 | 7.8 |
| KXNFLSPREAD | 392 | 55% [50%, 60%] | 0.01 | 916 | 9.3 |

- **Thin rule: not triggered.** Passing and rushing yards are above 25%, and every ladder series has at least 2
  estimated liquid ladders per game. The margin is small: receiving yards and receptions are at 21%, with a median
  24-hour volume of 18 and 0 contracts.
- **Coverage:** yardage and reception ladders exist for games from October 2025 to January 2026, plus 2026 weeks 1-8.
- **Settlement (market rules text):** "If a player is active but never takes a snap, the market settles to the last
  fair market price before game start." Such markets have no event outcome and must be excluded from scoring. The
  rules text names no stat source, does not mention overtime (presumably included), and does not cover inactive
  players or stat corrections. The full contract terms were not read.
- **Blocker for steps 1-5:** the lab's props simulator (`lab/props`) has archived 1 game prospectively (2026 week 6)
  and has no historical projections. Its game inputs are undated `games.csv` lines. Walk-forward scoring first needs a
  historical, as-of re-run of the simulator. **Go/no-go is Travis's decision.**

# Steps 1-5 (preregistered 2026-10-29, before any replay, fit or price beyond step 0)

Travis chose the full historical rebuild. Everything runs locally. Codex's `lab/props` code is called, not edited.
The as-of replay lives in a new module, `lab/props_kalshi.py`.

## Scope
- Regular-season games with Kalshi player ladders and a Kalshi game environment at T-90: 2025 from October (week 5
  on) and 2026 weeks 1 to the latest completed week.
- Stats: `pass_yds`, `rush_yds`, `rec_yds`, `rec` (the simulator's four). Ladders: KXNFLPASSYDS, KXNFLRSHYDS,
  KXNFLRECYDS, KXNFLREC.
- **Scored rows:** (player, stat, threshold) rows in ladders that are liquid at T-90 (the step-0 filter), with a Kalshi
  result of yes or no. "No-snap" markets settle at a price and are excluded.

## 1. Raw data
- **Candles:** 7 days before kickoff to kickoff + 5h, for every scope market.
- **Trades** (`/markets/trades` and the historical equivalent) for every market liquid at T-90. Report how often the
  last trade before T-90 lies inside that candle's bid/ask.
- **Players:** matched to gsis IDs through `roster_weekly` (team plus normalized name). Unmatched players are reported
  and dropped.
- **Settlement:** Kalshi `result` vs the official stat computed from nflverse play-by-play with the lab's
  `lab.props.evaluate` actuals (stat >= threshold). Every disagreement is reported and nothing is edited. Scoring uses
  **Kalshi's settlement** as the outcome.

## 2. Market-implied distributions
For each ladder at T-90 and at the close (latest candle ending at or before kickoff), the threshold mids give
P(X >= k). Isotonic regression (non-increasing in k, weighted by 1/spread) makes them monotone. The market CDF is
defined only at the ladder's own thresholds. No extrapolation.

## 3. Game environment (the two simulator arms)
Both arms call the existing v2 simulator (`lab.props` sim, `calibrate_v2`, `V2.correct`, 10,000 runs, seeds as in
`lab.props.weekly`). Only the implied team points differ:
- **K (primary):** home margin and total medians from Kalshi at T-90. KXNFLSPREAD (both teams' ladders) and KXNFLGAME
  (the P(home win) point at margin 0) form an isotonic CDF of the home margin. KXNFLTOTAL forms an isotonic CDF of the
  total. Each median is linearly interpolated at 0.5. Implied points: home (total + margin) / 2, away (total -
  margin) / 2. A game whose ladders do not bracket 0.5 is excluded.
- **A (current):** the simulator's current input, `games.csv` `spread_line` and `total_line`. These are undated and
  probably closing lines, so **A may carry look-ahead.** A is descriptive and cannot pass anything.

For both arms: the QB is the most recent previous starter (never `games.csv`'s listed QB, which is the actual starter).
Availability is the game-week ACT roster from `roster_weekly`. Official inactives are published about 90 minutes before
kickoff, but the file is untimestamped (flagged). Model fits use seasons before the replayed season and play-by-play
of earlier weeks only, exactly as `lab.props.weekly`. v1 is also produced and reported descriptively. The naive
baseline is the existing "base" (recent-average) version.

## 4. Scoring (one look)
- **Ladder CRPS** per (player, stat, ladder) = sum over its liquid thresholds of (P_source(X >= k) - 1[result yes])^2.
  Simulator and base probabilities come from their quantiles, interpolated at k - 0.5.
- **Family G** (ladder CRPS, Bonferroni m = 3, 98.33% week-cluster CIs): K vs base (**primary**: K must beat base);
  K vs market at T-90; A vs K.
- **Family S** (stack, per threshold): logistic regression on logit(market at T-90) and logit(K). K adds value only if its
  weight's 95% week-cluster CI is above 0.
- **Family C** (CLV): move = market close - market T-90 per threshold; side = sign(K - market T-90). K passes if the mean
  CLV 95% CI is above 0 and the one-sided sign test p < 0.05. Base is the control and reported alongside.
- **Descriptive:** per-threshold log loss, PIT of the realized stat within each source's ladder CDF, the market close's
  ladder CRPS, and the v1 arms.
- Bootstrap: 2000 draws, seed 0, clustered by (season, week).

## 0b. Power (pilot, committed before the scored replay)
Replay arms K-free (A only) on 2025 weeks 1-4, which have no Kalshi player ladders and are never scored. Build
pseudo-ladders at each stat's typical Kalshi thresholds (pass 200/225/250/275/300, rush 40/60/80/100, rec yds
40/60/80/100, rec 3/4/5/6). Take the SD of week-mean (sim - base) ladder-CRPS differences per player-ladder and the
expected number of scored ladders per week from step 0. Report the MDE for the scored window and the weeks needed
for SESOI = 2% of the base's mean ladder CRPS. No prospective verdict before that many weeks.

## 5. Proof
Weekly sealed freezes of prop distributions (both arms, the market ladder at freeze, SHA-256 ledger pushed). Kalshi
settlement is the outcome source. The gate stays provisional until Codex rebuilds it from this document. Results and
freezes go on the Home-Win Research page (Props tab).

## Power results (pilot, 2026-10-29, before the scored replay)
`reports/props_kalshi/power.json`. Pilot: 2025 weeks 1-4, arm A v2 vs base, 1,337 pseudo-ladders. Mean
ladder CRPS: base 0.7173, v2 0.6691. Expected scored ladders per week:
176. SESOI (2% of base) = 0.0143. **History MDE over 21
scored weeks = 0.0297**, so the backtest can detect only effects about twice the SESOI.
**N = 90 frozen weeks** before any prospective family-G verdict.
