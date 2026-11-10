# Model audit, frozen pre-kickoff game predictions
Games: 55 (weeks 6 to 9 of 2026), stale-data snapshots: 0.

## Accuracy against the market (no-vig moneyline)
- Brier: model 0.2205, market 0.1960; difference +0.0245 (95% bootstrap +0.0074 to +0.0424). Positive means the model is worse.
- Log loss: model 0.6319, market 0.5828; difference +0.0490 (+0.0105 to +0.0899).
- Margin MAE: model 9.84, market spread 9.03.
- Home margin bias (actual minus predicted): model -2.49, market -1.81. Home win rate 0.455 against mean model p_home 0.559.
- Where the model and the price disagree by 5 points or more (31 games): the model's side won 35.5%; the model gave that side 53.9%, the market 44.7%.

## Systematic over or under estimation
Home side: the model's mean win probability exceeded the home win rate by +0.104 and its home margin exceeded the actual by +2.49 points. Opponent slices are not tested separately: they are the mirror of the team slices for the same games.

## Random variance or repeatable weakness
72 slices were tested (team, home side overall, projection range, spread, model side, model-minus-market gap, week). 13 reached p < 0.05 before correction; about 3.6 would by chance alone.
Slices that pass the repeatable test (n >= 8, Holm p < 0.10, same sign in both halves): **1**.

Lowest raw p-values, plus the home-side-overall rows and every slice that passed (nothing hidden):

| metric | slice | value | n | bias | p | Holm p | same sign both halves |
|---|---|---|---|---|---|---|---|
| win prob | team | PHI | 4 | +0.399 | 0.001 | 0.04 | True |
| win prob | market spread (home view) | (-7.0, -3.0] | 15 | +0.320 | 0.001 | 0.07 | True |
| win prob | model minus market home prob | (-1.001, -0.1] | 5 | -0.553 | 0.001 | 0.08 | True |
| win prob | team | CHI | 4 | -0.468 | 0.004 | 0.30 | True |
| win prob | model minus market home prob | (-0.05, 0.05] | 24 | +0.243 | 0.006 | 0.41 | True |
| margin pts | market spread (home view) | (-7.0, -3.0] | 15 | +6.949 | 0.010 | 0.64 | True |
| margin pts | team | BAL | 4 | +17.778 | 0.010 | 0.64 | True |
| margin pts | model minus market home prob | (-1.001, -0.1] | 5 | -10.730 | 0.011 | 0.71 | True |
| win prob | home side overall | all games (home side) | 55 | +0.104 | 0.100 | 1.00 | True |
| margin pts | home side overall | all games (home side) | 55 | +2.487 | 0.132 | 1.00 | True |

## What passed
A slice that passes is a hypothesis, not a finding: it was found by searching 72 cells on 4 weeks of games. It becomes a candidate only if it is written down now and tested on weeks that have not been played yet.

## Reading this
A positive win-prob bias means the model rated that group higher than results supported. With this few games a team-level bias is mostly noise: one result moves a team's mean by a few points.
Findings only count after they hold on games the audit has not seen: the next weeks' frozen snapshots are the held-out set, and any change to the model goes through the Champion/Challenger gate in MODEL_RESEARCH.md.
