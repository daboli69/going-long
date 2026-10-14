# Private CSV model integration

The intake code is live through PR16/17 (`4a739dd`); private hosted access/storage/uploader configuration is still missing. The separate numeric Challenger below is development work, not the current production recommendation model.

## What actually changes numbers

The receiving-yards Challenger uses three current-season exports: Receiving Advanced (route volume and verified season production), Receiving Man/Zone (conditional efficiency), and the upcoming opponent's Coverage Matrix.

Expected yards = routes/game × (opponent man share × player man yards/route + opponent zone share × player zone yards/route + unclassified share × player overall yards/route).

Unclassified coverage stays at the player's overall rate; its mass is never redistributed to known coverages. That is an explicit neutral-imputation assumption. Missing/one-sided rates, inconsistent route counts, duplicate identities, unmatched current-team appearance cohorts and past games are withheld. Exhaustive conditional routes must reconcile with verified yards within two-decimal export rounding; partial conditional exposure has an explicit residual-validation limitation. Source clocks must precede the future game; public context older than36hours cannot substitute for fresh context. The API uses current public snapshots, because data-only refreshes intentionally skip redeployment.

Actual local Week6 input replay: 224 forecasts,203 differ from the same-player season average,88 exclusions. These are input-sensitivity/engineering results, **not predictive accuracy gains**. Both the original Champion mean and current-season mean are kept as comparators. No calibrated win probabilities, confidence boost, default betting recommendation, eligibility override or model promotion.

## What does not yet change numbers

Other accepted coaching, OL, separation/role, pace, passing, rushing, positional-defense and expected-opportunity exports remain private candidate covariates/research context. They do not have learned numerical weights. They cannot honestly be described as improving every model. TD, rushing, passing and game-line models need separate preregistered experiments with point-in-time inputs and matched future outcomes; broad arbitrary multipliers would violate the Model Gate.

## Validation and privacy

Protocol: `config/fp_model_protocol.json`, frozen before outcome evaluation. The source-schema amendment for nonexhaustive coverage was also frozen before evaluating future outcomes. Untouched2026Weeks6–10, at least250player-games/40gameclusters, paired Champion/simple MAE/RMSE and game/player clustered confidence bounds are required before considering promotion. No Week6+ outcome evaluation has occurred.

`node scripts/fp_model_local.mjs <private FantasyPoints root>` evaluates existing local inputs offline. It writes only beneath ignored `model_inputs/challenger/`, including immutable code/protocol/public-context/source receipts. Those captures explicitly lack verified availability and are **not eligible forward-performance cohorts**. No CSV or numeric metric table is published. With private configuration, the protected reader can calculate and display the separate forecast next to its season baseline; this is not a replacement for production probabilities or DFS projections.

The PC watcher automatically ingests changed CSVs; authenticated model requests recompute from the uploaded current bundle. Private server configuration and a successful authenticated end-to-end smoke test remain release dependencies.
