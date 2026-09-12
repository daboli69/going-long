# Daily best plays

The Best Plays tab is scoped to upcoming kickoffs on the current Eastern calendar day, separately for NFL and NCAA. NCAA has game lines only. Lists contain singles, not a combined ticket. Both sides of NFL props enter the ranking.

Highest estimated win chance uses existing historical models with at least five games, excludes existing stale/extreme-model audit flags, and ranks the chance of winning rather than estimated return. Negative estimated returns remain explicit. These are unvalidated estimates, not measured confidence. One selection per player/game market is shown, capped at six; different markets can still depend on the same game.

Best value is independent of historical projection availability. Matching two-sided full-game quotes remove the bookmaker charge proportionally. Pinnacle is required; other designated reference books are Circa, Bookmaker/CRIS and BetOnline. Every quote is at most five minutes old, references must be within 60 seconds of the recreational price, and disagreement over three percentage points rejects the selection. Use the lowest reference probability minus one percentage point, with a 2.5% return hurdle below decimal 1.67, otherwise 3%, plus 0.5% for Pinnacle alone. This public research filter is separate from the scanner, which additionally applies its power-method probability bound, calibration penalty, final window and availability checks. It never claims actionable status or supplies stakes.

Value excludes integer lines, NFL moneylines with possible ties, and touchdown scorer markets without an independently modeled returned-stake / full-field comparison. Existing model rankings can include touchdown props where supported. Empty lists explain the unmet requirements; no fallback probabilities are invented.

Discord arbitrage candidates now include both teams, market, both opposing selections, American odds, books and the illustrative split of a $100 total stake. The internal ID remains in the journal for deduplication, not in the message. NCAA's availability qualification remains.

Verification covers daily scope, both sides, stale and desynchronized quotes, missing models, returned stakes, away spread signs and escaping. Live-feed browser checks at 375/430/1280 pixels showed six NCAA model cards and an honest empty value list without page errors or horizontal overflow.
