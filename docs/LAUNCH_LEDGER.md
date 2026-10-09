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
| 9 | P1 | GOING Score player-level redesign + validation + page | research report, data/going_score.json auto-built, page + breakdown | IN PROGRESS |
| 10 | P1 | Charts section (shared data endpoints + components) | nav entry, filters, tooltips, drilldowns, mobile | IN PROGRESS |
| 11 | P1 | Opportunity vs production (expected vs actual) research | pre-registered test next-game / next-3, report | IN PROGRESS |
| 12 | P1 | Showdown field model | private-file ownership/duplication, honest bands | SHIPPED |
| 13 | P1 | Today payload (29 MB raw first load) | lazy history/context | TODO |
| 14 | P2 | NB1 receptions, TD lean score, free-role challenger | prospective shadow only | SHADOW |
