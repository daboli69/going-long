# Private historical odds archive

Owner approved a finite acquisition using the existing The Odds API subscription,
with a lifetime ceiling of20,000 credits. This provider is **historical only**.
It is not connected to current prices, recommendations, availability, refresh
workflows, ABBEYS, or automatic model promotion.

## Acquisition and retention

- Local master: `%LOCALAPPDATA%/GOING/private/odds-history/` outside Git/OneDrive.
  `credential.json` stays only here; never include it in backups or uploads.
- `index.sqlite3` records every reservation, charge, request parameters, immutable
  response checksum and normalized quote. `raw/*.json.gz` preserves full replies.
- `plan.json` freezes completed NFL schedule windows from2024/2025/2026, cutoff
  at least24hours before import,10bookmakers and requested markets. Initial
  discovery uses the historical events endpoint. All requests require historical
  paths and aware old dates; live endpoints are refused before network access.
- First acquire h2h/spreads/totals boards at30minutes before scheduled kickoffs.
  Then acquire six prop markets in outcome-blind, SHA-ordered season round-robin:
  passing/rushing/receiving yards, receptions, passing TDs, anytime TD. Remaining
  credit can buy additional T-24hour prop observations. This is a bounded sample,
  not an exhaustive historical provider export or a certified closing line.
- Ten selected books include Pinnacle, DraftKings, FanDuel, Fanatics and others;
  selection does not guarantee each book/market exists for every event.
- Before each request, SQLite reserves its maximum cost against both the archive
  lifetime ceiling and provider account remaining/used headers. Unknown charges
  remain reserved and stop acquisition. No monthly renewal, scheduler or retry
  automatically spends another subscription allowance. Cached requests are reused.
- Missing historical events are explicit gaps. Only a404 EVENT_NOT_FOUND with
  authoritative headers proving zero charge can be skipped automatically. Other
  failures stop; do not clear a stopped ledger without independent reconciliation.
- Normalization keeps event/book/market/player/selection/line/price, requested
  scope, snapshot and bookmaker timestamps. In-play rows and book updates later
  than the snapshot are excluded. Never pair prices across books/snapshots/lines.
  Multiple distinct observations are retained; counts are not independent trials.

## Existing private cloud storage and app reference

`scripts/sync_odds_history.py` stages immutable originals, acquisition receipts
and per-event normalized objects, then publishes an index last after all event
and receipt objects exist. Checksums and acknowledged byte sizes are verified.
Cloud staging excludes the sportsbook key and limits additional compressed data
to200MB; it uses existing private Supabase Storage, not Postgres rows or a new
paid plan. Original paused Supabase project and existing datasets are untouched.

Cloud prefix: existing owner-protected `going-fp-private/odds-history/v1/`.
The bucket accepts JSON only. Stored JSON envelopes losslessly contain original
gzip bytes in base64 plus SHA256; no bucket MIME/security policy is weakened.
The200MB staging guard includes envelope/base64 overhead.
Upload uses the PC's existing constrained `GOING_FP_INGEST_TOKEN`, via fixed
`https://going-long.vercel.app/api/odds-history`, not the sportsbook credential.
No credential is added to Git, Vercel, client JavaScript or GitHub Actions.

The Evidence page's **Historical odds archive** panel uses existing Personal
journal sign-in. GET requires a valid Supabase user and the existing owner
allowlist. Responses are private/no-store. Readers query only saved objects;
they cannot spend sportsbook credits. Game, market and book filters and paging
preserve both snapshot and quote timestamps. Public tracker remains public.

## Offline commands and resumption

Use the repository virtualenv Python. All scripts default to the private root:

```
python scripts/odds_history.py status
python scripts/odds_history.py query --market player_pass_yds
python scripts/download_odds_history.py
python scripts/sync_odds_history.py --stage-only
python scripts/sync_odds_history.py
```

`summary.json` is written only after acquisition completes; `cloud-summary.json`
requires acknowledged backup of all staged objects. Sync is idempotent and cannot
call The Odds API. Keep the local database plus originals after cancellation;
offline queries and the hosted archive do not require the subscription/key.
Do not run `sample` merely to spend leftover credits. Odds requests generally
cost multiples of10; an unusable remainder should stay unused.

## Research limits and rollback

Oct14 acquisition completed at19,992credits (8remaining):491checksum-verified
original replies reproduce361,802normalized observations. Raw snapshots include
future and hypothetical playoff matchups. A separate immutable `schedule.json`
matches exact canonical home/away teams uniquely within36hours to completed
games in the existing public NFL schedule; quote snapshot must also precede the
**actual** kickoff. Provider event IDs/kickoffs remain preserved alongside the
canonical game ID/kickoff. Only649verified games/353,032observations enter the
app index. The other source observations remain losslessly archived, not labeled
played games or admitted to evaluation. Source schedule/hash and coverage gaps
are included in cloud acquisition receipts. No win/loss results select this cohort.

Stored quotes support future actual-price comparisons; they do not establish a
betting edge. Verify event/player joins, settlement/push/void rules, nearest
snapshot vs actual executable/closing price, market coverage and chronological
cohorts before evaluation. Selected prop sampling and missing-book/event coverage
must be disclosed. No production model was promoted by this acquisition.

Rollback the code commit to remove the reader/uploader. Private local originals
and cloud objects remain intact. Do not delete either as part of code rollback.

Provider references: [historical API documentation](https://the-odds-api.com/liveapi/guides/v4/),
[pricing](https://the-odds-api.com/#pricing),
[retention/use terms](https://the-odds-api.com/terms-and-conditions.html).
