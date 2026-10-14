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
