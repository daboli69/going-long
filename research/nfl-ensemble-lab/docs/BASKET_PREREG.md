# Quarterback line against the receiver basket: pre-registration

Written 2026-11-06, committed before any gap was computed. Football only. No staking and no bet sizing anywhere in this document.

## Question

A quarterback's passing yards equal the sum of his receivers' receiving yards. That is bookkeeping, not a forecast. So a book's quarterback line and the same book's receiver lines should agree after allowing for receivers who have no line. Does the gap between them predict which leg is wrong, does the market close it, and is it large enough to cover the vig?

## 1. Structural reason

The quarterback line and each receiver line are separate markets, priced by different traders and updated at different times, and receivers' lines are popular with casual bettors. Nobody is forced to keep the set consistent, and a consistent set is not what a bettor sees: they see one leg at a time. The gap might not close because fixing it needs a trader to move a leg against their own book's exposure, and because each leg is shaded for its own customers. A gap that closes before kickoff is noise. A gap that stays and predicts the result would show one leg is wrong.

This is a reason to look, not evidence.

## 2. Inputs: what exists and what does not

Exists:
- Every committed version of the GOING sportsbook feed from 2026-09-09 (201 versions, harvested into `data/raw/archive/props`), with each book's line, over and under odds (American), quote time and an in-play flag. 18 books, daily-fantasy pick'em sites excluded by the `dfs` flag. 14,095 book-snapshot-game combinations have a quarterback passing-yards line and at least two receiver lines in the same snapshot, covering 133 games.
- Play-by-play for 2026 (`data/raw/play_by_play_2026.parquet`, through week 9) for actual yards, and earlier seasons for checks.
- Kalshi passing-yards and receiving-yards ladders for the same games (`data/cache/props_kalshi`).

Checked before registering (structure, not a gap): in 2026 play-by-play, a team's quarterback passing yards equal the sum of its receivers' receiving yards in 95.9% of 244 team-games, with an average absolute difference of 0.69 yards. The identity holds closely enough to use.

Missing, and left missing:
- Sportsbook prop lines before 2026-09-09, so there is no earlier season.
- Fewer than twice-daily snapshots, so a line that moved twice between snapshots shows only its last value.
- Juice and limits: the lines are posted numbers, not executable prices.
- The share of passing yards that goes to receivers without a line. It is estimated, not known.

## 3. Fixed in advance

Units: one team in one game at one book in one snapshot. Receivers: those with a full-game receiving-yards line from sportsbooks (not pick'em) at that book and snapshot. A team-game-book needs the quarterback line and at least two receiver lines.

De-vig: the power method on the over and under prices of each leg (find k so that over probability to the k plus under probability to the k equals 1), then the over probability is the fair one.

Odds-adjusted line: line + sigma x z, where z is the normal quantile of the fair over probability and sigma is c x line. c is estimated separately for the quarterback and for receivers on the decide stage as the root-mean-square of (actual minus the odds-adjusted line) divided by the line. This gives a median-like number per leg.

Basket: B = the sum of the receivers' adjusted lines. Remainder share r(k) = the decide-stage mean of (quarterback yards minus the actual yards of the listed receivers) divided by quarterback yards, by number of listed receivers k (2, 3, 4, 5 or more; a bucket with fewer than 10 team-games uses the pooled mean). Implied quarterback line Q* = B divided by (1 minus r(k)).

Gap: G = Q_adj minus Q* in yards, and g = G divided by Q_adj. Positive means the quarterback is priced high against his receivers.

Stages by week: decide on weeks 1 to 4, confirm on weeks 5 to 8. Only games with a final result. The final pre-kickoff snapshot of each book-game is the one used for outcome tests. Week 9 and later are held for the prospective record.

Which leg is called wrong: regress the quarterback's error (actual minus Q_adj) on G, and the listed receivers' error (actual listed yards minus B) on G. If G is large and positive, the quarterback leg is called wrong when the first slope is negative and significant, and the receiver leg when the second is positive and significant. The two slopes are in yards per yard of gap.

## 4. Gate, before any real outcome or gap result is read

Planted mispricing: using the real structure (number of team-games and receivers per team-game, the lines) and the c values, simulate outcomes in which one leg is wrong by a fixed fraction rho of the gap, then run the full outcome test. rho = 0.25 is the smallest size of interest. A test is informative only if power at one-sided level 0.05/2 is at least 0.80. Report the number of team-games for 80% power. If the confirm stage cannot reach it, the outcome test is reported as uninformative and not read.

Closing test gate: the persistence coefficient kappa (below) is informative if 2.8 times its bootstrap standard error is at most 0.15.

## 5. Tests

- Outcome test (confirm stage only): the two slopes above, on the median gap across books for each team-game as the primary, bootstrap by game (2000 draws), one-sided, Holm across the two slopes. Per-book slopes are descriptive.
- Closing test (all weeks, outcome-free): for consecutive snapshots of the same book and game 6 to 30 hours apart, regress the change in g on the earlier g. kappa = minus the slope, the share of the gap closed per interval. Also regress the change in the quarterback's adjusted line and the change in the basket B on the earlier gap, to see which leg moves. Bootstrap by game. "Gap persists" if the upper end of the one-sided 95% interval for kappa is below 0.15. "Gap closes" if the lower end is above 0.15.
- Kalshi referee (descriptive): for games with a large book gap, whether Kalshi's quarterback median sits nearer the book's quarterback leg or its implied value from the receivers, from the nearest hourly mid before kickoff.
- Placebo: shuffle receivers across team-games within the same week and rerun the slopes 500 times. It should center at 0.

## 6. Cost check

Only for a result that passes. The rule: bet the leg called wrong against the gap, at that book's own odds for that side, on the final snapshot. Report the win rate against the break-even rate implied by those odds. One leg means one vig. The full basket trade (quarterback plus every receiver) is reported only as the sum of the legs' holds. No stake, no sizing.

## 7. Prospective record

Each week, save a write-once hashed file under `data/basket/` of every book's gap g, the legs and their odds, for unplayed games from the newest feed snapshot. Nothing is backfilled. Outcomes are added by a later scoring command.

## 8. Report order and rule

Completed, Model Research, Concerns, Next, Needs Travis. If nothing beats the vig, the result is "no edge found". Nothing in the app changes on this result.

## Amendment 1 (2026-11-06, committed before any gap is computed)

Implementation details left open in section 3. None depends on a result.
- The fair over probability used in the odds adjustment is clipped to 0.25 to 0.75, so a line quoted with extreme odds cannot move the adjusted line by more than a fixed amount.
- The c factors are found by iterating the definition four times (the adjusted line depends on c, and c on the adjusted line).
- Receiver errors use the line, floored at 5 yards, as the scale.
- Games are matched to results by home team, away team and kickoff date within a day. A game is final when its play-by-play reaches zero seconds remaining.
- For the outcome test, the primary value for a team-game is the median across books of the final pre-kickoff snapshot's gap, quarterback error and basket error.
- The gate for the outcome test uses the spread of the real gaps and the number of team-games (structure), never the relation between gaps and outcomes.
