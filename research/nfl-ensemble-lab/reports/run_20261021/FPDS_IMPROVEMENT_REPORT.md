# FPDS improvements — 2026-10-21

Implemented all five families as local shadow challengers and completed the fixed2022–2024 discovery assessment. No champion, simulator, default forecast or previous archive changed. No new2025 evaluation or2026 selection.

|Finding|Reference → new|Delta [corrected95% CI]|Decision|
|---|---|---|---|
|Rushing-yard median; n=2740/814 games|24.88237 → 24.27310 (-2.45% loss)|-0.60928 [-1.06802,-0.12640]|Point signal only; intervals under-cover|
|Receiving-yard median; n=6196/815 games|24.11674 → 23.65936 (-1.90% loss)|-0.45738 [-0.76455,-0.17521]|Point signal only; intervals under-cover|
|Winner: richer NFL features; n=813/813 games|0.23450 → 0.22724 (-3.10% loss)|-0.00726 [-0.01645,+0.00086]|Uncertain; interval includes zero|
|Winner: FPDS increment; n=813/813 games|0.22724 → 0.22666 (-0.26% loss)|-0.00059 [-0.00372,+0.00225]|Uncertain; interval includes zero|
|Margin: richer NFL features; n=815/815 games|10.03459 → 9.88206 (-1.52% loss)|-0.15252 [-0.54121,+0.22757]|Uncertain; interval includes zero|
|Targeted anytime TD; n=8042/815 games|0.19229 → 0.19012 (-1.13% loss)|-0.00217 [-0.00343,-0.00100]|Still behind NFL-only TD ensemble|

References differ: yardage medians are compared with the target-specific FPDS equal ensembles, richer NFL games with A7 NFL-only, FPDS winner increment with the richer NFL control, and targeted TD with the previous all-FPDS ensemble. Lower loss is better. Yardage/margin use MAE, winners/anytime TD use Brier. Both improved yardage directions held in3/3 discovery seasons. These are previously examined seasons, not independent confirmation.

Totals did not improve reliably: richer NFL total MAE10.39180 →10.50728. Weighting/stacking gains were all below the registered1% minimum. The repaired coherent models worsened point losses in all12 versions; passing-TD deviance worsened24.8%–45.0%. Arithmetic coherence alone is not accuracy. Other-player fractions averaged about15%–38% across variants; maximum numerical reconciliation error1.14e-13.

Coverage concern: direct rushing-yard80% ranges covered73.25% (reference78.98%); receiving-yard ranges75.36% (reference79.81%). Median accuracy improved while interval calibration deteriorated. No direct claim about a better predictive mean or a pure FPDS-provider effect follows from changing model objective/family.

Saved benchmarks: winner Brier for richer NFL+FPDS0.22666 versus unchanged champion0.21986 and closing market0.20989; margin MAE for richer NFL control9.88206 versus champion9.69704 and closing9.41840. No demonstrated champion/market win. Champion comparisons are descriptive: it used longer history and was selected on these examined years; closing prices can have later information. Saved champion totals were unavailable. Historical prop prices remain absent.

Completed / failures: initial study147 output configurations,2591 fitter dispatches,178 missing-auxiliary-label block failures,0 nominations under its unchanged global failure rule. A separate pre-registered12-output repair used750 dispatches and completed180 blocks/12 full identical-sample comparisons with0 failures/0 nominees. Unknown role labels were excluded only from auxiliary training, never replaced with0; every evaluation row remained.845/13219 historical player-game/team keys lacked exact auxiliary observation matches. Successful other families were not refitted. Original failures/results remain immutable. Including144 preparation-only rating dispatches:3485 total dispatches;159 output versions (147initial+12repair). This is not a parameter search or159 independent discoveries.

Checks: full suite405 passed,1 existing skip,522 warnings; latest targeted suite20 passed after aggregate-view changes.54 protected source/model/forecast files had identical hashes and modification times. Parent and repair A7 input hashes also matched. Existing unrelated changes were preserved. Included Codex allowance used; no new paid service or provider request.

Use: launch `launch_lab.bat` → Research → FPDS Research → Model improvements — Amendment8. The view combines65 completed original non-opportunity variants with12 repaired variants, retaining separate failure/trial history. `run_fpds_improvements.bat status` shows saved study states; full runbook: `docs/FPDS_IMPROVEMENTS.md`.

Next: compare the median approach against an equally specified NFL-only quantile model to isolate provider value; preregister earlier-OOF interval/conformal calibration; freeze any prospective challenger before future games. Nothing is approved for replacement. Inherited A7 prop targets use regular-time PBP filtering; overtime/book-settlement compatibility must be resolved before real-price use. No fresh holdout result or price-edge evidence is claimed.

Full original metrics: `A8_20261021T200416Z/REPORT.md` and `SECONDARY.md`. Separate repair: `A8_20261021T204121Z/REPORT.md` and `SECONDARY.md`.
