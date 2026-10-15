# FantasyPoints data-to-model integration map

Written Oct 15 from repository code and recorded research only. **The licensed CSVs and the historical odds database were not
readable from the cloud session that produced this map** (they live on the owner's PC and in owner-authenticated private storage),
so nothing below was re-measured on the data itself. Counts such as "341 CSVs" are the owner's figures, unverified here.
Evidence statuses come from `research/trend-intelligence/fp_field_status.json` and `LEDGER.md`; consumers were checked in code
(`server/fp-model.mjs`, `server/fp-research.mjs`, `shared/fp-research.js`, `scripts/fp_ingest/`, `scripts/trend_research/`).

## What actually changes a number today

Only `server/fp-model.mjs` turns CSV values into a forecast: three families (`receiving_advanced`, `receiving_man_vs_zone`,
`coverage_matrix`) feed the research-only receiving-yards Challenger. It is not wired to production probabilities, betting
recommendations or DFS projections. All other families are descriptive notes (`server/fp-research.mjs`), prospective weekly captures
(`scripts/fp_ingest/weekly.py`, `trends.py`) or inputs to registered offline experiments (`scripts/trend_research/`).

## Family map (27 tables in `config/fantasy_points_tables.json`)

| Family (tables) | Live consumer | Changes a forecast? | Recorded evidence | Missing |
| --- | --- | --- | --- | --- |
| Receiving advanced (`receiving_advanced`) | Challenger routes/game and verified yards; weekly trend state | Yes, research Challenger only | E1/E3 16-feature bundle REJECTED; compact 3-feature set INCONCLUSIVE (E6, post-hoc) | In-season point-in-time weeks; 2026 Weeks 6-10 holdout |
| Man vs zone (`receiving_man_vs_zone`) | Challenger conditional yards/route | Yes, research Challenger only | Man x opponent-man interaction REJECTED (E4, 0 of 2 seasons) | Same-season 2026 coverage history; Challenger accuracy not measured |
| Coverage matrix (`coverage_matrix`, team) | Challenger opponent mix | Yes, research Challenger only | Same E4 result; 2021 scales differ | Same |
| Routes run, alignment (`receiving_routes_run`) | Weekly trend state, notes | No | Alignment mix REJECTED as predictor (E1/E3) | Weekly history |
| XFP / XTD (`efficiency`, `rushing_bell_cow`, `rushing_advanced`) | Notes | No | Adds nothing beyond raw target/carry volume or free ffopportunity (E2/E8/E8b) | Redundant source |
| Bell-cow shares, advanced rushing | Notes | No | REJECTED (E9); efficiency does not persist | Goal-line carry history |
| Run/pass report (team) | Notes, weekly state | No | REJECTED for next-season pass rate (E5, low power) | In-season pace/PROE point-in-time |
| Separation (alignment, break, coverage, route) | Notes | No | Untested as a predictor; some units unstable | A registered test on completed seasons |
| Passing advanced / depth (QB pressure, time to throw) | Notes | No | Untested (production already applies a QB pressure scale) | A registered test |
| Offense snaps incl. inside 5/10/20 | Notes | No | 2026 only | Prospective TD-role experiment |
| Line matchups, QB/WR coverage matchups (next game) | Stored per weekly state | No | 2026 only, forward-looking | Prospective capture and shadow evaluation |
| Basic box scores | Cross-checks | No | Redundant with nflverse | None |
| Nine opponent positional/defensive exports (DFS) | `shared/dfs-matchup-csv.js`, on device only | DFS research scenario only | Arithmetic and legality checked; no outcome test | Weekly point-in-time versions |

Archived copies and overlapping exports (season-to-date vs weekly vs historical full-season files) are not independent evidence. Past-season
files are full-season totals, never Week-N information inside their own season. Only accumulating 2026 snapshots support point-in-time use.

## What the existing research says the data does and does not do

The ledger found that the signals which helped the Champion were not FantasyPoints fields: a prior-strength blend (E7), free
ffopportunity expected points beyond raw volume (E8b, exploratory) and raw target/carry volume (E8). The anytime/first/last TD
scoring-role blocks (JP-2/3/4) and DK distribution work (P3-5..P3-9) are PROMISING on free data. FantasyPoints is the least additive
source tested so far. That is a recorded finding, not a conclusion about data never tested (separation, QB pressure, goal-line usage).

## Historical odds archive: what it can and cannot test

Verified filters are in `docs/HISTORICAL_ODDS_ARCHIVE.md`: 649 actual games, one pregame board per game about 30 minutes before kickoff for
moneyline/spread/total, sampled props. It has ten books, no Novig or Kalshi, and no 24h/6h/1h/close series, so it can score the sportsbook
probability and a model against a pregame price, not closing-line value. Missions' offline exporter and backtest (`scripts/missions_history_export.py`,
`scripts/missions_backtest.cjs`) already apply the actual-game and pregame gates for game lines.

## Blocked until the data is reachable

1. Verifying the dataset inventory, column coverage, duplicates and missingness on the real files.
2. Any new fit or ablation (separation, QB pressure/protection, goal-line usage, pace/PROE) and any Challenger accuracy number.
3. Matched-price comparison of football forecasts against de-vigged historical props.

## Next experiments worth freezing (hypotheses only, not frozen)

Frozen protocols must be written with the data in view; these are candidates, ordered by the existing evidence.

1. Receiving Challenger shadow evaluation: weekly immutable receipts for 2026 Weeks 6-10 against Champion, season average and matched price.
2. TD scoring-role (JP-2/3/4) with FantasyPoints inside-5/10/20 snaps and end-zone targets as point-in-time 2026 features, against the free-data blocks.
3. Separation and QB pressure as registered tests on completed seasons (prior-season to next-season only), with feature-family ablations.
4. Game lines: expected possessions and pace from `run_pass_report` against the market-anchored baseline; current model has no information beyond the line (research/calibration/GAME_LINES.md).
