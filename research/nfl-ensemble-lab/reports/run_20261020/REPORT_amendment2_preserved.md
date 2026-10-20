# Week 7 shadow run - October 20

**Completed:** Part 1 finished 07:31 ET. Eight-hour window: 07:31:35-15:31:35 ET, completed. Frozen recency-weighted revision 2 covers 14 games, trained through completed week 6 / October 19. Both anchors, six props and first offensive TD; consensus/alternate/DFS/exchange labels, nonnegative intervals, coherence tables and view-only Streamlit page. Original 15 forecast hashes match.

**Leans:** [ranked sheet](C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/reports/leans_2026_w07_r02_20261020T185328300076Z.md) / [CSV](C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/reports/leans_2026_w07_r02_20261020T185328300076Z.csv): 3,443 comparison rows; A=0, B=1,184, C=2,259. These are investigation-readiness tiers, not win probabilities. Final refresh 14:47 ET; latest usable source quote 11:08 ET. 3,090 rows current; 353 unavailable. Quotes older than 24h cannot be current.

**Model research:** differences below are loss minus comparison, with paired game-cluster 95% CIs (2,000 draws). Twenty-two primary Holm slots: **no gate passed**. Benchmark rows show original v1; complete paired baseline-B/weighted/stacked results: [B3 table](C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/reports/run_20261020/B3_COMPARISON_2022.md). All six closing-feature tests and secondary diagnostics: [saved results](C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/reports/run_20261020/PART1_RESULTS.json). Closing lines are retrospective benchmarks/labelled ablations only.

| Hypothesis | Split / n | Metric delta [95% CI] | Decision |
|---|---|---|---|
| Pass-yard ensemble vs v1 | 2022; 478 / 264 games | MAE -1.625 [-3.769,+.551] | Rejected gate |
| Reception ensemble vs v1 | 2022; 1,749 / 271 | Deviance -.089 [-.130,-.048] | Rejected Holm gate |
| Receiving-yard ensemble vs v1 | 2022; 1,749 / 271 | MAE -.398 [-.835,+.042] | Rejected gate |
| Rushing-yard ensemble vs v1 | 2022; 819 / 271 | MAE -.297 [-.956,+.322] | Rejected gate |
| Closing-feature ablation | 2022; 8,576 stat rows / 271 | ATD Brier -.00030 [-.00087,+.00020]; rush MAE +.123 [+.050,+.201] | All six rejected |
| Margin blend vs closing | DEV 2019-22; 1,055 | MAE -.00064 [-.00733,+.00632]; CRPS +.00323 [-.00209,+.00912], n=799 | Rejected |
| Total blend vs closing | Same; 1,055 / 799 | MAE/CRPS 0 [0,0]; fitted w=0 | Rejected |
| Additional game search | DEV only; 1,661 trials | Best single MLP: 2022 LL gain .000496; CI unestimated | Challenger, adaptive DEV only |

**Concerns:** 4,795 exact benchmark matches, not all 8,576; original v1/B lack TD targets and use retrospective QB/roster eligibility. Three-seed 10,000-sim diagnostics: 5,490 stable / 68 unstable outputs, including zero-role outputs; precision is not accuracy. Twenty-six QB-out scenarios lack eligible replacements; scenario efficiencies stay fixed. All teams have coherence gaps; ATD sums count distinct scorers, not TD count. First-TD settlement is unverified. Unmatched: 1,293 stat-ineligible quote rows plus 71 unresolved/non-player rows, including Defense; no IDs guessed. No T-90 inactive lists yet. Startup-analysis failure retained; completed-search analysis succeeded separately. No untouched validation or 2026 selection claim.

**Next:** frozen once-only 2023-25 weekly check deferred for runtime; improve pregame eligibility/scenario coverage before further claims.

**Needs Travis:** review [Task Scheduler steps](C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/docs/PHASE10_DATA_ARCHIVE.md); no tasks registered. Model promotion requires approval.

**Checks:** 261 passed, one pre-existing skip, 518 warnings (321.02s). Champion/v1 unchanged; no eval, spend, sends, deployment or database writes. Bulk archives remain local; integrity manifest records their paths/hashes.
