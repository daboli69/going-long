# Data sources and provenance

Verified on 2026-10-16 by downloading from each endpoint. The lab records URL,
SHA-256, size, ETag/Last-Modified and download time for every file in
`data/raw/manifest.json`.

## Integrated

| Source | Endpoint | Used for | Notes |
|---|---|---|---|
| nflverse/nfldata `games.csv` | `https://github.com/nflverse/nfldata/raw/master/data/games.csv` | Schedule, scores, neutral site, roof, listed starting QBs, closing spread/moneyline/total | Primary schedule. Future games are listed with projected QBs close to kickoff. |
| nflverse-data `pbp` release | `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet` | Every team statistic (EPA, success, yardage, turnovers, sacks, third downs, red zone, pace) and QB EPA | 2015 is downloaded only for 2016 prior-season carryover. ~20 MB per season. |
| api.nfldata.org | `https://api.nfldata.org/v1/games` (public, no key, OpenAPI at `/openapi.json`) | Cross-check of final scores for the two latest seasons | It describes itself as the nflverse "gold layer". It is **not independent** of nflverse, so agreement only checks the download, never confirms the data. |

`nflverse-pbp` (the GitHub repo) builds the same play-by-play files published in the
`nflverse-data` `pbp` release. They are one source, counted once. nflverse
`schedules/games.csv` mirrors nfldata `games.csv`, so it is also counted once.

Refresh policy: completed seasons are downloaded once and reused. The schedule and
the live season's play-by-play are re-downloaded when older than 6 hours.
Play-by-play aggregation is cached by file hash.

## Investigated, not integrated

| Source | Why not |
|---|---|
| thadhutch/nfl-data-pipeline (redirects to `sports-quant`) | Scrapes PFF grades (paid subscription) and Pro-Football-Reference pages. The PFR content duplicates nflverse, and the PFF content breaks the $0 rule. |
| nflverse `injuries` | Report rows carry modification timestamps that can fall after kickoff. The lab has no reliable way to tell what was known pregame. |
| nflverse `ftn_charting` (pressure, etc.) | Coverage starts in 2022, so it cannot span the 2016+ training window. A Phase 1 feature would be missing for most training rows. |
| nflverse `stats_team`, `nextgen_stats`, `pfr_advstats` | Team stats are derived from the same play-by-play. NGS/PFR advanced stats are season- or week-level tables whose publication time is not recorded. Candidates for later work once availability timing is checked. |
| Weather (temp/wind in games.csv) | Values are observed at the game, not a pregame forecast. They would leak information. |
| Existing GOING `data/*.json` | Current-season snapshots for the website. No multi-season history and no timestamped odds archive was found in this checkout. |

## Odds caveats

The nfldata lines are consensus closing numbers with no per-line timestamp. They are
close to kickoff and therefore pregame. They are used **only** as a benchmark
(no-vig probability, spread MAE), never as model inputs. For upcoming games, the line
shown is whatever nfldata held at refresh time. 2016–2026 completed games all have
moneylines (one 2017 game lacks one).
