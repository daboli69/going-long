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

None.
