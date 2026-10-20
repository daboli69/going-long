# Phase 10 Amendment 2 — 2026-10-20

- Start: 06:34:55.5066185 America/New_York. Start SHA 1d60d120b49266b681b9e84c5b7255f0a95e889e.
- Branch codex/projections-20261019; Part 1 deadline 09:04:55; hard stop 17:34:55.
- Part 2 start/end pending completion of Part 1; eight hours includes last 45-minute wrap-up.
- 16 logical cores, at most 14 / idle priority. Existing unrelated docs/design-reference remains untouched.
- Prior report, preregistration, archive docs and Oct 19 STATUS read. No lab-root STATUS.md exists.
- Initial usage: 1% of five-hour window, 0% weekly; included allowance available. No credit purchase or metered service authorized.
- git fetch origin main complete; remote main fafe9ac. Local archive + refresh running; verify week-6 MNF completion before recent fit.
- Amendment 2 frozen before new experiment execution. Original v1 dev only covers four stats and retrospective eligibility; comparisons must report real intersections, never invent missing TD targets.
- Safety: no original eval call, no promotion, no odds API, keys, send/alerts/database/deployments/tasks. New revisions append; revision 1 immutable.
- 06:45: Step 0 complete: fresh-main archives and refresh succeeded; MNF final and completed-week cutoff 6 / 2026-10-19 verified. Baseline active suite 244 passed / 1 existing skip, 518 warnings, 350.57s.
- 06:53: frozen learned fit and market-implied-feature ablation completed; no family setting changes. Both convex blends are development-only: total chose w=0 in all folds, margin gains not distinguishable from zero. Original v1 dev is still running (buffered output); never invoked eval.
- 06:55: revision 2 forecasts created in a new directory; revision-1 hashes unchanged. Initial comparison export failed only at optional pandas to_markdown because tabulate is absent. Logged/skipped; replaced that formatting call with a plain Markdown writer, without adding a dependency or weakening any assertion. Failure count 1; bounded rerun pending. New fixture/regression suite passed 15 tests before this formatting correction.
- Frozen 2023–25 single look will not start: ~54 full weekly refits at observed multi-minute fit cost exceed the remaining Part-1 budget, even though >1 hour remains. No partial look or saved 2023–25 scoring was performed.
- 06:59: corrected sheet export succeeded. 14 games, 1,908 quote/projection rows; consensus 175, alternate 515, DFS-pickem 831, exchange 387. All nonconsensus gaps blank; nonnegative displayed quantiles verified. Per-team coherence gaps are exposed, not reconciled.
- Current unmatched names/labels: Justin Jefferson (15 lines), Michael Carter, Drew Ogletree, Kyle Pitts Sr.; CHI Bears D/ST, New England Patriots Def/ST, Chicago Defense, New England Defense. Exact-ID ambiguity/absence is preserved; no personal GSIS ID assigned to defense.
- New view-only Projections page reads saved CSVs and filters team/stat/line_type/coherence_flag; no run/promote/send controls. Targeted tests 17 passed, including fixed tolerances, push/no-push probabilities, consensus exclusions, contract guards, output-only quantile floors and eight-hour deadline bounds.
- Original dev is progressing normally (~20 games per 3.5 minutes). Initial 45-minute wrapper-wait estimate was shorter than projected completion (~49 minutes); the waiting wrapper is paused while the SAME original evaluator continues, bounded by Part 1. A first process-identity guard correctly refused to alter the venv launcher; the actual wrapper was then identified/paused, with automatic resume after evaluator exit. No evaluator restart, config change or eval invocation.
