# Five-family FPDS improvement study

Local shadow research only. The completed A7 job is the frozen source snapshot. No provider website, paid API, new download, spent evaluation, promotion or forecast replacement is involved.

Run `scripts\launchers\run_fpds_improvements.bat` from the lab. It runs the committed Amendment8 protocol for up to three hours, checkpointing completed blocks. Stop with Ctrl+C; inspect private status with `scripts\launchers\run_fpds_improvements.bat status`; resume the exact snapshot with `scripts\launchers\run_fpds_improvements.bat resume --run RUN_ID --hours 3`. Changed source/configuration refuses resume. Failed blocks stay logged and cannot silently qualify a configuration. No automatic retries or parameter searches occur.

The five families are implemented separately:

1. Stronger game inputs rebuild lagged offensive/defensive efficiency, pace, previous-season blending, opponent-adjusted ratings and last-known QB history. Injury rows require a verified earlier timestamp; unavailable reports retain an unknown flag. This restores champion-style information, not the champion's fitted artifact or every advanced feature.
2. Target-specific FPDS groups are chosen by football/schema definitions before fitting. No outcome-based column selection is performed.
3. Conservative weights and stacking use only earlier emitted out-of-fold predictions, with 50% shrinkage toward equal averaging. Warm-up stays equal. Binary calibration also uses earlier emitted predictions.
4. Team opportunities, eligible-player usage shares and conditional efficiency produce a separate coherent prop output, with an explicit other-player remainder. Passing/receiving share the team passing-yard projection. Offensive anytime-TD probabilities follow allocated event intensities; the expected number of distinct scorers differs from the expected TD-event count.
5. Direct quantile heads, hurdle/negative-binomial count distributions and sigmoid/isotonic recalibration are fixed distribution challengers. Quantiles are sorted and floored at zero except margin. Pseudo-lines are lagged last-eight-played-game medians floored plus0.5, diagnostic only. NB-only changes probability shape, not the mean; no primary mean improvement is claimed for it.

Discovery remains 2022–2024, previously examined. No new 2025 confirmation, no 2026 model selection. A lower historical error is exploratory. The registered >=1% improvement, corrected interval, season agreement, identical sample and no-failure rules nominate only; they never promote. Genuine future archived predictions must confirm any change. No historical prop-price edge is testable.

The budget is147 member/head outputs, at most300 internal fit configurations and4500 fit calls. All are counted. Existing A7 predictions are reused rather than refitted for combination/calibration tests. Market lines remain post-fit benchmarks.

Private inputs, models, row-level outputs and checkpoints remain ignored under `data/cache/fpds/amendment6/improvement8/`. Only aggregate research metrics/metadata can be committed. View aggregate results in **Research → FPDS Research → Model improvements — Amendment 8**.

The batch command produces secondary diagnostics once from saved discovery outputs, then formats an aggregate report. Individual member comparisons use the registered game/prop family correction sizes. Bias and pseudo-line probability intervals are explicitly unadjusted secondary diagnostics and cannot nominate a model. Reliability bins retain exact boundary probabilities. The mean need not have50% of outcomes above it; discrete medians may have ties. No new fits or spent holdout scores are involved. `python -m lab.fpds_improve_diagnostics --run RUN_ID` and `python -m lab.fpds_improve_report --run RUN_ID` expose these separate saved-output steps; existing reports are never overwritten.

## Completed run and separate data-label repair

The original study is `20261021T200416Z`; it retains178 opportunity-label failures and zero nominations. Its65 complete non-opportunity variants were not refitted. The preregistered repair is `20261021T204121Z`:12 complete opportunity variants, all original evaluation rows, zero failures, zero nominees. Auxiliary heads train only on finite verified earlier labels; missing source observations are never invented as zeros. The app combines these studies for viewing while retaining their separate trial/failure histories. The recorded repair command was `scripts\launchers\run_fpds_improvements.bat repair-opportunity --parent 20261021T200416Z --hours 1`. Completed snapshots cannot be overwritten or resumed as new evidence. Use `scripts\launchers\run_fpds_improvements.bat status` or the app to review existing results.

See `reports/run_20261021/FPDS_IMPROVEMENT_REPORT.md`: median rushing/receiving forecasts improved, but their80% intervals under-cover; no default model changed. More historical reruns do not provide independent confirmation. Existing weekly projections remain the separate frozen workflow.
