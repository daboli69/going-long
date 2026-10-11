# Full-engine confidence research — October 11, 2026

Research branch `codex/model-confidence-research`, base `d990931`. No betting
model promoted, provider credits consumed, production publication or 2026 outcomes
used in these experiments. Public revised nflverse historical files are cached
outside Git; result artifacts contain only aggregate metrics, fitted research
priors and source hashes. `DATA_INVENTORY.md` maps every market's actual inputs.

## Completed experiments

| Fixed challenger | Evaluation sample | Existing/simple comparator | Challenger | Finding |
| --- | --- | --- | --- | --- |
| Current-season opponent-adjusted ridge margin | 448 games, 2024–25 | Current PF/PA MAE 10.3848 points | 10.3936 | Rejected: paired improvement CI −0.3184 to +0.2926 |
| Same ridge total | Same 448 games | Current PF/PA MAE 10.3345 | 10.4061 | Rejected: CI −0.2717 to +0.1331 |
| Carry/target opportunity ATD | 4,211 player-games / 224 games, 2024 | Reconstructed fixed Champion Brier .14149 | .13828 | Promising: delta −.00321; game-cluster CI [−.00571,−.00054] |
| Same ATD formula | 4,182 player-games / 224 games, 2025 | Reconstructed fixed Champion .13895 | .13397 | Promising: delta −.00498; CI [−.00741,−.00234] |
| Opportunity × shrunk efficiency passing yards | 400 QB starts, 2025 | Current-team mean MAE 60.00 yards | 58.28 | Improvement vs simple mean: paired game CI [−2.69,−.75] yards; raw weighted Champion 58.50, not the passing-yards refit |
| Same stages, passing TD counts | Same 400 starts | Current mean MAE 1.0266 | 1.0154 | Small improvement vs mean; not a probability/market result |
| Same stages, receptions | 4,211 appearances, 2025 | Current mean MAE 1.2844 | 1.2969 | Does not improve baseline |
| Same stages, receiving yards | 4,208 appearances, 2025 | Current mean MAE 16.6255 | 16.8447 | Worse: game-cluster error delta CI [+.0224,+.4037] yards |
| Same stages, rushing yards | 2,505 appearances, 2025 | Current mean MAE 12.6217 | 12.8154 | Does not improve baseline |

The ATD formula learns two global conversion rates on 2021–23:
`lambda = earlier current-team carries/game × .0310903 + targets/game × .0442564`;
`P(TD) = 1 − exp(−lambda)`. All three RB/WR/TE groups improve Brier in both years.
This smooths zero-TD histories rather than manufacturing confidence. Calibration
slopes remain .716/.767; no diagnostic calibration fit was applied. Rare return,
defensive and recovery TDs are included in the inherited outcome/Champion labels
but have no separate opportunity term. This is a simpler first experiment, not
the zone/team allocation model preregistered separately in `td_protocol.json`.

No passing-yard refit superiority claim follows from comparing with the raw
weighted mean. Exact corrected 24-game posted-line research remains unchanged.
Historical closing game lines in `game_results.json` are diagnostic benchmarks,
not quotes executable at a pregame decision. Props/ATD have no matched sportsbook
prices here, no synthetic lines and no ROI/edge result.

## Integrity and limitations

- Protocols were fixed before fitting; alpha/home prior and demand/efficiency
  strengths were not tuned after evaluation. Ridge centering was corrected to
  solve the zero-sum constrained block with unequal team counts; the hypothesis,
  parameters and evaluation period remained fixed.
- Team forecasts use only the forecast season, whole-week cutoffs and a
  conservative kickoff +12h availability assumption. Props use current-team
  current-season observations, explicit participation and QB start identity.
  Aggregate training priors learn earlier relationships, not older player form.
- Training for general props uses available 2019–22 public rows; missing 2016–18
  rows are not invented. Zero-stat offensive appearances require positive snaps.
  Exact snapped game identity is required; unmapped rows are excluded. Yardage
  without the assumed opportunity (e.g. laterals) is reported as unsupported.
- Historical receipts are revised releases, not contemporaneous immutable
  snapshots. Props replay labels its retrospectively known roster/start cohort
  explicitly; it does not prove that availability was known pregame.
- 2024–25 were previously researched. Locked retrospective results are not an
  untouched promotion holdout. Paired game and player clustering are both
  reported for props; game forecasts use season-week clustering.
- Fresh independent specialist review was interrupted by the account usage
  limit. Root inspected both specialists' partial implementations, fixed adapter,
  stint, source validation and isolation issues, and added 20 offline regressions.
  Another reviewer should examine the actual code before any model promotion.

## Full-engine implementation method

One football feature pipeline should feed market-specific models:

1. Team possessions, pace, pass/run volume, QB availability and opponent-adjusted
   efficiency produce a joint home/away scoring forecast. Margin, total and
   moneyline must derive from the same joint score distribution, with push/tie
   treatment, rather than three conflicting formulas.
2. Passing attempts × efficiency; carries × rushing efficiency; targets × catch
   probability × yards/catch produce projections. Team volume constrains player
   shares. Role changes and uncertainty must be estimated from dated inputs.
3. Team scoring opportunities × goal-line/end-zone player allocation produces
   rushing/receiving/anytime TD counts. First/last TD require their own possession
   order and credited-scorer/settlement labels; an ATD gain does not validate them.
4. Market-specific residual distributions turn projections into Over/Under,
   cover and TD probabilities. Fit calibration on earlier folds and measure it
   on later observations. Alternative-line tails need separate checks.
5. NCAA needs its own team/player identity, opponent and availability contracts;
   NFL coefficients and defensive exports are not NCAA evidence.

The next meaningful experiment is historical **goal-line/zone and team volume**
for the promising TD model, then prospective frozen forecasts. General receiving
shrinkage failed; test team target volume and player share separately before
adding arbitrary matchup multipliers. The supplied nine defensive exports
currently affect DFS research/context, not betting probabilities. Paid-data lift
requires dated permitted exports; today's aggregates cannot backfill historical
features. Display likelihood, data support and predictive uncertainty separately.

## Reproduce offline

Use the project's Windows virtualenv Python, with cached public weekly stats,
snaps/players in `.cache/model-confidence-public` and games in
`.cache/model-confidence-games.csv`:

```text
python research/model-confidence/game_challenger.py --csv .cache/model-confidence-games.csv --output research/model-confidence/game_results.json
python research/model-confidence/td_volume.py
python research/model-confidence/props_replay.py
python -m unittest discover -s tests -p test_model_confidence_research.py
```

The ridge objective follows [standard ridge regression](https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression).
Game fields follow the [nflverse schedule dictionary](https://nflreadr.nflverse.com/articles/dictionary_schedules.html).
