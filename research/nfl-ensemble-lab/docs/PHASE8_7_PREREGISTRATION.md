# Phase 8.7 pre-registration: multi-season separation edge from NFL Next Gen Stats, local lab only

**Written 2026-10-18, before any Phase 8.7 metric was computed or joined to outcomes.** Nothing changes in the champion,
the challengers or the GOING site. One historical look.

## Why
Phase 8.6 tested a Big Data Bowl (BDB) arrival-separation edge on 2023 only. It pointed the predicted way but was not
significant (p 0.23, 224 games). Its proxy check found that NGS team-week target-weighted `avg_separation` correlates
r = 0.58 with BDB arrival separation, which passed the r ≥ 0.5 bar for an adequate weekly proxy. NGS is published every
week from 2016, so the same edge can be tested over many seasons.

## Data
- **Separation:** `data/raw/ngs_receiving.parquet` (NFL Next Gen Stats weekly receiving, via nflverse), rows with
  `season_type == "REG"` and `week > 0` (week 0 is the season aggregate). Rows with missing `avg_separation` or `targets`, or
  `targets == 0`, are dropped. NGS lists only qualifying receivers each week; that limitation is accepted as is.
- **Games:** `data/raw/games.csv`, `game_type == "REG"`, final scores present, ties excluded. A team-week is joined to its game
  by season, week and team (team codes through `lab.ingest.normalize_team`).
- **Champion:** out-of-fold `p_weighted_average` from `lab.specialists.baseline.load_oof()` (exists for 2018+ only).
- **Close:** no-vig closing moneyline probability from `games.csv` (`market81.american_to_prob` + `novig`).

## Metric
- **OffSep(team, game):** Σ(avg_separation × targets) / Σ(targets) over that team's NGS receivers in that season-week.
- **DefSep(team, game):** separation the defense allowed = OffSep of the opponent in that same game (the target-weighted
  separation of the opposing receivers it faced).
- **As-of team edge for (team, season, week w):** E = mean(OffSep) − mean(DefSep), each mean taken over the team's games of
  the same season in weeks strictly before w. Each mean needs at least 3 earlier games with a value, otherwise E is missing.
  No cross-season carry-over. Higher = better pass-game separation matchup.
- **Angle:** E(underdog) − E(favourite). Larger favours the underdog. Predicted direction: a larger angle lowers the
  favourite's win probability beyond the base, i.e. a **negative** coefficient.

## Samples (fixed now)
- **Discovery:** 2018–2020. Champion OOF does not exist before 2018, so 2016–17 are not used for the champion test.
- **Confirmation:** 2021, 2022, 2024, 2025. **2023 is excluded** because it was examined in Phase 8.6. 2026 (in progress)
  is excluded.

## Primary test (champion base, decisive on confirmation only)
- **Favourite:** the champion favourite (`p_weighted_average ≥ 0.5` → home).
- **Model:** logistic regression of favourite-won on logit(champion OOF p_fav) + z(angle), using `upsets84._test` and
  `upsets84._logit` unchanged.
- **Standardisation:** z uses the mean and SD of the angle over the discovery games; the same frozen scale is used for
  confirmation (the test p-value does not depend on the scale).
- **Test:** one-sided likelihood-ratio test for a negative coefficient on z(angle).
- **Discovery result:** reported only. It does not gate confirmation and nothing is changed because of it.
- **Decision (confirmation 2021, 2022, 2024, 2025 pooled):** **pass** = one-sided p < 0.05 **and** the per-season
  coefficient negative in at least 2 of the 4 confirmation seasons (per-season fits with ≥ 40 games). Anything else is a fail.
- One primary decision, so no multiplicity correction.

## Secondary (reported, not decisive): beyond the market
- **Favourite:** the market favourite (no-vig close ≥ 0.5 → home); the angle is oriented to the market underdog.
- **Model:** favourite-won on logit(no-vig close p_fav) + z(angle), same one-sided test.
- **Samples:** discovery 2016–2020 (the close exists before the champion does) and the same confirmation seasons.
- Reported with the same pass criteria for reference only. Phases 8.3–8.5 found nothing beyond the close; this is not expected
  to pass.

## Descriptive (reported, not tested)
- Number of team-weeks and games with a defined angle per season.
- Upset rate by angle quintile (observed vs champion-implied) on confirmation games.

## If the primary passes
It becomes a prospective hypothesis only, to be registered separately with a frozen scale and a minimum game count before
any 2026+ evaluation. It never changes the champion, a challenger or GOING.

## Not allowed
- Changing the metric, the weighting, the 3-game minimum, the samples, the direction or the decision rule after results.
- Re-running with variants (cushion, air yards, other weights, position filters) against outcomes.
- Using 2023 or 2026 outcomes in this phase.
