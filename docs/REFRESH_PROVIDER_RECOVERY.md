# Refresh provider recovery — October 14

Run38643644513 failed because the **successful HTTP response** for NFL core
props explicitly signaled incomplete/degraded coverage. This differs from the
HTTP503 mock responses printed by the test suite in the same workflow log.
The old adapter discarded the provider's explanation, so the failed books and
internal-cap hint cannot be reconstructed from that run. Do not invent them.
Savant CSV-only coverage was a descriptive-context warning, not the failing step.
Availability and publication integrity succeeded.

The repair serializes the existing two props-board requests, retaining all market
families and the same request/retry/page budget. This avoids competing expensive
board queries from this client. It is a contention mitigation, not proof that the
provider's own source failures or caps have been repaired. HTTP200 incomplete
responses are not retried at additional credit cost.

Partial responses now retain bounded, credential-redacted request IDs,
`x-result-degraded` book keys and `x-result-truncated-hint` explanations in
`source_errors`, workflow logs and the health artifact/summary. A repeated or
backward continuation offset stops immediately instead of downloading duplicates.
No incomplete source becomes FRESH; failed NFL outputs remain excluded from
publication and existing quotes retain their actual timestamps.

Savant's free public API and bulk CSV get one bounded retry for transient network,
429 and server errors, honoring Retry-After up to60seconds. Other errors fail
immediately; final diagnostics include HTTP status. A direct read on Oct14
returned200, season2026, week5,32teams. This does not establish historical source
availability or force the source healthy when a later request fails.

Provider guidance: https://parlay-api.com/docs/response-shapes and
https://parlay-api.com/docs explain that truncated coverage can arise from
internal caps or failed books and cannot necessarily be fixed by pagination.
Each successful props page consumes credits. Do not blindly add retries or probe
every bookmaker. Use the new hint/request ID to distinguish an internal read cap
(consider bounded query partitioning) from an unavailable upstream book (provider
repair required). Preserve strict health until complete coverage actually returns.

Rollback: revert the provider recovery implementation commit. No database,
credentials, availability engines, model weights or licensed CSV inputs change.
Keep the Recovery Supabase/Vercel settings and schema2 availability contract from
PRs19–22; see CURRENT_AVAILABILITY.md. Original paused Supabase remains intact.

## Released verification

PR23 merged as `c1eb439b3eef88a4bf8b2565247b4598f46fe704`. Exact-main application
validation38646575589 passed888Node and626Pythonrun(621passed,5existing skips),
both builds. Local full dependency audit found0advisories. Code deployment
3aqRejugHKE2bBqqdi5Bi4rvHLGL succeeded.

Ordinary refresh38646575488 finished **success**, healthy/publication_ready true,
no issues, source failures or publication failures. Actual props query returned
503/PROPS_TEMPORARILY_BUSY and recovered on the existing bounded retry; all four
source states are FRESH. Data commit `34003bc5a5ca9e2c5700a25c6c7506b8a6df2e54`
contains9356core and1358derivative quotes, possibly_truncated false. This verifies
recovery for this run, not permanent provider reliability or a causal experiment
proving serialization alone fixed the provider.

Savant API returned HTTP403 from GitHub, versus200 from the local direct check.
The public CSV loaded13842rows. Its partial-context warning remains visible and
non-blocking; no access-control bypass or fabricated API success. API access from
GitHub requires the source operator's support if needed; retries do not fix403.

Ignored receipts: `.cache/refresh-provider-recovery/validation.json`,
`exact-main-ci.log`, `hosted-refresh.log`, `hosted-health/refresh-health.json`.

## Follow-up: confirmed serving cap

Run38660477354 returned explicit internal per-source cap headers, no degraded
books, and10000rows at offset0 followed by1row at offset10000. The earlier green
run did not establish lasting recovery; serializing requests cannot remove this
serving cap. Pagination cannot recover the missing rows.

The follow-up planner retains exactly two serialized props queries. It estimates
market volumes from the saved normalized quotes. When the old split exceeds80%
of the10000-row serving cap, it greedily balances whole market families between
two disjoint requests, including every canonical market exactly once. Unknown
market weights are planning placeholders, never probabilities or freshness proof.
Small/unknown boards keep the original split. With the actual saved9728quotes,
the planned loads are4872and4856; these are estimates, not live response counts.

Both queries may now contain main and derivative markets. Core/derivative health
reflects every query needed by that family; an outage cannot certify part of the
family fresh. Fallback rows are selected by that query's markets and keep their
original timestamps. Coverage diagnostics record each partition and its state.
An explicitly truncated response stops immediately, saving an unproductive
second paid page. Other genuine pagination remains supported. No extra queries,
book exclusions, raised cap, invented quotes or relaxed health requirements.

Synthetic tests reproduce an11210-row core board with1000derivative rows and
verify complete reconstruction within two requests, unique identities, retained
clocks and failures of either mixed query. A single market that still exceeds
the cap remains degraded; additional requests or service spending require a
separate decision. Receipt: `.cache/props-cap-partitions/offline-plan.json`.

The two-query hosted trial38663793308 **failed** its final health check: partition1
returned6376rows without truncation; partition2 returned7203rows but reported a
busy-book read-window cut. Continued workflow steps report successful conclusions
under continue-on-error; these are not proof of source success. The final health
artifact and step outcome are authoritative. No incomplete NFL file was published.

Travis then explicitly authorized reasonable additional pulls against his20000
monthly-credit allowance. The scheduled workflow now selects `markets`: eight
single-main-market queries plus one small derivative query, serialized and capped
at one page each. Normal successful props cost27credits/run, about2350/month on
the20/week schedule (excluding other endpoints, website/manual/scanner usage and
ambiguous transport retries). No upgrade, overage setting or new service enabled.
Default standalone behavior stays two queries. Full provider hints are retained
up to2048characters with credential redaction. Wire `market_key` takes precedence
over the descriptive `market` field in coverage counts. Core/derivative clocks
and freshness still reflect every relevant request.
