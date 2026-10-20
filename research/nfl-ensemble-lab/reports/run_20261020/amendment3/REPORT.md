# October 20: Amendment 3 local app and weekly pipeline

**Completed:** Local **Projections** and **Leans** now have cached revision selection, consensus/current defaults, skew controls, five tabs, diagnostics, glossary and filtered downloads. Actual entrypoint: zero exceptions on both pages. Week-7 revision 3:14 games/504 player-stat projections, cutoff October19/week6;24 frozen member fits. Both anchors,1,000 sims/three seeds:5,971 stable/189 unstable outputs. Sixteen replacement cases use labelled anonymous assumptions; zero simulation-case failures. All29 earlier forecast hashes match. Latest comparison:[sheet](C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/reports/leans_2026_w07_r03_20261020T214325731600Z.md).

**Model research:** 2022 development only; n=stat rows/games. A is observed-over frequency minus predicted probability at synthetic prior-game median lines (not actual prices). B/C are adjusted loss minus original; negative favors adjustment. Paired game-cluster95% CIs,2,000 draws. **No gate passed** in the eight-test primary Holm family; no promotion.

| Hypothesis / metric | n/games | Delta [95% CI] | Decision |
|---|---|---|---|
| A: anytime_td bias | 2637/271 | +0.001 [-0.015,+0.018] | Diagnostic |
| A: pass_tds bias | 504/267 | -0.051 [-0.094,-0.008] | Diagnostic |
| A: pass_yds bias | 386/205 | -0.098 [-0.145,-0.051] | Diagnostic |
| A: rec bias | 1990/271 | -0.031 [-0.054,-0.008] | Diagnostic |
| A: rec_yds bias | 1775/239 | -0.015 [-0.037,+0.007] | Diagnostic |
| A: rush_yds bias | 766/239 | +0.003 [-0.027,+0.032] | Diagnostic |
| B: pass_yds mae | 507/267 | +6.185 [+4.001,+8.487] | Rejected |
| B: rush_yds mae | 825/271 | +0.719 [+0.195,+1.244] | Rejected |
| B: rec_yds mae | 1765/271 | +0.763 [+0.481,+1.059] | Rejected |
| C: anytime_td brier | 2398/271 | +0.003 [+0.001,+0.006] | Rejected |

All pinball/log-loss tests, reliability bins and mean/median exceedance:[results](C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/reports/run_20261020/amendment3/RESULTS.json). Full eligible accounting covers8,576 rows/271 games, including809 absent structural members;3,252 team-stat remainder records conserve. Primary rows above use the preregistered matched sample.

**Concerns:** All28 teams retain original coherence gaps; reconciliation worsens accuracy and stays separate. Prospective accounting includes58 missing structural rows and168 explicit other/unresolved remainders; maximum conservation error5.7e-14. TierA=0 (B1,199/C2,329 comparison rows, not independent opportunities). Latest source quote11:08 ET; stale after24h. Replacement identities/inactives remain unknown until verified. First-TD settlement and prospective accuracy are unvalidated. Existing American-odds branch warnings persist; delivered probabilities are finite/in range. One bad test-path invocation and one patch-context failure were logged; no assertion failure or new test skip.

**Next:** Frozen2023-25 single look deferred:54 fits plus~816 structural games exceed the remaining budget. Week7 descriptive scoring skipped: no games completed. Address calibration/eligibility before another acceptance study; never tune on2026 results. [Previous eight-hour report preserved verbatim](C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/reports/run_20261020/REPORT_amendment2_preserved.md).

**Needs Travis:** Launch `.\launch_lab.bat`; sidebar **Projections** / **Leans**. Refresh next week: `.\run_week_projections.bat --week 8` (`--plan` previews). Review `.\scripts\register_archive_tasks.ps1 -WhatIf`, then run manually if desired. Script not executed; no tasks created.

**Checks:**284 passed/one pre-existing skip/519 dependency warnings (328.77s), source f409dfa; actual final-sheet AppTests passed. Champion v20261016_212540/v1 unchanged. No eval, spend, sends, deployment or database writes. Run started16:13 ET; implementation/tests complete17:44 ET, final integrity/commit handoff follows.
