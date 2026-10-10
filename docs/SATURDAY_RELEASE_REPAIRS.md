# Saturday release repairs — October 10, 2026

Verdict: **READY WITH RESTRICTIONS for a controlled application release with unavailable recommendation features paused. NOT READY to enable the full betting/DFS slate with the currently retained sources.** No production release or model promotion is authorized by this report.

Baseline independently audited by Opus: `c8164da337d581253d00e2e1304746e1517359bb`. Repair source revisions: `ddcb51a40cad53329c6fd780a462ba531bf2df7e`, `c6b644e925a74568c8441e97295a48beececc9ac`, `e61ffb12015c065823db202dfebefa8214698aca`. Final exact tested source/documentation and simulated-integration commits, complete command exits, counts and preservation receipts are saved in `.cache/saturday-validation.json`. Tests must finish successfully there before this verdict is used. No main merge, push, provider credit use, alerts, real freeze, retrospective ABBEYS edit or Challenger promotion was performed.

## Repairs and independent evidence

| Audit defect | Repair / acceptance evidence |
|---|---|
| First TD game total overwritten by home scorer mass | Separate immutable `game_total` and `scorer_total`. Regression reproduces old away-mass collapse, verifies unequal matchup expectations, home/away swap, changing home weights without affecting away mass, empty home player pool, future participation rejection and full field sum1. Version2 metadata distinguishes corrected calculation. Offline recomputation on retained public schedules verifies arithmetic; it is not a backtest of accuracy. |
| First TD ineligible players and unsafe old snapshots | Both Jackpot views call one candidate filter using the shared eligibility engine; identity/team/full probability field/current week/start checks. Legacy calculation versions suppressed. Prop-game association requires unique teams/kickoff match within60seconds. No rescaling offered/available players to100%; other offense/DST/noTD remain. |
| First TD market semantics | Credited scorer excludes passer-only TDs. Unconditional model odds treat noTD as loss; actual void/refund rules unverified. All FirstTD expected profit/Kelly/stakes withheld, quotes explicitly separate. Corrected estimates research-only, uncalibrated. |
| Roster move test can deadlock refresh | Broad suite diagnostics are independent of stable model-logic gates. Source, test, integrity and publication failures separated. Valid unrelated components remain publishable; model-dependent tracker/ledger/charts excluded on model gate failure. Malformed JSON/gzip/overflow, stale inputs, failed owner groups and companion manifests fail closed. |
| New file clock conceals stale injury information | Exact free nflverse bytes retain upload/content SHA and aware source-content timestamps; injury uses earlier upload/report-content clock. Identical reuploaded bytes cannot become fresh. Backward sources/newer production reports preserved. JS/Python freshness checks generation AND injury/roster content clocks/report weeks; conflicts/unverified status block. All recommendation surfaces consume the shared decision. |
| Unsafe refresh concurrent replay | Single ordinary push; a race/transport failure reports publication failure. Removed reset/reapplication of old snapshots over newer main. No force push/reset in the publication path. |
| Confidence/profit wording | GOING Score evidence depth describes samples/coverage, not calibrated accuracy. Parlay model-implied return labelled unvalidated and disclosed as positive by selection; no profitability claim. |
| Premature UTC Sunday freeze | Sunday04:20 America/New_York guard, EDT/EST cron opportunities, Eastern slate date including UTC Monday Sunday-night game. Temp-only tests cover Saturday19:59/20:01/23:59ET, Sunday before/at threshold, DST, repeated/concurrent atomic writes. Freeze waits for fresh, verified essential sources and FRESH props/derivatives; no real freeze invoked. |
| Fanatics preservation | Three legs/three canonical distinct games, exact rational+2000 boundary for integer American quotes, manual price binding/expiry, eligibility and ranking preserved. Independent exact arithmetic317,929 synthetic triples had no floor mismatches. Shared-player exposure now disclosed without changing ranking. Safe pause when current UI/engine unavailable replaces legacy fallback. No arbitrary60% cap. |
| Frozen ABBEYS | Entire production data and ABBEYS core/Champion/calibration configuration unchanged from audited baseline in repairs. Week5 board remains14picks, journal4records/2snapshots verifies. Historical observation registration stays immutable. |

## Remaining release restrictions

1. Current retained injury/roster snapshots lack required content provenance. **Availability-dependent recommendations, including manually priced Fanatics entries, cannot be enabled merely by changing the file generation clock.** A real verified refresh must satisfy the new gate; no inferred timestamps/backdated status clearance.
2. Current props/derivatives remain FALLBACK/STALE and automatic Fanatics ATD quotes absent. Engineering/manual-entry tests use synthetic prices; no fabricated real quote or live slip is provided. Feed recovery and actual user-entered app prices are separate inputs. Promotion rules remain explicitly unverified.
3. Legacy FirstTD snapshots suppressed; corrected v2 requires a valid source refresh. Even thereafter it remains research-only with no sportsbook EV/stakes until settlement semantics are verified.
4. Natural Sunday freeze remains pending and will refuse current degraded/unverified sources. Never manually force a catch-up freeze after kickoff.
5. Official chosen-contest DK CSV/permitted ownership and actual scanner-host heartbeat remain unavailable. Legal-lineup tests do not establish actual slate readiness, ownership calibration, or tournament profitability.
6. Today-ranking v3 historical generator registration is unchanged. Safety repairs change the actual generator hash, so its collector intentionally refuses new capture until a separately preregistered version is approved; no historical journal or old experiment rewritten.

No independently verified unresolved P0/P1 source-code defect remains within the repaired audit scope. The above data/feature gates are material blockers for unrestricted recommendations. Earlier reports' broader NOT READY verdict still applies to full live betting/DFS use; this restricted verdict does not waive it.

## Controlled integration and deployment procedure

Only after Travis explicitly approves production integration/deployment:

1. Fetch main again. Re-run the local merge rehearsal if its SHA differs from `67ed9a37316daa4acdc04eaf0c4460c65a6d1d24`. Integration is a normal merge of the repaired release branch; never reset main or replay older production snapshots. Verify upstream-changed data blobs match current main and frozen ABBEYS14pick board/journal match the takeover branch. Research branch `codex/saturday-model-research` is excluded.
2. Use the exact tested integration tree; full Node/Python, both production builds, dependency checks, source-health audit and ABBEYS verify receipts must be available. Source-health may be degraded only with corresponding features visibly paused. Check real rendered restricted state on desktop/mobile after staging; rerun health against actual deployed inputs before enabling anything.
3. Record deployment ID and SHA, publish the approved candidate, verify snapshot/cache/version parity, eligibility pause messages, Fanatics quote expiry/manual entry only with verified availability, freeze guard and frozen ABBEYS board. Current tests do not certify an unpushed remote CI or live host deployment.
4. Let authorized existing scheduled refreshes acquire genuine data. No new paid queries or credentials; do not mark retained failed components FRESH. Clear feature restrictions only when their stated gates actually pass. Model promotion is a separate user decision.

## Rollback

Preserve immutable deployment IDs and the tested static package before any publication. A rollback must not reactivate audited FirstTD/availability defects: **c8164da alone is not a safe rollback for betting features.** If initial deployment fails, use prepared static `ops/rollback-maintenance/index.html`: publish that directory as a static site (empty build command, that output directory), with no functions/data/recommendations. This is a reviewable emergency artifact, not deployed here. Verify root serves maintenance and former betting/data/API routes return unavailable rather than old predictions. Travis's production approval is still required.

If later source activation or a subsequent UI deployment fails, restore the exact tested restricted deployment/package and keep source gates paused; preserve newer production data and append-only ABBEYS/tracker journals. Undo a focused source change only on a codex branch, review its safeguard effects and repeat relevant checks before publication. Never reset data/main or revert frozen Week5 observations.

## Predictive intelligence is a separate gate

Full inventory, feature matrix, continuous/probability loss evidence, market comparison, calibration, weaknesses and ranked hypotheses: [Saturday model research](SATURDAY_MODEL_RESEARCH.md). Isolated research commit `030dd62db65978e8e179e7c3aef37f1945bdfad3`, worktree `C:/Users/travi/.codex/worktrees/going-saturday-models/GOING`. Parent independently reproduced passing results and audited TD metrics/research tests. No Challenger qualifies for promotion. Existing policies/ABBEYS retained; application correctness is not predictive superiority.
