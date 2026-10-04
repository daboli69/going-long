# ABBEYS — NFL current-season board

Find it at **Football → NFL → More → ABBEYS**, or `/long/?mode=betting&tab=abbeys`. This independent straight-up board does not alter Today, game/prop models, GOING Score/Confidence, DFS, or the Champion/C1/C2 experiment. One winner is issued for every actual regular-season Sunday game at/after 09:30 Eastern and every Monday game in the selected week. Earlier days and byes are excluded. Final Monday kickoff supplies the score tiebreaker; identical kickoff times break by game ID. No Monday game means no invented tiebreaker.

## Prediction boundary

`shared/abbeys-core.cjs` copies only **season, regular-season week, game ID, teams, kickoff, an explicit neutral flag, and completed scores**. Only results from the selected season and earlier weeks, at least 12 hours before the actual freeze, train the board. Target-week Thursday results are deliberately excluded. Old seasons, sportsbook fields, odds-derived ratings, historical injury effects, player indices and prior model coefficients are not passed to the predictor.

| Feature | Source / season | Freshness and limits | Market-derived? |
| --- | --- | --- | --- |
| Team points scored/allowed per game | `data/results.json`, explicit NFL ID/active season | Frozen public generation receipt; no per-result upstream publication time | No |
| League mean / designated-home margin | Same earlier-week scores in that season | Small early-season sample; not opponent adjusted | No |
| Schedule / teams / kickoff | Allowlisted fields of `data/nfl_betting.json` | Snapshot generation receipt; mixed-source file also contains odds, which are discarded | No |
| Direction stability | Leave one prior week out, refit the same current-season benchmark | Sensitivity diagnostic, not calibrated confidence or win probability | No |
| Injury/practice reports | `injury_context.current_reports`, exact current season/week/team | Separate post-freeze context; generation age ≤36h, not confirmed inactives or individual report publication times | No |
| Weather / starter changes | Not reliably quantified | No forecast adjustment or invented weather | No |
| Historical trends / book comparison | Optional post-freeze layer | None attached in v1: no verified trend or book-level quote timestamp | Never predictive |

The v1 scoring benchmark takes the symmetric average of a team's scored points and its opponent's allowed points, adding/subtracting half this season's observed designated-home margin. It uses all earlier games equally. A reliable neutral-site flag sets that venue term to zero; current reduced schedule lacks reliable venue detail, so international/home-designation bias remains a concern. Reasons show the actual scoring/prevention/net-scoring inputs and contradictory raw averages, with sensitivity and personnel limitations. No unexplained feature weights are introduced.

`Stable lean`, `Sensitive lean`, `Limited evidence` and `Toss-up` describe the registered sensitivity/sample rules, **not percentages or validated betting value**. A zero forecast margin uses a disclosed alphabetic team-code tie break to meet the one-winner requirement. No current-season league results means no numerical score is invented. Final Monday integers are the nearest nonnegative winner-consistent score pair; this is a point estimate, not a likely exact outcome. See the locked [research protocol](../research/abbeys/PROTOCOL.md) and [retrospective diagnostics](../research/abbeys/README.md).

## Official freeze and results

Use the existing common-Git cycle mutex and clean public input files; no provider calls. From the fresh source checkout:

```text
node research/abbeys/collect.cjs capture SOURCE_CHECKOUT 4 manual
node research/abbeys/collect.cjs settle SOURCE_CHECKOUT
node research/abbeys/collect.cjs verify SOURCE_CHECKOUT
```

The first command is an example for initial Week 4, not permission to replay it. Choose the actual upcoming week. Capture refuses a board once **any applicable Sunday/Monday kickoff has started**, refuses an already-frozen week, and records actual process time. No official predictions are backfilled. The initial manual Week 4 board is official prospective product tracking, separate from the future research holdout and all retrospective diagnostics.

`data/abbeys/journal/` is a dedicated public append-only hash-chain journal using the existing exclusive-lock, atomic-link, bounded writer. Each snapshot preserves the entire allowlisted schedule/results input, cutoff, predictions/reasons/counts/sensitivity, Monday scores, model/protocol hashes, public source revision and canonical JSON receipt hashes. Original snapshots are never recomputed for display using newer data. Duplicate/conflicting keys, locks, pending files, corruption, changed model/protocol definitions and alteration/removal of committed blobs fail verification. A failed context/materialization step leaves the original freeze intact: inspect the failure, then run `verify` and `materialize`; never delete the observation to retry. Missing optional injury context remains explicitly unavailable. Manual invalidation requires a reason and evidence, appends an auditable record and removes no original bytes.

`settle` uses only newer public Git results with the exact game/teams/kickoff, nonnegative integer final scores and an after-kickoff generation receipt. Raw result evidence and win/loss/tie settlement are appended separately with source revision/hash. A revised conflicting result is appended as a conflict and leaves the displayed grade unresolved; it never silently replaces the first result. Missing, ambiguous, postponed/unfinished or unverified cancelled games remain pending. A final tied game is a tie, not a guessed win. The final Monday result adds per-team and combined absolute score errors and an exact-match indicator. No score/grade is reconstructed for weeks before launch.

`data/abbeys-board.json` is a disposable materialized view of the immutable records. The browser loads it through the **existing public Git-backed snapshot endpoint**, with packaged fallback on outage. Thus ordinary verified data-only publication can update the board without inventing another deployment or persistence system. No browser-local voluntary cohort, database migration, API key, paid service, entry automation or new scheduler is involved.

## Scheduled-agent handoff

Existing recurring cycles retain their schedule, 15-minute budget, concurrency/publication/review gates and football priorities. When an upcoming week is due, they may perform this bounded existing-data operation; do not create another automation. `capture ... WEEK scheduled` is allowed only in the 08:00–08:15 ET slot on the date of the earliest **whole-week** kickoff minus 12h, before that origin. A missed/unrepresentable slot is missing coverage, not permission to backfill. The Sunday/Monday product pool is kept separate from the whole-week research origin.

Scheduled v1 records are labeled **B-only prospective holdout**, not paired B-vs-C evidence. C forecasts are not yet systematically frozen; a genuine paired comparison needs pre-origin C snapshots on identical inputs. Preserve this limitation. Holdout raw results may accumulate, but grades/errors/aggregates remain locked until at least January 16, 2027 noon ET **and all Week 18 games final**; a postponement requires the later registered release. The visible season record currently covers manual official boards only and says so. Never fabricate a prospective sample from after-the-fact C fitting.

Future changes must retain v1's implementation and protocol bytes or add a separate versioned implementation/registry; the current verifier intentionally refuses in-place v1 changes. New features, recency/opponent adjustment or injury weights require a new preregistration, chronological checks and untouched later data. No automatic replacement/promotion based on a few wins.

Next priorities: freeze C alongside B prospectively without opening the holdout; improve audited neutral-site/starter availability provenance; add verified current-season efficiency features only through a new comparison; then evaluate score/margin errors, winner counts and sensitivity bands with sample size and game/week dependence. No Brier/log loss until genuine calibrated probabilities exist, and no ROI/CLV for this straight-up board without appropriate prices and settlements.
