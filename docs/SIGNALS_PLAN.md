# Signal system: repository audit and implementation plan

Audited 2026-09-11 against main 0d1baa6, local source, production snapshots and live /api/odds requests. No AGENTS.md in the repository or workspace ancestry; no .openai/hosting.json. Deployment remains Vercel.

## Current inventory

- index.html: single-file client; betting props/game lines/periods/projections, fantasy draft board and Trade Analyzer. Node/jsdom tests cover routing and betting math.
- scripts/build_pipeline.py: nflreadpy weekly player stats, rosters, snap counts, schedules; sportsdataverse cfbfastR schedules. Trailing 12 appearances, at least 5 games. Snap counts add zero-stat appearances. Exact/team-aware fuzzy matching exports aliases. Mixed nonpositive/positive lognormal yardage and Poisson counts; First TD competing hazards; scaled 1H/1Q distributions. Game score projections have walk-forward error summaries, not validated betting returns.
- scripts/pbp_features.py: neutral-win-probability PBP, first 15 plays, team pace/pass tendency, pass-snap participation proxies, air yards, goal-line shares, charted pressure and coverage. Missing routes, OC identity and slot alignment are explicitly inactive. Some old availability text says First TD inactive despite the newer derivative model; model fitting and predictive validation must be distinguished.
- scripts/build_history.py: fantasy weekly history and NGS season aggregates (266 players have an NGS block). These are not weekly efficiency trends or career histories.
- scripts/build_data.py: Sleeper roster, FantasyFootballCalculator ADP, FantasyCalc trade values. Existing fantasy sources are outside the new signal design; no new dependency on their values.
- scripts/build_nfl_betting.py, build_ncaa_lines.py, parlay_feed.py and server/parlay.mjs: normalized real Parlay odds. server/worker.mjs is the alternate hosting adapter.
- api/odds.mjs: GET NFL/NCAA, server-only PARLAY_API_KEY, two-minute runtime cache, compressed output, safe provider errors. api/snapshot.mjs: four allowlisted GitHub snapshots with packaged fallback. No write API, database, outcomes endpoint, pick history or closing-price archive.
- config/parlay-markets.json defines aliases; vercel.json builds static files plus Node functions. GitHub Actions refreshes snapshots daily at 10:20 UTC; visible client refreshes odds every five minutes. No unattended personal bet tracking exists.

Production requests succeeded: NFL 10,765 props, 79 raw games, 1,700 period quotes; NCAA zero props, 140 raw games, 1,274 period quotes. Counts are observations, not fixed expectations. Historical betting snapshot has 784 profiles. A fresh snapshot timestamp does not make its historical observations fresh: many last-game/participation dates are January 2026.

Existing engine computes win/refund/loss probabilities, return per dollar (including refunds), and quarter-Kelly capped at 2% bankroll. It chooses the higher modeled-return side. Game comparison selects best lines; it does not yet build a robust same-contract, one-vote-per-book reference. First TD normalizes the listed bookmaker pool only, explicitly not complete-market margin removal. DFS prices have no fabricated single-pick payout. There is no measured signal hit rate, signal calibration or historical odds archive.

## Reviewable increments

1. **Evidence engine and grouped explorer.** Same-contract price shopping; line disagreement using one representative main line per book; a historical-model gap in either direction. Contextual flags for catching up/run protection, faster neutral pace, pass-snap target demand and pressure only with enough recent observations. These are inspectable mechanisms and screening rules, not fitted increases in win probability. Count distinct evidence families, not badges: role and game script overlap; multiple market badges count once. Show confidence as not established, with the supporting families beside it, rather than invent a 0–100 strength score. All predictive flags start experimental.
2. **Prospective trust ledger.** Freeze first-seen predictions, signal version, input dates, prices, book, kickoff and a same-book two-sided reference before kickoff. Log both flagged and unflagged eligible candidates for an honest comparison within the observed board. One observation per contract/side prevents multiple books inflating the record. Local device storage, explicit export/import backup and durable weekly stars; stars reset Tuesday Eastern, tracked records do not. Record later pregame prices only while the app is open; a quote near kickoff is labeled a sampled closing price, never an invented true close. No retrospective signal backfill. Auto-grade supported full-game NFL props and NFL/NCAA game lines from public results; unsupported periods/First TD require an explicit user-entered settlement. Manual results stay out of automatic validation summaries.
3. **Pick ideas and plain-language UI.** Single picks plus two-leg, same-book, different-game illustrations: higher estimated chance versus larger estimated return. No same-game product-of-probabilities. Reject duplicate games and missing/stale prices; no DFS payout without contest rules. Show the independence assumption, estimated combined chance and illustrative product payout, not a guaranteed or quoted parlay price. Save a build and grade its legs including void/refund reductions. No confidence lift from combinations.

## Data readiness and changes to proposed ideas

Ready: current prices, full-game model distributions, recorded game outcomes, player box scores. Public proxies: participation counts, pressure and neutral pace; require current last-observation dates and denominators, otherwise explain inactivity. Role expansion is a watch item, not a promise that routes will increase. Model-vs-line gaps are not proof that a sportsbook is chasing recent results.

Defer: defense-by-position ratings (existing aggregate does not preserve position/opponent strength sufficiently), injury/depth-chart changes (no verified timely feed here), drops/tips/luck (incompletions do not identify blame), NGS trends (only season aggregates wired), full-career milestones (rolling data insufficient), coverage-based efficiency boosts (thin per-player cells), same-game joint probabilities, weather and promotion scraping. No fabricated placeholders for these. Percentiles require like-for-like position/market and recent eligible peers; defer rather than compare unlike populations.

## Validation policy and methodology

Screening thresholds are versioned policy, not research-proven cutoffs. Do not automatically promote any signal to calibrated just because N gets large. Status is unvalidated with no automatic resolved observations, then early recorded results with actual contract count and distinct games. Probability accuracy uses three-outcome squared error against the frozen two-sided bookmaker reference on exactly the same records; separate refunds and voids. This is a descriptive prospective check, not evidence of causal lift. Weekly/season out-of-time evaluation and uncertainty grouped by game are prerequisites to a future calibrated status. Selected picks, manual results and unflagged comparison groups remain distinguishable. No retroactive refitting using outcomes.

The probability scoring approach follows Gneiting and Raftery, *Strictly Proper Scoring Rules, Prediction, and Estimation* (2007): https://stat.uw.edu/research/tech-reports/strictly-proper-scoring-rules-prediction-and-estimation . Smaller squared forecast error is better; a made-up confidence percentage is not a substitute.

Bet size depends critically on estimated probabilities; fractional sizing reduces exposure to estimation mistakes, not proof the estimate is good. See David Aldous, *The Kelly criterion*: https://www.stat.berkeley.edu/~aldous/Real_World/kelly.html . Existing engine sizes remain model estimates; new experimental suggestions do not add stake multipliers.

Price movement supplies information beyond a binary win/loss, but closing markets can be wrong, especially thin props. Same contract and side are required to compare prices; movement in the line is reported separately from price movement. Public empirical evidence in soccer is not a measured NFL effect: https://www.football-data.co.uk/blog/pinnacle_efficiency.php . Do not call price movement proof of profitable skill.

Public charting definitions and release timing: https://nflreadr.nflverse.com/reference/load_participation.html and https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html . Attribute FTN via nflverse for post-2022 charting; do not call pass snaps routes.

## Verification

Test price identity, stale/future inputs, both directions, duplicate books/games, immutable pregame logs, no future-outcome leakage, void/refund settlement, probability scoring, missing results, restored storage and weekly stars. Browser test mobile 375/430 px and existing routes. Run existing JS/Python tests and both production builds, then push reviewable commits and check Vercel.
