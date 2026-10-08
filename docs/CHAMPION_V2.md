# Champion v2 (promoted 2026-10-08)

**What changed.** For the markets and positions below, the player projection is no longer the last-12-games mean with 80% weight on current-season games. It is a
prior-strength blend, `(k*current_mean + c*prior_mean)/(k + c)` over the same 12-game window (k = current-season games in the window; c fixed per market), and receiving yards also
use a pooled spread. Nothing else in the Champion changed (window, minimum games, QB verified starts, injury scaling, Poisson counts).

| Market | Positions | c | Shape |
| --- | --- | --- | --- |
| receptions | WR TE RB | 2 | Poisson (negative binomial parked, see below) |
| receiving yards | WR TE RB | 1 | lognormal on positive games with a per-position coefficient of variation (WR .7, TE .7, RB .9) and nonpositive mass shrunk toward the position rate (10 pseudo-games) |
| receiving TD, anytime TD | WR TE RB | 4 | Poisson |
| rushing TD | RB | 3 | Poisson |
| passing TD | QB | 4 | Poisson |

Unchanged (shadow only): rushing yards, passing yards (blend and pooled spread were not supported by a holdout interval excluding zero), every position not listed.

**Evidence** (research/trend-intelligence, ledger P3-1, P3-6/P3-6b; promotion_check_champion_v2.json). Parameters fit on 2021-2023, validated on 2024, confirmed on 2025 (a
confirmation holdout: wave-2 experiments had looked at 2023-2025). Full probability chain at realistic lines, Brier gain over v1: receptions +1.3%, receiving yards +2.9%,
receiving TD +2.2%, rushing TD +1.5%, anytime TD +2.0%, passing TD +3.3%; every season 2024 and 2025, player-clustered intervals above zero, worst segment -0.7%. v1 was
overconfident (calibration slope for receiving yards 0.42); v2 reaches about 0.80, still overconfident. Settled 2026 predictions (809 contracts, 16 games, one week, mostly the
first three games of the season): Brier 0.2491 to 0.2435, interval includes zero. This neither confirms nor refutes the historical gain. Independent QA reproduced the P3-1
numbers from raw data with separate code.

**Switch and rollback.** `config/champion_policy.json` (`"active": true`). Set it to `false`, or run the build with `GOING_CHAMPION_POLICY=v1`, and the next data refresh restores the
previous model; with v1 in force the stat dictionaries are identical to the pre-v2 code. Profiles built under v2 carry `policy: "champion-v2"` and the season-evidence method string
"prior-strength blend c=... (champion-v2)", which the tracker files as its own cohort (`champion-v2`). A slate mixes cohorts: rushing yards and unlisted positions stay on 80/20.

**Known limits.** (1) The injury/availability scaling still rebuilds a yardage spread from the overall mean and sd (existing behaviour, QA finding D3); a patch that keeps the zero
mass is parked in `research/trend-intelligence/pending/injury-scaling-keeps-zero-mass.patch` because the frozen today-ranking-v1 experiment hashes that file. (2) Negative binomial receptions
(+0.6-1.1% Brier on top, P3-5) needs a change to `propProbabilities`, also hashed by that experiment: patch parked in `pending/negative-binomial-receptions.patch`; activate both when
a today-ranking-v2 registration is made. (3) No historical prop prices exist, so nothing here measures ROI or closing-line value. (4) The Today ranking v1 experiment keeps collecting,
but from the promotion date its probabilities come from v2 for the listed markets; rows carry the policy string so analyses can split before and after.
