# GOING Charts data files

`python scripts/charts_build.py` writes compact, versioned, point-in-time JSON files to `data/charts/` (each under 400 KB; the builder refuses to write a
larger one and trims the lowest-ranked rows to fit). It runs in `.github/workflows/data.yml` after the tracker step (`continue-on-error`, output
committed with `data/charts`). Public data only: nflverse, ffverse/ffopportunity, `data/history.json`, and the aggregate of `data/public_tracker`.
Licensed Fantasy Points data is never read, and `licensed_data_used` is `false` in every file.

Every file has the same envelope: `schema` (`id`, `version`, `fields`), `as_of`, `generated_at` (only moves when content changes, so identical rebuilds
produce no diff), `provenance` (sources and attribution), `method_flags`, `unavailable_fields`, `notes`, `data`. `index.json` lists files, sizes, hashes.

`method_flags` values are `descriptive` (describes what happened) or `predictive` (survived a pre-registered out-of-sample test). Everything is
`descriptive` today; see `research/trend-intelligence/OPPORTUNITY_VS_PRODUCTION.md` (E12). Chart copy must not imply the residual forecasts anything.

| File | Content | Source | Notes |
|---|---|---|---|
| `opportunity_vs_production.json` | per skill player 2026 YTD: expected PPR, actual PPR, residual, games, position, team, 3-game trend | ffopportunity `ep_weekly_2026` | players under 2 expected PPR per game omitted |
| `weekly_roles.json` | last 8 played weeks: offensive snap share, target share, carry share (arrays aligned to `weeks`) | nflverse stats and snap counts | **routes are not public**; listed under `unavailable_fields` |
| `scoring_opportunity.json` | expected vs actual TDs per game, red-zone targets, inside-5 touches, inside-2 carries, tier | `data/history.json` `scoring_role` | inside-10 is not in scoring_role; not estimated. Windows cross seasons |
| `team_trends.json` | plays, pass rate and pass rate over expectation (all plays and neutral situations) by team and week | nflverse play-by-play (`xpass`) | PROE is relative to the nflfastR xpass model |
| `model_calibration.json` | reliability bins, Brier and n by market and tracking group | settled `data/public_tracker` predictions | aggregate only; first pre-kickoff observation per contract; wins and losses only |

Unknown is `null`, never zero. A section whose source fails is skipped and its previous file stays; the script exits 1 so the workflow reports it.

## Reading `model_calibration.json` (at the 2026-10-09 build)

5,066 settled contracts, overall Brier 0.254, skill -0.018 versus always predicting the base rate. The top probability bins are over-confident (the 0.9-1.0 bin
stated 0.94 and won 0.72; the 0.8-0.9 bin stated 0.84 and won 0.56). That is descriptive evidence about the stated probabilities, not about profit.

## Tests and local run

`python -m unittest discover -s tests -p test_charts_build.py` (synthetic data, no network). `python scripts/charts_build.py --cache-dir <dir> [--offline] [--only name ...]`.
