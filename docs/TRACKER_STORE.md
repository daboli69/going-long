# Public tracker store

`data/public_tracker/` holds the primary football tracking log. It replaces the single
`data/public_tracker.json`, which grew past what GitHub (100 MiB per file) and the snapshot API
(4.5 MB responses) can carry. Nothing about the records changed: ids, order, fields, key order and
bytes are identical to the former file.

## Layout

- `manifest.json` (about 100 KB, the only mutable file). Top-level summaries (`groups`, audits,
  `latest_run`, `sources`, `methodology`...), `top_level_keys` (original key order) and one entry per
  segment: file, record count, byte sizes, SHA-256, `sealed`, first/last `observed_at`.
- `segments/seg-NNNNNN.json`. Consecutive records in their original order, at most about 5 MB of
  source JSON each (about 3.3 MB stored). A segment is sealed (never rewritten) once the next one
  starts. Inside a segment, exact-duplicate subtrees and long strings (provenance, receipt inputs,
  repeated rule text, ...) are stored once in `dict` and referenced as `{"$ref":"<id>"}`.
- `data/public_tracker.json` is now a small `schema_version: 2` tombstone pointing at the manifest. A
  reader that was missed fails loudly instead of silently reading stale history.

## Rules the writer enforces (`scripts/tracker_store.mjs`)

1. **Append-only.** Every stored record must be unchanged and in place; shrinking or editing refuses
   to write.
2. **Lossless.** Each segment is expanded again and compared record by record before writing.
3. **Sealed segments never change; the manifest is written last** (temp file + rename). A crash or
   retry leaves the previous manifest pointing only at complete files.
4. **Hard failure on missing or corrupt state.** A checksum mismatch, a missing segment, or a tombstone
   without its manifest raises. It is never treated as an empty tracker (that would re-freeze every
   prediction).
5. Size guard: any file over 30 MB is refused (warning at 8 MB).

## Reading

- Node: `loadTrackerSnapshot(dataDir)` in `scripts/tracker_store.mjs`.
- Python: `load_tracker(data_dir)` in `scripts/tracker_store.py`.
- Browser: `loadTrackerVerified(getText, {share:true})` in `shared/tracker-store.mjs` (verifies every
  segment checksum; `share` keeps one object per dictionary entry for read-only use).
- API: `/api/snapshot?file=public_tracker/manifest.json` and `public_tracker/segments/seg-NNNNNN.json`
  (fixed-format names only).

## Rollback

```sh
git revert <store commits>                                   # restores readers and writer
node scripts/tracker_store.mjs export > /tmp/public_tracker.json   # BEFORE reverting data: every record, byte-identical to the legacy file
cp /tmp/public_tracker.json data/public_tracker.json        # overwrite the tombstone, then commit
```

The pre-migration single file also remains in git history. `data/public_tracker/` may be left in place
(unused) or removed.
