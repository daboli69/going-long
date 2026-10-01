# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Going Long: audit entry point

## Commands

Windows checkout; use `.venv/Scripts/python.exe` for Python. These mirror CI
(`.github/workflows/test.yml`: Node 22, Python 3.12):

```sh
npm ci
pip install -r scripts/requirements.txt
npm test                                   # node --test tests/*.test.cjs
python -m unittest discover -s tests -p 'test_*.py'
npm run build                              # scripts/build_static.py + vite build
node scripts/build_vercel.mjs              # Vercel output -> dist/vercel (disposable)
```

Single tests:
`node --test tests/betting.test.cjs`;
`python -m unittest tests.test_football_context` (or `...Class.test_name`).
`npm run dev` starts Vite. There is no linter configured.

## Architecture

- **Hosting**: Vercel serves a static bundle assembled by `scripts/build_vercel.mjs`
  (not the plain Vite output) plus `api/*.mjs` functions, which bundle `data/*.json`
  via `vercel.json` `includeFiles`. `api/snapshot.mjs` serves an allowlist of
  data snapshots; a new `data/*.json` the site needs must be added to that
  allowlist and covered by a test.
- **Frontends**: football board, draft board and trade analyzer are Vanilla JS in
  `index.html` (tests load it via jsdom). `apps/validation/` is a React/Vite app
  (private journal; metrics in `metrics.mjs`). `apps/yard/` is the baseball
  integration (separate upstream repo).
- **Data pipeline (Python, `scripts/`)**: `build_pipeline.py`, `pbp_features.py`
  and `football_context.py` produce projections/snapshots into `data/`.
  `.github/workflows/data.yml` refreshes `data/` twice daily on `main` only, so
  `data/` changes constantly and generation timestamps do not prove completeness.
- **Scanner (`scripts/topdown/`)**: `feed.py` normalizes odds contracts, `model.py`
  builds the sharp-book benchmark, `inactives.py` parses official inactives,
  `journal.py` stores to local SQLite and Supabase. `scan_markets.py` and
  `settle_markets.py` drive it; `run_local_scanner.py` is the long-running worker
  on the owner's Windows PC, **not** deployed by Vercel.
- **Database**: `supabase/migrations/20260911_market_journal.sql` defines
  ownership and immutable-write rules.
- Detailed code map: `docs/AUDIT_GUIDE.md`. Assumptions: `docs/TOP_DOWN.md`,
  `docs/BETTING_MODEL.md`.

## Roles and rules

- **Codex is the primary developer. Claude is the independent reviewer and
  progress reporter.** Do not modify application code unless Travis asks.
- Football (NFL/NCAA) is primary; baseball (Going Yard) is regression-only;
  basketball is off limits until the owner authorizes it.
- Model experiments follow the Champion/Challenger gate in `MODEL_RESEARCH.md`;
  no promotion without chronological out-of-sample evidence.
- Work on `codex/` branches; no pushes to main, deployments, migrations or force
  pushes without asking.
- Never enable paid APIs, extra credits, or paid services ($0 additional spend).

## Reviews

- Read `PROGRESS.md` and `MODEL_RESEARCH.md` first. Open other files or diffs
  only when needed; do not repeatedly scan the repo.
- Keep reports short, in this order: Completed, Model Research, Concerns, Next,
  Needs Travis.
- Challenge unsupported model claims, overfitting, data leakage, questionable
  data, and risky changes.

## Usage budget

- Minimize token usage.
- Reserve at least 25% of Travis's Claude usage for school. Stop GOING work
  around 30% remaining.

# Audit entry point

Start with [docs/AUDIT_GUIDE.md](docs/AUDIT_GUIDE.md) for full audits only. This
file is context for Claude Code and other reviewers, not runtime configuration.

When asked to audit, inspect the current checkout and report findings before
editing code. Record the commit SHA. Treat existing documentation, model claims,
and passing tests as claims to verify, not proof of correctness or profitability.

Focus on reproducible defects, quantitative assumptions, data provenance,
time leakage, settlement rules, authentication, secrets, and operational failure
paths. Report severity, file/line references, a concrete failure scenario, and
the smallest useful fix. Distinguish verified defects from questions that need
live evidence. Report gaps even if an existing comment calls them intentional.

Do not run scanners with `--send`, `scripts/smoke_alerts.py`, database migrations,
or production mutations as part of a read-only audit. They have real external
effects. An explicit user request can authorize separate integration testing.
Use mocks for ordinary tests. Do not request or disclose service keys, webhook
URLs, passwords, or the contents of excluded `private/` files.

The football board remains Vanilla JS in `index.html`; the private validation
journal is React in `apps/validation/`. Vercel hosts the website and API routes.
The continuous Python scanner runs separately on the owner's Windows PC.
There is no assumption that a Vercel deployment restarts that worker.

Never invent missing historical odds, outcomes, probabilities, measured returns,
or a validation percentage. A scoring-error backtest is not a betting-return
backtest. Public feed availability and existing policy thresholds do not prove
that a strategy is profitable.
