# Phase 14 pre-registration: QB value, information arrival, honest weekly monitoring

Written 2026-10-26, before any number in this study was computed. Local lab only. No change to the champion, the challengers,
the scheduler, the Windows task or GOING. Commits stay local.

Motivation (Phase 13): QB changes occur in 19% of games, the market moves twice as far in them, and the champion's loss to
the closing line is three times larger there (0.046 against 0.014).

## 1. Ledger and backlog
`research_ledger.json` holds every hypothesis with its registration commit, kill rule, status and backlog score. Every
future idea gets the same fields.

score = targeted gap × share of games affected × probability of detection within two seasons ÷ cost in hours

- Targeted gap and game share come from the Phase 13 error budget.
- Detection probability uses the Phase 13 power formula (SD 0.196 for paired per-game log-loss differences).
- `docs/LEDGER.md` is generated from the JSON file. QB value is ranked first by construction of this study, and the
  remaining entries are scored by the formula.

## 2. Information arrival (event study; descriptive and ongoing)
- **Events** (2026 onward, from the lab's own timestamped archives):
  1. a team's depth-chart QB1 changes between consecutive depth-chart snapshots;
  2. a team's QB1 first appears as Out or Doubtful in an archived injury report (nflverse or ESPN);
  3. the projected starter in the stage snapshots changes.
- **Line:** the DraftKings home spread from the archived ESPN snapshots. The move is measured from the last snapshot
  before the event to the first snapshot at or after the event plus 1 hour, plus 6 hours, plus 24 hours, and to the last
  snapshot before kickoff.
- **Comparison:** the same windows anchored at random times for the same games.
- **History, 2018 to 2024:** the opening-to-closing move in QB-change games against other games (the Phase 13 proxy).
- This part has no pass or fail. It is refreshed weekly.

## 3. QB value model
**Model.** An empirical-Bayes hierarchical normal model.
- Data: QB dropbacks (`qb_dropback == 1`) with `qb_epa` and `cpoe` from nflverse play-by-play, 2006 onward. These are the
  rawest public per-play data.
- **Skill:** θ_i ~ N(μ_i, τ²), with μ_i = a + b1 · log(draft pick, undrafted = 260) + b2 · experience bucket (0, 1, 2, 3+
  seasons) + b3 · shrunk career CPOE.
- **Observation:** the weighted mean EPA per dropback, ē_i ~ N(θ_i, σ² / n_i). Earlier seasons are weighted 0.5 per year
  back, using at most the three previous seasons plus the current season before the game. σ² is the per-dropback EPA
  variance.
- **Fitting:** a, b1 to b3 and τ by marginal maximum likelihood on QB-seasons before each evaluation season.
- **Backups:** a QB with few dropbacks falls back to μ_i. That is the replacement-level prior: low draft capital and little
  experience imply a low prior mean.
- **Output:** the posterior mean θ̂ before each game. The QB value in points per game is θ̂ × D, where D is the mean team
  dropbacks per game in the training seasons and 1 EPA counts as 1 point.

**Margin change.** For a QB-change game (the starting QB differs from the team's previous game), the change for the team
is Δ = (θ̂_new − θ̂_old) × D. Δ_home is the home team's change minus the away team's.

**Market QB adjustment.** Market power ratings come from a ridge regression of closing spreads on team indicators plus home
field, over each team's previous 6 games. The market adjustment is this game's opening spread minus the spread those ratings
expect.

**Adjusted forecast.** logit p_adj = logit p_champion + γ · Δ_home, where γ is fitted on 2018 to 2020 QB-change games.

**Single historical look, 2021 to 2024 QB-change games (Holm across Q1 and Q2):**
- **Q1 (primary), the model knows what the market prices:** Pearson correlation of Δ_home with the market QB adjustment.
  One-sided test that it is above 0.
- **Q2, the forecast improves:** log loss of p_adj below the champion's. One-sided paired bootstrap, 5,000 resamples.
- **Reported, not decisive:**
  - correlation of Δ_home with the opening-to-closing move;
  - closing line value: correlation of (logit p_adj − logit p_open) with (logit p_close − logit p_open);
  - the same metrics for the champion alone.

**Kill rule.**
- If Q1 fails, or Q1's correlation is below 0.2, the QB value item is killed for fixed-sample work.
- If Q1 passes and Q2 fails, it continues prospectively as a monitor only.
- If both pass, it continues to a frozen prospective challenger.

**Validation beyond us.** These are descriptive:
- Correlate θ̂ × D for each starting QB with nfelo's `home_538_qb_adj` and `away_538_qb_adj` (FiveThirtyEight QB Elo
  adjustments, converted at 25 Elo points per point of spread), game by game, for 2018 to 2024.
- Correlate Δ with the change in those adjustments in QB-change games.

## 4. Weekly monitoring that stays honest
- **The e-process.** A betting e-process on bounded per-game evidence x_t in [−1, 1], where H0 is that the mean is at most 0.
  - The wealth is E_t = Π(1 + λ_t · x_t), with a predictable bet λ_t = clip(running mean ÷ (running variance + running mean²),
    0, 0.5), starting at 0.
  - Reject H0 when E_t ≥ 20 (α = 0.05). This holds at any stopping time, so checking it every week is valid.
- **Monitors, all on 2026 games after this registration:**

  | Monitor | Evidence x_t |
  |---|---|
  | M1 Phase 11 blend vs champion (final stage) | log loss of the champion minus log loss of the blend, clipped to [−1, 1] |
  | M2 p5 challenger vs champion | the same form |
  | M3 p7 challenger vs champion | the same form |
  | M4 closing market vs champion | the same form; tests whether the market is better |
  | M5 S2P flagged games | dog won minus the champion's dog probability |
  | M6 QB adjustment in QB-change games | log loss of the champion minus log loss of p_adj |

- These monitors are additional. The original fixed-sample rules of Phases 3, 8.4 and 11 stay authoritative.
- A monitor crossing 20 is reported to Travis. Nothing is promoted automatically.

## 5. Prospective freeze
`python -m lab.phase14 freeze` writes, before kickoff, each team's projected starter and backup QB values with a
timestamp, to `artifacts/phase14/prospective/`. They are scored after games.

## Not allowed
- Changing definitions, windows, priors, γ, D or the kill rule after results are seen.
- Scoring 2021 to 2024 more than once.
- Promoting anything without prospective evidence and Travis's approval.
