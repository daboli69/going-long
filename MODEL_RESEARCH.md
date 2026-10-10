# Model research

Takeover baseline: `3f2651e`, 2026-10-10. Champion stays unchanged. Research claims require decision-time data, chronological validation, paired market comparison, uncertainty, and an untouched holdout before promotion.

| Hypothesis / audit | Evidence | Test | Result | Status |
| --- | --- | --- | --- | --- |
| Passing-yards refit adds information beyond market | Existing `research/prop-lines/out/passyds_lines.txt`, n=119 QB-games | Source/aggregate inspection; original historical inputs unavailable | Inherited main Brier .2627 refit vs .3055 raw and .2500 market; MAE 61.6 vs 73.6 raw and 59.2 line. Extraction defects require regeneration; not reproduced Codex performance | Empirical validation blocked; no promotion |
| Historical quote reconstruction is point-in-time and two-sided | `research/prop-lines/build_quotes.py` | 10 offline regressions: asynchronous sides, late observations, ambiguous identity, market/date eligibility | Confirmed groupby.last fabricated mixed-observation pairs and receipt cutoff missing. Fixed intact observations with both clocks before kickoff, reject ambiguous IDs/non-REG dates | Engineering repair verified at 52c5b79; aggregates unverified |
| First-TD normalization/outcome refer to the same game | `scripts/first_td_quote_summary.py`, `research/prop-lines/td_live_and_firsttd.py` | Five isolated tests: concurrent games, team order, partial runners | Exact scheduled game, same-game scorer and per-game coverage/overround replace date aggregation | Engineering repair verified; first/last-TD predictive validity unproven |

Do not access or publish excluded private/licensed inputs, invent missing prices or treat synthetic regression fixtures as performance evidence.

Before any next fit, freeze dataset hashes, exact game/player/market/book/line/side contracts, decision-time availability, push/void/nonparticipant policy, chronological folds and untouched later holdout, same-sample Champion/market/simple baselines, clustered uncertainty and acceptance thresholds. General historical joins need exact event/team/player provenance, not dates/names alone. No repeated holdout tuning. CLV/ROI require real matched timestamped prices and settlements. Failed hypotheses belong here. Champion and ABBEYS remain unchanged.
