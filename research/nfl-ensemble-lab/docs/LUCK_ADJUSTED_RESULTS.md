# Luck-adjusted team strength: results

Run 2026-11-01 under `docs/LUCK_ADJUSTED_PREREGISTRATION.md` and its Amendment 1. One look at 2012 week 1 to 2026 week 8.
Numbers are in `docs/luck_results.json`, `docs/luck_tuned.json` and `docs/luck_checks.json`.
The tuned settings were committed at `98fc23e1` before the test ran. The builder was committed at `7b72a6ba` before any tuning.

**Result: not accepted.** The new model is worse than the current score model and worse than Elo on the primary score. Removing luck made it worse,
not better. Nothing is promoted, the current model stays the champion, and no forecasts are frozen for weeks 9 to 18.

## The model, in one paragraph

Team strength came from pass and rush EPA per play outside garbage time, adjusted for opponents with a weekly ridge, with interceptions, fumbles and
red-zone results replaced by shrunk expectations, then smoothed by a Kalman filter and mapped to margin and total by weekly least squares. Settings
were chosen on 2008 to 2011 only.

## Primary score: margin CRPS (lower is better), 3,756 games in 250 weeks

| Model | Margin CRPS | Total CRPS | Winner log loss | Brier |
|---|---|---|---|---|
| New: luck-adjusted play-level strength | 7.602 | 7.681 | 0.6460 | 0.2272 |
| Current score model | 7.519 | 7.666 | 0.6388 | 0.2240 |
| Margin-aware Elo (tuned on 2008 to 2011 only) | 7.463 | 7.823 | 0.6338 | 0.2216 |
| Same plays, no luck removal | 7.531 | 7.673 | 0.6409 | 0.2248 |

| Comparison (new minus reference) | Difference | 95% interval, weeks resampled | Better in |
|---|---|---|---|
| C1: current score model | +0.083 | +0.032 to +0.137 | 4 of 15 seasons |
| C2: Elo | +0.138 | +0.091 to +0.185 | 0 of 15 seasons |
| C3: same plays, no luck removal (mechanism) | +0.071 | +0.038 to +0.103 | 4 of 15 seasons |

A positive difference means the new model scored worse. Holm-adjusted Diebold-Mariano p-values: C1 0.0024, C2 under 0.0001.
The detectable size from the power calculation was 0.069, so the C1 gap is about the size the history could see, and the C2 and C3 gaps are larger.

Secondary scores against the current model: total CRPS +0.015 (interval -0.026 to +0.060, no difference); winner log loss +0.0072 (+0.0015 to +0.0129, worse);
Brier +0.0031 (+0.0005 to +0.0058, worse). Against Elo the new model's total forecast is better (-0.142, -0.191 to -0.094), but Elo has no total model of its own,
only a weekly average, so that is not a real contest.

## Acceptance rule

| Criterion | Met |
|---|---|
| 1. C1 and C2 intervals below zero after Holm, gain of at least 0.035 | No (the differences are positive) |
| 2. Winner log loss and Brier not worse than the current model | No |
| 3. 80% coverage between 75% and 85% for margin and total | Yes (margin 80.6%, total 80.2%) |
| 4. Better than the current model in at least 9 of 15 seasons | No (4 of 15) |
| 5. Placebo shows no gain, and the leak canary is flagged | Yes |

## Checks on the test

- **Placebo:** shuffling the new model's forecasts within each week made the score 0.938 worse (0.858 to 1.023), so the real forecasts carry signal. They are just not better than the references.
- **Leak canary:** with the game's own final margin added as a feature, margin CRPS fell from 8.02 to 0.70 and the as-of check flagged all 2,560 targets. On the real runs the as-of check found 0 violations.
- **Elo reference:** the Elo rebuilt from the standard formula matches the lab's saved Elo to 9.8e-7 over 3,770 games when it uses the lab's neutral-site rule. That rule has a small bug: Seattle's stadium rename in 2020 turns four home games into neutral games, and 79 games differ by more than 0.001 in win probability. I did not change the lab. This study treats a game as neutral when the schedule says so or the stadium id differs.
- **Closing-line reference:** the line's win probability is within 0.031 on average of the nflverse pregame value. nflverse uses a steeper curve, and 25 of 3,771 of its first-play values sit on the wrong side. The benchmark used here is the line with its spread fitted on earlier seasons.
- **Tuning window (2008 to 2011, 1,024 games):** all three models were within 0.005 CRPS (new 7.995, same plays no luck removal 7.990, Elo 7.991). The new model's chosen settings sat on three grid edges (longest memory, no process variance, strongest regression between seasons), and the near-tie rule found no near ties. The registered grid was kept.

## Against the closing line (descriptive only)

On the same 3,756 games the closing line scores 0.6121 log loss and 7.235 margin CRPS; the new model alone scores 0.6460. The blend weight on the new model was negative in every season
(mean -0.283 in logit space), meaning the model's disagreement with the line pointed the wrong way on average. The blended winner log loss beat the line by 0.0015 (-0.0032 to +0.0002), an interval that includes zero,
and the blended margin CRPS differed from the line by +0.0005 (-0.0065 to +0.0073). Nothing here shows the model adds to the line.

## Rebuild check

One script (`scripts/luck_run.py all`) goes from the raw files to every number above. I ran it twice from a clean checkout of the repository (a separate git worktree at the same commit, reading the same data folder).
The two runs produced identical checks, tuned settings and results, and both matched this checkout once the block of code-file hashes was set aside. Those hashes differ between the two checkouts, and I did not trace why.

This check can catch hidden state in the working folder, steps done by hand, and unstable ordering or randomness. It cannot catch a flaw in the idea or in the logic of the code, because the same code ran each time.
That is why the planted leak, the placebo, the reference checks and the closing line carry the weight.

## What this test could not show

- **Whether the model beats the betting market.** The closing-line comparison is descriptive, and the closing spreads have no time stamps, so they may include late news.
- **Anything about injuries, quarterback changes, weather or players.** They were left out on purpose.
- **A betting return.** A better score is not a profit.
- **A gain under about 1% of the score.** The history is too short to see it.
- **A fresh result.** The 2012 to 2026 window was already used once for the current model. The new model never touched it before this look, but the window is not new.
- **Anything from the prospective weeks.** Weeks 9 to 18 of 2026 could only flag a gross failure, about a 5% gap. Because the model was not accepted, no forecasts were frozen for them.
- **Why it lost.** The gap could come from leaving out kicking and special teams, from per-play EPA being a noisy stand-in for points, or from luck removal discarding signal that repeats (interception rate partly belongs to the passer). None of these was tested, and testing them on this window would spend it again.

## One side observation, not tested

The Elo control, tuned on 2008 to 2011 only, scored 7.463 against 7.519 for the current score model. That is a difference of 0.055, below the 0.069 this history can detect, and it was not a registered comparison, so it is not a finding.
