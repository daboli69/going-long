# Phase 10 status — 2026-10-19

- Started 16:34:56 America/New_York. Hard stop 19:00; wrap-up starts 18:30.
- Starting SHA: 5ca58e80bd16fcf0fb4283eb8bcdee726f1e602c.
- Branch: codex/projections-20261019.
- Baseline refresh and tests pending; no experiment results yet.
- Initial tracker location was misunderstood. Per user correction at 16:46, trackers are at GOING root; duplicate lab trackers removed. Root tracker appends are explicitly authorized by the amendment.
- Safety: local lab writes only; no odds calls, spending, holdout props use, scoring 2026 or promotion.
- 16:43: baseline active suite passed: 217 passed, 1 pre-existing skip, 518 warnings. Unscoped pytest failed collection on duplicate bundled release copies; active suite is tests/.
- Refresh completed 16:37:38; one source warning, no missing play-by-play seasons.
- Archive fixture tests: 4 passed; ensemble/simulator regressions: 27 passed.
- 16:44: first feature preparation failed one-to-one validation (prior-roster candidate duplicates). Skipped fitting; added evidence-based newer-roster resolution with ambiguous equal-time identities excluded, to be fixture-checked before a fresh preparation.
- Amendment acknowledged 16:46: development stays <=2021 / walk-forward 2022. Freeze selected config as dated Amendment 1 and commit before reading 2023–25 player files; then recency-weighted refit through last completed 2026 week for prospective shadow forecasts, with cutoff in each archive. Optional single 2023–25 pass must finish before 18:15; never invoke lab.props.evaluate eval.
- Authorized freshness correction: git fetch origin main completed without branch switch; latest committed nfl_betting.json will be archived directly from origin/main. Lines >24 hours old must be labelled stale.
- 16:46: verified origin/main snapshot generated 2026-10-19T17:01:50Z (15 games, 1,015 props), unlike stale working-tree copy. Remote archive started.
- 16:47: second preparation attempt passed candidate uniqueness, failed mixed-format ISO timestamp parsing. Logged and skipped fitting; parser changed to pandas format=mixed. No experiment metrics inspected and no 2023–25 player files read.
