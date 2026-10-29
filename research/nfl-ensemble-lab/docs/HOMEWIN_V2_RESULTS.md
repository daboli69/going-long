# Home-win study v2: results

Run 2026-10-28/29. Protocol `18e98172`, Amendment 1 `98519f2f` (before any CLV sign), code `7fa8c37b`, one look.
Numbers: `reports/homewin_v2/results.json`, file SHA-256
`83fd6ac488eeb9f2c9502034492b4a212061efd67b51a37f483e9fc55dd95993`. **Every gate reading below is provisional until
Codex rebuilds it from the protocol and matches** (log loss and CLV to 4 decimals). Reused history; nothing is promoted.

## 0. Power
- **Log loss.** History MDE is 0.0106, twice the 0.005 SESOI. **N_LL = 1,126 frozen weeks.** Game outcomes cannot
  confirm a 0.005 edge in any useful time, so no prospective log-loss verdict will be issued.
- **CLV.** Primary point Friday (Amendment 1). **N_CLV = 7 frozen weeks.** T-90 was unusable as primary: 90% of
  T-90-to-close moves are exactly zero because GOING snapshots are about 3.4 hours apart.

## 1. Look-ahead in nflverse EPA (H1)
Walk-forward EP was fit on earlier seasons only, up to 10. Against nflverse EPA on pass/run plays, the play-level
correlation was 0.931 in 2003 (one training season), 0.962 in 2004 and 0.98-0.99 from 2012. Mean difference was +0.03
EPA/play before 2020 and +0.001 in 2026; success agreement was 88% in 2003 and 95-96% from 2012. Team-game EPA/play
correlation was 0.987. The look-ahead was real but small after the first few seasons. **Rerun of the frozen v1 specs
(weekly T_w): all four fail,** with results almost identical to v1. margin_platt +0.00669 [-0.00131, +0.01449];
xgb_deep +0.00168 [-0.00393, +0.00667]. Positive means worse than Elo.

## 2. Per-game decision points (H2)
At T-90 all four fail: margin_platt +0.00647 [-0.00137, +0.01443], worse in 11 of 15 seasons; xgb_deep +0.00124
[-0.00447, +0.00649], better in 7 of 15. Value of information on the same 3,756 games:

| Point | QB-change flags | elo | margin | xgb_deep |
|---|---:|---:|---:|---:|
| open | 0 | 0.6339 | 0.6400 | 0.6350 |
| Wednesday | 6 | 0.6332 | 0.6393 | 0.6349 |
| Friday | 83 | 0.6337 | 0.6395 | 0.6358 |
| T-90 | 99 | 0.6332 | 0.6390 | 0.6344 |
| close | 99 | 0.6332 | 0.6390 | 0.6348 |

Per-game timing raised QB-change flags from 27 (v1 weekly) to 99, nearly all arriving Friday. That moved log loss by
less than 0.001. QB news at this frequency is too rare to show up in season-scale win/loss scoring. No official inactives
are archived, so the T-90 and close points add nothing beyond Friday's injury report.

## 3. Stacking (H3), provisional pass
Fit on all 2012-2026 T-90 out-of-fold rows, 97.5% week-cluster intervals:
- elo + margin: elo 0.677 [0.475, 0.873], **margin 0.367 [0.130, 0.621]**.
- elo + xgb_deep: elo 0.578 [0.277, 0.848], **xgb_deep 0.411 [0.128, 0.721]**.

Both new-model weights exclude zero, so by the preregistered rule both **add value** to Elo. The size matters more than the
pass. Walk-forward stacked log loss is 0.6329 (margin) and 0.6330 (xgb_deep) vs Elo alone 0.6332, a 0.0003 gain. That is
about a fifteenth of the SESOI and far below anything the power analysis says can be confirmed prospectively. Read it
as "the play-by-play models carry some information Elo lacks", not as a usable edge. The three-input 2026 stack with
the market (n = 105) has every interval spanning zero, which says nothing either way.

## 4. CLV (H4)
2026 games only (quotes exist for no earlier season). **Primary, Friday / xgb_deep: mean -0.0012 [-0.0041, +0.0011],
44 toward vs 46 away, one-sided p = 0.62. Fail.** Friday / margin: -0.0018. T-90 moves are near zero for all models.

**Unplanned and descriptive only:** from the open, margin's view predicted the line's direction. Mean CLV was +0.0196
[+0.0085, +0.0317], 60 of 90 toward, p = 0.001. xgb_deep was +0.0115 [+0.0013, +0.0253], p = 0.036; Elo +0.0023
[-0.0087, +0.0180]. This is the most interesting number in the study. It is also 1 of 12 descriptive comparisons on 90
games from one partial season. Opening lines move most and are the softest, and the sign could reflect news that arrives
after the open and happens to align with play-by-play form. It is a hypothesis for a new preregistered prospective
test (open-point freezes), not evidence of an edge. No betting return was measured.

## Missing data (exact)
- Timestamped market: 2012-2025 (none). 2026: 90 of 106 games at open and Wednesday, 104 at Friday, 105 at T-90 and close.
- Injury timestamps: 2012-2014 and 2025. Official inactives: none archived.
- 2002: no walk-forward EP (no earlier season), so ratings start in 2003.
- The Kalman rating (item 5) was not run, as preregistered.
- Historical ESPN FPI: unusable (modified after games); captured prospectively only.

## Prospective proof
- Weekly freezes continue (`home_win_deep.py freeze`). Week 8 was frozen before kickoff.
- `home_win_v2.py freeze-game` freezes each game 105-90 minutes before kickoff, with market and FPI captured at that
  instant. It is tested in dry-run mode and not yet scheduled, because scheduling needs Travis's approval.
- No CLV verdict before 7 frozen weeks; no log-loss verdict (N_LL = 1,126).
