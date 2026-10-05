# GOING Picks: football first

Permanent product north star: **select game â†’ see GOING picks â†’ understand why â†’ see opportunity/injury/matchup â†’ concern â†’ market â†’ optional deep research**. Sophisticated underneath, simple to use. Approved `docs/design-reference/` remains the visual source of truth.

## Product decision

Going Yard starts with ranked hitters, a readable rating and explanatory badges; details follow the recommendation. Going Long had competing probability, Score, readiness and price workflows before the user could find a bet. The reset follows Yard's disclosure philosophy, not its baseball methods.

PRODUCT proposed reusing GOING Score. MODEL RESEARCH rejected that: a player index cannot rate an exact Under or changing line. A separate direction-aware football-case rating won. FOOTBALL DATA rejected inferred routes, inferred absences and automatic injury-transfer bonuses. MODEL RESEARCH rejected positive Any-TD probability as directional proof, overlapping model/production as independent confirmation, and prioritizing game lines merely because they are easier to populate. These objections shape the implementation.

Today opens GOING Picks for the nearest upcoming game. Select another game directly, optionally select a market family. Six cards initially, **Show more without a permanent cap**. Each shows the bet, 1â€“5 rating, evidence badges, why, main concern, observed book price/time and View research. Confidence's Current Support/Developing/Check First remain available as diagnostics in collapsed advanced research; they are no longer the primary discovery experience. No model or non-betting tool is replaced.

## Current display and capture policy: football-case-v2

GOING rating is shown as **72/100**, never 72%. It ranks the exact football thesis, not a player index, win chance, probability confidence, calibrated edge or expected return. It does not reuse GOING Score metrics. This is a deliberately simple, unfitted research policy requested by Travis; numerical granularity is not measurement precision.

The original signed evidence components, interesting-case rule, integrity exclusions, badges, concerns, market-specific inputs and overlapping-evidence caps below remain intact. First compute the original evidence tier (1–5). Its 20-point band is 1–20, 21–40, 41–60, 61–80 or 81–100. Then refine **only inside that band**:

`rating = 20 × (tier − 1) + 1 + round(19 × strength)`

`strength = clamp(directional projection gap / existing model standard deviation, 0, 1)`

For yardage, receptions and TD-count props the gap is signed `(projection − line)`. Spread uses signed `(home-margin mean + home spread)`, total signed `(total mean − total line)`, moneyline signed home-margin mean. Over/Home is positive, Under/Away negative. Use the exact existing prop SD or game-margin/total SD in the same units. A full favorable model SD saturates the refinement; larger gaps cannot leap an evidence band. This is a bounded unit-free contrast, **not** a normal-CDF win probability, favorite ranking or new forecast. The one-SD saturation and 20-point bands are declared policy assumptions, not fitted thresholds.

A bigger favorable gap separates otherwise tied theses; a wider model spread lowers that refinement. Missing/nonpositive/nonfinite SD adds no refinement, remains unknown and never rejects the football thesis. An opposing model adds no refinement; its existing negative evidence component still applies. Unknown matchup/role/price stays unknown. No invented independent confirmation: model plus current production remains capped at 60/100; a model-only case at 40/100. Any TD stays separate role research, without a comparable directional model gap or yardage refinement. Rating 100 does not mean certainty.

Ordering is rating, signed evidence points, kickoff, stable exact-contract ties. Primary-line selection, direction selection and price handling are unchanged. For example, two previously 3/5 cases with +2 and +12 directional projection gaps and SD 20 become 43/100 and 52/100. The numeric difference has a reproducible cause; it is not two different claims of win probability. Independent opportunity/matchup/injury evidence is still needed to enter a higher band. Within-band ordering remains unvalidated and may favor misestimated/narrow SDs; future validation must test that assumption.

Future captures use **going_picks_v2 / going-picks-v2**, freezing the rating, original tier, refinement inputs/method, rank, exact contract and policy/input fingerprints before kickoff. V1 /5 predictions, research receipts, ranks and outcomes are preserved byte-for-byte; the tracker exposes both cohorts and renders each original scale. Never convert old ratings, combine policy cohorts into one bankroll or backfill v2 recommendations. Only genuine matched priced predictions enter the existing $100 results/ROI; unpriced research remains separate. The initial prospective question is whether within-tier higher directional-gap ratings separate future outcomes on identical market families and game-cluster samples. No outcomes were used to select this recipe; predeclare exact cutoffs, splits and criteria before fitting or comparing performance, and preserve every existing holdout/release gate.

## Frozen initial recipe: football-case-v1

This is a heuristic ordering of the football thesis, **not probability, confidence, profitability or +EV**. Its weights and trend thresholds are professional policy assumptions, not fitted or empirically validated. Unknown contributes zero, disagreement subtracts. Existing model forecasts and GOING Score are unchanged.

| Component | Exact rule | Points |
| --- | --- | --- |
| Model direction | Existing projection versus the exact line; spread uses home-margin mean plus home spread, total uses projected total minus total, moneyline uses home-margin direction | +2 agreement / âˆ’2 disagreement |
| Current production | Exact player/team/current-season observed mean versus line; game markets use both teams' published current finals | +1 / âˆ’1 |
| Usage trend | Targets for receiving, carries for rushing. Two chronological groups, at least two observed games each; absolute change â‰¥1/game AND relative change â‰¥20%; signed for Over/Under | +1 / âˆ’1 |
| Matchup | Exact player/opponent/market-role/game/current-season active published residual with lineage and fresh source; sign respects Over/Under | +1 / âˆ’1 |
| With/without | Exact current-game weekly OUT confirmation; â‰¥2 with and â‰¥2 without; market-specific targets/carries change â‰¥1/game and â‰¥20%; source fresh and identity matched | +1 / âˆ’1 |
| Availability uncertainty | Existing questionable/limited/practice-DNP or stale injury treatment | âˆ’1 |

Interesting means the signed total is positive. Rating is the total clamped to 1â€“5. **Model plus production alone is capped at 3/5**, because they overlap. A model-only thesis can appear at 2/5 with missing evidence disclosed. Counterevidence can leave a lower-ranked, still interesting case; agreement in every dimension is not required. Hard integrity/status exclusions remain: valid supported pregame contract, appropriate sport/market, existing model nâ‰¥5, current history â‰¤24h, exact player/team identity, recent player history â‰¤28d, no manual/DFS row and no known unavailable player. Reserve/inactive/PUP/IR/suspended statuses block Picks. No fake picks are inserted into empty games.

One primary line per player/market/game is chosen closest to standard âˆ’110 decimal pricing **before rating**; the stronger direction is selected at that line. Opposite sides/alternate lines/books and one-minute vendor kickoff drift do not multiply the board. Actual contracts retain their original identifiers. Same-line offers prefer usable timestamp, newest quote, then payout and stable book ties. Ranking uses rating, signed points, kickoff, stable contract tiesâ€”never probability, sportsbook favorite or GOING Score. This standard-line heuristic is unvalidated; all original markets remain available.

### Market families and badges

| Family | Current evidence used | Limits |
| --- | --- | --- |
| Receiving yards / receptions | Existing model, current production, targets/target share, chronological targets, exact receiving residual, receiving opportunity with/without | Offensive snaps are not routes; no invented alignment/first-read data |
| Rushing yards | Existing model, current production, carries/rush share, chronological carries, exact rushing residual, carries with/without | No invented blocking/front or expected rushing-yard model |
| Passing yards / TDs | Existing model, current production, verified-start pass attempts | No manufactured pressure/coverage/OL adjustment |
| Rush/receiving TD counts | Existing model and exact current TD production | Rare events remain uncertain; no transferred yardage interpretation |
| Any TD | Current observed offensive TD participation; capped 2/5 **TD role research**, below primary Picks | Positive probability alone earns no model points |
| NFL / NCAA game lines | Existing team model, both teams' current published finals; NFL measured team environment in deeper research | Descriptive raw scoring overlaps the model; NCAA never requires NFL player-role data |

First TD and 2+ Any-TD remain in their existing specialized tools, outside primary v1 Picks; their methods are unchanged.

Badge triggers: **MODEL +** positive exact-direction model component; **VOLUME** available positive current targets/carries/verified-start pass attempts (descriptive, no extra points); **ROLE UP/DOWN** the declared chronological count-change rule; **MATCHUP +/âˆ’** exact active direction-matched residual; **WITH/WITHOUT** the declared exact-game cohort rule; **STATUS WATCH** existing nonblocking injury treatment; **ROLE SCENARIO** existing injury redistribution scenario, never an observed causal boost; **TD ROLE** observed current rushing/receiving TD participation. No decorative badges or opaque aggregate score.

## Opportunity, injury and expected versus actual

Additive public NFLverse evidence joins schedule, GSIS/PFR roster identities, positive offensive snaps, complete final-game PBP and exact weekly injury reports. A game needs final scores and a game-end PBP marker. Positive snaps establish participation; an omitted row is unknown. Zero targets/carries requires that verified participation and complete PBP. The sparse original usage log remains a fallback without fabricated zeroes. Published current-season scopes/projections are preserved.

Teammate cohorts include cross-position redistribution, not just the obvious backup. WITH requires observed offensive snaps. WITHOUT requires explicit weekly OUT and no contradictory offensive snaps; missing reports never establish an absence. Two observations per condition is the descriptive minimum, not reliable causal evidence. Current-game OUT must match the schedule week before adding injury points. Historical associations stay visible even when the next week's status is unknown.

The actual 2026 public injury schema lacks `date_modified`, despite its documentation listing that field. Undated weekly reports support **retrospective descriptive cohorts only**, never proof of what was known before historical kickoff. Future Picks freezes record the actual published snapshot, retrieval time and fingerprints. No instant inactive feed or injury-change push service is claimed. Existing data workflow refreshes at **10:20/22:20 UTC** and after eligible script/config pushes; Codex's eight development slots are not eight guaranteed injury refreshes. Reopening/refetching the app reconsiders loaded evidence, not an unseen new report.

Expected versus actual uses existing **CP-summed expected catches versus actual catches on modeled targets**. This describes catch opportunity; it does not invent expected yards, expected TDs, a bounceback forecast or causal luck. No extra rating points are awarded. Targets/carries and snap shares are shown separately from production. Four-game count trends may reflect game script/opponents; they do not prove increased route share or an injury cause.

Data trust order: exact identity and current confirmed availability; measured participation/current opportunity; traceable market-specific model and current production; adequately matched current matchup; small descriptive splits/scenarios. Strong source quality does not make a tiny sample strong evidence.

## Price

Football case is primary. Matched book odds and quote time are context. Five-minute freshness remains a price label, not a football veto. Missing, future-dated, corrupt or stale quotes never become fresh. Comparison/parlay saving requires valid matched price and timestamp within 24h; stale prices are visibly marked for checking. Dramatic line changes create a different exact contract; no recommendation at one line guarantees another. No demonstrated sportsbook-pricing edge is claimed.

## Prospective learning

The existing collector freezes a separate `going_picks_v1` board / `going-picks-v1` cohort. Capture-time rating, points, badges, component explanations, opportunity/injury/matchup/expected-catch facts, unknowns, why, concern, exact game/player/market/side/line/price, actual capture timestamp, candidate/policy/input fingerprints and original model output are retained. Old records are never relabeled.

Every interesting primary thesis gets an append-only `pick_research` receipt, even without usable pricing. Official full-game results append separate research outcomes. Only valid priced contracts become predictions in the existing **$100 stake** results graph and ROI calculation. Missing prices never create wagers or ROI. Repeated snapshots retain the first prediction/receipt. Same-game markets are correlated; boards/cohorts can overlap and are not additive bankrolls.

Predeclared question: within identical market families and available priced contracts, do higher initial ratings and declared usage/matchup/with-without badges improve future outcomes over model-only cases? Collect prospectively from first v1 publication. Review four full future football weeks for source integrity and descriptive coverage; then reserve the next four full weeks untouched for any fitted challenger. Before fitting, register an exact data cutoff, chronological folds, release date, eligible paired sample, benchmarks and acceptance criteria in a separate experiment. Do not tune this recipe from wins, inspect an unregistered holdout, or claim validation from early returns. Evaluate â‰¥50 distinct game clusters per comparison/family or mark insufficient; game-cluster uncertainty, Brier/log loss/calibration for probabilities, MAE/RMSE for projections, and ROI only from actual saved prices/results. Rating itself is not a probability and cannot receive a Brier score. New policies need new versions; production model promotion still requires Travis approval. Existing Champion/C1/C2 and all frozen research gates remain untouched.

## Current gaps / next priorities

No current measured routes, first-read share, receiver alignment, reliable pressure/OL effects, fresh current participation charting, expected yard/TD model or causal with/without estimates. Existing PBP contains red-zone/goal-line detail, but v1 does not award an unvalidated new scoring-role bonus. First improve exact-game injury freshness and opportunity coverage; then independently preregister relevant market-family improvements. Do not collect another dataset without naming the betting question it resolves.

## Failed refresh investigation

[Run 37336119083](https://github.com/daboli69/going-long/actions/runs/37336119083) failed because the existing NFL props provider returned HTTP503 `PROPS_TEMPORARILY_BUSY` after its bounded retry. Previous props were retained as FALLBACK; successful snapshots were committed, then the source-failure summary correctly failed the run. This was a provider outage, not proof that every snapshot failed. Existing credentialed ParlayAPI steps ran; Travis previously confirmed their allowance incurs $0 additional. No new provider, local credentialed call, paid activation, workflow bypass or retry deployment was introduced. Dollar billing cannot be independently established from run logs.
