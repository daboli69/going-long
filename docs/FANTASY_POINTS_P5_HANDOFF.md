# FantasyPoints P5: weekly TD, pace/totals, real-archive audit and prospective shadow (local session handoff)

Written 2026-10-16 UTC from the owner's PC. Credential-free; aggregates only. No model promoted, nothing merged or deployed, no paid request.
Branch `codex/fantasypoints-td-pace-shadow`, cut from the reviewed `claude/going-missions-sharp-intelligence-aj31dh` tip `b9f94a7`. Tested commit: see the last section.

## Process
- Protocols P5-1/P5-2/P5-3 were committed and ledger-registered in `be73f37` **before any runner existed** (`scripts/trend_research/protocol_p5.py`). Runners and results are in later commits.
- Disclosed: before registration I had opened the archive summary, counted exported records and read the exporter. No model-vs-market or FP-vs-outcome score had been computed.
- 2021-2025 are previously inspected development evidence (E1-E14, P3-x, JP-x, P4-1). Nothing here is an untouched holdout. The original E13/E14 registrations and verdicts are unchanged (a test checks this); the reviewer's v2-rule reading of E14 remains a separate description.

## P5-1 weekly end-zone / inside-20 target TD role (anytime TD): INCONCLUSIVE
Data that exists: `receiving_advanced_weekly` EZTGT, EZTD and i20 TGT for 2021-2025 (2026 through Week 4). Historical goal-line **carries** do not exist (rushing i5 is a share, not a count; 2026 inside-5/10/20 snaps are 2026-only), so none were used.
Population: the JP-2 population restricted to rows with at least one FP receiving row in the prior 6 rows, identical rows for every model. **Coverage loss: RBs are almost absent from the FP weekly receiving panel** (RB rows kept per season: 0, 0, 1, 11, 7 against about 1,470 lost), so the test is effectively WR/TE. Holdout n=4,096 (366 players); validation n=4,046 (356).

| Holdout 2025 | log loss | Brier | calibration slope |
| --- | --- | --- | --- |
| B0 Champion v2 (uncalibrated) | 0.4126 | 0.1223 | 0.50 |
| B0c recalibrated Champion | 0.3928 | 0.1200 | 1.07 |
| B1c TD frequency | 0.3913 | 0.1195 | 1.05 |
| B2c free inside-20 / inside-5 volume | 0.3834 | 0.1175 | 1.08 |
| BF all free JP-2 blocks | 0.3767 | 0.1160 | 1.09 |
| M1 = B0c + FP end-zone | 0.3847 | 0.1178 | 1.09 |
| M2 = BF + FP end-zone | 0.3769 | 0.1160 | 1.08 |

Primary comparisons (Bonferroni over 2, player-clustered): M1 vs B0c holdout gain +0.0081 nats (adjusted CI 0.0045 to 0.0120), which alone would be ACCEPT_FOR_SHADOW. M2 vs BF is -0.0002 (adjusted CI -0.0007 to 0.0003): REJECT. Overall INCONCLUSIVE by the frozen rule.
Reading: the FP labels help only because they re-measure scoring-zone volume that the free play-by-play blocks already hold. M1 vs B2c is -0.0013, and the single feature `fp_i20tgt12` gives +0.0079 vs B0c, the same size as the free rz_tgt12. No TD shadow capture was built for P5-1 because no FP TD feature earns shadow status. Goal-line carries remain a prospective-only feature.

## P5-2 pace and totals vs matched pregame totals: INCONCLUSIVE
Archive total records: 2024 280, 2025 283, 2026 79; 25 did not match the regular-season schedule (postseason). Features are same-season only and need at least 3 prior games.
Coverage: 2024 has **0 of 267** usable records with FP pace (no `run_pass_report_weekly` export for 2024; nothing imputed, no season totals, no cross-season borrowing). 2025: 223 of 271. 2026: 31 of 79 (Weeks 1-3 lack priors). Common FP-eligible rows n=254 (223 + 31). Development games 2021-2023: 671. Every forecast asOf precedes its snapshot (minimum 88 h, median 163 h).

| Brier gain vs the equal-weight de-vigged pregame market (254 games, market Brier 0.2494) | gain | 95% game-clustered CI | relative |
| --- | --- | --- | --- |
| C_FP (FP pace) | +0.0002 | -0.0039 to +0.0039 | +0.08% |
| B_NFL (public pace) | -0.0004 | -0.0034 to +0.0023 | -0.16% |
| B_PTS (recent scoring) | -0.0006 | -0.0022 to +0.0010 | -0.24% |
| CH_RAW (raw Champion trailing average) | -0.0102 | -0.0231 to +0.0025 | -4.1% |
| C_FP vs B_NFL (beyond public pace) | +0.0006 | -0.0020 to +0.0032 | +0.24% |

C_FP is better in 2026 Weeks 1-5 (+0.0045, n=31) and worse in 2025 (-0.0004, n=223), so it fails the both-periods condition, and the interval is too wide to reject a 0.5% gain. 2024 without FP pace: B_NFL +0.0008, B_PTS +0.0001 (n=219, intervals include 0). The production Champion (market-anchored) equals the market by construction; the raw Champion is worse than the market, as the earlier audit found. The model's probabilities sit near the market because the line carries the information.

## P5-3 real-archive game-line audit and comparison: FAIL on the frozen criterion, zero data violations
`scripts/archive_game_line_audit.py` re-derives from the raw index: 1,925 records, 649 games, 15,254 book pairs, all reproduced from raw quotes (side, line, price). Only h2h/spreads/totals were requested (no period or alternate market). One decision snapshot per game. `quote_at <= snapshot_at < actual kickoff` for all 30,508 quotes. Snapshot 4.4 to 34.4 minutes (median 34.4) before the actual kickoff; quotes 4.5 to 48 minutes. Implied-probability sums 1.010 to 1.070 (none crossed). Schedule kickoffs equal nflverse kickoffs. Outcomes recomputed from scores match.
**Status is FAIL only because 15 Week-5 2026 games (2.3%, above the 1% limit) have no independent nflverse score:** the cached public `games.csv` predates Week 5 (cached 2026-10-08). I did not download a refreshed file without your approval. Refreshing that free public cache and rerunning `run P5-3` should clear it.
Timestamp semantics stay distinct: snapshot_at (provider board), quote_at (bookmaker update), forecast asOf (kickoff of the latest prior game used + 4 h), feature availability (end of that game). The FP archive `known_at` stamp is retrospective (2026-10-08), so historical availability is assumed, not observed.
The implemented comparison on real records (walk-forward, Brier, equal vs research vs learned): moneyline 518, spread 509, total 514 scored records; differences vs equal are within about 0.0002 and intervals span 0. No CLV claim (no closing series).
**Defect found and fixed:** the learned-weights step overflowed to NaN when a vanishing-weight source was the only one on a board, so the spread comparison returned "no fold" and the total comparison silently lost a fold (384 scored, now 514). `shared/market-validation.js` `learnWeights` now stops the update before it leaves the simplex; the regression test in `tests/missions-history.test.cjs` fails on the old code.

## Prospective shadow pipeline (`scripts/fp_shadow.py`)
Captures the P5-2 forecasts (CH_RAW, B_PTS, B_NFL, C_FP) plus the matched market price for unstarted 2026 Weeks 6-10 games.
- Write-once (exclusive create, read-only file), hash-chained ledger, real wall-clock capture time (`--now` only with `--dry-run`).
- Refuses games within 30 minutes of kickoff, a market board older than 6 hours, and any directory inside the repository.
- Records source hashes, per-source feature cutoffs, code SHA, protocol spec hash and exclusions. `settle` adds outcomes in separate files; `score`, `verify` and `receipt` (hashes and timestamps only) are included. 13 failure-safety tests.

**Current status: nothing is captured yet.** A dry run at 2026-10-16 00:14Z found 27 capturable games (Weeks 6-7), but the newest board on `origin/main` was generated 2026-10-15 15:03Z (9 h old), so the 6 h rule excludes them. Weeks 8-10 have no posted totals. The Thursday game was inside the lead window. Run `scripts/run_fp_shadow_capture.cmd` right after a data refresh. It is not scheduled; a scheduled task is yours to approve. The matched market in shadow is the single-provider consensus board (proportional de-vig), not the multi-book archive board.
Untouched outcomes: only 2026 games whose kickoff is after their capture time. 2026 Weeks 1-5 results were read by the P5-2 evaluation and are inspected.

## Private data dependencies and cloud reproduction
Private (not in Git): `FantasyPoints/` including `research/cache`, `%LOCALAPPDATA%/GOING/private/odds-history/`, the derived `odds-history-derived/` (export, market probabilities, forecasts) and `fp-shadow/`.
Local commands:
- `python scripts/missions_history_export.py --out <derived>/missions-input.json`
- `node scripts/archive_market_probs.cjs <derived>/missions-input.json <derived>/market-probs.json`
- `python scripts/trend_research.py --root <FantasyPoints> run P5-1 P5-2 P5-3`
- `python scripts/archive_game_line_audit.py --root <odds-history> --games <FantasyPoints>/research/cache/games.csv`

Cloud reproduction without local files: `tests/test_p5_experiments.py`, `tests/test_fp_shadow.py` and the node regression test verify the frozen spec hashes, aggregate-only results, the 2024 gap accounting, the lag and leakage logic, write-once and late-forecast refusal, and the audit on a synthetic archive. `research/trend-intelligence/ledger.json` entries P5-1, P5-2 and P5-3 hold the aggregates quoted here.

## Limitations
Small samples (254 games; WR/TE only for TD). No historical player-prop prices. One pregame board per game and no closing line. The P5-3 frozen criterion is unmet until the public score cache is refreshed.
Feature definition clarification: `pts6` is the expected total (the two teams' mean points scored and allowed, halved) minus the line, and evaluation offsets use the archive line. The spec wording was ambiguous; ridge models are scale-invariant, only the CH_RAW comparator depends on it.

## Tested commit
All results above were produced and tested at `204379da6003fd18d2c0848110d414d69f9a175c`: `python -m unittest discover -s tests -p 'test_*.py'` 697 tests OK (5 existing skips), `npm test` 909 of 909 pass, `npm run build` and `node scripts/build_vercel.mjs` exit 0 (`npm ci` and the repository's declared Python requirements only). The commit that adds this section changes this document only.
Environment notes: the Windows worktree needed LF line endings (CI is Linux) for one workflow-text test; and my earlier local `.git/info/exclude` entries `FantasyPoints/` and `StatApi/` were unanchored and broke the reviewer's case-insensitive StatApi ignore test, so they are now anchored.
