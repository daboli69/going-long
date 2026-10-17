# Phase 7.1: QB and injury audit, model-input transparency, live validation

- **Branch:** `codex/nfl-ensemble-lab`, building on 75eb35a.
- **Audit time:** Saturday 2026-10-17, about 15:00 UTC. The week-6 Sunday games had not started, and no archived game has finished.
- **Unchanged:**
  - the frozen champion v20261016_212540, including its QB logic and prediction code;
  - the registered challengers' features and selection rules;
  - all existing archives.

## A. QB and injury pipeline audit
| Question | Finding |
|---|---|
| Why do the champion and the Phase 7 challenger pick different QBs? | The champion uses rule v1: the previous game's starter, replaced only if the verified report lists him Out/Doubtful. The Phase 7 challenger also has rule v2, which projects a primary starter's return when this week's report lists him with a status other than Out/Doubtful. Week 6 has exactly one difference: Chicago (v1 Tyson Bagent, v2 Caleb Williams, who is Questionable with full practice). Sleeper also lists Williams at QB1. |
| Are statuses applied to the right week? | Yes. Statuses are keyed by game, and only week-6 games carry week-6 flags (verified: weeks 7–18 have zero). The live label already ignores a report from another week. |
| Returns, benchings, trades, IR | **Return:** v1 never projects one (that's v2's case). **Benching and IR:** both rules follow last game's starter, which is usually right, because IR players are absent from reports. **Trade:** v1 could keep a traded QB for his old team until that team plays again (rare). Future weeks are inherently provisional: for week 7 v1 still assumes Jalen Hurts (last completed starter), while Sleeper lists Tanner McKee. |
| Do stale depth charts or listings override injury information? | Not in any model: depth charts and nfldata listings are never model inputs. In the live labels they no longer override the official report (fixed in Phase 7). |
| 2025 missing injury data | **Systematic.** nflverse dropped `date_modified` from 2025, so no 2025 game has a verified pregame report. A projected QB change was flagged in 0% of 2025 games, against 1.1–6.0% (typically about 3–4%) in 2016–24. The champion trained on 2025 rows where injured starters looked healthy, which mildly dilutes the QB-change signal. The 2025 diagnostic evaluation also had no QB-out information. This can't be changed in the frozen champion. |
| Do 2026 reports arrive in time? | **Not for the Friday stage.** nflverse's file had only 6 game statuses at Friday 17:03 ET; the final statuses (159) arrived between then and Saturday 06:00 ET. All 13 Friday-stage forecasts therefore had no verified final report. For example, Philadelphia's Friday forecast assumed Jalen Hurts, whom the official report lists Out. The t24h and later stages do have it (HOU–JAX t24h verified). NFL.com publishes the report on Friday afternoon; its archive (started Saturday) will measure the lag from now on. |

## B. Snap-based player model audit
- **Pregame safety:**
  - The real-data perturbation gate passes with 0 leaking columns (re-run in 7.1).
  - Weekly fits use only games before the week's first kickoff, so a Thursday game's EPA never enters that week's Sunday fit.
  - Lineups use the team's own prior games, including that Thursday game's snap counts. Those snaps are published the next day (2026 week-6 Thursday snaps were present by the Saturday 10:00 UTC download), well before Sunday forecasts.
- **Identity:** PFR→gsis matching covers 99.8–100% of snap share in every season 2016–2026. Unmatched players (3 in 2026, 5 snaps or fewer) are dropped.
- **Low-information players:** 7.8% (offense) and 8.0% (defense) of 2026 lineup snaps, against 5–6% before. They are valued at the shrunk league-average prior, not a replacement level, which may overrate unknown players. Documented, not changed: the registered challenger is frozen.
- **Current data:** the stale Phase 5 ratings (participation through 2025) agree with the snap model at 0.97–0.99 correlation in 2018–25, but only 0.52–0.88 in some 2026 weeks. The snap model is the one that sees 2026.
- **Labels:** every version's inputs now name their player model: "Phase 5 RAPM (participation through 2025, N days stale)" or "Phase 7 snap model (2026 snaps)".
- **Participation:** none is fabricated.

## C. Transparency (`lab/transparency.py`)
**New snapshots store, beside the forecast:**
- `champion_inputs`: QB per side, rule, injury report status and time, player model, missing features.
- `inputs` and `margin_ensemble` for each challenger.
- `live_qb_monitoring_only`: excluded from the content hash and never used by any model.

Existing archives are untouched.

**The Model Debate page shows, per game:**
1. what the champion knew;
2. what each challenger knew;
3. what live monitoring knows now (official report, weekly roster, Sleeper and v2, labelled *projected (sources agree)*, *conflicting* or *unavailable*);
4. after the game, the *confirmed* starters.

It also shows every archived pregame forecast for the game, separate from the newly calculated analysis. A warning appears when live monitoring disagrees with the champion's QB assumption.

## D. First live-weekend audit (`lab/audit7.py`, `python -m lab.cli audit`)
- **Scheduler:** 150 ticks with 0 errors. The task runs `pythonw -m lab.scheduler tick` independently of Streamlit (last result 0).
- **Stages:** 14 archived (13 Friday, 1 t24h), 13 missed (early-week, before the scheduler was installed), 157 pending.
- **Archive integrity:** every archive was made before kickoff, is read-only, matches its hash, and has no overwrites. Champion and challengers were saved together in 14 of 14.
- **Lag:** the Friday stages were archived at 02:38 UTC, 279 minutes after the scheduled time, as a within-deadline catch-up when the scheduler was installed. t24h was 1 minute late.
- **Changes between stages:** HOU–JAX gained its final report from Friday to t24h, and its champion probability was unchanged (0.684). The champion uses no injury features other than the QB rule.
- **Scoring:** no archived game has finished. Postgame scoring runs automatically after every refresh, and missing forecasts are never back-filled.
- **Phase 7 challenger:** registered at 14:25 UTC, so it first appears from the 17:00 UTC t24h stage onward.

## E. Prospective comparison (`lab/compare7.py`)
- **Method:** identical archived games only, per stage, covering:
  - accuracy, log loss, Brier score, 5-bin ECE and margin MAE;
  - QB projection correctness against the confirmed starters;
  - injury-report completeness;
  - first-vs-last forecast changes;
  - paired log-loss deltas with bootstrap 95% CIs.
- **Decision rule:** "accumulating evidence" until 128 games. The registered Holm-corrected rule still makes the decision, and nothing is promoted automatically.
- **Results so far: none** (0 completed archived games).

## F. Why the six models agree (`lab/shared_errors.py`, descriptive, walk-forward 2018–2026)
- **Identical inputs:** all six receive the same 85 features from 6 groups.
- **One signal:** one component explains 91% of prediction variance. The rating-margin difference alone explains 50–77% of each model's logit, and each model is explained 65–94% by the other five.
- **Agreement isn't confidence:** within the same probability band, unanimity adds nothing. 50–60% favourites won 51% when unanimous (297 games) and 55% when split (573). Vote counts must not be read as confidence; the Model Debate now says so.
- **Shared misses:** all six were wrong in 537 games (23%). The closing market was also wrong in 84.5% of those, so most shared misses were not predictable before kickoff. In 15.5% the market was right, the candidates for missing pregame information. In games where the QB projection turned out wrong, the market was right on 20% of shared misses, against 14% otherwise. QB-projection errors are not over-represented among shared misses (20.3% vs 20.9% overall).
- **Diversity:** the models need different information, not more model types.

## Commands
```
python -m lab.cli audit          # weekend audit (+ artifacts/phase7/stage_table.csv)
python -m lab.cli compare        # prospective three-version comparison
python -m lab.cli shared-errors  # shared-error diagnosis
```
