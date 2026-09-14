# GOING — product, architecture and trust audit

Audit date: September 14, 2026. This is an assessment and proposed roadmap, not an implementation release.

## Scope and evidence

The master realignment brief is the governing request. Application code, models, workflows, deployment configuration, public live data, and the live football interface were inspected. No model, application, database, scanner or deployment configuration was changed for this audit. No notification smoke test was sent.

Repository references below are relative to these audited checkouts:

- **Long:** `work/going-long`, repository `daboli69/going-long`, commit `3ffbe5af6997b0eb934471fc8e5780aee0b57cb1`.
- **Yard:** `work/going-yard`, repository `daboli69/hr-board`, commit `daf92ca575fd7248720b0026bfe6361c777217b1`.

The deployed Long feature release was confirmed successful. Generated public data can be newer than these checkouts; live and local observations are distinguished below. This was not an authenticated production database/security audit, an account billing audit, a full mobile device test, or an independently reproduced profitability study. Repository instructions, including Long's `CLAUDE.md` read-only audit boundaries, were reviewed.

## A. Executive assessment

GOING already contains useful research infrastructure: real odds, historical distributions, public football participation/context features, a substantial baseball modeling pipeline, configurable parlays, a shared brand/navigation layer, and several outcome journals. It is much more than a mockup.

It is not yet one coherent recommendation product. The raw boards, Best Plays, Signals, First TD predictor, promo builder, parlay builder, scanner and baseball tools use overlapping but different eligibility, probability, ranking and recording paths. This allows one surface to show an attractive-looking bet that another surface deliberately excludes. It also means that a displayed recommendation is not guaranteed to become a reproducible, graded record.

The highest-priority issue is trust consistency. In the live football interface, the audit observed Troy Franklin anytime touchdown at +1400 with a displayed 34.1% chance, +411.1% estimated return and 2% stake, and J.K. Dobbins over 47.5 rushing yards at a displayed 96.6% chance. These are observations of application output, not endorsed forecasts or verified betting opportunities. Their size demands a common model/price disagreement review state. A small historical-model footer does not adequately distinguish them from a vetted recommendation.

The strongest product direction is the brief's research assistant: show the entire qualified slate, explain the reasons and weaknesses, compare prices, and let the user investigate. Keep sharp-book comparison as a price-quality layer. Do not make an internal alert scanner's operational gates the definition of all useful research.

**Recommendation:** fix shared eligibility, record completeness and grading first; then simplify the experience around the resulting common pool. Preserve the existing football, baseball, draft, trade and hosting components. A wholesale framework rewrite would not address the principal risks.

## B. Current architecture

```text
Public football data                 Baseball data
nflreadpy / sportsdataverse           Statcast / MLB Stats API / other adapters
             |                                      |
Python histories + context           Yard ETL: contact, props, runs, context
             |                                      |
Long data/*.json                     Yard docs/*.json + frozen pregame records
             |                                      |
             +---------- Vercel snapshots -----------+
                                |
Parlay API -> server/parlay.mjs -> api/odds -> browser models/rankers
                                |
              hub / football / baseball / validation

PC scanner -> separate top-down model -> SQLite -> Supabase -> Results
     |                                          ^
     +-> Discord                 board collector + settlement scripts

Browser Signals local ledger and Yard result files are additional paths.
```

| Area | Implemented components | Architectural implication |
|---|---|---|
| Hosting | Long `scripts/build_vercel.mjs`, `vercel.json` | One Vercel deployment assembles the hub, `/long/`, `/yard/` and `/validation/`. |
| Football application | Long `index.html` | Large Vanilla JS application also contains draft and trade functionality. It is not a Next.js app. |
| Results | Long `apps/validation/src.jsx`, `metrics.mjs`, `load-journal.mjs` | Separate React application consuming the journal. |
| Branding | Long `hub/index.html`, `shared/going-shell.js`, `shared/going-shell.css` | Shared identity exists; internal navigation and interaction models still differ. |
| Baseball application | Yard `docs/index.html`, `docs/going-platform.js`; Long `apps/yard/` mirror | Two repositories plus a copied frontend create release/drift risk. |
| Public APIs | Long `api/odds`, snapshot, yard-snapshot, validation-config, promo-availability routes | Odds/config/data delivery, not a central recommendation service. |
| Football histories | `scripts/build_pipeline.py`, `pbp_features.py`, `football_context.py` | Statistical profiles, game baselines and descriptive context are partly separate products. |
| Market engine | `scripts/topdown/model.py`, `secondary.py`, `scan_markets.py` | Sharp-reference pricing and operational gates are separate from browser projection math. |
| Tracking | `collect_model_plays.cjs`, `topdown/tracking.py`, `journal.py`, `settle_markets.py` | Automated collection exists, but coverage does not include every displayed market or new builder. |
| Alternate infrastructure | `server/worker.mjs`, older Yard templates/scripts | Possible legacy paths; usage must be established before removing them. |

The board collector executes the existing football page in jsdom. Reusing the board's calculation avoids maintaining another approximate implementation, but couples unattended recording to UI structure, page initialization and network behavior.

## C. Vision alignment matrix

| Major requirement | Classification | Repository evidence / gap |
|---|---|---|
| One GOING identity and domain | PARTIALLY EXISTS | Shared shell and assembled routes exist; sport-specific navigation remains inconsistent. |
| Recreational bettor's research workflow | EXISTS BUT SHOULD CHANGE | Numerous technical tabs and raw quote rows precede discovery and explanation. |
| No per-user live LLM dependency | ALREADY EXISTS | Inspected runtime routes and recommendation code are deterministic; no consumer inference path found. |
| Central computation and cached consumption | PARTIALLY EXISTS | Static ETL and cached APIs exist; browser calculations and duplicate fetchers remain. |
| Entire qualifying opportunity pool | EXISTS BUT SHOULD CHANGE | Intermediate candidates exist; Best Plays/First TD/Yard curated functions truncate without complete exploration. |
| Separate eligibility, ranking and presentation | PARTIALLY EXISTS | Some helper separation, but selection and display caps are mixed. |
| Probability separate from confidence/value | EXISTS BUT SHOULD CHANGE | Probabilities and returns are shown; data quality and calibration uncertainty are not a consistent separate dimension. |
| High-probability, fair-price parlay candidates | PARTIALLY EXISTS | Builders allow several ranking/use cases; shared price-quality definitions are missing. |
| Role before results, NFL | PARTIALLY EXISTS | Public pass-snap proxy, target share, catch shortfall and context exist; 2026 participation feed currently unavailable. |
| Process before results, MLB | ALREADY EXISTS | Contact quality, expected-versus-actual, pitch mix, park and pitcher context are implemented. Their edge is not thereby proven. |
| Coaching/coverage/defensive context | PARTIALLY EXISTS | Team tendencies and curated coaches exist; current slot charting and learned OC identity do not. |
| Player-informed NFL/NCAA game models | DOES NOT EXIST in the primary baseline | `build_game_models` uses team points scored/allowed; richer player context is not integrated. |
| Player-informed MLB game model | ALREADY EXISTS | `etl/runs.py` incorporates lineup, starter, bullpen and environment. Calibration still needs stronger validation. |
| NCAA game-only betting with player research | PARTIALLY EXISTS | Game-only betting is supported; player-to-game contribution is missing. |
| Expandable evidence for every claim/risk | PARTIALLY EXISTS | Context details and model metadata exist; no uniform immutable claim-to-source lineage. |
| Contrary evidence and market already pricing a signal | PARTIALLY EXISTS | Some gates/warnings and book comparisons; no consistent counterargument record. |
| Three levels: discovery, why, full research | EXISTS BUT SHOULD CHANGE | Many useful pieces, fragmented across screens rather than one progression. |
| Full filters, AND chips, saved research | PARTIALLY EXISTS | Search, games, periods and some local signal filters/favorites exist; not one cross-surface contract. |
| Configurable Parlay Lab and boosts | PARTIALLY EXISTS | Legs/odds/books/games/boosts exist; accepted SGP pricing and dependency engine do not. |
| Weakest leg and replacements | PARTIALLY EXISTS | Weakest marginal leg appears; robust comparable replacements and joint-risk handling are incomplete. |
| Every recommendation automatically graded | DOES NOT EXIST | New First TD/parlay surfaces and several market types lack the full recording/settlement path. |
| Graphical cumulative results | DOES NOT EXIST in the reviewed validation UI | Cards/tables and summaries exist; unified cumulative units/profit chart does not. |
| Actual versus hypothetical performance | ALREADY EXISTS in journal UI | Labels distinguish estimated flat-stake records; cross-system completeness is still limited. |
| Earned validation labels | PARTIALLY EXISTS | Research warnings and sample checks exist; some probability paths overstate calibration status. |
| Time-aware learning and safe model promotion | PARTIALLY EXISTS | Replay and feedback exist; strict source-time guarantees and promotion tests are incomplete. |
| Shared account-wide odds budget | DOES NOT EXIST | Local scanner counter is not a shared budget across browser, CI and all collectors. |
| Subscription readiness | DOES NOT EXIST as a finished system | Billing, entitlements and commercial operating controls are not established in inspected code. |
| Commercial data rights and live cost/headroom | CANNOT YET DETERMINE | Requires provider terms/account-level evidence; public availability alone is insufficient. |

## D. Edge assessment

“Implemented” means the code computes the feature. It does not mean the feature improves betting returns.

| Sport/layer | Demonstrated behavior | Plausible mechanism | Validation still needed |
|---|---|---|---|
| NFL market comparison | Matches comparable contracts, removes bookmaker margin, applies freshness and reference checks. | A better price on the same outcome can improve returns. | Whether these designated books lead each specific market, executable prices, true closing comparisons and out-of-time returns. |
| NFL role/opportunity | Pass-snap proxy, targets, air yards, red-zone usage and team pace are exported. | More participation creates more opportunities; usage can precede production. | Role stability, current-source coverage and incremental improvement beyond the line. |
| NFL pressure/coverage | Conditional pressure rates and historical coverage splits exist; some adjustments remain inactive. | Pressure can change passing efficiency and rushing/check-down opportunities. | Effect size, confounding, current charting and calibration. |
| NFL first scorer/periods | Competing-hazard First TD and scaled period distributions exist. | Goal-line/opening usage and early pace are relevant. | Full outcome calibration; current constants are assumptions, not measured advantage. |
| NCAA | Team scoring baselines and live price comparison. | Team strength and price disagreement contain information. | Opponent/roster adjustment, schedule strength and usable historical prices. |
| MLB | Contact quality, pitch mix, expected contact results, starter/bullpen/park/context models. | Contact and opportunity describe process more directly than yesterday's home run count. | Independent replay, proper probability calibration and improvement after market price is included. |

The local Yard backtest artifact contains 135 days and 36,139 observations. Its raw Heat/100 calibration diagnostic reports a worse probability error than a constant baseline (approximately 0.1754 versus 0.0964). This does **not** establish that every Yard HR probability model fails; it establishes that raw Heat cannot be treated as an event probability. The runs artifact shows only a small probability-error improvement, about 0.2474 versus 0.2495 over 1,811 games, with replay limitations described below. Neither result proves profitable bets.

No demonstrated profitable edge across NFL, NCAA or MLB can responsibly be asserted from this audit. There are useful mechanisms and substantial measurement infrastructure to build on.

## E. Going Long UX audit

The live page starts on Player Props, offering eight competing tabs: TD Promo, Best Plays, First TD Predictor, Parlays, Player Props, Game Lines, Projections and Signals. Sport selectors, period selectors, market chips, several sorts, bookmaker and game menus, and a second legacy navigation bar add further choices.

Useful work already exists: team badges, current-week filtering, matchup controls, compact bookmaker comparisons, pagination, historical details and explicit unavailable-category notices. The problem is the hierarchy. A new user must understand the tools before discovering what GOING actually likes.

Observed quote rows also repeat the same player across books. That is appropriate inside a comparison drawer, but weak as the default discovery experience. The live page showed 923 quotes with 50 on the first page; quote count is not distinct opportunity count.

Recommended hierarchy: **Today's research → All opportunities → Games → Parlay Lab → Results**, with football research subcategories/filtering rather than eight equal destinations. First TD should be a market specialization; promo tools belong within Parlay Lab. Draft and trade remain available through a clear Betting/Fantasy mode.

A discovery card should identify the exact bet, best usable price, estimated chance, price assessment, strongest reason, main risk and data age. Expand it for evidence and comparisons; expand again for full research. A model-quality review flag must follow the bet onto every screen.

The current copy still includes notation such as `E[TD]`, “lognormal,” “Poisson,” and bare percentage stake suggestions. Put technical methodology in research details and explain the primary number in ordinary language. Full 375–430px, keyboard and screen-reader acceptance testing belongs in the implementation phase; this audit does not certify those checks.

## F. Recommendation-pool audit

Long's `signalCandidates` generates game and prop candidates from supported quotes and historical profiles. It evaluates both over and under where available and reduces identical contracts to their best payout. That is a useful starting point.

`rankBestPlays` then applies different freshness and model checks, deduplicates at a coarser event/player/market level, and selects a limited result. Its key omits line and side, so alternatives can disappear before presentation. Best Plays selects six, or a three-game/three-prop blend. This is not merely paginating a stored full qualifying list.

Other limits: First TD predictor takes eight players per game; Yard's Model Above Market view takes 60; one fantasy research view takes 80. Signals has a Show More path and the raw props board has pagination, so the problem is not universal—those particular curated selections lack access to the remainder.

Global and category rules are mixed. The scanner uses reference-book and minimum-return gates. Best Value uses fresh reference pricing. Historical research accepts older quotes and prior-season profiles under separate conditions. Raw props still display extreme model disagreement with a suggested stake. These are different products presented under one identity.

Alternate lines are not represented by a comprehensive shared identity throughout the stack. The server's 10,000-row props cap and derivative-only fallback also mean ingestion completeness is not guaranteed. First establish which contracts arrived, which are unsupported, which qualify, and which were excluded—and retain the reason.

Target design: retain every supported evaluated contract using sport/event/player/market/period/side/line/rules identifiers. Keep quote variants underneath it. Store eligibility and exclusion reasons separately from category memberships and ranks. Curated cards can show a small first page, but must link to “View all qualifying plays” with accurate counts and stable pagination. Research without a usable price can remain visible as research; it is not a priced recommendation.

## G. Data and explainability audit

Live checks establish that data is not simply absent:

- Public football context returned HTTP 200, generated September 14 at 16:25 UTC. Its source report includes 2,596 2026 play-by-play rows, 1,397 snap rows and 2,963 roster rows. The 2026 participation source reports unavailable/ValueError.
- Live Yard board returned HTTP 200, generated September 14 at 15:26 Eastern, with 10 games and 242 players.
- Live Yard pregame results returned HTTP 200 with 15 graded games. The local Yard result artifact was older; calling the production tracker empty based on that file would be incorrect.
- Local Long historical data was about 9.3 MB, generated September 13, and includes some 2026 player games. Coverage is uneven; “no current-season data” is no longer a universally accurate statement.
- The local Savant context reports failed Savant API/CSV attempts and an nflreadpy fallback. A URL returning HTTP 200 alone is not evidence of a valid current CSV.

The public nflverse loaders document participation as a separate dataset; availability must be checked independently of weekly box scores. The application should preserve that distinction rather than label pass snaps as routes. [nflreadpy loaders](https://nflreadpy.nflverse.com/api/load_functions/), [participation loader](https://nflreadr.nflverse.com/reference/load_participation.html).

Explanations are partly traceable through context payloads, historical samples and source metadata. They are not consistently frozen alongside the exact prediction. `topdown/tracking.py` uses the broad version `board-tracking-1`; feature/model changes can therefore share a label. Some descriptive flags are attached after the probability calculation. They should say “supporting context,” not imply they caused the forecast.

Required evidence record: source and availability time; event/entity IDs; observed statistic and denominator; window; comparison baseline; feature version; direction and size of any actual model adjustment; uncertainty/missingness; contradictory evidence; model/policy version; exact quote and time. Explanations should be rendered from this structure without a live LLM. Store a snapshot/hash so a future researcher can reproduce what the user saw.

## H. Self-learning audit

Implemented updating is a combination of fresh data and limited feedback—not a general continuously improving model.

1. Football player profiles use the latest 12 games with a five-game minimum. New games replace older games; there is not a learned season-to-current-form weighting schedule in that primary path.
2. PBP/context features are rebuilt. Updating a statistic is not learning whether the statistic predicts future outcomes.
3. The scanner's secondary baseline uses 40/60 season/recent-form weighting and stronger early-season priors. It is distinct from the primary browser distributions.
4. Scanner feedback applies a conservative one-sided probability penalty after at least 50 settled bets and 20 games. It measures past overprediction, with shrinkage and a cap. It does not learn which feature caused the error, and it uses a selected actionable sample.
5. Yard loads empirical score-band HR rates and multiplies some probabilities by trend, mix, historical badge and context factors. Those additional factors are not automatically calibrated merely because the starting score-band rate was measured.
6. Offline replay/backtest scripts exist. There is no complete automatic challenger evaluation, approval and rollback system for model updates.

Temporal weaknesses matter. Football `build_game_models` prevents same-kickoff leakage but adds a game's completed result before the next kickoff bucket; on overlapping kickoff times this can put a not-yet-finished game's residual into the next prediction's uncertainty estimate. The separate NFL context backtest has a stronger kickoff-plus-12-hours guard.

Yard `etl/backtest.py` includes date guards, but also loads a season FanGraphs aggregate outside the per-day replay and uses the day's actual participating batters/first pitcher. These inputs require historical availability timestamps or explicit diagnostic-only labeling. A historical replay that knows who ultimately played is not automatically a clean pregame test.

Recommended learning: freeze forecasts; score future outcomes; compare with both simple and market baselines; evaluate by sport/market/odds band; group uncertainty by game/day; test changes on held-out future blocks; promote only with documented evidence. A losing bet is not itself proof that its supporting signal was wrong.

## I. Game-model audit

**NFL and NCAA:** `scripts/build_pipeline.py:157`, `build_game_models`, averages each team's recent scoring with the opponent's recent points allowed. It estimates margin and total variation from historical prediction errors. It does not incorporate player availability, offensive line changes, role shares, receiver/coverage fit, play-caller changes or player contribution into this main game baseline. Those features elsewhere in the product should not be presented as inputs to this game forecast.

**NFL derivatives:** scaled period distributions and pace factors exist. They are useful explicit starting assumptions, not independently validated period models. Discrete counts use Poisson, with dispersion exported but not used to select a more flexible family. Rushing and receiving tails, role changes and zero opportunities need dedicated evaluation.

**MLB:** `etl/runs.py` already uses lineup hitter quality, opposing starter, bullpen, park/environment and a bullpen fatigue adjustment. Its module commentary is less current than its implementation, so “bullpen availability is entirely missing” would be inaccurate. It uses several fixed priors, clamps and weights; these should be measured rather than replaced reflexively. The Markov variant is not automatically better: the reviewed artifact's total error is worse than the simpler variant.

Recommended order: preserve and benchmark current baselines; add a hierarchical team/opponent model; then add available player contributions with uncertainty and missing-data fallback. Evaluate each addition against the actual market. Adding more features without an out-of-time gain is not progress.

## J. Parlay audit

Long's `shared/football-parlays.js` supports 2–6 legs, desired odds, books, selected games, market kinds and profit boosts. Different-game combinations multiply individual probabilities under an independence assumption. Same-game mode avoids displaying an invented joint probability or accepted combined price; this restraint should remain.

However, same-game selection is still a heuristic, not a fitted dependency model. Duplicate-player and some overlapping-side rules are not a complete compatibility system. It needs explicit mutual-exclusion checks, settlement-rule matching and a joint distribution or a clearly unpriced research designation.

Search is bounded: limited options per event and retained combinations per depth mean not every feasible parlay is searched. This is acceptable computationally if disclosed; it must not silently reduce the full single-bet opportunity pool. Explain “best among combinations searched,” not an unqualified global optimum.

Profit boosts correctly modify winnings rather than returned stake. The current calculation does not establish promotion eligibility, maximum bonus, stake caps or an accepted sportsbook ticket price. Those facts must accompany a claim that the boosted ticket has an attractive price.

Fanatics Sunday TD research is based on the supplied $5/three-leg/+2000 constraints and generates cross-game triples. Full official eligibility terms remain a separate uncertainty. Yard also has probability/price lookup paths keyed too coarsely by name and type; game and book identities need to remain attached throughout selection.

The target Parlay Lab should show the weakest leg, why each leg belongs, an evidence-based replacement set, exposure shared with saved tickets, the assumptions behind combined chance, and the sportsbook's actual combined quote when available. A high payout target should not force poor candidates into the pool.

## K. Results audit

The journal architecture includes immutable records, ownership policies in migrations, automatic hypothetical board collection, settlement scripts, odds-band results and price-movement diagnostics. These are valuable foundations. Production policy installation was not independently verified in this audit.

Coverage is the main problem. `settle_markets.py` handles full-game NFL/NCAA game markets and five NFL prop fields: passing yards, rushing yards, receiving yards, receptions and passing touchdowns. It does not provide complete settlement for anytime TD, First TD, rushing/receiving TD counts, 1Q/1H or parlays. The new First TD predictor and parlay outputs are not fully registered through the shared collector. A user seeing these recommendations cannot assume Results will later grade them.

The validation UI distinguishes hypothetical $100 flat stakes from actual entered bets. It has summaries/tables, but not the requested unified cumulative units/profit chart. Its near-kickoff reference observations are a useful price-movement diagnostic, not necessarily the actual final market close.

Yard's frozen pregame records are a good prospective design. A concrete failure case exists in `etl/grade_pregame.py`: a final schedule combined with an empty/missing boxscore can classify players as having no recorded appearance, persist the game as graded, and skip it on later runs. Unavailable data must remain retryable; it must not masquerade as a final nonappearance.

Previously settled football IDs also need a correction/reconciliation design. Preserve the original forecast, but allow a versioned settlement correction when an official stat changes. Record forecasts, published recommendations and actual bets separately so performance denominators remain honest.

## L. Cost audit

No runtime per-user LLM calls were found in the inspected recommendation/API paths. Primary recurring costs are odds requests, hosting, pipeline compute, storage and transfer, plus optional data services.

| Consumer | Current behavior | Cost/control issue |
|---|---|---|
| Football GitHub pipeline | Twice daily scheduled refresh | Separate from browser/scanner consumption. |
| Yard board | Eight daily scheduled runs during season; offseason gate reduces work | More frequent live/status and grading jobs are separate. |
| PC scanner | 60-second housekeeping; odds about every 120 seconds near kickoff, 30 minutes within a day, six hours otherwise | Its 60,000 estimated monthly cap covers its own requests, not the whole account. |
| Browser / odds API | Frontend refresh and server/CDN cache | Ten-minute cache and five-minute value freshness are inconsistent; refreshing need not produce a newly usable quote. |
| Baseball odds | Browser fetches multiple prop categories; ETL has its own fetch | Duplicate retrieval opportunities. |
| Snapshots | GitHub-hosted updates plus packaged static files | Mixed freshness and repeated transfers; Long history is about 9.3 MB locally. |
| Journal | SQLite plus Supabase, immutable history and repeated scans | Growth, sync backlog, retention and query-window controls matter. |

The provider documents endpoint/request credit accounting; an HTTP request count alone is not a complete account-wide cost estimate. [Parlay credit explanation](https://parlay-api.com/answers/how-odds-api-credits-work), [API documentation](https://api.parlay-api.com/docs).

The previously stated 100,000 monthly allowance is a planning constraint, not a balance verified in this audit. Do not allocate it from a single worker's counter. Centralize fetches by sport/event/market/time bucket, coalesce simultaneous requests, record actual usage where available, and reserve budget for final-window updates. Stale cached research should remain readable with its timestamp.

A runtime issue also affects cost and reliability: sequential 45-second provider waits, including a later fallback, can exceed the route's 60-second Vercel budget. Use one request deadline and a partial-result contract.

Actual provider balances, Vercel/Supabase plan headroom, paid optional-source usage and commercial redistribution rights remain unverified. A subscription product needs these checked before pricing or launch promises.

## M. Risk register

| ID | Priority | Risk and evidence | Required control |
|---|---|---|---|
| R1 | P0 | Raw board presents extreme probabilities/returns with stake suggestions while other rankers reject similar disagreements. | Shared model-quality and price checks; review-only state propagated everywhere. |
| R2 | P0 | Displayed markets/builders lack complete recording and settlement. | Coverage registry and automatic immutable recommendation records. |
| R3 | P0 | Empty MLB boxscore can become permanent nonappearance. | Validate completeness, retry and reconcile. |
| R4 | P0 | Historical evaluation does not consistently use data-availability time. | Strict forecast cutoff and poison/future-data tests. |
| R5 | P0 | API fallback can outlast serverless deadline; freshness clocks conflict. | Single deadline, partial responses and coherent freshness policy. |
| R6 | P1 | Hard caps/coarse deduplication hide legitimate alternatives. | Canonical full pool; category ranks and stable pagination. |
| R7 | P1 | Supporting context can be mistaken for an actual model input. | Separate drivers/context; immutable evidence lineage. |
| R8 | P1 | Current participation unavailable; prior roles may be stale. | Source-specific missingness and explicit historical fallback. |
| R9 | P1 | SGP lacks complete compatibility and accepted price. | Constraint graph and honest unpriced state. |
| R10 | P1 | Several ledgers and generic model versions prevent clean comparison. | Canonical IDs, versioned policies, shared read model. |
| R11 | P1 | Browser/CI/scanner can consume the same odds budget independently. | Shared usage ledger/cache with reserve and degradation policy. |
| R12 | P2 | Sparse football samples and overlapping features create false certainty. | Shrinkage, grouped uncertainty, incremental tests and market baselines. |
| R13 | P2 | Player context not integrated into NFL/NCAA game forecasts. | Validated player-aware model additions. |
| R14 | P2 | Raw score calibration plus ad hoc multipliers can overstate probability quality. | Calibrate the complete final model on future holdouts. |
| R15 | Launch blocker | Rights, billing, entitlements and production security/operations not fully established. | Commercial/source review and explicit launch readiness checks. |

## N. Prioritized roadmap

These are reviewable increments. Each should preserve current working routes and fantasy features, include a before/after comparison, and be committed independently after validation. No implementation started as part of this audit.

### P0.1 — One trust policy across existing displays

- **Objective / benefit:** Prevent raw-model outliers from looking like approved bets while preserving them for research.
- **Files:** Long `index.html`, `shared/football-parlays.js`, `shared/touchdown-promo.js`, `scripts/topdown/model.py`; Yard `docs/index.html` probability display paths.
- **Dependencies:** Existing model/source/quote metadata inventory; no new provider.
- **Implementation:** Define supported, research-only, priced, review-required and unavailable states; attach exact reasons. Separate chance, price advantage and uncertainty. Remove actionable stake suggestions from unresolved disagreement states.
- **Tests:** Outlier, stale quote, prior-season role, missing source, unsupported period, and equal-contract price fixtures on every surface.
- **Acceptance:** The same contract has the same trust state everywhere; research remains inspectable; no invalid record silently disappears.
- **Risk:** Overly broad gates can suppress useful research. Separate visibility from actionability and record all exclusions.

### P0.2 — Complete recording and reliable settlement

- **Objective / benefit:** Make Results represent what the product actually recommended.
- **Files:** Long `collect_model_plays.cjs`, `topdown/tracking.py`, `journal.py`, `settle_markets.py`, Supabase migrations, validation metrics; Yard `pregame_records.py`, `grade_pregame.py`.
- **Dependencies:** P0.1 states; explicit market/period/rule registry.
- **Implementation:** Freeze recommendation and evidence IDs before start; register First TD/parlay outputs; add supported settlement adapters; keep unavailable outcomes pending; version corrections. Never reconstruct an old forecast from today's model.
- **Tests:** Final-with-empty-boxscore, delayed results, first scorer/DST/no-TD, period boundaries, zero participation, ties/refunds, stat correction, duplicate scan and retry.
- **Acceptance:** Every published recommendation has a durable ID and visible settlement status; unsupported markets cannot imply automatic grading; retries do not double-count.
- **Risk:** Sportsbook settlement differences. Preserve rule assumptions and keep ambiguous cases ungraded rather than guessing.

### P0.3 — Repair validation time boundaries

- **Objective / benefit:** Make historical evidence usable for model decisions.
- **Files:** Long `build_pipeline.py`, `backtest_topdown.py`, `backtest_nfl_context.py`; Yard `etl/backtest.py`, calibration artifacts.
- **Dependencies:** P0.2 forecast/source timestamp contract.
- **Implementation:** Gate by actual availability time or conservative documented delay; remove future season aggregates; distinguish actual-lineup diagnostic replay from pregame forecasts; benchmark complete probability paths against simple and market baselines.
- **Tests:** Overlapping kickoffs, future-stat poisoning, unavailable lineup, season boundary and deterministic fold replay.
- **Acceptance:** Adding future information cannot change an earlier forecast; every performance report names its cutoff policy and eligible population.
- **Risk:** Historical inputs may not exist. Report the narrower valid test instead of filling gaps with present-day data.

### P0.4 — Odds deadline and freshness consistency

- **Objective / benefit:** Stop prolonged loading and contradictory fresh/stale states.
- **Files:** Long `server/parlay.mjs`, `api/odds`, `vercel.json`, frontend refresh logic and scanner adapters.
- **Dependencies:** Provider response/credit metadata already available.
- **Implementation:** One deadline per request, coalesced fetches, partial-category statuses, explicit truncation detection and separate fetched/book timestamps.
- **Tests:** Timeouts, category failure, 10,000-row truncation, cached responses, concurrent consumers and clock skew.
- **Acceptance:** Usable cached data renders promptly; route finishes within its budget; missing categories never claim completeness; freshness agrees across screens.
- **Risk:** Provider pagination/limits may constrain recovery. Expose incomplete coverage instead of extra uncontrolled polling.

### P1.1 — Canonical opportunity pool and evidence contract

- **Objective / benefit:** Preserve all qualified opportunities and make explanations reproducible.
- **Files:** Extract existing ranker/identity helpers from Long `index.html` into shared pure modules; tracking adapters; Yard `going-platform.js` and odds joins.
- **Dependencies:** P0 trust states and recording identifiers.
- **Implementation:** Canonical event/entity/market/period/side/line/rule identity; quote children; eligibility separate from rank; typed reasons/risks; source snapshots. Add exhaustive pool pagination and exclusion diagnostics.
- **Tests:** Overs/unders/alternates, duplicate kickoff formats, MLB doubleheaders, book selection, order stability and pagination completeness.
- **Acceptance:** Every qualifying contract is reachable and counted; changing ranking cannot change eligibility; evidence reproduces the original card.
- **Risk:** ID migration could duplicate old records. Use explicit legacy mapping and compare counts before switching.

### P1.2 — Unified discovery and research UX

- **Objective / benefit:** Let a casual bettor understand the slate quickly.
- **Files:** Long `hub/index.html`, `shared/going-shell.*`, `index.html`; Yard `docs/index.html`, `going-platform.js`; validation navigation.
- **Dependencies:** P1.1; preserve draft/trade flows.
- **Implementation:** Shared design tokens and navigation; discovery/why/research layers; all-opportunity filters; one card per contract with books inside; visible main risk; market-specific tools nested under research/Parlay Lab.
- **Tests:** 375/390/430px widths, keyboard navigation, 44px targets, contrast, filter persistence, loading/empty/error states and fantasy regression checks.
- **Acceptance:** A new user can find a recommendation, inspect its evidence, compare books and return to the full pool without losing context. No emoji or untranslated primary betting/statistics jargon.
- **Risk:** Hiding advanced tools too deeply. Keep stable deep links and an accessible full research view.

### P1.3 — Results that explain performance

- **Objective / benefit:** Show what is improving and what remains uncertain.
- **Files:** `apps/validation/src.jsx`, `metrics.mjs`, `load-journal.mjs`, shared journal query layer.
- **Dependencies:** P0.2; P1.1 identifiers.
- **Implementation:** Cumulative units/profit, drawdown, probability reliability, price movement, odds-band and market breakdowns; separate all forecasts, published plays and actual bets; expose pending/missing/corrected results.
- **Tests:** Hand-calculated stakes/refunds, duplicate contracts, date ranges, corrections, empty history and pagination/query limits.
- **Acceptance:** Chart totals reconcile with the ledger; hypothetical stakes are unmistakable; no historical probability is replaced by today's estimate.
- **Risk:** Many charts can create false patterns in small groups. Show denominators and uncertainty, not decorative rankings.

### P1.4 — Parlay Lab compatibility and replacement engine

- **Objective / benefit:** Make configurable combinations useful without inventing joint certainty.
- **Files:** Long `shared/football-parlays.js`, promo module; Yard parlay functions; canonical pool and tracking.
- **Dependencies:** P1.1 and P0.2.
- **Implementation:** Explicit incompatible/shared-outcome rules, price provenance, best replacement candidates, exposure view, weakest-leg explanation and boost caps/eligibility fields. Keep unsupported SGPs as research.
- **Tests:** Contradictory outcomes, period/full-game overlap, same-player legs, no feasible combination, boost profit cap and replacement constraints.
- **Acceptance:** No impossible ticket; no invented SGP price/chance; every displayed ticket can be recorded with assumptions; bounded search is disclosed.
- **Risk:** Full combinatorial search is expensive. Preserve all singles while using transparent bounded ticket search.

### P1.5 — Shared cost and source-health controls

- **Objective / benefit:** Keep usage within the monthly plan while retaining useful final-window data.
- **Files:** `server/parlay.mjs`, scanner configuration, football/Yard workflows, snapshot adapters and operational status views.
- **Dependencies:** P0.4; verified provider accounting.
- **Implementation:** Shared fetch buckets, account-wide usage reconciliation, monthly/final-window reserves, offseason cadence, cache hit metrics and source-age status. Define journal retention/archive policy without deleting audit history blindly.
- **Tests:** Simulated month/slate consumption, concurrent jobs, provider outage and low-budget degradation.
- **Acceptance:** All consumers contribute to one budget estimate; remaining balance is reconciled where available; exhausting discretionary refresh never breaks cached research.
- **Risk:** Provider headers may not expose exact usage. Mark estimates and reconcile manually at the account level until supported.

### P2.1 — Validated football opportunity and game models

- **Objective / benefit:** Connect available player opportunity to actual prop/game forecasts.
- **Files:** `build_pipeline.py`, `pbp_features.py`, `football_context.py`, model calibration/export schemas.
- **Dependencies:** P0.3; current source coverage; P1.1 evidence.
- **Implementation:** Position-relative pass-snap/usage gaps with shrinkage; opportunity-versus-efficiency decomposition; opponent-adjusted team baseline; player availability/usage contribution. Add one feature family at a time. Keep unsupported routes/slot/OC identity inactive.
- **Tests:** New team/role, missing participation, low targets, held-out seasons/weeks, baseline comparisons and feature removal tests.
- **Acceptance:** Each promoted adjustment improves a predeclared future-period metric or remains explicitly experimental; NCAA stays game-only for betting.
- **Risk:** Sparse NFL data and unstable college rosters. Pool carefully, widen uncertainty and avoid unsupported fine splits.

### P2.2 — Baseball probability and incremental-signal validation

- **Objective / benefit:** Separate useful ranking signals from credible event probabilities.
- **Files:** Yard `compute.py`, `features.py`, `runs.py`, `backtest.py`, frontend probability helpers and calibration exports.
- **Dependencies:** P0.3 and complete frozen records.
- **Implementation:** Calibrate the final adjusted model; benchmark contact, pitch mix, bullpen and environment individually and jointly after market price; distinguish missing inputs from poor metrics; retain simpler runs model if it wins.
- **Tests:** Future holdouts, missing Statcast, lineup changes, doubleheaders, grouped resampling and baseline comparison.
- **Acceptance:** Probability labels describe the validated final path; raw scores cannot silently become chances; claimed improvements include a measured denominator and uncertainty.
- **Risk:** Correlated features and multiple comparisons. Predeclare experiments and keep untouched evaluation periods.

### P3.1 — Controlled learning and commercial launch readiness

- **Objective / benefit:** Improve safely and establish conditions for a subscription launch.
- **Files:** Model registry/evaluation jobs, Results, source registry, deployment/auth configuration; later billing/entitlements once product boundaries are chosen.
- **Dependencies:** P0–P2 foundations and sufficient prospective history.
- **Implementation:** Champion/challenger reports, versioned promotion/rollback, drift alerts; commercial source-rights inventory; authenticated tenant tests; onboarding, billing and support/operations plan. These are separate small releases, not a single rewrite.
- **Tests:** Reproducible model rollback, failed promotion, cross-account isolation, quota stress and subscription entitlement fixtures when implemented.
- **Acceptance:** No model self-promotes from a short winning streak; each release has reproducible evidence; launch passes explicit data-rights, trust, security and operating-cost gates.
- **Risk:** The calendar can pressure premature claims. Readiness evidence, not the next season's date, should determine launch scope.

## O. Questions and disagreements

1. **I agree with preserving the full qualified single-bet pool. I do not recommend enumerating every possible parlay.** The number of combinations grows too quickly. A bounded search with disclosed coverage is defensible; hiding qualifying singles is not.
2. **A high chance of winning is not confidence in the model.** Show both estimated chance and how much evidence supports it. A heavily favored outcome at a poor price should not receive a value badge simply because it wins often.
3. **More inputs are not automatically more edge.** Coaching head-to-head, slot matchups and complex models need available data, stable definitions and future-period tests. Free public data cannot support every proprietary charting claim.
4. **The reason a price moved is usually not observable here.** Current odds snapshots do not establish emotional money, informed money or bookmaker intent. Describe the measured movement and disagreement without inventing a cause.
5. **“Calibrated” must apply to the final probability path.** A measured starting rate followed by unvalidated multipliers does not earn that label automatically.
6. **A unified product does not require rewriting everything in React.** Shared contracts, pure calculations, design tokens and a common journal solve the present problems more directly.
7. **Product decision for review:** I recommend public discovery emphasize explanatory research and priced opportunities, with operational scanner/arbitrage diagnostics inside advanced research. The scanner remains useful internally; it should not define the entire user experience.
8. **Launch decision for review:** I recommend treating next baseball season as a target, with scope conditional on prospective results, data rights and operating readiness. Do not promise demonstrated profitability or full automation for markets the tracker cannot yet settle.

**Stop point honored:** this audit proposes the work. Application/model restructuring has not begun, and the implementation sequence waits for review of this assessment.
