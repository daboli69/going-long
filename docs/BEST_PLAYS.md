# Daily best plays

The Best Plays tab is scoped to upcoming kickoffs on the current Eastern calendar day, separately for NFL and NCAA. NCAA has game lines only. Lists contain singles, not a combined ticket. Both sides of NFL props enter the ranking.

Highest estimated win chance uses existing historical models with at least five games, excludes existing stale/extreme-model audit flags, and ranks the chance of winning rather than estimated return. Negative estimated returns remain explicit. These are unvalidated estimates, not measured confidence. One selection per player/game market is shown, capped at six; different markets can still depend on the same game.

Best value is independent of historical projection availability. Matching two-sided full-game quotes remove the bookmaker charge proportionally. Pinnacle is required; other designated reference books are Circa, Bookmaker/CRIS and BetOnline. Every quote is at most five minutes old, references must be within 60 seconds of the recreational price, and disagreement over three percentage points rejects the selection. Use the lowest reference probability minus one percentage point, with a 2.5% return hurdle below decimal 1.67, otherwise 3%, plus 0.5% for Pinnacle alone. This public research filter is separate from the scanner, which additionally applies its power-method probability bound, calibration penalty, final window and availability checks. It never claims actionable status or supplies stakes.

Value excludes integer lines, NFL moneylines with possible ties, and touchdown scorer markets without an independently modeled returned-stake / full-field comparison. Existing model rankings can include touchdown props where supported. Empty lists explain the unmet requirements; no fallback probabilities are invented.

Discord arbitrage candidates now include both teams, market, both opposing selections, American odds, books and the illustrative split of a $100 total stake. The internal ID remains in the journal for deduplication, not in the message. NCAA's availability qualification remains.

Verification covers daily scope, both sides, stale and desynchronized quotes, missing models, returned stakes, away spread signs and escaping. Live-feed browser checks at 375/430/1280 pixels showed six NCAA model cards and an honest empty value list without page errors or horizontal overflow.

## Week 6 correction: game-line probabilities and returns (Oct 16)

GOING's NFL spread and total model is market-anchored (`shared/game-market.js`): at the posted line its probability is the line, so the old
"probability x price - 1" on a spread or total only measured the price against 50% and ignored the sportsbook's margin. It was not an independent edge.
It also drove a "Historical model estimates $x returned per $1" flag on those rows.

Best Plays now applies a presentation-layer correction (`shared/market-fair.js`, called after `rankBestPlays`; the frozen generator, policy functions and
every journal are untouched, and the original numbers stay on each row as `modelProb`/`modelEv`):
* With at least four independent other books quoting the identical contract and line (copied-price books count once, a book never judges itself, quotes
  under 60 minutes, dispersion under 1.5 pp) the win chance is that leave-one-out consensus (probit vig removal) and expected return is computed from it with
  pushes handled exactly (`win x (decimal - 1) - loss`).
* Otherwise the only estimate is the book's own de-vigged two-way price; expected return then shows the cost of the vig and no edge is claimed.
* An edge is "supported" only for a consensus-backed, non-exchange, fresh (15 minute) quote at or above a 1% return. Exchange prices (fee, spread and size
  unknown) and stale quotes never qualify. The "model gap" flag is removed from game rows, and badges read "Market-priced, no independent model edge" or
  "Consensus price comparison" instead of "Model-screened research".
* Player-prop probabilities still come from the player models and are unchanged.
Replay on the Oct 16 snapshot: 20 game rows carried a model-gap flag with 3% or more "expected return" before; 0 after. 33 rows showed 1% or more before, 11 after, none
supported (all were Novig exchange prices).

Touchdown opportunity evidence (`shared/td-opportunity.js`) describes the public role data (expected touchdowns per game, snap share, red-zone targets,
goal-line carries, inside-5 touches, role trend) with its as-of date, refuses data that is stale, future-dated or from another season, and never reads a missing
value as zero. It adds no probability.
