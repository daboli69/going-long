# Claude handoff: Going Up independent player-points research

Prepared October 28, 2026. [Download the complete study ZIP](https://github.com/daboli69/going-long/raw/refs/heads/nba-research-transfer-2026-10-27/Going-Up-NBA-Points-Research-2026-10-28.zip). Paths below refer to the extracted study folder. Read [the research report](GOING_UP_REPORT.md) for the research result and this file for implementation/reproduction/merge context. This adds one isolated investigation; it does not replace the existing NBA models.

## User's local project and what ChatGPT could access

Local project:

    C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\NBA ensemble

Earlier installed research:

    C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\NBA ensemble\updates\2026-10-27-dca2756e533d

The earlier installer verified 58 files, with manifest SHA256 dca2756e533d0d3d3e4e6103ad2ea44eeb04d27dca41e6021742a8931479e222. Existing app integration and OneDrive sync were not verified. app.py, nba_lab and START_NBA.bat were not accessible to ChatGPT and were not changed.

This study inspected the recovered cloud workspace /workspace/going-long at Git HEAD 8d8b7a14030960674eef8e4f40da07ffb1d6e8f3. It preserved existing uncommitted NBA research, code/configs, result files and raw caches. registration.json stores initial git status and 56 protected-file SHA256s. New work lives only in research/going-up-points-2026-10-28; Python packages were installed into /workspace/going-up-venv, not an app environment. No production source, schedule, wager, alert, deployment or unrelated GOING component was changed.

## Assignment and hard boundary

Determine whether one opportunity-based generative basketball model improves player-points distributions against a simple prior-outcomes baseline and a valid existing-model reference. No sportsbook information may enter development or evaluation: no prices, lines, implied probabilities, consensus forecasts, betting returns, feature selection from markets, or market priors/targets. The local model must be audited for this condition before its forecasts can become an eligible comparator.

This is one study, not permission to rebuild the app or add UI, markets, prediction architectures or broad feature catalogs. Preserve the frozen original and all user edits. Do not rescue a disappointing result with added features. See PLAN.md and registration.json, plus the dated future-confirmation amendment.

## What was implemented

- A points-only study package named going_up, distinct from the host's scripts and nba_lab packages.
- An independent NBA event-to-box shooting/points auditor. It uses exact game/person IDs, record order, separate related actions and official 2/3/FT arithmetic. No credited assist becomes a tracking opportunity.
- Safe allowlisted basketball input derivation, explicit source hashes, mapped official outcomes, an earlier-only prior-roster proxy and exclusion receipts. Unknown outcomes are not DNP zeros.
- One candidate: partially pooled participation/positive minutes, constrained team minutes, earlier joint game/opportunity templates, Gamma individual attempt rates, integer multinomial allocation and Beta shooting conversion.
- An outcomes-only empirical PMF baseline A.
- Auxiliary B: unchanged KOTC v1 code reconstructed on the same information/cohort with an explicit unknown-experience adapter. This is not the Windows model or an original historical prediction.
- Four development-only recency/prior configurations, chronological stress and later assessments, development-only component/oracle/simplicity/lag checks, two Monte Carlo seeds, discrete calibration/tail checks, and paired game/player and week/player uncertainty.
- Saved per-game forecasts, complete predicted PMFs, identities, origins, observations, evidence/season contributions, exclusions, scores and deterministic settings.
- Independent CRPS calculation from saved PMFs using a different mathematical identity.
- Missing-outcome sensitivity bounds across every nonnegative integer point total, without inventing outcomes.
- Source-preservation checks and separate experimental code/input locks.
- A research report and exportable PNG/SVG diagnostics.

The previous KOTC FGA-pool candidate remains unsupported and inactive. This study does not activate it. The older proposed participation/minutes task is not retroactively declared completed or promoted; the hurdle here belongs to this independent C candidate and has its own evaluation limits.

## Important audit result: old reproducibility defect

Old collect_slates constructs games from a set and sorts by tipoff alone. Simultaneous games can therefore get different global RNG stream segments across Python hash orders. An initial January 6 rerun differed in per-player PRA CRPS by up to .65538. Restoring the saved player/game order reproduced the retained result to about 7.1e-15. Winner scores reproduced to 1.2e-16. The raw event/stint audit also reproduced.

See AUDIT_ADDENDUM.md and data/original-metrics-reproduction-attempt.json and data/original-metrics-reproduction-restored-order.json. The old code was not patched. If fixing this later, create a separate version with an explicit (tipoff, game_id) tie-break and retained RNG assignment policy; do not rewrite old observations or claim old seeds alone fully reproduce the original stream.

## What the result can and cannot establish

All past archives had already been inspected. Historical forecasts generated now are rolling-origin replays under an assumed 36-hour result lag, not immutable actual-time pregame predictions. Strict archived source-known-time enforcement leaves zero historical forecasts. Do not relabel the later March/April period as untouched merely because it was scored after a new code lock.

The Windows player-points model and original immutable forecasts are absent. B in this study is an auxiliary frozen-code reconstruction, with selected C recency parameters for a controlled common-input comparison, not a valid original-production forecast test. No rookie/year-two validation is possible without verified debut metadata. Final interpretation must retain those distinctions even if a numerical comparison is favorable.

The target field uses the latest earlier team box, not the target game's participant list. It can retain departed/unavailable players and omit new joiners. Exact NBA box outcomes are used where present; absent/wrong-team/unknown-minute records remain unscored. Missing-outcome bounds quantify score sensitivity but cannot verify historical roster membership. All primary comparisons use identical scored rows.

Current-season ending-year 2027 rows in the input export are not used for ending-year 2026 predictions. Every target obeys its season-to-date plus the three preceding seasons. Future 2027 forecasts must use 2024–2027. Recency has greater new-season per-game weight; older full seasons can still contribute more total mass. ESS and season shares are in the forecast PMFs' player records.

Original vendor JSON, independent period-start lineup observations and point-in-time injury records were not available. Historical injuries are excluded entirely. Parsed NBA action rows and producer-derived possession/lineup records are not independent providers. The candidate uses a disclosed box possession proxy and joint empirical game templates, not a proven causal or full-possession model.

## Files to read

1. REPORT.md: concise eight-question result; exactly one final study verdict.
2. AUDIT.md and AUDIT_ADDENDUM.md: original audit and independently reproduced evidence.
3. PLAN.md, registration.json, design-clarifications.json and future-confirmation-amendment.json: frozen design and dated amendments.
4. MODEL_SPEC.md: exact candidate, references and limits.
5. code-lock.json: code/data/development/plan hashes frozen before first assessment.
6. runs/development-001/development.json: grid choice, development comparisons and ablations.
7. runs/assessment-001/assessment.json: matched later-period results, both seeds, paired intervals, missing-data bounds and exclusions.
8. runs/components-001/components.json: development-only minute, participation, attempt and residual diagnostics.
   runs/diagnostics-003/corrections.json supersedes the original development ablation table for two diagnosed implementation issues; original receipts and the partial diagnostic attempt remain preserved.
9. runs/*/*forecasts.json.gz: full finite forecast distributions and observed outcomes.
10. runs/*/*scores.json.gz: paired per-player scores.
11. data/inputs.json.gz: portable allowlisted derived input snapshot; raw source identifiers/metadata are embedded.
12. data/raw-reconciliation.json, template-exclusions.json and reproduction receipts: exact evidence/provenance.
13. tests/test_study.py: software invariants, temporal exclusions, roster purity, score verification and missing-outcome bounds.
14. reference/: byte-preserved old code/configs/reports required for auxiliary B. The reference manifest verifies only included files; it does not assert that absent original caches are present.

The final package manifest inventories actual delivered paths and SHA256s. Do not assume old full .cache folders, raw vendor JSON or a complete local app were included.

## Reproduce safely in a separate folder

Recommended local destination for this study:

    C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\NBA ensemble\updates\going-up-points-2026-10-28

Do not extract over app.py, nba_lab, the root requirements, the old versioned installation or existing forecasts. Read local AGENTS.md/CLAUDE.md instructions. Verify the package manifest before using the code.

Use Python 3.12 and an isolated virtual environment. environment-lock.txt records the actual runtime dependencies. Set OPENBLAS_NUM_THREADS=1 and OMP_NUM_THREADS=1 for reproducible finite research runs. The runtime is CPU-only; PyMC/NumPyro were not needed or used.

From the extracted study root:

~~~text
python -m pip install -r environment-lock.txt
python -m pytest -q tests
python -m going_up.reproduce --forecasts runs/assessment-001/later-forecasts.json.gz --scores runs/assessment-001/later-scores.json.gz --output independent-later-score-check-002.json
python -m going_up.run assess --inputs data/inputs.json.gz --development runs/development-001/development.json --lock code-lock.json --output runs/reproduction-002
~~~

Use fresh output paths. The default --repo points to bundled reference/. With --repo /workspace/going-long, the original cloud workspace can also verify all original protected files; the portable reference verifies its source/report subset and explicitly cannot verify absent raw caches. Do not bypass lock failures or edit code-lock.json to make altered code appear original. A materially changed experiment needs a new registration and version.

To reproduce development selection independently, run the develop stage with the same inputs, a new output folder and the bundled reference. To preserve the recorded assessment identity, the assess command above uses the original bundled development receipt, not the fresh receipt's timestamp-dependent file hash.

Full raw rebuild and the old original-study simulation require the original archived inputs/raw caches or exact refetched bytes from recorded URLs. The portable derived dataset permits the new primary scoring/evaluation to be reproduced without claiming raw caches were delivered. Source hashes and raw audit receipts preserve that distinction. If upstream bytes differ, make new receipts and do not forge an old equivalent snapshot.

## Merge into the actual local model

1. Inventory local git status/edits and applicable instructions. Do not reset anything.
2. Inspect app.py, nba_lab, START_NBA.bat, requirements, existing forecast storage and timestamps. Establish how local points distributions really work and whether any market data enters them.
3. Preserve the existing app and models. Add this study as an isolated research folder and reference import/subprocess boundary only. Avoid global scripts package/path collisions.
4. Audit original local forecast snapshots: exact IDs, pre-tipoff known times, model/input versions, predicted PMFs or samples, eligibility and immutable outcomes. Point estimates alone cannot support distribution CRPS without an honestly registered distributional specification.
5. Compare original independent local forecasts with A/C only where genuinely matched. If B cannot be reconstructed without leakage, keep it missing. Do not call the study's auxiliary B the production model.
6. Run the software tests and independent score verifier. Report installation, integration and predictive validation as separate claims.
7. Do not alter thresholds, retrofit priors or add features after reading the assessment. Do not activate C or change the existing winner/PRA models as a merge side effect.

## Genuine forward evidence still needed

The first month-long future reservation could never meet the registered 50-game/2000-observation minimum under one-game-per-day sampling. Before any future outcomes, it was transparently extended to November 1, 2026–February 28, 2027; the original plan remains intact. No automatic collector, scheduler, actual-time forward freeze adapter or future forecast was created.

Before first forward predictions, register a precise local data/roster/forecast-freeze adapter and collect real pre-tipoff source receipts. Preserve original local B forecasts and matched A/C outputs before each cutoff. Historical dated pages downloaded later are not substitute contemporaneous receipts. Require the original practical CRPS, clustered uncertainty, calibration and sample gates; do not extend dates or weaken gates after outcomes. If samples or required forecasts are unavailable, retain the inconclusive interpretation.

## Next message Claude should give the user

State the actual local files inspected, what was verified, which pieces are only installed research, what changed during integration, how it was tested and what remains missing. The research report's conclusion is not permission for production promotion or a claim of accurate or profitable recommendations.

## Final measured result for Claude

The candidate reduced CRPS against A by 5.71% in January–February and 4.19% in March–April. The later game/player-cluster interval crossed zero. Gains against the auxiliary B reconstruction were only .0614 and .0442 CRPS, below the frozen practical threshold, and were not a comparison with the local app. Tail calibration was mixed. The overall report concludes **Inconclusive: insufficient reliable evidence**.

There are 95 assessment games and 2322 scored player-games, plus 184 unknown outcomes. Missing-outcome bounds, eight-batch Monte Carlo errors and both seeds are retained. All 56 protected original files remained unchanged. Fourteen new tests and 48 original tests passed. Independent CRPS verification covered 13281 model forecasts and agreed within 2.2e-14. Original native raw caches are not included; safe derived inputs and forecast PMFs are included.

The registered 80% coverage gate was not changed after outcomes. Because points are discrete and zero-heavy, compare observed coverage to actual PMF-implied interval mass as well as the nominal level. First-game-per-Eastern-date sampling limits all-NBA generalization. Registration timestamps are local process records, not independently attested public preregistration.
