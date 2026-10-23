# NBA agent-reviewed pregame context - 2026-10-23

Completed before verified16:00Eastern first tipoff. Two bounded agents independently identified concrete gaps;root implemented the fixed study and local integration. All22existing protected model/forecast files unchanged. No promotion,paid service,odds ingestion,deployment or NFL edit.

## What was tested

| Fixed hypothesis | Log loss control -> new | Delta [corrected95%CI] | Better seasons | Decision |
|---|---|---|---:|---|
| season_continuity | 0.608294 -> 0.608490 | +0.000197 [-0.000926,+0.001286] | 1/2 | Rejected by fixed development gate |
| shared_possessions | 0.608294 -> 0.608297 | +0.000003 [-0.000139,+0.000144] | 1/2 | Rejected by fixed development gate |

Both tests used the same2460already-examined2024/2025games;train through target-2,calibrate target-1. Exactly2configurations/4base fits/4sigmoid calibrators;2comparisons corrected with Bonferroni,2000whole-game bootstrap draws. Gate>=1%LL gain,corrected CI<0,both seasons improve,Brier no worse. Neither passed. The prespecified315game opening-season subset is descriptive only;its accuracy cannot override worse log loss. No2025-26confirmation re-evaluation,current2026-27outcome selection or extra search after seeing these results.

Season continuity tracks current-season released games,age and prior-season share/interactions without arbitrarily resetting form. Shared-possession efficiency uses both matching positive box-score estimates;unknown boxes stay unknown. Every outcome is available strictly after tipoff+24h. A joint schedule-strength graph was deferred to a separate protocol.

## Useful addition for tonight

Filtered ESPN game injuries/current roster fields are now archived with real retrieval/provider timestamps,exact athlete/team IDs,source URLs,content SHA256 and append-only versions. Full game summaries,odds and pickcenter are never retained or used as inputs. No PDF parser or package install required. Source URLs: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401909848 and https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/4/roster . Official reporting rules: https://official.nba.com/nba-injury-report-2026-27-season .

Snapshot 2026-10-23T19:10:46.684439+00:00:12unstarted games,24team rosters,58injury rows(44Out/14Day-To-Day),zero source issues/conflicts/future-dated entries. Five team summaries returned no entries and remain unknown,not confirmed healthy. An older injury update is distinct from stale retrieval;lineups remain unconfirmed. The official HTML index can lag newer PDF releases: the 15:08 Eastern retrieval still listed a 14:15 report. The app displays the indexed report time and this limitation; PDF statuses are not parsed.

| Team | Released current-season games | Prior20game minutes retained on current roster |
|---|---:|---:|
| MIL | 1 | 74.6% |
| CHI | 1 | 62.6% |

These explain why82historical games are not82games of evidence for the current roster. Retention and known-Out minute shares are diagnostics,not causal absence effects or predicted point losses. Incoming players can have zero prior team minutes. No availability entry changes a winner/score probability in this implementation.

Both prespecified context configurations were frozen/committed before operational refit and archived for12unstarted games(24rows) at 2026-10-23T18:56:43.391850+00:00. Their failed gates are stored/displayed explicitly;they are research copies,not recommended replacements. Forecasts include hashes,creation/training/calibration availability cutoffs. Existing winners/score/individual copies remain intact. Descriptive future scoring is automatic on manual daily refresh,using earliest revision per game/candidate/config and no retuning.

## Verification and use

70 offline tests pass. New checks cover own/future outcome canaries,season boundary,strict24h lag,matching possession boxes,exactIDs,unknown reports,conflicts/future timestamps,finite positive minute denominators,started games,immutable context archives and daily orchestration. Independent agent QA found no concrete chronology/sample/freeze/archive issue. Actual Today/Research/Data pages rendered against real artifacts. Live-data QA caught a nested-expander incompatibility in Streamlit1.40;fixed with a checkbox and a populated-availability regression,without changing models or weakening tests.

Open START_NBA.bat ->1 -> Today -> Pregame availability & roster continuity. Use Refresh availability + save context research copies before tipoff;old source snapshots and forecasts stay saved. Daily option2 also collects it. Research & Calibration shows the two rejected numerical tests. Saved availability over60minutes old is visibly stale;empty reports are always unknown. No scheduled task or background source polling was created.

Next research: timestamped lineup/player-impact inputs and a separately preregistered joint strength model. Do not convert injury names or lost historical minutes into guessed probability adjustments. Props still require a validated minutes/rotation/availability model. No guaranteed accuracy improvement is claimed for the diagnostic panel.
