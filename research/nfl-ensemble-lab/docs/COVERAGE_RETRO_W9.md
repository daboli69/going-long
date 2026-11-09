# Coverage matchup, Week 9 Sunday: would it have called the good and bad days?

Written 2026-11-09, committed before any score below was computed. Exploratory and descriptive: 13 games is far too few to validate anything, nothing is promoted, and the Coverage tab stays history, not a forecast.

## Disclosures

- The Week 9 scores and several box-score facts (for example the Packers-Patriots turnovers) were known before this rule was written. The rule below was fixed without looking at any receiver's or quarterback's Week 9 line against the coverage numbers.
- The coverage matchup was not built to predict single-game receiver lines. This is a first look at whether it points the right way, not a test it was designed to pass.

## Games and inputs

Sunday 2026-11-08 games only (13); Thursday's JAX-BAL is excluded and Monday's BUF-MIN is unplayed. Each game is rebuilt as of Week 9: FantasyPoints weeks 1 to 8 plus last season, nflverse quarterback coverage tags for 2022 to 2025, and defense position profiles from passes before Week 9 only (`covcard.build(before=(2026, 9))`). The quarterback is the one who threw the most passes in the game, so a starter-selection miss cannot count against the data.

## Predictions (fixed now)

1. **Receiver edge.** For each receiver the card lists (at least 60 routes pooled over 2025 and 2026, top 8 per team), the card's `edge`: his man and zone yards per route weighted by how often the defense plays man and zone, minus his overall yards per route. Outcome: receiving yards in the game minus his average receiving yards per team game in 2026 before Week 9.
2. **Position share.** For each team-side and position (WR, TE, RB): the card's expected share of targets against this defense minus the quarterback's usual share. Outcome: the position's actual share of targets in the game minus the same usual share.
3. **Quarterback EPA.** For each quarterback-game: the card's expected EPA per pass minus his usual EPA per pass. Outcome: his actual EPA per pass in the game minus his usual.

## Scoring

- Spearman rank correlation between each prediction and its outcome, with a permutation p-value (10,000 shuffles, seed 20261109) and the share of cases where the signs agree.
- All named players and games are listed, ranked by the prediction, not by the outcome. Nothing is dropped after seeing the result.
- Reading rule: a correlation counts as evidence of direction only if the permutation p-value is below 0.05 **and** the sign agreement is above 55%. With these sample sizes a pass would still be a lead to follow prospectively, not a finding.

## Results (run 2026-11-09, `scripts/covcard_retro.py`, numbers in `docs/coverage_retro_w9.json`)

| Prediction | n | Spearman | Permutation p | Signs agree | Reading rule |
|---|---:|---:|---:|---:|---|
| 1. Receiver edge vs yards over his usual | 102 | -0.14 | 0.17 | 46% | Fails |
| 2. Position share of targets | 78 | +0.30 | 0.008 | 67% | Passes |
| 3. Quarterback EPA per pass | 26 | +0.32 | 0.115 | 52% | Fails |

- **Receivers: the coverage edge did not call good or bad days.** The top third by edge averaged 3.0 receiving yards below their usual and the bottom third 2.1 above. The largest edges (Gadsden, Burks, Mayer) were small-sample man and zone splits, and two of the worst misses (Burks and McConkey, 0 yards) may be players who did not play. That was not checked and the rule was not adjusted for it.
- **Quarterbacks: right direction, not reliable.** The two largest predicted gains (Shedeur Sanders +0.12, Drew Lock +0.11 over their usual EPA) both beat their usual by about +0.3. But the predicted shifts are tiny next to game-to-game noise, the signs agree only 52% of the time, and p is 0.115.
- **Position share passes the rule.** Added after the first run and not part of the rule: the three positions of one team-game sum to 1, so shuffling whole team-games gives p = 0.014 on 26 team-games. By position, tight ends carry it (Spearman +0.52, n = 26), wide receivers are weakly positive (+0.24) and running backs show nothing (-0.08). The predicted shifts are small (typically 1 to 2 points of target share).
- **Reading:** a lead for tight-end and wide-receiver target share, to follow prospectively. It is not a finding at 13 games, and nothing here supports calling individual receiver or quarterback days from coverage fit.
