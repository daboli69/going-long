# Today ranking: likelihood is not demonstrated betting value

Cycle `20261002-2348-ranking-research`. Research-only, no model/ranking promotion. Source production `219c510d1d10c45f8b429fab338f6052d993af25`; frozen clock `2026-10-02T23:47:12Z`. The user paused/resumed the session; remote main subsequently advanced to `7b2633ba80177129151910e89e57de860832dd38` (data refresh, unchanged application/ranking source). Captured-tip safety gate blocks publication. No commit, push, completion marker or receipt was fabricated. Results describe the ORIGINAL frozen snapshot, not refreshed live prices.

## Actual Champion pipeline

1. Public sportsbook snapshots join current-week NFL props and NFL/NCAA games to historical/current-season production projections. Props use existing distribution models; game moneyline/spread/total estimates use existing margin/total distributions. Only supported contracts with legitimate quotes are priced; NCAA has no player props. DFS/manual input is not the automatic Today source. Whole-game and supported period/alternate markets retain their existing eligibility; First TD remains experimental.
2. `signalCandidates()` computes probabilities, push-aware expected return and flags. `renderBestPlays()` expands ALL offer rows, adds `bestPriceCandidates()`, and passes all matching quotes into `rankBestPlays()` (index.html). Best offer/exact contract is chosen after probability then return sorting; no intentional sportsbook-brand preference.
3. `opportunityPool()` requires matching sport/type, this ET Tuesday–Monday football week, future kickoff, valid quote timestamps and age <=24h. Chance pool additionally needs 0<p<1, n>=5 recorded games and no blocking check (historical-only checks may remain). This does NOT require five current-season games, positive estimated return or prospective calibration. An estimated return >25% is a discrepancy check, not a validated optimum; surviving EV-ranked candidates bunch below this ceiling.
4. Sort win probability DESC, estimated return DESC as tiebreaker; deduplicate exact canonical contracts. Annotate alternate families: primary prop line is the available price closest to decimal 1.91, not a guaranteed provider-designated main line. First-visit filters hide alternate PROPS and odds shorter than -500; game alternates remain. Saved preferences can override defaults. Date, game, type, book, query and focus narrow this pool; explicit probability/return/payout/kickoff sorts are available. GOING Score is not used.
5. Game-first cards preserve each game's leading candidate ordering, show at most three model entries/two price entries when expanded, then link to deeper lists. Flat top3 and first three GAME cards differ when several leading candidates share a game. NFL leading GAME cards here are NYJ@CHI, IND@WAS and GB@TB; the first two flat entries share NYJ@CHI.
6. Separate price-qualified list needs prices <=5m old, aligned exact line/side/book quotes within 60s, zero push, mandatory Pinnacle reference, <=3 percentage-point reference disagreement, minimum reference probability minus 1 percentage point, and return >=2.5–3% plus 0.5% for a single reference. Approved recreational books only. These are explicit conservative price-comparison rules, not proven betting value. All snapshot quotes were approximately 7.7 hours old: ZERO fresh-five-minute rows and ZERO qualifying price candidates.

## Snapshot census, not performance/backtest evidence

Default scope is the FULL FOOTBALL WEEK, not just today's date. On Today (ET) specifically: NFL has zero remaining entries; NCAA has 13 entries from one game, Penn State@Northwestern. Its leading two entries are Over 45.5 and Over 45: redundant direction/market, different contracts. A short-favorite pattern is structural and observed in the weekly pool, not inevitable in every day's slate.

| Weekly default cohort | Contracts | Negative model return | Repeated directional-family rows | Champion top10 price < -300 | Champion top10 plus money |
| --- | ---: | ---: | ---: | ---: | ---: |
| NFL combined | 1,836 | 1,355 | 74 | 6 | 0 |
| NFL props | 1,692 | 1,261 | 0 | 6 | 0 |
| NFL games | 144 | 94 | 74 | 1 | 1 |
| NCAA games | 544 | 342 | 311 | 2 | 0 |

NFL top3: Isaiah Davis receiving Under 24.5, -488, p=.9980; Braelon Allen receiving Under 24.5, -400, p=.9811; Josh Downs rushing Under .5, -425, p=.9778. These very high estimates are NOT established accuracy. Top10 are six receiving/four rushing props, eight estimates >=90%, six games, seven Novig/three bet365 quotes. Books reflect best-available payout/coverage, not proven book bias. Unequal market inventory and comparable-but-unvalidated probability estimates disadvantage game markets in the combined view.

NCAA top3: Texas Tech moneyline -500, p=.8094, estimated return -1.39%; South Florida spread +2.5 -300, p=.7298, -2.69%; UTSA moneyline -500, p=.7253, -11.13%. High probability plainly does not imply model-positive expected return, let alone validated value.

Removing default price/prop-alternate protections exposes 3,691 NFL/560 NCAA contracts. All ten NFL leaders have p>=90% and prices shorter than -300; NCAA top10 have nine moneylines/nine prices shorter than -300. This is sensitivity analysis, not an implemented new default. Exact contracts deduplicate books; alternate lines can still repeat the same thesis. NCAA repeated-family rows are 311/544 (57.2%); their outcomes are neither equivalent nor independent. No confidence interval for a deterministic single-snapshot census or causal sportsbook conclusion.

## Fixed offline Challengers

Protocol saved before evaluation; no fitted weights, chosen favorable weights, Score/100, future outcomes or live calculation changes.

- **C1 expected-return order:** sort the IDENTICAL Champion-eligible pool by pWin*decimal+pPush-1; exact ties preserve Champion order. Includes legitimate available payout and returned stake. It measures a theoretical expectation given the original, potentially miscalibrated probability. It does not establish edge. NFL top10: zero prices below -300, three plus-money, eight games; NCAA: zero below -300, two plus-money, eight games.
- **C2 directional-family-diversified C1:** take the first C1 entry per exact event/kind/player-or-game/market/direction, ignoring line/book. Reduces redundant attention rather than claiming correlation or equivalent outcomes. NFL combined 1,836 ->1,762; NCAA 544 ->233. NCAA top10 changes from eight games/eight families to ten games/ten families. NFL default prop families already unique; no benefit there. Different lines remain distinct for settlement and evaluation.

C1 NFL lead candidates: Foster Moreau receiving Over 9.5 -115, David Montgomery rushing Under 59.5 -245, Eric Saubert First TD +6000. The latter has an experimental estimate ~2.05%; small longshot probability errors magnify estimated return. Both Challengers' highest returns sit just below the existing 25% review ceiling. More attractive-looking output is NOT superiority.

Price/freshness, provenance, current-season sample and reproducible directional redundancy are supportable diagnostics. Contract-specific uncertainty, calibrated model-market advantage and trustworthy cross-market quality weights are not sufficiently established for a universal composite. Evidence quality describes inputs, not accuracy. Same-book proportional de-vigging is a reference approximation, not true probability; favorite-longshot effects/method choice matter ([Clarke et al., 2017](https://www.sciencepg.com/article/10.11648/10026106)). Expected payoff is outcome-weighted payoff ([OpenStax](https://openstax.org/books/introductory-statistics-2e/pages/4-2-mean-or-expected-value-and-standard-deviation)).

## Chronological data feasibility and diagnostics

`public_tracker.json`: 5,168 predictions, 3,820 settlements, 1,458 later-price observations. Tracking started September 20. Model/quote/input hashes/timestamps exist, but only SELECTED best_model/all_projection cohorts are archived. Tracker's >=-500, positive gap/return and main-line/near-110 choices differ from Today. Complete contemporaneous eligible/rejected pools and policy ranks are missing. Therefore historical Champion-v-C1/C2 top-N Brier, ROI, CLV, ranking quality and superiority are **BLOCKED**, not zero or successful.

Selected-cohort diagnostic only: 3,082 best_model predictions; 1,292 lack a qualifying settled nonpush result; 1,790 usable records across 34 sport/market/policy/version cohorts. Require recorded inputs/quote <= observed < kickoff, valid provenance, published win/loss settlement afterward and by frozen cutoff. First exact contract per model cohort retained. Condition probability on nonpush pWin/(1-pPush). Early observed_at < September 26 UTC; later >= September 26. No fitting; later period is NOT certified untouched because prior audits may have accessed it. Revised history/validation files are not used to recreate old features/probabilities.

| Later selected LEGACY cohort | Contracts / games | Mean p / outcome frequency | Brier | Log loss |
| --- | --- | --- | ---: | ---: |
| NFL receiving yards | 122 /16 | .602 /.574 | .23875 | .67171 |
| NCAA spread | 11 /10 | .598 /.545 | .24313 | .67870 |
| NCAA total | 11 /10 | .610 /.636 | .25744 | .71049 |

These contract-weighted diagnostics are NOT evidence for current production ranking or current 80/20 policy. Current `board-research-3` receiving diagnostic has 18 contracts from ONE game; 16 paired frozen references yield model-minus-reference Brier +.00224, no interval/inference with <10 games. Current NCAA spread/total each have ONE settled game. There is no adequate independent sample to establish current calibration or rank-policy improvement. Only paired differences use equal-game weighting and deterministic 1,000-resample cluster percentile intervals; none of the actual paired cohorts has ten games. Probability evaluation uses proper scoring rules rather than hit rate ([Gneiting & Raftery, 2007](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)).

Frozen prices and published outcomes exist, but no full ranking-policy pool, verified wager execution/book-specific void handling or guaranteed final closing prices. Do not apply today's prices retroactively or claim realized ranking ROI/CLV. Later scheduled exact-contract/book quotes are later samples, not automatically a final close.

## Product conclusion and next experiment

Current page is mostly honest: Order explicitly says highest estimated win chance, not Score or established value; lead is a research candidate, not a ticket suggestion. Generic `Sort: GOING rank` remains ambiguous; `Estimated chance (default)` would clarify without altering calculations. No wording change implemented this session. Separate clearly defined likelihood research and fresh price-comparison views are better supported today than an invented universal 'best bet' score. An overall ranking remains an unvalidated research question, not rejected by this census.

Highest-value next experiment: freeze complete daily eligible pools and exclusions BEFORE outcomes using existing/free snapshots, with sport/game/player/market/side/line/book, quote/freeze/kickoff timestamps, win/push probabilities, price/two-sided reference, sample/current-season evidence, version/source hashes and all three policy ranks/top3/top10. Preserve pool and predictions append-only; append trustworthy settlements/closing observations separately. Deduplicate repeated cycle snapshots for inference and retain contract identity across thresholds.

Before collection/evaluation, preregister exact snapshot cutoff, earlier diagnostic vs untouched later blocks, game/slate cluster unit, market/sport cohorts, missing-price handling, sample/precision targets and promotion thresholds. Compare IDENTICAL eligible slates, proper scores/reliability plus top-N concentration/price behavior; market benchmark only on matched references. No tuning on heldout outcomes; no universal metrics for Score. This session does NOT implement collection or declare an arbitrary adequate sample. Existing script/config changes that invoke credentialed providers remain cost-gated. Promotion still needs Travis approval.

## Verification and state

18 offline research tests pass (payoff/push math, ties, no mutation/Score, exact family identity, quotes/inputs/profile/settlement chronology, first frozen records, invalid probabilities, cohort splits, proper scores and correlated game bootstrap). Two corrected exact-source replays are byte-identical; SHA256 `531bfc8e49e1f83db3d90bafae2ba8ea4e52c484379b68fee6be81dbafad0b08`. Results store protocol and public source hashes. Production baseline checks: Node219/219, Python96/96, npm build and Vercel build pass; existing shared-asset warnings only. No real provider, alert, private-input, paid or production calls. No application/model changes; no deployment or rollback needed. Research files/trackers are local pending safe publication after a fresh explicit cycle, not silently reconciled. Automation unchanged.
