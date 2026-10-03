# GOING operating rules

## Mission and scope
- **Going Long (NFL + NCAA)** is primary: improve data accuracy/freshness, game-line and player-prop models, UX/mobile, speed, reliability, bet discovery, QoL, useful data, accessibility and public usability.
- Central bettor question: **What are the most interesting data-backed bets today, and why?** Advance comprehension, game-centric research, mobile/parlays and trustworthy matchup evidence; compare product/data/research opportunities with recent cycles rather than defaulting to easy maintenance. No quotas or busywork.
- **Going Yard (MLB)**: maintain and prevent regressions; football takes priority.
- **Going Up (basketball)**: no development until Travis authorizes it.

## Roles (hats, not seven always-running agents)
| Role | Responsibility |
| --- | --- |
| MANAGER | Rank evidence by user impact, correctness, urgency and effort; delegate only worthwhile, bounded work. |
| FOOTBALL DATA | Audit NFL/NCAA provenance, identifiers, missingness, freshness, useful metrics and free data opportunities. |
| MODEL RESEARCH | Proactively research credible new football modeling methods, features, statistical techniques and tracker-derived hypotheses for both game lines and player props. Research freedom is broad; test promising ideas through the Model Gate, require evidence for production changes and report results concisely. |
| UI/UX | Audit desktop/mobile navigation, typography, spacing, accessibility, bet discovery and QoL. |
| QA/PERFORMANCE | Reproduce bugs; check regressions, mocked APIs, calculations, builds and performance. |
| PRODUCT | Identify high-value improvements for public users; define benefit and acceptance criteria. |
| BUILDER | Implement the smallest validated high-priority improvement; test and record rollback. |

## Work loop and token discipline
1. Read `PROGRESS.md`, then relevant findings and changed files; use `docs/AUDIT_GUIDE.md` for the code map. Do not repeatedly inventory/reread the repo.
2. Select at most one meaningful issue; record owner, evidence and acceptance criteria in Working. Default to one relevant role; maximum 15 minutes active work per daily cycle, including tests and handoff. Defer unfinished work without claiming completion.
   Eight independent ET occurrences use unique date/time/run IDs and the common-Git cycle lock. Inspect latest main/review state and today's work; systematic ranking collection counts against the same 15-minute budget. Skip overlapping work; never take over an unexplained lock.
3. Maximum **3 concurrent agents total, including MANAGER**. Narrow tasks and file ownership; no duplicate investigations unless independent validation adds value.
4. Use cheapest capable included model where cycle-specific selection is available: Luna/low for routine work, Sol only for demonstrated difficulty, Astra only for exceptional escalation with Travis's approval. Do not change global/chat settings as a workaround; record unavailable selection once. Never buy credits.
5. Handoff only finding, file/line, reproduction/evidence, proposed fix, tests and blocker. Reuse findings; research reports results, not essays.
6. Test the bounded change, update the trackers, and stop. If no meaningful work exists, stop without busywork or repeated unchanged reports.

## Model gate
**Research -> hypothesis -> backtest -> out-of-sample validation -> compare to current model -> accept/reject.**
- Keep current production methods as **Champion**; version experimental **Challengers** separately. No automatic promotion or live retuning from a few wins.
- GOING Confidence is qualitative **evidence readiness**, separate from estimated likelihood, price/value and the player GOING Score. Follow production `docs/GOING_CONFIDENCE.md`: exact current direction-relevant support, honest concerns/freshness, no invented confident call or calibrated percentage.
- NCAA current-team evidence takes priority conceptually; learn sample-aware windows/decay/priors empirically. Existing 80/20 is an unvalidated Champion policy, not a requirement. Follow separate `research/ncaa-recency/protocol.json`; historical as-of inputs are blocked, NFL remains independent. No fitting/promotion from revised aggregates or assumed coaching/QB/roster continuity.
- Today experiment `today-ranking-v1`: follow production `research/today-ranking/PROTOCOL.md`; preserve complete frozen pools and append results/invalidation separately. Never rewrite policies/cutoffs after outcomes or treat Score/100 as probability. New hypotheses need a new future version; ranking promotion requires Travis.
- Require credible primary research with citations, established statistical methods, or reproducible data evidence. Never invent methodology, odds, results or performance.
- Freeze hypothesis, data cutoff, splits and acceptance criteria before fitting. Train only on inputs/outcomes available at decision time; use chronological folds and an untouched later holdout. Guard against leakage, repeated holdout tuning, correlated selections and overfitting.
- Compare identical eligible samples against Champion and a suitable market/simple benchmark; report sample size and uncertainty. Track Brier/log loss and reliability/calibration for probabilities; MAE/RMSE for projections; CLV/ROI only with real matched prices, settlements and push/void handling. Hit rate alone is insufficient.
- Record hypothesis/evidence/test/result/status in `MODEL_RESEARCH.md`. Insufficient data means blocked/research-only, never fabricated validation.

## Cost, safety and completion
- **$0 additional spending.** Never activate paid APIs, usage credits, hosting, subscriptions, datasets or other paid services without Travis's approval. Existing credentials do not authorize consuming metered credits.
- Work on `codex/` branches; preserve user edits, small commits and a revert path. No force pushes, destructive resets or major rewrite.
- Review branch `codex/going-long-daily-review` is automation-owned; Claude reviews read-only. Travis's later scoped authorization permits completed tested ordinary low-risk cycles there and through existing main-to-Vercel production. Follow `docs/DAILY_REVIEW_PIPELINE.md`: explicit paths, exact diffs, unchanged captured tips, clean isolated main-based worktree, completion/receipt and rollback. No unrelated history, force push, conflict reconciliation, PR/merge or alternate deployment.
- Ask before risky production, database/schema/migrations, authentication/security, secrets, destructive operations, major architecture, paid services, Going Up or model/ranking promotion. Ordinary low-risk publication does not waive these gates.
- Do not send alerts, run `--send`/`scripts/smoke_alerts.py`, expose secrets or access excluded private inputs. Use mocks/offline fixtures for ordinary tests.
- Test before claiming completion: targeted regressions, then affected build/integration checks. Use `.venv/Scripts/python.exe` on Windows. Standard checks: `npm test`; `python -m unittest discover -s tests -p 'test_*.py'`; `npm run build`; `node scripts/build_vercel.mjs`.
- Update `PROGRESS.md` and `MODEL_RESEARCH.md` only when meaningful; no unchanged-status churn. Keep Progress limited to Completed / Working / Problems / Next / Needs Travis. Record revision, checks, limitations and verified vs unverified findings; no parallel backlog.
