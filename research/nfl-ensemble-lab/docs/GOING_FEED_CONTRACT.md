# Lab → GOING data contract: `going-nfl-lab-feed` v1

| | |
|---|---|
| **Producer** | `lab/going_feed.py` (validated by `going_feed.validate`) |
| **Publisher** | `lab/publish_going.py` |
| **Consumer** | GOING `api/nfl-lab.mjs` (validates `schema` and a `1.x` `schema_version`) and `shared/nfl-intel.js` (`GoingNflIntel.validate`) |

## Versioning
- `schema_version` follows semantic versioning.
- **1.x minor releases only add optional fields.** Consumers must ignore unknown fields.
- **Removing or renaming a field, or changing its meaning, requires 2.0.0.** The API would then serve the version the deployed site
  expects. The site rejects any major version it doesn't know, and shows "not available" rather than guessing.

## Guarantees
- **Read-only:** built only from existing artifacts. The feed never writes to models, the scheduler, the registry or archives.
- **Pregame only:** every forecast is an immutable stage snapshot archived **before** kickoff. Both validators reject any game whose
  `forecast.archived_at` is at or after `kickoff_utc`.
- **Post-game data stays separate:** `final_score` appears only after a game is completed. It is never mixed into a forecast.
- **No invented values:** absent data is `null`, or an empty list or object.
- **Sanitised:** no file paths, raw feature vectors, local hashes, research files, credentials or private data. The validator
  rejects feeds containing path-like or credential-like strings.
- **Probabilities and spreads:** probabilities are for the **home team**. Spreads are home-positive: +12.5 means the home team is
  favoured by 12.5, the nfldata convention. ESPN's home-negative spread is converted.

## Shape (v1.0.0)
```
{ schema: "going-nfl-lab-feed", schema_version: "1.0.0", generated_at: ISO-8601 UTC,
  source:    { publisher, scheduler_release, champion_version, challengers: [{version, label, registered_at}] },
  freshness: { latest_forecast_archived_at, stale_after_hours: 36 },
  notices:   { correlation, experimental, market, challengers },                       // fixed explanatory text
  performance: {
    historical:  { model: "champion", note, windows: [{window, games, accuracy, log_loss, brier, margin_mae}] },  // walk-forward
    prospective: { stage, games, required_games: 128, by_version: [...], note } },                              // archived pregame only
  games: [{
    game_id, season, week, home_team, away_team, kickoff_utc,
    status: "scheduled" | "in_progress_or_started" | "final", final_score: {home, away} | null,
    forecast: { stage, stage_label, archived_at, timeliness, stale_inputs, data_refreshed_at,
                champion: { version, p_home, predicted_winner, margin_home },
                models: [{ key, label, p_home, margin_home }],                           // the six original models
                disagreement: { vote, range, std } },
    stages:      [{ stage, archived_at, p_home, timeliness }],                           // forecast history for the game
    challengers: [{ version, label, p_home }],                                           // registered shadow challengers (research)
    player_intel: {
      qb: { home|away: { champion_assumes, starter_listed_out, starter_questionable, live_projection, live_status,
                         injury_report, injury_report_retrieved_at } },
      lineups: { home|away: { available, starters_expected_out, important_absences: [{player, unit, status, type, availability}],
                              ol_starters_expected, ol_regular_starters } } | null,       // analysis, not a champion input
      lineup_note },
    simulation: { experimental: true, stage, archived_at, p_home, margin_home, total, margin_p10, margin_p90, total_p10, total_p90 } | null,
    market: { at_forecast: { source, timestamp, p_home_novig, spread_home, home_moneyline, away_moneyline },
              latest: { source, retrieved_at, p_home_novig_current, p_home_novig_open, spread_home_current, total_current,
                        home_moneyline_current, away_moneyline_current } | null,
              champion_minus_market_at_forecast, comparable, warning } }] }
```

## Window
The feed covers games kicking off from 4 days before `generated_at` to 10 days after it.

## Staleness
The website marks the feed **stale** when `generated_at` is older than `freshness.stale_after_hours` (36 h). Stale feeds are
still shown, with a warning, because they remain valid pregame forecasts.
