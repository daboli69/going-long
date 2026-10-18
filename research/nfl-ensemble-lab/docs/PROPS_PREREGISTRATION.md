# Player-props distribution simulator: pre-registration (local lab only)

**Written 2026-10-18, before any simulator code or result existed.** This is a separate experimental predictor. It does not
touch the champion game model, the challengers or the GOING site.

## Method: play-by-play Monte Carlo
The method follows the approach DraftKings Engineering published ("Modeling Football: Combining ML models and Monte Carlo
simulations", Feb 2024). Each simulated play passes through a chain of fitted models, and game state updates after every play
until the clock runs out:

1. **4th down:** go / punt / field goal (multinomial logistic).
2. **Play type:** pass or run (logistic), plus a team pass-rate offset in logit space.
3. **Pass:** sack (logistic) → air-yards bin (multinomial) → complete / incomplete / interception given air yards (multinomial)
   → yards-after-catch bin given air yards (multinomial) → fumble lost.
4. **Run:** rush-yards bin (multinomial) → fumble lost.
5. **Kicks:** field-goal make by distance (logistic), punt net distance and kickoff start position (empirical, latest training
   season), PAT and two-point attempts (empirical rates).
6. **Clock:** seconds run off per play (empirical by play result and hurry-up state).

**Model inputs:** down, distance, field position, score difference, quarter, time left and timeouts. Sub-models are fitted on
earlier seasons only (walk-forward).

**Players:**
- **Who is available:** only players listed active (ACT) on that week's nflverse roster. Inactives (INA) are announced 90 minutes
  before kickoff, so this uses pregame information only.
- **Targets and carries:** each pass target and run carry is drawn from the available players' as-of shares (season to date,
  blended with last season at k = 4 games). When a player is inactive, his share is redistributed within his position group in
  proportion to the remaining players' shares.
- **Player efficiency:** as-of offsets for each receiver's average depth of target and catch rate, and each rusher's
  yards-per-carry tilt, all shrunk toward 0.
- **QB:** the starter is the QB who took the team's first dropback. Starters are publicly known before kickoff; this is a
  stated assumption.

**Team strength (market-anchored, as books do):**
- Each offense gets one efficiency scalar per game, applied in logit space: it tilts gain bins up or down, raises completion,
  and lowers interception and sack chances.
- The scalar is calibrated by bisection so that mean simulated points match the closing implied team totals
  ((total ± spread)/2). Closing lines are pregame information.
- A high total therefore inflates both offenses together.

**Simulations:** 10,000 per game. Every player's yards and receptions come from the same simulated plays, so a QB's yards always
equal his receivers' yards.

## Evaluation (no historical prop odds exist in the lab, so this measures distribution quality, not betting profit)
- **Seasons:**
  - Development (repeated looks allowed for building and debugging): 2022.
  - **Evaluation, one look:** 2023, 2024 and 2025, regular season. Sub-models are fitted on 2016 through the previous season.
- **Player-games (eligibility uses as-of shares only):**

  | Stat | Players included |
  |---|---|
  | Passing yards | starting QB |
  | Rushing yards | players with as-of carry share ≥ 20% |
  | Receiving yards and receptions | players with as-of target share ≥ 10% |

- **Baseline B: an independent per-player model** (the one-player-at-a-time approach):
  - Mean = the player's as-of per-game average × (implied team total ÷ his team's as-of points per game).
  - Yards: normal, using the player's as-of SD shrunk to the position SD at k = 4 games.
  - Receptions: Poisson.
  - It uses the same market lines and the same availability rule as the simulator.
- **Primary test:**
  - Metric: mean CRPS (continuous ranked probability score, lower = better), pooled over all eligible player-game-stats in
    2023–25.
  - Comparison: simulator vs baseline B, paired.
  - Significance: a one-sided game-cluster bootstrap (2,000 resamples). **The simulator passes if its mean CRPS is lower with
    p < 0.05.**
- **Secondary (reported, not decisive):**
  - CRPS by stat type.
  - 80% and 50% interval coverage.
  - PIT histogram (probability integral transform: where each actual result fell within its predicted distribution).
  - **Tail calibration:** the Brier score of P(stat > that player's as-of 85th percentile), where props live.
  - **Over/under log loss** at a synthetic line equal to the baseline's median rounded to x.5.
  - **Correlation check:** same-game correlation of QB passing yards with his top receiver's receiving yards, simulated vs
    actual.
  - Mean simulated vs actual team points, and how the calibration converged.

## If it passes
- It becomes a prospective experiment only: distributions are archived before kickoff and scored after the games.
- A betting comparison needs real prop lines. No free, timestamped historical prop source exists in the lab. If a free and
  permitted live source is found, it would be added as a separately pre-registered archive.
- No GOING exposure without Travis's approval.

## Not allowed
- Tuning any sub-model, bin, shrinkage or calibration choice on 2023–25 results.
- Re-scoring 2023–25 after changes. A changed simulator is evaluated only prospectively (2026 onward).
