# Does knowing who plays beat knowing team strength? Protocol frozen 2026-10-28 before any win-probability scoring with player features

Builds on `docs/NBA_XGB_PREREGISTRATION.md` and `docs/NBA_XGB_RESULTS.md` (team-strength study, finished). Home-win probability only;
no props, spreads, totals, betting strategy or sportsbook features.

## Disclosures

1. The earlier study already scored 2025 and 2026 for the team-strength models, and ablations were run on those seasons. These seasons are
   therefore not clean for any comparison that includes the base models. The only clean evidence will be the live 2026-27 season
   (hashed forecasts issued before tipoff). Results on 2025-2026 are reported as "retrospective test", not confirmation.
2. Everything below was chosen before any win-probability model saw a player-based feature. Already seen (not outcomes of the new features):
   RAPM tuning error, play-probability log loss by season, reconstruction audits.
3. Historical injury-report rows come from today's archive copy of the NBA PDFs. Each PDF carries its own publication time in the
   file name and header; `available_at` is the latest of header time, URL slot and HTTP Last-Modified. This is publisher-side time, not proof
   of when anyone saw it. ESPN box scores and play-by-play were retrieved in October 2026; their publication time is not known.

## Raw material actually used

- ESPN play-by-play (SportsDataverse release, 12 seasons archived with SHA256) -> stints and lineups. Validated 2021 onward only: final score
  matches in 99.92% of reconstructed games and 99.92% of player-games are within one minute of ESPN box minutes. Seasons 2019 and 2020 failed
  reconstruction in 30% of games (event ordering) and are not used. Per-season counts in `research_nba_xgb/PBP_AUDIT.json`.
- Official NBA injury report PDFs, 2021-22 to 2025-26 (816 game days, 1,631 PDFs). Selected report per game day = latest report published
  at least one hour before that day's first tipoff.
- ESPN player box scores (minutes, played, starter) for labels and recent-minutes history.
- Existing team box scores for cross-checks. Official NBA CDN/stats endpoints returned 403 or timed out from this machine, so they were not used.
- Not obtained: free historical closing market probabilities; free public Elo history covering 2024-26. Comparisons to them are reported as not done.

## Time stamps per record

event time (game date ET); publication time (injury: `available_at`; results: tipoff + 24 h proxy and the next-ET-day rule);
retrieval time (October 2026 for all history); prediction cutoff = first tipoff of the ET day minus 60 minutes. Team-result features use games dated
at most one day earlier. A game's own-day injury report is used only if `available_at` is at or before that cutoff.

## Measurements

- Player ratings: regularized adjusted plus-minus (ridge) on stints, weight = possessions x 0.5^(age/half-life). Refit weekly; the fit on day R uses games
  dated <= R-1; a game uses the latest fit on or before its date. Penalty and half-life chosen by next-week stint error in season 2023 only
  (done: penalty 3000, half-life 730 days, `docs/NBA_AVAIL_RAPM_TUNING.json`).
- Play-probability model: logistic on status, reason category, status x reason, games played in last 10, recent minutes, games-missed streak.
  Refit once per season on earlier injury-era seasons (2022 onward). First usable season 2023.
- Expected team value = sum over candidate players of (P(play) x recent minutes, rescaled to 240) / 48 x player RAPM net rating.
  Full-health value assumes P = 1 for usual rotation players (>= 5 of last 10 games and >= 10 average minutes).
- Features: `full_value_diff` (player quality at full health), `avail_effect_diff` (expected minus full-health value, home minus away),
  `missing_min_diff`. Diagnostic only, never a feature: `oracle_value_diff` (value using actual minutes played, retrospective).

## Models and splits

Base features (frozen earlier): elo_diff, recent_net_diff, rest_diff, b2b_home, b2b_away, home_court. Availability features missing before 2023
(XGBoost: NaN; logistic: 0 plus a has-availability flag). Models: calibrated Elo; base logistic; availability logistic; base XGBoost; availability XGBoost.
Expanding window, annual refit, training seasons 2017 to F-1. Development fold F = 2024 (all hyperparameters: C grid as before, 20 seeded XGBoost configurations from the
earlier space, shallow rule, calibration none vs Platt chosen on fold 2024 with calibrators fit on out-of-sample folds 2022-2023). Retrospective test: 2025 and 2026, run once
after `docs/NBA_AVAIL_FROZEN.json` is committed. Live: 2026-27.

## Power (stated before testing)

Per-game paired log-loss differences have standard deviation about 0.06 to 0.07 on earlier development folds; 0.08 is used to be conservative.
Games needed for 80% power at alpha 0.05: about 5,600 for a true gain of 0.003; about 3,100 for 0.004; about 2,000 for 0.005.
The retrospective test has 2,459 games, so its minimum detectable difference is about 0.0045. **The retrospective test is not large enough to
settle a 0.003 effect.** A null result means "no effect larger than about 0.005 was found", not "no effect". The live season
(about 1,230 games) lifts the combined total to about 3,700 games only at season end.

## Statistics

Log loss (primary), Brier with Murphy decomposition (reliability, resolution, uncertainty), calibration slope and intercept, reliability bins.
Paired differences with date-clustered bootstrap (4,000 draws), 7-day block bootstrap, and a Diebold-Mariano test on daily loss differentials with
Newey-West variance (bandwidth floor(n^(1/3))). Three primary comparisons, so 98.3% intervals and alpha 0.0167:
(1) availability logistic vs base logistic, (2) availability XGBoost vs availability logistic, (3) availability XGBoost vs calibrated Elo.
Credible = interval excludes zero, DM p < 0.0167, and the same sign in both test seasons.
Ablation (remove one group, availability logistic and availability XGBoost): availability shortfall, player quality, Elo, recency, rest;
add-back of opponent-adjusted efficiency.

## Leakage and verification

Randomized-outcome test (all outcomes after each cutoff replaced with random values; earlier predictions must not change), mutation test with a planted leak,
day-by-day replay equal to batch. Separate evaluation script with no package imports. A second feature implementation written from a written
specification alone by an independent agent, compared field by field. Daily forecasts for 2026-27 hashed and committed before tipoff.
