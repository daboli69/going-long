# Fantasy Points Data Suite ingestion

Local importer for the paid Fantasy Points Data Suite CSV exports. Code, the table registry and these docs are in the repo;
**the data is not**. The repository is public and the exports are licensed, so `FantasyPoints/` is gitignored and nothing in
the importer publishes a licensed value. Only `--publish-status` writes a metadata-only file (table names, week, state).

## Tuesday workflow

1. Download the Fantasy Points exports and drop them in `FantasyPoints/Inbox` (any filename, any number of files).
2. Run `python scripts/fantasy_points.py import`.
3. Read the printed report: freshness per table, files that were held, unmatched players, columns to review.

Nothing to rename, move, combine or label. The Inbox is never modified or emptied; re-running is safe (identical files are
recognised by checksum and skipped). The exit code is 0 even when a file was held so the rest of a GOING refresh continues;
add `--strict` for a non-zero exit. `status`, `inventory`, `verify` and `fields` are read-only.

The folder is found from `--root`, `GOING_FP_ROOT`, `<repo>/FantasyPoints`, then `../GOING/FantasyPoints`.

## Layout (`FantasyPoints/`)

```
Inbox/                      your downloads (untouched)
raw/<season>/through-week-NN/<table>__<sha12>.csv   immutable copy of a live season-to-date export
raw/<season>/full-season/...                        a finished season (games >= 16)
raw/_unrecognized | _rejected | _quarantine/        preserved bytes of files that could not be imported
normalized/<season>/<table>/<scope>__<sha12>.json   GOING-facing rows
identity/roster_<season>.csv                        public nflverse roster cache (identity source)
manifests/index.json  freshness.json  last_run.json
```

The manifest is written last, atomically. A crash leaves only content-addressed files, which the next run reuses; stray
`*.tmp` files are removed at the start of each run.

## What an export is (found from the real files)

Every export is a **season-to-date** table with a two-row header (group row, column row), data rows, one blank line and a
glossary footer. There is **no week column and no week in the filename**. The only week information is `G` (games played),
so GOING records `through_games = max(G)`. That equals the week until all teams have had their bye (week 14), after which
`through_week` is left empty and only `through_games` is used. Consequences:

* A week-range or single-week export (`G` all 1) would be indistinguishable from a Week 1 export; it shows up as STALE
  against the expected week instead of passing as current. `--through-week N` lets the operator state the truth.
* A season-to-date export **cannot** be decomposed into weekly observations (rates cannot be differenced and only one
  snapshot exists). Weekly history therefore accumulates prospectively: each Tuesday's capture is kept as its own
  `through-week-NN` snapshot. Nothing is invented.
* A finished season downloaded later is a `full_season` snapshot (17 games). A past-season file with fewer is held
  (`held_scope`) until someone says what it is. Between February and June the just-finished season is treated as a past one.
* `--through-week N` only applies to files not imported yet, only to the current in-season export, and is capped at the
  number of games that can have been played; it never rewrites an existing snapshot.

## Detection and protection rules

| Situation | Behaviour |
| --- | --- |
| Table type | decided by the column signature, not the filename |
| Unknown columns/table | `_unrecognized`, reported, nothing normalized |
| Missing, renamed or retyped column | `_quarantine`, previous valid snapshot stays current, reported |
| Added column | imported, flagged `imported_review`, column class `UNREVIEWED` until classified |
| Season after the current one, or more games than can have been played | rejected |
| Ragged/truncated rows, bad encoding, no header | `_rejected` (bytes preserved) |
| Few teams (filtered or partial download) | status `partial`; never counts as current; absence means unknown |
| Same bytes again | `duplicate`, no new files |
| Same season/table/week, different bytes | explicit `revision`; both stay archived. The newer **download time** (file modified time, not filename or processing order) is current; an older download arriving later is `older_revision_ignored` |
| Damaged or deleted archive/normalized file | re-created from the Inbox copy (`repaired`); the revision chain and known-at time never change |
| Surprising cell (`G` = `N/A`), blank line in the data, blank first line | file rejected and preserved, never a crash or silent row loss |
| Another import running / leftover locked `.tmp` | lock file stops a second run; a locked temp file is reported, not fatal |
| Partial re-export of a week already imported completely | complete snapshot stays current |
| Blank cell | `None`, never 0 |

## Identity

Canonical player id is the nflverse `gsis_id` already used across GOING. Team codes map to nflverse (`ARZ→ARI`, `BLT→BAL`,
`CLV→CLE`, `HST→HOU`). Matching is deterministic: name+team+position, then name+team, then name+position league-wide (trade or
stale roster, flagged for review), then first-initial+last name within team+position, then explicit aliases from
`config/fantasy_points_aliases.json` if one exists. Anything with two candidates is `ambiguous`, anything without is
`unmatched`; both keep `player_id: null` and are listed in the report. There is no fuzzy matching. `scripts/fp_ingest/identity.py`
takes plain roster rows so the prop-name matching work can reuse it rather than add a second resolver.

## Freshness

`expected games = roster week - 1` from `data/nfl_roster.json` (override with `--expected-through`). Per table: `current`,
`stale`, `partial`, `missing`, `quarantined`. A missing or stale table is never evidence about a player.

## Leakage model

`store.point_in_time(manifest, snapshot_season, table, for_season, for_week, known_by)` is the only sanctioned way to read
snapshots for a backtest or prediction. `known_by` is required for same-season lookups (it raises without it). `first_imported_at`
is the **known-at** time: when GOING first accepted the data, not when it first saw a file it then rejected or held.

* same season: only a snapshot **captured live** (`known_live`) with all its games before the target week, imported by
  `known_by`; forward-looking matchup tables (`OPP`, OL/DL matchups) only for the single week they were made for;
* a retrospective export of the same season is never eligible inside that season;
* a finished season is eligible for later seasons only. It was downloaded later, so it can contain Fantasy Points
  corrections made after that season; this is the one accepted look-back imprecision;
* a correction imported after `known_by` is invisible before it, and a partial re-export never hides a complete snapshot;
* once every team has had its bye (14+ games) one extra week is held back because games and week number stop lining up;
* no snapshot returns `None`, never zero.

**Research implication:** within-season, point-in-time Fantasy Points features exist only from 2026 forward (one capture per
week). The 2021-2025 downloads are full-season totals; they support prior-season to next-season research, not walk-forward
intra-season backtests. `MODEL_RESEARCH` and QA must audit this before any Fantasy Points feature touches a Champion model.

## Model boundary

Field classes live in `scripts/fp_ingest/fields.py` and `docs/FANTASY_POINTS_FIELDS.md`. Nothing here is read by a model,
GOING Rating, ABBEYS or the ranking policies. Predictive use goes through hypothesis, historical test, chronological OOS,
calibration, Champion comparison, human approval.

## Tests

`python -m unittest discover -s tests -p "test_fantasy_points_ingest.py"` (80 tests, synthetic fixtures built from the real
registry; includes regression tests for every defect the independent QA review found). `GOING_FP_ROOT=<folder>` adds a test that every real export is recognised with the current schema. The
`ProtectionRemovalTests` class switches each critical protection off and requires the guarding scenario to fail.

## Rollback

The importer is additive and reads/writes only `FantasyPoints/`; no GOING data, model or workflow depends on it yet, so
reverting the branch is enough. **Do not delete `raw/` or `manifests/index.json`**: `raw/` is the only copy of earlier
weeks once you overwrite Inbox files, and the manifest is the only record of when each file became known (needed for
leakage-safe backtests). `normalized/` can be rebuilt by re-running the import with the originals in the Inbox.

## Historical exports (2021-2025)

A file reports how many games it covers (`G`) but not how it was filtered in Fantasy Points, so **nothing is inferred** for past
seasons:

| What you downloaded | Command | Stored as | Usable for backtests |
| --- | --- | --- | --- |
| A full finished season (G reaches 17) | `import` | `full-season` | next season onward only |
| Cumulative weeks 1-N, if Fantasy Points lets you pick them | `import --declare cumulative --only "<pattern>"` | `cumulative-through-game-NN` | **yes**: point-in-time by content (games through N), whatever the download date |
| One single week, if offered | `import --declare week:N --only "<pattern>"` | `week-NN`, `weekly_entries()` | stored as true weekly observations; never summed or served as cumulative |

A declaration always names its files with `--only` (a filename pattern, e.g. `--only "2023_wk*"`); it is refused without one and
never touches other Inbox files. Run it once; the files stay archived and plain `import` afterwards treats them as duplicates.
Without a declaration a partial past-season file is held (`held_scope`) with these instructions. A one-game file declared
`cumulative` is refused (`cumulative_ambiguous`): every single week looks like that, so declare it `week:N` (`week:1` for the
opener). Declare only what you filtered in Fantasy Points; a 2-week range (G=2) cannot be told from "weeks 1-2" by the file.

## Known limits

* A "last N weeks" export of the current season carries no marker; it is read as season-to-date through N games and shows
  as STALE, not as an error. Export full season-to-date tables.
* Weekly history before 2026 is not reconstructible with point-in-time fidelity (see Leakage model).
* Registry glossary text is not committed (vendor text); it lives in the archived raw files.
