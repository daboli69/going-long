# In-game tracker

The tracker reads raw ESPN game data while a game is on, compares each player's box score with the pregame projection, and updates the projection for the rest of the game. It also gives a live win chance. Code: `lab/ingame.py` (model), `lab/ingame_feed.py` (feed, freezing, live state), `scripts/ingame_capture.py` (recording), `scripts/ingame_replay.py` (replay and checks), `scripts/ingame_eval.py` (backtest). The route `/api/live/{gid}` serves the newest state, and the Game view has a Live tab that shows it (score, win chance, role warnings, and each player pregame against updated; it refreshes every 15 seconds while a game is on, and asks ESPN directly when the newest saved snapshot is older than 15 seconds, so it does not depend on the recorder running; ESPN itself can lag the broadcast by about half a minute).

## How it works

A player's final stat is split into three parts, each of which can go wrong for a different reason.

1. **Team volume.** How many pass attempts or rushes the team still has coming. This depends on the clock, the score (a trailing team throws more) and the team's usual pace.
2. **Share.** The fraction of those attempts that reach him. His pregame share is updated with what he has seen so far (Beta-Binomial).
3. **Efficiency.** Yards per target or carry, and catch rate. His observed rate is pulled toward his pregame rate.

The pregame projection is the same model at kickoff with nothing observed, so any difference between frozen and updated comes only from the update. The constants (prior strength of the share, efficiency shrinkage, volume rule, score spread) are fitted on seasons up to 2023. Season 2024 was used to check, and 2025 and 2026 weeks 1 to 8 were never used to fit anything.

Each gap between live and projection is split into script (team volume), role (share) and luck or efficiency. Only role changes become warnings: a warning fires when the chance that his true share is far from his pregame share reaches 95%, with at least 12 team attempts seen.

The win chance uses the score, the clock, the drive in progress (expected points) and the frozen pregame margin. The existing full-game replay in `lab/gamesim.py` cannot start from a mid-game state, so this is a separate, simpler model. It does not use injuries that happen during the game, except through the box score.

## What the feed does not show

Snaps and routes are not in any free live feed, so opportunity means targets, carries and pass attempts. Red-zone touches are not tracked. Anything the feed leaves out is empty, never filled in.

## Frozen projections

`ingame/frozen/<game>.json` holds the saved forecast and Players-tab projections with a SHA-256 hash. A frozen file is never overwritten, and a changed file fails its hash check. `ingame/ledger.jsonl` lists every freeze. Nine games on 1 November 2026 were frozen after kickoff, and they are marked as such. They are tracked, but they are not clean pregame tests. Five were frozen before kickoff.

## Backtest (play-by-play replayed as if live)

Test seasons: 2025 and 2026 weeks 1 to 8, 380 games, 27,535 player checks at 10, 20, 30, 40 and 50 minutes. CRPS is lower-is-better. "Clock only" knows the clock and score but learns nothing about the player. Intervals come from a block bootstrap by game.

| Stat at 30 min | CRPS frozen | CRPS clock only | CRPS updated | Gain over clock only (95% interval) |
|---|---|---|---|---|
| Receiving yards | 16.9 | 10.1 | 9.5 | 0.63 (0.45 to 0.81) |
| Rushing yards | 19.4 | 11.3 | 9.5 | 1.76 (1.39 to 2.14) |
| Passing yards | 61.1 | 35.8 | 22.0 | 13.8 (11.9 to 15.7) |

The update beats the frozen number at every checkpoint, which is partly mechanical because yards already gained are banked. The fairer comparison is clock only, and the update beats it at every checkpoint with an interval above zero. Over all checkpoints the gain over clock only is 2.67 (2.37 to 2.97). The Brier score for beating a line set at the frozen median improved at every checkpoint against clock only, by a hair for passing at 50 minutes. Calibration for these over-the-line chances is close to the diagonal, with the 80 to 90% bin predicting 0.85 and seeing 0.78.

Role warnings at the 95% level fired about 1.3 times per game. When a warning said the share had dropped, the rest-of-game share was below 80% of pregame 98% of the time (the base rate is 47%). For a rise, 88% (base rate 26%). Warnings are rare enough to read.

Win chance against the frozen pregame margin: better at every checkpoint, with the interval above zero from 30 minutes on. Against nflfastR's own in-game win probability: better at 10, 20 and 30 minutes, tied at 40, and slightly worse at 50 (not significant). The model is overconfident in the tails: the 0 to 10% bin predicted 3% and saw 9%.

Full numbers: `docs/ingame_eval.json`.

## Live check on 1 November 2026 (eight 1pm games, all final)

- **Win chance.** Brier score over all snapshots: this tracker 0.210, ESPN 0.188, Kalshi 0.201 (seven games, the market had closed for one). Much of this is one upset, ARI at DAL. Eight games cannot separate them, and ESPN was ahead.
- **App projections.** For 97 player-stat lines at 40 minutes, the mean absolute error against the final box score was 43.9 yards for the app's frozen projection, 26.9 for that projection shifted by the live update, and 25.7 for the tracker's own model. The update helped in seven of eight games. These games were frozen after kickoff.
- **Box score against nflverse play-by-play.** Not done. nflverse had not posted these games when checked. `scripts/ingame_replay.py --final-check` runs it once they appear.
- **Feed consistency.** Play-by-play types and the box score differ by 0 to 5 attempts per team, in the direction of kneels, scrambles and two-point tries that my play classifier does not count. This is not an outside check, since both come from ESPN.

## Limits

- The pregame baseline is a trailing eight-game average, with zeros for missed games. A quarterback who just changed teams starts with a low share. The update corrects this quickly, but the frozen baseline is weak. The prior strength came out near its lowest allowed values (1 for rushing and passing, 8 for receiving), which says the baseline carries little information.
- The backtest does not know who was inactive. Players who did not play count as zeros.
- Game win chance is too confident in the tails.
- Kalshi in-game history is only available for captured games, so the market comparison has seven games. The 1pm games went to OT only once (TEN at CIN), and overtime is outside the 60-minute model.
- Hourly Kalshi candles are too coarse to replay old games against the market.

## Running it

```
.venv\Scripts\python.exe scripts\ingame_capture.py          # during games; saves raw ESPN snapshots to data/raw/ingame
.venv\Scripts\python.exe scripts\ingame_replay.py --freeze  # freeze the week's projections (before kickoff)
.venv\Scripts\python.exe scripts\ingame_replay.py --final-check
.venv\Scripts\python.exe scripts\ingame_eval.py             # chronological backtest
```

## Version 2 (1 November 2026)

Pre-registered in `docs/INGAME_PREREG_V2.md` and committed before any test was run. Fit on 2018 to 2023, calibrated on 2024, tested once on 2025 and 2026 weeks 1 to 8. Full numbers: `docs/ingame_eval_v2.json`.

**What changed.** The pregame baseline now comes from snap counts and play-by-play across teams (a player's last eight games played, whatever team he played for), and games a player sat out are left out of his average. The share update is fitted by a hierarchical Bayesian model in PyMC (partial pooling by role group), with convergence checks passed (R-hat at most 1.01). The win chance has a second candidate, a gradient-boosted game-state model with isotonic calibration. Efficiency shrinkage is still a fitted constant.

**Result against the pre-registered rule.**

| Comparison | Gain (95% interval) | Holm-adjusted DM p | Beats? |
|---|---|---|---|
| Receiving yards, v2 vs v1 (CRPS) | 0.73 (0.61 to 0.85) | below 0.001 | Yes |
| Rushing yards, v2 vs v1 (CRPS) | 0.91 (0.72 to 1.09) | below 0.001 | Yes |
| Passing yards, v2 vs v1 (CRPS) | 0.06 (-0.08 to 0.21) | 0.28 | No |
| Win chance, v2 vs v1 Brownian (Brier) | -0.006 (-0.013 to 0.000) | 0.17 | No, slightly worse |
| Win chance, v2 vs nflfastR (Brier) | 0.002 (-0.011 to 0.015) | 0.74 | No, tied |
| Win chance, v2 vs frozen pregame (Brier) | 0.042 (0.028 to 0.057) | below 0.001 | Yes |

So version 2's baseline and share model is live for receiving and rushing, and passing and the win chance stay on version 1. The comparison uses only player-games both versions track and in which the player played, so version 2 gets no credit for knowing who sat out. The gain is largest early (receiving, 1.7 yards of CRPS at 10 minutes, 0.1 at 50 minutes) because that is where a better pregame number matters.

**The new win model was worse than the old one out of sample.** Its isotonic calibration was fitted on 2024 and did not hold: in the test seasons, games it gave 90 to 100% won 92% of the time. Version 1's Brownian model stays.

## Feed delay

ESPN's own timestamp for a play versus the first time our recorder saw it, over 308 plays polled every 20 seconds: median 53 seconds, 9 in 10 within 72 seconds (`docs/ingame_latency.json`). The Live tab shows these numbers, and shows a warning when no new play has appeared for longer than the usual delay allows. The figure is measured against ESPN's timestamp, not the television picture.

## Reconciliation with the official play-by-play (eight 1pm games, 1 November 2026)

After matching players by ESPN id, the box scores the tracker used were compared with the nflverse play-by-play for the same games. Yards matched for every receiver and every running back. The 34 differences (listed in `docs/ingame_replay.json`) all fall into three kinds:

- **Pass attempts (18 quarterbacks):** nflverse counts sacks as attempts and ESPN does not. Yards are equal.
- **Quarterback rushes (12):** ESPN counts kneel-downs as rushes with negative yards and nflverse does not.
- **Target and carry counts (4 receivers):** a one-target difference.

The first kind is a real mismatch between the history the model learned from (sacks counted) and the live feed (sacks not counted), so a live team's attempts run a little low against the model's expectations. It has not been corrected, because that would change the pre-registered event definitions. It is the first thing to fix in the next version.

## What is still missing

- Routes run, which no free source gives. Snaps stand in for them in the baseline.
- Sportsbook in-game prices, which have no free source.
- Official inactive lists for past seasons. A player with no snaps stands in for an inactive one in the backtest, and the live tracker uses the posted list.
- Kalshi and ESPN in-game prices for scoring: only the games recorded since 1 November 2026.
