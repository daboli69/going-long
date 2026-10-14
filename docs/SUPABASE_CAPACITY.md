# Supabase capacity investigation — October 14, 2026

Status: read-only diagnosis complete; recovery is not implemented. No production rows,
indexes, policies, credentials or plans changed. The user approved resuming the existing
Free project, but Supabase refused because its database is reported as 2.0 GB.

## Evidence

The provider's downloaded gzip backup is preserved privately in Downloads. Its filename
is dated September 29; it is not evidence of a current running database snapshot.
Streaming inspection consumed the complete gzip successfully and recorded aggregate
metadata only in ignored `.cache/supabase-size/backup-size.json` and `record-kinds.json`.
No private rows or credentials are committed here.

- Backup: 108,819,987 compressed bytes; 737,881,673 uncompressed SQL bytes.
- `market_journal`: 1,140,107 rows; 737,585,901 COPY bytes, over 99.9% of exported data.
- Closing observations: 946,260 rows / 476,925,832 COPY bytes.
- Predictions: 107,751 rows / 205,908,124 COPY bytes.
- Settlements: 25,807 rows / 20,068,538 COPY bytes.
- Remaining kinds: runs, references, quotes, inactive reports, notifications, arbitrage.
- No placed-bet rows or Storage objects in this backup. Preserve those tables and their
  constraints regardless; this does not prove they remain empty elsewhere today.
- Eight secondary journal index definitions; primary-key storage is additional.

COPY/export bytes and gzip sizes are **not** physical PostgreSQL table/TOAST/index sizes.
We cannot promise that removing redundant indexes alone gets below the quota.

## Preserve features and every record

Recommended design to prototype before any production migration:

1. Retain the original paused project and immutable backup as rollback sources.
2. Losslessly archive full original rows (ID, owner, both timestamps, kind and payload)
   into private compressed shards with hashes, counts and a manifest. Reconcile every
   original ID and byte-for-byte decoded row after round-trip. Archive creation alone
   does not reclaim database space.
3. Keep current decisions, their required followups, placed bets and bet-referenced
   predictions relational. Add authenticated, owner-filtered, paged archive access to
   the private journal before moving any historical relational copies. Preserve all
   research observations; do not silently substitute only a final closing price.
4. Restore a compact candidate locally and measure actual database/index sizes before
   requesting an approved production recovery/cutover. Local PostgreSQL is not currently
   available; Docker is installed but its engine is not running. No restore was tested.
5. Route future observation history into the same durable archive system, with receipts
   and bounded relational growth. Avoid polling-time prediction fan-out unnecessarily
   duplicating closing payloads; any normalization must retain the original associations.
6. Monitor database, object storage and egress separately. A fixed-size database cannot
   retain unlimited history: retain verified local cold archives as well as a bounded
   hosted working set, or revisit capacity as history grows. Do not promise unlimited
   all-history cloud queries on a finite Free plan.

This is an architecture proposal, not authorization to delete, migrate or create a
replacement production database. Those steps require a concrete verified recovery plan.

## Relevant application findings

- Public tracker/backtests use published snapshots; Supabase is the optional private
  journal mirror. No public app feature was removed during this investigation.
- `apps/validation/load-journal.mjs` currently reads relational predictions, settlements,
  closings and placed bets. An archive without a reader union would lose functionality.
- `scripts/topdown/journal.py` excludes raw quotes/references from default sync, but
  actionable predictions still accumulate at polling timestamps. Do not reset delivery
  flags or assume excluding raw quotes alone fixes growth.
- `scripts/scan_markets.py` records closings per prediction/book/quote timestamp. Large
  counts are consistent with fan-out; they are not proof of corrupt or disposable data.
- Append-only triggers prevent journal DELETE/UPDATE; placed bets reference prediction
  IDs. Do not bypass these safeguards as a cleanup shortcut.
- Current reader needs the owner/kind/time/ID cursor index. Older overlapping/expression
  indexes are candidates for measured review, not blind removal.
- FantasyPoints inputs already use a private object rather than relational rows. Keep
  that approach. Hosted CSV activation remains blocked pending capacity and access setup.

## Provider constraints checked

[Database size](https://supabase.com/docs/guides/platform/database-size): Free database
quota 500 MB, including indexes; new projects also have baseline schema overhead.
Organization fair-use restrictions depend on average daily size over the billing cycle,
so a smaller replacement does not guarantee immediate removal of existing restrictions.

[File limits](https://supabase.com/docs/guides/storage/uploads/file-limits): Free uploads
cannot exceed 50 MB per object. The 109 MB backup cannot be uploaded as one object;
private archives require smaller shards and a separately checked storage/egress budget.

Independent code reviewer checked the query/sync paths and passed 3/3 private-loader
tests. No full suite rerun was warranted for this documentation-only investigation.
