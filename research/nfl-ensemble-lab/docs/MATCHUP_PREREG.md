# Do matchup features beat the closing line: pre-registration

Written 2026-11-08, committed before any feature or test number is computed. Football only. No staking and no bet sizing anywhere in this document.

## Question

Green Bay beat New England 45-27 in Week 9 after the ensemble gave New England 57.7% and the market gave it 59 to 64%. Looking back, some pregame numbers leaned toward Green Bay: its defense ranked 7th against the pass and 4th in interception rate, New England's quarterback ranked 28th in interception rate, and season-long net efficiency was close to even. Does any of that carry information about the winner beyond the closing line, across many games? One game cannot answer this, so this document sets up the test on past seasons and on future weeks.

## 1. Structural reason and honest prior

The closing moneyline already prices team strength, home field and known injuries, so a feature built from public play-by-play has to add something the market missed. A matchup feature could add something if the market weights season-long efficiency or turnover luck badly. The prior is against it. Every earlier test of a closing-line gap in this lab came back null, and interception and takeaway rates are known to carry little from year to year. The expected outcome is a null result, and a null result is a valid answer.

Disclosure: the feature ideas below came from looking at one game after it finished. That game cannot count as evidence for them. The test seasons below were not looked at when the features were chosen.

## 2. Data

- `data/raw/games.csv`: scores, closing spread and closing moneylines for each regular-season game. Games without a closing home and away moneyline are dropped and the count is reported.
- `data/raw/play_by_play_<season>.parquet`: 2006 to 2026, for the features. Regular season only. Plays with a pass or run type and a non-missing expected-points-added value.
- Everything is computed as of the week before each game, from earlier weeks only. Week 1 uses the previous season with the shrinkage in section 3.

## 3. Fixed in advance

**Champion.** The no-vig home win probability from the closing moneylines (the simple proportional remove of the overround). Call its log-odds `m`.

**Challengers.** Each is a logistic regression of the home win on `m` plus the listed features, with a ridge penalty of 1.0 on the feature coefficients and none on `m`. Features are home minus away, standardised on the training seasons.

- **H1, efficiency.** Two features. (a) Net efficiency: offense expected points per play minus defense expected points per play allowed. (b) Pass matchup: home offense pass expected points per dropback minus away defense pass expected points per dropback allowed, minus the same for the away offense against the home defense. Each team rate uses all plays of the current season through last week, shrunk toward the previous season's full-year rate with weight n/(n+250) plays on the current season, and toward zero for a team's first season in the data.
- **H2, turnovers.** One feature: for each side, the offense's interception rate per dropback times the opposing defense's interception rate per dropback, each shrunk toward the league rate with weight n/(n+300) dropbacks, then home minus away.
- The three features are fixed. No other feature, window, shrinkage constant or penalty is tried. Quarterback changes are handled by using the team rate, as the champion does.

**Fitting and scoring.** Walk-forward by season. To score season S, fit on every season from 2006 through S-1. Test seasons are 2022, 2023, 2024 and 2025. 2026 weeks 1 to 9 is scored the same way as a separate confirm sample, once all nine weeks are in the data, and is also reported without the Green Bay game.

**Metric.** Log loss per game, challenger minus champion, so negative is better. Interval by bootstrap over weeks (2,000 draws), because games within a week are not independent.

**Pass rule.** A challenger passes only if all of these hold:
- Pooled 2022 to 2025 mean difference is below zero with the 95% interval wholly below zero (one-sided 97.5% for each of two tests).
- The point estimate is at least 0.002 better, the smallest gain worth acting on.
- Better in at least 3 of the 4 test seasons.
- The 2026 point estimate is better, with no interval requirement because the sample is small.
- Brier score is no worse.

Two hypotheses are tested, so the alpha for each is 0.025. Nothing outside H1 and H2 is read as a result.

## 4. Gate before any real outcome is read

**Placebo power check.** Shuffle each feature's values across games within the same season and week, refit and score, 200 times. Report the standard deviation of the paired difference and the smallest effect detectable with 80% power. A hypothesis whose smallest detectable effect is larger than 0.006 log loss is reported as "not testable" and its outcome comparison is not read. This uses no outcome beyond the fit the placebo itself runs on.

**Planted effect.** Add 0.004 of log loss gain by moving the champion probability toward the true result for a random 25% of test games, and confirm the pass rule fires in at least 80% of 200 runs. If it does not, the pass rule is too strict for this sample and that is reported before anything is read.

## 5. Descriptive checks, not pass-fail

- Calibration of the champion for games it priced between 55% and 65% for the home side, with and without a flagged defensive mismatch (the opposing defense in the top 8 for pass expected points allowed and the home quarterback in the bottom 8 for interception rate). Counts per cell are shown so a reader can see how thin they are.
- Where the lab's frozen ensemble probabilities exist, the same log-loss comparison against the champion, descriptive only.

## 6. Prospective record

From Week 10, before kickoff each week, a write-once file under `data/matchup/` records the feature values, both challenger probabilities and the champion probability for every unplayed game, with a SHA-256 hash. Nothing is backfilled. The prospective score is read after 60 or more games, and not before.

## 7. Report order and rule

Completed, Model Research, Concerns, Next, Needs Travis. If neither hypothesis passes, the result is "matchup features add nothing over the closing line", with the table of what was and was not testable. Nothing in the app or the ensemble changes on this result. A pass changes nothing either until the owner approves a Champion/Challenger promotion.
