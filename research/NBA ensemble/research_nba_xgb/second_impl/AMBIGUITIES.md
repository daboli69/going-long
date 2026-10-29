# Ambiguities and decisions

1. Status 'NOT YET SUBMITTED' rows (status text, not_yet_submitted true) have athlete_id null in the data, so they are filtered out by the "athlete_id not null" rule. Where a row has not_yet_submitted true and a player, I let NotYetSubmitted override the status text.
2. Injury status strings other than the six listed get an all-zero status indicator.
3. Injury rows are matched to a team-game by (game_id, team_id); candidates = injury athlete ids for that team.
4. SUB events whose text lacks "enters the game for" are treated as ordinary non-substitution events (no counts, actors = athlete_id_1 for starter detection).
5. Starter scan covers the whole game for each team (as written); the box-starter fallback is used only if the scan does not give exactly five and the box has exactly five flags.
6. Stint close: counters are reset on closing; a substitution at the same elapsed time as the current stint start does not close a stint. Events are assigned to the stint in play order (events after a sub at the same second belong to the new stint).
7. Possession side = event team_id; events with a team not equal to home/away are ignored. Overtime clocks use the 5-minute rule; clocks without ':' are parsed as seconds.
8. Stints with poss<=0.5 or end<=start are dropped. Games dropped for lineup inconsistency still do not affect candidates (candidates use boxes only).
9. Ratings: players with stint data only in training get columns; all players seen in any stint get columns (extra columns shrink to 0). Refit grid: 2021-12-01 + 7k days up to the last labelled game date. A refit with no stints gives zero ratings. Games before the first refit get no ratings (not relevant for 2023+).
10. Decay weight uses calendar days between R-1 and game date.
11. Candidates: team history is continuous across seasons (no reset); history includes the 2021 season games. Only previous-10 games of that team, regardless of season gaps.
12. A "played" player in history uses box minutes > 0 and not did_not_play; the minutes stored are box minutes.
13. Candidates for 2022 games are built, but the model for season T uses 2022..T-1 so the first scored season is 2023.
14. Play-probability model: unscaled design as specified, sklearn LogisticRegression(C=1, L2, lbfgs).
15. Values: if a team's sum of expected minutes is 0 the game is dropped (NaN). A candidate with missing avg_min uses 12 for expected minutes, clip(.,4,38). "Usual" requires avg_min present.
16. Missing minutes uses clip(avg_min(missing=12),4,38) for usual players only (avg is always present for them).
17. Stints: first stint starts at 0-0 and 0 s; last stint ends at the last event's elapsed time and score.
