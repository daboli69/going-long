# Targets, roles and joint simulations — 2026-10-21

Completed all six implementation paths and the fixed matched-control study:43 output configurations,390 fit/estimation dispatches,31 comparisons, zero failed model blocks or comparisons. One reception-count candidate passed its exploratory discovery gate. Nothing is promoted; champion, simulator v1, default projections and existing forecasts remain unchanged. No new2025/2026 scoring or real2026 refit occurred.

Point-model comparisons use the same fixed histogram-boosting specification in both arms.

|Path|Evidence / sample|Decision|
|---|---|---|
|Correct targets/entities|Reconstructed OT/kneels/spikes, scorer IDs and native-ID offensive participation;1073/13219 candidates lack known outcomes. Ambiguous laterals add per-stat exclusions.21/1087 historical games quarantined from drive fitting after scoreboard checks.|New private target version; unknowns never invented as0. No independent official box-score certification.|
|FPDS matched control|Reception Poisson deviance1.49323 →1.47413 (−1.28%); delta−0.01909 [−0.03933,−0.00104],n6153/815games; Holm p=.03898; improves2023/24, worsens2022.|Exploratory shadow candidate only; no untouched confirmation or price-edge claim.|
|Explicit earlier role changes|No target passes; receiving-yard MAE24.25406 →24.23392, delta−0.02014 [−0.08562,+0.05294],n5848/774games.|Rejected for adoption; tiny uncertain point differences.|
|Workload mixtures/scenarios|Passing-yard CRPS43.29977 →44.43110, delta+1.13132 [+0.60616,+1.74626],n1464/795games. Rushing CRPS also worsens.|Rejected. Ranges become too broad; scenario occurrence probabilities stay unknown.|
|Shared game conditions|Joint energy score1.71602 →1.72472, delta+0.00870 [+0.00282,+0.01463],n746games; marginal probabilities unchanged by design.|Rejected. More correlation did not improve the tested joint distribution.|
|Discrete drive scoring|Winner Brier.22724 →.23964; margin MAE9.88206 →10.48573 (delta+.60367 [+.23281,+.99708]); total10.50728 →10.76272.813winner/815margin-total games.|Rejected versus chronological NFL control, not a champion replacement.|
|Group uncertainty checks|Stable-role WR receiving coverage74.24% →79.32%,n2481/761games; stable-role RB stays96.21%,n765/563games. Overall receiving interval-score reduction0.40% misses the1%gate.|Useful descriptive warning; no nominated interval model. Widening cannot fix already excessive ranges.|

Intervals are family-corrected95% whole-game bootstrap intervals (2000 draws); predeclared Holm/sample/season/1% gates apply. These are already-examined2022–24 discovery seasons, not confirmation. FPDS passing-yard MAE improves2.07% in point estimate but its corrected interval includes0. Other provider targets do not pass. Full31-row results: `A10_20261022T004905095944Z/REPORT.md` and `AGGREGATE_RESULTS.json`; subgroup diagnostics are descriptive only.

Data concern: evaluation uses each stat's matched **known-label cohort**, with pregame eligibility unchanged. It does not validate inactive/void probabilities or the whole candidate slate. New losses cannot be compared directly with older regulation/roster-zero reports. Source publication times/revisions remain unverified. The copula is a statistical prototype, not a physically reconciled play-by-play model. The drive model includes defensive/special-teams scoreboard increments and reports tie mass separately; broader realism did not imply better accuracy. Extra workload variation may overlap uncertainty already present in residuals; that explanation remains a hypothesis.

Use: `launch_lab.bat` → Research → FPDS Research → **Targets, roles & simulations — Amendment10**. Optional group coverage is inside that expander. `run_fpds_simulation.bat status` reviews saved states; the runbook documents bounded audit/research/resume and explicit private shadow projection commands. New snapshots never replace defaults. Manual2026 projection I/O was tested with mocked estimators; a real recent-data fit was not run.

Next / Needs Travis: independent official player-stat snapshots are needed for certification; preserve the reception candidate for a separately frozen prospective comparison. Do not adopt role mixtures, copula or drive changes from this run. Promotion still requires approval and stronger evidence.

Checks: final full suite436passed/1existing skip/522warnings in330.19s;21targeted checks also passed. The actual aggregate/group app view renders, and completed-run CLI resume refuses without modifying status. All19actual input hashes and1447/1448broader prior-run hashes match. The unused shared games cache changed during the existing21:00ET scheduler refresh; this study did not consume it, and no task was created or invoked here. Champion pointer remainsv20261016_212540. Both public JSON files passed row-identifier guards.

Run used pre-fit scientific source4bbc59c and committed protocol365948d. Post-run work only hardens checkpoint/overwrite/source guards, bounds explicit projection runtime and caches repeated reference reads; no models or metrics were rerun. Preparation-only null-team failure and audited snapshot remain separate and immutable. Unrelated edits preserved; raw/row-level FPDS stays ignored.
