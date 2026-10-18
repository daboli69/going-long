# Player-props distribution simulator (local lab experiment)

**Pre-registration:** `docs/PROPS_PREREGISTRATION.md` plus Amendment A. This is separate from the champion game model and from
GOING.

## What it is
A play-by-play Monte Carlo of each game, following DraftKings Engineering's published football engine:
- every play passes through a chain of small fitted models;
- the game state updates after each play;
- the whole game is run 10,000 times.

The output is a full distribution for every player's passing yards, rushing yards, receiving yards and receptions. All of them
come from the same simulated plays:
- a QB's yards always equal what his receivers caught;
- one receiver's big day takes targets from the others;
- a high-total game inflates both offenses together;
- an inactive starter's targets and carries go to his position group.

| Stage | Model |
|---|---|
| 4th down | go / punt / field goal (multinomial logistic: distance, field position, score, time) |
| Pre-snap penalty | empirical rate, yards and automatic first downs |
| Play type | pass / run (logistic) + team pass-rate-over-expected offset |
| Pass | sack → receiver (as-of target shares) → air-yards bin (situation mixed with receiver's own depth profile) → complete / incomplete / interception (+ receiver catch offset) → yards after catch → fumble |
| Run | rusher (as-of carry shares) → rush-yards bin (situation mixed with rusher's profile) → fumble |
| Red zone | gains drawn from real outcomes at the exact yard line |
| Kicks | field-goal make by distance, PAT rate, punt and kickoff field position (latest training season) |
| Clock | seconds per play by result and hurry state, scaled to match real plays per game |
| Team strength | one efficiency scalar per offense, calibrated to the market's implied team totals |
| Uncertainty | per-simulation team efficiency and player-share noise |

**Implementation:**
- **Code:** `lab/props/models.py` (sub-models), `lab/props/sim.py` (vectorised simulator; all simulations advance one play per
  step), `lab/props/players.py` (as-of inputs), `lab/props/evaluate.py` (walk-forward evaluation).
- **Training:** every evaluated season is fitted on 2016 through the previous season only.
- **Availability:** players listed active on that week's roster. Inactives are announced 90 minutes before kickoff.

## Running it (Travis starts it; nothing runs automatically)
```
python -m lab.props.evaluate dev       # 2022 development season, ~1 hour (optional, repeatable)
python -m lab.props.evaluate eval      # 2023-2025, THE single pre-registered look, ~3-4 hours; refuses to run twice
python -m lab.props.evaluate analyze eval
```
- **Results:** `artifacts/props/<tag>/` (`player_games.parquet`, `analysis.json`), with a log in `artifacts/props/<tag>_run.log`.
- **Dashboard:** Blind-spot research → "Player props simulator".

## Pass rule
The simulator passes if its mean CRPS over all eligible 2023–25 player-game stats is lower than baseline B's (the independent,
one-player-at-a-time model), with a one-sided game-cluster bootstrap p < 0.05. Also reported:
- coverage, PIT and tail calibration;
- over/under log loss at a synthetic line;
- QB–WR1 correlation;
- simulated vs implied points.

## Limits (stated up front)
- **No profit claim.** There are no historical prop odds in the lab, so this measures how good the distributions are, not
  betting profit. A betting test needs a free, permitted, timestamped prop-line archive, which would be a new pre-registration.
- **Not simulated:** timeouts, defensive and return touchdowns, two-point attempts and overtime. Player stats are regulation only.
  The red-zone boost absorbs the missing points, so simulated touchdown rates run high; touchdown props are not evaluated.
- **Starting QB:** assumed to be the QB who threw the team's first pass. Starters are publicly known before kickoff.
- **2022 development check** (60 games): the simulator had lower CRPS than the baseline on all four stats, with means 3–6% high.
  It was used for building only and is not evidence.
