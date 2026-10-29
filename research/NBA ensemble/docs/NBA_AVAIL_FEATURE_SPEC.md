# Feature specification for the availability features (for an independent reimplementation)

Goal: for every labelled regular-season game, produce `full_value_diff`, `avail_effect_diff`, `missing_min_diff`, `avail_value_diff`
using only information available before the game. Inputs are listed in section 0. Tolerances for agreement are in section 8.

## 0. Inputs (read these files only)

- `research_nba_xgb/canonical/games.parquet`: one row per game. Use rows with `completed` and `verified` true as labelled games. Columns:
  `game_id` (str), `season` (ending year), `game_date` (America/New_York date string), `tipoff_utc`, `home_id`, `away_id`, `neutral`, `home_score`, `away_score`.
- `data/raw/archive/pbp_<season>/*.parquet` (take the file with the latest name): ESPN play-by-play for seasons 2021 to 2026. Columns used:
  `game_id, season_type, game_play_number, type_text, text, team_id, athlete_id_1, athlete_id_2, period_number, clock_display_value, home_score, away_score, scoring_play, shooting_play`.
  Use `season_type == 2` and games present in the labelled set. Sort each game by `game_play_number`.
- `data/cache/player_boxes.parquet`: ESPN player boxes. Columns used: `game_id, team_id, athlete_id, minutes, did_not_play, starter`.
  A player "played" when `minutes > 0` and `did_not_play` is not true.
- `data/cache/injury_reports.parquet`: parsed official NBA injury reports, one selected report per game day. Columns used: `game_id, team_id, athlete_id, status,
  reason, not_yet_submitted, available_at`. Keep rows where `game_id` and `athlete_id` are not null.

## 1. Stints (seasons 2021 onward)

Elapsed seconds of an event: for period p <= 4, `720*(p-1) + (720 - remaining)`; for p >= 5, `2880 + 300*(p-5) + (300 - remaining)`; `remaining` is the clock in seconds.
Event kinds from `type_text`: starts with "Free Throw" -> FTA; equals "Offensive Rebound" -> OREB; contains "Turnover" -> TOV; equals "Substitution" -> SUB; otherwise OTHER.
A substitution is a SUB event whose `text` contains "enters the game for"; `athlete_id_1` enters, `athlete_id_2` leaves; `team_id` is the team.

Starters per team (home_id, away_id): scan the game's events in order. For an event whose `team_id` is that team: if it is a substitution, the leaving player
(if never "seen" before) is a starter; then mark both players seen. If it is not a substitution, its actors are `athlete_id_1`, plus `athlete_id_2` when the event is a scoring play
of kind OTHER (assist); every actor not yet seen is a starter; mark seen. A game is dropped if either team does not end with exactly five starters (if the box has exactly five
`starter` flags for the team, those five may be used instead).

Process events in order keeping the on-court sets. At a substitution event: if the leaving player is not on court or the entering player already is, drop the whole game.
Otherwise, if the event's elapsed time is greater than the current stint start, close the current stint at that time and start a new one with the same lineups; then apply the swap.
Stint points = change in home score and in away score between stint start and end (scores read at the closing substitution event; the first stint starts at 0-0; the last stint ends at the last event).
Count per side (side = event `team_id`) within a stint: FGA = events with `shooting_play` true of kind OTHER; FTA; OREB; TOV.
Possessions per side = FGA + 0.44*FTA - OREB + TOV. Drop stints with end time <= start time.

## 2. Ratings (RAPM)

Observation = one stint seen from one offence (two per stint). `poss = (home_poss + away_poss)/2`, drop stints with poss <= 0.5. y = 100 * points / poss; weight = poss.
Columns: intercept; home-court sign (+1 for home offence, -1 for away offence, 0 if `neutral`); for each player an offence indicator (on court for the offence); for each player a defence indicator.
Weighted ridge: penalty 3000 on every player column, 1e-6 on intercept and home-court. Refits every 7 days starting at day 2021-12-01 (calendar days).
The fit at day R uses only stints from games dated <= R-1, with weights multiplied by `0.5^((R-1 - game_day)/730)`. Player rating = offence coefficient - defence coefficient (points per 100 possessions).
A game dated D uses the latest refit with R <= D. Players with no rating use 0.

## 3. Candidates (per team per game)

Process labelled games from season 2021 on in order of (game_date, tipoff_utc, game_id). For each team keep its list of previous games (appended after the game is processed), each with the map {player: minutes} of players who played.
Candidates for a team-game = every player who played in any of the team's previous 10 games, plus every player on that team's injury rows for this game.
Per candidate:
- `gp_last10`: number of the previous 10 team games (fewer early on) in which the player played.
- `avg_min`: weighted mean of the player's minutes over the games played among those previous games; weight `0.8^(n-1-i)` where i is the index among the previous games (n of them), i.e. newer games weigh more. Missing if none.
- `streak_missed`: number of most recent consecutive previous team games not played (count back from the newest).
- status: injury `status` if listed, 'NotYetSubmitted' if listed with `not_yet_submitted` true, 'NotListed' otherwise.
- reason category from the injury `reason` text, lower-cased, first match in this order of substrings: 'g league'->gleague, 'two-way'->gleague, 'assignment'->gleague, 'rest'->rest, 'management'->rest, 'personal'->personal,
  'suspension'->suspension, 'health and safety'->health_safety, 'not with team'->not_with_team, 'injury'->injury, 'illness'->injury, 'soreness'->injury, else 'other'; unlisted players have 'other'.
- label `played` (from the game's own box) - used only to fit the play model.

## 4. Play-probability model

Design matrix columns, in order: indicators for status in [Out, Doubtful, Questionable, Probable, Available, NotYetSubmitted]; indicators for reason in
[injury, rest, gleague, personal, suspension, health_safety, not_with_team, other]; indicator (Out and injury); indicator (Questionable or Doubtful, and injury);
`gp_last10/10`; `clip(avg_min, 0, 40)/40` with missing avg_min = 12; `min(streak_missed,10)/10`.
Logistic regression, L2, C = 1.0. For games of season T, fit on all candidate rows of seasons 2022 .. T-1 (games from 2022 on only; no model, hence no features, for 2022 and earlier; requires more than 500 rows).

## 5. Team values

For one team-game with play probabilities p_i: expected minutes m_i = p_i * clip(avg_min (missing=12), 4, 38); rescale so sum m_i = 240; value = sum_i (m_i/48) * rating_i.
Full-health value: use p_i = 1 for "usual" players (`gp_last10 >= 5` and `avg_min >= 10`), otherwise the model p_i; same rescaling.
Missing minutes = sum over usual players of (1 - p_i) * clip(avg_min, 4, 38).

## 6. Game features (home minus away unless stated)

- `avail_value_diff = home_expected_value - away_expected_value`
- `full_value_diff = home_full_value - away_full_value`
- `avail_effect_diff = (home_expected - home_full) - (away_expected - away_full)`
- `missing_min_diff = away_missing_minutes - home_missing_minutes`

## 7. Output

A parquet with `game_id` and the four features for every labelled game of seasons 2023 to 2026 for which they can be computed.

## 8. Agreement tolerance

Report, per feature, the correlation with the primary implementation's values, the mean and maximum absolute difference, and the games with absolute difference above 0.05.
Differences are expected only from solver tolerance and from edge cases the specification leaves open; every ambiguity found while implementing must be listed.
