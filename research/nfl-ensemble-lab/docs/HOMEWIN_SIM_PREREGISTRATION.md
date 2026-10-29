# Drive-level game simulator: pre-registration

Written 2026-10-29, before any drive model was fit. $0, local lab only, no new data vendors. Same question as v1/v2
(P(home win)), plus the margin and total distributions the simulator implies. No change to the lab champion,
scheduler, Windows task or GOING. Nothing is promoted. One look per hypothesis.

**Reuse disclosure.** 2012-2026 outcomes were scored in v1/v2, so this backtest is reused history. The untouched tests are
the prospective freezes.

## 1. Drives from raw plays
- **Source:** nflverse play events, regular season, sorted by `play_id`. A drive is a maximal run of consecutive plays with
  a down (1-4) by the same `posteam` in the same `game_half`. Kickoffs, extra points and two-point tries are not drive
  plays.
- **Start state:** `yardline_100`, `half_seconds_remaining`, score difference (`posteam_score - defteam_score`), timeouts,
  and offense home or away.
- **End class**, checked in this order: OPP_TD (`td_team` is the defense on any drive play); TD (`td_team` is the
  offense); SAFETY; FG (made); MISSED_FG (missed or blocked); TURNOVER (interception or fumble lost on the last play);
  PUNT; DOWNS (last play 4th down, no first down); END_HALF (last drive of the half); else OTHER (dropped and counted).
  **OPP_TD is an added ninth class.** Pick-sixes and return TDs need it, because the next possession stays with the same
  team.
- **Duration** = start clock minus the next drive's start clock (0 at the end of the half).
- **Cross-check:** for each drive, the nflverse `fixed_drive_result` of its first play, mapped to these classes. Report the
  agreement rate by season and class. Nothing is changed to raise it.

## 2. Drive-outcome model (multinomial logit)
- **Features:** 10-yard start-field bins plus linear `yardline_100`; time-left bins (0-30, 30-120, 120-300, 300+ seconds);
  score difference clipped to +/-21, divided by 7, plus its absolute value; offense-home and neutral indicators; offense
  and defense franchise one-hots.
- **Fit:** scikit-learn multinomial `LogisticRegression`, L2 with C = 1.0 (this is the shrinkage on team effects), lbfgs.
  Sample weight is 0.5^(age in days / 240). Training covers drives of the current and 3 previous seasons from games
  that kicked off before R.
- **R** = the week's earliest T-90 minus 4 hours: results known before the week's first decision point, as in v2.
  Refit weekly.
- **Baseline:** the same fit and weights with only the field-position features and offense-home. No teams, score or time.

## 3. Simulator
- **Pace model:** empirical resampling. For each (end class, start-field bin), the training drives' (duration, next
  drive's start yard line) pairs. Half-opening kickoff starts come from the current season if at least 50 exist, else
  the previous season.
- **Points:** TD 7 (6 in overtime), FG 3, SAFETY +2 to the defense, OPP_TD +7 to the defense.
- **Possession:** passes to the other team after every class except OPP_TD (same offense receives) and END_HALF. The
  half-1 receiver is a coin flip, and the other team receives in half 2.
- **Overtime** when tied: 600 seconds from 2017, else 900. A first-possession TD, safety or OPP_TD ends it. After both
  teams have possessed, any score ends it. If time expires, the game is a tie.
- **Runs:** 10,000 simulations per game, `numpy.random.default_rng(seed = int(sha256(gid)[:8], 16))`. Output: P(home
  win) (ties count half for log loss; tie probability reported), the discrete margin pmf and the total pmf.

## 4. Scoring (walk-forward 2012 week 1 to the latest completed week)

| Family | Comparison | Pass rule |
|---|---|---|
| D: drives (primary) | per-drive log loss, model vs baseline | 95% week-cluster CI of the mean difference below 0 |
| G: games (m = 2) | margin RPS, simulator vs v2 T-90 normal margin (discretized); total CRPS, simulator vs league normal (mean and SD of totals from the current and 2 previous seasons before R) | 97.5% CI below 0, each separately |
| W: win (m = 2) | simulator and simulator Platt vs elo (v2 T-90 elo) | v2 gate: CI below 0, DM p < 0.025, Brier no worse, at least 9 of 15 seasons |
| S: stack | elo + simulator logits, simulator weight | 95% CI above 0 |

- **Descriptive:** share of games decided by exactly 3 or 7 points (actual vs mean predicted, with CI); tie rate;
  randomized-PIT histograms (10 bins) for margin and total, with chi-square and KS uniformity p-values.
- RPS is over integer margins -80 to 80, and CRPS over integer totals 0 to 120 (unnormalized sums of squared CDF
  differences). Week-cluster bootstrap: 2000 draws, seed 0.

## 0. Power (computed from a pilot, then committed before the main run)
- **Pilot:** this frozen spec run walk-forward on 2009-2011, outside the evaluation window, with training back to
  2006, against the same baselines (v2 features for the normal margin and elo).
- From the SD of week-mean paired differences, compute MDE = (z(1 - a/2) + z(0.8)) x SD / sqrt(weeks) for history
  (all 2012-2026 weeks) and per prospective week, with a as in each family.
- **SESOI:** drive log loss 0.005 nats; margin RPS and total CRPS 0.5% of the baseline's pilot mean; win log loss
  0.005. N for each family = the smallest weeks with MDE <= SESOI. No prospective verdict for a family before its N.

## 5. Leakage and external checks
- v2 point-builder leakage checks run unchanged.
- **Simulator perturbation:** shuffle the end classes and durations of every drive in games kicking off at or after R.
  The week's simulated outputs must be identical; a cutoff 8 days late must change them (negative control).
- **2026 descriptive:** latest pre-kickoff GOING spread and total (median across books) vs simulated median margin and
  total; MAE of each vs actual.
- **Freezes:** `scripts/home_win_sim.py freeze`, weekly before the first kickoff, every game's full pmfs, write-once
  SHA-256 archive, ledger pushed.
- **Reproduction:** Codex rebuilds from this document. Fits are deterministic (match to 4 decimals). Simulation metrics
  must match within 3 Monte Carlo standard errors, which are reported. **Gate readings are provisional until then.**

## Power results (2026-10-29, from the 2009-2011 pilot, before the main run)
`reports/homewin_sim/power.json`. Drive rebuild: 144,198 drives, 99.0% agreement with nflverse `fixed_drive_result`
(lowest season 98.5%), 656 OTHER drives dropped.

| Family | SD of week means | SESOI | History MDE (2012-2026) | Weeks needed prospectively |
|---|---:|---:|---:|---:|
| D drive log loss | 0.0275 | 0.005 | 0.0049 | **237** |
| W win log loss | 0.0396 | 0.005 | 0.0077 | **598** |
| G margin RPS | 0.520 | 0.040 | 0.101 | **1,623** |
| G total CRPS | 0.748 | 0.038 | 0.146 | **3,624** |

Only family D is powered on history at its SESOI. No prospective verdict for a family before its week count.
A pilot bias check on 62 games of 2010 weeks 1-4 found simulated median total 43.0 vs actual 40.6, and median margin
+2.2 vs +2.7. No spec was changed.
