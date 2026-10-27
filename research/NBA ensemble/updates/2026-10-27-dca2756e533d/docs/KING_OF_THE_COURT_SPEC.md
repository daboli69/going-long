# King of the Court: pre-implementation research specification

Prepared 2026-10-27 before implementing the module. Scope: local, Tuesday NBA regular-season PRA-leader research. No interface, live wagering, publication or change to NBA winner/NFL models. The final user instruction resolves the earlier current-season-only paragraph: use season-to-date plus the three preceding NBA seasons. Ending-year 2027 means 2026–27.

## 1. Contest interpretation and evidence

The two user-supplied screenshots show an account offer dated **October 27, 2026**, identifier EP70GG. They are the primary evidence for this particular offer; their complete linked sweepstakes terms are not included. Do not substitute another account's prize pool or another week's top-three promotion.

| Question | Interpretation | Evidence / unresolved issue |
| --- | --- | --- |
| Prize | $1,000,000 in non-withdrawable bonus bets | Screenshot; not cash or cash-equivalent EV |
| Winner | Highest combined points + rebounds + assists among that day's NBA players | Screenshot; exact eligible games/player market list still requires a pregame offer receipt |
| Tie | All qualifying customers selecting any tied leader share one pool equally | Screenshot item 7; do not split pool equally between players |
| Entry | Opt in; select one single-use token before placing a qualifying wager | Screenshot; one token per customer |
| Qualifying wager | Prematch NBA player-prop single or Same Player NBA Parlay, all legs on one player; at least $5; each leg -200 or longer | Screenshot; ordinary parlays/SGPx/boosts/live/cashed-out/voided bets excluded |
| Funds | Cash balance or DK Dollars | Screenshot |
| Deadline | Token expires at the start of the final October 27 game; a qualifying prop must still be prematch | Screenshot; this is not permission to produce a whole-slate prediction after earlier games start |
| Distribution | Within 24 hours / following day; expires seven days after issuance | Screenshot |
| Account eligibility | Screenshot lists 21+ in AR/AZ/CO/CT/IA/IL/IN/KS/LA (select parishes)/MA/MD/ME/MI/MO/NC/NJ/NY/OH/OR/PA/TN/VA/VT/WA/WV; 18+ in DC/KY/NH/PR (residents only), physically located | Transcription of offer display; not independently verified jurisdiction rules |
| Must original prop win? | Leader selection appears independent of the prop result; no winning-prop condition appears in the shown eligibility text | Interpretation, not fully verified October 27 legal terms; payout calculations remain conditional on a valid qualifying entry |
| Overtime, stat corrections, postponement, cancellation, interrupted games | Unresolved in the shown promo text; voided bets are explicitly ineligible | Never invent a settlement rule; unresolved contests stay pending |
| Recurrence | User expects Tuesdays; operator's indexed October 27 article also describes recurring Tuesdays | Editorial corroboration, not immutable future offer terms; each date needs its own offer record |

Verification attempt: operator editorial search result at https://dknetwork.draftkings.com/2026/10/27/draftkings-king-of-the-court-value-picks-for-tuesday-10-27-26/ supports recurring Tuesday marketing and token mechanics. Opening that page and https://sportsbook.draftkings.com/promos/king-of-the-court failed in the available browser tool. An indexed editorial result contained inconsistent player text and is not used for player/team facts. Complete account-specific sweepstakes terms, exact slate, cancellation rules and official promotion-specific crowd data remain unavailable. Search results from other dates/publishers do not upgrade these to verified facts.

## 2. Sources and missingness inventory

| Material | Free source / intake | Current evidence and use |
| --- | --- | --- |
| Schedule and official reported boxes | hoopR / sportsdataverse shared ESPN release archives | Accessible via GitHub; season 2025 discovery: 35,250 player rows, 2,648 team rows, including postseason/exhibitions. 6,940 player rows have missing minutes; do not convert unknown/DNP rows to zero production. These are digested boxes, not event evidence. |
| Raw play-by-play, substitutions and lineups | nba_api NBA live JSON; pbpstats possession/lineup processing; SportsDataverse PBP archives | Adapter/reconciliation layer; unavailable events remain explicitly missing. NBA IDs and ESPN IDs require an explicit crosswalk. No independent-provider claim for duplicate underlying events. |
| Pregame roster, injuries, starters, expected rotation | Timestamped source exports | Not in historical box archives; required manifest before a full-slate prospective run. Never infer a historic roster from who eventually played. |
| Tracking opportunities | NBA tracking where freely accessible | Potential assists and actual rebound chances are not inferable from credited box assists/rebounds. Missing tracking stays missing; label FGA/FTA and missed-shot pools as proxies. |
| Actual qualifying token selections / total entrants | Operator's promo-specific disclosure/export | Unavailable. No measured ownership percentages or unconditional monetary EV. |

The managed environment allows GitHub/package downloads, not direct NBA/ESPN/PBP Stats/sportsbook network access. Browser search can retrieve indexed evidence but does not supply a live statistics pipeline. Source exports can be imported locally; no proxy bypass or paid service is used.

Store raw content-addressed files and retrieval receipts. Canonical records retain source-known times separately from game times. Preserve gaps and reconciliation failures. Full production-grade possession/lineup claims require event/box agreement; a box-only run is a disclosed research approximation with recommendation readiness blocked.

## 3. Model specification

**History boundary.** For target ending-year S, use only S−3 through S and only results known before the decision origin. Decay each game's contribution by both season age and within-season age. Newer seasons always receive larger per-game season multipliers; no missing season contributes a zero. Report weighted effective sample size `(sum w)^2 / sum(w^2)` and each season's actual weight share. A sparse current season may contribute fewer total observations while retaining greatest per-game weight. Pre-register a small decay/shrinkage grid and select on earlier chronological development folds; freeze selected settings before later evaluation. Compare current-season-only and equal-weight variants.

**Experience.** Use externally sourced debut/experience metadata known at prediction time. Do not label a player a rookie just because a dataset lacks their prior history. Learn same-experience/position priors from earlier historical NBA rookie or second-year appearances, at the same early-season game-count stage, with league fallback explicitly labeled. Separate current-team minutes/role from transferable player production rates. Team changes reset the role sample; they do not erase player skill history. Current pregame rotation scenarios have priority over a past team's minutes. Do not assign unverified scenario probabilities to questionable players.

**Team context.** Estimate pace, FGA/FTA per possession, three-point share, shooting efficiency, assist propensity and offensive/defensive rebound capture from weighted prior team games. Use opponent defensive and offensive context through symmetric matchup estimates, shrunk to the league. Show the measured inputs and formula. Box-derived possessions `FGA − OREB + turnovers + .44 FTA` are an explicitly conventional proxy, not counted PBP possessions. No hand-set individual matchup multiplier or inferred potential-assist tracking.

**Minutes and rotation.** Estimate recent current-team minutes and variability separately from per-minute opportunities. Incorporate only verified pregame starters, availability, lineup evidence and explicit expected-minute scenarios. Simulate joint minutes constrained to five players' worth of game time, with per-player game-length caps. Unknown participation blocks a purportedly complete-slate forecast; do not silently delete an uncertain high-ceiling player.

**Correlated simulation.** Use a shared game possession draw, empirical game-length/overtime uncertainty, team opportunity pools and jointly constrained minutes. Allocate integer shot attempts and free throws to roster players using per-minute opportunities and simulated minutes. Sample made shots with shrunk efficiencies. Allocate rebounds from actual simulated missed-shot pools and assists from actual made-field-goal pools, excluding the shooter from receiving their own assist. This preserves integer PRA, team/player accounting and shared pace/rotation/opportunity dependence. It is an aggregate game simulator, not a reconstruction of every live possession or exact five-player stint. Estimate variation from eligible history; mark unsupported components rather than claiming learned effects.

**Trend.** Show recent-vs-longer-window minutes, FGA/FTA opportunity and per-minute production separately, plus weighted uncertainty. Report upward evidence as a diagnostic; do not multiply a projection because a player is labeled trending. Compare shooting conversion separately from role changes. Rookies and role transitions retain wider model uncertainty.

**Leader.** Every draw compares the complete official eligible PRA field, including unselectable or unhighlighted contenders if the contest defines the leader over all players. Return expected PRA, 10/50/90 percentiles, sole-leader probability, tied-leader probability, inclusive-leader probability and Monte Carlo standard errors. Inclusive leader probabilities may sum above one. Equal fractional tie-credit probabilities sum to one but are not customer prize shares. Missing field/rosters block unconditional leader claims.

**Popularity and prize split.** Accept only complete, timestamped promo-specific counts as measured ownership. Alternatively accept an explicitly hypothetical complete ownership vector and total-other-entrant count. For each simulated leader set L, a customer selecting i receives `pool * 1{i in L} / (1 + sum(N_j for j in L))`, where N excludes this customer. Sample entrant counts under a supplied ownership scenario rather than replacing expected reciprocal counts with reciprocal expected counts. Report conditional face-value bonus-bet share and scenario sensitivity; never cash EV. Qualification ambiguity keeps all prize outputs conditional. No internally invented popularity percentages.

## 4. Validation protocol

Before outcomes: freeze this specification, candidate grid, code/source receipts, fold origins and later holdout. Each fold reconstructs a complete Tuesday slate using America/New_York date, before its earliest tipoff; never drop an early game after it begins. Use rolling S−3..S histories inside every fold. Capture current lineup/injury/offer evidence prospectively; historical box-only diagnostics cannot establish decision-time availability.

Validate independently: official box points/rebounds/assists, event reconciliation, exact roster/field identity, no future game or source-known time, duplicate/conflict detection, minutes/team-stat constraints, self-assist exclusion, tie math, timezone/date and source freshness. Synthetic fixtures test arithmetic only.

Evaluate PRA MAE, distribution CRPS and 80% interval coverage; sole/inclusive-leader event Brier/log loss and calibration; compare season averages, minutes-times-rate, current-only and equal-history baselines on identical player/slate cohorts. Report coverage and omitted slates. Use paired whole-slate bootstrap intervals and separate rookie/second-year/established cohorts. Candidate selection is performed only on earlier development outcomes; holdout is never used to choose weights. Sparse Tuesday evidence remains insufficient. Popularity accuracy needs actual selection counts; one winning pick cannot validate it.

No promotion or accuracy/ROI claim from a simulation count, test count or retrospective example. Existing model-promotion gates remain separate. No scheduled task, bet, alert or production publication.

## 5. Proposed output (entirely illustrative, not real player estimates)

| Player | Expected PRA | 10–90% PRA | Sole leader | Tied leader | Any leader | Popularity |
| --- | --- | --- | --- | --- | --- | --- |
| Example rookie A | 36.2 | 20–54 | 8.4% | 0.6% | 9.0% | Unknown; scenario input only |

Evidence: expected minutes and interval; current-team role sample; rookie-cohort prior provenance; FGA/FTA per minute; pace/offense/opponent-defense values; season weight shares and effective sample size; recent minutes/opportunity/efficiency changes separately. Readiness: research-only; missing live lineup/offer details listed. Scenario payouts appear only with an explicit ownership/entrant assumption. This mock row is not executable current-slate data.

Implementation follows this document; unavailable source evidence must constrain the output rather than be replaced with fabricated inputs.
