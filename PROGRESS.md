# Progress
Updated: 2026-10-19 (Phase 10 lab only). Initial audit: `7d33e75`; manual heartbeat test (cycle 3): `eb9ad8e`.

## Completed
- Phase 10 lab (Codex, codex/projections-20261019): recovered local quote history, archived 11 weather pulls, implemented independent game anchors and six-target props ensembles/first TD, and exported 15 pregame shadow forecasts in week-6/7 CSV/Markdown/Excel sheets. Amendment 1 freeze 9147dd5 preceded recent-data reads; recency-weighted refit cutoff Oct 12 / completed 2026 week 5. Champion/v1 untouched; no 2026 scoring or spend. Verified: final active lab suite 244 passed / 1 existing skip; 15-archive timing/independence/probability checks and both workbook previews passed. Detailed report: research/nfl-ensemble-lab/reports/run_20261019/REPORT.md.
- Imported repository; isolated setup on `codex/agent-infrastructure`.
- Added seven role definitions, bounded work loop, three-agent cap, cost/safety rules and Champion/Challenger gate.
- Audited CI, build paths, saved NFL/NCAA snapshots, tracker/calibration code and existing game/prop diagnostics; reused `docs/AUDIT_GUIDE.md`.
- Cycle 2 checks: Node 162/162; Python 96/96 in local `.venv`; both builds and `git diff --check` passed. Existing Vercel shared-asset warnings remain; files are copied by the build script. No live deployment verification.
- Existing heartbeat: daily 10 AM America/New_York; one issue, 15-minute active-work budget, relevant roles only, quiet unless actionable. Cycle 3 manually tested its rules; actual scheduled execution not yet observed. Automation unchanged this cycle.
- NFL/NCAA/context snapshots dated Oct 1; generation timestamps alone do not establish completeness or live freshness.
- Cycle 1 (FOOTBALL DATA + QA, one agent): audited football snapshot loading and deployment freshness; no application edits. Offline handler check reproduced a missing allowlist entry (9/10 loader snapshots accepted); API/cheatsheet tests passed 8/8. No real provider requests or production checks.
- Cycle 2 (BUILDER + QA, one agent): allowed `season_learning.json` so football matchup context can load nightly updates. Two regression tests failed before the fix, passed after; all 10 loader snapshots accepted with mocked upstream, timestamps/fallback preserved, invalid paths rejected.
- Closed CI coverage gap: push filters now include `apps/**`, `shared/**`, `hub/**`. Offline path checks cover public football/shared pages plus existing validation/baseball; data-only updates remain excluded and PR trigger retained.
- Cycle 3 (FOOTBALL DATA, one agent): traced scanner-status provenance; verified worker/private override, CLI/public default, journaled run record and absent refresh publication. Mocked API fallback returned the unchanged Sep 12 timestamp. No application/model edits, live requests, private inputs or spend; MODEL_RESEARCH.md unchanged because no research evidence changed.
- Review pipeline preparation: added local exact Vercel Git-deployment exclusion for `codex/going-long-daily-review` and `docs/DAILY_REVIEW_PIPELINE.md`. Config/path checks, 8/8 Vercel/API tests and local Vercel build passed; existing build warnings remain. GitHub metadata confirms public repo; standard Ubuntu Actions minutes free, existing cache/billing settings not verified. No workflow, automation or external settings changed; no pushes, remote branch, merge or deployment.

## Working
- NBA Ensemble (Codex,2026-10-23; explicitly authorized by Travis): separate research/NBA ensemble, winners-first six fixed families, no NFL imports/data/model changes. Evidence: free SportsDataverse schedules/team boxes reachable,15offline leakage/schema/UI tests passed. Acceptance: frozen chronological discovery/confirmation, honest metrics versus Elo, six-model debate, standalone local dashboard/one launcher and immutable prospective forecasts. Actual data refresh/research in progress; no promotion/deployment/spend.
- Review publication disabled. Local exclusion prepared; external project/root/hooks, approved baseline/commit set and reviewer access remain prerequisites. No current claim of end-to-end deployment protection or cloud visibility.

## Problems
- Phase 10 verified limits: authorized quotes start September 2026, so 2022 original-v1/market-scaled-B/closing-line comparisons are blocked. Historical first-TD eligibility misses 26 scorers; ambiguous names and unsupported multi-TD quote comparisons remain explicitly unavailable. No qualified model is promoted.
- **Verified provenance gap:** `scripts/run_local_scanner.py:53` writes private `scanner-status.json`; `scripts/scan_markets.py:160` defaults to the public artifact only outside that override and journals runs. Refresh workflow neither runs the scanner nor publishes status. Public Sep 12 status is not evidence that the worker stopped; its two-book notice also differs from current scanner policy. No direct references found in current football UI/shared/app code; API still exposes it. Current worker health remains unverified; do not repeat this audit without new evidence.
- **Verified model limits:** game diagnostic uses revised historical data, not archived decision-time inputs; prop role adjustment worsens overall MAE. Neither is promotion evidence (see `MODEL_RESEARCH.md`).
- **Unverified:** rendered mobile/a11y, live API uptime/latency, production permissions and paid-provider budgets; unit tests do not establish these.

## Next
- Phase 10: optional frozen-config 2023–25 single look was skipped for the 18:15 deadline; run once only in a separately budgeted session. Continue prospective quotes/inactives; improve earlier-roster eligibility. Never invoke lab.props.evaluate eval.
1. UI/UX + PRODUCT: inspect football at mobile/desktop widths; prioritize one reproducible navigation, accessibility or bet-discovery issue.
2. MODEL RESEARCH: reuse calibration replay; predeclare later holdout and evaluate game lines/props separately before any promotion.
3. FOOTBALL DATA: when scanner health is operationally needed, use a sanitized current status export; decide whether a public health signal has user value before designing publication. Do not expose private status wholesale or restart the worker during audits.

## Needs Travis
- Phase 10 manual Task Scheduler steps: research/nfl-ensemble-lab/docs/PHASE10_DATA_ARCHIVE.md. No tasks created or release activated. Tonight's T-90 inactive window is after the 18:30 no-new-work cutoff; parser fixture passed, live pull remains unverified.
- Keep checkout available, computer awake and Codex running for scheduled work. Setup: `cd94e3a`; fixes: `08b0230` (revert for rollback); AGENTS.md edit committed as `eb9ad8e`. This cycle changes only this tracker, saved in a separate local audit commit. Nothing pushed/deployed by this cycle.
- Cycle-specific model selection is unavailable in this manual chat/heartbeat interface; settings retained, no global/chat model change or escalation. Luna preference remains an instruction, not a verified model override. No new API, credit purchase or service activated.
- If replay research is blocked, provide a sanitized decision-time quote/outcome export; never service keys. Do not request this until needed.
- Approval required before production/DB/auth/architecture/paid changes; initial setup needs none.
- Review pipeline: approve baseline and explicit initial commits, then separately authorize remote review-branch creation/first push after external prerequisites are verified. Automatic review-branch pushing requires a later explicit heartbeat authorization; never main/merge/deploy. Any Vercel project-setting or paid-capacity change needs separate approval. See `docs/DAILY_REVIEW_PIPELINE.md`.
