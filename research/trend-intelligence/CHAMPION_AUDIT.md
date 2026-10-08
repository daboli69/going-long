# Champion audit (2026-10-08)

Machine-readable version: `champion_map.json`. Benchmarks: `champion_benchmark.json`. All claims were read from code and checked against the frozen 2026
tracker; the production numbers are reproducible with `scripts/trend_research/champion.py`.

## How the Champion works

1. **Projection** (`scripts/build_pipeline.py`): per player and market, the last 12 regular-season appearances (QBs: verified starts), at least 5, weighted
   **80% on current-season games / 20% on earlier-season games** whenever both exist (equal weights otherwise). Counts are Poisson(weighted mean); yardage is a
   lognormal on positive games plus the empirical zero/negative mass. Nothing else sets the mean except an injury/availability scale, a next-man-up boost and, for QBs,
   a pressure scale (`index.html attachProjection`, `shared/football-injuries.js`). There is no matchup, pace, game-script, weather or home/away adjustment for players.
   Games: team trailing scores (same window and weights), normal margin/total, no opponent strength, home field or injury term.
2. **ffopportunity and Fantasy Points are not inputs.** Expected points appear only as descriptive facts.
3. **Recommendation layer** (`index.html`, `shared/football-picks.js`, `football-confidence.js`): there is **no BET/PASS tier**. `best_model` ranks by model win
   chance (favourites lead) and is tracked only at EV >= 3%; `going_picks_v2` rates the football case /100 from direction-of-model, production, usage trend, role-matched
   matchup (rec/rush yards only), with/without, availability, independent of price, EV and probability. `best_value` (sharp-consensus) has produced zero records.

## Is current-season usage handled correctly? No.

After one game, that single game carries 80% of the weight although eleven earlier games supply the minimum sample (effective sample size about 1.5). Week 1 puts all weight on the
prior season with no shrinkage. The weighted standard deviation is deflated, probabilities are never capped or recalibrated (the live feed showed 0.99999999937; the maximum frozen tracker value is 0.9990), and the repository's own
(unaudited) season review reports 80/20 with higher RMSE than equal weights in 2026. Wave-2 experiment **E7** quantifies it on 2021-2025: replacing 80/20 with a prior-strength blend lowers
the mean's MAE in weeks 1-6 by about 6-7% for QB passing yards/TDs and about 1.3% for receptions and receiving yards, and changes nothing for touchdowns or rushing yards. The exploratory E7b, using the Poisson log score, finds gains in every count market, partly an artefact of zero predicted means. The 2026 prospective check (E10, 179 receptions predictions, 11 early-season) is
uninformative, neither confirming nor refuting.

## Real benchmarks

* **Production tracker, 2026 weeks 1-4** (frozen predictions, settled): the unselected universe (`all_projection`, 2,319 decided bets, 77 games) has Brier 0.258 against 0.230 for the
  vig-included price-implied probability, flat-stake ROI -4.4% (95% CI -10.3% to +3.6%). The gap between model and price largely reflects selection (where the model disagrees most with the price, the price tends to be right). `best_model` (EV-selected) predicts a 58.3% win rate and wins 49.4%, ROI -2.7%
  (CI -8.2% to +2.6%); on the 71 games it shares with the other groups its ROI is -6.4%. `going_picks_v2` has only 6 settled predictions. No cohort shows a demonstrated edge; none shows a demonstrated loss beyond the vig.
* **Closing-line value cannot be measured honestly**: no closing record is flagged near-kickoff and the median closing gap is about 3.6 days before kickoff.
* **Reconstructed Champion, 2021-2025** (point-in-time): mean absolute error by market and season in `champion_benchmark.json` (for example receptions about 1.24, receiving yards about 15.7, passing yards about 62.5).
* **Game model vs the closing market** (1,359 games 2021-2025): margin RMSE 13.54 vs 12.63 for the market line; total RMSE 13.68 vs 13.08. The team-score model is clearly weaker than the market.
* Reconstruction fidelity: the rebuilt mean equals the frozen `projection_mean` to 1e-6 for 91% of receptions and receiving-yards records (and every frozen receptions probability equals Poisson of that mean);
  the mismatches are injury/availability multipliers and, for QBs, the 730-day dormancy rule for verified starts.

## Weaknesses in the recommendation architecture (verified)

1. Football thesis, price and counter-evidence are separated in the rating, but the **tracked `best_model` cohort is selected on EV**, so the evidence rating plays no part in what is evaluated, and EV above 25% is
   removed as a "check".
2. The football rating nets evidence linearly: a model that opposes the direction (-2) can be offset by two +1s; there is no veto. Model, production and usage trend are overlapping functions of the same recent games, so a
   tier-4 case can be one signal counted three times.
3. The only continuous term is direction-gap divided by the model's own SD, so a misestimated narrow SD raises the rating.
4. Matchup evidence exists only for receiving and rushing yards; passing, receptions, TDs and games have none.
5. The `check` veto in the picks assessor is dead code in production (`flags` is always empty); the stale-model and EV-review audit used by the board does not reach Picks v2.
6. Picks v2 bypasses the -500 odds floor the tracker applies to every other group, so a near-certain, tiny-payout price can be frozen.
7. The line is chosen (closest to even money) before the thesis is rated, so rating depends on which line the market makes nearest -110.
8. Missing evidence lowers the tier by withholding positives (stale context removes usage/matchup points); it is not scored negative, but it is not neutral either.
9. One failing readiness check sends an otherwise supported case to "Check first".
10. The same bet appears in several tracking groups and on both sides in `all_projection`; groups cannot be pooled as independent samples. The game is the cluster.
11. Overdispersion is ignored in Poisson pricing (receptions variance/mean about 1.22, passing TDs about 0.75).

## Proposed Challenger architecture (not implemented)

football projection (Challenger mean: prior-strength blend + ffopportunity in-season expected volume) -> uncertainty (unweighted or shrunk SD, probability bounds) -> sportsbook line and price -> edge assessment kept separate
from the football rating -> evidence (descriptive badges, including Fantasy Points) -> concern -> recommendation. GOING Rating stays strength of the football case; the Score stays separate.
