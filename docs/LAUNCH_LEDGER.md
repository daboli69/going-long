# GOING 1.0 launch ledger (deadline Sun 2026-10-11 09:00 ET)

Source of truth for the launch mission. Status: TODO / IN PROGRESS / BLOCKED / VERIFIED / SHIPPED. Update in the same commit as the work.
Rollback: Champion `config/champion_policy.json` (`active:false` or env `GOING_CHAMPION_POLICY=v1`); picks cohort v2 intact beside v3; every shadow file write-once.
Baseline 2026-10-09 20:00Z: branch `claude/phase3-weekly` = origin/main 1fa0584; Node 549 pass; Python 340 (3 missing-package errors: thefuzz, polars).

| # | Pri | Task | Acceptance | Status |
| --- | --- | --- | --- | --- |
| 1 | P0 | Data freshness + refresh health | refresh commits land; red step identified as sportsbook props 503 (known, separate) | VERIFIED (diagnosed) |
| 2 | P0 | First-TD availability gate (ACT only) | `tests/test_qa_a_final.py` passes after next refresh regenerates history.json | SHIPPED, verify after refresh |
| 3 | P0 | Best Plays / Today v3 rating, all-games list, role watch | node suite green; real-page check | SHIPPED |
| 4 | P0 | Player card intelligence (role trend, scoring role) | real-page check | SHIPPED |
| 5 | P0 | Jackpot (expired-slate guard, scoring role, First TD gate) | real-page check | SHIPPED |
| 6 | P0 | DFS Classic distributions, ownership, measured objective | headless lineup valid; copy honest | SHIPPED (limitations documented) |
| 7 | P0 | Sunday pregame freeze in workflow | `data/freezes/2026-10-11.json` exists before 13:30Z Sunday | IN PROGRESS: verify Sunday 08:20Z run |
| 8 | P0 | Windows scanner state | cannot be inspected from this session | BLOCKED (owner machine) |
| 9 | P1 | GOING Score v2 (player-level) | P4-1: matches shrunk xFP for QB/RB/WR, beats for TE; page with breakdown, movers, compare | SHIPPED (modest validation) |
| 10 | P1 | Charts section | 7 charts verified rendering on real data; auto-built by refresh | VERIFIED (mobile pass pending) |
| 11 | P1 | Opportunity vs production research | E12: no predictive cell; descriptive only | VERIFIED |
| 12 | P1 | Showdown field model | private-file ownership/duplication, honest bands | SHIPPED |
| 13 | P1 | Today payload | measured on production: 29 MB raw is 2.5 MB over the wire (brotli: history 1.18 MB, context 1.09 MB) | VERIFIED, lazy loading deferred (risk > benefit before Sunday) |
| 15 | P0 | Calibration repair: game lines market-anchored, TD means corrected, extreme-probability guard | docs/CALIBRATION_AUDIT.md repair pass; independent QA reproduced | SHIPPED |
| 14 | P2 | NB1 receptions, TD lean score, free-role challenger | prospective shadow only | SHADOW |
| 16 | P0 | Players to Target (fantasy and betting) with injury/IR/bye/availability gating | tests/going-targets.test.cjs; independent QA found 0 unavailable players in real-data lists; mobile 375px no overflow | SHIPPED |
| 17 | P0 | Spread key-number push mass | table-driven pushes at 3/7/10 | SHIPPED |
| 18 | P0 | DFS real-data QA (Classic 10/04, Showdown 9/20-10/08, private ownership models, read-only) | all lineups legal, CPT 1.5x exact, ownership sums 900%/600%, no NaN; found DK Status column ignored (fixed: IR/OUT excluded in Classic and Showdown); lineup ownership understated 2.6-3.8x (known, UI says so); D/ST not negatively correlated with opposing offense; Oct 11 slate not posted, Throne mode stale snapshot; no ROI measured | VERIFIED WITH LIMITS |
| 19 | P0 | Central eligibility engine (shared/going-eligibility.js + scripts/eligibility.py): fail-closed on stale/missing data | tests/going-eligibility.test.cjs, tests/test_eligibility_mirror.py | SHIPPED |
