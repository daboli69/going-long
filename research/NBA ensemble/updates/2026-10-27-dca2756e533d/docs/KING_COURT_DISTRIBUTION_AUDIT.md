# King of the Court distribution audit, before model changes

2026-10-27. This audit concerns the retained v1 source and existing receipts. No v1 model or protocol is changed. Passing arithmetic tests and a synthetic demo are not predictive validation.

| Component | Measured support | Approximation / unresolved assumption | Diagnostic |
| --- | --- | --- | --- |
| Minutes | Weighted current-team appearances; recorded minute variability; optional pregame minute scenarios | Independent positive lognormal draws followed by team normalization; no available-player DNP mixture, explicit foul/blowout state or fitted five-player interaction. Rounded boxes are not exact stints. | Minute coverage/zero mass and PRA changes under observed-minute conditioning |
| Pace | Weighted box-derived pace mean/SD | Lognormal shape; `.44 FTA` possession proxy; shared pace cannot establish measured possession dependence | Raw-event/possession reconciliation where accessible; fixed-pace ablation |
| Attempts | Historical FGA/FTA per possession and per-minute player shares | Independent team Poisson FGA/FTA pools, even after a game pace draw. Variance=mean is not fitted or validated. | Conditional residual variance/covariance and tails; priority candidate for ONE repair |
| Shooting | Weighted makes/attempts and disclosed Beta(1,1) prior | Weighted counts treated as posterior exposures; independent efficiencies; symmetric logit defense adjustment is unfitted | Conversion-only ablation, component covariance and upper-tail checks |
| Rebounds | Integer misses, recorded offensive/defensive capture, player shares | Every missed FT enters a proxy pool; dead balls/non-reboundable misses compensated only through aggregate capture, not event classification | Identify FT sequence/dead-ball evidence; do not relabel proxy as observed chance |
| Assists | Credited assists tied to made field goals, no self-assists | No potential-assist/passing tracking; rate allocation is not measured creation opportunity | PBP credited-assist reconciliation; no inferred potential assists |
| Overtime | Empirical historical OT frequency and period count | Same empirical OT mix for every matchup; not fitted to closeness | Observed OT frequency, fixed-regulation diagnostic; preserve original OT model |
| Dependence | Shared pace, minute constraints, common shot/rebound/assist pools | Within-player and across-player covariance not empirically validated; team attempt coupling conditional on pace is absent | Component correlations; marginal-preserving player shuffle; slate-max distribution |
| Experience/recency | Explicit rookie/second-year prior code; rolling four-season boundary and an earlier-fold selection contract | Real debut metadata and archived complete pregame slates absent; no selected parameters in existing receipts | Do not invent experience; report unknown strata. Separate diagnostic parameter choice from valid prospective calibration |

Priority hypothesis: Poisson field-goal-attempt variation may inflate conditional opportunity variance and distort the joint PRA upper tail. This is a hypothesis from source inspection, not a measured conclusion. Before changing this component, compare its implied variance with eligible historical conditional FGA residuals. If unsupported, report it and do not claim a successful repair.

Existing boxes have already been inspected for intake integrity and are reused research material. No historical season will be called untouched. A comparison conditioned on the recorded box field or observed minutes is a posterior-predictive diagnostic, not a reconstructed pregame forecast. Historical availability, an eligible promotion field and debut season cannot be inferred from eventual participation. Missing genuine pregame receipts block a valid prospective probability-calibration claim.

The frozen diagnostic plan and its actual-time receipt are in `research/king-court/distribution-v2/`. The current source hashes and prior receipts are preserved. New diagnostic/repair code lives outside `scripts/king_court/`, keeping its existing code-hash contract and popularity/prize functions intact.
