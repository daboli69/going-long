# Public tracker store

`data/public_tracker/` holds the primary football tracking log. It replaces the single
`data/public_tracker.json`, which grew past what GitHub (100 MiB per file) and the snapshot API
(4.5 MB responses) can carry. Nothing about the records changed: ids, order, fields, key order and
bytes are identical to the former file.

## Layout

- `manifest.json` (about 100 KB, the only mutable file). Top-level summaries (`groups`, audits,
  `latest_run`, `sources`, `methodology`...), `top_level_keys` (original key order) and one entry per
  segment: file, record count, byte sizes, SHA-256, `sealed`, first/last `observed_at`.
- `segments/seg-NNNNNN-<sha12>.json`. Consecutive records in their original order, at most about 5 MB of
  source JSON each (about 3.3 MB stored). The name embeds the first 12 hex digits of the file's SHA-256, so a
  file is never rewritten in place. A segment is sealed (unchanged forever) once the next one starts; only the
  newest (open) segment gets a new name when records are appended. Inside a segment, exact-duplicate subtrees and long strings (provenance, receipt inputs,
  repeated rule text, ...) are stored once in `dict` and referenced as `{"$ref":"<id>"}`.
- `data/public_tracker.json` is now a small `schema_version: 2` tombstone pointing at the manifest. A
  reader that was missed fails loudly instead of silently reading stale history.

## Rules the writer enforces (`scripts/tracker_store.mjs`)

1. **Append-only.** Every stored record must be unchanged and in place; shrinking or editing refuses
   to write.
2. **Lossless.** Each segment is expanded again and compared record by record before writing.
3. **Files are content-addressed and the manifest is written last** (temp file + rename). Superseded
   open-segment versions and temp debris are deleted only after the new manifest exists, so a crash or
   retry always leaves a manifest whose every referenced file exists with a matching checksum.
4. **Hard failure on missing or corrupt state.** A checksum mismatch, a missing segment, a truncated or
   unparsable manifest, or a tombstone without its manifest raises. Only a missing manifest with no legacy
   file means a genuinely fresh checkout. It is never treated as an empty tracker (that would re-freeze every
   prediction).
5. Size guard: any file over 30 MB is refused (warning at 8 MB).

## Reading

- Node: `loadTrackerSnapshot(dataDir)` in `scripts/tracker_store.mjs`.
- Python: `load_tracker(data_dir)` in `scripts/tracker_store.py`.
- Browser: `loadTrackerVerified(getText, {share:true})` in `shared/tracker-store.mjs` (verifies every
  segment checksum; `share` keeps one object per dictionary entry for read-only use).
- API: `/api/snapshot?file=public_tracker/manifest.json` and `public_tracker/segments/seg-NNNNNN-<sha12>.json`
  (fixed-format names only; the client verifies each segment against the manifest checksum and retries once
  for cache skew).

## Rollback

```sh
git revert <store commits>                                   # restores readers and writer
node scripts/tracker_store.mjs export > /tmp/public_tracker.json   # BEFORE reverting data: every record, byte-identical to the legacy file
cp /tmp/public_tracker.json data/public_tracker.json        # overwrite the tombstone, then commit
```

The pre-migration single file also remains in git history. `data/public_tracker/` may be left in place
(unused) or removed.

## Validation light ledger (derived, UI only)

The Validation dashboard no longer loads the heavy store on first paint. `data/derived/validation_ledger/` holds a
**derived projection** of the canonical segments, one shard per segment plus `index.json`:

- Built by `node scripts/validation_ledger.mjs build` (its own data.yml step, after the tracker step). It is a pure,
  deterministic function of the store: no clocks or randomness, so deleting it and rebuilding reproduces identical bytes.
- A shard keeps only what `apps/validation/metrics.mjs` and the dashboard lists read, in the same
  `{id,kind,observed_at,payload}` shape, so the dashboard's own code produces identical numbers
  (`tests/validation-ledger.test.cjs` compares every displayed number and field across 82 filter/group combinations
  against the full store). It derives `model_cohort` and `rules` exactly as the dashboard would, and drops
  `provenance`, `readiness_snapshot`, `picks_snapshot`, full `model_evidence`, and the `pick_research*` kinds.
- File names embed the source segment checksum and the shard's own checksum. The index records the source segment
  checksums; the browser refuses a ledger that does not match the store manifest it loaded and **falls back to the full
  store** (also on any fetch/checksum error). Index and shards carry `derived: true, not_for_evaluation: true`.
- Heavy evidence loads **on demand**: opening "Show saved evidence" fetches the one canonical segment that holds the
  record (verified against the manifest checksum) and renders the same lines as before.
- Season windows: the default load is the latest season's shards. A shard lists the seasons of the predictions it
  holds *and of the predictions its settlements/closings refer to*, so a window never drops a settlement. "Load earlier
  seasons" loads the rest in canonical order. (One season exists today, so everything loads.)
- It is **never** read by the tracker writer, calibration, settlement or any audit; a test fails if any of those
  files mention it. The canonical store remains the only source of truth.

Rollback: remove the ledger step from `data.yml` and `data/derived/`; the dashboard then loads the full store exactly
as before (or revert the dashboard commit).

## Scaling thresholds for the Validation ledger (revisit when measured, not by date)

The ledger's wire size, parsed heap and per-interaction CPU all grow with the number of records inside a season (about
0.5 MB raw / 106 KB gzipped per active day, measured 2026-10). Do not start another architecture project until a
measurement crosses a threshold. Measure with the production page (cold load, throttled-free desktop Chrome and a
mid-range phone profile) and record the numbers in `PROGRESS.md`.

| Signal | Watch | Act (start per-shard partial aggregates + lazy per-shard rows) |
| --- | --- | --- |
| Ledger wire size, all loaded shards, gzipped | 8 MB | 12 MB |
| Parsed JS heap of the Validation page | 60 MB | 100 MB |
| Time from navigation to dashboard numbers (cold, phone profile) | 3 s | 5 s |
| Time to apply one filter change (main thread) | 150 ms | 300 ms |
| `scripts/validation_ledger.mjs` size guard (warn 8 MB / max 30 MB per shard) | any warning | any failure |

`node scripts/validation_ledger.mjs build` prints the shard sizes, so the first row can be read from CI logs; the others
need a browser run. Planned response when a row reaches "Act": publish a per-shard partial aggregate computed with
`apps/validation/metrics.mjs` (the dashboard math must stay the single implementation), load rows only for the shard a
user drills into, and keep the full-ledger path as the fallback. Season windows already reset the first paint each
season; the "Load earlier seasons" path is the one that will hit these limits first.

Known small follow-ups (not blocking): the season window starts in July, so check the "Complete record" wording before
the 2027 preseason; once a second season exists the closing-count tile and slate/game lists reflect only loaded shards;
an evidence fetch on a page left open for hours fails until refreshed; stale raw-content caches can send some visitors
down the (correct but heavier) full-store fallback.
