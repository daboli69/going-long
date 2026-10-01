# Progress
Updated: 2026-10-01. Initial audit: `7d33e75`; cycles 1-2 based on `cd94e3a` plus the requested AGENTS.md role edit.

## Completed
- Imported repository; isolated setup on `codex/agent-infrastructure`.
- Added seven role definitions, bounded work loop, three-agent cap, cost/safety rules and Champion/Challenger gate.
- Audited CI, build paths, saved NFL/NCAA snapshots, tracker/calibration code and existing game/prop diagnostics; reused `docs/AUDIT_GUIDE.md`.
- Cycle 2 checks: Node 162/162; Python 96/96 in local `.venv`; both builds and `git diff --check` passed. Existing Vercel shared-asset warnings remain; files are copied by the build script. No live deployment verification.
- Activated in-chat automation `going-long-daily-improvement`: daily 10 AM America/New_York; one bounded issue/run, quiet unless actionable, existing included usage only. First scheduled execution not yet observed.
- NFL/NCAA/context snapshots dated Oct 1; generation timestamps alone do not establish completeness or live freshness.
- Cycle 1 (FOOTBALL DATA + QA, one agent): audited football snapshot loading and deployment freshness; no application edits. Offline handler check reproduced a missing allowlist entry (9/10 loader snapshots accepted); API/cheatsheet tests passed 8/8. No real provider requests or production checks.
- Cycle 2 (BUILDER + QA, one agent): allowed `season_learning.json` so football matchup context can load nightly updates. Two regression tests failed before the fix, passed after; all 10 loader snapshots accepted with mocked upstream, timestamps/fallback preserved, invalid paths rejected.
- Closed CI coverage gap: push filters now include `apps/**`, `shared/**`, `hub/**`. Offline path checks cover public football/shared pages plus existing validation/baseball; data-only updates remain excluded and PR trigger retained.

## Working
- None. Two highest-priority validated fixes complete locally; awaiting ordinary review/deployment approval.

## Problems
- **Verified evidence gap:** `data/topdown_status.json` is dated Sep 12; cannot establish current scanner health. Most football snapshots are newer. No live worker/database audit performed.
- **Verified model limits:** game diagnostic uses revised historical data, not archived decision-time inputs; prop role adjustment worsens overall MAE. Neither is promotion evidence (see `MODEL_RESEARCH.md`).
- **Unverified:** rendered mobile/a11y, live API uptime/latency, production permissions and paid-provider budgets; unit tests do not establish these.

## Next
1. FOOTBALL DATA/QA: audit per-source completeness/scanner freshness and current status publication without metered calls.
2. UI/UX + PRODUCT: inspect football at mobile/desktop widths; prioritize one reproducible navigation, accessibility or bet-discovery issue.
3. MODEL RESEARCH: reuse calibration replay; predeclare later holdout and evaluate game lines/props separately before any promotion.

## Needs Travis
- Keep checkout available, computer awake and Codex running for scheduled work. Setup: `cd94e3a`; cycle 2 saved in a separate local fix commit on `codex/agent-infrastructure` (identify via `git log -1`). Revert that commit for rollback. Nothing pushed/deployed; earlier AGENTS.md edit remains intact and uncommitted.
- The heartbeat inherits this chat's model settings; select the cheapest capable included model for routine runs if desired. No new API, credit purchase or service was activated.
- If replay research is blocked, provide a sanitized decision-time quote/outcome export; never service keys. Do not request this until needed.
- Approval required before production/DB/auth/architecture/paid changes; initial setup needs none.
