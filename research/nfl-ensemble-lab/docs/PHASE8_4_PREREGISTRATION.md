# Phase 8.4 pre-registration: high-variance underdogs and sharp line movement

**Written 2026-10-18, before either test was computed.** This study is local to the lab only.

**Question:** which underdogs win **more often than their price implies**?

## Definitions
- **Champion favourite:** the side with champion out-of-fold probability ≥ 0.5. **p_fav** is that probability, and an
  **upset** means the favourite lost (ties excluded).
- **Line favourite:** the side favoured by the opening spread (Sportsbook Review, 2016–21). Pick'em openers are excluded.
- **Spreads** use the favourite's perspective: a positive number is how many points it is favoured by.

## Test V: high-variance underdogs (football-only, primary)
- **Variance style index (VI) of the champion underdog:** the mean of four standardised, season-blended, as-of team traits
  (feature-store columns with the `{side}_blend_` prefix). Every trait is pre-signed so that higher = more variance:

  | Trait | Column |
  |---|---|
  | Offensive explosive-play rate | `explosive_rate` |
  | Defensive takeaways per game | `d_turnovers` |
  | Defensive sack rate | `d_sack_rate` |
  | Offensive pass rate | `pass_rate` |

- **Model:** logistic regression of favourite-won on logit(p_fav) + VI (standardised).
- **Pre-declared direction:** a negative coefficient (high-variance underdogs upset more often than p_fav says).
- **Window:** 2018–2025 (2,219 games).
- **Secondary, reported but not decisive:** VI(underdog) − VI(favourite).

## Test S: early line movement toward the underdog (market-informed, primary)
- **Movement:** m = favourite's opening spread − favourite's closing spread, using the line favourite. Positive means the line
  moved toward the underdog.
- **Primary S2 (beyond the champion):** logistic regression of line-favourite-won on logit(champion p for the line favourite) + m
  (standardised). Window: 2018–21, where the champion's out-of-fold probabilities and the SBR lines overlap.
- **Pre-declared direction:** a negative coefficient.
- **Secondary, reported but not decisive:**
  - **S1:** the same model with the opening-line probability in place of the champion. A related result is already known
    (Phase 8.1 H2b: movement predicts outcomes given the open), so S1 is a replication in favourite terms, not a new finding.
  - **S3:** the same model with the closing-line probability. The expected result is null, because the close absorbs the movement.
  - **Upset-flag table:** for moves of ≥ 1.5 points toward the underdog, the underdog's actual win rate against the rates implied
    by the opening line, the champion and the closing line.

## Decision rule (Holm across V and S2; one look)
- **A test passes** if its Holm-adjusted one-sided p < 0.05 **and** the coefficient has the pre-declared sign in a majority of
  seasons: ≥ 5 of 8 for V, ≥ 3 of 4 for S2.
- **If V passes:** a prospective football-only hypothesis, judged on the champion's archived final-stage forecasts from
  registration onward, over 256 games.
- **If S2 passes:** a prospective market-informed upset flag, judged on archived ESPN opening → latest-before-final-stage movement
  from registration onward, over 128 games with movement data.
- **Never:** no change to the champion or the registered challengers, and no re-testing of variants after the look.
