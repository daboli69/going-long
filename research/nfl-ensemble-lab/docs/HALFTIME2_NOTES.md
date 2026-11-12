# Halftime challenger (v2): did not beat the current model

Written on 11 November 2026. Code: `lab/halftime2.py`. The current model is `lab/halftime.py`, tested once on 2025 (see `docs/HALFTIME_PREREG.md`).

## What was tried

The challenger kept every input of the current player model and added:

- the player's position, and flags for a quarterback change during the first half;
- a forecast of the team's second-half pass and rush attempts from the score, the pregame line and the first-half play mix;
- the player's share of team targets and carries, updated from the trailing share by the first-half count (a beta-binomial update; fitted prior strengths were 40 team targets and 10 team carries);
- yards per target, catch rate and yards per carry, pulled toward the league average;
- the opponent's trailing receiving and rushing yards allowed;
- a blend with the simple rule, with the weight chosen on the validation seasons;
- nine quantile models, so the chance of an over comes from a fitted distribution instead of pooled past outcomes.

## Result on the validation seasons (2023 and 2024)

Mean absolute error. The gain is the current model's error minus the challenger's, with a 95% bootstrap interval over games.

| Target | Challenger | Current model | Gain (95% interval) |
|---|---|---|---|
| Second-half receiving yards | 13.095 | 13.016 | -0.079 (-0.129 to -0.030) |
| Second-half receptions | 0.994 | 0.991 | about -0.003 |
| Second-half rushing yards | 11.826 | 11.892 | 0.066 (0.004 to 0.126) |

Quantile loss (lower is better), challenger against current model: receiving yards 4.684 against 4.679; receptions 0.3612 against 0.3616; rushing yards 4.459 against 4.374.

The share-and-volume forecast on its own, with no trees, scored 13.665, 1.035 and 12.329.

Four more variants were scored on the same seasons: a more heavily regularised challenger, an average of the two models, a more heavily regularised current model, and the current model fitted on 2004 to 2022. All landed within about 0.08 of the current model.

## Reading

- The challenger is worse on receiving yards, level on receptions and slightly better on rushing yards. Its distribution is no better placed, and worse for rushing yards.
- These seasons were used to design both models, so even the rushing gain is not evidence. It is also too small to matter.
- The first-half touch counts already carry what the added features try to say. More structure on the same play-by-play does not help.
- Decision: the challenger does not advance. The 2026 Weeks 1 to 9 holdout was not scored and stays unspent. `lab/halftime.py` remains the model.

## What could still help

- Snaps and routes by half would be new information, but the free participation files stop at 2025 and are not published during a game, so they cannot feed a live halftime forecast.
- A sportsbook halftime line as an input. None is on disk yet; the folder `data/raw/halftime_lines/` is ready for them.
- In-game injury reports. Free play-by-play does not label a player hurt in the first half.
