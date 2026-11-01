# Luck-adjusted team strength: pre-registration

Written 2026-11-01, before any fit of the new model and before any score of it on any year. The commit that holds this file is the
registration. Any later change goes in a separate commit before the run it affects, and is listed under Amendments.

## Question

Does team strength built from play-level efficiency, with luck removed, predict future NFL margins and totals better than the current
score model, and by how much? One hypothesis, one primary score, one holdout. No other models or features are added.

## What the history can and cannot show

The window 2012 week 1 to 2026 week 8 was already used once, by protocol 94e455cc, to score the current score model and its Elo control
(docs/FORECAST_RESULTS.md). The new model has never been fitted or scored on any of those years, and its settings are chosen on 2008 to 2011
only. Even so, the window is not fresh: its outcomes were seen for the older model, and that is declared here. The history result is
retrospective evidence. The only outcomes nobody has seen are the 2026 games from week 9 on.

Detectable effect (scripts/luck_prereg_power.py, saved in docs/luck_prereg_power.json), using only the saved forecasts of the current model
and its Elo control on 3,756 played games in 250 weeks, with whole weeks resampled because games in one week share noise:

| Quantity | Paired standard error | Smallest improvement detectable (80% power, 5% two-sided) |
|---|---|---|
| Margin CRPS, 2012 to 2026 week 8 | 0.0247 | 0.069 (about 0.9% of 7.52) |
| Winner log loss, 2012 to 2026 week 8 | 0.00236 | 0.0066 (about 1.0% of 0.639) |
| Margin CRPS, 2026 weeks 9 to 18 only (about 150 games) | | about 0.35 (about 4.6%) |

So the history can detect a gain of roughly 1%. The ten prospective weeks cannot detect anything under about 5%. A prospective result will
therefore be reported as a check for gross failure, not as confirmation of a small gain. A gain between zero and the detectable size is
"inconclusive", never "no effect".

## Data (all local, no downloads, $0)

- `data/raw/play_by_play_2002.parquet` to `play_by_play_2026.parquet`: every play, with nflverse EPA, win probability, turnovers, kicks.
- `data/raw/games.csv`: schedule, scores, closing spread and total (all seasons), moneylines (2009 on), roof, temperature, wind.
- `data/raw/participation_2016` on, `snap_counts_2015` on, `roster_weekly_2016` on: used only to check who played, not as model inputs.
- `data/cache/homewin_deep/forecast_wf.parquet`: saved walk-forward forecasts of the current model and its Elo control.

As-of rule: a game's features use only plays from games that ended at least 12 hours before the target game's kickoff. Week 1 uses the
previous season, shrunk toward the league by the offseason factor below. Weather, injuries and quarterback changes are not model inputs.

## The model

Per team and season, estimated from plays before the target game:

1. Plays: pass plays (dropbacks, sacks included) and rushes with a non-missing EPA. Kneels and spikes out. Garbage time out: plays when the
   offense's win probability before the snap was under 0.05 or over 0.95.
2. Opponent adjustment: ridge regression of EPA per play on offense and defense team effects, separately for passing and rushing, with
   home field as a covariate. Games are weighted by a half-life decay in games.
3. Luck removal, applied before step 2:
   - Fumbles lost: replaced by the expected number, the fumbles times the league rate at which the fumbling team loses the ball (learned from prior seasons).
   - Interceptions: the team's interception rate per dropback, shrunk toward the league with k dropbacks of league-average play.
   - Red-zone touchdown rate and field-goal rate by distance bucket: shrunk toward the league with k attempts of league-average play.
   - A turnover play enters at the league-average EPA of that play type and down-and-distance bucket times the shrunk probability, not its realized value.
4. Time variation: a Kalman filter with a random-walk strength state per team and unit (pass offense, rush offense, pass defense, rush defense),
   process variance q, and regression toward the league of the state by factor rho at each new season.
5. Mapping to games: margin = a + b x (home strength minus away strength) + h; total = c + d x (sum of the four offensive and defensive strengths in the game).
   The constants come from least squares on earlier games only, refit each week with the same decay. Predictive spread is the trailing
   three-season residual spread, widened by the parameter-uncertainty term.

The feature builder is committed before the first score on 2012 or later, and its commit hash is written into the results file.

## Settings chosen on 2008 to 2011 only (burn-in 2002 to 2007)

Five settings, each on a grid fixed here, 960 combinations in all. Selection is by margin CRPS in a walk-forward over 2008 to 2011. When two
combinations are within 0.1 standard error, the one with more shrinkage wins. Nothing is tuned after that.

| Setting | Grid |
|---|---|
| Ridge strength lambda | 5, 15, 40, 100, 250 |
| Half-life of games (games) | 8, 16, 32, no decay |
| Luck-shrink k (dropbacks or attempts) | 100, 300, 1000 |
| Kalman process variance q | 0, 0.01, 0.03, 0.1 (as a fraction of the observation variance) |
| Offseason regression rho | 0.5, 0.65, 0.8, 0.95 |

## Controls

- A. The current score model: its saved walk-forward forecasts, untouched.
- B. Margin-aware Elo: rebuilt from `games.csv`, with K, the margin-of-victory multiplier, home field and offseason regression set on 2008 to 2011 only.
- C. Same plays, no luck removal: the same builder with step 3 switched off and the same grid. This isolates what the luck removal adds.
- Winner probability from each margin forecast comes from the same normal distribution, so every comparison is like for like.

## Metrics and comparisons

Primary score: margin CRPS, walk-forward, 2012 week 1 to 2026 week 8.

| Id | Comparison | Role |
|---|---|---|
| C1 | New model against A, margin CRPS | Primary |
| C2 | New model against B, margin CRPS | Primary |
| C3 | New model against C, margin CRPS | Mechanism, descriptive |
| S1 | Total CRPS against A and B | Secondary |
| S2 | Winner log loss and Brier against A and B | Secondary, with reliability and resolution |
| S3 | 80% interval coverage, and PIT histograms | Calibration |
| M1 | Blend with the closing line | Market check, descriptive |

Intervals: 95%, resampling whole weeks (4,000 draws, seed 20261101), plus a Diebold-Mariano test with a Newey-West variance as a check.
Holm correction across C1 and C2. A within-week shuffle of the new model's forecasts is the placebo: it must show no gain.

M1: logit(p_blend) = logit(p_line) + w x (logit(p_new) minus logit(p_line)), with w fitted on earlier seasons only, expanding window, and
reported with its interval even if it is zero. The line's win probability comes from the closing spread with a normal spread fitted on earlier
seasons, and from de-vigged moneylines as a check from 2009 on. The closing lines have no time stamp in this file, so they may include late news.

## Acceptance rule

The new model becomes a Challenger only if all of these hold:

1. C1 and C2: the 95% interval for the CRPS change is entirely below zero after Holm, and the point improvement is at least 0.035 (half the detectable size).
2. Winner log loss is not worse than A by more than 0.002 (upper end of the interval below +0.002), and Brier is not worse.
3. Margin and total 80% coverage both between 75% and 85%.
4. Better than A in at least 9 of the 15 seasons.
5. The placebo shows no gain and the leak canary is flagged.

Otherwise the result is reported as not accepted, or as inconclusive when the point estimate is favorable but under the detectable size.
Accepted or not, nothing is promoted without Travis's approval, and the current model stays the champion.

## Checks on the test itself

- Leak canary: a feature built from the target game's own final margin is added once. The as-of validator must flag it, and the walk-forward
  CRPS with it must collapse. If either fails, the pipeline is stopped and fixed before any real result.
- Reference check: my Elo is compared with the lab's saved Elo forecasts (`p_elo`, `elo_mu`), and the closing-line win probability is compared
  with the nflverse pregame win probability in the first play of each game (`vegas_wp`, `home_wp`). Gaps larger than rounding are reported
  and the run stops until they are explained. No third-party Elo file is used: the FiveThirtyEight archive path I tried returned 404, so
  nothing is downloaded.
- Rebuild check: one script goes from raw files to every reported number. It is run twice from a clean copy of the repository and the output
  hashes are compared. This catches hidden state and manual steps. It cannot catch a flaw in the idea or the code logic, which is why the
  closing line, the placebo and the future games carry the weight.

## Prospective games

If the model is accepted as a Challenger, its forecasts for 2026 weeks 9 to 18 are written to `reports/luck/freeze_ledger.jsonl` before each
week's first kickoff with the SHA-256 of the forecast file and the commit hash of the code, and scored after the games. By the power table
above, ten weeks can only flag a gross failure.

## What this test cannot show

- Whether the model beats the betting market. M1 is descriptive. The earlier protocol found no gain over Kalshi, and a history of closing
  spreads without time stamps cannot settle it.
- Anything about injuries, quarterback changes, weather, or players. They are left out on purpose.
- Anything about money. A better score is not a betting return.
- A gain smaller than about 1% of the score. The history is too short to see it.

## Downloads

None. Everything above is on disk. A third-party Elo reference was considered and dropped because its source was not found.

## Amendments

### Amendment 1 (2026-11-01, committed with the builder, before any tuning and before any score on 2012 or later)

Disclosure first. Between the pre-registration and this amendment I built the pipeline and ran it for smoke tests on the tuning window only
(2008 to 2011): four settings at luck shrink k = 300, with and without luck removal, to confirm that the units and slopes are sane (strength-to-margin
slope about 0.95, correlation with margin 0.39 against Elo's 0.40). Nothing from 2012 on was read by any run (the plain-text loaders stop at the
tuning season). Those four runs are the only looks at model results so far.

1. **Ridge grid changed.** The registered lambda grid (5, 15, 40, 100, 250 plays) is far below the natural scale: with a per-play variance of about 2.25 and a team
   effect spread of about 0.06, sigma^2 over tau^2 is about 600 plays. The grid is now 40, 100, 250, 600, 1500. Still five values, 960 combinations in all.
2. **Neutral sites.** The lab's saved Elo marks a game neutral when the stadium name differs from the home team's usual one, so Seattle's renamed stadium
   made its last four 2020 home games neutral there. The lab's Elo is reproduced to 9.8e-7 over 3,770 games when that rule is used (`luck_checks.json`), so the
   rebuild is faithful. In this study a game is neutral when the schedule says Neutral or the stadium id differs from the home team's usual one, which handles
   renames and the 2012 Toronto game. The lab's rule is a small bug (79 games differ by more than 0.001 in Elo win probability); it is reported, not fixed here.
3. **Closing-line reference check.** The closing-line win probability (normal, spread fitted on earlier seasons) is within 0.031 on average of the nflverse
   pregame value (median 0.021). The gap is a steeper curve in nflverse. 25 of 3,771 nflverse first-play values sit on the wrong side (data defect). This is explained,
   not a failure; the benchmark for M1 is the line with the spread fitted on earlier seasons' results.
4. **Kicking.** Field goals and extra points are not in the pass or rush units, so their luck is excluded outright instead of shrunk. No separate kicking term.
5. **Units and plays.** Pass = dropbacks (sacks and scrambles included); rush = designed runs. Kneels, spikes, penalty-only plays and special teams are out.
   Garbage time is out (win probability before the snap under 0.05 or over 0.95). Playoffs are out everywhere.
6. **Luck removal, as built.** Interception rate per dropback, red-zone EPA per play and fumble outcomes use the team's own plays in this season to date and the two before,
   shrunk toward the league (as of the target week) with k plays of league-average value. A fumble play enters at the league-expected EPA given the league rate
   of fumbles lost. An interception count is replaced by the shrunk rate times dropbacks at the league mean interception EPA. Red-zone plays (inside the 20, not turnovers)
   enter at the shrunk team red-zone mean. The defense view of the same plays uses the defense's own history. With no luck removal the realized EPA per play is used.
7. **Ridge.** Weights are plays times 0.5 to the power (age in weeks over the half-life), age counting weeks since the game plus 4 for each season boundary. Rows: this season and the
   two before. Columns: intercept, home field (not neutral), offense effect and defense effect for every team, with lambda on the team effects only.
8. **Kalman.** Observation for an offense state = the team's adjusted EPA per play minus the ridge intercept, home term and the opponent's ridge defense effect (the defense state
   mirrors it), with variance equal to the ridge residual variance over the play count. Process variance per game = q times the residual variance over the league's average plays
   per game. Prior variance = residual variance over lambda. At each new season the state is multiplied by rho and its variance moves toward the prior by 1 minus rho squared.
   Opponent effects used for a week come from ridge fits on earlier weeks only.
9. **Scores.** Margin = h x (not neutral) + b x strength gap, with no separate intercept (a would be unidentified with h). Strength is in points per game: each unit's rating times the league's
   average plays per game for that unit as of the week. Total = c + d x the sum of all four units across both teams. Weekly weighted least squares over earlier games from 2003 on within three seasons,
   the same half-life weights. Predictive spread = the weighted residual spread times the square root of one plus leverage, floored at 3 points.
10. **Controls.** B (Elo): K in {10, 15, 20, 30}, reversion in {0.25, 0.33, 0.5}, home field in {40, 55, 70} Elo points, margin-of-victory multiplier on, mapped to margin by the same weekly
    least squares (no decay); its total forecast is the weekly weighted mean total. C (same plays, no luck removal): the same grid without k, 320 combinations.
11. **Ties in tuning.** Combinations within 0.1 standard error (paired by game) of the best margin CRPS are near ties; the winner among them has the largest lambda, then the largest k,
    then the smallest q, then the smallest rho, then the longest memory. Settings that land on a grid edge are reported.
12. **Statistics.** 4,000 week-resamples at seed 20261101. Diebold-Mariano on weekly mean differences with a Newey-West variance of 4 weeks, two-sided. Holm over C1 and C2 uses those p-values.
    Acceptance criterion 1 needs both 95% intervals below zero and both Holm-adjusted p under 0.05. Criterion 2 reads "Brier is not worse" as a mean difference at or below zero.
    Criterion 5 reads the canary as flagged when the as-of check reports violations for the leaked feature, the check on real runs reports none, and margin CRPS with the leak falls under half of
    the honest value. Placebo: 200 within-week shuffles of the new model's mean and spread pairs; it passes when the mean CRPS difference against the current model is at or above zero.
13. **M1.** The blend weight is chosen on 2008 up to the season before the one scored, on a grid from -0.5 to 1.5 in steps of 0.05, in logit space for the winner and by least squares for the margin.
14. **Tuned settings are frozen by commit.** `docs/luck_tuned.json` must be committed and unchanged before the test stage will run, and its commit hash goes into the results.
