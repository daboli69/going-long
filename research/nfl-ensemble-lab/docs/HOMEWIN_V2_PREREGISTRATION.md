# Home-win study v2: pre-registration

Written 2026-10-28, after the v1 results (`docs/HOMEWIN_DEEP_RESULTS.md`, Elo stayed best) and before any v2 number was
computed. Same question, $0, local lab only. No change to the lab champion, scheduler, Windows task or GOING. Nothing is
promoted by this study. One look per hypothesis.

**Reuse disclosure.** 2012-2026 history was scored in v1, so the v2 backtests are reused history. The 2026 market rows were
compared on log loss in v1, but CLV signs were never computed. The untouched tests are the prospective freezes.

## 0. Power (computed first, committed before anything else)
- **Log loss vs Elo.** The SD of week-mean paired differences comes from v1's margin_platt minus elo (v1 file
  `walk_forward.parquet`; design-stage use only). MDE = (z(1 - a/2) + z(0.80)) x SD / sqrt(weeks), with
  a = 0.0125 (the Bonferroni gate). Smallest effect of interest (SESOI): **0.005** log loss.
- **CLV.** For each point P in {open, Wednesday, Friday, T-90}, the SD of week-mean de-vigged moves (close minus P) on
  2026 games with quotes at both points. Model signs are not used. MDE uses a = 0.05/2. SESOI: **0.005** probability.
- Report the MDE for 2012-2026 history and the prospective MDE after N frozen weeks (about 14 games a week).
  **N_LL** and **N_CLV** are the smallest N with MDE <= SESOI. No prospective verdict on log loss before N_LL weeks,
  or on CLV before N_CLV weeks.
- **Primary CLV point** = the point with the smallest CLV MDE. Ties go to the earlier point.

## 1. Walk-forward expected points (removes look-ahead in nflverse EPA)
- **Plays:** nflverse play events, using only raw fields: down, ydstogo, yardline_100, half_seconds_remaining,
  game_half, timeouts, roof, posteam/defteam/home, and the scoring fields td_team, field_goal_result and safety.
  nflverse `epa`, `ep` and `success` are read only to compare against.
- **Label:** the next score in the same half relative to the possession team, in 7 classes
  (-7, -3, -2, 0, +2, +3, +7). A play's own score counts.
- **EP model** per season S: XGBoost multi:softprob fit on seasons max(2002, S-10) to S-1, scrimmage plays with
  down 1-4. Features: down, ydstogo, yardline_100, half_seconds_remaining, home, dome/closed roof, both teams'
  timeouts. Fixed settings: 200 trees, depth 5, eta 0.1, subsample 0.8, colsample 0.8, min_child_weight 5, seed 0.
  2002 has no EP (no earlier season), so ratings start in 2003.
- **EPA:** EP_after - EP_before. EP_after = the signed points of a score occurring on the play or before the next
  scrimmage play; else the next scrimmage play's EP (sign flipped on a possession change); else 0 at the end of the half.
  Success = EPA > 0.
- **Report:** per-season correlation, mean difference and mean absolute difference vs nflverse EPA on pass/run plays,
  plus the team-game EPA/play correlation.
- **Rerun:** v1's frozen margin and xgb_deep specs, unchanged, with weekly T_w and the v1 gate (H1).

## 2. Per-game decision points (walk-forward EPA)
For each game, US Eastern time, capped at kickoff minus 90 minutes:
- **open** = 20:00 on the Sunday at least 2 days before the game date (lab Phase 15 convention);
- **Wednesday** = 12:00 on the last Wednesday before the game date;
- **Friday** = 17:00 on the last Friday before the game date;
- **T-90** = kickoff minus 90 minutes (primary);
- **close** = kickoff.

Every input uses only rows timestamped before the point: results (game finished, kickoff + 4h), Elo (as-of rating
history), ridge ratings, QB values and starters, injury rows, inactives and quotes. At each point, the models are trained on
earlier games' features built at the same point. xgb_deep hyperparameters are tuned once per season (25 trials) on T-90
features and reused at every point. xgb_v1 is not scored at the points; its rolling form has no as-of variant.
**H2:** at T-90, margin, margin_platt, xgb_deep and xgb_deep_platt vs elo, with the v1 gate (Bonferroni m = 4, CI below
zero, DM p < 0.0125, Brier no worse, at least 9 of 15 seasons). **Value of information:** log loss per model per point,
and QB-change flags fired per point. Descriptive.

## 3. Stacking (H3)
Walk-forward logistic regression on the logits of elo and the new model (margin or xgb_deep at T-90), fit on earlier
out-of-fold rows. Weights are reported from the fit on all 2012-2026 out-of-fold rows, with week-cluster bootstrap
intervals (2000 draws, Bonferroni m = 2, so 97.5%). The new model **adds value** only if its weight's interval lies
entirely above zero. A three-input stack adding logit(market at T-90) is fit on the 2026 rows with quotes. It is
descriptive and too small to pass anything.

## 4. CLV (H4, main external test)
For every game with quotes at P and at the close: move = p_close - p_P (de-vigged multi-book median, observed before
each point). side = sign(p_model(P) - p_market(P)), and CLV = move x side. **Primary:** xgb_deep at the primary CLV point.
It passes if the mean CLV 95% week-cluster CI lies above zero and the one-sided sign test p < 0.05. Other models and
points are descriptive. Quotes keep being collected by GOING's existing twice-daily job; undated lines are never used.

## 5. Kalman rating
Not run. The item was optional, and one spec was allowed but not required. Skipping it keeps the study to 4 hypotheses.

## Independent proof
- **Freezes:** `freeze` continues weekly; `freeze --per-game` freezes each game between 105 and 90 minutes before its
  kickoff. Both are write-once SHA-256 archives with market and ESPN FPI captured at the same instant, and the ledger is
  pushed. Wiring `--per-game` into the scheduler needs Travis's approval.
- **Reproduction:** Codex rebuilds H1-H4 from this document alone. Claude's numbers are published with the SHA-256 of
  `reports/homewin_v2/results.json`. **Gate readings stay provisional until Codex's numbers match** (log loss to
  4 decimals, CLV means to 4 decimals).
- No verdict on the prospective record before N_LL / N_CLV weeks.

## Power results and Amendment 1 (2026-10-28, before any H1-H4 number or CLV sign)
Computed at commit 18e98172. Numbers are in `reports/homewin_v2/power.json`.
- **Log loss.** SD of week-mean differences 0.0502; 250 history weeks; history MDE **0.0106** at the gate's alpha. That is
  twice the SESOI, so 2012-2026 history cannot detect a 0.005 improvement. **N_LL = 1,126 weeks** (about 66 seasons).
  In practice, no prospective log-loss verdict will be issued.
- **CLV** (2026 games with quotes at both points): RMS move and the share of exactly-zero moves were open 0.0702 / 0%,
  Wednesday 0.0309 / 4%, Friday 0.0175 / 13% and T-90 0.0021 / 90%. GOING snapshots are about 3.4 hours apart (median),
  so T-90 and the close are usually the same snapshot.
- **Amendment 1.** The preregistered rule (smallest MDE) picks T-90, which is degenerate. Its MDE is small only because
  almost nothing moves, and an effect of size SESOI cannot occur when the typical move (0.002) is below the SESOI.
  Replacement, fixed before any CLV sign is computed: the primary CLV point is the point with the smallest N_CLV among
  points whose RMS move is at least 2 x SESOI. That gives **Friday, N_CLV = 7 frozen weeks.** T-90 CLV is reported
  descriptively. Thursday games' Friday point is the previous Friday, per the definition above.
