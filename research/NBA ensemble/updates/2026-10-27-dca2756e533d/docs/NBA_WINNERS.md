# NBA winners research v1

This is a runnable six-algorithm starting point for **NBA outright winners, including overtime**. It lives separately from NFL/ABBEYS and does not publish picks or change existing models. It is not perfected or approved for betting. The registered protocol is `config/nba_winners_v1.json`; ending-year season 2025 means 2024–25.

## Six voters and the debate

| Voter | What it learns | Main limitation |
| --- | --- | --- |
| Elo | Opponent-adjusted sequential team strength; fixed K=20, home offset=65 | Slow after rotation changes; parameters are starting assumptions |
| Regularized logistic regression | Linear effects of team form, scoring, opponent strength, rest and venue | Cannot capture every nonlinear matchup |
| Histogram gradient boosting | Nonlinear interactions in those pregame inputs | Can overfit small samples |
| Random forest | Averages different tree partitions of the inputs | Often conservative; shares features with boosting |
| Gaussian naive Bayes | Class-conditional feature distributions | Independence assumption is poor for correlated basketball statistics |
| Ridge margin/Gaussian | Regularized expected margin converted to win probability using residual spread | Gaussian residual assumption and in-sample variance are uncalibrated approximations |

Every game retains six probabilities, picks, weights, contributions, strongest home/away cases, vote count and probability range. Models do not change their forecasts to agree. The resolver combines them using **only earlier settled out-of-sample squared errors**, shrunk toward Brier .25 with 100 pseudo-games, then normalizes inverse losses. It starts at equal weights. This transparent rule is frozen as a research starting point; it is not an optimized stacking model.

A range of at least .25 or a winner probability below .55 flags review. These are disclosed review rules, not validated betting thresholds. A pick still appears; an exact .50 uses designated home and says so. Agreement is not independent confirmation, since the models share inputs. `feature_values` shows the actual evidence; tree explanations are not fabricated.

## Free sources and current wiring

| Source | Role | v1 status |
| --- | --- | --- |
| [hoopR](https://github.com/sportsdataverse/hoopR) | R access to ESPN schedules, boxes, PBP and NBA Stats | Shared ESPN schedule JSON exports accepted |
| [sportsdataverse-py](https://github.com/sportsdataverse/sportsdataverse-py) | Python access and historical bulk archives | Active: public schedule parquet archives used by `load_nba_schedule` |
| [nba_api](https://github.com/swar/nba_api) | NBA.com team/player boxes, schedules and game logs | Next enrichment/cross-check adapter; not a v1 predictive input |
| [pbpstats package](https://github.com/dblackrun/pbpstats) | Possessions, on-floor lineups, shot zones and event corrections | Next possession/lineup feature layer; not yet integrated |
| [PBP Stats](https://www.pbpstats.com/) | Aggregated possession/lineup and on/off analysis | Companion verification source; not yet integrated |

These are not five independent providers. hoopR and sportsdataverse often expose the same ESPN or NBA feeds; pbpstats.com derives statistics from the package's processed data. NBA.com can throttle or block cloud requests. No paid source or API key is needed by this implementation. This environment permits GitHub archives; NBA/ESPN/PBP Stats live domains are not in its current network allowlist, so no live access to them is claimed.

The fetch command reads the exact GitHub release URLs used by the SportsDataverse loader, preserving raw hashes and retrieval times without depending on a changing package import surface. The ingest command accepts the loader's parquet or a hoopR JSON export:

```r
schedule <- hoopR::load_nba_schedule(seasons = 2025)
jsonlite::write_json(schedule, "nba_schedule_2025.json", dataframe = "rows", na = "null")
```

The boundary copies game ID, ending-year season, tipoff, teams, explicit neutral/completed flags and final scores only. No odds, provider win percentages or season-end records enter the features. Prefixes namespace ESPN game IDs; a future NBA.com join needs an explicit exact-game crosswalk, not a guessed ID match.

Regular-season flags alone are insufficient: the actual development archives include All-Star games and NBA Cup finals under season type 2. The adapter excludes non-NBA team codes, Cup championship games, playoffs/play-in/preseason, postponed/cancelled/in-progress rows, unknown tipoff/venue flags and invalid finals. Cup semifinals and other counted regular-season Cup games remain eligible. Conflicting duplicate IDs fail; identical duplicates deduplicate. Accepted seasons each contain 1,230 completed regular-season games in the retained development sources.

## Running locally

From the repository root, with Python 3.12:

```sh
python -m pip install -r scripts/nba_winners/requirements.txt
python -m scripts.nba_winners fetch --seasons 2023 2024 2025 --cache .cache/nba-winners/raw --output .cache/nba-winners/development.json
python -m scripts.nba_winners backtest --input .cache/nba-winners/development.json --output .cache/nba-winners/run-001.json
python -m unittest tests.test_nba_winners -v
```

For previously downloaded files or R exports:

```sh
python -m scripts.nba_winners ingest --input nba_schedule_2025.json --output .cache/nba-winners/import-001.json
```

Outputs use exclusive creation: choose a new receipt name on subsequent runs. Fetches always request the archive again, save raw bytes under a content hash, and fail visibly on network errors. The source receipt includes retrieval times, hashes and exclusions. Ingesting an old file does not certify source freshness. A complete run retains protocol/code/input hashes, forecasts, date-cluster paired intervals, Brier/log loss/accuracy, reliability bins, coverage and prediction correlations. Raw archives and full run outputs remain local in ignored `.cache/`.

The first 300 eligible completed games train the initial model; both teams need five earlier current-season games. Elo and rolling statistics reset each season. Supervised algorithms can learn across registered development seasons. Team features include full-season and last-5/10 margins, smoothed win rate, scored/allowed points, margin variability, opponent strength, rest, back-to-back schedule and recent game load. Possessions, four factors, travel and lineup status are absent from v1.

For a local upcoming slate, fetch development seasons and the current ending-year season into one new snapshot, then run:

```sh
python -m scripts.nba_winners predict --input .cache/nba-winners/current.json --output .cache/nba-winners/predictions-001.json
```

This considers only games tipping in the next 24 hours, requires actual source retrieval receipts at most 36 hours old, excludes future finals and never incorporates a target game's score. The current season also needs five prior eligible games per team; early-season exclusions are expected. No unplayed game is invented from an old archive. The locked 2026 holdout cannot be downloaded/evaluated/trained through these commands. Current season 2027 does not require opening 2026: v1 resets team features and can retain 2023–25 supervised training history. A fresh HTTP receipt establishes retrieval, not upstream completeness or an injury clearance.

## Chronology and evidence limits

Historical feature construction releases a final score 36 hours after tipoff and only then updates Elo/scoring histories. Prior scheduled tipoffs supply rest without revealing embargoed scores. Each UTC date freezes its weighting origin; algorithms refit every 30 days using only eligible earlier games. Weight updates use only earlier replay predictions with released results. The expanding home-win-frequency comparator uses the same eligible earlier training cohort. Every baseline is graded on the same forecast games.

**This is retrospective out-of-sample replay, not prospective tracking.** Revised archive schedules/scores were retrieved today; historical publication times, injuries and rescheduling decisions are not reconstructed. The 36-hour rule reduces result overlap but does not prove historical availability. Development results can guide a separately registered v2; they cannot establish held-out performance. No tuned calibration layer, ROI or market-edge claim is included.

Season 2026 is registered as an untouched holdout for this implementation. It has not been opened by this work. Any future holdout run must be a separately authorized, frozen evaluation; repeated inspection/tuning would invalidate that role. Passing development tests is not model promotion. See the retained [development report](../research/nba-winners/README.md).

## Next stages

1. Add exact-game NBA.com crosswalks and lagged team boxes: possession-adjusted offensive/defensive ratings, pace and four factors. Check duplicate underlying feeds instead of treating them as extra evidence.
2. Add pbpstats possession/lineup parsing and PBP Stats aggregate checks. Estimate player/lineup strength with shrinkage and capture injuries, likely starters and expected minutes **before tipoff**. Do not substitute today's lineup for a historical pregame lineup.
3. Register a second model version and a chronological comparison for the extra inputs; calibrate on an earlier window and assess on untouched later data. Record immutable prospective picks, inputs, model versions and subsequent official outcomes.
4. Require paired Brier improvement versus Elo, equal weights and home frequency, nonworsening log loss, calibration/coverage review and existing promotion approval before a live release.
5. Extend to spreads/totals with validated margin distributions and actual timestamped lines; then player props with minutes, usage and joint uncertainty. Winner accuracy by itself does not validate spread or prop forecasts.
