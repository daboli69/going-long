# FPDS local ingestion — metadata only

Subscription rows, unmatched identities and derived player values stay in ignored local data folders. No website login, scraping or API. Sources are read-only. Copy hashes and full private mapping report live under `data/raw/fpds/` / `data/cache/fpds/`.

Inventory: 145 files; imported unique CSV copies 139; weekly feature tables 6. Import time 2026-10-21T00:46:04.940954+00:00.

## Files

| File | Bytes | Modified UTC | Data rows | Table | Schema | Season: explicit weeks | Key columns |
|---|---:|---|---:|---|---|---|---|
| coverageMatrixExport (1).csv | 6427 | 2026-10-07T23:24:58.232171+00:00 | 32 | coverage_matrix | H001 | 2025: season summary; week unknown | season=Season; team=Team Name |
| coverageMatrixExport (2).csv | 6422 | 2026-10-08T00:25:13.891934+00:00 | 32 | coverage_matrix | H001 | 2024: season summary; week unknown | season=Season; team=Team Name |
| coverageMatrixExport (3).csv | 6425 | 2026-10-08T00:25:26.000983+00:00 | 32 | coverage_matrix | H001 | 2023: season summary; week unknown | season=Season; team=Team Name |
| coverageMatrixExport (4).csv | 6415 | 2026-10-08T00:25:37.578585+00:00 | 32 | coverage_matrix | H001 | 2022: season summary; week unknown | season=Season; team=Team Name |
| coverageMatrixExport (5).csv | 6170 | 2026-10-08T00:25:47.484846+00:00 | 32 | coverage_matrix | H001 | 2021: season summary; week unknown | season=Season; team=Team Name |
| coverageMatrixExport.csv | 6387 | 2026-10-07T23:24:47.847177+00:00 | 32 | coverage_matrix | H001 | 2026: season summary; week unknown | season=Season; team=Team Name |
| efficiencyExport (1).csv | 144263 | 2026-10-07T23:25:54.804533+00:00 | 489 | efficiency | H002 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| efficiencyExport (2).csv | 1248504 | 2026-10-08T20:03:32.377897+00:00 | 4358 | efficiency | H003 | 2025: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| efficiencyExport (3).csv | 1232009 | 2026-10-08T20:04:19.271472+00:00 | 4289 | efficiency | H003 | 2024: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| efficiencyExport (4).csv | 1254808 | 2026-10-08T20:05:21.371356+00:00 | 4359 | efficiency | H003 | 2023: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| efficiencyExport (5).csv | 1246530 | 2026-10-08T20:06:08.511219+00:00 | 4347 | efficiency | H003 | 2022: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| efficiencyExport (6).csv | 1261920 | 2026-10-08T20:07:26.202801+00:00 | 4389 | efficiency | H003 | 2021: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| efficiencyExport (7).csv | 291797 | 2026-10-08T20:08:02.159338+00:00 | 1016 | efficiency | H003 | 2026: 1,2,3,4 | season=Season; week=WEEK; team=Team; position=POS |
| efficiencyExport.csv | 102628 | 2026-10-07T20:56:33.706002+00:00 | 358 | efficiency | H002 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| lineMatchupsExport.csv | 5976 | 2026-10-07T20:53:28.338925+00:00 | 30 | line_matchups | H004 | 2026: season summary; week unknown | season=Season; team=Team Name,Team |
| offenseSnapsExport (1).csv | 68060 | 2026-10-07T23:26:19.253519+00:00 | 426 | offense_snaps | H005 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| offenseSnapsExport.csv | 68060 | 2026-10-07T20:57:09.238389+00:00 | 426 | offense_snaps | H005 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (1).csv | 30718 | 2026-10-07T23:28:22.987967+00:00 | 77 | passing_advanced | H006 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (2).csv | 30673 | 2026-10-08T00:31:00.610887+00:00 | 77 | passing_advanced | H006 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (3).csv | 31799 | 2026-10-08T00:31:16.491584+00:00 | 80 | passing_advanced | H006 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (4).csv | 32785 | 2026-10-08T00:31:30.245161+00:00 | 83 | passing_advanced | H006 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (5).csv | 30775 | 2026-10-08T00:31:44.961622+00:00 | 78 | passing_advanced | H006 | 2021: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (6).csv | 30673 | 2026-10-08T00:32:08.533778+00:00 | 77 | passing_advanced | H006 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (7).csv | 31799 | 2026-10-08T00:32:17.894646+00:00 | 80 | passing_advanced | H006 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (8).csv | 32785 | 2026-10-08T00:32:27.060108+00:00 | 83 | passing_advanced | H006 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport (9).csv | 30775 | 2026-10-08T00:32:36.741633+00:00 | 78 | passing_advanced | H006 | 2021: season summary; week unknown | season=Season; team=Team; position=POS |
| passingAdvancedExport.csv | 20315 | 2026-10-07T20:51:02.580740+00:00 | 49 | passing_advanced | H006 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| passingBasicExport (1).csv | 16150 | 2026-10-07T23:27:19.729172+00:00 | 77 | passing_basic | H007 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| passingDepthExport (1).csv | 23264 | 2026-10-07T23:27:53.108389+00:00 | 77 | passing_depth | H008 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| passingDepthExport (2).csv | 23237 | 2026-10-08T00:32:55.057913+00:00 | 77 | passing_depth | H008 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| passingDepthExport (3).csv | 24025 | 2026-10-08T00:33:08.523402+00:00 | 80 | passing_depth | H008 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| passingDepthExport (4).csv | 24799 | 2026-10-08T00:33:24.618622+00:00 | 83 | passing_depth | H008 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| passingDepthExport (5).csv | 23347 | 2026-10-08T00:33:35.556505+00:00 | 78 | passing_depth | H008 | 2021: season summary; week unknown | season=Season; team=Team; position=POS |
| passingDepthExport.csv | 15316 | 2026-10-07T20:51:30.045473+00:00 | 49 | passing_depth | H008 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| qbCoverageMatchupExport.csv | 7927 | 2026-10-07T20:51:53.779723+00:00 | 28 | qb_coverage_matchup | H009 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingAdvancedExport (1).csv | 142713 | 2026-10-07T23:21:39.516534+00:00 | 376 | receiving_advanced | H010 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingAdvancedExport (2).csv | 1465368 | 2026-10-08T19:54:31.885758+00:00 | 4037 | receiving_advanced | H011 | 2025: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingAdvancedExport (3).csv | 1469523 | 2026-10-08T19:54:56.393591+00:00 | 4055 | receiving_advanced | H011 | 2024: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingAdvancedExport (4).csv | 1501663 | 2026-10-08T19:55:20.274737+00:00 | 4144 | receiving_advanced | H011 | 2023: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingAdvancedExport (5).csv | 1455948 | 2026-10-08T19:55:44.061897+00:00 | 4015 | receiving_advanced | H011 | 2022: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingAdvancedExport (6).csv | 1473487 | 2026-10-08T19:56:10.260149+00:00 | 4057 | receiving_advanced | H011 | 2021: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingAdvancedExport (7).csv | 356988 | 2026-10-08T20:09:08.709034+00:00 | 983 | receiving_advanced | H011 | 2026: 1,2,3,4 | season=Season; week=WEEK; team=Team; position=POS |
| receivingAdvancedExport.csv | 110341 | 2026-10-07T21:42:46.125694+00:00 | 298 | receiving_advanced | H010 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingBasicExport (1).csv | 52571 | 2026-10-08T00:10:27.251095+00:00 | 343 | receiving_basic | H012 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingBasicExport (2).csv | 50308 | 2026-10-08T00:10:53.428604+00:00 | 327 | receiving_basic | H012 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingBasicExport (3).csv | 53117 | 2026-10-08T00:11:21.211747+00:00 | 346 | receiving_basic | H012 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingBasicExport (4).csv | 54729 | 2026-10-08T00:11:53.282183+00:00 | 357 | receiving_basic | H012 | 2021: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingManVsZoneExport (1).csv | 65348 | 2026-10-07T23:22:16.570427+00:00 | 376 | receiving_man_zone | H013 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingManVsZoneExport (2).csv | 65470 | 2026-10-08T00:17:12.105740+00:00 | 381 | receiving_man_zone | H013 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingManVsZoneExport (3).csv | 63351 | 2026-10-08T00:17:30.181519+00:00 | 368 | receiving_man_zone | H013 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingManVsZoneExport (4).csv | 65271 | 2026-10-08T00:17:56.715490+00:00 | 378 | receiving_man_zone | H013 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingManVsZoneExport (5).csv | 59819 | 2026-10-08T00:18:12.382025+00:00 | 388 | receiving_man_zone | H013 | 2021: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingManVsZoneExport.csv | 49858 | 2026-10-07T20:50:03.455437+00:00 | 298 | receiving_man_zone | H013 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingRoutesRunExport (1).csv | 124541 | 2026-10-07T22:41:15.063524+00:00 | 519 | receiving_alignment | H014 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingRoutesRunExport (2).csv | 1333452 | 2026-10-08T10:46:55.775215+00:00 | 5527 | receiving_alignment | H015 | 2025: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingRoutesRunExport (3).csv | 1334798 | 2026-10-08T10:47:44.924865+00:00 | 5535 | receiving_alignment | H015 | 2024: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingRoutesRunExport (4).csv | 1364694 | 2026-10-08T10:48:34.257325+00:00 | 5656 | receiving_alignment | H015 | 2023: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingRoutesRunExport (5).csv | 1348278 | 2026-10-08T10:49:24.961867+00:00 | 5591 | receiving_alignment | H015 | 2022: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingRoutesRunExport (6).csv | 1354581 | 2026-10-08T10:50:16.148527+00:00 | 5611 | receiving_alignment | H015 | 2021: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| receivingRoutesRunExport (7).csv | 324381 | 2026-10-08T20:08:39.235343+00:00 | 1346 | receiving_alignment | H015 | 2026: 1,2,3,4 | season=Season; week=WEEK; team=Team; position=POS |
| receivingRoutesRunExport.csv | 96406 | 2026-10-07T21:43:28.330317+00:00 | 409 | receiving_alignment | H014 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByAlignmentExport (1).csv | 127490 | 2026-10-07T23:22:53.595170+00:00 | 519 | separation_alignment | H016 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByAlignmentExport (2).csv | 127930 | 2026-10-08T00:18:48.618016+00:00 | 522 | separation_alignment | H016 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByAlignmentExport (3).csv | 126382 | 2026-10-08T00:19:05.901185+00:00 | 513 | separation_alignment | H016 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByAlignmentExport (4).csv | 133356 | 2026-10-08T00:19:24.799525+00:00 | 540 | separation_alignment | H016 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByAlignmentExport.csv | 96875 | 2026-10-07T20:50:24.388625+00:00 | 408 | separation_alignment | H016 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByBreaksExport (1).csv | 133912 | 2026-10-07T23:23:28.939944+00:00 | 519 | separation_breaks | H017 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByBreaksExport (2).csv | 134337 | 2026-10-08T00:21:20.627993+00:00 | 522 | separation_breaks | H017 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByBreaksExport (3).csv | 132637 | 2026-10-08T00:21:41.381826+00:00 | 513 | separation_breaks | H017 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByBreaksExport (4).csv | 139439 | 2026-10-08T00:21:58.275486+00:00 | 540 | separation_breaks | H017 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByBreaksExport.csv | 101125 | 2026-10-07T20:50:41.616327+00:00 | 408 | separation_breaks | H017 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByCoverageExport (1).csv | 127847 | 2026-10-07T23:19:25.983776+00:00 | 519 | separation_coverage | H018 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByCoverageExport (2).csv | 128082 | 2026-10-08T00:20:06.032273+00:00 | 522 | separation_coverage | H018 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByCoverageExport (3).csv | 126634 | 2026-10-08T00:20:26.358598+00:00 | 513 | separation_coverage | H018 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByCoverageExport (4).csv | 133763 | 2026-10-08T00:20:45.944163+00:00 | 540 | separation_coverage | H018 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByCoverageExport.csv | 96869 | 2026-10-07T20:49:04.705193+00:00 | 408 | separation_coverage | H018 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByRoutesExport (1).csv | 280516 | 2026-10-07T23:20:47.017161+00:00 | 519 | separation_routes | H019 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByRoutesExport (2).csv | 280839 | 2026-10-08T00:22:40.122772+00:00 | 522 | separation_routes | H019 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByRoutesExport (3).csv | 277073 | 2026-10-08T00:23:05.900091+00:00 | 513 | separation_routes | H019 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByRoutesExport (4).csv | 290548 | 2026-10-08T00:23:54.890802+00:00 | 540 | separation_routes | H019 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| receivingSeparationByRoutesExport.csv | 208836 | 2026-10-07T20:49:35.246967+00:00 | 408 | separation_routes | H019 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| runPassReportExport (1).csv | 18671 | 2026-10-07T23:26:51.791857+00:00 | 32 | run_pass_report | H020 | 2025: season summary; week unknown | season=Season; team=Team Name |
| runPassReportExport (2).csv | 235706 | 2026-10-08T20:01:02.491907+00:00 | 544 | run_pass_report | H021 | 2025: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team Name |
| runPassReportExport (3).csv | 235809 | 2026-10-08T20:01:28.621181+00:00 | 544 | run_pass_report | H021 | 2023: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team Name |
| runPassReportExport (4).csv | 234870 | 2026-10-08T20:01:50.675702+00:00 | 542 | run_pass_report | H021 | 2022: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team Name |
| runPassReportExport (5).csv | 235982 | 2026-10-08T20:02:11.928466+00:00 | 544 | run_pass_report | H021 | 2021: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team Name |
| runPassReportExport (6).csv | 58227 | 2026-10-08T20:10:46.373638+00:00 | 128 | run_pass_report | H021 | 2026: 1,2,3,4 | season=Season; week=WEEK; team=Team Name |
| runPassReportExport.csv | 17822 | 2026-10-07T20:56:55.598149+00:00 | 32 | run_pass_report | H020 | 2026: season summary; week unknown | season=Season; team=Team Name |
| rushingAdvancedExport (1).csv | 38944 | 2026-10-07T23:30:16.520402+00:00 | 145 | rushing_advanced | H022 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| rushingAdvancedExport (2).csv | 340391 | 2026-10-08T19:58:10.652754+00:00 | 1333 | rushing_advanced | H023 | 2021: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingAdvancedExport (3).csv | 341149 | 2026-10-08T19:58:30.638930+00:00 | 1335 | rushing_advanced | H023 | 2022: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingAdvancedExport (4).csv | 333856 | 2026-10-08T19:58:51.306185+00:00 | 1302 | rushing_advanced | H023 | 2023: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingAdvancedExport (5).csv | 333856 | 2026-10-08T19:59:15.238359+00:00 | 1302 | rushing_advanced | H023 | 2023: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingAdvancedExport (6).csv | 335071 | 2026-10-08T19:59:34.435482+00:00 | 1308 | rushing_advanced | H023 | 2024: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingAdvancedExport (7).csv | 331720 | 2026-10-08T20:00:11.822848+00:00 | 1295 | rushing_advanced | H023 | 2025: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingAdvancedExport (8).csv | 78738 | 2026-10-08T20:10:04.861352+00:00 | 302 | rushing_advanced | H023 | 2026: 1,2,3,4 | season=Season; week=WEEK; team=Team; position=POS |
| rushingAdvancedExport.csv | 26208 | 2026-10-07T20:52:56.188325+00:00 | 97 | rushing_advanced | H022 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| rushingBasicExport (1).csv | 38669 | 2026-10-08T00:34:33.778278+00:00 | 138 | rushing_basic | H024 | 2024: season summary; week unknown | season=Season; team=Team; position=POS |
| rushingBasicExport (2).csv | 39167 | 2026-10-08T00:34:50.968397+00:00 | 140 | rushing_basic | H024 | 2023: season summary; week unknown | season=Season; team=Team; position=POS |
| rushingBasicExport (3).csv | 42807 | 2026-10-08T00:35:08.575424+00:00 | 154 | rushing_basic | H024 | 2022: season summary; week unknown | season=Season; team=Team; position=POS |
| rushingBasicExport (4).csv | 45350 | 2026-10-08T00:35:28.695292+00:00 | 164 | rushing_basic | H024 | 2021: season summary; week unknown | season=Season; team=Team; position=POS |
| rushingBellCowExport (1).csv | 26025 | 2026-10-07T23:31:05.886711+00:00 | 161 | bell_cow | H025 | 2025: season summary; week unknown | season=Season; team=Team; position=POS |
| rushingBellCowExport (2).csv | 287903 | 2026-10-08T10:44:09.190180+00:00 | 1777 | bell_cow | H026 | 2021: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingBellCowExport (3).csv | 292254 | 2026-10-08T10:44:32.699648+00:00 | 1806 | bell_cow | H026 | 2022: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingBellCowExport (4).csv | 275062 | 2026-10-08T10:44:59.019802+00:00 | 1696 | bell_cow | H026 | 2023: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingBellCowExport (5).csv | 276641 | 2026-10-08T10:45:18.797593+00:00 | 1710 | bell_cow | H026 | 2024: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingBellCowExport (6).csv | 284453 | 2026-10-08T10:45:35.887142+00:00 | 1761 | bell_cow | H026 | 2025: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | season=Season; week=WEEK; team=Team; position=POS |
| rushingBellCowExport (7).csv | 67791 | 2026-10-08T20:09:37.878134+00:00 | 418 | bell_cow | H026 | 2026: 1,2,3,4 | season=Season; week=WEEK; team=Team; position=POS |
| rushingBellCowExport.csv | 19966 | 2026-10-07T20:53:13.027925+00:00 | 126 | bell_cow | H025 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\bell-cow-report.csv | 13805 | 2026-10-14T01:00:37.562757+00:00 | 112 | bell_cow | H027 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\coach-records.csv | 9759 | 2026-10-13T20:05:07.793460+00:00 | 97 | coach_records | H028 | season/week unknown | team=TEAM |
| Week 6\coverage-matrix.csv | 5287 | 2026-10-13T20:04:56.972198+00:00 | 34 | coverage_matrix | H029 | 2026: season summary; week unknown | season=Season |
| Week 6\fantasy-points-allowed-qb (1).csv | 4299 | 2026-10-13T20:03:22.880744+00:00 | 34 | fantasy_points_allowed_qb | H030 | season/week unknown | position=POS |
| Week 6\fantasy-points-allowed-rb (1).csv | 3491 | 2026-10-13T20:03:26.523067+00:00 | 34 | fantasy_points_allowed_rb | H031 | season/week unknown | position=POS |
| Week 6\fantasy-points-allowed-te (1).csv | 3000 | 2026-10-13T20:03:41.588507+00:00 | 34 | fantasy_points_allowed_te | H032 | season/week unknown | position=POS |
| Week 6\fantasy-points-allowed-wr (3).csv | 3184 | 2026-10-13T20:03:29.932171+00:00 | 34 | fantasy_points_allowed_wr | H032 | season/week unknown | position=POS |
| Week 6\fantasy-points-allowed-wr (4).csv | 3142 | 2026-10-13T20:03:35.495492+00:00 | 34 | fantasy_points_allowed_wr | H032 | season/week unknown | position=POS |
| Week 6\fantasy-points-allowed-wr (5).csv | 3048 | 2026-10-13T20:03:38.093495+00:00 | 34 | fantasy_points_allowed_wr | H032 | season/week unknown | position=POS |
| Week 6\lineup-combos-ol.csv | 26865 | 2026-10-13T20:07:10.127504+00:00 | 196 | lineup_combos_ol | H033 | 2026: season summary; week unknown | season=Season; team=TEAM |
| Week 6\pace (1).csv | 7900 | 2026-10-13T20:07:23.901574+00:00 | 34 | team_pace | H034 | 2026: season summary; week unknown | season=Season |
| Week 6\passing-depth-of-target.csv | 11112 | 2026-10-13T20:05:55.881971+00:00 | 53 | passing_depth | H035 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\passing-situation (1).csv | 7442 | 2026-10-14T01:04:44.747659+00:00 | 35 | passing_situation | H036 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\passing-situation.csv | 10824 | 2026-10-14T01:03:08.369614+00:00 | 53 | passing_situation | H036 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\passing-stats.csv | 17984 | 2026-10-13T20:05:47.586061+00:00 | 53 | passing_advanced | H037 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\playcaller-stats (1).csv | 12886 | 2026-10-13T20:04:42.544585+00:00 | 34 | playcaller_stats | H038 | 2026: season summary; week unknown | season=Season; team=TEAM |
| Week 6\playcaller-stats (2).csv | 12905 | 2026-10-13T20:04:46.835589+00:00 | 34 | playcaller_stats | H038 | 2026: season summary; week unknown | season=Season; team=TEAM |
| Week 6\playcaller-stats.csv | 13214 | 2026-10-13T20:04:30.637357+00:00 | 35 | playcaller_stats | H038 | 2026: season summary; week unknown | season=Season; team=TEAM |
| Week 6\rb-wr-efficiency.csv | 72937 | 2026-10-14T01:01:02.002026+00:00 | 310 | efficiency | H039 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-alignment.csv | 43466 | 2026-10-14T01:01:28.182971+00:00 | 314 | receiving_alignment | H040 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-points-allowed (1).csv | 6933 | 2026-10-13T20:03:02.751302+00:00 | 34 | receiving_points_allowed | H041 | season/week unknown | team=Team |
| Week 6\receiving-separation-by-alignment (1).csv | 47931 | 2026-10-14T00:59:35.558630+00:00 | 314 | separation_alignment | H042 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-separation-by-alignment (2).csv | 47931 | 2026-10-14T01:02:04.145722+00:00 | 314 | separation_alignment | H042 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-separation-by-alignment.csv | 32023 | 2026-10-14T00:59:27.453135+00:00 | 228 | separation_alignment | H042 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-separation-by-coverage (1).csv | 56069 | 2026-10-14T01:03:20.924614+00:00 | 314 | separation_coverage | H043 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-separation-by-coverage (2).csv | 36386 | 2026-10-14T01:05:36.423604+00:00 | 228 | separation_coverage | H043 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-separation-by-coverage.csv | 56069 | 2026-10-14T01:02:48.802826+00:00 | 314 | separation_coverage | H043 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-separation-by-role.csv | 37641 | 2026-10-14T01:01:44.178703+00:00 | 195 | separation_breaks | H044 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-separation-by-routes.csv | 106999 | 2026-10-14T01:02:15.817296+00:00 | 314 | separation_routes | H045 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-situation.csv | 34348 | 2026-10-14T01:01:35.494821+00:00 | 314 | receiving_man_zone | H046 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\receiving-stats.csv | 76221 | 2026-10-14T01:00:21.292952+00:00 | 314 | receiving_advanced | H047 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\rushing-stats.csv | 20877 | 2026-10-14T01:00:43.555964+00:00 | 102 | rushing_advanced | H048 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |
| Week 6\team-defense (1).csv | 20988 | 2026-10-13T20:04:02.427189+00:00 | 32 | team_defense | H049 | 2026: season summary; week unknown | season=Season |
| Week 6\team-defense (2).csv | 23985 | 2026-10-13T20:04:07.984621+00:00 | 34 | team_defense | H049 | 2026: season summary; week unknown | season=Season |
| Week 6\team-offense.csv | 21065 | 2026-10-13T20:02:05.781852+00:00 | 32 | team_offense | H050 | 2026: season summary; week unknown | season=Season |
| wrCoverageMatchupExport.csv | 52224 | 2026-10-07T20:52:34.216638+00:00 | 195 | wr_coverage_matchup | H051 | 2026: season summary; week unknown | season=Season; team=Team; position=POS |

## Coverage grid

| Table | Season | Explicit weeks | Season-only/snapshot files | Missing regular-season weeks |
|---|---|---|---:|---|
| bell_cow | 2021 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| bell_cow | 2022 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| bell_cow | 2023 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| bell_cow | 2024 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| bell_cow | 2025 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 1 | none |
| bell_cow | 2026 | 1,2,3,4 | 2 | 5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| coverage_matrix | 2021 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| coverage_matrix | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| coverage_matrix | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| coverage_matrix | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| coverage_matrix | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| coverage_matrix | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| efficiency | 2021 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| efficiency | 2022 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| efficiency | 2023 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| efficiency | 2024 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| efficiency | 2025 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 1 | none |
| efficiency | 2026 | 1,2,3,4 | 2 | 5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| line_matchups | 2026 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| lineup_combos_ol | 2026 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| offense_snaps | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_advanced | 2021 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_advanced | 2022 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_advanced | 2023 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_advanced | 2024 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_advanced | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_advanced | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_basic | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_depth | 2021 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_depth | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_depth | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_depth | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_depth | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_depth | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| passing_situation | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| playcaller_stats | 2026 | none | 3 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| qb_coverage_matchup | 2026 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_advanced | 2021 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| receiving_advanced | 2022 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| receiving_advanced | 2023 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| receiving_advanced | 2024 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| receiving_advanced | 2025 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 1 | none |
| receiving_advanced | 2026 | 1,2,3,4 | 2 | 5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_alignment | 2021 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| receiving_alignment | 2022 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| receiving_alignment | 2023 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| receiving_alignment | 2024 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| receiving_alignment | 2025 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 1 | none |
| receiving_alignment | 2026 | 1,2,3,4 | 2 | 5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_basic | 2021 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_basic | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_basic | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_basic | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_man_zone | 2021 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_man_zone | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_man_zone | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_man_zone | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_man_zone | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| receiving_man_zone | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| run_pass_report | 2021 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| run_pass_report | 2022 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| run_pass_report | 2023 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| run_pass_report | 2025 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 1 | none |
| run_pass_report | 2026 | 1,2,3,4 | 1 | 5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| rushing_advanced | 2021 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| rushing_advanced | 2022 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| rushing_advanced | 2023 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| rushing_advanced | 2024 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 0 | none |
| rushing_advanced | 2025 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 | 1 | none |
| rushing_advanced | 2026 | 1,2,3,4 | 2 | 5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| rushing_basic | 2021 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| rushing_basic | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| rushing_basic | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| rushing_basic | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_alignment | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_alignment | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_alignment | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_alignment | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_alignment | 2026 | none | 4 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_breaks | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_breaks | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_breaks | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_breaks | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_breaks | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_coverage | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_coverage | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_coverage | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_coverage | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_coverage | 2026 | none | 4 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_routes | 2022 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_routes | 2023 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_routes | 2024 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_routes | 2025 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| separation_routes | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| team_defense | 2026 | none | 2 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| team_offense | 2026 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| team_pace | 2026 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |
| wr_coverage_matchup | 2026 | none | 1 | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18 |

## Gaps and interpretation

- Explicit weekly core history starts2021. Run/Pass Report2024 is missing; confirmation is pending, never substitute its2025 file.
- Core2026 explicit weekly exports cover1–4: weeks5–6 are missing as of completed week6; weeks7–18 are future/not yet due. A `Week 6` directory label does not make a season summary into a weekly file.
- Season-only/full-season or season-to-date exports are flagged. No end-of-season summary is used for predictions within that same season. Current snapshot availability is actual import time; historical weekly joins are event-time reconstructions, not proof of historical publication/version timing.
- Injury Database and Cornerbacks/Shadow tables are absent by recognizable filenames/headers; no data or IDs are invented. Team Pace, Playcaller Stats, Coverage Matrix and Separation are present as summaries/snapshots rather than complete explicit weekly series.
- Missing/ambiguous player/team mapping rows: 7953; malformed rows: 0; source files without explicit season: 8. Private identity details: `data/cache/fpds/imports/60db5c9ef7f17898ae0d/unmatched.json` (never commit or print).
- No GSIS/player/game IDs are guessed. Source-native IDs are kept distinct from GSIS. Team/season/week schedule joins require one exact regular-season game. Conflicting duplicates are excluded, not averaged.
- Weekly features use last8 known source games (rates averaged as rates; not pooled event rates); cumulative weekly snapshots use the latest value. Source-week w enters only later weeks and after the final scheduled kickoff in w plus24h. Explicit observation-aware mode also requires actual import before decision; it is unavailable retrospectively.
- Import command: `import_fpds.bat`. It copies, never moves; existing raw imports/manifests/caches are never overwritten. Exact repeat returns the saved import. Changing source content appends a new cache revision. All model-facing row data remain ignored/local.

## Header schemas (no data rows)

### H001

Group header: ["Team Details", "", "", "", "", "", "", "Man/Zone", "", "", "", "Middle of Field Look (Closed/Open)", "", "", "", "Coverages", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "G", "Season", "Location", "Team Name", "DB", "MAN %", "FP/DB", "ZONE %", "FP/DB", "1-HI/MOF C %", "FP/DB", "2-HI/MOF O %", "FP/DB", "COVER 0 %", "COVER 1 %", "COVER 2 %", "COVER 2 MAN %", "COVER 3 %", "COVER 4 %", "COVER 6 %"]

### H002

Group header: ["Player Details", "", "", "", "", "", "Rushing", "", "", "", "", "", "Receiving", "", "", "", "", "", "", "", "", "", "Total", "", "", "", "", "Efficiency", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "FPTS", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "ATT", "YDS", "TD", "YACO", "MTF", "EXP", "RTE", "TGT", "REC", "YDS", "TD", "AY", "YAC", "YACO", "MTF", "EXP", "TOUCH", "YFS", "TD", "MTF", "YACO", "YPC", "YACO/ATT", "MTF/ATT", "EXP RUN %", "YPRR", "YPT", "YAC/REC", "YACO/REC", "MTF/REC", "EXP REC %", "YFS/TOUCH", "MTF/TOUCH", "YACO/TOUCH", "EXP PLAY %", "RuYDS/G", "RecYDS/G", "YFS/G", "FP/G", "FP", "XFP", "XFP/G", "XFP %", "XTD", "XTD/G"]

### H003

Group header: ["Player Details", "", "", "", "", "", "", "", "", "Rushing", "", "", "", "", "", "Receiving", "", "", "", "", "", "", "", "", "", "Total", "", "", "", "", "Efficiency", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "FPTS", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "Season Type", "WEEK", "Opponent", "ATT", "YDS", "TD", "YACO", "MTF", "EXP", "RTE", "TGT", "REC", "YDS", "TD", "AY", "YAC", "YACO", "MTF", "EXP", "TOUCH", "YFS", "TD", "MTF", "YACO", "YPC", "YACO/ATT", "MTF/ATT", "EXP RUN %", "YPRR", "YPT", "YAC/REC", "YACO/REC", "MTF/REC", "EXP REC %", "YFS/TOUCH", "MTF/TOUCH", "YACO/TOUCH", "EXP PLAY %", "RuYDS/G", "RecYDS/G", "YFS/G", "FP/G", "FP", "XFP", "XFP/G", "XFP %", "XTD", "XTD/G"]

### H004

Group header: ["Team Details", "", "", "", "", "", "Offense Stats", "", "", "", "", "", "", "", "Defense Stats", "", "", "", "", ""]

Column header: ["Rank", "Name", "G", "Season", "Location", "Team Name", "RUSH GRADE", "PASS GRADE", "ADJ YBC/ATT", "PRESS %", "PrROE", "Team", "TM ATT", "YBCO", "Name", "ADJ YBC/ATT", "PRESS %", "PrROE", "ATT", "YBCO"]

### H005

Group header: ["Player Details", "", "", "", "", "", "Total", "", "", "Rushing", "", "", "Passing", "", "", "Inside 5", "", "", "Inside 10", "", "", "Inside 20", "", "", "FPTS", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "Snaps", "TM Snaps", "Snap %", "Snaps", "TM Snaps", "Snap %", "Snaps", "TM Snaps", "Snap %", "Snaps", "TM Snaps", "Snap %", "Snaps", "TM Snaps", "Snap %", "Snaps", "TM Snaps", "Snap %", "FP/G", "FP"]

### H006

Group header: ["Player Details", "", "", "", "", "", "Passing", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "Scrambles", "", "", "Passing Advanced", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "FPTS", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "DB", "ATT", "CMP", "CMP %", "YDS", "YDS/G", "YPA", "TD", "INT", "1D", "RATE", "SACK", "SACK %", "SK YDS", "ANY/A", "SCRM", "YDS", "TD", "CPOE", "aDOT", "AY", "Deep Throw %", "Deep Throw", "YAC %", "ADJ CMP %", "1Read %", "ACC %", "CATCH %", "OFF %", "HERO %", "TWT %", "EZATT", "DROP %", "DROP YDS", "TTT", "TTP", "TTSK", "TTSC", "QB SK", "QBP", "PRESS %", "PRESS SK %", "PrROE", "CHK %", "RPO %", "TA", "BAT", "SPK", "FP/DB", "FP/OPP", "FP/G", "FP", "OPP"]

### H007

Group header: ["Player Details", "", "", "", "", "", "Passing", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "Total Rushing", "", "", "Scrambles", "", "", "FPTS", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "DB", "ATT", "CMP", "CMP %", "YDS", "YDS/G", "YPA", "TD", "INT", "1D", "RATE", "SACK", "SACK %", "SK YDS", "ANY/A", "ATT", "YDS", "TD", "SCRM", "YDS", "TD", "FP/DB", "FP/OPP", "FP/G", "FP", "OPP"]

### H008

Group header: ["Player Details", "", "", "", "", "", "Overall", "", "", "", "", "", "", "", "", "Behind LOS", "", "", "", "", "", "", "", "", "0-9 Yards", "", "", "", "", "", "", "", "", "10-19 Yards", "", "", "", "", "", "", "", "", "20+ Yards", "", "", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "HERO", "TWT", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "HERO", "TWT", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "HERO", "TWT", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "HERO", "TWT", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "HERO", "TWT"]

### H009

Group header: ["Player Details", "", "", "", "", "", "", "Matchup", "", "", "", "", "Man", "", "", "", "Cover 2", "", "", "", "Cover 3", "", "", "", "Cover 4", "", "", "", "Cover 6", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "OPP", "DB", "DB/G", "FP/DB", "EXP FP/DB", "COV GRADE", "DEF MAN %", "DEF FP/DB", "QB MAN %", "QB FP/DB", "DEF COVER 2 %", "DEF FP/DB", "QB COVER 2 %", "QB FP/DB", "DEF COVER 3 %", "DEF FP/DB", "QB Cover 3 %", "QB FP/DB", "DEF COVER 4 %", "DEF FP/DB", "QB Cover 4 %", "QB FP/DB", "DEF COVER 6 %", "DEF FP/DB", "QB COVER 6 %", "QB FP/DB"]

### H010

Group header: ["Player Details", "", "", "", "", "", "Receiving", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "Advanced", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "FPTS", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "RTE", "RTE %", "aDOT", "AY", "AY Share", "TGT", "TGT/G", "TGT %", "TPRR", "REC", "CR %", "YDS", "RecYDS/G", "TM YDS %", "YPRR", "YPT", "YPR", "YAC", "YAC/REC", "YACO", "YACO/REC", "TD", "TM TD %", "i20 TGT", "EZTGT", "EZTD", "DP TGT", "1READ", "1READ %", "MTF", "MTF/REC", "1D", "1D/RR", "DRP", "DRP %", "CTGT", "CTGT %", "DESIGN", "DESIGN %", "CT", "CC", "CC %", "HERO", "RATE", "THREAT", "YPTOE", "WIDE RTE %", "SLOT RTE %", "INLINE RTE %", "BACK RTE %", "FP/RR", "FP/G", "FP", "XFP", "XFP/G", "XFP/RR", "RecXFP"]

### H011

Group header: ["Player Details", "", "", "", "", "", "", "", "", "Receiving", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "Advanced", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "FPTS", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "Season Type", "WEEK", "Opponent", "RTE", "RTE %", "aDOT", "AY", "AY Share", "TGT", "TGT/G", "TGT %", "TPRR", "REC", "CR %", "YDS", "RecYDS/G", "TM YDS %", "YPRR", "YPT", "YPR", "YAC", "YAC/REC", "YACO", "YACO/REC", "TD", "TM TD %", "i20 TGT", "EZTGT", "EZTD", "DP TGT", "1READ", "1READ %", "MTF", "MTF/REC", "1D", "1D/RR", "DRP", "DRP %", "CTGT", "CTGT %", "DESIGN", "DESIGN %", "CT", "CC", "CC %", "HERO", "RATE", "THREAT", "YPTOE", "WIDE RTE %", "SLOT RTE %", "INLINE RTE %", "BACK RTE %", "FP/RR", "FP/G", "FP", "XFP", "XFP/G", "XFP/RR", "RecXFP"]

### H012

Group header: ["Player Details", "", "", "", "", "", "Receiving", "", "", "", "", "", "", "", "", "", "", "", "", "", "FPTS", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "TGT", "TGT %", "REC", "YDS", "TM YDS %", "YPR", "YPT", "RecYDS/G", "CR %", "TD", "TM TD %", "i10", "i20 TGT", "FUM", "FP/G", "FP", "PPR", "NON-PPR"]

### H013

Group header: ["Player Details", "", "", "", "", "", "Overall", "", "", "", "Man", "", "", "", "Zone", "", "", "", "Single-High", "", "", "", "Two-High", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "RTE", "TPRR", "YPRR", "FP/RR", "RTE", "TPRR", "YPRR", "FP/RR", "RTE", "TPRR", "YPRR", "FP/RR", "RTE", "TPRR", "YPRR", "FP/RR", "RTE", "TPRR", "YPRR", "FP/RR"]

### H014

Group header: ["Player Details", "", "", "", "", "", "Overall", "", "", "", "", "Wide", "", "", "", "", "", "", "Slot", "", "", "", "", "", "", "Inline", "", "", "", "", "", "", "Backfield", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "RTE", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "WIDE RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "SLOT RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "INLINE RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "BACK RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR"]

### H015

Group header: ["Player Details", "", "", "", "", "", "", "", "", "Overall", "", "", "", "", "Wide", "", "", "", "", "", "", "Slot", "", "", "", "", "", "", "Inline", "", "", "", "", "", "", "Backfield", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "Season Type", "WEEK", "Opponent", "RTE", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "WIDE RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "SLOT RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "INLINE RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "BACK RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR"]

### H016

Group header: ["Player Details", "", "", "", "", "", "Overall", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "Wide", "", "", "", "", "Slot", "", "", "", "", "Inline", "", "", "", "", "Backfield", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "+1 Rate", "+2 Rate", "+3 Rate", "Neg Rate", "TGT", "REC", "YDS", "TD", "AY", "ADOR", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE"]

### H017

Group header: ["Player Details", "", "", "", "", "", "Overall", "", "", "", "", "Horizontally Breaking", "", "", "", "", "", "Vertically Breaking", "", "", "", "", "", "Static", "", "", "", "", "", "Shallow/Underneath", "", "", "", "", "", "Backfield", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE"]

### H018

Group header: ["Player Details", "", "", "", "", "", "Overall", "", "", "", "", "Man", "", "", "", "", "Zone", "", "", "", "", "Red Zone", "", "", "", "", "Cover 2", "", "", "Cover 3", "", "", "Cover 4", "", "", "Cover 6", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "WIN RATE", "RTE", "SEP SCORE", "WIN RATE", "RTE", "SEP SCORE", "WIN RATE", "RTE", "SEP SCORE", "WIN RATE"]

### H019

Group header: ["Player Details", "", "", "", "", "", "Overall", "", "", "", "", "", "Slant", "", "", "", "", "", "", "Out", "", "", "", "", "", "", "In/Dig", "", "", "", "", "", "", "Hitch", "", "", "", "", "", "", "Comeback", "", "", "", "", "", "", "Corner", "", "", "", "", "", "", "Post", "", "", "", "", "", "", "Go", "", "", "", "", "", "Crossers", "", "", "", "", "", "", "Screens", "", "", "", "", "", "", "Flat", "", "", "", "", "", "", "Backfield", "", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "TGT", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "ADOR", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE"]

### H020

Group header: ["Team Details", "", "", "", "", "", "Overall", "", "", "", "", "1st Half", "", "", "", "", "2nd Half", "", "", "", "", "Inside 10", "", "", "", "", "Inside 20", "", "", "", "", "Leading By 7+", "", "", "", "", "Neutral", "", "", "", "", "Trailing By 7+", "", "", "", "", "<5 Yds to Go", "", "", "", "", "5-9 Yds to Go", "", "", "", "", "10+ Yds to Go", "", "", "", "", "1st Down", "", "", "", "", "3rd Down", "", "", "", ""]

Column header: ["Rank", "Name", "G", "Season", "Location", "Team Name", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %"]

### H021

Group header: ["Team Details", "", "", "", "", "", "", "", "Overall", "", "", "", "", "1st Half", "", "", "", "", "2nd Half", "", "", "", "", "Inside 10", "", "", "", "", "Inside 20", "", "", "", "", "Leading By 7+", "", "", "", "", "Neutral", "", "", "", "", "Trailing By 7+", "", "", "", "", "<5 Yds to Go", "", "", "", "", "5-9 Yds to Go", "", "", "", "", "10+ Yds to Go", "", "", "", "", "1st Down", "", "", "", "", "3rd Down", "", "", "", ""]

Column header: ["Rank", "Name", "G", "Season", "Season Type", "WEEK", "Location", "Team Name", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %", "SNAPS", "PASS", "RUSH", "PASS %", "RUSH %"]

### H022

Group header: ["Player Details", "", "", "", "", "", "Rushing", "", "", "", "", "", "", "Advanced", "", "", "", "", "", "", "", "", "", "", "", "", "Zone Concept", "", "", "", "", "", "Man/Gap Concept", "", "", "", "", "", "FPTS", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "ATT", "YDS", "RuYDS/G", "YPC", "TD", "FUM", "1D", "EXP RUN %", "EXP YDS", "EXP YDS %", "i5 %", "TD RATE", "Success %", "STUFF %", "MTF", "MTF/ATT", "YACO", "YACO/ATT", "YACO %", "YBCO/ATT", "ATT", "ATT %", "YDS", "TD", "YPC", "Success %", "ATT", "ATT %", "YDS", "TD", "YPC", "Success %", "FP/G", "FP", "XFP", "XFP/G"]

### H023

Group header: ["Player Details", "", "", "", "", "", "", "", "", "Rushing", "", "", "", "", "", "", "Advanced", "", "", "", "", "", "", "", "", "", "", "", "", "Zone Concept", "", "", "", "", "", "Man/Gap Concept", "", "", "", "", "", "FPTS", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "Season Type", "WEEK", "Opponent", "ATT", "YDS", "RuYDS/G", "YPC", "TD", "FUM", "1D", "EXP RUN %", "EXP YDS", "EXP YDS %", "i5 %", "TD RATE", "Success %", "STUFF %", "MTF", "MTF/ATT", "YACO", "YACO/ATT", "YACO %", "YBCO/ATT", "ATT", "ATT %", "YDS", "TD", "YPC", "Success %", "ATT", "ATT %", "YDS", "TD", "YPC", "Success %", "FP/G", "FP", "XFP", "XFP/G"]

### H024

Group header: ["Player Details", "", "", "", "", "", "Rushing", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "Receiving", "", "", "", "", "", "", "", "", "", "", "", "", "", "FPTS", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "ATT", "YDS", "RuYDS/G", "YPC", "TD", "FUM", "SCRM", "YDS", "TD", "1+ %", "3+ %", "5+ %", "10+ %", "15+ %", "20+ %", "30+ %", "i5", "i5 %", "i10", "i10 %", "i20", "i20 %", "TGT", "TGT %", "REC", "YDS", "TM YDS %", "YPR", "YPT", "RecYDS/G", "CR %", "TD", "TM TD %", "i10", "i20 TGT", "FUM", "WO", "WO/G", "FP/G", "FP"]

### H025

Group header: ["Player Details", "", "", "", "", "", "Snaps", "", "", "Rushing", "", "", "Receiving", "", "", "", "", "", "FPTS", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "Snaps", "TM Snaps", "Snap %", "ATT", "TM ATT", "ATT %", "RTE", "DB", "RTE %", "TGT", "TM TGT", "TGT %", "XFP", "TM XFP", "XFP %", "XFP/G", "FP/G", "FP"]

### H026

Group header: ["Player Details", "", "", "", "", "", "", "", "", "Snaps", "", "", "Rushing", "", "", "Receiving", "", "", "", "", "", "FPTS", "", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "Season Type", "WEEK", "Opponent", "Snaps", "TM Snaps", "Snap %", "ATT", "TM ATT", "ATT %", "RTE", "DB", "RTE %", "TGT", "TM TGT", "TGT %", "XFP", "TM XFP", "XFP %", "XFP/G", "FP/G", "FP"]

### H027

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Snaps", "Snaps", "Snaps", "Rushing", "Rushing", "Rushing", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "FP", "FP", "FP", "FP", "FP", "FP", "FP", "FP", "FP"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "Snaps", "TM Snaps", "Snap %", "ATT", "TM ATT", "ATT %", "RTE", "TM DB", "RTE %", "TGT", "TM TGT", "TGT %", "FP", "XFP", "FP/G", "XFP/G", "DIFF", "TM XFP", "XFP %", "TM RB XFP", "BACKFIELD XFP %"]

### H028

Group header: ["Coach", "Coach", "Coach", "Coach", "Coach", "Record", "Record", "Record", "Record", "Points", "Points", "Points", "Points", "Points", "Plays", "Plays", "Plays", "Plays", "Plays", "Plays", "Plays", "Plays"]

Column header: ["RANK", "COACH", "ROLE", "TEAM", "G", "W", "L", "T", "WIN %", "PF", "PA", "DIFF", "PF/G", "PA/G", "PLAYS", "PLAYS/G", "YDS", "Y/P", "EPA/P", "SUCC %", "PASS %", "RUN %"]

### H029

Group header: ["", "Team Details", "Team Details", "Team Details", "Team Details", "Man/Zone", "Man/Zone", "Man/Zone", "Man/Zone", "Middle of Field Look (Closed/Open)", "Middle of Field Look (Closed/Open)", "Middle of Field Look (Closed/Open)", "Middle of Field Look (Closed/Open)", "Disguised Coverage", "Disguised Coverage", "Disguised Coverage", "Coverages", "Coverages", "Coverages", "Coverages", "Coverages", "Coverages", "Coverages", "Personnel & Press", "Personnel & Press", "Personnel & Press", "Personnel & Press", "Personnel & Press"]

Column header: ["Season", "Rank", "Name", "G", "DB", "MAN %", "FP/DB", "ZONE %", "FP/DB", "1-HI/MOF C %", "FP/DB", "2-HI/MOF O %", "FP/DB", "DISGUISE %", "TO 1-HI %", "TO 2-HI %", "COVER 0 %", "COVER 1 %", "COVER 2 %", "COVER 2 MAN %", "COVER 3 %", "COVER 4 %", "COVER 6 %", "BASE %", "NICKEL %", "DIME %", "PRESS % (ANY)", "PRESS % (TGT)"]

### H030

Group header: ["TEAM DETAILS", "TEAM DETAILS", "TEAM DETAILS", "TEAM DETAILS", "PASSING", "PASSING", "PASSING", "PASSING", "PASSING", "PASSING", "PASSING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "FP", "FP", "FP", "FP"]

Column header: ["Rank", "Name", "POS", "G", "DB", "ATT", "CMP", "YDS", "TD", "RATE", "PASS FP", "ATT", "DES ATT", "SCRM", "YDS", "DES YDS", "SCRM YDS", "YPC", "DES YPC", "SCRM YPC", "TD", "DES TD", "SCRM TD", "DES FP", "SCRM FP", "FP", "FP/G", "FP/DB", "FP/OPP"]

### H031

Group header: ["TEAM DETAILS", "TEAM DETAILS", "TEAM DETAILS", "TEAM DETAILS", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "FP", "FP", "FP", "FP"]

Column header: ["Rank", "Name", "POS", "G", "ATT", "YDS", "YPC", "TD", "Ru FPG", "TGT", "REC", "YDS", "YPT", "TD", "Re FPG", "TMS %", "YMS %", "FP SH %", "FP", "FP/G", "FP/OPP", "FP/TCH"]

### H032

Group header: ["TEAM DETAILS", "TEAM DETAILS", "TEAM DETAILS", "TEAM DETAILS", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RECEIVING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "RUSHING", "FP", "FP", "FP"]

Column header: ["Rank", "Name", "POS", "G", "TGT", "REC", "YDS", "YPT", "TD", "Re FPG", "TMS %", "YMS %", "FP SH %", "ATT", "YDS", "YPC", "TD", "Ru FPG", "FP", "FP/G", "FP/OPP"]

### H033

Group header: ["", "Unit Details", "Unit Details", "Unit Details", "Unit Details", "Unit Details", "Unit Details", "Unit Details", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Pass Protection", "Pass Protection", "Run Game", "Run Game"]

Column header: ["Season", "Rank", "Unit", "TEAM", "MEN", "G", "SNAPS", "SNAP %", "PASS %", "EPA/P", "EPA/DB", "EPA/DR", "SUCC %", "EXP %", "PRES %", "SACK %", "YPC", "YBC/A"]

### H034

Group header: ["", "Team Details", "Team Details", "Team Details", "Volume & Pace", "Volume & Pace", "Volume & Pace", "Volume & Pace", "Situational Pace", "Situational Pace", "Situational Pace", "Situational Pace", "Situational Pace", "Situational Pace", "Pass Tendency", "Pass Tendency"]

Column header: ["Season", "Rank", "Name", "G", "PLAYS", "PACE", "PL/DR", "SEC/DR", "PACE LEAD", "PACE TRAIL", "PACE NEU", "PACE DIFF", "PACE H1", "PACE H2", "PASS %", "PROE"]

### H035

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Behind LOS", "Behind LOS", "Behind LOS", "Behind LOS", "Behind LOS", "Behind LOS", "Behind LOS", "Behind LOS", "Behind LOS", "Behind LOS", "0-9 Yards", "0-9 Yards", "0-9 Yards", "0-9 Yards", "0-9 Yards", "0-9 Yards", "0-9 Yards", "0-9 Yards", "0-9 Yards", "0-9 Yards", "10-19 Yards", "10-19 Yards", "10-19 Yards", "10-19 Yards", "10-19 Yards", "10-19 Yards", "10-19 Yards", "10-19 Yards", "10-19 Yards", "10-19 Yards", "20+ Yards", "20+ Yards", "20+ Yards", "20+ Yards", "20+ Yards", "20+ Yards", "20+ Yards", "20+ Yards", "20+ Yards", "20+ Yards"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "ACC %", "HERO", "TWT", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "ACC %", "HERO", "TWT", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "ACC %", "HERO", "TWT", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "ACC %", "HERO", "TWT", "ATT", "CMP", "YDS", "TD", "INT", "RATE", "CATCH %", "ACC %", "HERO", "TWT"]

### H036

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Man", "Man", "Man", "Man", "Man", "Man", "Man", "Man", "Zone", "Zone", "Zone", "Zone", "Zone", "Zone", "Zone", "Zone", "Single-High", "Single-High", "Single-High", "Single-High", "Single-High", "Single-High", "Single-High", "Single-High", "Two-High", "Two-High", "Two-High", "Two-High", "Two-High", "Two-High", "Two-High", "Two-High"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "DB", "CMP %", "YPA", "TD", "INT", "RATE", "EPA/DB", "FP/DB", "DB", "CMP %", "YPA", "TD", "INT", "RATE", "EPA/DB", "FP/DB", "DB", "CMP %", "YPA", "TD", "INT", "RATE", "EPA/DB", "FP/DB", "DB", "CMP %", "YPA", "TD", "INT", "RATE", "EPA/DB", "FP/DB", "DB", "CMP %", "YPA", "TD", "INT", "RATE", "EPA/DB", "FP/DB"]

### H037

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Passing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "FP", "FP", "FP", "FP", "FP", "FP", "FP", "FP", "FP"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "SNAP %", "DB", "ATT", "CMP", "CMP %", "YDS", "YPA", "TD", "XTD", "INT", "1D", "RATE", "ANY/A", "SUCC %", "SACK", "SACK %", "SK YDS", "SCR", "SCR YDS", "SCR TD", "ATT", "YDS", "TD", "CPOE", "ADJ CMP %", "ADOT", "AYDS", "DEEP %", "EZATT", "YAC %", "1ST RD %", "ACC %", "CATCH %", "OFF TGT %", "HERO %", "TWT %", "DROP %", "DROP YDS", "TTT", "TTP", "TTSK", "TTSC", "QBSK", "PRESS %", "QK PRES %", "P2S %", "PRES O/E", "RB TGT %", "WR TGT %", "TE TGT %", "WIDE TGT %", "SLOT TGT %", "INLINE TGT %", "BACK TGT %", "CKD %", "RPO %", "TA", "BPA", "SPK", "EPA", "EPA/DB", "EPA/P", "FP/DB", "FP/OPP", "FP", "XFP", "FP/G", "XFP/G", "DIFF", "PASS FP", "RUSH FP"]

### H038

Group header: ["", "Coach", "Coach", "Coach", "Coach", "Coach", "Volume", "Volume", "Volume", "Volume", "Volume", "Volume", "Volume", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Scheme Tendencies", "Fantasy", "Fantasy", "Fantasy", "Fantasy", "Fantasy", "Fantasy", "Fantasy", "Fantasy", "Target Share", "Target Share", "Target Share", "Target Share", "Target Share", "Target Share", "Target Share", "Route Running", "Route Running", "Route Running", "Route Running", "Route Running", "Route Running", "Route Running", "Route Running"]

Column header: ["Season", "RANK", "Coach", "Role(s)", "TEAM", "G", "PLAYS", "PLAYS/G", "PACE", "DB", "RUNS", "PASS %", "RUN %", "FP/DB", "EPA/PLAY", "EPA/DB", "EPA/R", "ANY/A", "YPC", "PASS Y/G", "RUSH Y/G", "Y/P", "SUCC %", "PASS SUCC %", "RUSH SUCC %", "BLITZ EPA/DB", "4TH GO %", "RZ PASS %", "ZONE RUN %", "PROE", "ED PASS %", "2L RUN %", "BASE PASS %", "8+ BOX RUN %", "PA %", "UC %", "MOT %", "DS MOT %", "NH %", "RPO %", "11P %", "12P %", "13P %", "21P %", "OZ %", "IZ %", "GAP %", "SNEAK %", "QB FP/G", "RB FP/G", "WR FP/G", "TE FP/G", "QB XFP/G", "RB XFP/G", "WR XFP/G", "TE XFP/G", "WR TGT %", "RB TGT %", "TE TGT %", "WIDE TGT %", "SLOT TGT %", "INLINE TGT %", "BACK TGT %", "RR/DB", "WR RR/DB", "TE RR/DB", "RB RR/DB", "WIDE RR/DB", "SLOT RR/DB", "INLINE RR/DB", "BACK RR/DB"]

### H039

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Total", "Total", "Total", "Total", "Total", "Total", "Total", "Total", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "Efficiency", "FP", "FP", "FP", "FP", "FP", "FP"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "SNAPS", "Snap %", "TOUCH", "YFS", "TD", "XTD", "MTF", "YACO", "ATT", "ATT %", "YDS", "TD", "XTD", "YACO", "MTF", "EXP", "RTE", "RTE %", "TGT", "TGT %", "REC", "YDS", "TD", "XTD", "AY", "YAC", "YACO", "MTF", "EXP", "YPC", "YACO/ATT", "MTF/ATT", "EXP RUN %", "RUN SUCC %", "YPRR", "YPT", "YAC/REC", "YACO/REC", "MTF/REC", "EXP REC %", "REC SUCC %", "YFS/TOUCH", "MTF/TOUCH", "YACO/TOUCH", "EXP PLAY %", "RuYDS/G", "RecYDS/G", "YFS/G", "FP/SN", "EPA/SN", "EPA/RU", "EPA/TGT", "EPA/RTE", "FP", "XFP", "FP/G", "XFP/G", "DIFF", "XFP %"]

### H040

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Overall", "Overall", "Overall", "Overall", "Overall", "Wide", "Wide", "Wide", "Wide", "Wide", "Wide", "Wide", "Slot", "Slot", "Slot", "Slot", "Slot", "Slot", "Slot", "Inline", "Inline", "Inline", "Inline", "Inline", "Inline", "Inline", "Backfield", "Backfield", "Backfield", "Backfield", "Backfield", "Backfield", "Backfield"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "RTE", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "WIDE RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "SLOT RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "INLINE RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR", "RTE", "BACK RTE %", "TM RTE %", "TGT", "TPRR", "RTE %", "YPRR"]

### H041

Group header: ["Team", "Team", "Team", "OUTER", "OUTER", "OUTER", "OUTER", "OUTER", "OUTER", "OUTER", "OUTER", "OUTER", "OUTER", "OUTER", "SLOT", "SLOT", "SLOT", "SLOT", "SLOT", "SLOT", "SLOT", "SLOT", "SLOT", "SLOT", "SLOT", "SLOT", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE LWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR", "OUTSIDE RWR"]

Column header: ["Rank", "Team", "G", "TGT", "REC", "YDS", "TD", "INT", "RATE", "YPG", "FP", "FPG", "FP RK", "FP/T", "TGT", "REC", "YDS", "TD", "INT", "RATE", "YPG", "FP", "FPG", "SLOT %", "FP RK", "FP/T", "TGT", "REC", "YDS", "TD", "INT", "RATE", "YPG", "FP", "FPG", "FP RK", "FP/T", "TGT", "REC", "YDS", "TD", "INT", "RATE", "YPG", "FP", "FPG", "FP RK", "FP/T"]

### H042

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Wide", "Wide", "Wide", "Wide", "Wide", "Slot", "Slot", "Slot", "Slot", "Slot", "Inline", "Inline", "Inline", "Inline", "Inline", "Backfield", "Backfield", "Backfield", "Backfield", "Backfield"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "SEP MS", "ADOR", "TGT %", "+1 Rate", "+2 Rate", "+3 Rate", "Neg Rate", "TGT", "REC", "YDS", "TD", "AY", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE"]

### H043

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Man", "Man", "Man", "Man", "Man", "Zone", "Zone", "Zone", "Zone", "Zone", "Red Zone", "Red Zone", "Red Zone", "Red Zone", "Red Zone", "Cover 2", "Cover 2", "Cover 2", "Cover 3", "Cover 3", "Cover 3", "Cover 4", "Cover 4", "Cover 4", "Cover 6", "Cover 6", "Cover 6"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "SEP MS", "ADOR", "TGT %", "+1 Rate", "+2 Rate", "+3 Rate", "Neg Rate", "TGT", "REC", "YDS", "TD", "AY", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "SEP SCORE", "WIN RATE", "RTE", "SEP SCORE", "WIN RATE", "RTE", "SEP SCORE", "WIN RATE", "RTE", "SEP SCORE", "WIN RATE"]

### H044

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "X (Wide, On the Line)", "X (Wide, On the Line)", "X (Wide, On the Line)", "X (Wide, On the Line)", "X (Wide, On the Line)", "X (Wide, On the Line)", "Z (Wide, Off the Line)", "Z (Wide, Off the Line)", "Z (Wide, Off the Line)", "Z (Wide, Off the Line)", "Z (Wide, Off the Line)", "Z (Wide, Off the Line)", "F (Slot)", "F (Slot)", "F (Slot)", "F (Slot)", "F (Slot)", "F (Slot)", "Condensed (Wide, Reduced Split)", "Condensed (Wide, Reduced Split)", "Condensed (Wide, Reduced Split)", "Condensed (Wide, Reduced Split)", "Condensed (Wide, Reduced Split)", "Condensed (Wide, Reduced Split)"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "SEP MS", "ADOR", "TGT %", "+1 Rate", "+2 Rate", "+3 Rate", "Neg Rate", "TGT", "REC", "YDS", "TD", "AY", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "WIN RATE"]

### H045

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Overall", "Slant", "Slant", "Slant", "Slant", "Slant", "Slant", "Slant", "Out", "Out", "Out", "Out", "Out", "Out", "Out", "In/Dig", "In/Dig", "In/Dig", "In/Dig", "In/Dig", "In/Dig", "In/Dig", "Hitch", "Hitch", "Hitch", "Hitch", "Hitch", "Hitch", "Hitch", "Comeback", "Comeback", "Comeback", "Comeback", "Comeback", "Comeback", "Comeback", "Corner", "Corner", "Corner", "Corner", "Corner", "Corner", "Corner", "Post", "Post", "Post", "Post", "Post", "Post", "Post", "Go", "Go", "Go", "Go", "Go", "Go", "Go", "Crossers", "Crossers", "Crossers", "Crossers", "Crossers", "Crossers", "Crossers", "Screens", "Screens", "Screens", "Screens", "Screens", "Screens", "Screens", "Flat", "Flat", "Flat", "Flat", "Flat", "Flat", "Flat", "Backfield", "Backfield", "Backfield", "Backfield", "Backfield", "Backfield", "Backfield"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "RTE", "SEP SCORE", "YPRR", "TPRR", "WIN RATE", "SEP MS", "ADOR", "TGT %", "+1 Rate", "+2 Rate", "+3 Rate", "Neg Rate", "TGT", "REC", "YDS", "TD", "AY", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE", "RTE", "RTE %", "SEP SCORE", "YPRR", "TPRR", "ADOR", "WIN RATE"]

### H046

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Overall", "Overall", "Overall", "Overall", "Man", "Man", "Man", "Man", "Zone", "Zone", "Zone", "Zone", "Single-High", "Single-High", "Single-High", "Single-High", "Two-High", "Two-High", "Two-High", "Two-High"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "RTE", "TPRR", "YPRR", "FP/RR", "RTE", "TPRR", "YPRR", "FP/RR", "RTE", "TPRR", "YPRR", "FP/RR", "RTE", "TPRR", "YPRR", "FP/RR", "RTE", "TPRR", "YPRR", "FP/RR"]

### H047

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Receiving", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Alignment", "Alignment", "Alignment", "Alignment", "FP", "FP", "FP", "FP", "FP", "FP", "FP", "FP"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "SNAP %", "RTE", "RTE %", "TGT", "TGT %", "YPRR", "TPRR", "aDOT", "AY", "AY Share", "YDS", "TM YDS %", "YPT", "YPR", "REC", "CR %", "YAC", "YAC/REC", "YACO", "YACO/REC", "TD", "XTD", "TM TD %", "i20 TGT", "EZTGT", "EZTD", "1D", "1D/RR", "RATE", "1READ", "1READ %", "DESIGN", "DESIGN %", "CTGT", "CTGT %", "DEEP", "EXP %", "DRP", "DRP %", "CT", "CC", "CC %", "HERO", "MTF", "MTF/REC", "THREAT %", "YPTOE", "EPA/TGT", "WIDE RTE %", "SLOT RTE %", "INLINE RTE %", "BACK RTE %", "FP", "XFP", "FP/G", "XFP/G", "DIFF", "FP/RR", "XFP/RR", "RecXFP"]

### H048

Group header: ["", "Player Details", "Player Details", "Player Details", "Player Details", "Player Details", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Rushing", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Advanced", "Zone Concept", "Zone Concept", "Zone Concept", "Zone Concept", "Zone Concept", "Zone Concept", "Man/Gap Concept", "Man/Gap Concept", "Man/Gap Concept", "Man/Gap Concept", "Man/Gap Concept", "Man/Gap Concept", "FP", "FP", "FP", "FP", "FP"]

Column header: ["Season", "Rank", "Name", "Team", "POS", "G", "SNAP %", "ATT", "DCS %", "SNEAK %", "YDS", "YPC", "TD", "XTD", "FUM", "1D", "EXP RUN %", "EXP YDS", "EXP YDS %", "i5 %", "TD RATE", "SUCC %", "STUFF %", "RYOE", "YBC/ATT", "HIT %", "YACO/ATT", "YACO %", "MTF", "MTF/A", "EPA/A", "EPA", "ZONE ATT", "ZONE ATT %", "ZONE YDS", "ZONE TD", "ZONE YPC", "ZONE SUCC %", "MAN ATT", "MAN ATT %", "MAN YDS", "MAN TD", "MAN YPC", "MAN SUCC %", "FP", "XFP", "FP/G", "XFP/G", "DIFF"]

### H049

Group header: ["", "Team Details", "Team Details", "Team Details", "Record", "Record", "Record", "Record", "Record", "Record", "Volume & Pace", "Volume & Pace", "Volume & Pace", "Volume & Pace", "Volume & Pace", "Drives", "Drives", "Drives", "Drives", "Drives", "Drives", "EPA", "EPA", "EPA", "EPA", "EPA", "Success", "Success", "Success", "Explosive", "Explosive", "Explosive", "Turnovers", "Turnovers", "Coverage", "Coverage", "Coverage", "Coverage", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Penalties", "Penalties", "Penalties", "Fantasy", "Fantasy", "Fantasy", "Fantasy"]

Column header: ["Season", "Rank", "Name", "G", "W-L-T", "WIN %", "PF", "PA", "DIFF", "TO +/-", "PLAYS", "Y/P", "TOP", "PACE", "AVG START", "DR", "PTS/DR", "SCR %", "TD %", "FG %", "PUNT %", "EPA", "EPA/P", "EPA/DR", "EPA/DB", "EPA/RU", "SUCC %", "PASS SUCC %", "RUSH SUCC %", "EXP %", "PASS EXP %", "RUSH EXP %", "TO", "TO/DR %", "MAN %", "ZONE %", "1-HIGH %", "2-HIGH %", "BASE %", "SUB %", "PRESS %", "SACKS", "SACK %", "BLITZ %", "BOX", "PASS %", "PROE", "PEN", "PEN YDS", "PEN EPA", "QB FPG", "RB FPG", "WR FPG", "TE FPG"]

### H050

Group header: ["", "Team Details", "Team Details", "Team Details", "Record", "Record", "Record", "Record", "Record", "Record", "Volume & Pace", "Volume & Pace", "Volume & Pace", "Volume & Pace", "Volume & Pace", "Drives", "Drives", "Drives", "Drives", "Drives", "Drives", "EPA", "EPA", "EPA", "EPA", "EPA", "Success", "Success", "Success", "Explosive", "Explosive", "Explosive", "Turnovers", "Turnovers", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Tendencies", "Penalties", "Penalties", "Penalties", "Fantasy", "Fantasy", "Fantasy", "Fantasy"]

Column header: ["Season", "Rank", "Name", "G", "W-L-T", "WIN %", "PF", "PA", "DIFF", "TO +/-", "PLAYS", "Y/P", "TOP", "PACE", "AVG START", "DR", "PTS/DR", "SCR %", "TD %", "FG %", "PUNT %", "EPA", "EPA/P", "EPA/DR", "EPA/DB", "EPA/RU", "SUCC %", "PASS SUCC %", "RUSH SUCC %", "EXP %", "PASS EXP %", "RUSH EXP %", "TO", "TO/DR %", "PASS %", "PROE", "MOTION %", "PA %", "PRESS %", "SACKS", "SACK %", "11P %", "11P EPA/P", "12P %", "12P EPA/P", "21P %", "21P EPA/P", "PEN", "PEN YDS", "PEN EPA", "QB FPG", "RB FPG", "WR FPG", "TE FPG"]

### H051

Group header: ["Player Details", "", "", "", "", "", "", "Matchup", "", "", "", "", "", "Man", "", "", "", "", "Cover 2", "", "", "", "", "Cover 3", "", "", "", "", "Cover 4", "", "", "", "", "Cover 6", "", "", "", ""]

Column header: ["Rank", "Name", "Team", "POS", "G", "Season", "OPP", "RTE", "RTE/G", "FP/RR", "EXP FP/RTE", "COV GRADE", "YPRR", "DEF MAN %", "DEF FP/DB", "FP/RTE", "RTE %", "YPRR", "DEF COVER 2 %", "DEF FP/DB", "FP/RTE", "RTE %", "YPRR", "DEF COVER 3 %", "DEF FP/DB", "FP/RTE", "RTE %", "YPRR", "DEF COVER 4 %", "DEF FP/DB", "FP/RTE", "RTE %", "YPRR", "DEF COVER 6 %", "DEF FP/DB", "FP/RTE", "RTE %", "YPRR"]
