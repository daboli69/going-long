# Phase 11 pre-registration: market-blend shadow challenger

**Written 2026-10-26, before any Phase 11 code or prospective result.** This file is committed and pushed on its own, so the
git history proves the order. The weights below were fitted before this file was written. No prospective score for the
challenger, and no 2022–2025 score with these weights, has been computed.

## Why
- **H5 primary (Phase 8.1) failed:** the champion adds nothing to the closing line (gain −0.0042, CI −0.0095 to +0.0012).
- **H5 secondary was positive:** against the *opening* line the two were complementary. On 2019–21 the walk-forward
  combination scored 0.6318, against 0.6336 for the champion and 0.6357 for the opening market (p 0.04 against the
  recalibrated open; secondary, not Holm-significant).
- **H1 agreed:** given the champion, disagreement with the opening line predicts the outcome (coefficient 0.51, Holm p 0.003).
- **Live 2026 weeks 6–7 (26 final-stage games), already seen:** champion log loss 0.774, closing market 0.696. This is the
  motivation, not evidence. Those games are scored below as descriptive only.

The challenger uses market input, so it is **not independent football intelligence**. It is a shadow forecast, kept apart
from the champion, and nothing about the champion, the two challengers or the scheduler changes.

## The challenger (frozen)
p = σ(a + b_c · logit(p_champion) + b_o · logit(p_open))

| Weight | Value |
|---|---|
| a (intercept) | −0.13190614801204809 |
| b_c (champion) | 0.2569285247107809 |
| b_o (opening market) | 0.8164881145183679 |

- **logit:** probabilities are clipped to [1e-4, 1 − 1e-4] first, as in `lab/market81_eval.py`.
- **p_champion:** the champion's calibrated home-win probability (`p_champion` in the stage snapshot).
- **p_open:** the opening moneyline, made no-vig by multiplicative normalisation of the two implied probabilities.

### How the weights were fitted
- **Data:** the champion's walk-forward out-of-fold probability (`p_weighted_average`, `lab.specialists.baseline.load_oof`)
  joined to the AusSportsBetting opening moneylines (`Home Odds Open`, `Away Odds Open`, decimal) in
  `data/raw/market/aussportsbetting_nfl.xlsx`, matched by `lab.upsets85.match_asb`.
- **File:** SHA-256 `6719592dcfe4838836f850649276ad7a303ca242a3f71b13f9e96088d5673851`. It is local and never committed.
- **Seasons:** 2018–2021, all game types with a win or loss (ties dropped): **1,083 games** (265 / 266 / 268 / 284).
  The plan allowed 2014–2021, but champion out-of-fold probabilities start in 2018, so nothing earlier can be used.
  2022 and later are never used for fitting.
- **Why ASB and not SBR:** SBR has only opening *spreads*, which need a fitted σ to become probabilities. ASB has opening
  *moneylines*, the same quantity the live ESPN/DraftKings archive records. ASB is the primary and only fitting source.
- **Model:** unpenalised logistic regression (`LogisticRegression(C=1e6)`), with an intercept, as in H5.
- **Stability, seen before freezing (leave one season out):** b_c ranged 0.09–0.45 and b_o 0.73–0.96; the intercept ranged
  −0.20 to −0.09. The champion weight is noisy. The negative intercept says 2018–21 openers over-priced the home side
  (2020 was played mostly without crowds). Both are recorded risks, not reasons to refit.

## Live input
- **Opening line:** for each game and stage, the earliest file in the ESPN odds archive (`data/raw/archive/market/`,
  provider DraftKings) retrieved **before that stage's snapshot time** (`predicted_at`) that has both opening moneylines
  (`home_ml_open`, `away_ml_open`). A row matches a game on home team, away team, and kickoff within 24 hours.
- **Fallback:** if no such opener exists, the challenger equals the champion for that game and stage, and the row is
  flagged `fallback_no_opener`. The archive started 2026-10-17 18:54 UTC, so earlier games mostly fall back.
- **Closing market (secondary benchmark):** the latest archived DraftKings current moneyline (`home_ml_close`,
  `away_ml_close`) retrieved before kickoff, made no-vig the same way. Games without one are left out of the secondary test.

## Tests
- **Primary:** final-stage log loss of the challenger against the champion on the same games, with the existing Phase 3 rule:
  at least **128** scored final-stage games, and a paired bootstrap 95% CI of (challenger − champion) that lies wholly
  **below zero**. The bootstrap is `lab.prospective._paired` (2,000 resamples, seed 0). It is evaluated once, when the
  128th game is scored. Fallback games are included (their difference is zero), and the opener-available subset is
  reported beside it.
- **Secondary:** the same comparison against the closing market, on games with both an opener and a closing quote.
  Reported only; it cannot promote anything.
- **Counted games:** only final-stage snapshots made after this file's commit time. Weeks 6–7 of 2026, and any other game
  whose final snapshot came earlier, are reported as **descriptive only** and never count toward 128.
- **Also reported, never tested:** every other stage (early, early_week, friday, t24h, t90, t60); accuracy and Brier;
  the fallback rate.
- **Retrospective check, descriptive only:** the frozen weights on 2022–2025 ASB openers against the champion's
  out-of-fold probability. These seasons were exposed in Phase 8 (closing-line work), so this is not a holdout and not a gate.

## Rules
- **No promotion without Travis's approval,** even if the primary test passes. Promotion is never automatic.
- **Separate module:** `lab/market_blend11.py` scores from the immutable stage snapshots and the ESPN archive. It reads them
  only. It writes only to `artifacts/phase11/`.
- **No live change:** the pinned scheduler release, the Windows task, the champion, both challengers and every archive are
  unchanged. The challenger is not written into snapshots.
- **No refit:** the weights above are final. Any change is a new pre-registration with a new name.
- **$0:** no paid feeds or keys.

## Known limitations
- The ASB opener's time is unrecorded (T2). DraftKings posts lookahead lines up to two weeks early, so the live "open" may
  be earlier, and staler, than the 2018–21 openers the weights were fitted on.
- The champion's historical probabilities are walk-forward out-of-fold values, while the live champion is one fixed model
  (v20261016_212540). Their calibration may differ.
- 128 final-stage games needs about half a season, and the true gain may be smaller than the test can detect.
