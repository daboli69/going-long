# Kalshi player props: pre-registration, step 0 (inventory and liquidity)

Written 2026-10-29, after listing which Kalshi series and markets exist (tickers, counts, open and close dates) and
before reading any price, spread, volume or trade. Read-only public data, $0, no trading code. Steps 1-5 are not
preregistered yet. They depend on this step's go/no-go, which Travis decides.

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
