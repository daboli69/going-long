# In-game tracker v2.1: pre-registration

Written on 1 November 2026, before version 2.1 was fitted or scored. The git commit that holds this file is the timestamp.

## Why

Reconciling the eight 1pm games of 1 November 2026 with the official play-by-play showed that the history the models learn from counts attempts differently from the live feed (`docs/INGAME_TRACKER.md`). The nflverse columns count sacks as pass attempts and leave quarterback kneel-downs out of rushes. ESPN's box score does the opposite. With ESPN-style counting, the count mismatches against the live box scores fall from 34 to 10 of 198 player lines.

## The one change

Version 2.1 is version 2 with a single difference: `EVENT_DEFINITION = "espn"` in `lab/ingame.py`. A pass attempt excludes sacks, and a rush includes kneel-downs. Everything is then refitted from scratch on that definition: team volume, share and efficiency constants, pools, and the PyMC share model (same priors, same seed, 700 draws after 1000 tuning steps, 2 chains). Nothing else is changed. The win-chance model is not touched.

## Test

Same split as version 2: fit through 2023, test on 2025 and 2026 weeks 1 to 8, evaluated once. Both runs use the committed code and the same player-game rows.

## Rule for replacing version 2

Paired comparison on rows both versions track, CRPS of the final stat at the five checkpoints, per stat (receiving, rushing, passing). Quarterback rushing rows are left out of the rushing comparison, because the two definitions give different final totals for quarterbacks (kneel-downs).

- Version 2.1 replaces version 2 for a stat if the mean CRPS gain over version 2 has a 95% block-bootstrap interval above zero (resampling games) and the Diebold-Mariano p after a Holm correction across the three stats is below 0.05.
- If no stat passes, version 2 stays live. Version 2.1 is also not adopted for a stat where it is worse with an interval entirely below zero.
- Secondary, reported only: the reconciliation count mismatches (above), and results by checkpoint.

## Not changed

Sportsbook in-game prices and routes are still unavailable. The 2026 test weeks overlap the weeks used to score version 2, as before.
