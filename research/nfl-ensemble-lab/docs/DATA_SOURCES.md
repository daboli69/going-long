# Data sources and provenance

Phase 10 (2026-10-19): local GOING game/prop quotes and git history are archived
read-only with book/source/quote/observation times and content hashes. The freshest
committed copy is read via `git show origin/main:data/nfl_betting.json` after an
explicit fetch; the stale working-tree copy is preserved. Quotes >24 hours old
are labelled stale, and T1 requires verified pregame observation. No odds API,
credentials or paid service is used. Every Open-Meteo pull is archived with
retrieval/valid times (context only); official inactive-list parsing is reused
read-only. Details and manual scheduling: `docs/PHASE10_DATA_ARCHIVE.md`.

Verified on 2026-10-16 by downloading from each endpoint. The lab records URL,
SHA-256, size, ETag/Last-Modified and download time for every file in
`data/raw/manifest.json`.

## Integrated: model inputs

| Source | Endpoint | Used for | Pregame validity |
|---|---|---|---|
| nflverse/nfldata `games.csv` | `github.com/nflverse/nfldata/raw/master/data/games.csv` | Schedule, scores, neutral site, stadium, closing lines | Scores only for prior games. Lines are a benchmark, never a feature. Listed starting QBs are **not** used as features (since Phase 1.5). |
| nflverse-data `pbp` | `.../releases/download/pbp/play_by_play_{season}.parquet` | Team stats, EPA, QB EPA, previous-game starter | Aggregated from games before kickoff only. |
| nflverse-data `injuries` | `.../releases/download/injuries/injuries_{season}.parquet` | Official NFL game-status designations and practice participation | **2016–2024:** each row has `date_modified`; rows modified at or after kickoff are dropped (0–0.3% per season). **2025:** the file has no row timestamps, so it is excluded. **2026+:** used only from snapshots the lab archives with its own download time before kickoff. |
| nflverse-data `snap_counts` | `.../releases/download/snap_counts/snap_counts_{season}.parquet` | Player role = mean snap share over his last 4 games before kickoff | Postgame stats of earlier games only. |
| nflverse-data `players` | `.../releases/download/players/players.parquet` | ID map (gsis ↔ pfr ↔ espn) and names | Static identifiers. |

## Integrated: live monitoring only (never model inputs)

| Source | Endpoint | Shown as |
|---|---|---|
| ESPN public injury feed | `site.api.espn.com/apis/site/v2/sports/football/nfl/injuries` (no key) | Out/IR/Doubtful lists and a cross-check of the projected QB's status. It includes IR and transactions-style statuses the official report lacks. It has no validated history, so it is excluded from models. |
| nflverse `depth_charts` (2025+) | `.../depth_charts/depth_charts_{season}.parquet` (daily ESPN snapshots, `dt` timestamp) | Current QB1 cross-check. |
| api.nfldata.org | `/v1/games` | Score cross-check. It is derived from nflverse, so it is not independent evidence. |

## Investigated, not integrated

| Source | Why not |
|---|---|
| nflverse depth charts 2016–2024 | Weekly team-released charts without publication timestamps. "Pregame by process" cannot be verified, so they are excluded from history. |
| nflverse weekly rosters / transactions | Season-week roster status is recorded retrospectively without timestamps. |
| Official NFL.com / team injury pages | Same content as the official report already ingested through nflverse. Scraping HTML adds fragility without new information. |
| Starting-QB announcements (press) | No free, timestamped, machine-readable archive. Projected starters come from the rule below. |
| thadhutch/nfl-data-pipeline (`sports-quant`) | PFF grades require a subscription; the PFR data duplicates nflverse. |
| FTN charting (pressure) | Coverage only from 2022. |
| Weather (games.csv temp/wind) | Observed at the game, not forecast. |
| Game-day roof open/closed | Decided near kickoff. Replaced by the static stadium roof type. |

## Projected starting QB (pregame rule)
1. The starter (most dropbacks) of the team's previous completed game.
2. If a verified pregame official report lists him Out or Doubtful: the team's other QB with
   the most dropbacks for the team this season and last; otherwise an unknown replacement
   (replacement-level efficiency prior).
3. The first game of a season uses last season's final starter (`qb_offseason` = 1, an uncertainty flag).

As a diagnostic only (not used anywhere), the projection matches the recorded starter in
88% of 2016–2026 games. The other 12% is real pregame uncertainty (offseason moves,
benchings, late scratches) that the old feature hid by using the actual starter.

## Archive
Every refresh that sees a changed live injury file stores
`data/raw/archive/nflverse_injuries_<UTC download time>_<hash>.parquet`, and each ESPN fetch
is stored as JSON. These archives become the lab's own timestamped injury history for
2026 onward. **Keep this folder.** Deleting it destroys history that cannot be re-downloaded.
