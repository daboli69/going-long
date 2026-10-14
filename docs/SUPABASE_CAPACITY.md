# Supabase capacity investigation — October 14, 2026

Status: lossless archive and authenticated reader implemented locally. User created a
new Free project (GOING Recovery) and submitted the prepared account/schema restoration.
New hosted baseline after setup: 11,327,155 bytes, one restored account, no relational
journal rows. All93shards+owner manifest uploaded, downloaded and SHA-256 matched. Hosted post-upload size11,679,411database bytes/104,091,099private object bytes (94objects), bucketpublic=false. Authenticated access/cutover verification remains in progress.
Original paused project and backup are intact. No upgrade or deletion occurred.

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

The user authorized this recovery path and personally created the new Free project and
submitted credential-restoring setup. No original data deletion is part of the recovery.
GOING still points at the original project until hosted checks and controlled cutover.

## Implementation and reproduced results

- `scripts/journal_archive.py build/verify`: exact original COPY rows, bounded 8 MiB raw
  gzip shards, SHA-256 manifests and disk-backed ID/hash reconciliation. No network or
  database mutations. Existing destinations are never overwritten; incomplete results
  are never promoted. Public/build paths and nested private-directory tricks rejected.
- Actual source: all 1,140,107 journal rows verified in 93 shards / 104,040,969 gzip bytes.
  `received_at`, original IDs, ownership, payload text and every research observation
  remain present. A verified persistent copy, original backup and recovery files are
  under `%LOCALAPPDATA%/GOING/private/recovery-20261014`, outside Git and OneDrive.
- `compact`: new private SQL backup retaining every non-journal SQL byte, recent rows
  and bet-referenced predictions; all omitted relational journal rows remain in the
  verified archive. Actual source has no rows since September 30 or placed bets, so the
  candidate is 44,845 gzip bytes with zero hot journal rows. This is a recovery candidate,
  not a blindly executable replacement for managed Supabase platform schemas.
- `bootstrap`: empty-target guard, original auth account/identity/session records,
  source-column checks, public append-only schema and owner-protected private buckets.
  Populated unsupported feature tables or incomplete COPY sections stop restoration.
  Managed platform migration histories stay in the full backup, not transplanted onto
  a newer platform. No password reset or original-project change.
- Real auth/schema script independently restored in an isolated PostgreSQL fixture:
  accounts1, identities1, sessions16, refresh tokens72, AMR claims16; JSON metadata types
  retained. Hosted setup subsequently returned account1 and 11.3 MB database size.
- Journal-only PostgreSQL16 restore with PK/cursor indexes: 1,031,315,456 relation bytes.
  Therefore even rebuilding only the essential indexes does not make this dataset fit
  500 MB relationally. Isolated compact journal plus auth/schema fixture: about 8.3 MB,
  excluding the hosted platform's baseline; hosted size must be measured separately.
- `apps/validation/journal-archive.mjs` and loader: authenticated owner-folder reads,
  bounded decompression, hashes/counts/ownership/time bounds checked, live/archive union
  with semantic duplicate checking. Missing/corrupt history fails visibly rather than
  silently scoring incomplete results. Archive enablement defaults off, configured by
  `GOING_JOURNAL_ARCHIVE=1`; public tracker unchanged. Logout invalidates pending loads.
- Actual offline reader parity: same 58,332 performance-view records as original source
  (32,525 predictions, 25,807 settlements), identical sorted-ID digest. Source has no
  actionable predictions; unused closing rows remain preserved, not invented as CLV.
- Owner-only Storage RLS tested on isolated PostgreSQL, including an existing broad
  permissive policy: anonymous read denied, cross-owner read denied, browser writes denied.
  Browser upload labels gzip as `application/x-gzip`; bounded private bucket explicitly
  allows this equivalent MIME type alongside `application/gzip` and JSON.
- Independent review found and repaired unsafe output-path acceptance, unsupported
  nonempty feature-table omission, and missing COPY terminator checks. Focused independent
  verification: 9 Node + 14 Python tests passed. Final full checks use the ignored
  `.cache/supabase-size/` receipt/logs and exact revision recorded there.

## Remaining cutover and growth gates

Do not point GOING at the new project until archive uploads and authenticated reads are
verified, old/new owner IDs agree, hosted size is under quota and current code is released.
Preserve the original Vercel URL/key configuration for rollback. Restored auth sessions
use a new project's signing keys, so users must sign in again; original login credentials
are preserved rather than reset.

This release is one-time recovery, not an unlimited free-storage guarantee. Scanner
`Journal.sync()` remains an unbounded mirror if reconfigured to the new project. Do not
repoint that writer before verified ongoing archive rotation/capacity controls are ready.
Public refreshes do not need that mirror; current private FP object is replaced in place.
Monitor object storage and egress as well as relational growth; finite Free capacity
cannot promise indefinitely hosted access to unlimited observation history.

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

Initial code reviewer checked query/sync paths and passed 3/3 original private-loader
tests; implementation and additional independent review/results are recorded above.

## Credential incident resolved; archive connection live

A browser selector error included the new recovery project's legacy service-role JWT in
a tool response. Treat it as exposed; no key is committed or repeated in these docs.
Legacy API keys are disabled and the previous legacy JWT signing key is revoked.
Both direct API-key and Bearer-JWT probes now return HTTP401; the current ECC signing
key is unchanged. The exposed key was never used for recovery uploads. Original
GOING credentials and its paused database remain intact. The published validation
configuration now points to Recovery with private archive reading enabled.

Release PR19 merged as 432fc0ab17d32dfba13231b8498d91b5136a4dbf; exact-main
CI38632850266 and Vercel deployment succeeded. All 93 hosted shards and the manifest
were downloaded and matched to the local hashes. Recovery uses 11,679,411 database
bytes and 104,091,099 private Storage bytes for 94 objects. All 1,140,107 source rows
remain preserved; the existing reader's 58,332 prediction/settlement IDs match exactly.
SQL role checks show owner94 objects, other authenticated users0, anonymous0.
Authenticated owner UI readback still requires signing into GOING itself.

Private CSV server settings remain unconfigured. The original organization quota
warning can persist through the prior billing-cycle average; no paid plan was enabled.
Do not repoint the unbounded scanner mirror until future archive rotation/capacity
controls are verified. This recovery preserves existing history; it does not establish
unlimited ongoing Free-plan capacity.

The private input storage adapter now supports SUPABASE_SECRET_KEY, sending opaque
sb_secret keys only as apikey, not as a Bearer JWT; legacy credentials remain compatible
for existing installations. Supabase migration docs explicitly require this distinction:
https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys
