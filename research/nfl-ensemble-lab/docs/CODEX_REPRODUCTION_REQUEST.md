# Independent reproduction request for Codex

Written 2026-10-29. Seven studies on the branch `codex/projections-20261019` were built and run by Claude, one look each.
**Every gate reading is provisional until you rebuild it from the protocol document alone and the numbers match.**
Please do not read the results documents before you have your own numbers, and report disagreements without editing
either side's files.

**Tolerances.** Deterministic fits: match to 4 decimals. Simulation metrics: within 3 Monte Carlo standard errors (state
yours). Live-data inputs can differ: Kalshi history is archived but its listings change, and the nfldata API at
api.nfldata.org is currently a parked domain, so the code falls back to the lab's `games.csv`. Report any differing input
counts first.

| # | Study | Protocol (frozen first) | Code commit | Rebuild with | Numbers to compare |
|---|---|---|---|---|---|
| 1 | Deep home-win model | `docs/HOMEWIN_DEEP_PREREGISTRATION.md`, `741a13e7` | `555d5317` | `scripts/home_win_deep.py backtest` | 3,756 games; log loss elo 0.6332, xgb_deep 0.6354, margin_platt 0.6397; all four gate candidates fail |
| 2 | Home-win v2 | `docs/HOMEWIN_V2_PREREGISTRATION.md`, `18e98172` + Amendment 1 `98519f2f` | `7fa8c37b` | `scripts/home_win_v2.py backtest` | H1 margin_platt +0.00669; H2 T-90 xgb_deep +0.00124; H3 margin weight 0.367, xgb_deep 0.411; H4 Friday xgb_deep CLV -0.0012; power N_LL = 1,126, N_CLV = 7 |
| 3 | Drive-level simulator | `docs/HOMEWIN_SIM_PREREGISTRATION.md`, `067e5583` | `8e3cdb51` | `scripts/home_win_sim.py pilot`, then `backtest` | drive log loss -0.16911; margin RPS +0.0509; win log loss 0.6401 vs elo 0.6332; stack weight 0.184; 99.0% drive agreement with nflverse |
| 4 | Kalshi props vs simulator | `docs/PROPS_KALSHI_PREREGISTRATION.md`, `31af0b08` | `60b72455` | `scripts/props_kalshi.py pilot`, `pull`, `replay`, `score` | 1,242 ladders, 6,654 thresholds; CRPS K 1.0286, base 1.0707, market 0.9978; K vs base -0.0421; settlement agreement 99.91% |
| 5 | Market-anchored props | `docs/PROPS_MARKET_ANCHORED_PREREGISTRATION.md`, `7964284b` + power `4909f1ba` | `6ff6e5bc` | `scripts/props_market_power.py`, then `scripts/props_market_model.py` | 762 ladders in 6 weeks; M1 +0.0007 [-0.0037, +0.0051]; placebo p 0.119; M2 -0.0434 |
| 6 | Joint score model | `docs/FORECAST_PREREGISTRATION.md`, `94e455cc` + Amendment 1 and power `db086e43` | `cc41214a` | `scripts/forecast_study.py pilot`, then `run` | tau 4.0 / 3.0; L1 margin CRPS 7.507 vs Elo-normal 7.475 (+0.0323 [-0.0296, +0.0941]); K1 b = 0 every week; K2 +0.0044 [+0.0004, +0.0090]; total-lean Spearman -0.168 |
| 7 | Market lag, availability events, usage | `docs/MARKET_NEWS_PREREGISTRATION.md`, `396af66a` + Amendments 1 and 2 | `5bb093a1` and `d7c047c9` | `scripts/usage_study.py pilot`, `run`, `confirm`; `scripts/market_news_study.py power`, `run` | usage gain targets +0.0441 [0.0392, 0.0490], carries +0.0513, 2024 confirmation +0.0555 and +0.0585; kappa_K winner +0.010, spread 0.000, total -0.023; kappa_P winner +0.111, total +0.223; 29 key-player events |

Notes for the rebuild:
- Studies 4 and 5 use the shared Kalshi cache under `data/cache/props_kalshi/`; a fresh pull takes several hours
  (about 63,000 candle requests, polite pacing).
- Results files should be compared by their JSON values, not by file hash, because git's line-ending conversion changes
  the bytes on checkout.
- Open questions I would like a second opinion on: whether the walk-forward training minimum (500 thresholds) is what
  leaves only 6 scorable weeks in study 5, and whether the Kalshi spread/total median interpolation is sound.
