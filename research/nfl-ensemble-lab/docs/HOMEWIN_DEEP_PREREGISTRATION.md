# Deep home-win model: pre-registration

Written 2026-10-28, before any feature, fit or result of this study was built. Local lab only. No change to the lab
champion, its challengers, the scheduler, the Windows task or GOING. $0 spend. Nothing is promoted by this study.

**Question (unchanged from `scripts/xgb_home_win.py`).** Probability that the home team wins each regular-season NFL game.

**Data reuse disclosure.** Seasons 2016-2025 have been used by earlier lab phases, and the existing Elo/XGBoost script was
run on 2025-2026 on 2026-10-28. The walk-forward backtest is therefore *reused history*, not an untouched holdout. The only
untouched test is the prospective freeze below.

## Decision time
For week w of a season, **T_w = first kickoff of the week minus 90 minutes** (kickoff times from ESPN, UTC). Every model
and every game of the week uses only data available before T_w. This matches one weekly freeze before the first kickoff.
Consequence, accepted in advance: Friday injury designations and Sunday inactives are *not* visible for Sunday games.

## Raw inputs (automatic, cached, provenance recorded)
1. **Schedule/scores:** api.nfldata.org `/v1/games` (as in `xgb_home_win.py`).
2. **Kickoff times, neutral flags, score cross-check:** ESPN public scoreboard API.
3. **Play-by-play:** nflverse `play_by_play_{season}.parquet`, 2002-current, via `lab.sources.download_pbp` (manifest
   with sha256). Plays = regular season, `pass == 1` or `rush == 1`, `epa` not null, excluding no-plays, kneels, spikes and
   two-point tries. Pass = dropbacks (incl. sacks, scrambles).
4. **Injuries:** `lab.availability.load_injury_rows`, rows with `available_at < T_w` only. Expected coverage 2016-2024
   and 2026; 2025 has no row timestamps (missing, reported).
5. **Official inactives:** `lab.inactives10` archive, `observed_at < T_w` only. Expected coverage: none (missing, reported).
6. **Market:** GOING T1 quotes (book `last_update`, read from GOING git history via `lab.market81`), multi-book median
   no-vig home probability. Two benchmarks per game: *close* = latest consensus before kickoff, *decision* = latest before
   T_w. No timestamped quote = missing. Undated lines (nfldata `spread_line`, SBR, AusSportsBetting) are never used.

## Models (all fixed here; 8 probability series)
- **elo:** `add_elo_pregame` from `xgb_home_win.py`, parameters unchanged.
- **xgb_v1:** `xgb_home_win.py` FEATURES and XGB_PARAMS, refit every week on all earlier games.
- **margin (primary candidate).**
  - Team ratings: weighted ridge per season on per-team-game offense values, y = mu + O_offense + D_defense + h*home.
    Four ratings: pass EPA/play, run EPA/play, pass success rate, run success rate. Row weight = plays / mean plays.
    Prior: O, D shrink toward **rho = 0.5** times the team's end-of-previous-season rating with penalty **lambda = 4**
    game-equivalents; mu and h unpenalized. Fit on the season's games before T_w (week 1 = prior only).
  - Edge = (O_home + D_away) - (O_away + D_home) for each rating.
  - **Starting QB at T_w:** the QB with the most dropbacks in the team's latest game before T_w. If that QB is listed
    Out, Doubtful, IR or Suspended in pregame injury rows (or inactive in official inactives) available before T_w, the
    expected starter is the team's other QB with the most dropbacks that season, else the previous season, else
    "unknown" (prior value). QB value = shrunk EPA/dropback on all dropbacks before T_w, n0 = 250, prior = mean
    EPA/dropback over the first 250 career dropbacks of QBs debuting 2003-2011. **qb_delta** = value(expected starter) -
    dropback-weighted value of the team's passers in the rating window. qb_delta_diff = home - away.
  - Margin: OLS, home margin ~ pass_epa_edge + run_epa_edge + qb_delta_diff + rest_diff + homefield (1 - neutral), no
    intercept, fit on all earlier games from 2004. Rest = days since the team's previous game, capped at 21.
  - P(home win) = Phi(pred / sigma); sigma = SD of earlier out-of-sample walk-forward residuals once >= 256 exist, else
    the degrees-of-freedom-corrected in-sample residual SD.
- **xgb_deep:** XGBClassifier on pass/run EPA and SR edges, qb_delta_home, qb_delta_away, elo_diff, homefield,
  rest_diff, week. Monotone constraints: +,+,+,+,+,-,+,+,0,0. Optuna (TPE, seed 0, 25 trials) once per season at week 1,
  on earlier data only, validation = the last two earlier seasons; space max_depth 2-5, learning_rate 0.01-0.2 (log),
  min_child_weight 1-20, subsample 0.6-1, colsample_bytree 0.5-1, reg_lambda 0.1-10 (log). Weekly refit with early
  stopping (max 1000 trees, patience 50) on the chronologically last 15% of training rows.
- **\*_platt:** each of the four above, Platt-scaled on logit(p) using that model's earlier walk-forward predictions only
  (>= 256 games, else uncalibrated). Isotonic is not used (it overfit in the NBA lab).

## Walk-forward and scoring
- For every week from 2012 week 1 to the latest completed week: train on everything before T_w, predict only that week.
- Scored set: completed, non-tied regular-season games 2012 onward. Metrics per model: log loss (primary), Brier,
  accuracy, ROC AUC, 10-bin reliability table, ECE.
- **Uncertainty:** paired per-game loss differences; week-cluster bootstrap, 2000 draws, seed 0. Diebold-Mariano test on
  weekly mean loss differences with Newey-West variance, lag 4.

## Gate (one look)
Family vs elo, Bonferroni m = 4: margin, margin_platt, xgb_deep, xgb_deep_platt. A candidate **passes** only if all hold:
1. corrected (98.75%) CI of the log-loss difference vs elo is entirely below zero;
2. DM p < 0.0125;
3. Brier no worse than elo;
4. lower log loss than elo in at least 9 of the 15 seasons 2012-2026.

**margin_platt is the pre-named primary.** Comparisons vs xgb_v1 and vs the market are descriptive with uncorrected 95%
CIs. Market comparisons cover 2026 only (expected n of about 100) and cannot pass or fail anything. Passing the gate
earns challenger status for the prospective test, not promotion. Promotion requires the prospective record and
Travis's approval.

## Leakage and data checks (automated tests; a failure stops the run)
- **Perturbation test:** for sampled weeks, corrupt every result, play, injury row and quote at or after T_w; features
  and predictions for that week must not change.
- Every injury row, inactive and quote used has a timestamp strictly before its cutoff.
- **Scores:** every completed nfldata game must match exactly one ESPN event (same teams, within a day) with identical
  scores, or the run fails.
- **Neutral flags:** nfldata `location` (lab games table, 2015+) vs ESPN `neutralSite` in seasons where ESPN reports any.
  Disagreements fail the run unless listed in a reviewed allowlist with a written reason.

## Prospective proof
`freeze` archives every model's probability for each game of the next week not yet kicked off. It includes the market
consensus and ESPN FPI game projection observed at freeze time. Archives go through `lab.archive10.save`: write-once,
SHA-256 of the content, timestamped, read-only. `score` matches archives to final results without editing them.
Historical ESPN FPI is not used, because its predictor values are modified after games (observed 2026-10-28).
