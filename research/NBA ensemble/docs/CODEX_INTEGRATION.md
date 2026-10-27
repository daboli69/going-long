# Codex research package: local integration, 2026-10-27

Package: `updates/2026-10-27-dca2756e533d` (manifest SHA256 `dca2756e...e222`, matching the install receipt in `transfer-receipts/`). Handoff: `CLAUDE_HANDOFF.md` from Codex. The package files are unchanged; the app reaches them only through `nba_lab/codex_research.py`.

## How it is connected

- **Separate environment.** `updates/.../.venv-research` (Python 3.12.10, NumPy 2.5.4, Polars 2.1.0, scikit-learn 1.9.1). Codex recorded Polars 1.44.2; the newer version passed every test. Your app's `.venv` is untouched.
- **Separate process.** The adapter runs Codex's CLIs with that Python and the package folder as the working directory. Nothing is imported, so Codex's generic `scripts` package can't clash with anything here.
- **Today page.** The Forecast switch has a fourth option, "Codex winner research (6 different voters)": Elo, logistic, gradient boosting, random forest, naive Bayes and ridge margin, in the same per-model lean board.
- **Research & Calibration page.** A "Codex research package" expander shows file verification, a test button, the reproduced development replay and the King of the Court data audit.
- **Daily refresh (launcher option 2).** After the original and shadow forecasts, it runs a Codex forecast. A failure there is printed and skipped; it never stops the original forecasts.
- **CLI.** `python -m nba_lab.cli codex-verify`, `codex-tests`, `codex-forecast`.

## What was tested on this PC

| Check | Result |
|---|---|
| All 57 payload files vs manifest SHA256 | All match |
| Codex's own tests (11 winner, 24 KOTC, 13 diagnostics) | 48 passed |
| Winner fetch + development backtest, 2022-23 to 2024-25 | 3,125 forecasts; every Brier, log loss and accuracy figure matches the handoff exactly |
| KOTC fetch + ingest + audit, 2023-24 to 2026-27 | Accepted games 1,229 / 1,173 / 1,195 / 51 and every exclusion count match the handoff |
| KOTC synthetic demo, 20,000 draws | Runs; output is labelled synthetic |
| Live winner forecast through the adapter | Runs end to end; 0 games forecast (see below) |
| App: Codex board with fixture forecasts, empty-date message, research page | Render without errors |
| This app's test suite (incl. 3 new adapter/daily tests) | 89 passed |

## Why tonight shows no Codex forecasts

Codex's `predict` only covers games in the next 24 hours and needs at least 5 completed current-season games per team. On 2026-10-27 every team had 2 or 3, so all 4 games were excluded. Forecasts should start appearing in early November, once teams have played 5 games.

Its training also skips 2025-26, because that season is Codex's locked holdout. The fetch refuses it, so live training uses 2022-23 to 2024-25 plus the current season.

## Not runnable, by design or for lack of data

- **KOTC `simulate`, `freeze`, `select`, `settle`.** These need a complete pregame slate with independent field evidence and verified debut metadata, plus at least eight registered prospective slates. None exist yet. Building one from final box scores would break Codex's rules, so I didn't.
- **Distribution diagnostic `compare`.** It needs Codex's original `.cache/king-court-deepening` inputs, which weren't in the transfer.
- **FGA repair.** It stays inactive, as the handoff requires.
- **Participation and minutes study.** Written up by Codex, not implemented. This app already has one of the inputs it asks for: official injury-report PDFs for 2021-22 to 2025-26, parsed and timestamped (`docs/INJURY_REPORTS_AUDIT.md`).

Nothing here validates Codex's probabilities as recommendations. Its development replay is not a holdout test, and its ensemble doesn't beat its own logistic or ridge members.
