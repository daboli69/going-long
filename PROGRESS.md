# Progress
Updated: 2026-10-01. Initial audit: `7d33e75` (origin/main).

## Completed
- Imported repository; isolated setup on `codex/agent-infrastructure`.
- Added seven role definitions, bounded work loop, three-agent cap, cost/safety rules and Champion/Challenger gate.
- Audited CI, build paths, saved NFL/NCAA snapshots, tracker/calibration code and existing game/prop diagnostics; reused `docs/AUDIT_GUIDE.md`.
- Checks: Node 160/160; Python 96/96 in local `.venv`; `npm run build`, `node scripts/build_vercel.mjs` and `git diff --check` passed. Vercel build emits shared-asset bundling warnings; assets are copied by the build script.
- Activated in-chat automation `going-long-daily-improvement`: daily 10 AM America/New_York; one bounded issue/run, quiet unless actionable, existing included usage only. First scheduled execution not yet observed.
- NFL/NCAA/context snapshots dated Oct 1; generation timestamps alone do not establish completeness or live freshness.

## Working
- None. Initial infrastructure/audit complete; daily MANAGER loop selects from Next.

## Problems
- **Verified, medium:** `.github/workflows/test.yml` push path filter omits `shared/**`, `apps/yard/**`, `apps/players/**`, `apps/results/**`, `hub/**`. A push touching only these paths skips validation; pull requests still trigger it.
- **Verified evidence gap:** `data/topdown_status.json` is dated Sep 12; cannot establish current scanner health. Most football snapshots are newer. No live worker/database audit performed.
- **Verified model limits:** game diagnostic uses revised historical data, not archived decision-time inputs; prop role adjustment worsens overall MAE. Neither is promotion evidence (see `MODEL_RESEARCH.md`).
- **Unverified:** rendered mobile/a11y, live API uptime/latency, production permissions and paid-provider budgets; unit tests do not establish these.

## Next
1. QA/BUILDER: extend CI push paths for public/shared files; verify path coverage and affected tests.
2. FOOTBALL DATA: check per-source freshness, completeness and scanner status display/refresh using existing fixtures, without metered API calls.
3. UI/UX + PRODUCT: inspect football at mobile/desktop widths; prioritize one reproducible navigation, accessibility or bet-discovery issue.
4. MODEL RESEARCH: reuse calibration replay; predeclare later holdout and evaluate game lines/props separately before any promotion.

## Needs Travis
- Keep this checkout available, computer awake and Codex app running for local scheduled work. The three operating files are committed locally on `codex/agent-infrastructure`; they have not been pushed/deployed. Rollback: revert the setup commit (`git log -1` identifies it).
- The heartbeat inherits this chat's model settings; select the cheapest capable included model for routine runs if desired. No new API, credit purchase or service was activated.
- If replay research is blocked, provide a sanitized decision-time quote/outcome export; never service keys. Do not request this until needed.
- Approval required before production/DB/auth/architecture/paid changes; initial setup needs none.
