# King of the End Zone (version 1, retired)

This is the first, heuristic version. The board now uses the version 2 model, which is tested week by week in `docs/KINGZONE_WALKFORWARD.md` and fixed in `docs/KINGZONE_PREREG.md`. On the same 119 finished 2026 games version 2's average log score is -2.83 against -2.82 for this version's check (`docs/kingzone_backtest.json`), so the rebuild is about as good on that sample while being honest about its calibration and testable on 1,079 games.

A board of each player's chance to score the longest touchdown of one game, built for the Monday-night promotion that pays a share of a prize pool to that player. Code: `lab/kingzone.py`. Screen: the "King of the End Zone" tab. Check: `scripts/kingzone_backtest.py`, output in `docs/kingzone_backtest.json`.

## What the model does

1. Learns how long touchdowns are, per carry and per target, by position, from 2022 regular-season play-by-play up to the week before the game. A touchdown's length is the yard line the play started from.
2. Scales that shape for each player by his own rate of 20+ and 40+ yard gains per touch, pulled toward his position's rate. Receivers also get deep-target rate, yards after the catch and yards per route run. Runners get broken tackles per carry. These change only the long lengths.
3. Scales it again by the opposing defense's rate of 20+ and 40+ yard gains allowed per carry and per target over its last seven games.
4. Uses the simulated game's expected carries and targets, and holds each team's touchdown total to the touchdown rankings' figure for that team.
5. Adds competitors that are not on the list: touchdowns by other players, and defense and special-teams touchdowns at the league rate and length.
6. Treats touchdowns of each length as Poisson. A player's chance is the chance that his touchdown is the longest of the game; ties split evenly.

The importance weights (explosive rate 0.55 for receivers and 0.70 for runners, deep targets 0.25, yards after the catch 0.15, yards per route run 0.15, broken tackles 0.30) follow the brief's "very high / high / medium" order. They are judgment, not fitted.

## What is not in it

Player top speed and acceleration, offensive-line and pressure measures, route and coverage alignment, and the promotion's own prices. The free data has none of them. Punt and kickoff returners are not listed individually; returns sit in the defense and special-teams share.

## Check against this season's finished games

119 finished games from weeks 1 to 8 of 2026. Each board was built with history strictly before that game's week, and scored against the real longest touchdown from play-by-play. The baseline splits the game's touchdown chance in proportion to each player's expected touchdowns, the same number the touchdown rankings use.

| Measure | Model | Baseline |
| --- | --- | --- |
| Average log score, 95 games won by a listed player | -2.82 | -2.90 |
| Average chance given to the real winner | 7.4% | 7.2% |

The winner was in the model's top 1 in 15% of games, the top 3 in 42% and the top 5 in 58%. The model gave 14.8% to the field (defense, special teams and unlisted players); in 18.5% of games the longest touchdown came from there.

The paired gain in log score is 0.084 per game with a 95% bootstrap interval of -0.005 to 0.172. That is a small edge that is not clearly different from zero. With one winner per game and 95 usable games the check cannot separate the two. Treat the board as a reasoned ordering, not a measured advantage. The simulated games used for completed weeks may include information from after kickoff that the pregame app would not have had, so this check is also slightly generous.
