# GOING: audit and subscription launch roadmap

Audit date: September 12, 2026. Target: controlled paid launch for the 2027 baseball season. This is an assessment and proposed work sequence, not a claim of launch readiness or proven profitability.

## Product direction

One GOING account and interface, with Going Yard and Going Long as sport workspaces. Primary promise: identify prices worth investigating, explain the evidence, and show an honest record of the recommendations. Fantasy shares player research but stays a separate mode. Basketball follows a stable baseball/football foundation.

Common navigation: Today, Best Plays, Explore, Results, Account. Sport and Betting/Fantasy selectors keep the same location across workspaces. One type scale, spacing system, neutral background, orange action color, accessible focus treatment and reusable game/player cards. The marketing landing page explains the product; a returning signed-in user lands on their preferred slate.

## Verified current state

- The football repository contains the GOING hub, football single-file application, copied Yard frontend, React validation app and shared Vercel odds endpoints. Baseball ETL and its authoritative frontend live separately in hr-board. This duplication can drift.
- Yard's live public snapshot endpoints returned HTTP 200. The inspected slate contained 15 games and 270 players; the saved HR odds snapshot contained 120 entries. History contained 165 days. These counts prove availability, not accuracy or profit.
- Yard includes Statcast contact scoring, contact-gated hit estimates, pitcher strikeout distributions, game-run modeling, numerous contextual features, price comparisons and pick builders. It does not need another generic dashboard.
- Yard's homepage rendered at 390 and 1280 pixels without horizontal overflow or JavaScript errors. However, several competing navigation concepts and shorthand such as HEAT, BRL, ISO and IAA dominate the user journey. Estimated edges of +92%, +86% and +62% appeared during one live-page observation; exact price/probability provenance needs investigation, not an assumption that these are executable opportunities.
- Long now freezes prospective research and Best Plays and grades published results. It still depends on the owner's awake PC for continuous collection. Supabase is above its free storage quota. Existing user isolation and authentication are foundations, not a complete subscription system.

## Highest-priority findings

### P0: exact market identity before any value claim

Yard docs/index.html allPropEV (around line 8185) computes P(at least one hit), then prices fetchedPropFor('hit',name) without requiring its line to be 0.5. The HRR branch similarly assumes a 1.5 threshold. The shared adapter can choose a primary alternate line based on bookmaker coverage. This is a concrete contract-mismatch risk. The same check must cover Over versus Under, listed starter rules, doubleheaders, quote time and event start.

Build one typed quote/selection representation: event ID, player ID, sport, period, market, side, line, book, price, timestamp and settlement rules. A probability must identify the exact contract it prices. Test every market adapter against captured real provider examples. Quarantine extreme discrepancies for review instead of celebrating them automatically.

### P0: correct same-game parlay math

Yard genParlay/renderSGP (around lines 8480–8510) multiply leg probabilities and single prices even in same-game mode. Outcomes in one game move together; books also supply their own combined ticket price. Those products are not a validated same-game probability or an executable payout. Default to singles. Cross-game combinations may display an explicitly stated independence approximation. Same-game builds need joint game simulation plus an actual ticket quote before displaying value.

### P0: trustworthy historical records

etl/track.py _hr_map keys HR results by batter ID, while grade_date looks up player ID without game ID. Doubleheaders can combine two games into one result. Daily snapshots in etl/build_board.py are rewritten on repeated builds, omit game_pk in the player whitelist, and retain only 16 snapshots. They do not establish an immutable pregame betting ledger.

Use game ID + player ID, explicit participation and final status. Freeze each recommendation before its event starts with model version and quoted contract. Preserve failures, missing data and cancellations separately from losses. Keep outcome corrections as new records. Archive historical evidence under the applicable data license; do not quietly rewrite past recommendations.

### P1: consistent and defensible probabilities

Yard has different probability paths: hit_gated, interpolated historical tiers, fixed fallback anchors, hardcoded HIT_BADGE_LIFT factors, and calibrated HR rates multiplied by further adjustments. A calibrated base does not prove the adjusted result is calibrated. etl/hitmodel.py PitchShape.xba_on_contact actually uses observed hits / batted balls; its name can imply expected-contact data it is not using.

Centralize probability generation and label its source. Keep scores as scores. Fit adjustments only on earlier observations, evaluate on later dates, and compare each added feature against the same simpler baseline. Shrink short-window rates toward longer histories based on opportunities observed, with uncertainty shown. Statcast expected statistics describe contact quality; a gap alone is not a guaranteed future rebound.

### P1: remove known lookahead from validation claims

etl/backtest.py around line 1981 explicitly documents applying current-season FanGraphs pitcher aggregates to earlier starts. That branch is exploratory, not a clean historical performance claim. Preserve an as-of feature store and use chronological training, calibration and evaluation periods. Group evaluation by game/day, and retain a final untouched evaluation period. Measure pricing performance with frozen odds, not just whether higher-ranked hitters homered more often.

### P1: subscription boundaries and operations

Public static model JSON and unauthenticated data endpoints cannot enforce a meaningful paid entitlement. Introduce shared account/entitlement middleware and server-side authorization for premium responses. Use payment webhooks with deduplication, cancellation, failed-payment and refund handling; never trust a client-only paid flag. Test that one member cannot read another member's bets, preferences or notification destinations.

Replace the PC dependency with a scheduled persistent worker before accepting subscribers. Fetch once per provider/market and share cached results; do not make one upstream request per member. Retain raw polling locally or in controlled archival storage and keep the serving database compact. Add latency/freshness monitoring, feed failure alerts, backup/restore checks and cost accounting per active subscriber.

## What to add after correctness

1. A single Best Plays experience in both sports: Best Value, Highest Estimated Win Chance, and Watchlist. Each card shows exact bet, best price among the user's books, minimum acceptable price, estimated chance, uncertainty, kickoff/start time and two concrete reasons.
2. Changes that matter: lineup confirmation, batting-order promotion, starting pitcher replacement, starter workload changes and relevant bullpen availability. Reprice or withdraw affected recommendations automatically.
3. Price history with evidence: reference books, matched timestamps and how the offered payout compares. Treat thin HR markets differently from liquid game lines; reference coverage must be measured per market.
4. A unified results dashboard with separate all-model, published Best Plays and actual-bet cohorts. Track flat-stake results, forecast error and later-price comparisons without selecting only winning dates or markets.
5. Baseball opportunity modeling: distribution of plate appearances, pinch-hit/removal risk, starter versus bullpen exposure, and pitcher batters faced. Extend existing models rather than count the same contact-quality signal repeatedly under different badge names.

## Work sequence and acceptance gates

- September–October 2026: repair market/side/line joins, doubleheader grading and parlay claims; consolidate recommendation logging; establish a shared visual system and uniform navigation. Gate: no known contract mismatch, every published recommendation has a frozen record, stale markets visibly stop qualifying.
- November–December: evaluate model variants chronologically, centralize pricing functions, refactor large frontend/ETL files into tested modules, and conduct private usability testing. Gate: consistent probabilities across screens and reproducible historical results with data/version lineage.
- January–February 2027: build memberships, billing, onboarding, book preferences, notification controls and durable hosted workers. Confirm commercial data permissions and operating costs. Gate: isolated accounts, tested cancellation and restore flows, monitored feed failures, and no dependence on the owner's PC.
- 2027 preseason: invite-only beta using real upcoming slates. Validate availability, onboarding and recommendation withdrawal. Spring-training accuracy does not establish regular-season accuracy.
- Opening-season release: limited paid launch only if operational gates pass. Publish measured records and limitations; do not promise a profitable season or claim certainty from a few weeks.

## Commercial data gate

ParlayAPI's published terms distinguish public odds display and commercial/redistribution rights, require Business tier or higher for the described public odds-comparison use, and limit retention of line-level pricing beyond 90 days without written consent. Confirm the actual account agreement before pricing subscriptions or promising long-term odds archives. Free access to MLB/Savant/other sources does not itself establish commercial display rights; review each source and logo asset independently.

Sources:
- https://parlay-api.com/terms
- https://api.parlay-api.com/legal/acceptable-use
- https://supabase.com/docs/guides/deployment/going-into-prod
- https://baseballsavant.mlb.com/expected_statistics
- https://library.fangraphs.com/principles/sample-size/
- https://library.fangraphs.com/principles/regression/

## Immediate recommendation

Start with a pricing-and-grading correctness pass alongside the shared navigation/card design. More badges, longshot builders and basketball expansion come later. Choose subscription pricing after commercial feed costs and a retained-user beta are measured. A useful paid product needs trustworthy decisions and a clear record more than a larger feature count.

## Implementation log — September 13 continuation

Completed and pushed in separate increments:
- Shared GOING brand/header/navigation plus consistent research cards, controls and detail surfaces. Browser checks pass at 375, 430 and 1280 pixels across hub, football, baseball and results.
- Baseball hit/HRR pricing requires the model's exact supported line. Integer strikeout lines are excluded until refund probabilities are implemented. This does not yet solve every identity/freshness issue in the legacy adapter.
- Parlay Builder preserves the selected Under probability and label. Different-game research selects distinct known games. Same-game joint chance and all ticket payout/value claims are withheld without a supported combined model and ticket quote. Other baseball ticket-generation surfaces still require audit.
- Legacy baseball grading now scopes outcome maps by game/player and excludes ambiguous or absent participants. Existing history was not silently rewritten. Legacy daily files remain mutable and cannot prove pregame timing.
- New per-game research records are frozen before kickoff in snapshots/pregame. A separate official-final boxscore grader and Research record view show their results. These records currently hold scores, not exact frozen quotes/probabilities; they do not establish ROI or calibration. Initial result set is empty, accurately labeled.

Verification: five new JavaScript contract/parlay checks, five Python game-identity/pregame/final-grading checks, Vercel endpoint checks and production browser navigation checks pass. Prior integration jobs for the game-identity and freeze commits passed. The latest full integration job should be checked after completion.

Next work: audit all remaining ticket/price paths; ensure complete official outcomes and corrections remain retryable; add versioned exact prediction/price records with bounded storage; separate prospective validation from exploratory historical tests; remove known current-season lookahead before claiming calibrated performance. Continue UI consolidation without hiding missing evidence.


### September 13: automatic Fanatics Sunday research
- Removed pasted prices and manual player-status entry. The promo view recomputes automatically from existing fresh Fanatics ATD quotes and Going Long estimates, with three distinct games and the configured +2000 floor.
- Added a cached, free ESPN roster screen. Missing/stale rosters, non-active players, and any listed injury designation are excluded. This screen does not claim official inactive clearance; final scanner gates remain separate.
- Five ranked alternatives are a maximum, not an invented minimum. Missing combinations display an automatic waiting state. The feature adds no ParlayAPI polling.
- Verified all 32 live ESPN rosters; 41 targeted tests and the Vercel build passed. Full promo terms and final ticket prices still require sportsbook confirmation.
