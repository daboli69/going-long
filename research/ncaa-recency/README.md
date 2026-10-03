# NCAA recency research v1

Status: **audit completed; experiment registered; blocked on historical inputs; no fit, winner, promotion or production weighting change**. Source revision: `a609255b196724ab116c1754fcf5585ad9014884`. This is separate from `today-ranking-v1`; neither its artifacts nor its holdout were read.

## What production actually consumes

- `scripts/build_pipeline.py:73` assigns **80% current / 20% all older games** whenever both are present, even after just one current game. This is an existing policy, not a requirement or validated optimum. With one current game and eleven historical games, Kish effective sample size is approximately **1.55**, although the model reports twelve recorded games.
- `build_game_models` at line 218 takes the **last 12** per team across seasons and requires five recorded games per team, including older games. Home projected score is the mean of home weighted points scored and away weighted points allowed; away reverses the teams. There is no NCAA opponent-strength or home-field fit here. Both projected mean and residual SD feed browser normal distributions.
- Results enter preceding history only after `result_available_at`, otherwise **kickoff +12 hours**. The fallback is a chronology precaution, not evidence of actual publication time. Pooled residual RMSE is a diagnostic across historical seasons, not a fresh calibrated win probability or untouched result.
- `index.html:3432` loads `history.json` through `api/snapshot` with a static-file fallback. `gamesFromParlay` (3463) uses the matching history model, requiring a unique exact-team match within six kickoff hours. `gameQuotes` (4179) turns those means/SDs into spread/total/moneyline estimates. The season-aggregate `ncaa_lines.json.ratings` and its 13.39 slope **do not supply this NCAA model path** when `games_raw` exists. Such season-end ratings would be unsafe historical pregame inputs without dated versions.
- `scripts/pbp_features.py:47` selects last twelve games across seasons and aggregates unweighted neutral snaps (pre-snap WP .20–.80). The NCAA output lacks per-game rows, season-separated totals and effective sample counts. It supplies pace/pass-rate observations, not the NCAA score means. The NCAA canonicalizer omits player/coverage/pressure fields; no NCAA player, defense or coverage rows exist in this snapshot. NFL-only context/coaching data do not establish NCAA turnover.

## Verified local snapshot evidence

`audit-20261003.json` contains exact input/source SHA-256 hashes and a reproducible clock. The saved history was generated **2026-10-03 01:14:53 UTC**; NCAA PBP aggregates at **01:15:36 UTC**. Both list 2024–26 sources loaded, but schedule provenance is only `sportsdataverse: loaded`, without release hash or per-season row coverage.

| Observation | Count / finding |
| --- | --- |
| NCAA scheduled / modeled rows | 545 / 529; 544 scheduled in 2026, one unresolved 2024 schedule row |
| Minimum current games per modeled matchup | 98 with 2; 397 with 3; 34 with 4; no matchup with 5 |
| All modeled team sides' current weight | 1,058 at 0.8 |
| Historical diagnostic | 1,367 errors; margin RMSE 18.116, total RMSE 16.010; not untouched OOS/calibration |
| NCAA aggregate team rows | 330; latest observation in 2026 for 233, 2025 for 77, 2024 for 20 |
| Observation dates | Latest 2026-09-27; oldest team's latest 2024-08-30 |
| PBP rows | 469,215 eligible snaps; 98,184 neutral snaps |
| NCAA player / defense / coverage rows | 0 / 0 / 0 |
| Latest published NCAA score rows | 217; zero known result-publication timestamps |
| Saved bookmaker events | 131, generated 01:14:44 UTC; stored FRESH status describes that refresh, not the audit clock |

All 529 model rows include future season games, not just today's slate. Team latest-year counts include the broader PBP universe; they are not FBS-only or a measurement of current roster continuity. A newly generated file must never turn old team observations into current evidence.

The pinned `sportsdataverse==0.1.4` loader source reads public release assets under `sportsdataverse-data/cfb_schedules` and `cfbfastR_cfb_pbp`; upstream normalization derives from ESPN/cfbfastR. The local installed loader file SHA-256 is `6e4f45fa736d44e9ffa16952b6c14ee485c6b21e9e4b0b8dd2889e446c135ae4`, verified by reading package source only. No loader or provider function was invoked. Current raw release bytes were not retained by the build, so package/source inspection cannot prove which exact release revision produced the saved aggregates.

## Registered experiment and early season

Read [protocol.json](protocol.json) for fixed cutoffs, candidates, formulas and acceptance criteria. Preserve this registration; changes after fitting or outcomes require a new future version, with results/invalidation recorded separately. Register before fitting: development seasons 2018, 2019, 2021, 2022; chronological validation 2023–25; 2020 excluded before testing due to COVID schedule differences. Historical revised public data may support **retrospective diagnostics**, never a claim that today's rebuilt features were actually known at an old decision time.

Compare Champion to uniform 4/6/8/12-game histories, current-season means shrunk toward the previous-season mean with 2/4/8 pseudo-games, and decays with game-age half-lives 2/4/8 plus a fixed season-boundary discount. These grid values are experiments, not magical percentages. Keep the score architecture fixed so weighting is the only difference. Shrinkage gives a limited early-season sample less influence and lets its weight rise as games accumulate; missing prior/season evidence stays disclosed. Each forecast must retain current/historical counts, weights, effective n and source cutoff.

Choose at most one margin and one total challenger using historical chronological validation, before a **complete future 2027 season holdout**, August 1–December 19, unlock January 8, 2028. A full future season is deliberate: the elapsed 2026 early season cannot now be an untouched test of early-season shrinkage. No collection or fitting has been enabled by these files. Register any feasibility pilot separately; never invent missed captures or treat ranking observations as this experiment's data.

Same eligible games; RMSE primary, MAE/bias/coverage and stages 0–2/3–5/6+ current games secondary. Use paired time-block uncertainty and a simple earlier-data benchmark. Holdout gates: at least 500 paired games, 12 weekly clusters, 75 games per stage and at most 10% missing outcomes. Required benefit is 0.25 RMSE points, multiplicity-adjusted interval excluding zero, no stage MAE worsening above 0.5 points. Insufficient data means INSUFFICIENT. Promotion still requires Travis. Projection gains alone do not validate spread probabilities or returns.

**Exact blocker:** latest public snapshots contain neither raw multi-season completed schedules/game-level PBP features nor trustworthy historical publication versions. The 217 score rows cannot recreate the Champion's twelve-game inputs or test alternate histories. No NCAA comparative backtest was run; no weighting/window superiority is claimed.

## Turnover and feature-specific follow-up

No verified NCAA head coach/coordinator assignments, starting-QB timelines, depth charts or roster continuity enter the saved game-model/PBP path. Do not infer these from team names or zero missing fields. A newly available free endpoint is a possible source, not a verified historical as-of feature.

The upstream R loaders document free returning-production and weekly-rating releases. They need a separate coverage/license/schema/revision and point-in-time audit before acquisition/use: some weekly FPI rows are explicitly out of sequence, and season ratings are season-end aggregates. No extra API/account/paid service is needed merely to inspect documentation; no dataset was fetched here. Missing coordinator or starter assignments remain unknown. A future structural-break challenger needs a new protocol, genuine pregame timestamps, and enough changed/unchanged teams to validate separately.

Pace, pass share, efficiency, explosiveness and red-zone behavior should not share a universal stabilizing threshold. A future feature-specific study needs game-level counts/exposure and chronological posterior-predictive validation. The current snapshot only justifies identifying missingness and observation dates. Opponent-adjusted NCAA ridge features deserve their own experiment once raw history can be reconstructed; do not enlarge this weighting grid after seeing results. NFL recency remains a separate research question and is unchanged.

## Reproduce without network

From the repository root with the existing Windows Python environment:

```powershell
& C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/.venv/Scripts/python.exe research/ncaa-recency/audit.py --as-of 2026-10-03T12:59:18Z
& C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/.venv/Scripts/python.exe -m unittest discover -s research/ncaa-recency -p 'test_*.py'
```

The audit reads an explicit public-file allowlist; stdout is default. It never reads private inputs/ranking artifacts, downloads, fits, sends alerts or changes production data. Source rollback is deletion/revert of this research folder only; observations and frozen experiments stay retained.

## Primary sources

- Hyndman & Athanasopoulos: [rolling-origin cross-validation](https://otexts.com/fpp3/tscv.html) requires earlier observations; [exponential smoothing](https://otexts.com/fpp3/ses.html) gives decreasing older weights. Neither establishes an NCAA-optimal half-life.
- Stephens Lab: [empirical Bayes normal means](https://stephenslab.github.io/ebnm/articles/shrink_intro.html) supplies the shrinkage rationale; learned priors must use earlier data, with their uncertainty retained.
- SportsDataverse: [pinned Python loader source](https://raw.githubusercontent.com/sportsdataverse/sportsdataverse-py/v0.1.4/sportsdataverse/cfb/cfb_loaders.py), [R release loaders and point-in-time caveats](https://raw.githubusercontent.com/sportsdataverse/cfbfastR/master/R/load_cfb_datasets.R). New source capabilities do not imply GOING already consumes them.
