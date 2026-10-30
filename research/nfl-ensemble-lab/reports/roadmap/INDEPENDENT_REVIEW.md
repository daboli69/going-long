# Independent review of the eight amendments (2026-10-30)

Reviewer: a fresh Claude subagent with no memory of the work, read-only, asked to audit GOVERNANCE.md, the attempt folders, the
code diffs and the commit order. It is the same model family as the author, so it is a weaker check than a person or a second
toolchain. This is its verdict, shortened but not softened. Author notes follow in GOVERNANCE.md ("Record corrections after
independent review").

Overall verdict: the amendments pass, with concerns on 2, 4, 6, 7 and 8. No sign that any band or condition was tuned toward a
real-data pass. Nothing in the repository was changed by the reviewer.

| Amendment | Verdict | Main point |
|---|---|---|
| 1 | PASS | Flaw real (standard error 2.2 points at the 5% edge with 100 sims); original failed run kept. Attempt 1 at 400 sims still failed, so the fix was incomplete, but nothing was hidden. |
| 2 | CONCERN | Split is independent of results. The Step 3 floor of 300 became 250 with no formula. 2026 is not pristine (pooled paired differences were already seen). |
| 3 | PASS | A market-equals-truth world cannot test a boundary test. Committed before the first rehearsal output. |
| 4 | CONCERN (mild) | Flaw real (191 ladders in 13 weeks for 2025). The floor fell from 500 to 150, just under the known count. Props power never reaches 80%. |
| 5 | PASS | Logic flaw confirmed (the market price stays inside the dependent variable). The cited smoke test (103 of 160) is not in the record. The "0.049 gain is detectable" claim was wrong and is retracted in Amendment 7. |
| 6 | CONCERN | Cited numbers match attempt 1. SPA bug real. Lowering the junk BH limit from 95% to 90% after seeing 94% eases a pass, though 95% is the expected value under a correct test. |
| 7 | CONCERN | Wild bootstrap-t is justified. The planted_strong world was introduced after a 41% planted rejection and passes at 82% against 80% (standard error about 3.8 points). The "97% power" calibration had no file. |
| 8 | CONCERN (mild) | Flaw real. The 0 of 20 result was known and disclosed. First run kept. |
| code fix, greater-than to at-least | PASS | Correct and conservative. |

Separate checks reported:
- Gate order: every real output post-dates its rehearsal pass. The gate reads only a PASS flag, not a code hash. Real Steps 3, 4 and 5 ran before real Step 2. Real Step 7 ran after the failed Step 6 (disclosed, superseded).
- 2026 use: no model-versus-market comparison on 2026 after confirmatory_rules.json was written.
- Reproduction: re-running Steps 3 and 5 gave identical p-values and statuses; ladder-derived floats differed by at most 4e-9 relative.
- Statistical points: sign-flip wild tests assume symmetric differences; the Step 2 simulation has no week effects; Step 3's identity check cannot fail; PBO on 8 blocks of 13 weeks is one noisy statistic; Step 5 total false positives 8.1% against a 9% limit; "converged in at least 98% of draws" was replaced by "p finite" without an amendment.
- Unsupported claims: "Real Step 2 passed all its conditions" (condition (d) was not checked); the 97% power claim; the label audit's winner check covers one game; the sensitivity script omitted p_xgb_v1; the real margin joint-model weight is significantly negative and the decision table would "freeze" it.

One reviewer claim was not reproduced: it reported numpy 2.5.3 and scipy 1.18.1 in the virtual environment. The environment has
numpy 2.1.3 and scipy 1.14.1, matching repro_check.json.
