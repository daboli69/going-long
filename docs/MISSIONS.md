# GOING Missions + Sharp Market Intelligence (experimental)

Route `/missions/` (`apps/missions/`), engine in `shared/`. Football/NFL only. No paid service, no production model change.
`?asof=snapshot` replays the saved odds file with a prominent "not live" banner.

## Choosing the games
The form lists every upcoming game grouped by Eastern kickoff day (Thursday night is Thursday, not Friday UTC). The next game day is selected by default; tick any games across days, or use "Only this day". The engine takes `mission.events` (game ids) or `mission.date` (ET day). "Paths to target" states the price a ticket must pay for the chosen exposure (for example $20 to $100 at 100% exposure needs +400), lists straights and one-book cross-game parlays that reach it ranked by chance of hitting, and says plainly when the slate cannot (one game cannot form a priced parlay; same-game parlay prices are not in the feed).

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

## Historical odds archive (added by the Oct14 archive release; verify before relying on it)
`docs/HISTORICAL_ODDS_ARCHIVE.md`: a private, finite The Odds API archive (649 verified NFL games 2024-2026, 353,032 observations,
ten books: Pinnacle, DraftKings, FanDuel, BetMGM, Caesars, BetOnline, Bovada, LowVig, BetRivers, Fanatics). It lives only on the owner's
PC and in owner-authenticated private storage, so it is **not reachable from cloud sessions** and has not been run here.
* It has **no Novig or Kalshi** quotes, so the research claim behind the largest weights (Novig 7.5, Kalshi 7) cannot be tested on it.
  Only equal vs research (FanDuel, DraftKings, Pinnacle, BetOnline, Caesars, BetMGM, Fanatics) vs learned weights among those books can.
* One board about 30 minutes before kickoff per game (props: sampled). No 24h/6h/1h snapshots, so price-discovery leadership and
  multi-horizon CLV are not testable from it; that board is not a certified closing line.
* Run offline on the PC that holds the archive (nothing is written inside Git):
  `python scripts/missions_history_export.py` then `node scripts/missions_backtest.cjs <root>/missions-backtest-input.json --out <outside-repo>/report.json`.
  The exporter reuses the archive's actual-schedule gate, keeps the latest pre-kickoff board per game, pairs prices only within one
  book/market/line, drops pushes, and joins the real final score from `data/nfl_betting.json`. Tested on synthetic fixtures only.

## Not done / blockers
* The backtest above has not been run on real data (private archive unavailable to this session); results are unknown, not positive or negative.
  Learned vs research weights, the spread/total/moneyline split and calibration will be real once the owner runs it.
* No stored 24h/6h/1h/close snapshots of the live feed yet; price discovery and CLV need those (`market-validation.js` has the buckets).
* Historical prop prices exist only as a sampled archive; the prop over/under tax and prop consensus are not wired to it.
* Player-prop consensus is not wired into Missions.
* Missions simulate by reusing the current slate each weekend; future edges are not forecast.
* `data/missions_model.json` is not refreshed by workflows; a stale snapshot disables the model cross-check automatically.
