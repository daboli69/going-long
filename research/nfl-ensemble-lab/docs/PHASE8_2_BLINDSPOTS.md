# Phase 8.2: prediction blind spots and error discovery

- **Code:** `lab/blindspots82.py`. **Results:** `artifacts/phase82/`.
- **Prospective hypotheses:** `docs/PHASE8_2_PREREGISTRATION.md`, pushed as ab73ef3 at 20:01 UTC before any registered game.
- **Status of the numbers:** all historical figures are **exploratory**, because every season 2018–25 has been examined in
  earlier phases.

## 1. Live system
- **Task:** the real Windows task runs `pythonw.exe -W ignore "...\releases\run_tick.pyw"` from `releases\` (verified via
  `Get-ScheduledTask`).
- **Runs:** each run stamps `artifacts/scheduler/code_version.json` with release `lab-v8.1.0-ec56eb3`. All runs since the
  19:28 UTC switch completed with last result 0, with no errors and no launcher error log.
- **Rollback:** previous release `lab-v7.3.1-d9a650e`, plus a task-action backup.
- **Archives:**
  - Champion and both challengers are saved together in every stage snapshot (audit: 21 of 21 before this phase).
  - Market snapshots go to `data/raw/archive/market/`, read-only and separate from model inputs.
  - Drive-simulator distributions go to `artifacts/phase81/drive_sim_archive/` from the next stage on.
- **Postgame scoring** runs after every refresh. No archived game has finished yet.
- **ARI–LA 20:05 UTC t24h:** see the addendum at the end.

## 2. The 77-game champion-vs-market comparison
Recomputed from source: 77 unique completed 2026 games, with outcomes re-verified.

| Market quote | Market log loss | Champion log loss | Market minus champion [95% CI] |
|---|---|---|---|
| 24 h before kickoff | 0.649 | 0.659 | −0.010 [−0.059, +0.038] |
| Last pregame quote | 0.650 | 0.659 | −0.010 [−0.059, +0.039] |

Brier is 0.228 for the market and 0.234 for the champion.

- **The market was slightly better, not worse** (lower log loss is better), and the difference is not significant.
- **The Phase 8.1 report** gave these numbers correctly, but mislabelled the information as "equal". The champion's walk-forward
  probabilities use inputs up to kickoff, so they had *more* recent information than the 24-hour quote.
- **Correction:** a dated erratum was appended to `docs/PHASE8_1_MARKET.md`; the original table was not edited.

## 3. Champion error audit (out-of-fold, 2018–25, 2,219 games)
- **Overall:** accuracy 64.4%, log loss 0.630, Brier 0.220, margin MAE 10.17.
- **Calibration in the large is essentially perfect:** favourites were predicted to win 64.4% and won 64.4%. Excess log loss is
  −0.001.

| Slice | Notable finding (favourite predicted vs observed win rate) |
|---|---|
| Favourite band 75–80% (188 games) | 77.3% vs 72.3% (excess +0.062, z ≈ 1.6) |
| Favourite band 55–60% (414 games) | 57.5% vs 52.7% (excess +0.013) |
| Favourite band 80–90% (144 games) | 83.5% vs 87.5% (under-confident) |
| Weeks 1–4 (503 games) | 63.8% vs 61.6% (excess +0.009) |
| Weeks 9–18 | slightly under-confident |
| Home vs away favourite | log loss 0.616 vs 0.651. Away favourites are harder, but calibrated (62.1% vs 62.7%) |
| Predicted margin 7–10 (364 games) | 74.4% vs 72.0% (excess +0.026) |
| No verified injury report (291 games, mostly 2025) | excess +0.007 vs −0.002 with a report |
| Teams | Pittsburgh (+0.046), Atlanta (+0.042) and Green Bay (+0.037) have the highest excess; NYG (−0.045) and CHI (−0.040) the lowest. With about 135 games each, these spreads are consistent with noise |
| Seasons | excess ranges from −0.027 to +0.022, alternating with no trend |

## 4–5. Candidate blind spots, A–G (27 pregame conditions; `screen.csv`)
For each condition I measured:
- its frequency and log loss;
- excess log loss vs other games, with a bootstrap CI;
- signed miscalibration;
- a likelihood-ratio test *given the champion's probability* (condition × logit interaction, Holm across all conditions);
- how many seasons share the sign;
- a **walk-forward recalibration inside the condition** (the honest test of a targeted correction).

| Result | Conditions |
|---|---|
| No condition is significant after Holm | all 25 testable ones (Holm p = 1.0). The only nominal hit is a time-zone shift ≥ 2 (p = 0.047), not credible after 25 tests |
| Excess CI excludes 0 | none |
| Targeted correction would have helped (walk-forward) | only favourites > 80% (+0.013 inside the condition, +0.0005 overall) and two negligible ones. **Every other targeted correction made things worse** |
| Consistent across seasons | none: e.g. QB change 2+/5−, early weeks 5+/3−, favourites 70–80% 6+/2− (still not significant) |
| Champion handles it *well* | QB change / projected Out (72 games): log loss 0.597, excess −0.034, i.e. better than its stated confidence. Recent-form shift: −0.035 |
| Too few games or no variation | stale player model, unknown QB (0 games in completed seasons) |

**Conclusion:** the champion has no statistically credible, pre-kickoff-detectable blind spot in 2018–25. Its errors are what a
calibrated 64%-accurate forecaster produces.

## 6. Shared errors (the 514 all-six-wrong games in 2018–25; 537 including 2026)
| Group | Games | Mean favourite probability | Mean model disagreement |
|---|---|---|---|
| All six wrong | 514 | 0.657 | 0.044 |
| Unanimous right | 1,055 | 0.694 | 0.048 |
| Split votes | 650 | 0.554 | 0.063 |
| Market right, champion wrong | 186 | 0.563 | 0.049 |
| Champion right, market wrong | 143 | 0.567 | 0.054 |

- **Pregame conditions don't predict unanimous misses.** Given the favourite-probability band, no condition is associated with
  all six models being wrong (all Holm p = 1.0; closest: OL churn OR 1.25 and recent-form shift OR 0.71, both p > 0.05).
- **They are ordinary upsets** of moderate favourites (mean 65.7%), not a distinct class of game.
- **Model disagreement adds no information** beyond the combined probability. Walk-forward, the gain is +0.0009 (CI −0.0024 to
  +0.0040), and it changes sign by season. Phase 8's in-sample p = 0.024 did not survive out of sample.

## 7. Market disagreement (closing line, unequal information; market-informed and kept separate)
- **Large disagreements cluster in personnel situations.** In the top 10% of champion–market disagreements:

  | Condition | Odds ratio | p |
  |---|---|---|
  | QB change | 3.7 | < 1e-4 |
  | Concentrated unit out | 2.1 | 0.0005 |
  | Weeks 1–2 | 1.9 | 0.001 |
  | Defensive or OL absences | 1.9 / 2.1 | |
  | Inexperienced QB | 1.5 | |

  The market reacts strongly to QB and injury news.
- **But it isn't more accurate there.** Its log-loss edge in those games equals its edge everywhere: QB change 0.029 vs 0.021,
  concentrated outs 0.025, weeks 1–2 0.006, OL 2+ out 0.043, all with CIs including 0. The market's advantage is broad, not
  concentrated where it disagrees with the champion's personnel view.
- **Timing:** the opening line is level with the champion, the closing line is better, and the 24 h line is between. The edge
  appears to come with time, but historical timestamps are too coarse to prove it. That is pre-registered as P3.
- **Not inferred:** betting volume, informed money, or causation.

## 8. Targeted corrections
No credible blind spot emerged, and walk-forward within-condition recalibration hurts in almost every condition. **No correction
was built, and no challenger was registered.** I stopped at the diagnostic stage, as the protocol requires.

## 9. Three hypotheses for prospective testing (pre-registered; future games only)
| ID | Hypothesis | Exploratory evidence | Sample | Supported if |
|---|---|---|---|---|
| P1 | Early-season overconfidence (football-only) | −0.022 (about 1 SE) | 256 week-1–4 games | CI of fav-side miscalibration < 0 |
| P2 | OL disruption (≥2 OL starters confirmed out) raises excess log loss (football-only, with a market companion) | +0.027 (CI −0.04 to +0.10); market edge 0.043 vs 0.020 | 150 games | CI of the excess difference > 0 |
| P3 | The market's advantage grows from Friday to final stage (market-informed timing) | open ≈ champion, close > champion | 128 paired games | difference > 0 with CI excluding 0 |

Each is evaluated once at its sample size, with Holm across the three. Progress shows on the dashboard
(`lab.blindspots82.prospective_eval`).

## 10. Integrity
- **Unchanged:** the champion, the six models, both challengers, all model artifacts and every archive. The registry still
  tracks the same three versions.
- **Inputs:** no new model feature was introduced. All condition flags are pre-kickoff columns already covered by the leakage
  gate.
- **Rejected findings are all recorded in this report and the CSVs:** every condition, the disagreement signal, and targeted
  corrections.

## Answers
1. **Is the pinned scheduler working?** Yes (section 1).
2. **Was the 77-game comparison corrected?** It was verified and the erratum added. The market was slightly better (−0.010, n.s.),
   and the information was not exactly equal.
3. **What are the largest measurable weaknesses?** Mild overconfidence in the 75–80% band and in weeks 1–4, and harder away
   favourites. None is significant.
4. **Which are statistically credible?** None after multiple-comparison correction.
5. **Which are random losses?** Effectively all of them. Calibration in the large is exact.
6. **Are the shared-error games different?** No. They are upsets of moderate favourites, with no distinguishing pregame pattern.
7. **Does model disagreement contain useful information?** No (walk-forward gain about 0).
8. **Does market disagreement identify missing football information?** It flags QB and injury situations, but the market isn't
   more accurate in them. No missing football input is identified.
9. **Which blind spots are detectable before kickoff?** All the candidate conditions are, but none is predictive.
10. **Which findings are consistent across seasons?** None.
11. **Are targeted corrections justified?** No.
12. **Which hypotheses deserve prospective testing?** P1–P3.
13. **Are existing models and archives unchanged?** Yes.
14. **What should Phase 8.3 prioritize?** Let the prospective archive answer P1–P3 and the challenger questions.
    - The most valuable engineering is reliable, stage-matched market and injury timing data.
    - The most promising source of *new* information is whatever the market learns between Friday and kickoff (P3). It should be
      measured before more modelling.
    - Further historical mining of 2018–25 is unlikely to be informative.

## Addendum: first pinned-release stage forecast (ARI–LA t24h, 2026-10-17)
- **Run:** the tick started at 20:05:01 UTC under `lab-v8.1.0-ec56eb3`.
- **Timing:** the snapshot was archived at 20:05:47, 46.7 s after the tick started and labelled **on_time**. The
  `compute_seconds` value now correctly includes the refresh.
- **Integrity:** the champion `v20261016_212540` and both challengers were saved together, and the file is read-only.
- **Research archives:** the post-forecast hook then archived a new ESPN/DraftKings odds snapshot
  (`espn_odds_20261017T200547Z_*.json`, 13 games) and the drive-simulator distribution (`2026_06_ARI_LA_t24h.json`).
- **Errors:** none.
