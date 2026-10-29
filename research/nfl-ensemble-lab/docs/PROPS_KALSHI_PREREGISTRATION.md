# Kalshi player props: pre-registration, step 0 (inventory and liquidity)

Written 2026-10-29, after listing which Kalshi series and markets exist (tickers, counts, open and close dates) and
before reading any price, spread, volume or trade. Read-only public data, $0, no trading code. Steps 1-5 are not
preregistered yet. They depend on this step's go/no-go, which Travis decides.

## Inventory already observed (no prices)
`data/cache/kalshi/player_inventory.parquet`. Per-game player ladders: KXNFLRECYDS (22,595 markets, 331 events),
KXNFLREC (16,633 / 269), KXNFLRSHYDS (11,214 / 326), KXNFLPASSYDS (5,825 / 350), KXNFLANYTD (5,482 / 285), KXNFLPASSTDS
(1,832 / 238), plus attempts, completions, interceptions, combined yards and ladder/escalator variants. Game environment:
KXNFLTOTAL (9,283 / 471), KXNFLSPREAD (11,897 / 471), KXNFLTEAMTOTAL. **The yardage and reception ladders start at the
February 2026 Super Bowl.** For the regular season they cover 2026 only. Anytime TD, total and spread reach back into
2025.

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
