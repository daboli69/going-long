# Independent takeover — 2026-10-10

**NOT READY for a new production release.** Local repairs are verified; refresh, real-slate and historical-evidence dependencies prevent global certification. No production push/deployment, paid provider call, alert, live bet, production freeze or model promotion occurred. This is the detailed issue ledger; the root trackers remain concise.

## Reconstructed state

- Original checkout: `C:\Users\travi\OneDrive\Documents\ChatGPT\GOING`, branch `codex/agent-infrastructure`, HEAD `3958ed160e7137b4b1d4a2397cdcfa1a076184cd`. Local commits and untracked folders preserved; no private/licensed folder inspected.
- Fetched base: `3f2651e77689b6b525502d87047da68b58c00bc9`, a data refresh after Claude application commit `6716bc8db4afc97e99dc104fab7e1ba60fd8ca84`. Original branch was 195 commits behind upstream after fetch.
- Development worktree: `C:\Users\travi\.codex\worktrees\going-takeover\GOING`, branch `codex/going-takeover`.
- Read-only public evidence: [application CI on 6716bc8 succeeded](https://github.com/daboli69/going-long/actions/runs/38021571957); Vercel Production deployment on that SHA succeeded at 03:44:10Z. [Latest inspected refresh failed](https://github.com/daboli69/going-long/actions/runs/38021571991) at Report source failures. [Pages deployment on 3f2651e succeeded](https://github.com/daboli69/going-long/actions/runs/38021924527). Vercel and Pages are distinct evidence.
- Live Vercel `/long/` returned HTTP 200 at 12:51:57Z, about 595 KB HTML. Alias bytes not matched to a Git SHA; deployment success does not establish provider health.
- Original Claude report not found. Used user handoff, Git, public deployment/workflow evidence, relevant launch/calibration/DFS reports, research source/aggregates, workflows and tests. Full private empirical reproduction and every application surface were not completed.

## Issue ledger

| Severity | Evidence / reproduction | Repair and verification | State |
| --- | --- | --- | --- |
| P0 | Fresh unknown statuses, missing candidate IDs, contradictory sources and timestamp-only malformed feeds could pass eligibility. Corrupt week99 hid current Out; explicit missing input and malformed UTC offsets differed across languages. | Shared engines require active identity, reconcile status/team, validate structure/week1–22/offsets and use roster's authoritative week. Direct tests plus 54 shared adversarial JSON cases. | Fixed locally |
| P0 | Unknown-profile props and DFS fallback projections/kickers bypassed roster identity. Primary Classic callback rebuilt evidence pool directly; saved drafts survived feed changes. | `index.html` gates individual DFS rows by unique name/team/position and current eligibility. Unknown props fail closed. Generic drafts rechecked before display/export/freeze. Classic refreshes on remount, async generation completion and receipt creation. DST team projections exempt from individual identity matching. Integration/UI regressions. | Fixed locally |
| P0 | GOING Score cached cards/movers/comparisons and Python Score/Jackpot builders lacked consistent current candidate exclusions. | Visible candidates filtered; missing/stale engine pauses cards. Python complete-candidate checks use explicit as-of cutoff; Jackpot refuses fresh unsafe output. Immutable historical artifacts preserved. | Fixed locally |
| P1 | Vercel first-parent check skipped code followed by data; packaged data/deletions also needed builds. | Compare all changes since verified previous deployment. Missing/non-ancestor/shallow baseline builds; skip only A/M files served by exact shared live API allowlist. Isolated Git regressions cover chains, merges, deletions, packaged files and baseline failures. | Fixed locally; host run pending |
| P1 | Historical groupby.last paired asynchronous sides never jointly posted; receipt cutoff absent and normalized-name identity ambiguous. | One intact observation; vendor and receipt before kickoff; reject ambiguous IDs, unsupported markets and non-REG dates. Ten offline regressions. Old aggregates not regenerated from unavailable inputs. | Extractor fixed; empirical evidence blocked |
| P1 | First-TD summaries grouped concurrent games by date and assigned another game's scorer. | Exact scheduled day/home/away game, same-game scorer, per-game overround/coverage. Five regressions. | Fixed locally; first/last TD unvalidated |
| P1 | Non-atomic Sunday manifest, offset-string kickoff ordering and missing roster provenance. | Exclusive atomic strict-JSON publication; six writers produce one complete immutable file; compare instants and hash roster. Temporary-repo tests cover Eastern date, passed kickoff and idempotence. | Fixed locally; production freeze untouched |
| P1 | Touchdown Throne refresh failure omitted from workflow final report. | Explicit failed-refresh summary; partial successful snapshots remain recoverable. | Fixed locally; workflow not triggered |
| P1 | npm high advisory, source-map-js 1.2.1. | Lockfile 1.2.2; npm audit zero advisories. | Fixed locally |

No known P0 remains in the audited scope after independent review. This is not exhaustive certification of every surface, sport, identity edge case or private environment. Fresh timestamps do not prove complete official game-day actives; general historical joins still require exact event/team/player contract provenance.

## Model evidence

No production parameter, Champion/Challenger choice or ABBEYS constant changed. Passing-yards refit, receptions correction and market-anchored game lines remain inherited behavior. Probability cautions retained. Receptions live slope, DNP correction, TD slopes, rushing share and receiving-role rejection are prior reports, not newly estimated results.

`research/prop-lines/out/passyds_lines.txt` historically reports 119 modeled QB-games and 1,452 posted lines:

| Inherited result | Raw v1 | Refit | Market / line |
| --- | --- | --- | --- |
| Main Brier, lower is better | .3055 | .2627 | .2500 |
| Main yardage MAE | 73.6 | 61.6 | 59.2 |
| Alternate Brier, >=2 books | .3006 | .2634 | .2496 |

These are **pre-repair artifact values, not independently reproduced Codex before/after predictive performance**. All-alternate slope .51 and >=2-book subset slope -.23 describe different samples. Rebuild before accepting sample sizes, intervals or superiority. Internal improvement does not establish market information or profitability. Synthetic fixtures verify counterexamples, not accuracy. No new ROI/CLV, predictive gain or betting edge claimed. First/last-TD and correlated parlay probabilities remain research-only. Follow frozen Model Gate in `MODEL_RESEARCH.md` for next experiments.

## DFS and product

- Full suite passes existing salary, slots, captain multipliers, locks, exposure and optimizer fixtures; specialist separately ran 57 DFS tests. This is not actual October 11 contest validation or projection/field-ROI backtesting.
- Different objectives can share an optimum; comparison text reports identical rosters. No evidence identical results alone prove an optimizer defect. No competitive profitability claim.
- Browser-imported ownership models with `lineup_calibration` are consumed. No automatic `StatApi` loader exists. Reported private calibrated file unavailable in public worktree; excluded original folder not inspected. Coefficients, holdout results and real-file integration remain unverified. Player ownership sum is distinct from lineup probability/duplication. No new duplication calibration produced.
- Product improvements: honest availability pause/withdrawal on Score, props and DFS. Existing visual system preserved; no broad redesign or speculative recommendations.
- Local Vercel browser smoke: Today/Best, GOING Score and Classic import, 375×812 mobile and 1365×900 desktop. No horizontal overflow in checked states; mandatory contest import/empty state worked. No actual CSV supplied/imported. Static local API fallback is not production-refresh integration testing.

## Validation and rollback

Source commits: `fbbb8f0` availability/DFS/freeze; `30cbb4b` deployment/refresh/dependency; `52c5b79` quotes/first-TD. Revert in reverse order on an authorized release branch; never reset user work. None pushed.

Source revision `52c5b79` after review: **Node 620/620; Python 426 tests with five skips; npm run build; node scripts/build_vercel.mjs; npm audit zero; diff whitespace checks.** Baseline Node 604/604 and Python 401 with five skips. Skips reflect unavailable optional/private inputs, not suppressed failures. First final build met a Windows directory lock held by the owned smoke server; stopping it resolved the lock and both builds passed. Existing bundler script/asset warnings remain.

Final documentation commit receives both full suites/builds before delivery; exact tested SHA reported in final response. Logs preserved under ignored `.cache/codex-takeover/`. New branch has no remote CI result because not pushed; earlier public CI applies to 6716bc8 only. No separate lint/typecheck configured. Changed-source credential scan is bounded, not certification of history or private inputs.

Specialists: availability/parity; quantitative/DFS/quotes; separate adversarial QA. Reviewer found additional Classic bypasses, deletion and malformed week/offset cases; repairs reviewed again with no further actionable defect in scope. Maximum three concurrent agents including manager respected, with review after initial specialists finished.

## Resume priorities and manual dependencies

1. **P1 refresh:** inspect failed public workflow steps; recover props freshness/503 from recorded public responses/mocks first. No metered call without cost authorization. Verify source completeness/provenance and official inactive coverage; 36-hour checks do not certify game-day status.
2. **P1 real DFS:** obtain official October 11 contest CSV from authorized source; record SHA, contest/slate and exact games. Check actual IDs/salaries/positions/kickoff; Classic nine slots/$50,000 or Showdown six/one 1.5× captain; exclude unavailable candidates; exercise all objectives/late swap. Licensed ownership stays private. If supplied, verify accepted calibration schema/browser provenance. No invented slate.
3. **P1 empirical evidence:** rebuild permitted raw history with exact contracts and both clock cutoffs. Freeze folds/holdout/criteria before same-sample Champion/market/simple comparison with clustered uncertainty. Replace claims with dated regenerated reports; no automatic promotion.
4. **P1 freeze:** inspect October 11 production artifact only after naturally created. Check before earliest kickoff, hashes/freshness and immutable idempotence. Diagnose missing workflow artifact; never trigger a production write-once freeze as a test.
5. **Private scanner:** not verified running. On actual host, Travis can inspect expected task/service/process and sanitized recent heartbeat/run timestamps without starting it, enabling alerts/--send or exposing credential-bearing commands. Public tracker workflow does not prove private scanner operation.
6. Broader remaining product/accessibility/performance audit: Markets, Games, Signals, Parlays, Evidence, Charts, Targets, Jackpot, Results; deeper NCAA identity/freshness and point-in-time features. Do not mark these completed.

Separate approval required for production publication, paid/metered data, excluded private input, material auth/database/architecture changes and model promotion. Ordinary isolated work remains authorized. No persistent continuation scheduled.

Deployment references: [Vercel exit-code behavior](https://vercel.com/kb/guide/how-do-i-use-the-ignored-build-step-field-on-vercel), [previous-deployment SHA guidance](https://github.com/vercel/vercel/discussions/7251). Missing/unavailable SHA conservatively builds without fetching.
