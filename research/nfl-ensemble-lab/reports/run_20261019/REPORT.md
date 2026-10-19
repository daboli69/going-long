# Phase 10 — 2026-10-19

**Completed:** 15 pregame shadow forecasts: tonight's game and all 14 week-7 games. CSV/Markdown/JSON/Excel include both anchors, intervals, six player targets, first TD and available benchmarks. Amendment 1 freeze `9147dd5` preceded newer-data reads; weighted refit cutoff **2026 week 5 / October 12**. Champion/v1 unchanged. $0 spend; no deployment, messages or database writes.

**Model research:** negative deltas favor the challenger; paired game-cluster bootstrap 95% CIs, 2,000 draws. Development only; no fresh holdout claim. Primary multiplicity family: 78 comparisons.

| Hypothesis | Split / n | Evidence | Decision |
|---|---|---|---|
| B1 combined calibration | Games DEV 2019–22 / 1,100 | LL vs champion +.00310 [-.00231,+.00843] | Rejected |
| B1 family search | DEV only / 726 trials | Best MLP replacement 2022 LL gain .00099; adaptive search already used 2022 | Descriptive; no registry update |
| B2 independent scores | REG DEV / 1,055 | Margin MAE 10.191; vs champion +.00023 [-.10098,+.09228]. Total MAE 10.813; vs mean -.39449 [-.58300,-.20828] | Useful baseline; no champion gain; market comparison blocked |
| B3 props ensemble | Fit ≤2021; walk-forward 2022 / 8,576 rows, 271 games | Equal passing-yard MAE vs independent simulator -6.185 [-8.617,-3.856]; ATD Brier -.00503 [-.00842,-.00153] on matched rows | Required original-v1/B benchmarks unavailable; unvalidated reference |
| B4 scoring features / first TD | Same 2022 / 271 games | ATD Brier -.00184 [-.00302,-.00075], Holm p=.07396. First-TD LL -.01876 [-.03935,+.00287] | Not accepted; first TD diagnostic only |
| B5 simulation precision | First 8 fixed 2022 games; 2 seeds | 1,000 sims passes frozen stability limits, ~1.24 s/game; yard-head 80% coverage .817/.790/.793 | Recommend 1,000; small-sample diagnostic |
| B6 prospective retention | 15 unplayed 2026 games | 0 qualified configurations; frozen equal reference archived | Shadow only; no 2026 scoring |

**Data archive status:** 155 source versions recovered; 144 new game-market snapshots, 128 prop snapshots, 11 weather pulls. All seven quote types exist. Independently observed pregame history starts September 10, 2026. Latest remote snapshot: October 19, 13:01 ET; >24h lines marked stale. Current names map exactly except `Defense`; 452 historical ambiguous/unmatched labels reported. Bulk data/models stay local; `ARTIFACT_MANIFEST.json` records hashes.

**Concerns:** no authorized 2022 market/v1/B benchmarks or implied-points ablation. Prior-roster pools missed 26 actual first scorers, retained in scoring. Player simulations cover regulation; first TD excludes passing/defense/special teams. Unverified first-TD settlement and 14 multi-TD count lines prevent price comparisons; append-only corrections preserve original forecasts. Weather/routes lack validated history and are excluded. Failures/repairs: `STATUS.md`. No betting-return claim.

**Checks:** final active suite **244 passed, 1 existing skip**, 518 warnings, 315.30s. Projection audit: zero timing, independence or probability-mass violations across 15 games. Both workbooks rendered/inspected; cached formulas verified. Longrun finished; no active job. `git diff --check` passed.

**Next:** optional frozen 2023–25 single look skipped for the 18:15 deadline; run once in a separately budgeted session. Never invoke `lab.props.evaluate eval`. Continue quotes/inactives; improve prior-roster coverage.

**Needs Travis:** manual Task Scheduler steps: `../../docs/PHASE10_DATA_ARCHIVE.md`; no tasks created. Tonight's T-90 window follows the 18:30 cutoff; inactives parser fixture passed, live pull remains undone. Release activation/promotion requires approval.

**Saved-output follow-up — 2026-10-19.** B2 REG DEV 2019–22; paired game-cluster bootstrap (2,000 draws, seed 20261019). Delta = independent error minus closing-line error, in points; RMSE differences are recalculated within each bootstrap draw. This resolves the earlier B2 closing-line blocker; timestamped pregame snapshots remain unavailable. Closing lines are benchmarks only; no features/fits changed. Initial raw-ID join failed completeness; existing canonical IDs resolve 16 OAK/LV aliases, recovering all 1,055 games. Spread uses home-margin convention (weekly.py team-point formula).

| Metric (independent / closing error) | n games | Delta vs closing | 95% CI | Decision |
|---|---:|---:|---|---|
| Margin MAE: independent 10.1909; closing 9.8882 | 1055 | +0.3027 | [+0.1339, +0.4857] | closing lower error; descriptive |
| Margin RMSE: independent 13.1389; closing 12.7726 | 1055 | +0.3662 | [+0.1811, +0.5613] | closing lower error; descriptive |
| Total MAE: independent 10.8133; closing 10.5412 | 1055 | +0.2721 | [+0.0840, +0.4505] | closing lower error; descriptive |
| Total RMSE: independent 13.5830; closing 13.2003 | 1055 | +0.3827 | [+0.1918, +0.5648] | closing lower error; descriptive |
| B3 original v1 / baseline B | requested 8,576 rows / 271 games | unavailable | unavailable | Saved 2022 v1/B outputs do not exist; skipped. |
| Frozen refit / next-week archive | cutoff 2026 week 5 / Oct 12 | unchanged | n/a | Week 6 incomplete; reuse existing week-7 forecasts. |
