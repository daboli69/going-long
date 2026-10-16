# FantasyPoints local session handoff (E13 separation, E14 QB pressure)

Written 2026-10-15 from the owner's PC. Credential-free; aggregates only. No model promoted, nothing deployed or merged.

## Branch and commit
- Branch `codex/fantasypoints-experiments`, cut from `origin/claude/going-missions-sharp-intelligence-aj31dh` (10539c9, which holds the integration map on top of main b129bb5).
- Tested commit: the branch tip at push time (`git rev-parse origin/codex/fantasypoints-experiments`); the cloud session should record that SHA.

## Data verification (real files, read-only)
- 341 CSVs under `FantasyPoints/` (runtime copies excluded); only **198 are unique by SHA-256**. 137 groups are byte-identical copies (every `Inbox/` export is also in `raw/`; `raw/inbox-autoload` repeats more). Count unique files, not 341.
- Independent evidence: `raw/{2021..2025}/full-season` (season totals), `raw/{2021..2025}/by-game` (weekly panel), `raw/2026/through-week-04` plus 2026 by-game. Past-season full-season files contain end-of-season values and are never Week-N information inside their own season.
- Gaps: separation tables exist only for 2022-2026 (none for 2021); `run_pass_report_weekly` is missing for 2024; `passing_basic` only 2025; 2026 snaps, line matchups and QB/WR coverage matchups exist only for through-week-04; outcomes JSON 2026 weeks 1-3.
- Missingness is structural, not random: team run/pass report 66% empty cells, passing advanced/depth 37-42% (2026: ~50%), coverage matrix 35%. Weekly receiving tables are ~1% empty.
- The "Player Details" name is not a unique key: 1-82 repeated names per table (multi-team seasons, name collisions). The loader keys on resolved gsis id and drops unresolvable duplicates; do not join on name.
- Odds index (`index.sqlite3`, opened read-only): tables control 4, pulls 500, quotes 361,802; ten books, 2024-09-05 to 2026-10-12; `summary.json` agrees. Per the existing archive doc it has no closing-line series, so it can score against a pregame price only. **No matched-price comparison was run in this session.**

## Changes
- `scripts/trend_research/experiments13.py` (new): E13 and E14, wired into `scripts/trend_research.py`.
- `research/trend-intelligence/ledger.json`: both specs pre-registered (hashes `cc9f6d76e293`, `f0209ba51842`) before any outcome was read, then run once.
- `tests/test_trend_e13_e14.py` (new) and a one-line spec-collection update in `tests/test_trend_research.py`.

## Results (prior season -> next season, rolling origin, fixed ridge, player-clustered bootstrap)
| Experiment | Test | Baseline MAE | With block | Relative change | CI of MAE delta | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| E13 receiving yds/g, WR/TE, n=408 (2 test seasons) | Separation overall | 10.508 | 10.629 | -1.2% | [-0.08, 0.32] | REJECTED (0/2 seasons better) |
| E13 | Separation vs man/zone | 10.508 | 10.687 | -1.7% | [-0.10, 0.47] | REJECTED (0/2) |
| E14 passing yds/g, QB, n=78 (3 test seasons) | Pressure / TTT / sack % | 26.79 | 27.89 | -4.1% | [-0.82, 3.08] | REJECTED under the first-wave rule, but the CI is wide |
| E14 (descriptive, not primary) | CPOE, aDOT, deep % | 26.79 | 25.53 | +4.7% | [-3.57, 0.94] | INCONCLUSIVE |

Baselines already contain the player's own per-game targets/receptions/yards (E13 also routes per game and TPRR; E14 attempts, yards, TDs). Reading: separation and QB pressure add nothing measurable beyond last season's own production. E14 has 78 pairs, so it cannot exclude a modest effect; treat as "no evidence", not "disproved". No test is a betting-return or CLV result.

## Tests performed
- `python -m unittest discover -s tests -p 'test_*.py'` in the worktree: OK (5 existing skips). The E13/E14 tests check frozen spec hashes, aggregate-only ledger, CLI wiring and the same-season leakage guard.
- Node tests and builds were not rerun (no JS changed).

## Private data dependencies
- `FantasyPoints/` (licensed CSV/JSON archive and `research/cache/` nflverse caches) and `%LOCALAPPDATA%/GOING/private/odds-history/`. Run with `--root <FantasyPoints>`. Neither is in Git: `FantasyPoints/` and `StatApi/` were added to the local `.git/info/exclude`; **they are not in the repo `.gitignore`, so consider adding them**.

## Limitations
- Two test seasons for separation (tables start 2022); small QB sample; season-level only, so no in-season point-in-time claim.
- Not run: weekly point-in-time TD role features (2026 inside-5/10/20 snaps exist only for 4 weeks), pace/PROE vs game lines, odds-archive matched-price test. These need the owner's go-ahead and more data.
- First-wave rule used for E13/E14 (consistent with E1-E5), so REJECTED means "below 0.25% gain", not a proof of zero effect.

## Reproduce without local files
1. `git checkout codex/fantasypoints-experiments && python -m unittest tests.test_trend_e13_e14 tests.test_trend_research` verifies the frozen specs and the committed aggregate results with no data.
2. `research/trend-intelligence/ledger.json` entries E13/E14 hold the exact specs and result numbers above.
3. Re-running the experiments requires the local archive (`python scripts/trend_research.py --root <FantasyPoints> run E13 E14`); a cloud session cannot, by design.
