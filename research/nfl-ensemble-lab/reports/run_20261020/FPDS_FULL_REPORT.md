# FPDS full report — Amendment 6

**Completed:** 37-file append-only ingestion/audit, as-of feature store, resumable research/weekly commands and local aggregate viewer.269 configurations attempted; 265 discovery completions, 4 recorded checkpoint failures. ONE frozen 2025 pass completed without failures; 2026 scoring is descriptive. 2 frozen configurations met the complete statistical shadow gate; nothing promoted.

**Data:** 210,146 valid weekly rows;5,270 identity/join-excluded rows. 27 possible export caps; five separation tables lack 2021. All 37 exports cover 2026 weeks 1–6, but coverage is not completeness. Strict later-week/final-kickoff+24h audit and canaries passed. Original publication dates and earlier vendor revisions remain unverified.

|Family: displayed discovery result|Metric; n / games|Delta [corrected95% CI]|Decision|
|---|---|---|---|
|H1: rec|Poisson deviance;6196/815|-0.01359 [-0.02383,-0.00337]|Rejected / exploratory; no confirmed frozen change|
|H2: rush_yds|MAE;2740/814|-0.3872 [-0.73,-0.04233]|Rejected / exploratory; no confirmed frozen change|
|H3: rec|Poisson deviance;6196/815|+0.01693 [+0.002427,+0.03013]|Rejected / exploratory; no confirmed frozen change|
|H4: pass_tds|Poisson deviance;620/330|-0.01267 [-0.04266,+0.01615]|Rejected / exploratory; no confirmed frozen change|
|H5: rec_yds|MAE;2037/271|-0.07482 [-0.2889,+0.1386]|Rejected / exploratory; no confirmed frozen change|
|H6: rec_yds|MAE;2037/271|-0.1093 [-0.4195,+0.1724]|Rejected / exploratory; no confirmed frozen change|
|H7: rec_yds|MAE;2037/271|-0.104 [-0.3102,+0.09998]|Rejected / exploratory; no confirmed frozen change|
|H8: pass_tds|Poisson deviance;620/330|+0.03436 [-0.01721,+0.0878]|Rejected / exploratory; no confirmed frozen change|
|H9: rec|Poisson deviance;6196/815|-0.0344 [-0.05828,-0.0126]|Challenger; 2 frozen confirmations|

**Frozen confirmation (2025; same selected configuration, no tuning):**
- rec stacked: Poisson deviance 1.449 → 1.397; delta -0.05196 [-0.07519,-0.02887], n=2016/272 games. Interval shown is paired95%; all corrected diagnostics remain in JSON.
- rush_yds stacked: MAE 25.41 → 24.38; delta -1.027 [-1.58,-0.4929], n=896/270 games. Interval shown is paired95%; all corrected diagnostics remain in JSON.

**Recommended changes:** only statistically qualified frozen stacks merit further shadow review; all other target configurations retain the control. No tradable edge established: game closing lines benchmark forecast loss; historical prop prices are absent. Pseudo-lines are calibration diagnostics, not price-edge evidence.

**Concerns:** selected family displays are exploratory; 269 trials and finite2,000-draw bootstrap tails, revised/truncated exports, prior 2025 exposure, overlapping unit averages and unmatched identities limit inference. The winning stacks are compared with linear controls: gains combine model family, paid data and shorter windows. Same-family, matched-window free-NFL controls are untested; FPDS-specific incremental value is not isolated. H7 causal on/off and replacement effects, coherence, stability and scenarios remain unvalidated. Earlier usage exhaustion consumed existing account credits; no purchase was initiated, but this session cannot be claimed$0.

**2025 game benchmarks:** margin MAE 10.4 vs closing 9.72, delta +0.717 [+0.342,+1.11], n=272; total MAE 10.7 vs closing 10.4, delta +0.292 [-0.0796,+0.686], n=272; win Brier 0.234 vs closing 0.212, delta +0.0223 [+0.00947,+0.0348], n=271. Forecast loss only; separate registered market-informed blends remain labelled in the aggregate JSON.
**Weekly / Needs Travis:** stale-schedule default selection is fixed (four fixture tests); keep all 37 full-history `week N` exports (docs/FPDS_WEEKLY_DOWNLOADS.md); run `run_weekly_fpds.bat --week 8`. Open `launch_lab.bat` → Research → FPDS Research for aggregates. Private subscription-derived rows must stay local.
Week 7 revision archived for 14 unstarted games; completed-week training cutoff=week 6 (2026-10-19); reviewed private projections/leans available. Every row remains investigation tier C.

**Checks:** 353 passed, 1 skipped, 522 warnings in 324.38s (0:05:24). 37 original Inbox files unchanged; forecast timing/cutoff/quantile/simplex checks passed. Existing 191 forecast/champion files checked; changed=0. No evaluation command, promotion or deployment. **Next:** verify uncapped exports/publication snapshots, preregister same-family matched-window free-NFL controls and reduced-table validation; never iterate on 2025.
