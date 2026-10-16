# Local scanner memory profile (2026-10-16)

Read-only investigation. No scanner restart, no `--send`, no provider call, no credential read, no application code changed.

## Finding

`pythonw.exe` running `scripts/run_local_scanner.py` swings between about 1.2 GB (floor) and 3.25 GB (OS peak) because every scan cycle calls `Journal.rows('prediction')` **four times**, and each call parses every prediction row ever stored.

| Evidence | Value |
|---|---|
| Live process (PID 11268, started 2026-10-12), 1 s samples, 90+ s | floor 1159-1213 MB, peaks 1.9-3.25 GB, `PeakWorkingSet64` 3255 MB (flat since start); several ramps per ~60 s scan, each ramp ~7-10 s |
| `private/topdown.sqlite` | 7.4 GB; kinds: closing 7.9 M rows, quote 1.27 M, **prediction 209,617 rows (~3.1 KB JSON each, ~650 MB text)**, reference 101 k, settlement 39 k |
| `rows_prediction` offline (harness below) | 6.9 s, **1,545 MB peak and held** |
| `rows_reference` / `rows_settlement` | 79 / 94 MB |
| `history.json` / `nfl_betting.json` / `results.json` parse | 75 / 41 / 24 MB peak |
| SQL id-only alternative (`ids_prediction_sql`) | 1.4 s, 27 MB |

Calls to `rows('prediction')` per scan (`scripts/scan_markets.py`, `settle_markets.py`, `topdown/tracking.py`): `track_predictions` (tracking.py:6), `settle` (settle_markets.py:15), `history_predictions` (scan_markets.py:104, held for the whole cycle), closing loop (scan_markets.py:128). `collect_board` adds two more (tracking.py:23) at least every 10 min. Peak = held `history_predictions` (~1.5 GB) + one transient copy (~1.5 GB) + ~100-200 MB of JSON snapshots = ~3.2 GB, matching the live peak. The 1.2 GB floor is the interpreter heap/allocator retaining freed pages plus the other loads; it did not creep during the sample window. I could not observe hours-long trends; `PeakWorkingSet64` has stayed at the same 3255 MB since 10-12, so there is no sign of a leak. The table grows about 1.9 k predictions/day, so the cost grows linearly.

Most of the loaded rows are dead weight: 160,092 of 209,617 predictions are `actionable=0` with no `tracking_group`. Every consumer ignores them: `settle` skips them, `track_predictions`/`collect_board` only read rows with `tracking_group`, the closing loop requires `actionable` or `tracking_group=='all_model'`, `feedback()` requires `actionable`. In fact **no stored prediction is `actionable=1`**, so `feedback()` currently contributes nothing. (Fact from the DB; whether that is expected needs the owner/Codex.)

Same code? The running checkout is `going-long` at `4f5164c`; `run_local_scanner.py`, `scan_markets.py`, `feed.py`, `inactives.py`, `journal.py` are byte-identical to this repo (`3958ed1`); `settle_markets.py` and `model.py` differ only in line endings. Verified with `diff --strip-trailing-cr`.

## Ranked fixes (not implemented; need owner/Codex approval)

1. **Filter in SQL** (biggest, low risk). Add `Journal.rows(kind, where=...)` or `prediction_rows(tracked_or_actionable=True)` selecting `WHERE kind='prediction' AND (json_extract(payload,'$.actionable')=1 OR json_extract(payload,'$.tracking_group') IS NOT NULL)`. Cuts parsed rows 209 k to ~50 k (~370 MB per call, ~4x). Same results for every consumer above because each one already discards the others.
2. **Id-only queries** for the "existing ids" sets (`track_predictions`, `collect_board`, `settle` existing): `SELECT id ...` or `SELECT json_extract(payload,'$.prediction_id')`, ~27 MB.
3. **Load once per cycle**: fetch the filtered predictions once in `scan()` and pass the list to `track_predictions`, `settle` and the closing loop (3 of the 4 loads disappear). Keep read order `observed_at`.
4. **Closing loop**: query only rows with kickoff in the next 600 s (store `kickoff` in a column or `json_extract(payload,'$.kickoff')` filter); it needs a handful of rows, not the history.
5. **Release before sleep**: `del history_predictions` and `gc.collect()` at the end of `scan()`; reuse parsed `history.json`/`nfl_betting.json`/`results.json` by mtime (they are loaded 2-3x per cycle, ~140 MB). Minor.
6. Separate issue, not memory: `journal.append` commits per row (millions of `closing`/`quote` rows); batch commits would cut disk churn. The 7.4 GB DB itself may deserve a retention/archival policy for `closing` and `quote`.

Expected result after 1+3: working set roughly 300-500 MB peak, floor under 300 MB (estimate from the harness numbers, to be re-measured).

## Test plan

- Unit: build a temp journal with mixed actionable / tracked / untracked predictions and assert the filtered query returns exactly the rows the old code's consumers kept (`settle`, `track_predictions`, `feedback`, closing loop produce identical journal writes before and after). Use the repo's existing mocks in `tests/`; no network.
- Equivalence replay against a **copy** of the journal (never the live file): run old and new `scan()` with stubbed network/send and diff the appended rows.
- Memory: `python scripts/profile_scanner_memory.py --db <copy> --data <scanner-data> rows_prediction ids_prediction_sql` before and after.
- Deploy: owner restarts the worker after review (needs approval; not done here).

## Harness

`scripts/profile_scanner_memory.py` (read-only `mode=ro`, no network, no scanner imports). Example:

```
python scripts/profile_scanner_memory.py --db <topdown.sqlite> --data <scanner-data> rows_prediction ids_prediction_sql history_json
```

## Needs approval

Any code change in `journal.py`/`scan_markets.py`/`settle_markets.py`/`tracking.py`, restarting the scanner, and whether to push this branch.
