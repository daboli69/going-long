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

### P5-2 data correction (documented, not a tuning opportunity)
Rerun unchanged on 2026-10-16 after the public `games.csv` refresh. Input hashes: before `65a36db5f65c8de72a887bc1d76514d02fe70fb8c293a05e3b123903604a5d35`, after `1e6d4929896fb85e99375fec0ea9b182b92c0779cb9f37047fef2c1fe8a271de`. 40 rows changed, all 2026 Weeks 5-7 (15, 14, 11), none in 2025 or earlier. **Sample sizes and every metric are identical** (leaf-by-leaf comparison, tolerance 1e-12; verdict INCONCLUSIVE both times) because the evaluation games are 2026 Weeks 1-5 whose features use games through Week 4. The original result is preserved in the ledger entry (`P5-2.data_correction.result_before_cache_refresh`) next to the corrected one; P5-3 keeps a summary of its first FAIL.
Other dependents of the cache were checked: `games.csv` feeds the Champion frame, JP/P5-1 features and the E-series, but no row for 2025 or earlier changed, so P5-1 and the E13/E14/JP/P3 results are unaffected and were not rerun. The cached nflverse weekly stats for 2026 and the Fantasy Points weekly exports are separate files; they still end at Week 4, which is why the shadow cutoffs are Week 4.
Rolling-feature check on real data (`python scripts/p5_data_checks.py --root <FantasyPoints> --old-games <old csv>`): 13,048 feature cells (every team-game since 2021) re-computed independently with plain loops: 0 mismatches; every prior game used started before the target game; 0 uses of another season's games. Unplayed games have no score and are excluded from every window. Forecast `asOf` = kickoff of the latest prior game + 4 h, and was before the snapshot for all 254+ games (minimum 88 h).

## P5-3 real-archive game-line audit and comparison: PASS (after the public score cache was refreshed), zero data violations
Scope and criteria: all 1,925 exported full-game records (moneyline 647, spread 636, total 642) over 649 actual games, 2024-09-05 to 2026-10-12, ten books. Frozen pass rule: no violation of any listed check and under 1% of games without an independent score. This is an **integrity** audit of the data and the comparison code. It is not evidence of predictive improvement or a betting edge, and the model comparisons below remain research-only.
`scripts/archive_game_line_audit.py` re-derives from the raw index: 1,925 records, 649 games, 15,254 book pairs, all reproduced from raw quotes (side, line, price). Only h2h/spreads/totals were requested (no period or alternate market). One decision snapshot per game. `quote_at <= snapshot_at < actual kickoff` for all 30,508 quotes. Snapshot 4.4 to 34.4 minutes (median 34.4) before the actual kickoff; quotes 4.5 to 48 minutes. Implied-probability sums 1.010 to 1.070 (none crossed). Schedule kickoffs equal nflverse kickoffs. Outcomes recomputed from scores match.
**Update 2026-10-16:** the first run was FAIL only because 15 Week-5 2026 games (2.3%) had no independent score in the cached public `games.csv` (cached 2026-10-08). With your approval I downloaded the current free nflverse `games.csv` into the private cache (old copy kept as `games.2026-10-08.csv.bak`) and reran P5-3 unchanged: PASS, 0 violations, 0 games without an independent score. P5-2 was then rerun unchanged (see the data correction above): identical.
Timestamp semantics stay distinct: snapshot_at (provider board), quote_at (bookmaker update), forecast asOf (kickoff of the latest prior game used + 4 h), feature availability (end of that game). The FP archive `known_at` stamp is retrospective (2026-10-08), so historical availability is assumed, not observed.
The implemented comparison on real records (walk-forward, Brier, equal vs research vs learned): moneyline 518, spread 509, total 514 scored records; differences vs equal are within about 0.0002 and intervals span 0. No CLV claim (no closing series).
**Defect found and fixed:** the learned-weights step overflowed to NaN when a vanishing-weight source was the only one on a board, so the spread comparison returned "no fold" and the total comparison silently lost a fold (384 scored, now 514). `shared/market-validation.js` `learnWeights` now stops the update before it leaves the simplex; the regression test in `tests/missions-history.test.cjs` fails on the old code.

## Prospective shadow pipeline (`scripts/fp_shadow.py`)
Captures the P5-2 forecasts (CH_RAW, B_PTS, B_NFL, C_FP) plus the matched market price for unstarted 2026 Weeks 6-10 games.
- Write-once (exclusive create, read-only file), hash-chained ledger, real wall-clock capture time (`--now` only with `--dry-run`).
- Refuses games within 30 minutes of kickoff, a market board older than 6 hours, and any directory inside the repository.
- Records source hashes, per-source feature cutoffs, code SHA, protocol spec hash and exclusions. `settle` adds outcomes in separate files; `score`, `verify` and `receipt` (hashes and timestamps only) are included. 13 failure-safety tests.

**Capture status: no genuine capture exists, and none was fabricated or backdated.** A real (non-dry) run at 2026-10-16T01:04Z with the default safety rules wrote nothing (run report in `%LOCALAPPDATA%\GOING\privatep-shadow
uns`). Exact exclusions: Week 6, 13 games `market_snapshot_older_than_6h`; Week 6, 1 game (Thursday night) `started_or_less_than_30_min_to_kickoff`; Week 7, 14 games `market_snapshot_older_than_6h`; Weeks 8, 9 and 10, 43 games `no_matched_market_price` (no total posted). The newest published board (`origin/main`, `data/nfl_betting.json`) was generated 2026-10-15T15:03Z, about 10 h earlier; the 00:24Z data refresh failed to publish a newer one. The only way to capture now would be to relax the 6 h rule, which I did not do.
Duplicate/overwrite check with real inputs (scratch directory, labelled test, deleted afterwards; these are not captures): first run wrote 27 records, a second identical invocation wrote 0 and reported `already_captured` for all 27, appending to a capture file was refused by the read-only mode, and the ledger chain verified (27 entries, no problems). Unit tests cover the same plus late-forecast refusal and tamper detection.
## Scheduling status
**Automatic capture is not scheduled.** No `GoingLong-FP-Shadow-Capture` task exists (checked with Task Scheduler); the only related task in this repo family, `GoingLong-FP-Autoload`, is a different job and was not found either. `scripts/install_fp_shadow_task.ps1` is prepared and tested in dry-run mode: default prints the exact command and registers nothing; `-Activate` registers a per-user, limited (non-admin) task that runs `fp_shadow.py capture --market-from-git origin/main` hourly. **Activating it needs your approval** (it creates persistent configuration on your PC). It does not require production authorization: it makes no deployment, no paid or provider call and writes only to the private folder. Two caveats: the task points at this worktree path, so after integration reinstall it from the final checkout; and scheduling does not remove the blocker above, because capture needs a board under 6 h old and the published board is refreshed only by the twice-daily GitHub workflow (which failed at 00:24Z). A more frequent or more reliable board refresh is a production-workflow change that would need your authorization.

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
Small samples (254 games; WR/TE only for TD). No historical player-prop prices. One pregame board per game and no closing line. Small samples and no independent price source for player TD props.
Feature definition clarification: `pts6` is the expected total (the two teams' mean points scored and allowed, halved) minus the line, and evaluation offsets use the archive line. The spec wording was ambiguous; ridge models are scale-invariant, only the CH_RAW comparator depends on it.

## Final tests and revisions
Code revision tested: `63d66594626dd7287e00f980c11048369281750d`. `python -m unittest discover -s tests -p 'test_*.py'`: 702 tests OK (5 existing skips). `npm test`: 909 of 909 pass. `npm run build` and `node scripts/build_vercel.mjs`: exit 0. Only `npm ci` and the repository's declared Python requirements were used. The earlier `204379d` run was not relied on. The commit that adds this section changes `docs/FANTASY_POINTS_P5_HANDOFF.md` only (verify with `git diff --stat 63d6659..HEAD`).

Real-data checks (need the private files; run 2026-10-16): P5-1, P5-2 and P5-3 runs against `FantasyPoints/` and the odds index; `scripts/p5_data_checks.py` (13,048 rolling-feature cells, games.csv diff and hashes); the real non-dry capture attempt (0 captured, exclusions listed above); the duplicate/overwrite check with real inputs in a scratch directory.
Synthetic-data tests (run anywhere): `tests/test_fp_shadow.py` (16), `tests/test_p5_experiments.py` (21, including the synthetic archive audit and lag/leakage tests), the node regression test for learned weights, and the existing suites.

## Remaining limitations
- No genuine shadow capture yet; no automatic scheduling (needs your approval, and a fresh board is the real blocker).
- All experiments are INCONCLUSIVE and research-only; nothing is promoted. P5-3 PASS is an integrity result, not evidence of predictive value or a betting edge.
- Small samples (254 games for pace; WR/TE only for TD), one pregame board per game, no closing line, no historical player-prop prices.
- The 2026 nflverse weekly-stats and Fantasy Points weekly files end at Week 4; shadow features will carry that cutoff until they are refreshed.
- `pts6` clarification and the shadow market being a single-provider board are described above.
