# Official NBA injury-report PDFs: collection and coverage audit

Collected 2026-10-23 with `python -m nba_lab.injury_reports collect --start 2022 --end 2026`.
Code: `nba_lab/injury_reports.py`. Tests: `tests/test_injury_reports.py`.
Outputs (gitignored): `data/cache/injury_reports.parquet`, `data/INJURY_REPORTS_AUDIT.json`,
raw PDFs and `MANIFEST.json` under `data/raw/archive/injury_pdf/`.

This is a data collection only. No model, feature, frozen config or forecast uses it yet.

## Source and selection rule

- Source: `https://ak-static.cms.nba.com/referee/injury/Injury-Report_<date>_<slot>.pdf`, public, no login.
- Filenames were hourly (`_05PM`) through 2025-12-21. From 2025-12-22 they are quarter-hourly (`_05_00PM`).
- Hourly files are stamped half past: the `_05PM` file's own header says 5:30 PM, and its HTTP Last-Modified agrees.
- One report per ET game day. The collector takes the latest file whose header time, URL slot and HTTP Last-Modified are all at or before the day's first tipoff minus 1 hour.
- `available_at` is the latest of those three times. All three come from the publisher; our own retrieval was in October 2026 and is kept separately as `retrieved_at`.
- Each PDF is stored with its SHA256 and retrieval time. Slots that returned 403 are logged in the manifest and not requested again.

## Coverage (regular season)

| Season | Games | Game days | Days with report | Games on report | Both teams listed | Player rows | Not yet submitted | Rows without game_id | Unmatched player rows |
|---|---|---|---|---|---|---|---|---|---|
| 2021-22 | 1230 | 165 | 165 | 1230 | 1209 | 11949 | 71 | 22 | 3 |
| 2022-23 | 1230 | 164 | 164 | 1230 | 1210 | 10949 | 72 | 0 | 18 |
| 2023-24 | 1230 | 160 | 160 | 1229 | 1197 | 12368 | 58 | 4 | 25 |
| 2024-25 | 1230 | 163 | 163 | 1230 | 1218 | 13472 | 76 | 22 | 53 |
| 2025-26 | 1230 | 164 | 164 | 1230 | 1220 | 13351 | 63 | 44 | 206 |

- 816 of 816 game days have a qualifying report. 1,631 PDFs are archived. There were no download errors and no parse issues.
- `available_at` is before tipoff for every row with a game_id, in every season.
- Reports also preview the next day's games. Those 28,469 rows were dropped, so each game keeps rows from its own day's report.
- Rows without a game_id belong to games the report listed that are not in `games.parquet`. All of them are postponed games, for example the December 2021 COVID postponements, the January 2025 Los Angeles fire dates, and the January 2026 MIL@NOP, MIA@CHI, GSW@MIN and DAL@MIL games.
- "Both teams listed" counts games where both teams had at least one row. A team with nobody to report has no rows, so a missing team does not mean the data is missing.
- `NOT YET SUBMITTED` rows mean the team's status was unknown at that time. They do not mean the roster was healthy.

Statuses seen: Out, Doubtful, Questionable, Probable, Available. Counts by season are in the JSON audit.

## Player identity

Names are converted from "Last, First" and matched to ESPN `athlete_id` from `player_boxes.parquet`. Matching uses exact normalized names only: case, accents, periods and Jr./III suffix tokens are normalized. The first level with any candidate decides the match:

1. `team_exact`: same team and season (58,664 rows)
2. `team_suffix`: same team and season, ignoring the suffix (280)
3. `team_other_season`: same team, another season (2,009). These are mostly players who missed a whole season and so have no box that year, such as Zion Williamson in 2021-22 and Jamal Murray in 2021-22.
4. `season_exact`: another team, same season (434)
5. `any_exact`: any team, any season (397). Spot-checked; all are the same person, such as Gallinari, Bogdanovic and Zeller.

A match at any level needs exactly one athlete_id at that level; two or more is treated as ambiguous and left unmatched. Identity lookup uses boxes from the whole season, including later games. This resolves who a player is; it is not a feature value.

305 rows (19 names) stay unmatched and are listed in the JSON audit. They are players with no ESPN box in any season (Thomas Sorber in 2025-26, two-way and G League players) and name variants that we do not guess at: "Carlton Carrington" vs "Bub Carrington", "Alexandre Sarr" vs "Alex Sarr", "Kenyon Martin Jr." vs "KJ Martin". Adding any alias would need a reviewed, explicit table.

## Limits for the later study

- One early report per day. Late-evening games use a report from about an hour before the day's first tipoff, so late scratches are missed. A per-game cutoff would need more reports per day; the code supports it through `pregame_report` but does not do it yet.
- Regular season only. The play-in and playoffs are not collected.
- Before 2025-12-22, reports exist only hourly at :30. A 7:00 PM first tipoff therefore uses the 5:30 PM report.
- 2026-27 is not collected here. Running the same command with `--end 2027` collects it.
