# Phase 8.1: market intelligence, blind spots and independent validation

- **Pre-registration:** `docs/PHASE8_1_PREREGISTRATION.md`, pushed as 7f9eec8 at 18:48 UTC before any comparison.
- **Code:** `lab/market81.py` (data), `lab/market81_eval.py` (analyses), `lab/scoring81.py` (prospective drive-simulator archive).
- **Results:** `artifacts/phase81/`.
- **Unchanged:** the champion, the six models, both challengers, the specialists and the archives.

## 1. Live runtime
- **The release is built and ready:** `lab-v7.3.1-d9a650e` is built, tested (157 passed) and prewarmed, `CURRENT.json` points
  at it, and `run_tick.pyw --check` resolves the right package and cache slot.
- **The Windows task is not switched:** it still runs the development checkout (`task_mode: development`).
- **Why:** the switch command (`python -m lab.release switch-task release --confirm`) was **refused by the permission system**
  ("Account & Standing-Rule Changes"), even with the instruction in chat. It must be run by Travis or allowed explicitly; see
  "Approval needed" below.
- **Live path changes in this phase:**
  - an exception-safe research hook in `lab/scheduler.py` that runs *after* official snapshots are saved;
  - no change to any feature-building module, so the Phase 7.3 caches stay valid.

## 2–3. Market data recovered (every price carries a timestamp class)
| Source | Content | Coverage | Timestamp class |
|---|---|---|---|
| nfldata `games.csv` | closing spread, total, moneylines, spread/total odds | 2016–2026 | **T3** closing, untimestamped. For future games it is the current line at download time |
| Sportsbook Review archive (free, public pages) | opening and closing spread and total, closing moneyline; book unnamed | 2007–2021 (used 2016–21: 1,622 games, 0 unmapped teams) | **T2** opening, time unrecorded / **T3** closing |
| GOING `data/nfl_betting.json` git history (read-only; the paid feed was not called) | 142,408 pregame quotes from **15 books**, h2h, spreads and totals, each with the book's `last_update` | 2026 weeks 1–7: 107 games, about 200 consensus points per game | **T1** timestamp-verified |
| Lab stage snapshots `market_at_snapshot` | nfldata line at each forecast stage | from 2026-10-16 | **T1** (our refresh time) |
| **New:** ESPN scoreboard odds archive | DraftKings opening and current moneylines, spreads and totals | prospective, from 2026-10-17 18:54 UTC | **T1** (our retrieval time; the source gives no quote time) |

- **Validation:** SBR closing spreads correlate 0.994 with nfldata closing spreads, and 96% agree within one point (the
  differences are book and timing). Lines moved between open and close in 84% of games, by 1.7 points on average.
- **Not used:** aussportsbetting.com refuses automated downloads (403), and it was not pursued.
- **No paid feeds or keys were used.**
- **No-vig methods:** multiplicative (primary), additive and power give the same market log loss (0.6087–0.6089).

## 4. Champion vs market on identical games
| Comparison | Information | Games | Champion LL / Brier / Acc. | Market LL / Brier / Acc. |
|---|---|---|---|---|
| Closing moneyline, 2018–25 | **unequal** (the market knows inactives and late news) | 2,219 | 0.630 / 0.220 / 64.4% | **0.609** / 0.211 / 66.4% |
| Opening spread, 2018–21 | approximately equal (opening time unrecorded) | 1,083 | **0.628** / 0.219 / 64.2% | 0.630 / 0.220 / 63.3% |
| Multi-book consensus 24 h before kickoff, 2026 | equal, T1 timestamped | 77 | 0.659 / n/a / 57.1% | 0.649 / n/a / 62.3% (descriptive only) |

- **By season:** the closing market beats the champion in every season except 2018.
- **By favourite band:** the closing market is better in every band, with the largest gap above 70%.
- **Margins (closing spread):** spread MAE 9.8–10.7 vs champion 8.9–11.1, so the spread is better every season.
- **Who was right (closing line, 2,219 games):**

  | Outcome | Share |
  |---|---|
  | Both right | 58.0% |
  | Both wrong | 27.2% |
  | Champion right, market wrong | 6.4% (143 games) |
  | Market right, champion wrong | 8.4% (186 games) |

## 5. Blind spots (H3)
- **Method:** among the 10% of games with the largest champion–market disagreement, I checked whether six pre-specified pregame
  flags were over-represented where the market was right and the champion wrong. The flags: QB change, QB out or questionable,
  2+ non-QB starters out, coach change, week ≤ 3, rest difference ≥ 3.
- **Discovery, 2018–21 (opening market):** nothing was significant. Coach change had odds ratio 5.2, but on only 2 games
  (Holm p 0.84).
- **Reproduction, 2022–25 (closing market):** nothing; no flag survived.
- **So:** the disagreements are not explained by any QB, injury, coaching, rest or early-season input the lab has. There is no
  supported "stale input" story, and no football-only feature was tested as a result.

## 6. Pre-registered hypotheses (Holm across H1–H5)
| Test | Result | p (Holm) |
|---|---|---|
| **H1** disagreement with the **opening** market predicts champion error | **supported**: coefficient 0.51 on d = logit(market) − logit(champion), i.e. move about halfway toward the opening line (1,083 games). Against the closing line (unequal) the coefficient is 0.96, so nearly all the way | 0.0006 (**0.003**) |
| **H2** given the closing line, opening-to-close movement adds information | **no**: coefficient −0.02 (1,615 games), consistent with market efficiency. Given the *opening* line, movement is strongly predictive (p 5e-10): the close absorbs it | 0.46 (1.0) |
| **H3** stale-input flags explain market-right disagreements | **no** flag survives | (1.0) |
| **H4** the opening spread beats the champion margin | margin MAE 10.35 vs 10.47 (−0.12): directionally yes, not significant. A champion + spread blend equals the spread alone (10.47 vs 10.47) | 0.09 (0.36) |
| **H5** champion + **closing** market beats market alone | **no**: combination 0.6130 vs market 0.6088 (gain −0.0042, CI −0.0095 to +0.0012). The champion adds nothing to the close | 0.94 (1.0) |
| H5 secondary, with the **opening** market | the combination beats both. 2019–21: combination 0.6318, champion 0.6336, opening market 0.6357 (gain vs raw open +0.0039, p 0.21; vs recalibrated open +0.0073, p 0.04). Secondary and not Holm-significant | not primary |

## 7. The two questions
- **A. Can market information improve predictions?** Yes, trivially: the closing market alone beats the champion. But the
  champion adds nothing to the closing market. Against the opening line, the two are complementary (H1, H5 secondary). That
  improvement depends on market input, so it is **not independent football intelligence**.
- **B. Does market disagreement reveal missing football information?** Not with the lab's pregame inputs (H3 negative). The
  market's extra skill comes from information the lab doesn't have, or from aggregation, not from inputs the lab has but
  misuses.

## 8. Market movement and timing
- **Historical:** movement is real (84% of games move, 1.7 points on average) and predictive relative to the opening line, but
  fully priced in by the close.
- **2026 T1 history:** a median of 15 books per game, first quotes about 17 days before kickoff, last pregame quotes a median of
  about 2.6 hours before. The mean absolute move from first to last quote is 0.32 logit.
- **Not inferred:** betting volume, "sharp" action, or causation. No data supports them.
- **Prospective work** (relating each official injury update to the next market move) now has the data it needs: ESPN odds,
  the NFL.com timeline and GOING's history.

## 9. Prospective market archive
`market81.archive_espn_odds()` stores one immutable, read-only file per distinct odds content, with provider, opening and current
prices and our retrieval time. It runs only after a tick's official forecasts are saved, with a 15 s timeout, and never raises.
It is separate from champion inputs, and no forecast hash or archive is touched. Nothing is back-filled.

## 10. Drive simulator as a scoring model
| | Development 2018–22 | Exposed 2023–25 | Live 2026 |
|---|---|---|---|
| Margin MAE: simulator / champion / zero / closing spread (unequal) | 10.52 / 10.15 / 11.14 / 9.88 | 10.52 / 10.19 / 11.24 / 9.79 | 10.93 / 10.30 / 10.42 / 9.80 |
| Total MAE: simulator / league-mean baseline / closing total (unequal) | 11.78 / **11.28** / 10.63 | 10.95 / **10.71** / 10.09 | 11.58 / 12.26 / 10.59 |
| 80% interval coverage: margin / total | 80.6% / 92.1% | 77.3% / 91.3% | 74.7% / 93.7% |

- **Margins:** it beats the zero-margin baseline but not the champion.
- **Totals:** it is **worse than predicting the league average** in historical seasons.
- **Intervals:** margin intervals are well calibrated (PIT roughly uniform, normal approximation from the 10–90% range), but
  total intervals are too wide.
- **Prospective tracking** of its distributions has started (`artifacts/phase81/drive_sim_archive/`, one immutable file per game
  and stage). It is not promoted.

## 13. Challenger decision
- **Market-informed challenger:** H5 primary failed, so no challenger was registered. The opening-line complementarity is
  secondary, not Holm-significant, and depends on T2 lines with no live T2 feed. Prospectively, the new ESPN archive provides an
  opening price.
- **Football-only:** H3 found nothing, so no football-only test was run.
- **Registry:** unchanged. The champion and two challengers are still tracked.

## Approval needed (live runtime)
Run in a terminal in the lab folder, between scheduler ticks and not within 20 minutes of a stage:
```
.venv\Scripts\python.exe -m lab.release switch-task release --confirm
.venv\Scripts\python.exe -m lab.release status
```
- **Check:** `status` should then show `task_mode: pinned`, and `last_launcher_tick` should update within 5 minutes.
- **Rollback:** `python -m lab.release switch-task development --confirm`. A backup of the old task action is saved first.
- **Release included:** release `lab-v8.1.0-ec56eb3` (this phase's commit) was then built, tested (169 passed), prewarmed (cold
  129 s, warm 13.5 s) and activated, with `lab-v7.3.1-d9a650e` as its rollback. Switching the task therefore runs the
  Phase 8.1 code, including the market and drive-simulator archives.

## Phase 8.2 priorities
1. Prospective, equal-information champion vs market evaluation at each stage, using the new T1 archive. That is the only clean
   test left.
2. Relate official injury and QB updates (NFL.com timeline) to subsequent T1 market moves, to measure whether the market reacts
   to information the lab already has.
3. Decide whether a market-informed forecast is wanted as a separate, clearly labelled product. If so, pre-register it against
   the market alone, prospectively.

## Erratum (added 2026-10-17 in Phase 8.2; the table above is left as originally published)
**The 77-game 2026 comparison was recomputed from source data:**
- `artifacts/phase81/timestamped_2026_games.csv`: 77 unique completed games, with outcomes re-verified against the games table.

| Market quote | Market log loss | Champion log loss | Market minus champion [95% CI] |
|---|---|---|---|
| 24 h before kickoff | 0.649 | 0.659 | −0.010 [−0.059, +0.038] |
| Last pregame quote | 0.650 | 0.659 | −0.010 [−0.059, +0.039] |

Brier is 0.228 for the market and 0.234 for the champion.

**Corrections:**
1. **Lower log loss is better, so on these games the market was slightly better than the champion, not the reverse.** The
   difference is not statistically distinguishable from zero.
2. **The row was mislabelled "equal".** The champion's 2026 walk-forward probabilities use every pregame input up to kickoff,
   including the final injury report. A 24-hour-old market quote has *less* recent information, so this is approximately
   equal, slightly favouring the champion. It is not an exact equal-information contest. Exact stage-matched comparisons start
   with the prospective archive (Phase 8.2 hypothesis P3).
