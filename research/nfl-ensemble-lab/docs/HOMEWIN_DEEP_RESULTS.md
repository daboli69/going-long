# Deep home-win model: results

Run 2026-10-28. Protocol `741a13e7` (written before any fit), code `555d5317`, one look. Full numbers:
`reports/homewin_deep/backtest.json`. Reused history, not an untouched holdout (see the preregistration).

**Verdict: no candidate passed the gate. Nothing is promoted. Plain Elo remains the best of the eight in the
walk-forward.**

## Data checks (all passed)
- Scores: all 6,330 played regular-season games 2002-2026 week 7 matched ESPN exactly. The postponed duplicate of 2014
  NYJ@BUF (snow, moved to Detroit) is resolved by taking the completed event.
- Neutral sites: 2,911 games compared (nfldata `location` vs ESPN, seasons where ESPN flags any). There was one
  disagreement: 2021 GB@NO, moved to Jacksonville by Hurricane Ida. nfldata is right and the game is allowlisted with that
  reason.
- Play-by-play: 12,660 team-games (two per played game) and 15,554 QB-games. No play failed to map to a game.
- Leakage: corrupting every result, play, injury row and quote at or after T_w left the inputs for 2016 w3, 2020 w12,
  2024 w9 and 2026 w6 unchanged. The negative control (cutoff 8 days late) was detected, so the check can fail.

## Walk-forward 2012 to 2026 week 7 (3,756 scored games)

| Model | Log loss | Brier | Accuracy | ROC AUC | ECE |
|---|---:|---:|---:|---:|---:|
| elo | 0.6332 | 0.2215 | 64.3% | 0.6893 | 0.0268 |
| elo_platt | 0.6329 | 0.2214 | 64.0% | 0.6901 | 0.0265 |
| xgb_deep | 0.6354 | 0.2225 | 63.4% | 0.6855 | 0.0214 |
| xgb_deep_platt | 0.6355 | 0.2225 | 63.4% | 0.6855 | 0.0192 |
| margin | 0.6392 | 0.2243 | 63.2% | 0.6776 | 0.0173 |
| margin_platt (primary) | 0.6397 | 0.2244 | 63.0% | 0.6777 | 0.0228 |
| xgb_v1_platt | 0.6415 | 0.2252 | 63.4% | 0.6749 | 0.0243 |
| xgb_v1 | 0.6449 | 0.2262 | 63.3% | 0.6746 | 0.0308 |

## Gate vs elo (Bonferroni m = 4, 98.75% week-cluster CIs)

| Candidate | Log-loss delta [CI] | DM p | Brier delta | Seasons better | Result |
|---|---|---:|---:|---:|---|
| margin | +0.00599 [-0.00165, +0.01335] | 0.071 | +0.00275 | 3/15 | fail |
| margin_platt | +0.00657 [-0.00135, +0.01418] | 0.053 | +0.00286 | 4/15 | fail |
| xgb_deep | +0.00224 [-0.00372, +0.00755] | 0.354 | +0.00102 | 6/15 | fail |
| xgb_deep_platt | +0.00228 [-0.00409, +0.00767] | 0.360 | +0.00097 | 7/15 | fail |

Positive deltas mean worse than Elo. The primary candidate was worse than Elo in 11 of 15 seasons. Its fitted terms have
sensible signs and sizes: pass EPA edge 24.5 points per EPA/play, run 18.4, QB delta 10.4, home field 2.1, and sigma
13.4 to 14.2. That points to a weaker signal, not a sign or scale bug. Per the protocol, nothing was re-tuned after the
look.

## Why the QB adjustment did not help
At the weekly decision time (first kickoff minus 90 minutes, usually Thursday), Friday designations and Sunday
inactives do not exist yet. Pre-decision injury rows covered 0% of team-games in 2012-2014 and 2025 (no row
timestamps), 23-48% in 2015-2024, and 5% (28 of 544) in 2026. No official inactives are archived. Only 27 scored
games carried a QB-change flag in 15 seasons. A per-game decision time (kickoff minus 90 minutes for each game) would
see much more; that is a new hypothesis and needs its own preregistration.

## Market (2026 only, descriptive, uncorrected 95% CIs)
GOING T1 quotes exist only for 2026. Close (latest before kickoff): 105 games, market log loss 0.6638. Decision time:
90 games, 0.6793. Every model's interval vs the close includes zero. One of the 16 decision-time comparisons
(xgb_deep_platt, -0.035 [-0.070, -0.002]) excludes zero. With 16 uncorrected tests on 90 games, that is expected by
chance and is not evidence of an edge. No betting return was measured, and a scoring backtest is not a return backtest.

## Missing data (exact)
- Timestamped market: 2012-2025 entirely. Undated SBR and AusSportsBetting lines were not used, per the protocol.
- Injury row timestamps: 2012-2014 (no nflverse file loaded before 2015 in the lab archive) and 2025 (file has no
  `date_modified`).
- Official inactives: none archived.
- Historical ESPN FPI: unusable, because predictor values are modified after games. It is recorded prospectively only.
- Offseason QB moves (trades, signings, rookies) are invisible at week 1. The expected starter is last season's.

## Prospective record (the untouched test)
2026 week 8 frozen 2026-10-28 before the first kickoff: 14 games, every model plus market and FPI at freeze time.
SHA-256 `00a6a181269e98b5a57742177f16bbe6182ae46ed7caab1e742691a3d4e1943e`, logged in
`reports/homewin_deep/freeze_ledger.jsonl`. The archive is write-once and read-only. Run
`python scripts/home_win_deep.py freeze` each week before the first kickoff and `score` after the games.
