# Independent audit guide

Repository: https://github.com/daboli69/going-long (main).
Production: https://going-long.vercel.app/.
Guide written against application commit `1923249`; inspect your actual HEAD
because code and generated data continue to change.

## Get a reproducible checkout

```sh
git clone https://github.com/daboli69/going-long.git
cd going-long
git rev-parse HEAD
git status --short
```

Claude Code can inspect this checkout and its root `CLAUDE.md`. For a Claude
chat, provide the repository through the GitHub integration if available, or
attach a GitHub source ZIP. A URL alone does not guarantee that a chat session
has loaded every file. Ask the reviewer to state the files and revision it
actually inspected. The public source needs no production credentials.

## Code map

| Area | Start here |
| --- | --- |
| Hosting and route assembly | `vercel.json`, `scripts/build_vercel.mjs`, `hub/` |
| Football betting, draft board, trade analyzer | `index.html` |
| Private React journal and performance calculations | `apps/validation/src.jsx`, `apps/validation/metrics.mjs` |
| Server-side live odds and caches | `api/odds.mjs`, `server/parlay.mjs`, `config/parlay-markets.json` |
| Public snapshots and browser-safe Supabase configuration | `api/snapshot.mjs`, `api/yard-snapshot.mjs`, `api/validation-config.mjs` |
| Football projections and public PBP features | `scripts/build_pipeline.py`, `scripts/pbp_features.py`, `scripts/football_context.py` |
| Sharp-book benchmark and contract normalization | `scripts/topdown/model.py`, `scripts/topdown/feed.py` |
| Scanner, settlement, local storage and database delivery | `scripts/scan_markets.py`, `scripts/settle_markets.py`, `scripts/topdown/journal.py` |
| Official inactive extraction and T-75 warning | `scripts/topdown/inactives.py` |
| Windows worker and input refresh | `scripts/run_local_scanner.py` |
| Replay and chronological scoring tests | `scripts/backtest_topdown.py`, `scripts/backtest_nfl_context.py`, `scripts/export_replay.py` |
| Supabase schema, permissions and immutable records | `supabase/migrations/20260911_market_journal.sql` |
| Scheduled generated-data updates | `.github/workflows/`, `data/` |
| Baseball integration | `apps/yard/`; upstream https://github.com/daboli69/hr-board |

`docs/TOP_DOWN.md` and `docs/BETTING_MODEL.md` explain assumptions, not guarantees.
`docs/SIGNALS_PLAN.md` is a dated planning snapshot. The older draft setup section
of README is historical; it predates Vercel, server-side keys and Supabase.

## Local checks without production credentials

Use Python 3.12 and a Node version compatible with the committed lockfile.

```sh
npm ci
python -m venv .venv
# Activate .venv using the command appropriate to your shell.
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.cjs
node scripts/build_vercel.mjs
```

Review test source before execution. Dependency installation needs network
access; unit tests use fixtures/mocks and should not require private credentials.
Build output is disposable. Do not equate a passing test count with model
validation. Add independent counterexamples to the highest-risk assumptions.

`backtest_nfl_context.py` downloads public nflreadpy schedules. It measures
chronological score error, not ROI. Market replay needs real recorded decision
prices, official availability evidence, outcome timestamps and matched closing
quotes. Private replay inputs are intentionally absent from the public repo.
The smoke script sends a real labeled Discord test and writes a Supabase record;
it is not an ordinary offline test.

## Audit priorities

1. Check exact game/player/period/line identity, book aliases, stale and future
   timestamps, margin removal, fallback thresholds, probability discounts and
   stake calculations. Supporting book labels are policy designations.
2. Check official-list parsing against real page changes, incomplete lists,
   kickoff dates, late-game roundup updates, inactive player name matching,
   cache behavior, retries and warning deduplication. A public HTML parser is
   not a guaranteed official structured API.
3. Check chronological folds, historical input availability, selection
   deduplication, refunds/voids, closing-price joins, synthetic-test exclusion
   and separation of hypothetical stakes from actual bets.
4. Check database ownership and immutable-write rules against the migration.
   Public code cannot establish that production permissions match the SQL.
5. Check resource growth, pagination limits, sync backlogs, local outages,
   restart behavior and input freshness. The collector stops while the PC is
   asleep/offline; serverless hosting does not make it always-on.
6. Regression-check mobile routing, NCAA filtering, player props, fantasy drafts,
   the trade analyzer and baseball integration independently.

## Evidence boundaries

- `data/` contains generated observations of varying dates; inspect timestamps
  and source availability fields before calling any entry current or complete.
- nflreadpy/nflverse provide public football data; Savant extraction is separate.
  Public PBP does not supply every route, alignment or coaching identity metric.
- `.env.example` documents variable names only. `private/`, local credentials,
  SQLite journals, Supabase user records and Discord secrets are not audit
  artifacts to publish. Request a sanitized export if outcome evidence is needed.
- The repository does not demonstrate profitable returns merely because the
  pipeline runs. Distinguish implemented math, tested software behavior,
  historical score error and measured prospective betting results.

## Suggested audit request

> Audit daboli69/going-long at the current main commit. Read CLAUDE.md and
> docs/AUDIT_GUIDE.md, then independently inspect the code. Make no application
> changes and send no alerts. Prioritize correctness, time leakage, inactive
> clearance, odds matching, settlement, database access and operational failures.
> Give severity-ranked findings with file/line evidence and reproduction steps.
> State what you tested, what you could not verify, and which claims lack data.
