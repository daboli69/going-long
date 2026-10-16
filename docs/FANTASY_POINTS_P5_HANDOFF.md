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

Capture status, scheduling and the refresh blocker are in the Operational status section below.

Untouched outcomes: only 2026 games whose kickoff is after their capture time. 2026 Weeks 1-5 results were read by the P5-2 evaluation and are inspected.

## Private data dependencies and cloud reproduction
Private (not in Git): `FantasyPoints/` including `research/cache`, `%LOCALAPPDATA%/GOING/private/odds-history/`, the derived `odds-history-derived/` (export, market probabilities, forecasts) and `fp-shadow/`.
Local commands:
- `python scripts/missions_history_export.py --out <derived>/missions-input.json`
- `node scripts/archive_market_probs.cjs <derived>/missions-input.json <derived>/market-probs.json`
- `python scripts/trend_research.py --root <FantasyPoints> run P5-1 P5-2 P5-3`
- `python scripts/archive_game_line_audit.py --root <odds-history> --games <FantasyPoints>/research/cache/games.csv`

Cloud reproduction without local files: `tests/test_p5_experiments.py`, `tests/test_fp_shadow.py` and the node regression test verify the frozen spec hashes, aggregate-only results, the 2024 gap accounting, the lag and leakage logic, write-once and late-forecast refusal, and the audit on a synthetic archive. `research/trend-intelligence/ledger.json` entries P5-1, P5-2 and P5-3 hold the aggregates quoted here.

## Operational status (2026-10-16, evening US Eastern)
The sections below separate facts by kind. Research conclusions are above and unchanged: all experiments INCONCLUSIVE and research-only; P5-3 PASS is an integrity audit, not predictive evidence or a betting edge.

### Scheduler registration and execution (verified)
- Task `GoingLong-FP-Shadow-Capture` (one task; per-user, limited rights, no admin). Registered with your approval on 2026-10-16, then **replaced the same day by a durable version** after the replacement passed its own test.
- Executable: `C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\.venv\Scripts\python.exe` (the main checkout's venv). Script and working directory: the commit-pinned runtime copy `%LOCALAPPDATA%\GOING\private\runtime\fp-shadow\b3733e891708`, made with `git archive` of commit `b3733e891708b06173555cb0851e87e3e4785ea5` (`RUNTIME_COMMIT` records it). It no longer depends on the research worktree, which can be deleted.
- Arguments: `capture --root <FantasyPoints folder> --market-from-url main --weeks 6-10`. Board source: HTTPS GET of the public repository's `data/nfl_game_lines.json` and `data/nfl_betting.json`, whichever is newer (no credentials, no git, no provider request).
- Schedule: every 30 minutes, first trigger 2 minutes after registration, only while this user is logged in; `StartWhenAvailable`; multiple instances ignored; 5-minute limit. The PC's time zone is Eastern (Task Scheduler shows local time; run reports are UTC).
- Output: `%LOCALAPPDATA%\GOING\private\fp-shadow` (`captures/`, `ledger.jsonl`, `runs/`, `settled/`). Nothing is written inside Git.
- Execution evidence: the first worktree-based task ran at 21:31 EDT (result 0) and wrote a run report. The durable task ran manually at 21:38 and on its own schedule at 21:40:40 EDT, both result 0 with run reports written and 0 missed runs. "Registered and Ready" alone was not accepted as proof.
- Duplicate prevention: one fixed task name; the installer refuses if another task runs `fp_shadow.py`, refuses a name owned by something else, uses `MultipleInstances IgnoreNew`, and replaces the existing task only after the new runtime passes a dry-run capture. Re-running the installer for the same commit reuses the runtime.
- Reinstall or update: `powershell -File scripts\install_fp_shadow_task.ps1 -Commit <sha> -Activate` (dry run without `-Activate`). Remove: `Unregister-ScheduledTask -TaskName GoingLong-FP-Shadow-Capture -Confirm:$false`.

### Successful captures: none yet, and none fabricated
Every scheduled run so far wrote a report and no capture. Exact reasons at 2026-10-16T01:40Z: Week 6, 13 games `market_snapshot_older_than_6h` and 1 game `started_or_less_than_30_min_to_kickoff`; Week 7, 14 games `market_snapshot_older_than_6h`; Weeks 8-10, 43 games `no_matched_market_price`. The newest published board was generated 2026-10-15T15:03:47Z. The 6 h rule was not relaxed.
Repeat execution was verified with real inputs in a scratch directory through the runtime copy (27 written, then 27 `already_captured`, ledger verified; the scratch records were deleted and are not captures) and by unit tests. Nothing is backdated: `captured_at` is the wall clock at write time, and a forecast is refused within 30 minutes of kickoff.

### Refresh health
- Failed run `38829303688` (scheduled, 2026-10-16T00:24Z). The same signature occurred in `38809504532` (21:23Z, manual dispatch) and `38814908268` (22:07Z, push). The last success was `38756536155` (2026-10-15T15:00Z), whose board is still the published one.
- **Provider:** the last scope of the nine-query props plan, `props_partition_9` (the small derivative query), returned HTTP 200 with `truncated: true` (2,118, 2,236 and 2,425 rows). The provider's hint says one book writes more rows per hour than one query reads, so the response can miss props and whole games. Game-line (`odds`) data is a separate request.
- **Ingestion:** `build_nfl_betting.py` correctly marked the refresh FALLBACK (incomplete coverage), wrote the file and exited 1.
- **Publication:** `refresh_health.py` refused to publish `data/nfl_betting.json` because its owner step failed (`publication_failures` was empty; the guard worked as designed). Result: the whole file, including game lines fetched fresh in the same run, stayed unpublished and the published board aged past six hours.
- **Fix under our control (this branch; not merged or deployed):** `scripts/publish_game_lines.py` plus a workflow step publish `data/nfl_game_lines.json` from the same run, only when the odds source itself is FRESH and observed within 6 hours; otherwise it writes nothing and fails. It adds no provider request. Strict health on `nfl_betting.json` is unchanged (still unhealthy and withheld), the new file has its own owner in `refresh_health.OUTPUT_OWNERS`, and a failed game-lines step blocks only that file. 8 new tests, including a health-report scenario.
- **Not fixed (needs authorization):** the provider truncation itself. The only lever found is splitting the derivative query in two, which adds requests (roughly 3 credits per run if each of the nine queries costs about 3 of the 27 documented credits; an estimate, not measured). No such change was made.
- **Cadence audit:** scheduled refreshes run at 10:20 and 22:20 UTC daily, plus Monday 21:05 and five Sunday times (08:20, 09:20, 12:05, 15:45, 19:05). A board is under six hours old for about six hours after each successful run, so a 30-minute poll can catch it, but only if the refresh succeeds. Sunday kickoffs are well covered; Thursday and Saturday games rely on the 22:20 run. The task polls every 30 minutes and captures at the first eligible tick; triggering it from the workflow would be a production workflow change.
- **Provider usage (estimate, not an account reading):** in the last 30 days 159 workflow runs executed on `main` (66 scheduled, 87 push-triggered, 6 manual). At the documented 27 credits per full props refresh that is about 4,300 credits, versus the documented 2,350 for the scheduled cadence alone, against your stated 20,000 per month allowance (about 21%). Push-triggered runs are more than half of it; limiting them would save credits but is a production workflow change I did not make. I did not query the provider, since any request spends credits, so actual account usage, other endpoints and scanner usage are unknown.
- Until this fix reaches `main`, the next scheduled refresh (10:20 UTC) will most likely truncate the same scope again and no board will be fresh.

### Remaining approvals and blockers
1. Integrate this branch into `main` so the game-lines step runs in the production workflow (production workflow change; not done).
2. Authorize provider usage if you want the truncated derivative scope split (extra requests) or a manual refresh dispatch to produce a fresh board now (each full refresh is about 27 credits). Neither was triggered.
3. Optional: limit push-triggered refreshes to save credits (workflow change).
4. After integration the task keeps running unchanged; reinstall only to update the pinned commit.
No genuine prospective capture can exist until a board under six hours old is published while games remain more than 30 minutes from kickoff.

## Final tests and revisions
Code revision tested: `b3733e891708b06173555cb0851e87e3e4785ea5`. `python -m unittest discover -s tests -p 'test_*.py'`: 713 tests OK (5 existing skips). `npm test`: 909 of 909 pass. `npm run build` and `node scripts/build_vercel.mjs`: exit 0. Only `npm ci` and the repository's declared Python requirements were used. Earlier runs (`204379d`, `63d6659`) were not relied on. The commit that adds this section changes documentation only (verify with `git diff --stat b3733e8..HEAD`).

Real-data checks (private files, 2026-10-16): the P5-1/P5-2/P5-3 runs; `scripts/p5_data_checks.py` (13,048 rolling-feature cells); the P5-2 rerun after the games.csv correction (identical); real capture attempts and scheduled task runs; the scratch duplicate/overwrite test through the runtime copy; the GitHub run-log inspection.
Synthetic-data tests (run anywhere): `tests/test_fp_shadow.py` (19), `tests/test_p5_experiments.py` (21), `tests/test_publish_game_lines.py` (8), `tests/test_refresh_health.py`, the node regression test for learned weights, and the existing suites.

## Remaining limitations
- No genuine shadow capture; the refresh blocker above is outside this branch until it is integrated.
- All experiments INCONCLUSIVE and research-only; nothing promoted. P5-3 PASS is an integrity result only.
- Small samples (254 games for pace; WR/TE only for TD), one pregame board per game, no closing line, no historical player-prop prices; the shadow market is the single-provider board with proportional de-vig.
- Feature definition clarification: `pts6` is the expected total (the two teams' mean points scored and allowed, halved) minus the line, and evaluation offsets use the archive line; the spec wording was ambiguous, ridge models are scale-invariant and only the CH_RAW comparator depends on it.
- The 2026 nflverse weekly stats and Fantasy Points weekly exports end at Week 4, so shadow features carry that cutoff until refreshed.
- The task runs only while you are logged in and the PC is on; raw GitHub content can be cached for a few minutes.
