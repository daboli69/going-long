# Weekly folder workflow — 2026-10-22

## NFL Meta fallback — 17:22 ET follow-up
- Owner Codex/data/QA. User explicitly authorized NFL Meta injury API as a fallback when the post-week injury CSV is absent. Acceptance: option 6 works without CSV; original feeds remain; bounded Free-only requests, timestamped append-only private snapshots and exact roster mapping; no key in tracked files/logs; no model override or frozen-forecast rewrite.
- Implemented collector, hidden local configuration prompt, no-CSV reconciliation and app/runbook messages. Credential remains unconfigured; no authenticated API request, fit, eval, source CSV read or forecast regeneration performed. The key shared in chat was not copied; rotate it and enter its replacement locally. Free policy verified in public provider docs; paid-plan keys intentionally blocked.
- Targeted 52 checks passed. Initial synthetic identity assertion failed because its fixture bypassed existing name normalization; corrected fixture, rerun passed. One multi-file documentation patch failed atomically on a stale heading; reapplied with verified context. No tests weakened/skipped. Full suite running. Existing unrelated changes preserved.
- Initial unscoped pytest collected duplicate archived release test modules and stopped with 36 import-name collection errors. No source/tests deleted or changed to bypass them; rerunning the complete active `tests/` suite, the intended lab test directory.
- Final verification: active suite488passed/1existing skip/522warnings in338.19s; latest targeted52passed after cache/partial-page and hidden-prompt guards. `git diff --check` passed. Ignored credential/raw-data paths verified; staged privacy scan found no data files or credential-shaped values. No authenticated request/live refresh/fit/eval/promotion occurred. Follow-up needs Travis: rotate the chat-shared key, run the configure command locally, then START_HERE6. Forecast regeneration remains a separate missing connection; this change makes no injury-adjusted projection claim.

## Working
- Implementation complete; commit/push verification only remains.
- Owner Codex (data/UI/QA). Started08:47 ET. User authorized creation of Week 7–18 directories inside the previously read-only authoritative Inbox folder; this exception covers mkdir only, never source-file edits.12directories verified. Acceptance: Tuesday entry reads target Week folder, retains historical years, refuses future outcomes/missing tables, archives new frozen revision, scores prior frozen outputs, exposes app tables; separate injury context import; no model-policy changes or real fits during setup.

## Problems
- Initial targeted suite:2 failures/49passed exposed a source-selection parameter being overwritten by the baseline filename marker. Corrected variable scope; rerun51passed. No tests weakened/skipped. One combined documentation patch was rejected atomically on a mismatched README line; corrected, no partial source change.
- Injury status context cannot be claimed to alter frozen models; current configs do not validate that mapping.

## Completed
- Synthetic importer/menu/safety checks51passed. No source CSV contents printed, raw data committed, live refresh, fit, eval, promotion, task creation or deployment. Unrelated edits preserved.

## Next
- Finish end-to-end fixture/app checks, full suite, commit/push metadata and code only.

## Needs Travis
- Put all37 registered exports into Week8 on Tuesday after Week7; use START_HERE3. Add current injury-reports.csv to Week7 and use6 when ready.
- Expanded QA99passed (2existing warnings), including synthetic successful Tuesday orchestration, frozen prior-week game/prop scoring, archive-after-kickoff exclusion, working-history overlay idempotence, +24h/week completion gate, and real Streamlit fixture tables/filters. First cutoff fixture lacked the existing required gameday field; fixed fixture schema, passed. Full current suite in progress. Real readiness-only plan confirms37 baseline tables and12empty managed folders, no import/refresh/fit performed.

- Final QA: full current suite459passed/1existing skip/522warnings in334.92s; latest targeted28passed after preserving frozen schema admission and mid-read injury hash protection. START_HERE real Q smoke passed; readiness-only real plan37tables/12emptyfolders. No live import, model fit, eval, promotion or refresh. Frozen schema contract and source-week gates retained; manual launches blocked during folder updates. Reports/old forecasts remain immutable. Full suite collection preceded one added schema-contract regression; that regression passed in the final28-check targeted run.

- Injury-source follow-up09:13 ET (Codex/data/UI/QA): original official/ESPN/NFL.com/live refresh paths remain active. START_HERE6refreshes them before CSV import; existing live refreshes compare imported weeks automatically. Exact weekly-roster joins, pregame observation times, explicit unknowns, latest observed official precedence, secondary-source agreement/conflict/CSV-only labels. CSV supersedes only earlier CSV context; source versions and forecasts remain immutable. No new model input, probability adjustment, promotion or live source refresh executed during implementation.48targeted tests passed, including source-refresh ordering, source failure isolation, private append-only comparisons and aggregate AppTest. Full suite in progress; no failures so far.

- Injury follow-up final verification: full suite479passed/1existing skip/522existing warnings in331.19s; latest48targeted checks passed including the supplemental-failure isolation regression added after full-suite collection. No tests weakened/skipped. No actual provider call, CSV import, model fit, eval, forecast rewrite, source deletion or scheduled-task change performed. Unrelated working files preserved; raw/derived FPDS ignored.
