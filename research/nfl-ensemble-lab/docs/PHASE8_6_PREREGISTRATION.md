# Phase 8.6 pre-registration: Big Data Bowl 2026 tracking (2023 season), local lab only

**Written 2026-10-18, before any tracking metric was computed.** Nothing changes in the champion, the challengers or the
GOING site.

## Data
- **Source:** Kaggle NFL Big Data Bowl 2026, analytics and prediction. The zips were downloaded manually by Travis and
  extracted to `data/raw/kaggle/<competition>/`. They are local only; the competition rules forbid redistribution. Hashes are
  in `artifacts/phase86/provenance.json`.
- **Contents:** 2023 weeks 1–18 pass plays.
  - `input_*`: pre-throw tracking.
  - `output_*`: positions of the targeted receiver and the defenders in coverage, frame by frame while the ball is in the air.
  - `supplementary_data.csv`: play context (coverage, routes, EPA). Its 77 games from 2024 weeks 14–18 have no tracking and are
    not used.
- **Game join:** BDB `game_id` is matched to `games.csv` by season, week, home team and away team.

## Metric
- **Arrival separation** (one per targeted pass): at the last output frame (ball arrival), the distance in yards from the
  targeted receiver to the nearest tracked defender. Plays with no tracked defender, and plays nullified by penalty, are excluded.
- **Team-game values:**
  - **OffSep:** the offense's mean arrival separation in that game.
  - **DefSep:** the separation the defense allowed.
- **As-of team edge:** E = OffSep − DefSep, each averaged over the team's earlier 2023 games (strictly before the target week).
  At least 3 earlier games are required, otherwise the value is missing. Higher = better pass-game matchup quality.
- **Angle:** E(champion underdog) − E(champion favourite). Larger favours the underdog.

## Primary test T1 (one look)
- **Model:** logistic regression of favourite-won on logit(champion out-of-fold p_fav) + z(angle).
- **Data:** 2023, games with the angle defined (roughly weeks 4–18).
- **Test:** one-sided likelihood-ratio test for a **negative** coefficient. It passes if p < 0.05.
- **Caveats:**
  - 2023 is a research-exposed champion validation season.
  - With about 220 games, only a large effect is detectable.
  - A failure does not show that tracking is useless.

## Secondary (reported, not decisive)
- **T2:** the same angle with the no-vig closing-moneyline probability as the base, which tests for an edge beyond the market.
- **P1 proxy check:** the Pearson correlation between team-week OffSep and NFL Next Gen Stats team-week target-weighted
  `avg_separation` (published weekly, 2016+, already in the lab).
  - **NGS is an adequate weekly proxy** if r ≥ 0.5. That would allow a future multi-season, pre-registered separation test.
  - The two measure different moments (NGS: at catch or incompletion; BDB: at ball arrival), so a moderate r is expected.
- **Coverage profile (descriptive):** each team's man-coverage rate and its offense's separation against man and against zone.

## If T1 passes
It becomes a prospective hypothesis only. Weekly tracking data is not public, so it can be tracked live only through the NGS
proxy, and only if P1 passes. Under no circumstances does it change a model.

## Not allowed
- Changing the metric, the 3-game minimum or the direction after results.
- Testing additional tracking variants against outcomes.
