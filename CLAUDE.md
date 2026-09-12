# Going Long: audit entry point

Start with [docs/AUDIT_GUIDE.md](docs/AUDIT_GUIDE.md). This file is context for
Claude Code and other reviewers, not runtime application configuration.

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
