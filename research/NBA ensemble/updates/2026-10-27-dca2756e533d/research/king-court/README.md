# King of the Court research evidence

The research module is implemented and tested locally. **Predictive accuracy, learned recency parameters, actual popularity and a live target list remain unvalidated.** The [pre-implementation specification](../../docs/KING_OF_THE_COURT_SPEC.md) was delivered before implementation; the [usage guide](../../docs/KING_OF_THE_COURT.md) describes the commands and evidence contracts.

## Actual source audit

Current ending-year season 2027 and prior seasons 2024–2026 were downloaded from the free SportsDataverse release archives. Raw source identities, retrieval times and hashes are retained in [source-audit.json](source-audit.json). Underlying feeds overlap with hoopR/ESPN; these are not independent providers.

| Ending-year season | NBA season | Accepted reconciled games |
| --- | --- | ---: |
| 2024 | 2023–24 | 1,229 |
| 2025 | 2024–25 | 1,173 |
| 2026 | 2025–26 | 1,195 |
| 2027 | 2026–27 to retrieval | 51 |
| Total | | 3,648 |

Ninety-four regular-season final games were withheld for missing/unknown minutes or failed player/team/schedule accounting. These counts follow the strict final intake; the initial discovery audit had checked fewer missing-minute conditions. Exhibitions, NBA Cup championship games and nonfinal/postponed rows are separately excluded. Explicit DNP observations are retained as genuine zero minutes/production; unknowns never become zeros. Missingness and failed reconciliations are evidence to resolve, not games quietly removed from a predictive success rate.

This is a box/archive integrity audit. No real raw-event or lineup reconciliation is claimed; zero games have that verification in the retained snapshot. Historical pregame rosters/injuries, true tracking opportunities, official complete promo fields/terms, verified debut metadata and real qualifying-selection counts remain missing. Reading 2026 basketball history is for this separately requested King of the Court history window; no NBA-winner evaluation, fitting or model change was performed.

## Engineering checks

All **35 targeted tests passed**: 24 King of the Court tests plus 11 existing NBA winner tests. They cover season/recency boundaries, rookie/second-year priors, team changes, unknown/future data, independent full-field receipts, source age, boxes/events/substitution minutes, integer opportunity accounting, OUT exclusions, exact customer-level tie splits, missing ownership, immutable receipts and holdout/registration guards. All NBA winner Python source hashes match the earlier winner replay's receipts.

A fully synthetic **20,000-draw** example ran through simulation, statistical settlement and evaluation. A second unresolved-game outcome remained pending, and the original simulation receipt was unchanged. The example includes current-only/equal-history comparators. [illustrative-output.json](illustrative-output.json) retains an explicitly synthetic excerpt and exact code/protocol hashes. Full local receipts and compressed samples are in `.cache/king-court/validated-example*`.

Neither test count nor the synthetic example measures NBA predictive performance. No actual player probability, official selection percentage, cash value, betting edge, calibrated interval or model promotion is asserted.

## Conditions for the next empirical step

Register future development and later holdout Tuesdays against the frozen code/protocol. Capture complete eligible fields, roster/availability/rotation sources, game schedule and offer evidence before the earliest tipoff. Preserve outcome receipts separately. Select decay/shrinkage only on earlier registered folds; then evaluate later untouched slates with same-cohort baselines and whole-slate uncertainty. Report insufficient experience cohorts and slate counts rather than calling the model validated. No interface or publication is enabled by this research implementation.
