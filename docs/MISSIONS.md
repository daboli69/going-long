# GOING Missions + Sharp Market Intelligence (experimental)

Route `/missions/` (`apps/missions/`), engine in `shared/`. Football/NFL only. No paid service, no production model change.
`?asof=snapshot` replays the saved odds file with a prominent "not live" banner.

## What exists
| Piece | File | Status |
| --- | --- | --- |
| Vig removal (proportional, power, probit), fees, source aliases, board builder, copy detection, leave-one-out consensus, sample-size reliability | `shared/sharp-consensus.js` | tested on synthetic + real feed |
| Research weights (flag OFF) | `config/sharp_weights.json` | hypotheses, unvalidated |
| Seeded paired Monte Carlo (copula joint outcomes, probability uncertainty, pushes, withdrawal/reserve, 4/8/12 weekend survival) | `shared/mission-sim.js` | analytic checks in tests |
| Offers, qualification, cross-game parlays, objectives, strategy comparison | `shared/missions.js` | 15 tests |
| Walk-forward weight learning vs equal/research/model, cluster-bootstrap CIs, snapshot buckets (24h/6h/1h/close), CLV, price discovery, prop over/under calibration with out-of-sample deploy gate | `shared/market-validation.js` | synthetic tests only |
| GOING model cross-check snapshot | `scripts/build_missions_model.cjs` -> `data/missions_model.json` | manual refresh |

## Findings from inspecting the repo (verify, do not trust)
* The NFL spread/total model is market-anchored (`shared/game-market.js`): its probability at the posted line is exactly 0.5, so
  Best Plays "EV" on spreads/totals is price versus 50/50 and ignores vig (e.g. Novig +115 shows +7.5%). Missions never treats the
  model as independent evidence: it is a cross-check and veto only.
* Exchange (Novig) prices carry ~0 overround; against the sportsbook consensus they look +EV only because margin is absent. Fee,
  spread and size are not in the feed, so exchange offers are used for information and never certified as executable.
* On the 2026-10-13 17:37Z snapshot no sportsbook offer clears a +1% return hurdle (best about +0.2%). Missions reports that.
  BetRivers and Parx prices are identical on every non-standard market and are counted as one source.

## Policy (product constraints, not fitted)
Return hurdle 1%, at least 4 independent sources, dispersion <= 1.5 pp, offer quote <= 15 min, consensus quotes <= 60 min,
price no shorter than -500, integer lines rejected (no push estimate), same-game parlays rejected (no executable price),
parlay price = product of posted leg prices (unverified, labelled).

## Not done / blockers
* No historical multi-book odds with outcomes and timestamps exist in the repo, so learned vs research weights, CLV, price discovery
  and the prop over-tax cannot be evaluated on real data. Tools exist and are tested on clearly synthetic data. Next: append-only
  snapshot capture (buckets in `market-validation.js`) from the scheduled refresh; run `walkForward` once enough weeks exist.
* Player-prop consensus (props have per-book over/under odds, Novig/FanDuel/Caesars/DraftKings/bet365 covered) is not wired into Missions.
* Missions simulate by reusing the current slate each weekend; future edges are not forecast.
* `data/missions_model.json` is not refreshed by workflows; a stale snapshot disables the model cross-check automatically.
