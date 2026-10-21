# Local navigation cleanup

Owner: Codex (UI/UX + builder + QA). Evidence: screenshot shows23 flat sidebar destinations. Acceptance: all23 original pages retained once, six compact sections with at most6 visible pages, session page memory, deep-link compatibility, no model/data behavior changes.

Working: navigation implemented;11 affected AppTests passed. Initial low-priority CLI rejected pytest before tests; idle child wrapper used. Unscoped pytest discovered duplicate archived release tests and failed collection (36 import mismatches); archived releases left unchanged. Run the complete active tests/ suite explicitly. No assertion failure, test weakening or data/model edit.

20:13 active suite first run:277 passed/10 failed/1 existing skip. All10 failures are old page-start tests selecting a non-visible page from the flat radio (ValueError), not page-render failures. Updated their interaction to choose the section first, retained all original assertions and added selected-page assertion. No tests skipped or weakened. Main-entrypoint Projections/Leans/section-return smoke already passed offline.

## Completed
20:19 ET: all23 original page handlers retained exactly once under six sections (2/4/4/3/4/6 pages). Section/page controls use native Streamlit widgets, selected-page descriptions, session memory and existing query links. README updated. Actual main-entrypoint offline smoke: Projections/Leans five tabs each, zero exceptions; section round trip preserves last page.

Final complete active suite:287 passed,1 pre-existing skip,519 dependency warnings,348.01s. All original page-render assertions retained; new selected-page assertions added. All ten obsolete-control failures resolved on next run. No runtime assertion remains failing. Targeted checks11 passed. No models, forecasts, data collectors or deployed website files changed. Rollback: revert this navigation commit; no migration needed.

Final test log SHA256: b9250c298d0f1b1a99cb5850f8ef9e95c97910248d44da8a7280cc17e4a62068
