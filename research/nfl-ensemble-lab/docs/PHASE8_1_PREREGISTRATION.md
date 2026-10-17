# Phase 8.1 pre-registration: market intelligence

**Written 2026-10-17, before any Phase 8.1 comparison was computed.** It is committed on its own, so the git history proves
the order. Earlier phases reported the champion and the closing line side by side as a benchmark, so the general fact
that "the closing market is strong" is already known. Nothing below has been examined.

## Data and timestamp classes (every price is labelled with exactly one class)
| Class | Meaning | Sources |
|---|---|---|
| T1 timestamp-verified pregame | a quote with a recorded time before kickoff | GOING `nfl_betting.json` git history (multi-book quotes with per-book `last_update`; 2026, from Sep 9); lab stage snapshots `market_at_snapshot` (2026, from Oct 16); the new prospective ESPN/DraftKings archive |
| T2 opening, time unrecorded | the first posted line; exact time unknown (typically early in game week) | Sportsbook Review archive: opening spread and total, 2016–2021 |
| T3 closing, untimestamped | the final line before kickoff | nflverse/nfldata `games.csv` (spread, total, moneylines, 2016–2026); SBR closing spread, total and moneyline |

- T3 prices are used **only** for retrospective benchmarking and market-efficiency questions. They are always labelled
  *unequal information*, because a closing line knows inactives and late news that an early-week forecast cannot.
- T2 is used as the early-week market, labelled *approximately* equal information.

**No-vig conversion:**
- **Primary:** multiplicative (proportional) normalisation of implied probabilities.
- **Secondary, reported:** additive and power (exponent solved per game).
- **Spreads without moneylines:** P(home) = Φ(spread / σ), with σ fitted walk-forward on earlier seasons.

## Windows
- **Champion out-of-fold predictions:** 2018–2026.
- **Development:** 2018–2022, of which the T2 open lines cover 2018–2021.
- **Research-exposed check:** 2023–2025.
- **Prospective:** archived 2026 games only.
- **Walk-forward:** every fitted mapping (σ, combination weights) uses only seasons before the target season.

## Hypotheses (exactly these tests; Holm correction across the five primary tests H1–H5)
- **H1 (A: disagreement predicts champion error):** in the logistic regression of the outcome on logit(champion) and
  d = logit(market) − logit(champion), the coefficient on d is > 0. Tested against the T2 opening market (2018–21).
  Also reported against T3 closing (2018–22), labelled unequal information.
- **H2 (B: line movement):** given the closing spread probability, the opening-to-closing movement adds nothing. The test is
  movement's coefficient in outcome ~ Φ(close) + movement (SBR 2016–21). **Expected null** (market efficiency).
  A secondary, reported-only test: given the opening line, movement predicts the outcome.
- **H3 (C: stale inputs):** among the 10% of games with the largest |d| (T2 open, 2018–21), pre-specified pregame flags are
  over-represented in games where the market was right and the champion wrong. The flags are: QB change projected, verified
  QB out or questionable, ≥2 non-QB starters confirmed out, coach new or changed, week ≤ 3, rest difference ≥ 3 days.
  Discovered on 2018–21 with a per-flag Fisher test; a flag counts only if it **reproduces** on 2022–25 with the closing
  line. Any surviving flag gets exactly one football-only test: champion plus that flag's interaction with the champion
  logit, walk-forward, **without any market input**, against the recalibrated champion.
- **H4 (D: margins):** the margin forecast from the T2 opening spread beats the champion's predicted margin (MAE, 2018–21).
  The secondary test is whether a walk-forward linear blend of the champion margin and the spread beats the spread alone.
- **H5 (Question A: combination):** the walk-forward combination C = LR(logit champion, logit market) beats **market
  alone** M on log loss. Primary market: T3 closing moneyline, 2019–22. Same test with the T2 opening spread probability,
  2019–21. Beating the recalibrated champion R is reported but is **not** evidence of football intelligence, since copying
  the market already does that.

## Decision rules
- **Market-informed challenger** (at most one): registered only if H5 shows C beating M on development with Holm p < 0.05,
  the gain is ≥ 0 on the 2023–25 check, **and** a timestamped live market feed is archived at every stage. It would be
  labelled market-informed, never "independent football".
- **Football-only improvement:** only through the H3 path, and only if its football-only test beats R on development (Holm
  across the surviving flags, p < 0.05) and is ≥ 0 on the 2023–25 check.
- Otherwise nothing is registered, and the negative results are reported.

## Drive simulator (Phase 8 E), evaluated as a scoring-distribution model
- **Metrics:** margin MAE and total MAE against (a) the champion margin, (b) a zero-margin baseline, (c) a league-mean total
  baseline, and (d) the T3 closing spread and total (labelled unequal information).
- **Distribution quality:** coverage of the 10–90% margin and total intervals (target 80%), and the PIT histogram.
- **Prospective:** prospective tracking of its distributions starts now, kept separate from the winner challengers.
