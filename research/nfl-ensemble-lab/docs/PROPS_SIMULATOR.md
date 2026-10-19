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
- **Viewing:** sidebar → **Player Props**. Each game shows the official pregame archive once written, otherwise the latest preview.
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

## Result: the single pre-registered look, 2023–2025 (run 2026-10-18, 816 games, 17,740 player-game stats)
**PASSED.**
- Mean CRPS: simulator **13.30** vs baseline 13.96. The difference is −0.66 (−4.7%), 95% CI −0.83 to −0.50, one-sided
  p = 0.0005.

| Stat | n | CRPS sim / base | Mean sim / base / actual | 80% coverage sim / base | Over/under log loss sim / base | Big-game (> own 85th pct) Brier sim / base |
|---|---|---|---|---|---|---|
| Passing yards | 1,600 | **42.1** / 45.8 | 241 / 222 / 223 | 0.74 / 0.74 | **0.675** / 0.693 | **0.152** / 0.164 |
| Receptions | 6,618 | **1.24** / 1.26 | 3.78 / 3.64 / 3.56 | 0.89 / 0.80 | **0.657** / 0.671 | 0.135 / 0.135 |
| Receiving yards | 6,618 | **16.7** / 17.3 | 42.8 / 41.7 / 41.0 | 0.85 / 0.81 | **0.682** / 0.693 | 0.142 / 0.142 |
| Rushing yards | 2,904 | **17.1** / 17.9 | 49.4 / 46.8 / 46.9 | 0.75 / 0.81 | **0.681** / 0.693 | **0.145** / 0.147 |

- **Correlation:** the simulated within-game correlation of QB passing yards with the top receiver's yards is 0.44. The actual
  residual correlation is 0.45. The shared-play structure reproduces real same-game correlation.
- **Team points:** simulated 22.1 against market-implied 22.0 and actual 22.6.

### Known defects (found in this look; any fix is judged prospectively only)
1. **Overprojection.** Means run high: passing +8%, rushing +5%, receptions +6%, receiving +4%. The PIT histograms pile up in
   the lowest bin, and the simulator overstates big games (passing: 24.3% predicted vs 19.0% actual). It still wins on CRPS
   because its distribution shapes and correlations are better.
2. **Calibration overshoot.** In 10.7% of games, final simulated points missed the implied total by more than 2 (median miss
   0.4, worst about 13). `calibrate()` applies one last update without re-checking it.
3. **Spread is uneven.** Receptions and receiving yards are too wide (80% coverage 0.89 and 0.85); passing and rushing are too
   narrow (0.74 and 0.75).

### What it means
- **Distribution quality:** the whole-game simulation produces better player distributions than one-player-at-a-time models,
  mostly through better shape and correlation, despite the high bias.
- **Not a betting claim:** the over/under lines here are synthetic (baseline medians), not sportsbook lines.
- **Under the pre-registration,** the next step is prospective only: archive pregame distributions for 2026 games and score them
  after kickoff. A fixed version (bias, calibration re-check) would be a new version, judged only on 2026+ games.

## v2 and the 2026 prospective stage
**Pre-registration:** `docs/PROPS_V2_PREREGISTRATION.md`, committed (3a4d617) before any v2 code. v1 is frozen as evaluated;
v2 is judged only on 2026 games, against v1.

**Code:**
- `lab/props/v2.py`: settings and the mean-correction layer.
- `lab/props/sim.py`: `calibrate_v2` and `fit_gains`, plus per-kind `kappa_recv` / `kappa_rush`. With these keys absent, v1 is
  bit-identical; a test checks this.
- `lab/props/tune_v2.py`: the 2022 tuning grid.
- `lab/props/game.py`: shared per-game inputs, baseline B and quantile CRPS.
- `lab/props/weekly.py`: the weekly archive.

### Tuned values (2022 development season only; sub-models 2016–21; 136 games; `artifacts/props/v2_tuning/selection.json`)
| Fix | Setting | Value |
|---|---|---|
| 1(a) gain correction (training seasons) | yards per completion / per carry multipliers | 0.978 / 0.925 (neutral sim was 11.37 vs real 11.24 per completion, 4.72 vs 4.45 per carry) |
| 1(a) | red-zone boost refit | 0.996 (v1 0.824) |
| 1(b) per-stat mean correction | passing / rushing / receiving yards / receptions | 0.940 / 1.043 / 0.974 / 0.965 |
| 2 verified calibration | games missing implied points by > 2 | 0 of 136 (median 0.18, worst 0.94) |
| 3 dispersion | sigma_e / kappa_recv / kappa_rush | 0.25 / 30 / 10 |

**Implementation notes, recorded honestly:**
- Scaled gains are rounded to whole yards. Unrounded, a 0.998 multiplier turns 10-yard gains into 9.98, which fails 10-to-go
  conversions and drops neutral points from 23.0 to 19.6. That bug was caught in the first tuning attempt and fixed before
  any selection.
- After fix 1(a), the red-zone boost reaches its cap (1.0), so neutral points sit slightly below training. Market calibration
  sets every game's points anyway.
- **Selection:**
  - The lowest-CRPS point (sigma_e 0.25, kappa_rush 30; CRPS 13.655) and the pick (13.662) tied within 0.5%. The pick is
    closer to 0.80 coverage on all four stats.
  - Its 2022 80% coverage after correction is 0.80 / 0.81 / 0.82 / 0.81 (passing / receptions / receiving / rushing).
  - kappa_recv stayed at v1's 30, so the 2023–25 receiving width (0.85–0.89) is not addressed by share noise. Raising
    kappa_recv was worse on 2022 CRPS.
- These 2022 numbers are tuning, not evidence.

### Weekly command (manual; the pinned scheduler and Windows task are unchanged)
```
python -m lab.props.weekly                     # coming week, unstarted games only (best run after inactives, ~90 min before kickoff)
python -m lab.props.weekly archive --week 7 --game 2026_07_NE_CHI
python -m lab.props.weekly preview --week 7      # view-only projections for every game with lines; re-run any time (artifacts/props/prospective/preview/, never scored)
python -m lab.props.weekly score               # after games are final AND play-by-play is refreshed
python -m lab.props.weekly summary             # interim, descriptive
```
- **Archive:** `artifacts/props/prospective/<season>_w<week>/<game_id>.parquet` with v1, v2 and baseline-B mean plus
  quantiles 1–99% per eligible player-stat, and a `.json` sidecar (lines, availability rule per team, QB, commit, SHA-256).
  Files are created exclusively and never overwritten.
- **Scores:** `artifacts/props/prospective/scores/<game_id>.parquet`, written once.
- **Availability:**
  - The ACT roster once that team's inactives are published.
  - Otherwise ACT minus injury-report Out (Doubtful and Questionable stay in).
  - With no roster rows for that week, the latest earlier roster minus Out.

  Each team's rule is recorded per game. Running closer to kickoff gets the better rule.
- **Dashboard:** Blind-spot research → "Player props simulator" → "2026 prospective archive".
- **First archive (2026-10-18):** `2026_06_DAL_GB` was archived before kickoff with v1 and baseline B only; v2 had not been
  tuned yet. It is excluded from the paired v2-vs-v1 test. `2026_06_WAS_SF` (Monday) is left for Travis to archive after the
  inactives are out.
