# Market-led engine: implementation and operating limits

## Current repository audit
Going Long remains a single-file vanilla-JS football application with NFL/NCAA game lines, NFL props, a draft room and trade analyzer. `scripts/build_pipeline.py` publishes appearance-aware distributions; the existing browser computes projection-based returns and bankroll suggestions. Those are secondary research, not a replacement for the new price-led eligibility gates. `api/odds.mjs` keeps Parlay credentials server-side; `api/snapshot.mjs` serves allowlisted data. GOING now hosts `/long/`, `/yard/` and the isolated React `/validation/` application on one Vercel origin.

## Verified sources (September 11–12, 2026)
- The requested repository redirects to https://github.com/thadhutch/sports-quant . Its NFL process uses PFF Premium and PFR scraping, with walk-forward training. We inspected `src/sports_quant/modeling/backtest.py`; we did not copy premium-source scraping, accuracy claims, or trained models. Date-ordered evaluation is useful; historical accuracy does not establish profitable prices.
- https://nflsavant.com/about links public bulk files through 2025. `pbp-2026.csv` returned 404. The actual `/api/league?season=2026` endpoint returned four team rows and week 1; `/api/seasons` includes 2026. `extract_savant.py` ingests the live season API and falls back explicitly to nflreadpy for raw 2026 plays (323 rows at verification). A missing charting field is not a zero rate. Savant is also built from nflreadpy/nflfastR, so it is not independent confirming evidence.
- https://parlay-api.com/docs documents direct game/prop prices and historical/streaming options. Our authenticated scan observed Pinnacle, not Circa. Neither traded volume, bookmaker limits nor bettor identity is supplied by the selected endpoints. We label price disagreement and reference movement, never infer emotional/public money or liquidity from price alone.
- NFL inactive lists are delivered around 90 minutes before kickoff: https://operations.nfl.com/gameday/pre-game/countdown-to-kickoff . A timer is not proof the reports arrived. No verified free machine-readable official inactive feed was found. An operator-reviewed official nfl.com document is presently required for each team. The registration command stores the source, publication time, review time, complete player list and fetched content hash.
- Dixon–Coles concerns association football (soccer), not NFL point scoring: https://www.research.lancs.ac.uk/portal/en/publications/modelling-association-football-scores-and-inefficiencies-in-the-football-betting-market(d16276a2-d6e0-483b-a708-1d29663f1992).html . It is deliberately not applied to NFL points. A compound 7-point touchdown/3-point field-goal Poisson utility is provided as an explicitly incomplete secondary check; it omits PAT variation, safeties and scoring dependence.
- Official implementation references: https://supabase.com/docs/guides/database/postgres/row-level-security ; https://react.dev/learn/build-a-react-app-from-scratch ; https://core.telegram.org/bots/api#sendmessage ; https://docs.discord.com/developers/resources/webhook#execute-webhook .

## Decision math and evidence policy
`topdown/model.py` compares the exact event, contract, line and side at recreational books against Pinnacle/Circa pairs. It removes each reference book's margin separately using proportional and power assumptions. The raw benchmark is the middle reference estimate. The selection probability uses the more conservative margin-removal estimate, minus a disclosed 1-point policy discount and any earned historical overprediction penalty. It is an estimate, never a known true probability.

Defaults: two designated reference books; quotes no older than 180 seconds; cross-book times within 60 seconds; reference disagreement at most 3 percentage points; estimated repeat return at least 3%. Integer lines and two-way moneylines stay non-actionable without a refund model. These are policy cutoffs, not fitted confidence levels. Half-point full-game totals/spreads and supported player props are normalized; first-TD and period markets are outside this new benchmark adapter until their settlement rules and reference coverage are verified. Existing display ingestion is unchanged.

Eligibility additionally requires both reviewed inactive reports inside the final 90 minutes and a kickoff still in the future. A listed inactive player is blocked. `return = probability × decimal payout − 1`. Suggested research stake uses one-quarter of the bankroll formula, capped at 1% of the configured bankroll; blocked checks receive zero. No wager is executed.

Secondary venue scoring uses 40% current season / 60% last four venue games, then a league-centered normal/normal posterior. Prior weight is eight games during weeks 1–4 and four afterward. Overlapping windows do not become extra sample size. Before any current venue game, the estimate is exactly the league prior. A total more than 14 points from this simple check is quarantined for review. These assumptions are not a fitted NFL scoring distribution.

The feedback penalty uses only already-settled, prospective eligible selections, deduplicated by event/contract/side. It needs 50 selections across 20 games, uses 100 reference pseudo-observations, and can only subtract probability (maximum five points). It never automatically inflates a model after a winning streak. Model version and original forecast stay frozen.

## Durable logging / Supabase
Run `supabase/migrations/20260911_market_journal.sql` in the existing project SQL editor. It creates:
- `market_journal`: append-only owner-scoped quote, prediction, report, reference, near-kickoff observation, settlement, run, arbitrage and notification records. Forecast payloads store book, American/decimal odds, raw and discounted probability, odds band, suggested stake, reasons, model version and every relevant timestamp.
- `placed_bets`: actual accepted stake, decimal price and placement time, separate from hypothetical validation stakes. Insert/select policies require the authenticated owner; clients cannot rewrite predictions or historical tickets.

The scanner first writes an excluded `private/topdown.sqlite` journal, then syncs to Supabase. Delivery outages retain local records. Non-quote records have sync priority. Only the server service role writes journal records. React signs in with Supabase Auth and reads through row-level security. Never place the service-role secret in a client environment variable.

Server/scanner variables: `PARLAY_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GOING_OWNER_ID` (the sole Supabase Auth user's UUID). Vercel additionally needs `SUPABASE_PUBLISHABLE_KEY`, which is public by design. The project and credentials were not provided; live database integration is not claimed as tested.

## Scanner and notifications
Install `scripts/requirements.txt`. On a persistent host:

```powershell
python scripts/extract_savant.py
python scripts/scan_markets.py --once
python scripts/scan_markets.py --interval 60 --send
```

Use one alert destination: `DISCORD_WEBHOOK_URL`, or `TELEGRAM_BOT_TOKEN` plus `TELEGRAM_CHAT_ID`. These must be secrets on the scanner host. `--send` is required to transmit. Logs avoid secret-bearing request URLs. Alerts are deduplicated durably; a transport timeout can leave delivery uncertain, so exactly-once external delivery is not promised.

Before an actionable run, use `scripts/register_inactives.py --help` and verify both teams' real official reports. It creates `private/inactives.json` (or `INACTIVES_FILE`). Do not fabricate confirmations to make a timer pass. Until an official report adapter is verified, this is a manual dependency, not fully automatic inactives ingestion.

This is a polling collector, not exchange tick data. The default is one scan per 60 seconds, plus request latency, and it consumes provider credits. A Vercel request cannot host an endless Python loop. The collector must run as a persistent process/service; no such host was configured or left running here. The UI reports a scan as stale after five minutes. Scheduled GitHub model refreshes are not claimed to provide instant alerts.

Displayed-price arbitrage requires complementary exact contracts, different books, synchronized timestamps and an estimated margin above 0.5%. Stakes are apportioned by inverse payout. Limits, simultaneous acceptance, injury/void differences and withdrawal costs remain unverified; alerts call these candidates, not guaranteed profit. There is no market-volume or public-betting signal without its required data.

## Validation UI and settlement
`apps/validation/src.jsx` is the complete React app, built with Vite into the Vercel static output. It provides private sign-in, scanner readiness, search, review windows, per-band $100 flat-stake results, forecast error, matched near-kickoff reference comparisons, journal export and actual-bet entry. No backend connection means an explicit setup state, not invented example bets.

`settle_markets.py` uses published final games and appearance-aware player logs. Missing appearances remain unresolved; book-specific injury and void exceptions need reconciliation. Hypothetical $100 analysis includes returned stakes as zero profit and deduplicates repeated scans. Actual tickets are separate. No automatic calibrated badge is granted.

Future closing prices never enter the original decision. A same-contract sharp observation within ten minutes of kickoff is labeled a near-kickoff sample, not necessarily the actual last market price. Getting a better price than that later benchmark is complementary evidence to realized returns; neither proves a causal advantage across a few games.

## Activation still needed
Supabase project migration/owner account/secrets; Telegram or Discord destination credentials; a persistent collector host; verified official inactive reports. Circa was absent in the observed feed, so the default two-book gate also blocks action when only Pinnacle is available. Do not relabel a recreational book to satisfy it.
