# GOING Picks manual product reset

Cycle `20261005-122407-picks-reset-manual-a`. This is Travis's major manual product/data/research session, not a scheduled 15-minute cycle. The overlapping 14:00 heartbeat was deferred under this exact common-Git mutex; no scheduled snapshot was backdated or replayed.

The product now starts with **NFL → select game → ranked GOING Picks → why / concern / observed price → optional research**. The nearest upcoming game opens automatically. Six cards initially, Show more without a permanent cap. Existing Confidence classifications, filters, full ranked lists and diagnostics remain behind collapsed advanced research. Approved reference colors, typography, cards, navigation and bottom navigation remain intact.

## Decisions that won

- PRODUCT argued for Yard's immediate ranked candidates and explanatory badges. Literally testing production Yard showed ranked hitters on opening Betting, no evidence workflow required. Long now shows the default game's candidates on opening Betting; one game selection finds another game's bets. It adds football complexity in optional research, not initial navigation.
- PRODUCT suggested reusing Score; MODEL RESEARCH rejected it because a player index cannot rate an exact Under/line. A distinct direction-aware football-case rating won. Positive Any-TD probability alone is not evidence of an interesting directional thesis.
- MODEL RESEARCH challenged overlap between projections and current production: those inputs alone are capped at 3/5. No probability/market-favorite sort or easier-to-populate game-market priority.
- FOOTBALL DATA rejected inferred routes, missing-row-as-absence, and automatically boosting the obvious backup. Only measured opportunities and explicit weekly OUT/participation cohorts are used. Undated injury reports are retrospective descriptive associations, not immutable historical pregame knowledge.
- All roles agreed stale/missing price should not erase a football thesis, but cannot establish a live price or profitable betting edge.

Full exact recipe, market requirements, badge triggers and limits: production `docs/GOING_PICKS.md`. Initial weights/trend thresholds are policy assumptions, not fitted or empirically validated. Champion/C1/C2, Score, ABBEYS, DFS/Throne, 2+TD and frozen ranking definitions are unchanged.

## Actual current inputs and manual audit

`audit.json` contains actual candidate fields, exact source/policy hashes, component explanations, facts, concerns and observed price times. The 18:46:30Z offline audit used already public/current source snapshots, no credentialed odds call. 5,448 vendor rows consolidate to 287 market-family cases; 56 individual rows fail intact integrity/model/status gates. There are 259 positive primary cases (100 NFL, 159 NCAA) across 69 modeled games; separate Any-TD role research does not enter the primary Picks tracker.

| Game / exact research bet | Rating / badges | Football case | Main concern | Observed market |
| --- | --- | --- | --- | --- |
| ATL @ NO: NO to win | 3/5, MODEL + | Existing model direction plus raw current home margin 2.5, 3/3 finals | Only three current games | Hard Rock -120, Oct5 11:52ET |
| ATL @ NO: Under47.5 | 3/5, MODEL + | Projected total about46.5; raw current context47.2 | Same small sample, overlapping inputs | FanDuel -110, Oct5 11:52ET |
| TB @ DAL: Godwin Over27.5 receiving yards | 4/5, MODEL + / VOLUME / ROLE UP | Targets3.5→5.5, two chronological groups of two; model36.8 | Four-game count trend is not a lasting route/injury causal change | Novig -113, Oct5 06:38ET |
| TB @ DAL: Irving Over56.5 rushing yards | 4/5, MODEL + / VOLUME / ROLE UP | Carries12.5→15.5; model60.2 | Role trend may reflect script/opponents | FanDuel -114, Oct5 06:39ET |
| PHI @ JAX: Under43 | 3/5, MODEL + | Existing model and current raw context40.6, 4/4 finals | Opponent/personnel may change environment | Hard Rock -110, Oct5 11:52ET |
| Southern Miss @ Troy: Under49.5 | 3/5, MODEL + | Existing model and NCAA current context47.3, 3/3 finals | Small team sample; no NFL-role requirement | BetOnline -110, Oct5 11:52ET |

These are observed snapshot prices, **all need refresh at audit time**, not executable-price or value claims. Related markets are correlated, not independent bankroll opportunities. No current NFL game in the loaded modeled pool was empty. The actual NCAA Sacramento State @ Bowling Green game correctly shows no Picks because it lacks a usable matched pregame model/contract.

Noah Fant Over15.5 receiving yards is 2/5: current role4 targets/game and model support, but Questionable participation lowers the rating; confirm status for this actual game. Existing historical injury treatment remains deeper research, not a newly verified causal effect. No current exact-game OUT pair qualifies for a new injury boost; none was fabricated.

Ryan Flournoy's existing catch-opportunity evidence is15.9 CP-summed expected catches versus13 actual on23 modeled targets. It helps separate opportunity from outcome; it is not expected receiving yards, bounceback evidence or extra rating points.

## Useful new free data / remaining gaps

Additive public NFLverse/PFR-GSIS evidence:475 players' verified complete-game participation logs, explicit positive offensive snaps, target/carry counts and shares, weekly rosters/statuses, and569 teammate absence pairs,96 with at least two observations per condition. Cross-position redistribution is included. Omitted player-games are unknown; zero usage requires positive participation plus complete PBP. Every original football-context field remains unchanged.

The actual2026 injury table lacks publication timestamps (423 report rows with unknown time). It cannot establish historical pregame availability, instant active/inactive changes or reliable next-game confirmation. Missing current routes, first reads, alignment, pressure/OL, current charting and expected yards/TD models remain gaps. Existing goal-line/red-zone PBP is available but receives no unvalidated new bonus. Tiny with/without cohorts do not establish causality. Prioritize sources by the betting question resolved, not dataset count.

## Prospective learning and preserved records

First real pregame capture `2026-10-05T18:32:04.523Z`:259 priced predictions plus259 immutable research receipts in a separate `going_picks_v1` / `going-picks-v1` cohort. Each pins exact bet, line/book/price, rating, badges, opportunity/injury/matchup facts, model output, concern, actual time and input/policy hashes. All12,183 previous tracker records and all247 existing review ranking blobs/modes remain unchanged. Zero new settled Picks; no retrospective relabeling or performance claim.

Unpriced football cases retain research receipts and later official outcomes, without invented wagers/ROI. Valid priced contracts use existing full-game result rules, push/void handling and $100 profit/ROI graph. Register exact future splits/benchmarks/release criteria before fitting; first four future weeks are integrity/descriptive coverage, next four remain untouched for a separately registered challenger. Game-cluster uncertainty and adequate samples are required; no early model promotion or existing holdout inspection.

## Verification / workflow investigation

440/440 Node and114/114 Python tests pass; production and Vercel builds pass. Actual published data was tested at430/393/390/375/360/320 and1440×900; no horizontal overflow, clipped cards or blocked bottom navigation. Card disclosure, game/league/family selection, Show more6→12, exact-contract comparison and tracker cohort selection worked. DFS Captain tools and Score navigation remained reachable; existing non-betting regressions pass. Local production artifact has no app JavaScript errors; a pre-existing Vite dev ErrorOverlay failure occurred separately and was not hidden by a config workaround. Desktop/mobile screenshot proofs are adjacent.

[Failed refresh37336119083](https://github.com/daboli69/going-long/actions/runs/37336119083): NFL props provider returned503 `PROPS_TEMPORARILY_BUSY` after bounded retries. Previous props were preserved as FALLBACK;27 successful snapshots were committed as8812018628ba0baf9047b4fa0a1049aecfd0c408, then the source summary correctly failed. Credentialed existing ParlayAPI steps ran under Travis's previously confirmed $0 additional allowance; billing cannot be independently established from logs. No local paid call, provider activation, manual retry deployment or workflow bypass. Existing script-triggered refresh remains unchanged.

Production/review/receipt SHAs, exact patch replay and verified live status are recorded in PROGRESS.md and the final publication report. Claude review materials are publication evidence, not a claim that an external Claude verdict has occurred. No Travis action is needed for the routine tested reset.
