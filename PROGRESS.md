# Progress
Cycle: `20261002-2159-game-first` (dedicated 30-minute PRODUCT + UI/UX session; automation unchanged).
Production base: `3d9ae9ae05a54e8c7e324106840fc06b965f2c30`. Review base: `cb4e9988ae57890cdac6da2062309a676e5e13db`.
Production commit: `8626bebcbfba44a4b356cb4f35f8e9035febdd4c` (verified remote main; deployment/check status recorded in receipt).
Review completion SHA: recorded by subsequent receipt; receipt tip reported externally.

## Completed
- MANAGER + two Luna/low agents: UI/UX fixed phone navigation; PRODUCT/QA audited journeys, added grouping tests and independently reviewed handoff. Manager implemented/integrated the coherent game-first phase. Review caught an inconsistent all-games parlay default; fixed separate Today choices before final verification.
- Confirmed published snapshot had 3,691 NFL qualifying contracts in a card feed, hidden Score/Jackpot, sparse NCAA More positioning and no frozen Score outcome history. Prior maintenance/filter cycles reused, not repeated. Game-first research beats an isolated cosmetic fix: it connects quick-bettor Today, matchup prices, market browsing, evidence and selected-game Parlays without changing Champion eligibility or estimates.
- NFL/NCAA Today now starts with date/slate, compact scope summary and at most 12 game summaries. Each gives leading research candidate, Low/Moderate evidence, recorded reason, quote-age caveat and expandable top entries/why; full lists remain under advanced research. Ordering is explained as model estimates, not proven strength. More games loads another bounded page. Exact sport/teams/kickoff identities retained.
- Choose games on Today, then explicitly Build from selected games copies only those choices to the existing Parlay Lab. Separate NFL/NCAA selections; selection toggles preserve focus and Lab settings until handoff. Existing game exclusions/settings/unsupported-combination safeguards remain. Matchup action opens the exact sportsbook comparison; Markets explains availability versus ranked research.
- NFL Score and Jackpot are primary navigation. Score defaults to collapsed matchup groups, preserves opened groups on rerender and appears on Today when a matching eligible player/market score exists; explicitly an evidence index, not win probability. Jackpot explains First TD, last TD and longest-TD research; existing players/D/ST/returner calculation support untouched. NCAA remains game-markets-only. Phone More menu spans its containing navigation and fits the viewport.
- Six app/test files only; 173 additions/15 deletions. Targeted 71/71, full Node 186/186, Python 96/96, npm build and Vercel build pass. Offline browser used actual public snapshots: NFL/NCAA journeys, Today ET (3 NCAA games), lazy why, correct Liberty/Delaware comparison, selected-game SGP handoff, 390px More bounds (12..363), desktop two columns. No real provider/alert calls. Existing shared-asset build warnings unchanged.
- Champion calculations, ranking/eligibility, confidence, Score candidate math and parlay search verified byte-identical to base. Scope/secret checks, explicit staging, ordinary one-commit main ancestry and both unchanged remote tips passed. Existing Hobby Basic root connection/paid concurrency disabled verified read-only; only standard public application CI triggered, not credentialed data refresh. Exact patch strictly applies and reconstructs the whole tested production tree; review Vercel exclusion preserved. MODEL_RESEARCH.md unchanged: no experiment or promotion.

## Working
- None; production Vercel deployment succeeded. Live /long/ HTML and three affected shared assets return HTTP 200 and exactly match the tested production build/blobs. Claude receipt follows this completion; CI final state recorded there.

## Problems
- Feed contains some same-team fixtures one minute apart (and NCAA aliases); keep separate until provenance-backed reconciliation is tested. Summary counts research entries, not unique recommended tickets. High model win estimates/Score bands are not validated betting performance. Score scroll-to-top report not reproduced; keeping open groups helps disclosure state but is not a claimed scroll fix. Selections are session-local; default week remains available alongside Today ET.

## Next
1. Parlay workflow: explicit per-leg remove/swap/lock, preserve remaining legs and date/game context; supported book/SGP rules only.
2. Matchup workspace: GOING angles + relevant scores + conclusions first, deeper current evidence on request; then compact sticky Cheatsheet search/game jump groups.
3. Score tracking: separate prospective frozen local records (version, score/band, market, sport, exact contract, cutoff/quote, later settlement). No retrospective backfill; paired chronological samples/uncertainty and appropriate probability/error metrics. Existing Signals ledger does not track Score bands. Promotion still gated.
4. Reproduce refresh/scroll anchoring and audit timestamp/alias split fixtures; no arbitrary event merging. Claude fetches production SHA and reviews this cycle patch against recorded base, not older review app tree.

## Needs Travis
- None for this low-risk phase; $0 additional spend. High-risk/model promotion gates remain.
- Rollback: fresh codex branch from current main, `git revert 8626bebcbfba44a4b356cb4f35f8e9035febdd4c`, required tests/builds, ordinary authorized publication. Parent `3d9ae9ae05a54e8c7e324106840fc06b965f2c30`; no reset/force or automatic destructive rollback.
