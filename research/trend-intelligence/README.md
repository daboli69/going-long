# Trend Intelligence and Fantasy Points model research

Goal: find which signals genuinely improve GOING's ability to predict player and game outcomes, and only then turn them into
bettor-facing evidence. The chain GOING should eventually reason along:

`what changed -> why it changed -> does it persist -> matchup interaction -> expected outcome -> model -> market price -> counter-evidence -> bet / pass`

A trend is not a bet. A significant relationship is not a betting edge. Missing evidence is not negative evidence.

## Taxonomy

| Trend type | What it describes | Fantasy Points / GOING sources |
| --- | --- | --- |
| Role | routes, route participation, targets, TPRR, first-read and designed-target share, carries, snaps, goal-line usage | routes run, receiving advanced, bell cow, offense snaps |
| Deployment | slot / wide / inline / backfield, route types, depth, personnel, formation, motion, play action | routes run, separation by alignment/route/break, run-pass report |
| Opportunity | XFP, expected yards/receptions/TDs, air yards, inside-10/5 usage, opportunity vs production | efficiency, receiving advanced, bell cow, rushing basic/receiving basic |
| Regression | underlying opportunity differs from results; **tested, never assumed** | XFP vs FP, XTD vs TD |
| Team environment | EPA, success rate, PROE, pace, scoring, pressure, tendencies | run-pass report, coverage matrix, GOING game data |
| Matchup interaction | alignment x coverage, first read x defence, route x coverage, pressure x protection, front x rushing style | man-vs-zone, separation by coverage, coverage matrix, OL/DL (2026) |
| With / without | role change when a teammate is unavailable | needs point-in-time injuries + weekly role (2026) |
| Historical comparables | nearest-neighbour player-situations | earlier seasons only |
| Counter-evidence | every thesis must be able to say what argues against it | every family |

## What can be tested (never manufacture point-in-time data)

* **A. Prior season -> next season.** Features from season N-1 completed files, outcomes in season N. Testable now.
* **B. Cross-sectional / persistence** on completed seasons where the method is legitimate.
* **C. Same-season trend research** needs genuine point-in-time data. The 2021-2025 files are retrospective full-season totals and are
  **never** Week-N information inside their own season. Only the accumulating 2026 snapshots qualify.
* **D. 2026 prospective only.** Tracked from now; evaluated as observations accumulate.

`candidate_signals.json` maps 15 candidate signals to tables, markets, evidence class, seasons, leakage risk and a pre-set priority score
(betting value x data quality x testability).

## Process (enforced by code and tests)

1. **Pre-register**: `python scripts/trend_research.py register` hashes each spec (hypothesis, rationale, features, baseline, outcome, splits,
   decision rule) into `ledger.json` and it is committed BEFORE the run. A run refuses a spec that differs from its registration.
2. **Leakage control**: features for season N come only from season N-1 or earlier (`data.prior_features`), weekly rolling features use earlier
   weeks only, the season-N Fantasy Points file is an outcome only, and a lookup raises if asked to predict a season from its own totals.
3. **Chronological out-of-sample**: rolling origin; a model is fitted only on seasons before the one it is tested on. Fixed ridge penalty (10),
   nothing tuned on test data.
4. **Baselines first**: prior production, then prior production + rolling in-season usage (what GOING already knows). A fancy metric must beat
   those, not merely rediscover target share.
5. **Decision rule fixed in advance**: PROMISING needs >= 1% lower MAE, a paired cluster-bootstrap CI (Bonferroni-adjusted) that excludes 0, and
   improvement in >= 2 of 3 test seasons. REJECTED is a successful result when the test was sound.
   *Rule versions:* the first wave (E1-E6) used rule v1, whose REJECTED fires when the point estimate is below +0.25% regardless of interval width, so
   low-power rejections (E5, E1 yards) read as "no evidence", not "no effect". Experiments registered from now on use v2 (`reject_requires_ci`):
   REJECTED only when the interval excludes a worthwhile gain, otherwise INCONCLUSIVE.
6. **Ledger**: `ledger.json` (machine-readable, aggregate numbers only) and `LEDGER.md` (readable) keep every result, including negatives, so
   rejected ideas are not rediscovered. Post-hoc follow-ups are labelled exploratory and cannot be PROMISING (capped at NEEDS PROSPECTIVE DATA).
   *Robustness checks* (`python scripts/trend_research.py sensitivity`) are descriptive and recorded beside, never instead of, registered results.
7. **Champion / Challenger**: GOING as it is today is the Champion. Nothing here changes a production model, the GOING Rating, recommendation
   selection or ABBEYS. Promotion needs evidence and explicit approval.

## Prospective 2026 trend capture

`python scripts/fantasy_points.py trends` (also run at the end of `import`) differences two consecutive live season-to-date snapshots into
**that week's own usage** per player (routes, route share, targets, TPRR, target share, first-read and designed targets, carries, snaps,
inside-5/10/20 snaps, XFP) and compares it with the player's season-to-date baseline before the week. The state is a pure function of the two
snapshots, carries the later snapshot's known-at time, and is **write-once**: a corrected snapshot produces a separate revision file; later weeks
never touch earlier states. Local only (`FantasyPoints/trends/`), because it derives from licensed data.
