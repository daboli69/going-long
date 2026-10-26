# Phase 13 pre-registration: error budget, information timing and one structural challenger

Written 2026-10-26, before any number in this study was computed. Local lab only. No change to the champion, the challengers,
the scheduler, the Windows task or GOING. Commits stay local.

## Data
- Champion: walk-forward out-of-fold `p_weighted_average` and the ensemble margin, run v20261016_212540, 2018 to 2025.
- Market:
  - AusSportsBetting (ASB) opening and closing spreads and moneylines. A season qualifies only if at least 90% of its games
    have both, as in Phase 8.5 (2014 to 2024; 2025 fails).
  - nflverse closing moneyline and spread.
  - The lab's timestamped ESPN/DraftKings archive and stage snapshots for 2026.
- Public forecaster: nfelo `nfelo_games.csv`, joined on `game_id`. Its open and close probabilities are reported
  descriptively.
- Preseason win totals: sportsoddshistory.com, 2017 to 2025.
- New downloads are local only: hashes are in `data/raw/public/SHA256SUMS.txt`, and nothing is committed or published.

## A. Error budget (descriptive, reported with bootstrap intervals)
- **Noise ceiling:**
  - Log-loss floor proxy: the mean entropy of the closing no-vig probability.
  - Margin floor: the SD of (result minus closing spread).
- **Murphy decomposition** of the Brier score (10 equal-width bins) into reliability, resolution and uncertainty, for the
  champion, the open and the close. Games: 2018 to 2024, with ASB lines.
- **Gap attribution** of champion log loss minus close log loss into three parts:
  1. Calibration: the champion minus the champion recalibrated walk-forward (Platt scaling fitted on earlier seasons only).
  2. Modelling error versus the opener: the recalibrated champion minus the open.
  3. Information the market absorbed after the opener: the open minus the close.

  The historical out-of-fold forecasts are final-stage only. For 2026, the same comparison is made at every stage against
  the archived line at that stage's time (descriptive, about 40 games).
- **Power:**
  - Games needed to detect log-loss improvements of 0.002, 0.005, 0.01 and 0.02. One-sided alpha 0.05 and 80% power, using
    the observed SD of paired per-game differences.
  - Games needed to detect a 0.1 correlation in line-move prediction.

## B. Information-timing audit (descriptive)
Games from 2018 to 2024 are tagged:
- QB change: the starting QB differs from the team's previous game.
- Key starter out: a top-22 snap-share starter listed Out on a report modified before kickoff (2018 to 2024).
- Inactive starter: a regular starter listed INA that week.
- High wind forecast: at least 15 mph from the Open-Meteo historical forecast for kickoff. Only 2022 to 2024 are available.
  There is one request per stadium per season.

For each tag, report:
- how often it occurs;
- the mean absolute opening-to-closing move;
- the champion's log-loss gap to the close, with and without the tag;
- whether the champion's disagreement with the opener predicts the move (correlation).

## C. Structural challenger (the single primary test)
**Model.** A Kalman-filtered team strength on the points scale:
- margin = θ_home − θ_away + h + ε;
- weekly process noise q;
- between seasons, θ is pulled back toward a prior. The prior mean is β · (preseason win total − mean win total), with β
  fitted on earlier seasons only. Seasons before 2017 use θ carried over and shrunk by half.

**Market anchoring.** The forecast margin is open + κ · (θ_home − θ_away + h − open), where open is the ASB opening spread.
The probability is Φ(forecast margin / σ):
- κ is shrinkage toward the opener;
- σ is the residual SD.

**Fitting.**
- q, κ, σ and h are fitted by maximum likelihood on all games before each evaluation season (expanding window).
- Ratings warm up from 2014.
- One structural setting per component: no grid search over evaluation seasons.

**Out-of-time ablation.** Development seasons 2018 to 2020. Three components are checked: the win-total prior, dynamic
process noise (versus a static season rating) and anchoring (κ fitted versus κ = 1, which uses the model without the
opener). A component is kept only if removing it worsens development-season log loss. The kept set is written to
`artifacts/phase13/ablation.json` before the evaluation seasons are scored, and the code enforces this order.

**Evaluation.** Seasons 2021 to 2024, one look, games with ASB lines.
- **H1 (primary):** challenger log loss below the champion's.
- **H2:** challenger log loss below the opener's.

Tests: one-sided paired bootstrap by game (5,000 resamples) and a Diebold-Mariano test as a check, with Holm correction
across H1 and H2. A hypothesis passes if its Holm-adjusted bootstrap p is below 0.05.

**Reported, not decisive:**
- the challenger against the close and against the Phase 11 blend;
- Brier score and calibration;
- nfelo open and close on the same games.

## D. Simulator coherence (descriptive)
- The props simulator's game-level output is compared with reality in two ways:
  - a neutral run against 2024 league averages (plays, yards, touchdowns, red-zone rate, points SD);
  - the 2023 to 2025 evaluation archive of simulated against implied against actual team points.
- Simulated win probability is compared with the champion and the close on 60 games of 2025 (2,000 simulations each).
- Disagreements are reported as diagnostics only.

## E. Validation beyond us
- **Fast measure, 2018 to 2024:** line-move prediction, meaning the correlation of (forecast minus open) with
  (close minus open), for the champion, the challenger and nfelo.
- **Public forecaster:** nfelo log loss on the same games.
- **Prospective:** challenger forecasts for 2026 week 8 onward are frozen to
  `artifacts/phase13/prospective/` with their creation time, and scored after games. There is no promotion without
  prospective evidence and Travis's approval.

## Not allowed
- Changing any definition, component, window or threshold after a result is seen.
- Scoring 2021 to 2024 before `ablation.json` exists.
- Re-running the evaluation look.
