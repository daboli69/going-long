# Six follow-up tests — 2026-10-21

Completed locally:23 output configurations,25 matched comparisons,129 fit dispatches, zero failed blocks or comparisons. All input hashes unchanged. This is previously examined2022–2024 discovery, with expanding earlier-week training; no new2025/2026 scoring, forecasts, promotion or champion change. Protocol/source committed as016e7fc before fits. Private run:20261021T221222Z.

|Test|Result|Decision|
|---|---|---|
|1. Target/entity audit|Overtime changes149 receiving-yard,121 rushing-yard and70 passing-yard labels across2022–24 roster observations;7 anytime-TD labels.845/13219 candidate player/game/team keys lack exact observations;10 match another team,835 remain unresolved.|Definition problem verified; no guessed IDs or invented zeros. Official box-score/settlement reconciliation remains pending.|
|2. Matched NFL-only receiving median|MAE24.12161 →23.79987; delta−0.32174 [−0.53709,−0.09445], n6196/815 games,3/3 seasons.|Exploratory point nominee (−1.33%); its intervals still cover only76.11%.|
|2. Pure FPDS increment, same quantile model|Receiving23.79987 →23.65936:−0.14051 [−0.31453,+0.03814]; rushing24.49717 →24.27310:−0.22407 [−0.52767,+0.04285], n2740/814 for rushing.|Additional provider benefit remains uncertain.|
|3. Earlier-OOF residual correction|Winner Brier0.22724 →0.23217; margin MAE9.88206 →10.08354, delta+0.20147 [+0.06622,+0.33441]; totals10.50728 →10.56225.|Rejected; exact champion residual experiment blocked by later calibration-method selection. Strict chronological NFL control was the labelled surrogate.|
|4. Soft reconciliation|FPDS rushing MAE25.06160 →24.73854; delta−0.32306 [−0.51316,−0.12321], n2740/814,3/3 seasons.|Exploratory nominee (−1.29%) against its own weaker baseline; still worse than either quantile model. Other variants failed the fixed gate.|
|5. Earlier-only interval calibration|Receiving80% coverage75.36% →80.47%; rushing73.25% →79.49%. Interval-score deltas−0.43488 [−0.64123,−0.22558] and−0.72759 [−1.23306,−0.21546].|Useful coverage correction; score reductions0.42%/0.66% miss the1% gate. Medians/MAE unchanged.|
|6. Probability diagnostics/shrinkage|NFL-only anytime-TD Brier0.18984 →0.19502; FPDS0.19229 →0.19661. Winner Brier also slightly worsens.|Rejected. Lower apparent calibration error alone does not ensure useful discrimination or lower Brier.|

Intervals are family-wise corrected95% paired whole-game bootstrap intervals (2000 draws); Holm correction and fixed season/sample gates also apply. Two exploratory nominations, no untouched confirmation. Soft reconciliation is a fixed25% blend, not exact team consistency; the saved hierarchy retains its explicit other-player remainder. Summed scorer probabilities are not expected TD-event counts.

Probability diagnosis: NFL-only anytime-TD AUC falls0.6520→0.6191 and binned reliability error rises0.000341→0.001040; both discrimination and calibration worsen. FPDS follows the same direction. Winner accuracy is unchanged at61.75% for NFL-only despite slightly worse Brier; accuracy alone would miss that regression. The exact binned decomposition retains its within-bin residual.

Interval correction expands mean width from70.33 to73.49 receiving yards and69.97 to75.15 rushing yards. Both point-prediction vectors are unchanged. No finite-sample guarantee is asserted under NFL distribution shifts. Residual experiments inherited baseline interval columns; those columns are not recalibrated residual-model distributions and must not be interpreted as such.

Audit caveats: original overtime-game counts include postseason (changed-target counts are regular-season only); the season-type supplement gives49 regular-season overtime games in2022–24. Existing aggregation excludes kneels/spikes, so overtime inclusion alone does not establish settlement compatibility. Unresolved labels remain unknown. The full audit includes2021 for training-definition context; the table reports2022–24 only.

Next: establish correct official targets/eligibility before price comparisons; preserve the receiving median and calibrated-interval candidates for a separately frozen prospective test. No historical prop-price edge is testable; no new market-edge claim follows. Exact champion residual work requires chronology-safe champion reconstruction, not reuse of globally selected calibration choices.

Use `run_fpds_followups.bat status` for saved states. Detailed25-row results and probability reliability/AUC/accuracy diagnostics: `A9_20261021T221222Z/REPORT.md` and `AGGREGATE_RESULTS.json`. Method/runbook: `docs/FPDS_FOLLOWUP_TESTS.md`.

Checks: full suite415 passed,1 existing skip,522 existing warnings (418.43s); nine new targeted tests also passed before fits. All1448 frozen input hashes matched; three public JSON files passed row-identifier/schema guards. Existing unrelated edits were preserved. No raw FPDS data or individual predictions are included in this report.
