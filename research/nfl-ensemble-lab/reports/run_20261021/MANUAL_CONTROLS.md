# Manual FPDS controls — 2026-10-21

Completed: the full-history subfolder is authoritative. Loose older Inbox exports cannot replace it; later full-history weekly exports must preserve schema and historical coverage. Imports remain hashed, local and append-only.

Open `launch_lab.bat` → **Research → FPDS Research**. Choose the target week and **Games + props**, **Games**, or **Player props**:

- **Run projections**: refit matched NFL-only and NFL+FPDS shadow ensembles on all eligible seasons from 2021 through the available completed-week cutoff; simulate the selected unstarted week.
- **Compare FPDS**: matched 2022–2024 expanding development comparison for winner probability, margin, total and six prop targets, with paired whole-game uncertainty intervals. These seasons were previously examined; this is exploratory, with no new 2025 confirmation or 2026 selection.
- **Prepare data**: refresh/import and prepare inputs before a manual run. Starts require a click; jobs checkpoint and support exact resume. Existing forecasts remain unchanged.

Command alternative: `run_manual_fpds.bat` opens the menu. Example: `run_manual_fpds.bat project --week 8 --scope all --sims 10000 --seed 17`. Full runbook: `docs/FPDS_MANUAL_RUNS.md`.

|Verification|Result|
|---|---|
|Real cached preparation|37 FPDS groups; 224 matched free-NFL player window features; seasons 2021–2026|
|New real manual model fits / results|0; comparisons remain pending manual launch|
|Final full test suite|382 passed; 1 existing skip; 522 warnings; 326.35 seconds|
|Integrity|37 source files unchanged; prepared and old forecast hashes match; champion preserved|
|Launch guard|Committed protocol/source checks passed; one active job maximum|

Amendment 7 was committed before any manual fit. Its fixed ceiling is 104 output configurations; actual attempted fits are recorded per job. No configurations were tried on real data during this implementation. Synthetic/mocked fits are tests only.

Concerns: revised historical exports and unknown publication times limit retrospective conclusions. Forecast intervals use labelled warm-up residuals unless matching earlier out-of-fold results exist. Simulations are distribution draws, not the play-by-play simulator. Future weeks use information available now; future injuries/lineups remain unknown. Historical prop prices are absent. All outputs remain shadow, unvalidated tier C; no promotion or price-edge claim.

One real preparation attempt exposed `posteam` versus `team`; both schemas are now supported and tested. Failed jobs/logs were retained. Existing unrelated edits were preserved. Needs Travis: launch the local app and explicitly start the desired forecast or matched comparison.
