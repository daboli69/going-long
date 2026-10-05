# GOING Confidence: current football support

GOING Confidence answers **what GOING finds interesting today, why, and what needs caution**. `football-readiness-v2` is a descriptive evidence classifier, not a calibrated probability, proven edge, model promotion, or replacement for Today/GOING Score. Real contracts and existing model outputs stay unchanged.

## Definitions and safeguards

- **Current support:** the existing eligible model and traceable current football observations support the exact contract direction, with no blocking integrity or availability check. This means enough evidence to surface for research, not a guaranteed winner or demonstrated profitability.
- **Developing:** the existing eligible estimate is interesting to investigate, but relevant current opportunity, directional agreement, matchup, completed team scores or availability remains weaker/incomplete. Cards identify the concern; no stronger grade is fabricated.
- **Check first:** an unresolved model flag, missing/current-season model coverage, stale/future/missing model/player data, blocked/stale player status, or unsupported market prevents trusting the football assessment. Cards expose structured reasons and allow filtering them.

Existing eligibility remains NFL/NCAA, model-backed pregame game/prop contract, finite win/push probabilities and at least five recorded model games; NCAA has game markets only. Model freshness remains 24 hours; exact player observation remains 28 days; future dates fail. These are operational screening policies, not empirically validated accuracy thresholds. Current-season coverage and actual observation counts remain visible. A `low` sample-quality flag is disclosed rather than made an absolute veto: a descriptive current observation can be useful without justifying a High-confidence label. No calibrated High/Medium label is introduced.

## Market-specific evidence

| Family | Current evidence consumed | Direction check |
| --- | --- | --- |
| Receiving yards/receptions | Exact-player current appearances, positive observed targets and current-only market average; verified current pass-snap signal can also support Over | Current average and existing projection support the recorded Over/Under, or exact verified role/defense signal plus model direction |
| Rushing yards | Current carries and rushing-yard average | Current average and existing projection agree with the recorded direction; exact active rushing defensive signal is an alternative |
| Passing yards/passing TDs | Current QB **verified starts**, positive attempts, current-only yards/TD average | Current average and existing projection agree with direction; relief appearances are excluded |
| Rushing/receiving TD totals | Positive current offensive opportunity, exact TD-count observations | Current TD-count mean and existing projection agree with the line/direction |
| Anytime TD Yes | Current offensive opportunity plus at least one observed rushing/receiving TD appearance and an existing valid TD estimate | Descriptive TD involvement; rare-event probability is not required to exceed 50%. No goal-line/end-zone evidence is invented |
| NFL/NCAA spread/total/moneyline | Both teams' published completed current-season finals, scored/allowed averages, current model coverage | Symmetric scoring context and existing model support the recorded direction. This context is not a new forecast or verified personnel/defense matchup |
| First TD and other unsupported props | Separate market-specific evidence definition required | Check market coverage; other-market history is not silently reused |

Player evidence comes from published `history.json` exact profile ID/current roster team and current-season dated appearance rows; null statistics stay missing. January belongs to the preceding football season. Current roster identity does not establish historical team continuity after trades; coaching, routes and goal-line role are not inferred. The weighted historical model mean is never called a current-only average.

Completed team finals come from **`results.json`**, not the upcoming-only `history.betting.games` list. Only completed published full-game records with both nonnegative integer scores enter the adapter, with a results snapshot no older than 24 hours and the exact league source marked loaded/checked within 24 hours. A new file timestamp never makes retained results from a failed source fresh. Missing/stale/future league checks remain Developing with an explicit concern. For home H and away A, descriptive context is h=(H scored+A allowed)/2, a=(A scored+H allowed)/2; total=h+a, home margin=h-a. This is a transparent comparison of existing outcomes, not a fitted model, opponent-strength adjustment or an independent confirmation. Spread comparison uses the recorded home-perspective line. NCAA never requires NFL player-role evidence.

Defensive signals must match exact player, opponent, receiving/rushing role, kickoff within 60 seconds, weakness ID, current season, active status and lineage. Fresh file generation does not make historical charting current. Inactive/uncertain signals stay limitations.

## Football versus price

Price never creates or vetoes football support. Valid matching price/book/timestamp, five-minute quote freshness, win-only break-even and non-positive estimated return are shown separately. Missing/stale/future quotes say **Check price** even on Current Support cards. The five-minute rule remains required for claims of recent observed pricing and existing Best Value qualification; it was not loosened. Compare/parlay saving still needs a valid matched pregame quote no older than 24 hours. Push-aware model return remains pWin*decimalOdds+pPush-1, not proven value. High likelihood, short odds and payout alone never establish football support.

## Ordering, mobile and accountability

Within each view: more current observed games, then newer current evidence, then earlier kickoff; stable existing input ties. This transparent descriptive order is not a validated universal ranking or GOING Score sort. Existing date/game/book/search filters and complete pagination remain. Optional **Recent prices only** filters displayed cards to the existing valid matched quote/five-minute test; it defaults off and keeps separate NFL/NCAA state. Football group counts/classifications stay unchanged. The filtered count and empty state explicitly distinguish quote freshness from betting value; switching it off restores all evidence. Cards show contract, support reason, biggest concern, likelihood and price; details hold source facts and methodology. Check first filters only football blockers. Empty states point to the outstanding evidence and relevant views. The approved `docs/design-reference/` UI system remains authoritative.

Future public-tracker records may freeze a versioned capture-time readiness receipt, exact reasons/facts, assessor fingerprint and input fingerprints. Old records remain unchanged and explicitly lack saved readiness; no retrospective confidence reconstruction or relabeling. These receipts enable future chronological evaluation, not a claim of present accuracy.

## Validation limits and future work

Availability coverage, current routes/goal-line charting, verified active defensive signals and small current samples remain incomplete. Observations and the model share inputs, so they are not independent trials. No empirical validation establishes the zero-sign directional checks or sample/freshness rules as predictive thresholds. Predeclare future evaluations, use decision-time receipts, chronological validation and an untouched holdout, paired calibration/Brier/log loss and game-cluster uncertainty. Genuine matched prices and settlements are necessary for ROI/CLV. Do not tune labels after outcomes or promote Champion/C1/C2/ABBEYS/Score/2+TD/DFS.

Existing NCAA recency research in `research/ncaa-recency/` remains blocked on historical as-of inputs. Its frozen protocol, current 80/20 Champion weighting and untouched future holdout remain unchanged. Today-ranking-v1 definitions, hashes, journal records and release gates are unchanged; Confidence is not a new policy in that experiment.
