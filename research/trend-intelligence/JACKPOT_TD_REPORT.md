# Jackpot TD markets: what predicts anytime, first, last and longest TD

Pre-registered as JP-1..JP-5 (specs hashed 2026-10-09T10:51:42Z before any 2024/2025 number was computed; ledger.json, LEDGER.md). Code: `scripts/trend_research/experiments11.py`
(registered experiments), `jackpot_data.py` (point-in-time features), `jackpot_posthoc.py` (exploratory checks, labelled as such). Numbers: `research/trend-intelligence/jackpot_td_results.json`.

**Protocol.** Fit on 2021-2023 only (history from 2019), validate 2024, holdout 2025, no refit. Population: Champion-ready QB/RB/WR/TE appearances (6,122 player-games in 2024,
6,171 in 2025; 270 / 271 games with at least one touchdown). Baseline B0c = Champion v2 anytime rate (WR/TE/RB `(k*cur+4*prior)/(k+4)`, QB v1), recalibrated on development
(`logit p = a + b*ln rate`; b is about 0.5, i.e. the Champion rate is over-dispersed for TD markets). Anytime: logistic, player-clustered intervals. First / last / longest TD:
game-level conditional logit over all candidates of both teams plus an "other" alternative (returns, defence, non-candidates; the first scorer is a candidate in 89-91% of games),
game-clustered intervals. Bonferroni over the 8-9 block comparisons. Metric: log loss (nats), also Brier and top-k.
Verdict rule (fixed in advance): PROMOTE = validation gain > 0, holdout gain >= minimum effect (.001 anytime, .005 game markets) and adjusted holdout interval above 0; REJECT = holdout gain <= 0 or interval below
the minimum effect; SHADOW otherwise.

## 1. Is FIRST != ANYTIME != LAST? Partly, and not where we expected

* **Player ranking is the same.** An anytime-trained score used as the only feature of the first-TD (last-TD) model scores identically to a model trained on first (last) TDs
  (holdout log loss 2.7736 vs 2.7733; own-minus-transfer difference .000, CI -.020 to +.020; last: -.002, CI -.018 to +.015). Same signals, market-specific slope and "other" mass.
* **Pre-registered position hypotheses all fail** (JP-1 H1-H3, 1,316 games): RB / WR / rushing-TD shares of first vs last TD differ by under 1.5 points (pooled 2024-25), intervals span zero.
* **Team side differs, in the opposite direction to H4 (stable).** The pre-game favourite scores 59.2% of first TDs, 57.6% of all TDs but only 51.8% of last TDs
  (last minus first -7.4 points, CI -11.2 to -3.3; same sign in each of 2021-2025: 52.6, 50.2, 53.1, 53.8, 49.4% last vs 55.6-64.2% first). Pre-game win probability
  has a first-TD coefficient of +.146 and a last-TD coefficient of +.031 (difference CI +.03 to +.22, post-hoc).
* **Concentration differs (post-hoc, interval excludes 0).** Players with >=30% of their team's expected-TD mass (PRIMARY tier, n=863 player-games) score the first TD 14.9% and the last TD 10.2%
  of games (+4.8 points, CI +2.0 to +7.6; 2024-25 +6.5, CI +1.9 to +10.4), anytime 49%. First TD concentrates on starters; last TD leaks to depth and the trailing team.
* Opening-script usage (share of the team's carries+targets on its first two possessions, team's recent first-TD rate) is positive in both years (+.04 nats) but not proven (SHADOW).

## 2. Feature verdicts (anytime = single-feature test over 25 comparisons; first/last/king = block test)

All features are computed for a player-game from his own EARLIER appearances (shift(1) before every window; verified by hand against raw play-by-play), pre-game lines, and the
inactive list. "xTD" = expected TDs from carries and targets using the league TD rate per yard-line zone (carry/target x zones 1, 2, 3-5, 6-10, 11-20, >20 yards from the goal; rates fitted on
2019-2023 plays, stored in `jackpot_data.zone_rates`).

| Feature (definition) | Anytime | First | Last | King | Note |
| --- | --- | --- | --- | --- | --- |
| `xtd12` / `xtd6`: xTD per appearance, last 12 / 6 | **PROMOTE** (+.011 / +.011) | PROMOTE (block OPP +.074) | PROMOTE (OPP +.065) | PROMOTE (OPP +.044; SHADOW under alt. baseline) | strongest single signal |
| `xshare6`: player's share of team xTD, last 6 | **PROMOTE** (+.011) | PROMOTE (block ROLE +.065) | PROMOTE (ROLE +.057) | - | defines the role tier |
| `snap3`, `snap6`: offensive snap share, last 3 / 6 | **PROMOTE** (+.005 / +.004) | PROMOTE (ROLE) | PROMOTE (ROLE) | - | |
| `inside5_touch12`: carries+targets inside the 5, per game, last 12 | PROMOTE alone (+.005) | in OPP | in OPP | - | negative weight once xtd12 is in (collinear): emit, do not score on it |
| `tdres12`, `tdres6`: actual TDs minus xTD (TD luck), last 12 / 6 | PROMOTE alone (+.004 / +.002) | SHADOW | SHADOW | - | gain disappears once xtd12 is in the model: xTD already is the regression to the mean |
| `rz_tgt12`: targets inside the 20, per game | SHADOW | in OPP | in OPP | - | |
| `team_implied`, `team_win_p` (closing lines) | SHADOW (+.001) | SHADOW (TEAM) | SHADOW (TEAM) | REJECT | tilts team mass, not players: use at team level |
| `vac_alloc`: xTD of regular teammates inactive today, allocated by active xTD share | SHADOW (+.0016, CI -.0007 to +.004) | REJECT | SHADOW | - | injury-created opportunity not proven; keep collecting |
| position dummies (RB/TE/QB) | SHADOW / REJECT (TE, QB) | SHADOW | SHADOW | SHADOW | position adds nothing beyond role |
| `d_xtd36`, `d_share36`, `d_snap36`: last-3 minus last-6 trend | REJECT / REJECT / SHADOW | REJECT (TREND) | REJECT | - | trend adds nothing beyond level |
| `open_share6`, `tm_first_td_rate` | - | SHADOW (+.043, CI -.014 to +.094) | - | - | first-TD specific |
| `late_share6` (4th-quarter-lead carry share) | - | - | SHADOW (+.013) | - | |
| `long_prop` (shrunk share of own TDs of 30+ yards), `adot12` | - | - | - | SHADOW (+.028, CI -.013 to +.072) | king-specific |
| Historical TD totals as ranking baseline (last-12 TDs) | no better than Champion (+.0002 under a fair transform) | - | - | - | the apparent +.0025 was a log-floor artefact |

Combined score (ALL) vs B0c, log loss per unit: anytime +.0174 (4.2%; CI +.011 to +.025), Brier -4.1%, weekly top-10 precision .48 -> .58 (18 slates, noisy; validation year flat);
first +.100 holdout / +.069 validation; last +.062 / +.065; king +.075 / +.040. First-TD top-3 hit .28 -> .32, top-10 .69 -> .71 (intervals include 0); king top-3 +7 points.
A lean post-hoc score (xtd12, xshare6, snap3, inside5) fitted on development gives the same gains (anytime +.0154 holdout; first +.090; last +.064; king +.077).

## 3. Caveats (be skeptical)

* No historical prop prices: log loss and hit rates only, no ROI or closing-line value. Per-game markets have 263-271 games per season, so most game-level blocks cannot be separated from zero.
* Baseline transform sensitivity (post-hoc): with log(rate+.05) instead of log(max(rate,.01)) the anytime result is unchanged (OPP +.010, ROLE +.011, ALL +.015); for last TD ROLE and ALL drop to SHADOW,
  for king OPP drops to SHADOW. Registered verdicts stand; treat first/last/king gains as upper-ish estimates. Refit on 2021-2024 -> 2025 anytime: ALL +.0175, OPP +.0133, ROLE +.0135.
* The candidate set is Champion-ready players who appeared: "active" is known pre-game from inactives, but the table cannot see a player hurt on his first snap. Scorers outside the set sit in "other".
* Zone TD rates were fitted on 2019-2023 (development plus two earlier years), not re-estimated.
* 2025 is a holdout for these experiments, but Champion v2 itself was tuned on the same seasons.
* Post-hoc items (tier first-vs-last, coefficient differences, transfer test, lean score, alt baseline) are exploratory and cannot support promotion.

## 4. Proposed `scoring_role` record (per player, per history.json profile)

Emitted by the build pipeline from nflverse play-by-play; every field uses games strictly before the build date; windows count the player's own appearances; `n` = appearances available (emit
`null` fields and `confidence: "low"` below 5).

```
scoring_role: {
  version: 1, as_of: "<last game date used>", n: <appearances in window, max 12>,
  xtd_pg_l12, xtd_pg_l6,                 // expected TDs per game from carries/targets by zone (zone rates table in config)
  xtd_share_l6,                          // share of team xTD (team = sum over team skill appearances, same games)
  snap_pct_l3, snap_pct_l6,              // offensive snap share
  inside5_touch_pg_l12, rz_tgt_pg_l12, gl_carry_pg_l12,   // carries+targets inside 5; targets inside 20; carries inside 2
  td_pg_l12, td_luck_l12,                // actual TDs per game, and td_pg_l12 - xtd_pg_l12 (shrink toward 0 in the price, never add)
  tier: "PRIMARY" | "SECONDARY" | "TERTIARY" | "FRINGE",  // xtd_share_l6 >= .30 / .15-.30 / .05-.15 / < .05
  trend: { d_xtd36, d_snap36 },          // L3 minus L6, informational (REJECT/SHADOW: do not rank by it)
  open_share_l6, tm_first_td_rate_l8,    // SHADOW, first-TD
  late_lead_carry_share_l6,              // SHADOW, last-TD
  long_td_share, adot_l12,               // SHADOW, king: (long30 + 8*b)/(TDs + 8), b = league share of rush/rec TDs >= 30 yd (dev: computed in code)
}
// game-time (not stored in the profile): team_implied, team_win_p, vac_alloc (xTD of regulars inactive today, by active share)
```

Role tiers on 2021-2025 (anytime rate / first per anytime / last per anytime, development): PRIMARY .47 / .28 / .21 (n=472), SECONDARY .33 / .26 / .23, TERTIARY .19 / .22 / .24, FRINGE .07 / .22 / .23. Tiers separate
anytime rates monotonically in all three periods.

**Scoring recipe (lean score, post-hoc constants in `posthoc_production_candidate`, refit 2021-2025):** `logit P(anytime) = -2.360 + .195*ln(rate) + 2.739*xtd12 + 1.852*xshare6 + .864*snap3 - .747*inside5_touch12`
(raw features, winsorised at the development 1st/99th percentiles, median-filled). First / last / longest: `P(i) = exp(k*s_i)/(exp(u)+sum_j exp(k*s_j))` over all candidates of both teams with s the anytime logit and
(k, u) = first (.922, -.420), last (.766, -.094), king (.800, +.280, plus .213*z(long_prop) + .129*z(adot12) as SHADOW). Nothing here goes live without a shadow period on 2026 data.
