# Phase 5: player-level intelligence and model specialization (2026-10-17)

## 1. Data audit
| Data | Status before Phase 5 | Coverage / reliability | Pregame validity |
|---|---|---|---|
| Participation `offense_players` / `defense_players` (gsis IDs per play) | **Downloaded but never used**; only personnel strings were aggregated | 2016–2025; full 11v11 lists on 78% of plays (2016), 85–91% (2017–22), 99.6% (2023–25); IDs match the player table 100%; **no 2026 file yet** | Used only for later games |
| FTN charting (motion, play action, screen, RPO, no-huddle, out of pocket, blitzers, box) | not used | 2022–2026 (2026 through week 5) | Team rates from earlier games only |
| PFR snap counts | used for injury roles | 2012–2026 | Last 4 completed games → expected lineup |
| Verified injury reports | used | 2016–2024; 2026 from the lab's own archive; none for 2025 | Only rows timestamped before kickoff |

Not found as free, timestamped history: practice-squad elevations, inactive lists before kickoff,
historical starting-lineup announcements, PFF grades (subscription).

## 2. How player and replacement contributions are estimated (`lab/players.py`)
- **Model:** RAPM (ridge adjusted plus-minus) on per-play EPA with 334k plays, about 5,000 players, and
  separate offensive and defensive effects. It controls for down, distance, field position, score, quarter
  and home.
- **Shrinkage:** position-group effects get a light penalty and individual effects a heavy one, so each
  player shrinks toward his position group (hierarchical shrinkage). The penalty (λ = 3000) was chosen by
  predicting 2018 plays from 2016–17 plays only.
- **Weekly refits:** refit for every (season, week) on plays from games before that week's first kickoff
  (current season ×1, previous ×0.6, two back ×0.35): 220 fits in about 30 seconds.
- **Replacement level:** the mean effect of low-exposure players (< 300 plays) at each position, measured
  at that fit.
- **Team features per game:**
  - expected lineup = snap shares over the last 4 completed games;
  - players listed Out/Doubtful in a *verified* pregame report are replaced by the team's bench at that
    position (snap-weighted), or by the replacement level;
  - full vs projected lineup value and the value lost;
  - unit strengths (QB, OL, RB/WR/TE, DL, LB, DB);
  - information/uncertainty: snap-weighted log prior plays and the share of snaps by low-information players;
  - continuity: earlier plays the projected OL five, QB + top receivers and defensive core shared the field;
  - matchups: expected EPA, trenches and passing game.
- **Feature counts:** 45 model features (16 player model, 7 continuity/uncertainty, 22 FTN).
- **Caveats:** these are associations given teammates and opponents, not causal values. Players who always
  share the field cannot be separated (features therefore aggregate to units). 2026 ratings use plays through
  2025 (staleness up to about 250 days is shown).

## 3. Leakage prevention
- Every fit and feature uses only earlier games. The real-data perturbation gate now scrambles the target
  game's play EPA, on-field lists, team stats, QB EPA, snaps and all advanced sources: 0 of 1,182 columns
  changed for the 2,026 earlier games, and 1,054 later games changed.
- Unit tests cover: the RAPM fit is unaffected by later plays; co-play counts use earlier plays only; the
  adaptive ensemble never sees its own season.
- Known approximation: the single global λ was chosen on 2016–2018 plays, so 2016–17 training rows use one
  hyperparameter informed by 2018. No evaluated season is affected.

## 4. Results (`python -m lab.study5`, nested tuning, winner + margin)
**Champion with player features vs champion: 0 of 37 candidates passed the pre-declared gate.**

| Design | Dev 2019–22 | Val 2023–24 | Pooled (CI) | Holm p | 2025 diag |
|---|---|---|---|---|---|
| Player + continuity, weighted average | −0.0019 | −0.0040 | −0.0026 (−0.0048, −0.0005) | 0.32 | +0.0054 |
| Player model, weighted average | −0.0018 | −0.0011 | −0.0016 (−0.0034, +0.0002) | 1.0 | +0.0075 |
| All Phase 5, weighted average | −0.0019 | −0.0020 | −0.0019 (−0.0042, +0.0004) | 1.0 | +0.0095 |
| Adaptive context ensemble | +0.0045 | +0.0017 | +0.0043 | 1.0 | **+0.43 (failed)** |

- **Specialized families** (each family with player features vs its own earlier version, Holm within
  config): **Logistic Regression improved** (player + continuity: dev −0.0046, val −0.0036, Holm p 0.0015),
  and the **Single-layer NN** improved with the player model (p 0.016). Both were worse on 2025 (about
  +0.004) and better on 2026 to date (79 games). Neither beats the champion ensemble.
- **Specialization by situation:** 108 tests (7 situations × buckets × 6 models). 6 were supported after
  Holm, and **all say the Decision Tree is worse** than the champion. No model has a supported
  situational *advantage*.
- **Adaptive ensemble:** unstable. The context mix shifted (2025 has no injury data), and the stacker
  extrapolated badly. It was not re-tuned against the inspected 2025 season.
- **Margins (ensemble MAE):** dev improved 10.17 → 10.11 points, validation unchanged (10.17), 2025 worse
  (10.20 → 10.26–10.28). The closing spread remains better (9.84 on validation).
- **Champion: unchanged** (v20261016_212540, validation-weighted average).

## 5. Prospective tracking (the only fresh evidence left)
- **Pre-registered hypothesis:** `v20261017_021344_p5_player_continuity` (six models with player-model and
  continuity features). It is archived beside the champion in every snapshot, including per-model
  probabilities so the Logistic Regression family result can be tested. Decision after ≥ 128 future games:
  the paired improvement CI must lie below zero.
- **Discovery hypotheses:** 10 frozen hypotheses, generated from 2018–2025 out-of-sample predictions with
  568 features including player features. No historical validation look was used. They are evaluated only
  on games archived after 2026-10-17 02:15 UTC, with Holm across the 10.
- **Phase 2's historical result stands:** zero validated discoveries.

## 6. Debate changes
A sixth tab, "Players, matchups & uncertainty", shows:
- projected lineups, removed players and replacements, unit strengths, continuity and model staleness;
- player and unit matchup indicators;
- the spread of the six models' probabilities and every missing input;
- statistically supported situational evidence (currently: the Decision Tree is weaker in many situations);
- the pre-registered challenger's probability next to the champion's.

Everything comes from the models' own attributions and verified data.

## 7. Remaining uncertainty
- **Late scratches and elevations:** we cannot see which healthy players are inactive or practice-squad
  call-ups before kickoff.
- **2026 staleness:** RAPM ratings for 2026 rely on 2025 participation until nflverse publishes 2026.
- **2025 shift:** the 2025 drop for player features may reflect missing 2025 injury reports, or may be real.
  Prospective games will tell.
- **Small player effects:** player-level effects are small relative to play-level noise (the cross-validated
  MSE gain over shrink-to-group is tiny). Player value is hard to identify from on-field data alone.
