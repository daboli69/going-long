# FPDS data dictionary — Amendment 6

Metadata only. No subscription rows, player labels or values are published here.

All numeric game statistics are outcome-contaminated in their source week. They are usable only after a strict availability lag. Unknown/DFS/fantasy/projection fields are excluded. Header definitions below are guesses, not verified vendor definitions.

Historical exports downloaded in2026 are reconstructed event-time data. They cannot establish what a bettor could actually have observed in an earlier season. First imports cannot estimate earlier vendor revisions.

|Table|Rows|Usable entity-weeks|Unmatched rows|Ambiguous rows|Export-cap flag|2026 weeks|
|---|---:|---:|---:|---:|---|---|
|bell_cow_report|6300|0|6300|0|True|1,2,3,4,5,6|
|coach_records|8570|0|0|8570|False|1,2,3,4,5,6|
|cornerbacks|4700|0|4700|0|True|1,2,3,4,5,6|
|coverage_matrix|2904|2904|0|0|False|1,2,3,4,5,6|
|fantasy_points_allowed_qb|2904|2904|0|0|False|1,2,3,4,5,6|
|fantasy_points_allowed_rb|2904|2904|0|0|False|1,2,3,4,5,6|
|fantasy_points_allowed_te|2888|2888|0|0|False|1,2,3,4,5,6|
|fantasy_points_allowed_wr|2904|2904|0|0|False|1,2,3,4,5,6|
|injury_reports|8342|0|8342|0|False|1,2,3,4,5,6|
|lineup_combos_db|10600|50|0|10550|True|1,2,3,4,5,6|
|lineup_combos_front|9700|213|0|9487|True|1,2,3,4,5,6|
|lineup_combos_ol|6759|780|0|5979|False|1,2,3,4,5,6|
|lineup_combos_rb|11867|5|0|11862|False|1,2,3,4,5,6|
|lineup_combos_skill|10500|147|0|10353|True|1,2,3,4,5,6|
|lineup_combos_te|13600|16|0|13584|True|1,2,3,4,5,6|
|lineup_combos_wr|12600|22|0|12578|True|1,2,3,4,5,6|
|pace|2904|2904|0|0|False|1,2,3,4,5,6|
|passing_basic|1200|0|1200|0|True|1,2,3,4,5,6|
|passing_depth_of_target|1800|0|1800|0|True|1,2,3,4,5,6|
|passing_situation|1000|0|1000|0|True|1,2,3,4,5,6|
|passing_stats|1200|0|1200|0|True|1,2,3,4,5,6|
|playcaller_stats|2600|2570|0|30|True|1,2,3,4,5,6|
|rb_wr_efficiency|3200|0|3200|0|True|1,2,3,4,5,6|
|receiving_alignment|3200|0|3200|0|True|1,2,3,4,5,6|
|receiving_basic|1500|0|1500|0|True|1,2,3,4,5,6|
|receiving_separation_by_alignment|2900|0|2900|0|True|1,2,3,4,5,6|
|receiving_separation_by_breaks|2500|0|2500|0|True|1,2,3,4,5,6|
|receiving_separation_by_coverage|2600|0|2600|0|True|1,2,3,4,5,6|
|receiving_separation_by_role|2900|0|2900|0|True|1,2,3,4,5,6|
|receiving_separation_by_routes|1600|0|1600|0|True|1,2,3,4,5,6|
|receiving_situation|1700|0|1700|0|True|1,2,3,4,5,6|
|receiving_stats|1500|0|1500|0|True|1,2,3,4,5,6|
|rushing_basic|1600|0|1600|0|True|1,2,3,4,5,6|
|rushing_stats|1600|0|1600|0|True|1,2,3,4,5,6|
|shadow_index|50000|2820|24861|22319|True|1,2,3,4,5,6|
|team_defense|2300|2300|0|0|True|1,2,3,4,5,6|
|team_offense|2300|2300|0|0|True|1,2,3,4,5,6|

Per-column nonmissing counts for every season/week are in [FPDS_COLUMN_COVERAGE.json](FPDS_COLUMN_COVERAGE.json). They distinguish absent fields from observed zeros.

## File inventory and coverage grid

Coverage entries are observed week:row-count, not a completeness claim.2021–25 expected regular-season weeks1–18;2026 expected through the export marker (currently6). Missing entire weeks are listed. Entity coverage is checked separately against NFL eligible rows.

### bell-cow-report.csv

Table `bell_cow_report`; 942195 bytes; modified 2026-10-21T02:15:51.060946+00:00; SHA256 `d5e0971f8b7ec67b1c667110e6dfa80867f25d8becca40f27c0d9d760700ca65`; imported 2026-10-21T03:16:12.039639+00:00; header rows 2; raw rows 6302; valid weekly rows 6300; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`fp__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:69, 2:69, 3:66, 4:69, 5:68, 6:63, 7:60, 8:69, 9:63, 10:61, 11:67, 12:69, 13:61, 14:60, 15:69, 16:74, 17:69, 18:75|none|
|2022|1:65, 2:70, 3:65, 4:67, 5:70, 6:59, 7:63, 8:68, 9:60, 10:60, 11:63, 12:74, 13:65, 14:61, 15:67, 16:70, 17:68, 18:78|none|
|2023|1:76, 2:69, 3:71, 4:70, 5:56, 6:72, 7:54, 8:70, 9:63, 10:61, 11:64, 12:70, 13:57, 14:62, 15:74, 16:65, 17:71, 18:64|none|
|2024|1:68, 2:68, 3:66, 4:71, 5:60, 6:60, 7:66, 8:63, 9:67, 10:57, 11:59, 12:55, 13:64, 14:56, 15:65, 16:69, 17:74, 18:72|none|
|2025|1:69, 2:68, 3:69, 4:65, 5:64, 6:65, 7:63, 8:59, 9:55, 10:61, 11:62, 12:53, 13:66, 14:59, 15:67, 16:72, 17:69, 18:72|none|
|2026|1:67, 2:67, 3:67, 4:68, 5:68, 6:62|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__split_pct`|SPLIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`snaps__snaps`|Snaps (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`snaps__tm_snaps`|TM Snaps (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`snaps__snap_pct`|Snap % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__tm_att`|TM ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__att_pct`|ATT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tm_db`|TM DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tm_tgt`|TM TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp`|XFP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp_g`|XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__diff`|DIFF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__tm_xfp`|TM XFP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp_pct`|XFP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__tm_rb_xfp`|TM RB XFP (header inference; vendor definition unverified)|numeric|0.10|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__backfield_xfp_pct`|BACKFIELD XFP % (header inference; vendor definition unverified)|numeric|0.10|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### coach-records.csv

Table `coach_records`; 1007799 bytes; modified 2026-10-21T02:23:53.256834+00:00; SHA256 `01c76f2828c3f6f2c56ce6d64262885d746ccd444726821e2e1d63fc366a9fa4`; imported 2026-10-21T03:16:12.550559+00:00; header rows 2; raw rows 8572; valid weekly rows 8570; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`coach__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:96, 2:96, 3:96, 4:96, 5:96, 6:85, 7:78, 8:90, 9:84, 10:85, 11:90, 12:91, 13:84, 14:83, 15:95, 16:96, 17:96, 18:96|none|
|2022|1:92, 2:92, 3:92, 4:92, 5:92, 6:81, 7:80, 8:86, 9:74, 10:81, 11:81, 12:93, 13:88, 14:75, 15:93, 16:93, 17:87, 18:93|none|
|2023|1:93, 2:93, 3:93, 4:93, 5:81, 6:87, 7:75, 8:93, 9:82, 10:81, 11:82, 12:94, 13:76, 14:88, 15:93, 16:93, 17:93, 18:93|none|
|2024|1:95, 2:95, 3:95, 4:95, 5:83, 6:83, 7:89, 8:95, 9:90, 10:83, 11:83, 12:77, 13:95, 14:77, 15:95, 16:95, 17:95, 18:95|none|
|2025|1:95, 2:95, 3:95, 4:96, 5:84, 6:90, 7:90, 8:78, 9:85, 10:83, 11:89, 12:83, 13:95, 14:84, 15:95, 16:95, 17:95, 18:95|none|
|2026|1:95, 2:95, 3:95, 4:95, 5:89, 6:83|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`coach__rank`|RANK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`coach__coach`|COACH (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`coach__role`|ROLE (header inference; vendor definition unverified)|text|0.00|unknown|unverified text/units; excluded from numeric model features|
|`coach__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`coach__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__play_pct`|PLAY % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__w`|W (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`record__l`|L (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`record__t`|T (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`record__win_pct`|WIN % (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`points__pf`|PF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`points__pa`|PA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`points__diff`|DIFF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`points__pf_g`|PF/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`points__pa_g`|PA/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`plays__plays`|PLAYS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`plays__plays_g`|PLAYS/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`plays__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`plays__y_p`|Y/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`plays__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`plays__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`plays__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`plays__run_pct`|RUN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### cornerbacks.csv

Table `cornerbacks`; 665302 bytes; modified 2026-10-21T02:25:00.412382+00:00; SHA256 `5631791eb8a71e7cb37f2c68d323ecbc95244d5d66cc4975292d8054d1b4796f`; imported 2026-10-21T03:16:13.068559+00:00; header rows 2; raw rows 4702; valid weekly rows 4700; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player__player`, team=`player__team`, position=`player__pos`, native_id=`penalties__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:68, 2:62, 3:61, 4:66, 5:60, 6:56, 7:52, 8:59, 9:55, 10:50, 11:55, 12:49, 13:49, 14:64, 15:59, 16:60, 17:59, 18:56|none|
|2022|1:66, 2:65, 3:68, 4:56, 5:54, 6:47, 7:47, 8:45, 9:40, 10:46, 11:35, 12:51, 13:58, 14:48, 15:53, 16:46, 17:47, 18:53|none|
|2023|1:58, 2:56, 3:63, 4:48, 5:52, 6:51, 7:42, 8:58, 9:45, 10:50, 11:43, 12:53, 13:41, 14:50, 15:45, 16:63, 17:47, 18:37|none|
|2024|1:40, 2:42, 3:52, 4:50, 5:52, 6:42, 7:39, 8:53, 9:46, 10:39, 11:45, 12:43, 13:52, 14:42, 15:47, 16:43, 17:54, 18:50|none|
|2025|1:50, 2:52, 3:44, 4:34, 5:45, 6:36, 7:46, 8:33, 9:39, 10:39, 11:39, 12:41, 13:43, 14:38, 15:36, 16:45, 17:43, 18:34|none|
|2026|1:46, 2:42, 3:49, 4:45, 5:42, 6:41|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player__rank`|RANK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player__player`|Player (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`alignment__lcb_pct`|LCB % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`alignment__rcb_pct`|RCB % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`alignment__scb_pct`|SCB % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__tgts`|TGTS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__cmp_pct`|CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__ypt`|YPT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__td_tgt`|TD/TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__epa_tgt`|EPA/TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`coverage__fp_tgt`|FP/TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`coverage__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`separation_at_catch__step_pct`|STEP+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`separation_at_catch__blanketed_pct`|BLANKETED % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`forced_inc__fi`|FI (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`forced_inc__fi_pct`|FI % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__dpi`|DPI (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__dpi_yds`|DPI YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### coverage-matrix.csv

Table `coverage_matrix`; 475940 bytes; modified 2026-10-21T02:22:20.144588+00:00; SHA256 `61c9fec1e7439467f0982a38e2b072a3acb7f17373044abad2159c8b2b829c90`; imported 2026-10-21T03:16:13.435561+00:00; header rows 2; raw rows 2906; valid weekly rows 2904; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`team_details__name`, team=`None`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:26, 8:30, 9:28, 10:28, 11:30, 12:30, 13:28, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2022|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:28, 8:30, 9:26, 10:28, 11:28, 12:32, 13:30, 14:26, 15:32, 16:32, 17:30, 18:32|none|
|2023|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:26, 8:32, 9:28, 10:28, 11:28, 12:32, 13:26, 14:30, 15:32, 16:32, 17:32, 18:32|none|
|2024|1:32, 2:32, 3:32, 4:32, 5:28, 6:28, 7:30, 8:32, 9:30, 10:28, 11:28, 12:26, 13:32, 14:26, 15:32, 16:32, 17:32, 18:32|none|
|2025|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:30, 8:26, 9:28, 10:28, 11:30, 12:28, 13:32, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2026|1:32, 2:32, 3:32, 4:32, 5:30, 6:28|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`team_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__db_pct`|DB % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`team_details__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_zone__man_pct`|MAN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_zone__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|18.46|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`man_zone__zone_pct`|ZONE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_zone__fp_db__2`|FP/DB (header inference; vendor definition unverified)|numeric|17.63|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`blitz__blitz_pct`|BLITZ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`blitz__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.31|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`blitz__no_blitz_pct`|NO BLITZ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`blitz__fp_db__2`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`middle_of_field_look_closed_open__1_hi_mof_c_pct`|1-HI/MOF C % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`middle_of_field_look_closed_open__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|17.63|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`middle_of_field_look_closed_open__2_hi_mof_o_pct`|2-HI/MOF O % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`middle_of_field_look_closed_open__fp_db__2`|FP/DB (header inference; vendor definition unverified)|numeric|17.67|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`disguised_coverage__disguise_pct`|DISGUISE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`disguised_coverage__to_1_hi_pct`|TO 1-HI % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`disguised_coverage__to_2_hi_pct`|TO 2-HI % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverages__cover_0_pct`|COVER 0 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverages__cover_1_pct`|COVER 1 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverages__cover_2_pct`|COVER 2 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverages__cover_2_man_pct`|COVER 2 MAN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverages__cover_3_pct`|COVER 3 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverages__cover_4_pct`|COVER 4 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverages__cover_6_pct`|COVER 6 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`personnel_press__base_pct`|BASE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`personnel_press__nickel_pct`|NICKEL % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`personnel_press__dime_pct`|DIME % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`personnel_press__press_pct_any`|PRESS % (ANY) (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`personnel_press__press_pct_tgt`|PRESS % (TGT) (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### fantasy-points-allowed-qb.csv

Table `fantasy_points_allowed_qb`; 327973 bytes; modified 2026-10-21T02:25:46.638379+00:00; SHA256 `ea4c317d2b31d33f6d155012c639f89763dcd422c1a058190a5bf0a2b439c847`; imported 2026-10-21T03:16:13.994169+00:00; header rows 2; raw rows 2906; valid weekly rows 2904; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`team_details__name`, team=`None`, position=`team_details__pos`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:26, 8:30, 9:28, 10:28, 11:30, 12:30, 13:28, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2022|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:28, 8:30, 9:26, 10:28, 11:28, 12:32, 13:30, 14:26, 15:32, 16:32, 17:30, 18:32|none|
|2023|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:26, 8:32, 9:28, 10:28, 11:28, 12:32, 13:26, 14:30, 15:32, 16:32, 17:32, 18:32|none|
|2024|1:32, 2:32, 3:32, 4:32, 5:28, 6:28, 7:30, 8:32, 9:30, 10:28, 11:28, 12:26, 13:32, 14:26, 15:32, 16:32, 17:32, 18:32|none|
|2025|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:30, 8:26, 9:28, 10:28, 11:30, 12:28, 13:32, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2026|1:32, 2:32, 3:32, 4:32, 5:30, 6:28|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`team_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__fp_pct`|FP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`passing__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__cmp`|CMP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`passing__pass_fp`|PASS FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__des_att`|DES ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__scrm`|SCRM (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__des_yds`|DES YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__scrm_yds`|SCRM YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ypc`|YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__des_ypc`|DES YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__scrm_ypc`|SCRM YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__des_td`|DES TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__scrm_td`|SCRM TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__des_fp`|DES FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`rushing__scrm_fp`|SCRM FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_opp`|FP/OPP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|

### fantasy-points-allowed-rb.csv

Table `fantasy_points_allowed_rb`; 291078 bytes; modified 2026-10-21T02:25:57.937393+00:00; SHA256 `15f126a75b4577d8ef71b544e6dca6378dcef17d2d246305ea23aa8bd8f3e12a`; imported 2026-10-21T03:16:14.394204+00:00; header rows 2; raw rows 2906; valid weekly rows 2904; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`team_details__name`, team=`None`, position=`team_details__pos`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:26, 8:30, 9:28, 10:28, 11:30, 12:30, 13:28, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2022|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:28, 8:30, 9:26, 10:28, 11:28, 12:32, 13:30, 14:26, 15:32, 16:32, 17:30, 18:32|none|
|2023|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:26, 8:32, 9:28, 10:28, 11:28, 12:32, 13:26, 14:30, 15:32, 16:32, 17:32, 18:32|none|
|2024|1:32, 2:32, 3:32, 4:32, 5:28, 6:28, 7:30, 8:32, 9:30, 10:28, 11:28, 12:26, 13:32, 14:26, 15:32, 16:32, 17:32, 18:32|none|
|2025|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:30, 8:26, 9:28, 10:28, 11:30, 12:28, 13:32, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2026|1:32, 2:32, 3:32, 4:32, 5:30, 6:28|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`team_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__fp_pct`|FP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ypc`|YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ru_fpg`|Ru FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypt`|YPT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__re_fpg`|Re FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`receiving__tms_pct`|TMS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yms_pct`|YMS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__fp_sh_pct`|FP SH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_opp`|FP/OPP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_tch`|FP/TCH (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|

### fantasy-points-allowed-te.csv

Table `fantasy_points_allowed_te`; 254093 bytes; modified 2026-10-21T02:26:24.888858+00:00; SHA256 `c0cc892bbcc3bec60253e2ab306219d321916845960d3ad1fc14ec097b6574e1`; imported 2026-10-21T03:16:14.759759+00:00; header rows 2; raw rows 2890; valid weekly rows 2888; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`team_details__name`, team=`None`, position=`team_details__pos`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:26, 8:30, 9:28, 10:28, 11:29, 12:30, 13:28, 14:28, 15:32, 16:32, 17:31, 18:32|none|
|2022|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:28, 8:29, 9:26, 10:28, 11:28, 12:32, 13:30, 14:26, 15:32, 16:32, 17:30, 18:32|none|
|2023|1:32, 2:32, 3:32, 4:31, 5:26, 6:29, 7:25, 8:31, 9:28, 10:28, 11:28, 12:32, 13:25, 14:30, 15:32, 16:32, 17:32, 18:32|none|
|2024|1:32, 2:31, 3:32, 4:32, 5:28, 6:28, 7:30, 8:32, 9:30, 10:28, 11:28, 12:26, 13:32, 14:26, 15:32, 16:31, 17:32, 18:32|none|
|2025|1:32, 2:31, 3:31, 4:32, 5:28, 6:30, 7:30, 8:26, 9:28, 10:28, 11:30, 12:28, 13:32, 14:28, 15:31, 16:32, 17:32, 18:31|none|
|2026|1:32, 2:32, 3:32, 4:32, 5:30, 6:28|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`team_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__fp_pct`|FP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypt`|YPT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__re_fpg`|Re FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`receiving__tms_pct`|TMS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yms_pct`|YMS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__fp_sh_pct`|FP SH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ypc`|YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ru_fpg`|Ru FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_opp`|FP/OPP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|

### fantasy-points-allowed-wr.csv

Table `fantasy_points_allowed_wr`; 273763 bytes; modified 2026-10-21T02:26:13.049809+00:00; SHA256 `cb5b53e744090ee80ed71b659bd0c169b5aace14d65ad03bdc8351173430101c`; imported 2026-10-21T03:16:15.110757+00:00; header rows 2; raw rows 2906; valid weekly rows 2904; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`team_details__name`, team=`None`, position=`team_details__pos`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:26, 8:30, 9:28, 10:28, 11:30, 12:30, 13:28, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2022|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:28, 8:30, 9:26, 10:28, 11:28, 12:32, 13:30, 14:26, 15:32, 16:32, 17:30, 18:32|none|
|2023|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:26, 8:32, 9:28, 10:28, 11:28, 12:32, 13:26, 14:30, 15:32, 16:32, 17:32, 18:32|none|
|2024|1:32, 2:32, 3:32, 4:32, 5:28, 6:28, 7:30, 8:32, 9:30, 10:28, 11:28, 12:26, 13:32, 14:26, 15:32, 16:32, 17:32, 18:32|none|
|2025|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:30, 8:26, 9:28, 10:28, 11:30, 12:28, 13:32, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2026|1:32, 2:32, 3:32, 4:32, 5:30, 6:28|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`team_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__fp_pct`|FP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypt`|YPT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__re_fpg`|Re FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`receiving__tms_pct`|TMS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yms_pct`|YMS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__fp_sh_pct`|FP SH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ypc`|YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ru_fpg`|Ru FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_opp`|FP/OPP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|

### injury-reports.csv

Table `injury_reports`; 1281591 bytes; modified 2026-10-21T02:27:54.232482+00:00; SHA256 `4eeea02b12cb19e00e9920cb996cc93a5ed90bdd65ef85098f6a142f2e7a111c`; imported 2026-10-21T03:16:15.516513+00:00; header rows 2; raw rows 8344; valid weekly rows 8342; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`season__2`, week=`wk`, name=`player`, team=`team`, position=`pos`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:63, 2:55, 3:72, 4:68, 5:96, 6:88, 7:86, 8:91, 9:79, 10:86, 11:102, 12:92, 13:88, 14:84, 15:100, 16:97, 17:93, 18:98|none|
|2022|1:51, 2:61, 3:82, 4:92, 5:108, 6:101, 7:94, 8:86, 9:71, 10:87, 11:76, 12:84, 13:90, 14:79, 15:88, 16:87, 17:88, 18:80|none|
|2023|1:54, 2:54, 3:63, 4:76, 5:66, 6:75, 7:65, 8:92, 9:94, 10:83, 11:97, 12:104, 13:93, 14:97, 15:107, 16:108, 17:117, 18:111|none|
|2024|1:52, 2:65, 3:80, 4:89, 5:100, 6:91, 7:110, 8:103, 9:103, 10:93, 11:78, 12:67, 13:85, 14:75, 15:87, 16:107, 17:100, 18:108|none|
|2025|1:57, 2:66, 3:79, 4:87, 5:80, 6:89, 7:90, 8:87, 9:98, 10:97, 11:102, 12:89, 13:103, 14:84, 15:109, 16:109, 17:118, 18:111|none|
|2026|1:52, 2:57, 3:82, 4:83, 5:105, 6:116|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`season`|Season (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unnamed`|# (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`player`|Player (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`season__2`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`wk`|WK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`injury`|INJURY (header inference; vendor definition unverified)|text|0.02|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`practice`|PRACTICE (header inference; vendor definition unverified)|text|0.56|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`status`|STATUS (header inference; vendor definition unverified)|text|48.61|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`that_week_s_game__fp`|FP (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`that_week_s_game__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_s_game__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_receiving__rtes`|RTES (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_receiving__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_receiving__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_receiving__rec`|REC (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_receiving__rec_yds`|REC YDS (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_receiving__rec_td`|REC TD (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_rushing__des_att`|DES ATT (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_rushing__des_yds`|DES YDS (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_rushing__des_td`|DES TD (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_rushing__dcs_pct`|DCS % (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__att`|ATT (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__cmp`|CMP (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__pass_yds`|PASS YDS (header inference; vendor definition unverified)|numeric|40.28|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__pass_td`|PASS TD (header inference; vendor definition unverified)|numeric|40.28|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__int`|INT (header inference; vendor definition unverified)|numeric|40.15|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__sack`|SACK (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__scrm`|SCRM (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__scrm_yds`|SCRM YDS (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`that_week_passing__scrm_td`|SCRM TD (header inference; vendor definition unverified)|numeric|40.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### lineup-combos-db.csv

Table `lineup_combos_db`; 1516030 bytes; modified 2026-10-21T02:23:26.389368+00:00; SHA256 `61d9278b4e8f49c1380ee32e66937e1dd9a04621570246db140ba199aebb6bc5`; imported 2026-10-21T03:16:16.112677+00:00; header rows 2; raw rows 10602; valid weekly rows 10600; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`unit_details__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:118, 2:123, 3:123, 4:131, 5:128, 6:113, 7:110, 8:108, 9:100, 10:114, 11:119, 12:104, 13:108, 14:111, 15:117, 16:121, 17:124, 18:136|none|
|2022|1:102, 2:111, 3:103, 4:109, 5:117, 6:98, 7:99, 8:105, 9:93, 10:113, 11:92, 12:119, 13:110, 14:93, 15:115, 16:115, 17:115, 18:116|none|
|2023|1:113, 2:124, 3:101, 4:111, 5:101, 6:110, 7:86, 8:103, 9:121, 10:107, 11:101, 12:103, 13:89, 14:101, 15:122, 16:115, 17:118, 18:124|none|
|2024|1:104, 2:100, 3:118, 4:111, 5:104, 6:99, 7:107, 8:118, 9:102, 10:98, 11:111, 12:94, 13:123, 14:105, 15:116, 16:121, 17:117, 18:119|none|
|2025|1:105, 2:113, 3:117, 4:119, 5:91, 6:102, 7:115, 8:102, 9:93, 10:103, 11:105, 12:112, 13:116, 14:97, 15:121, 16:122, 17:118, 18:126|none|
|2026|1:110, 2:117, 3:123, 4:108, 5:110, 6:105|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`unit_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__unit`|Unit (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__men`|MEN (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__unit_pct`|UNIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|1.95|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|10.04|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|0.23|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production_allowed__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production_allowed__pass_yds`|PASS YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production_allowed__rush_yds`|RUSH YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production_allowed__pass_td`|PASS TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production_allowed__rush_td`|RUSH TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production_allowed__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### lineup-combos-front.csv

Table `lineup_combos_front`; 1512072 bytes; modified 2026-10-21T02:23:19.811932+00:00; SHA256 `e65ae01733ddc0ea37770d202a8e99febfb18bd08ff9231caf591e0f9caf7882`; imported 2026-10-21T03:16:16.780254+00:00; header rows 2; raw rows 9702; valid weekly rows 9700; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`unit_details__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:126, 2:104, 3:121, 4:114, 5:108, 6:101, 7:82, 8:114, 9:98, 10:93, 11:114, 12:101, 13:82, 14:96, 15:116, 16:103, 17:121, 18:128|none|
|2022|1:105, 2:97, 3:117, 4:114, 5:115, 6:99, 7:87, 8:103, 9:95, 10:106, 11:86, 12:115, 13:100, 14:83, 15:100, 16:110, 17:96, 18:94|none|
|2023|1:116, 2:106, 3:107, 4:102, 5:91, 6:105, 7:100, 8:117, 9:100, 10:92, 11:96, 12:117, 13:85, 14:108, 15:106, 16:107, 17:109, 18:112|none|
|2024|1:101, 2:100, 3:102, 4:104, 5:96, 6:99, 7:99, 8:113, 9:95, 10:95, 11:91, 12:83, 13:111, 14:80, 15:106, 16:111, 17:123, 18:110|none|
|2025|1:104, 2:108, 3:88, 4:97, 5:89, 6:91, 7:91, 8:77, 9:86, 10:92, 11:88, 12:96, 13:111, 14:93, 15:104, 16:101, 17:97, 18:92|none|
|2026|1:102, 2:88, 3:88, 4:100, 5:88, 6:90|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`unit_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__unit`|Unit (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__men`|MEN (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__unit_pct`|UNIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|2.78|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|16.23|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|0.29|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pass_rush__pres_pct`|PRES % (header inference; vendor definition unverified)|numeric|2.78|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pass_rush__sack_pct`|SACK % (header inference; vendor definition unverified)|numeric|2.78|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`run_defense__ypc`|YPC (header inference; vendor definition unverified)|numeric|16.23|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`run_defense__ybc_a`|YBC/A (header inference; vendor definition unverified)|numeric|16.23|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### lineup-combos-ol.csv

Table `lineup_combos_ol`; 996367 bytes; modified 2026-10-21T02:22:37.498433+00:00; SHA256 `69c258d9ab5245dbfb952a6146261c8259c3bc0b6f262e33ffc890b0d91b7c88`; imported 2026-10-21T03:16:17.294365+00:00; header rows 2; raw rows 6761; valid weekly rows 6759; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`unit_details__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:77, 2:65, 3:71, 4:70, 5:65, 6:66, 7:64, 8:63, 9:65, 10:70, 11:80, 12:71, 13:67, 14:68, 15:63, 16:82, 17:77, 18:94|none|
|2022|1:74, 2:65, 3:69, 4:68, 5:68, 6:68, 7:65, 8:65, 9:59, 10:62, 11:65, 12:66, 13:67, 14:63, 15:74, 16:74, 17:75, 18:84|none|
|2023|1:64, 2:63, 3:74, 4:63, 5:66, 6:61, 7:45, 8:74, 9:61, 10:50, 11:55, 12:71, 13:62, 14:76, 15:83, 16:82, 17:91, 18:94|none|
|2024|1:62, 2:64, 3:83, 4:70, 5:73, 6:68, 7:69, 8:81, 9:77, 10:62, 11:64, 12:53, 13:60, 14:46, 15:74, 16:78, 17:91, 18:75|none|
|2025|1:73, 2:68, 3:75, 4:77, 5:61, 6:63, 7:72, 8:65, 9:73, 10:67, 11:74, 12:81, 13:75, 14:69, 15:93, 16:95, 17:89, 18:83|none|
|2026|1:67, 2:75, 3:75, 4:70, 5:68, 6:57|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`unit_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__unit`|Unit (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__men`|MEN (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__unit_pct`|UNIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|17.84|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|7.18|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|6.51|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pass_protection__pres_pct`|PRES % (header inference; vendor definition unverified)|numeric|17.84|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pass_protection__sack_pct`|SACK % (header inference; vendor definition unverified)|numeric|17.84|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`run_game__ypc`|YPC (header inference; vendor definition unverified)|numeric|7.18|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`run_game__ybc_a`|YBC/A (header inference; vendor definition unverified)|numeric|7.18|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### lineup-combos-rb.csv

Table `lineup_combos_rb`; 1119504 bytes; modified 2026-10-21T02:22:58.993711+00:00; SHA256 `c4f2056b42435ca50675316924fe2e66055a2238486f10a8c821a09ad277fba7`; imported 2026-10-21T03:16:17.813403+00:00; header rows 2; raw rows 11869; valid weekly rows 11867; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`unit_details__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:133, 2:131, 3:134, 4:140, 5:137, 6:111, 7:111, 8:118, 9:114, 10:117, 11:123, 12:126, 13:110, 14:112, 15:125, 16:137, 17:136, 18:140|none|
|2022|1:132, 2:141, 3:133, 4:132, 5:137, 6:115, 7:122, 8:119, 9:117, 10:121, 11:126, 12:143, 13:133, 14:105, 15:132, 16:134, 17:129, 18:148|none|
|2023|1:140, 2:126, 3:127, 4:127, 5:116, 6:129, 7:101, 8:122, 9:105, 10:115, 11:116, 12:122, 13:100, 14:124, 15:136, 16:118, 17:129, 18:127|none|
|2024|1:126, 2:121, 3:127, 4:124, 5:109, 6:112, 7:124, 8:125, 9:117, 10:109, 11:110, 12:102, 13:128, 14:109, 15:127, 16:136, 17:136, 18:124|none|
|2025|1:129, 2:119, 3:129, 4:126, 5:121, 6:113, 7:117, 8:110, 9:109, 10:116, 11:126, 12:103, 13:131, 14:122, 15:130, 16:132, 17:141, 18:132|none|
|2026|1:128, 2:132, 3:126, 4:127, 5:123, 6:105|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`unit_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__unit`|Unit (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__men`|MEN (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__unit_pct`|UNIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|13.62|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|12.92|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|1.85|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__pass_yds`|PASS YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rush_yds`|RUSH YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__pass_td`|PASS TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rush_td`|RUSH TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### lineup-combos-skill.csv

Table `lineup_combos_skill`; 1501419 bytes; modified 2026-10-21T02:22:52.095493+00:00; SHA256 `9dace82d5ff09e3b07e3e0a573032aa4f6330cc3f9f0b8e4e518067d927bc95e`; imported 2026-10-21T03:16:18.521496+00:00; header rows 2; raw rows 10502; valid weekly rows 10500; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`unit_details__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:130, 2:115, 3:122, 4:128, 5:127, 6:103, 7:97, 8:118, 9:114, 10:107, 11:115, 12:119, 13:104, 14:114, 15:117, 16:112, 17:118, 18:109|none|
|2022|1:113, 2:114, 3:126, 4:125, 5:123, 6:101, 7:97, 8:112, 9:93, 10:100, 11:106, 12:109, 13:93, 14:97, 15:119, 16:116, 17:109, 18:113|none|
|2023|1:123, 2:119, 3:114, 4:106, 5:98, 6:101, 7:101, 8:124, 9:101, 10:118, 11:99, 12:118, 13:106, 14:108, 15:121, 16:107, 17:119, 18:116|none|
|2024|1:107, 2:116, 3:112, 4:113, 5:101, 6:98, 7:110, 8:114, 9:120, 10:97, 11:79, 12:94, 13:111, 14:89, 15:101, 16:112, 17:123, 18:120|none|
|2025|1:114, 2:132, 3:115, 4:107, 5:96, 6:104, 7:108, 8:96, 9:95, 10:104, 11:100, 12:97, 13:119, 14:97, 15:107, 16:110, 17:105, 18:105|none|
|2026|1:111, 2:106, 3:118, 4:104, 5:106, 6:93|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`unit_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__unit`|Unit (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__men`|MEN (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__unit_pct`|UNIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|4.13|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|14.78|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|0.12|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__pass_yds`|PASS YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rush_yds`|RUSH YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__pass_td`|PASS TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rush_td`|RUSH TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### lineup-combos-te.csv

Table `lineup_combos_te`; 1336424 bytes; modified 2026-10-21T02:23:11.695239+00:00; SHA256 `a6de83c39a6cbf9b53969ff9ef1f29f7be1050ed05d929590fffda279bbab416`; imported 2026-10-21T03:16:19.161573+00:00; header rows 2; raw rows 13602; valid weekly rows 13600; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`unit_details__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:146, 2:145, 3:157, 4:158, 5:146, 6:127, 7:113, 8:139, 9:124, 10:129, 11:142, 12:124, 13:124, 14:125, 15:140, 16:135, 17:140, 18:148|none|
|2022|1:149, 2:151, 3:151, 4:150, 5:148, 6:124, 7:145, 8:153, 9:125, 10:134, 11:137, 12:146, 13:140, 14:123, 15:153, 16:162, 17:150, 18:154|none|
|2023|1:153, 2:148, 3:153, 4:158, 5:125, 6:143, 7:130, 8:138, 9:131, 10:129, 11:126, 12:149, 13:123, 14:140, 15:155, 16:146, 17:135, 18:142|none|
|2024|1:148, 2:133, 3:146, 4:142, 5:132, 6:134, 7:137, 8:153, 9:150, 10:135, 11:131, 12:115, 13:146, 14:119, 15:143, 16:147, 17:144, 18:144|none|
|2025|1:147, 2:135, 3:150, 4:143, 5:141, 6:132, 7:140, 8:108, 9:131, 10:137, 11:123, 12:146, 13:147, 14:139, 15:157, 16:159, 17:153, 18:150|none|
|2026|1:167, 2:167, 3:168, 4:161, 5:170, 6:149|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`unit_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__unit`|Unit (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__men`|MEN (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__unit_pct`|UNIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|9.16|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|7.12|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|0.68|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__pass_yds`|PASS YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rush_yds`|RUSH YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__pass_td`|PASS TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rush_td`|RUSH TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### lineup-combos-wr.csv

Table `lineup_combos_wr`; 1384866 bytes; modified 2026-10-21T02:23:06.277370+00:00; SHA256 `ed43407d0a1db28c997211ac7fa16227ad362eb5eaa56ffb5e7786cd84c1a223`; imported 2026-10-21T03:16:19.918613+00:00; header rows 2; raw rows 12602; valid weekly rows 12600; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`unit_details__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:137, 2:133, 3:135, 4:136, 5:139, 6:113, 7:115, 8:134, 9:115, 10:130, 11:140, 12:130, 13:128, 14:125, 15:139, 16:142, 17:138, 18:142|none|
|2022|1:140, 2:131, 3:135, 4:129, 5:136, 6:112, 7:119, 8:125, 9:112, 10:114, 11:115, 12:130, 13:122, 14:101, 15:136, 16:125, 17:135, 18:135|none|
|2023|1:139, 2:151, 3:135, 4:145, 5:132, 6:130, 7:116, 8:138, 9:135, 10:121, 11:117, 12:137, 13:114, 14:132, 15:138, 16:139, 17:141, 18:139|none|
|2024|1:140, 2:137, 3:135, 4:126, 5:122, 6:118, 7:129, 8:138, 9:129, 10:109, 11:123, 12:112, 13:126, 14:104, 15:132, 16:131, 17:135, 18:129|none|
|2025|1:131, 2:137, 3:147, 4:153, 5:131, 6:133, 7:132, 8:114, 9:121, 10:137, 11:140, 12:135, 13:143, 14:121, 15:149, 16:154, 17:146, 18:137|none|
|2026|1:143, 2:142, 3:150, 4:148, 5:128, 6:131|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`unit_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__unit`|Unit (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__men`|MEN (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`unit_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__unit_pct`|UNIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`unit_details__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|6.11|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|7.23|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|0.10|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__pass_yds`|PASS YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rush_yds`|RUSH YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__pass_td`|PASS TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rush_td`|RUSH TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### pace.csv

Table `pace`; 602913 bytes; modified 2026-10-21T02:22:06.468297+00:00; SHA256 `4387177b580c21ece21d5e390cb69e426300ff0e7afd90265e31479065483fdd`; imported 2026-10-21T03:16:20.520228+00:00; header rows 2; raw rows 2906; valid weekly rows 2904; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`team_details__name`, team=`None`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:26, 8:30, 9:28, 10:28, 11:30, 12:30, 13:28, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2022|1:32, 2:32, 3:32, 4:32, 5:32, 6:28, 7:28, 8:30, 9:26, 10:28, 11:28, 12:32, 13:30, 14:26, 15:32, 16:32, 17:30, 18:32|none|
|2023|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:26, 8:32, 9:28, 10:28, 11:28, 12:32, 13:26, 14:30, 15:32, 16:32, 17:32, 18:32|none|
|2024|1:32, 2:32, 3:32, 4:32, 5:28, 6:28, 7:30, 8:32, 9:30, 10:28, 11:28, 12:26, 13:32, 14:26, 15:32, 16:32, 17:32, 18:32|none|
|2025|1:32, 2:32, 3:32, 4:32, 5:28, 6:30, 7:30, 8:26, 9:28, 10:28, 11:30, 12:28, 13:32, 14:28, 15:32, 16:32, 17:32, 18:32|none|
|2026|1:32, 2:32, 3:32, 4:32, 5:30, 6:28|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`team_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__play_pct`|PLAY % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__plays`|PLAYS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__pace`|PACE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__pl_dr`|PL/DR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__sec_dr`|SEC/DR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`situational_pace__pace_lead`|PACE LEAD (header inference; vendor definition unverified)|numeric|41.56|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`situational_pace__pace_trail`|PACE TRAIL (header inference; vendor definition unverified)|numeric|32.64|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`situational_pace__pace_neu`|PACE NEU (header inference; vendor definition unverified)|numeric|0.03|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`situational_pace__pace_diff`|PACE DIFF (header inference; vendor definition unverified)|numeric|73.28|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`situational_pace__pace_h1`|PACE H1 (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`situational_pace__pace_h2`|PACE H2 (header inference; vendor definition unverified)|numeric|0.17|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pass_tendency__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pass_tendency__proe`|PROE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### passing-basic.csv

Table `passing_basic`; 181264 bytes; modified 2026-10-21T02:12:46.461314+00:00; SHA256 `dfa3932edfc282bf7f80f50132dd6f84c9d010d50dd4237bc9b9adef64ce14ac`; imported 2026-10-21T03:16:20.977820+00:00; header rows 2; raw rows 1202; valid weekly rows 1200; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`fp__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:23, 2:18, 3:19, 4:17, 5:20, 6:12, 7:12, 8:13, 9:15, 10:10, 11:10, 12:12, 13:13, 14:14, 15:7, 16:12, 17:11, 18:11|none|
|2022|1:15, 2:12, 3:19, 4:12, 5:13, 6:11, 7:12, 8:12, 9:9, 10:12, 11:12, 12:15, 13:11, 14:14, 15:11, 16:10, 17:8, 18:6|none|
|2023|1:7, 2:15, 3:18, 4:13, 5:14, 6:9, 7:15, 8:14, 9:9, 10:13, 11:13, 12:14, 13:12, 14:12, 15:11, 16:15, 17:14, 18:14|none|
|2024|1:8, 2:12, 3:12, 4:10, 5:14, 6:10, 7:9, 8:18, 9:8, 10:10, 11:17, 12:16, 13:12, 14:11, 15:8, 16:18, 17:10, 18:11|none|
|2025|1:11, 2:11, 3:7, 4:10, 5:14, 6:13, 7:13, 8:9, 9:15, 10:11, 11:10, 12:13, 13:11, 14:10, 15:16, 16:15, 17:13, 18:9|none|
|2026|1:10, 2:13, 3:16, 4:15, 5:11, 6:15|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__db_pct`|DB % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__cmp`|CMP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__cmp_pct`|CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__ypa`|YPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`passing__sack`|SACK (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__sack_pct`|SACK % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__sk_yds`|SK YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__any_a`|ANY/A (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total_rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total_rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total_rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scrambles__scr`|SCR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scrambles__scr_yds`|SCR YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scrambles__scr_td`|SCR TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fp__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_opp`|FP/OPP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__opp`|OPP (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`fp__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### passing-depth-of-target.csv

Table `passing_depth_of_target`; 389067 bytes; modified 2026-10-21T02:13:32.646587+00:00; SHA256 `629f907f1b99041e86e3dab8fd966edcc4d94fbb4c930ac6882b1f26cceaa59b`; imported 2026-10-21T03:16:21.143820+00:00; header rows 2; raw rows 1802; valid weekly rows 1800; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`20_yards__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:26, 2:23, 3:25, 4:22, 5:23, 6:21, 7:16, 8:22, 9:19, 10:15, 11:18, 12:18, 13:19, 14:19, 15:18, 16:17, 17:19, 18:19|none|
|2022|1:23, 2:20, 3:27, 4:19, 5:24, 6:14, 7:17, 8:19, 9:13, 10:20, 11:17, 12:20, 13:16, 14:18, 15:17, 16:21, 17:15, 18:17|none|
|2023|1:16, 2:26, 3:21, 4:18, 5:19, 6:15, 7:19, 8:23, 9:16, 10:15, 11:17, 12:19, 13:17, 14:19, 15:19, 16:25, 17:22, 18:14|none|
|2024|1:14, 2:16, 3:20, 4:18, 5:17, 6:22, 7:15, 8:26, 9:20, 10:15, 11:22, 12:20, 13:22, 14:19, 15:16, 16:22, 17:17, 18:21|none|
|2025|1:17, 2:21, 3:17, 4:15, 5:23, 6:20, 7:20, 8:13, 9:18, 10:15, 11:12, 12:17, 13:17, 14:14, 15:21, 16:16, 17:16, 18:14|none|
|2026|1:18, 2:19, 3:20, 4:22, 5:16, 6:21|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__att_pct`|ATT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__cmp`|CMP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`overall__catch_pct`|CATCH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__acc_pct`|ACC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__hero`|HERO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__twt`|TWT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__cmp`|CMP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`behind_los__catch_pct`|CATCH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__acc_pct`|ACC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__hero`|HERO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`behind_los__twt`|TWT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__cmp`|CMP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`0_9_yards__catch_pct`|CATCH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__acc_pct`|ACC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__hero`|HERO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`0_9_yards__twt`|TWT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__cmp`|CMP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`10_19_yards__catch_pct`|CATCH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__acc_pct`|ACC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__hero`|HERO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`10_19_yards__twt`|TWT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__cmp`|CMP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`20_yards__catch_pct`|CATCH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__acc_pct`|ACC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__hero`|HERO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__twt`|TWT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`20_yards__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### passing-situation.csv

Table `passing_situation`; 216593 bytes; modified 2026-10-21T02:13:46.300879+00:00; SHA256 `4c14a03b4c2aab9673ac025ef705a7eadd6adb2fb1aa9aa7e2b455d9a98c0c19`; imported 2026-10-21T03:16:21.421962+00:00; header rows 2; raw rows 1002; valid weekly rows 1000; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`two_high__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:16, 2:10, 3:14, 4:15, 5:12, 6:14, 7:10, 8:10, 9:12, 10:10, 11:11, 12:10, 13:16, 14:15, 15:11, 16:10, 17:10, 18:8|none|
|2022|1:13, 2:12, 3:18, 4:9, 5:13, 6:12, 7:10, 8:10, 9:8, 10:13, 11:6, 12:12, 13:10, 14:14, 15:11, 16:11, 17:9, 18:10|none|
|2023|1:13, 2:16, 3:14, 4:11, 5:11, 6:13, 7:7, 8:12, 9:10, 10:11, 11:8, 12:10, 13:6, 14:16, 15:9, 16:13, 17:6, 18:5|none|
|2024|1:7, 2:7, 3:10, 4:9, 5:11, 6:10, 7:6, 8:11, 9:10, 10:9, 11:8, 12:12, 13:12, 14:10, 15:7, 16:15, 17:9, 18:9|none|
|2025|1:11, 2:10, 3:11, 4:11, 5:12, 6:6, 7:10, 8:4, 9:7, 10:9, 11:8, 12:9, 13:8, 14:8, 15:11, 16:9, 17:11, 18:7|none|
|2026|1:7, 2:7, 3:12, 4:12, 5:9, 6:13|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__db_pct`|DB % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__cmp_pct`|CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ypa`|YPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`overall__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`man__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__cmp_pct`|CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__ypa`|YPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`man__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`zone__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__cmp_pct`|CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__ypa`|YPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`zone__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`single_high__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__cmp_pct`|CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__ypa`|YPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`single_high__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`two_high__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__cmp_pct`|CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__ypa`|YPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`two_high__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`two_high__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### passing-stats.csv

Table `passing_stats`; 424659 bytes; modified 2026-10-21T02:13:09.301811+00:00; SHA256 `73a325415ce4091f2e829ed1b0c3af4e220520bdf895f852b0c7a3a9a77f4916`; imported 2026-10-21T03:16:21.628552+00:00; header rows 2; raw rows 1202; valid weekly rows 1200; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`fp__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:23, 2:18, 3:19, 4:17, 5:20, 6:12, 7:12, 8:13, 9:15, 10:10, 11:10, 12:12, 13:13, 14:14, 15:7, 16:12, 17:11, 18:11|none|
|2022|1:15, 2:12, 3:19, 4:12, 5:13, 6:11, 7:12, 8:12, 9:9, 10:12, 11:12, 12:15, 13:11, 14:14, 15:11, 16:10, 17:8, 18:6|none|
|2023|1:7, 2:15, 3:18, 4:13, 5:14, 6:9, 7:15, 8:14, 9:9, 10:13, 11:13, 12:14, 13:12, 14:12, 15:11, 16:15, 17:14, 18:14|none|
|2024|1:8, 2:12, 3:12, 4:10, 5:14, 6:10, 7:9, 8:18, 9:8, 10:10, 11:17, 12:16, 13:12, 14:11, 15:8, 16:18, 17:10, 18:11|none|
|2025|1:11, 2:11, 3:7, 4:10, 5:14, 6:13, 7:13, 8:9, 9:15, 10:11, 11:10, 12:13, 13:11, 14:10, 15:16, 16:15, 17:13, 18:9|none|
|2026|1:10, 2:13, 3:16, 4:15, 5:11, 6:15|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__db_pct`|DB % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__cmp`|CMP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__cmp_pct`|CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__ypa`|YPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__xtd`|XTD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__td_pct`|TD % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__int`|INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__int_pct`|INT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`passing__any_a`|ANY/A (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__sack`|SACK (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__sack_pct`|SACK % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`passing__sk_yds`|SK YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__scr`|SCR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__scr_yds`|SCR YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__scr_td`|SCR TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__cpoe`|CPOE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__adj_cmp_pct`|ADJ CMP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__adot`|ADOT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ayds`|AYDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__deep_pct`|DEEP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ezatt`|EZATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__yac_pct`|YAC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__1_st_rd_pct`|1ST RD % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__acc_pct`|ACC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__catch_pct`|CATCH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__off_tgt_pct`|OFF TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__hero_pct`|HERO % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__twt_pct`|TWT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__drop_pct`|DROP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__drop_yds`|DROP YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ttt`|TTT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ttp`|TTP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ttsk`|TTSK (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ttsc`|TTSC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__qbsk`|QBSK (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__press_pct`|PRESS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__qk_pres_pct`|QK PRES % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__p2_s_pct`|P2S % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__pres_o_e`|PRES O/E (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__rb_tgt_pct`|RB TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__wr_tgt_pct`|WR TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__te_tgt_pct`|TE TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__wide_tgt_pct`|WIDE TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__slot_tgt_pct`|SLOT TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__inline_tgt_pct`|INLINE TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__back_tgt_pct`|BACK TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ckd_pct`|CKD % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__rpo_pct`|RPO % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ta`|TA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__bpa`|BPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__spk`|SPK (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__epa`|EPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fp__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_opp`|FP/OPP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp`|XFP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp_g`|XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__diff`|DIFF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__pass_fp`|PASS FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__rush_fp`|RUSH FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### playcaller-stats.csv

Table `playcaller_stats`; 908903 bytes; modified 2026-10-21T02:24:42.616484+00:00; SHA256 `1f2dd73f79a2e71d2fc915ab03cf46a1d47d36b8127afbb9f5309b7c7a8f44c3`; imported 2026-10-21T03:16:21.998549+00:00; header rows 2; raw rows 2602; valid weekly rows 2600; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`None`, team=`coach__team`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:31, 2:28, 3:30, 4:31, 5:30, 6:28, 7:23, 8:30, 9:26, 10:25, 11:28, 12:27, 13:26, 14:25, 15:27, 16:28, 17:25, 18:28|none|
|2022|1:30, 2:27, 3:30, 4:31, 5:29, 6:27, 7:28, 8:27, 9:23, 10:27, 11:23, 12:30, 13:26, 14:25, 15:30, 16:27, 17:26, 18:27|none|
|2023|1:28, 2:29, 3:28, 4:25, 5:23, 6:25, 7:25, 8:30, 9:22, 10:27, 11:25, 12:28, 13:23, 14:24, 15:30, 16:29, 17:28, 18:28|none|
|2024|1:25, 2:28, 3:25, 4:28, 5:26, 6:26, 7:25, 8:32, 9:30, 10:26, 11:27, 12:25, 13:31, 14:26, 15:26, 16:29, 17:28, 18:29|none|
|2025|1:27, 2:28, 3:29, 4:28, 5:27, 6:28, 7:25, 8:22, 9:28, 10:23, 11:23, 12:23, 13:28, 14:23, 15:29, 16:28, 17:28, 18:26|none|
|2026|1:28, 2:29, 3:31, 4:30, 5:24, 6:27|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`coach__rank`|RANK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`coach__coach`|Coach (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`coach__role_s`|Role(s) (header inference; vendor definition unverified)|text|0.00|unknown|unverified text/units; excluded from numeric model features|
|`coach__team`|TEAM (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`coach__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__play_pct`|PLAY % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume__plays`|PLAYS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume__plays_g`|PLAYS/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume__pace`|PACE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume__db`|DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume__runs`|RUNS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume__run_pct`|RUN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__fp_db`|FP/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`efficiency__epa_play`|EPA/PLAY (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_r`|EPA/R (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__any_a`|ANY/A (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__ypc`|YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_y_g`|PASS Y/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__rush_y_g`|RUSH Y/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__y_p`|Y/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__pass_succ_pct`|PASS SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__rush_succ_pct`|RUSH SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__blitz_epa_db`|BLITZ EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__4_th_go_pct`|4TH GO % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__rz_pass_pct`|RZ PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__zone_run_pct`|ZONE RUN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__proe`|PROE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__ed_pass_pct`|ED PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__2_l_run_pct`|2L RUN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__base_pass_pct`|BASE PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__8_box_run_pct`|8+ BOX RUN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__pa_pct`|PA % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__uc_pct`|UC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__mot_pct`|MOT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__ds_mot_pct`|DS MOT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__nh_pct`|NH % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__rpo_pct`|RPO % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__11_p_pct`|11P % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__12_p_pct`|12P % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__13_p_pct`|13P % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__21_p_pct`|21P % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__oz_pct`|OZ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__iz_pct`|IZ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__gap_pct`|GAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scheme_tendencies__sneak_pct`|SNEAK % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fantasy__qb_fp_g`|QB FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__rb_fp_g`|RB FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__wr_fp_g`|WR FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__te_fp_g`|TE FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__qb_xfp_g`|QB XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__rb_xfp_g`|RB XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__wr_xfp_g`|WR XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__te_xfp_g`|TE XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`target_share__wr_tgt_pct`|WR TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`target_share__rb_tgt_pct`|RB TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`target_share__te_tgt_pct`|TE TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`target_share__wide_tgt_pct`|WIDE TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`target_share__slot_tgt_pct`|SLOT TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`target_share__inline_tgt_pct`|INLINE TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`target_share__back_tgt_pct`|BACK TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`route_running__rr_db`|RR/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`route_running__wr_rr_db`|WR RR/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`route_running__te_rr_db`|TE RR/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`route_running__rb_rr_db`|RB RR/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`route_running__wide_rr_db`|WIDE RR/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`route_running__slot_rr_db`|SLOT RR/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`route_running__inline_rr_db`|INLINE RR/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`route_running__back_rr_db`|BACK RR/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### rb-wr-efficiency.csv

Table `rb_wr_efficiency`; 835573 bytes; modified 2026-10-21T02:27:35.877857+00:00; SHA256 `89abc3e4911694bc5aa6ce08c251f5ce506ce8868171315fbca000b352a4caef`; imported 2026-10-21T03:16:22.605663+00:00; header rows 2; raw rows 3202; valid weekly rows 3200; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`fp__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:44, 2:44, 3:42, 4:44, 5:45, 6:37, 7:30, 8:40, 9:29, 10:28, 11:35, 12:34, 13:37, 14:36, 15:25, 16:34, 17:37, 18:47|none|
|2022|1:36, 2:28, 3:36, 4:34, 5:35, 6:30, 7:34, 8:35, 9:24, 10:32, 11:28, 12:37, 13:34, 14:33, 15:34, 16:30, 17:28, 18:27|none|
|2023|1:29, 2:45, 3:34, 4:29, 5:28, 6:31, 7:30, 8:35, 9:21, 10:33, 11:33, 12:38, 13:31, 14:32, 15:32, 16:34, 17:35, 18:31|none|
|2024|1:36, 2:36, 3:37, 4:43, 5:31, 6:36, 7:33, 8:41, 9:37, 10:29, 11:35, 12:25, 13:38, 14:35, 15:36, 16:37, 17:37, 18:33|none|
|2025|1:29, 2:38, 3:30, 4:38, 5:34, 6:28, 7:30, 8:29, 9:33, 10:31, 11:29, 12:29, 13:33, 14:29, 15:32, 16:37, 17:27, 18:23|none|
|2026|1:30, 2:23, 3:30, 4:40, 5:31, 6:28|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__tch_pct`|TCH % (header inference; vendor definition unverified)|text|100.00|unknown|unverified text/units; excluded from numeric model features|
|`total__snaps`|SNAPS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total__snap_pct`|Snap % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total__touch`|TOUCH (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total__yfs`|YFS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total__xtd`|XTD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total__mtf`|MTF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`total__yaco`|YACO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__att_pct`|ATT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__xtd`|XTD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yaco`|YACO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__mtf`|MTF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__exp`|EXP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__xtd`|XTD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ay`|AY (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yac`|YAC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yaco`|YACO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__mtf`|MTF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__exp`|EXP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__ypc`|YPC (header inference; vendor definition unverified)|numeric|47.22|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__yaco_att`|YACO/ATT (header inference; vendor definition unverified)|numeric|47.22|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__mtf_att`|MTF/ATT (header inference; vendor definition unverified)|numeric|47.22|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_run_pct`|EXP RUN % (header inference; vendor definition unverified)|numeric|47.81|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__run_succ_pct`|RUN SUCC % (header inference; vendor definition unverified)|numeric|47.22|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.03|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__ypt`|YPT (header inference; vendor definition unverified)|numeric|1.84|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__yac_rec`|YAC/REC (header inference; vendor definition unverified)|numeric|2.53|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__yaco_rec`|YACO/REC (header inference; vendor definition unverified)|numeric|2.53|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__mtf_rec`|MTF/REC (header inference; vendor definition unverified)|numeric|2.53|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_rec_pct`|EXP REC % (header inference; vendor definition unverified)|numeric|3.75|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__rec_succ_pct`|REC SUCC % (header inference; vendor definition unverified)|numeric|1.84|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__yfs_touch`|YFS/TOUCH (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__mtf_touch`|MTF/TOUCH (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__yaco_touch`|YACO/TOUCH (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__exp_play_pct`|EXP PLAY % (header inference; vendor definition unverified)|numeric|0.12|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__ru_yds_g`|RuYDS/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__rec_yds_g`|RecYDS/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__yfs_g`|YFS/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__fp_sn`|FP/SN (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`efficiency__epa_sn`|EPA/SN (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_ru`|EPA/RU (header inference; vendor definition unverified)|numeric|47.22|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_tgt`|EPA/TGT (header inference; vendor definition unverified)|numeric|1.84|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`efficiency__epa_rte`|EPA/RTE (header inference; vendor definition unverified)|numeric|0.03|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp`|XFP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp_g`|XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__diff`|DIFF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp_pct`|XFP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-alignment.csv

Table `receiving_alignment`; 594612 bytes; modified 2026-10-21T02:17:51.820577+00:00; SHA256 `da51abced5f3535a5acbe932317500b7943430fef63e5c3414d8a18889429cf8`; imported 2026-10-21T03:16:23.088661+00:00; header rows 2; raw rows 3202; valid weekly rows 3200; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`backfield__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:50, 2:34, 3:45, 4:47, 5:43, 6:40, 7:33, 8:36, 9:37, 10:38, 11:33, 12:36, 13:40, 14:46, 15:42, 16:45, 17:40, 18:41|none|
|2022|1:43, 2:42, 3:42, 4:33, 5:36, 6:38, 7:29, 8:26, 9:28, 10:36, 11:18, 12:38, 13:35, 14:43, 15:31, 16:42, 17:24, 18:33|none|
|2023|1:43, 2:40, 3:48, 4:32, 5:35, 6:35, 7:25, 8:44, 9:32, 10:34, 11:33, 12:40, 13:23, 14:43, 15:31, 16:45, 17:29, 18:18|none|
|2024|1:23, 2:22, 3:39, 4:27, 5:40, 6:21, 7:25, 8:26, 9:34, 10:33, 11:28, 12:30, 13:45, 14:30, 15:36, 16:38, 17:31, 18:33|none|
|2025|1:41, 2:39, 3:28, 4:24, 5:25, 6:20, 7:34, 8:15, 9:34, 10:24, 11:22, 12:28, 13:23, 14:26, 15:24, 16:33, 17:23, 18:20|none|
|2026|1:22, 2:27, 3:36, 4:30, 5:31, 6:37|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__wide_rte_pct`|WIDE RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__tm_rte_pct`|TM RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__slot_rte_pct`|SLOT RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__tm_rte_pct`|TM RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__inline_rte_pct`|INLINE RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__tm_rte_pct`|TM RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__back_rte_pct`|BACK RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__tm_rte_pct`|TM RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-basic.csv

Table `receiving_basic`; 179374 bytes; modified 2026-10-21T02:16:37.405420+00:00; SHA256 `468f08c08201ecae9ef72cbb5eff2d2d1dcf4598cd3c29180be1c5fb9784985a`; imported 2026-10-21T03:16:23.480506+00:00; header rows 2; raw rows 1502; valid weekly rows 1500; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`fp__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:19, 2:20, 3:22, 4:16, 5:21, 6:18, 7:11, 8:15, 9:13, 10:13, 11:15, 12:19, 13:17, 14:16, 15:13, 16:17, 17:11, 18:23|none|
|2022|1:14, 2:17, 3:23, 4:19, 5:18, 6:12, 7:15, 8:14, 9:12, 10:14, 11:13, 12:16, 13:19, 14:12, 15:17, 16:20, 17:12, 18:13|none|
|2023|1:10, 2:18, 3:20, 4:11, 5:16, 6:16, 7:13, 8:21, 9:11, 10:18, 11:12, 12:21, 13:16, 14:14, 15:13, 16:20, 17:18, 18:12|none|
|2024|1:11, 2:19, 3:18, 4:12, 5:20, 6:10, 7:14, 8:20, 9:19, 10:11, 11:17, 12:15, 13:19, 14:19, 15:14, 16:15, 17:21, 18:15|none|
|2025|1:11, 2:16, 3:11, 4:11, 5:19, 6:13, 7:19, 8:13, 9:16, 10:14, 11:11, 12:12, 13:14, 14:18, 15:13, 16:15, 17:16, 18:11|none|
|2026|1:11, 2:18, 3:18, 4:21, 5:15, 6:16|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tm_yds_pct`|TM YDS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypr`|YPR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypt`|YPT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__cr_pct`|CR % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tm_td_pct`|TM TD % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__i10`|i10 (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__i20_tgt`|i20 TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__fum`|FUM (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-separation-by-alignment.csv

Table `receiving_separation_by_alignment`; 600022 bytes; modified 2026-10-21T02:18:47.761148+00:00; SHA256 `c02a069ba0d6ef0e7afd8569d0885e3f7bcc2bec34dd79b2f981874bdde5db02`; imported 2026-10-21T03:16:23.660507+00:00; header rows 2; raw rows 2902; valid weekly rows 2900; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`backfield__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|none|1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18|
|2022|1:49, 2:51, 3:48, 4:38, 5:42, 6:44, 7:35, 8:32, 9:32, 10:38, 11:26, 12:46, 13:43, 14:52, 15:35, 16:49, 17:32, 18:37|none|
|2023|1:52, 2:47, 3:53, 4:36, 5:35, 6:46, 7:26, 8:51, 9:36, 10:36, 11:42, 12:45, 13:24, 14:49, 15:39, 16:53, 17:37, 18:24|none|
|2024|1:28, 2:24, 3:42, 4:34, 5:49, 6:27, 7:31, 8:31, 9:39, 10:35, 11:33, 12:36, 13:49, 14:35, 15:40, 16:44, 17:41, 18:38|none|
|2025|1:50, 2:47, 3:34, 4:31, 5:29, 6:25, 7:39, 8:20, 9:35, 10:28, 11:27, 12:32, 13:25, 14:30, 15:28, 16:38, 17:28, 18:27|none|
|2026|1:25, 2:31, 3:40, 4:35, 5:36, 6:44|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`splits__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_ms`|SEP MS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__1_rate`|+1 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__2_rate`|+2 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__3_rate`|+3 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__neg_rate`|Neg Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ay`|AY (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`wide__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slot__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`inline__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-separation-by-breaks.csv

Table `receiving_separation_by_breaks`; 617856 bytes; modified 2026-10-21T02:20:01.703883+00:00; SHA256 `a8362fbbae6f300bb9188b6147c84e17148110eab916e644282254adc0d01836`; imported 2026-10-21T03:16:24.033508+00:00; header rows 2; raw rows 2502; valid weekly rows 2500; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`backfield__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|none|1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18|
|2022|1:45, 2:40, 3:40, 4:32, 5:37, 6:39, 7:31, 8:26, 9:29, 10:37, 11:19, 12:41, 13:34, 14:46, 15:31, 16:42, 17:26, 18:31|none|
|2023|1:48, 2:38, 3:48, 4:32, 5:34, 6:37, 7:21, 8:46, 9:32, 10:34, 11:37, 12:41, 13:22, 14:41, 15:30, 16:45, 17:30, 18:20|none|
|2024|1:24, 2:22, 3:33, 4:28, 5:39, 6:23, 7:28, 8:26, 9:33, 10:32, 11:28, 12:34, 13:44, 14:30, 15:34, 16:40, 17:34, 18:35|none|
|2025|1:42, 2:40, 3:27, 4:27, 5:25, 6:21, 7:32, 8:15, 9:33, 10:24, 11:24, 12:29, 13:23, 14:23, 15:24, 16:35, 17:23, 18:21|none|
|2026|1:20, 2:28, 3:34, 4:33, 5:31, 6:37|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`splits__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_ms`|SEP MS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__1_rate`|+1 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__2_rate`|+2 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__3_rate`|+3 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__neg_rate`|Neg Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ay`|AY (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`horizontally_breaking__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`horizontally_breaking__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`horizontally_breaking__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`horizontally_breaking__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`horizontally_breaking__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`horizontally_breaking__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`vertically_breaking__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`vertically_breaking__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`vertically_breaking__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`vertically_breaking__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`vertically_breaking__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`vertically_breaking__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`static__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`static__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`static__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`static__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`static__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`static__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`shallow_underneath__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`shallow_underneath__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`shallow_underneath__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`shallow_underneath__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`shallow_underneath__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`shallow_underneath__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-separation-by-coverage.csv

Table `receiving_separation_by_coverage`; 605194 bytes; modified 2026-10-21T02:20:36.450651+00:00; SHA256 `8b8ee50d40a424329c8c89cc40da7c10b41d02fbd81422e13641c152fd1de7e1`; imported 2026-10-21T03:16:24.435505+00:00; header rows 2; raw rows 2602; valid weekly rows 2600; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`cover_6__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|none|1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18|
|2022|1:47, 2:42, 3:44, 4:33, 5:39, 6:41, 7:31, 8:28, 9:29, 10:37, 11:20, 12:43, 13:36, 14:49, 15:33, 16:42, 17:28, 18:34|none|
|2023|1:51, 2:39, 3:50, 4:34, 5:34, 6:40, 7:22, 8:48, 9:33, 10:34, 11:38, 12:43, 13:22, 14:45, 15:33, 16:47, 17:33, 18:20|none|
|2024|1:25, 2:22, 3:37, 4:30, 5:41, 6:24, 7:28, 8:27, 9:33, 10:34, 11:29, 12:34, 13:45, 14:31, 15:38, 16:43, 17:36, 18:35|none|
|2025|1:44, 2:40, 3:28, 4:27, 5:26, 6:21, 7:33, 8:15, 9:33, 10:25, 11:25, 12:29, 13:24, 14:23, 15:24, 16:36, 17:23, 18:21|none|
|2026|1:21, 2:28, 3:38, 4:33, 5:31, 6:38|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`splits__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_ms`|SEP MS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__1_rate`|+1 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__2_rate`|+2 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__3_rate`|+3 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__neg_rate`|Neg Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ay`|AY (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_2__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_2__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_2__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_3__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_3__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_3__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_4__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_4__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_4__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_6__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_6__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_6__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`cover_6__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-separation-by-role.csv

Table `receiving_separation_by_role`; 698311 bytes; modified 2026-10-21T02:21:03.270620+00:00; SHA256 `341080714cd300693e69a8b85b333dfbf5b9c8854256f8187633f5c14297b470`; imported 2026-10-21T03:16:24.867670+00:00; header rows 2; raw rows 2902; valid weekly rows 2900; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`condensed_wide_reduced_split__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|none|1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18|
|2022|1:50, 2:49, 3:49, 4:39, 5:45, 6:41, 7:33, 8:35, 9:32, 10:34, 11:28, 12:47, 13:42, 14:46, 15:36, 16:45, 17:32, 18:37|none|
|2023|1:48, 2:45, 3:53, 4:36, 5:36, 6:45, 7:25, 8:48, 9:32, 10:39, 11:44, 12:49, 13:25, 14:45, 15:40, 16:52, 17:36, 18:25|none|
|2024|1:28, 2:34, 3:40, 4:34, 5:44, 6:35, 7:29, 8:33, 9:35, 10:34, 11:33, 12:37, 13:45, 14:35, 15:38, 16:39, 17:41, 18:43|none|
|2025|1:46, 2:44, 3:37, 4:32, 5:31, 6:27, 7:42, 8:23, 9:32, 10:25, 11:35, 12:31, 13:32, 14:31, 15:27, 16:37, 17:32, 18:29|none|
|2026|1:30, 2:31, 3:36, 4:33, 5:39, 6:38|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`splits__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_ms`|SEP MS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__1_rate`|+1 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__2_rate`|+2 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__3_rate`|+3 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__neg_rate`|Neg Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ay`|AY (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`x_wide_on_the_line__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`x_wide_on_the_line__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`x_wide_on_the_line__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`x_wide_on_the_line__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`x_wide_on_the_line__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`x_wide_on_the_line__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`z_wide_off_the_line__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`z_wide_off_the_line__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`z_wide_off_the_line__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`z_wide_off_the_line__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`z_wide_off_the_line__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`z_wide_off_the_line__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`f_slot__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`f_slot__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`f_slot__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`f_slot__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`f_slot__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`f_slot__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`condensed_wide_reduced_split__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`condensed_wide_reduced_split__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`condensed_wide_reduced_split__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`condensed_wide_reduced_split__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`condensed_wide_reduced_split__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`condensed_wide_reduced_split__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`condensed_wide_reduced_split__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-separation-by-routes.csv

Table `receiving_separation_by_routes`; 622979 bytes; modified 2026-10-21T02:19:26.195785+00:00; SHA256 `ba4b099af7d891dba68540004f4e0622d001d1b23b515e89e96273e57259b206`; imported 2026-10-21T03:16:25.307143+00:00; header rows 2; raw rows 1602; valid weekly rows 1600; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`backfield__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|none|1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18|
|2022|1:33, 2:29, 3:30, 4:20, 5:27, 6:25, 7:24, 8:17, 9:22, 10:25, 11:10, 12:24, 13:23, 14:31, 15:24, 16:24, 17:17, 18:19|none|
|2023|1:23, 2:27, 3:28, 4:22, 5:24, 6:22, 7:15, 8:26, 9:22, 10:23, 11:19, 12:24, 13:15, 14:26, 15:16, 16:29, 17:18, 18:12|none|
|2024|1:13, 2:16, 3:22, 4:19, 5:26, 6:12, 7:21, 8:13, 9:25, 10:18, 11:17, 12:18, 13:35, 14:19, 15:25, 16:20, 17:21, 18:26|none|
|2025|1:27, 2:29, 3:15, 4:14, 5:17, 6:14, 7:24, 8:7, 9:19, 10:13, 11:13, 12:24, 13:12, 14:15, 15:15, 16:17, 17:16, 18:13|none|
|2026|1:13, 2:14, 3:23, 4:24, 5:17, 6:24|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`splits__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__sep_ms`|SEP MS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__1_rate`|+1 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__2_rate`|+2 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__3_rate`|+3 Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__neg_rate`|Neg Rate (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__ay`|AY (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slant__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slant__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slant__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slant__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slant__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slant__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`slant__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`out__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`out__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`out__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`out__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`out__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`out__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`out__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`in_dig__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`in_dig__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`in_dig__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`in_dig__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`in_dig__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`in_dig__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`in_dig__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`hitch__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`hitch__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`hitch__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`hitch__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`hitch__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`hitch__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`hitch__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`comeback__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`comeback__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`comeback__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`comeback__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`comeback__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`comeback__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`comeback__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`corner__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`corner__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`corner__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`corner__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`corner__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`corner__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`corner__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`post__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`post__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`post__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`post__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`post__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`post__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`post__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`go__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`go__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`go__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`go__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`go__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`go__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`go__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`crossers__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`crossers__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`crossers__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`crossers__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`crossers__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`crossers__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`crossers__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`screens__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`screens__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`screens__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`screens__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`screens__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`screens__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`screens__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`flat__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`flat__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`flat__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`flat__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`flat__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`flat__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`flat__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__sep_score`|SEP SCORE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__ador`|ADOR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__win_rate`|WIN RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`backfield__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-situation.csv

Table `receiving_situation`; 272368 bytes; modified 2026-10-21T02:18:21.820780+00:00; SHA256 `43676083b9c3c7d4343340f7436ae50100ad013500d3c971e526ded306bd8617`; imported 2026-10-21T03:16:25.774533+00:00; header rows 2; raw rows 1702; valid weekly rows 1700; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`two_high__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:33, 2:18, 3:27, 4:27, 5:21, 6:25, 7:14, 8:22, 9:29, 10:17, 11:18, 12:17, 13:28, 14:31, 15:20, 16:28, 17:17, 18:21|none|
|2022|1:28, 2:24, 3:26, 4:16, 5:25, 6:23, 7:23, 8:16, 9:16, 10:19, 11:9, 12:16, 13:21, 14:24, 15:20, 16:22, 17:12, 18:15|none|
|2023|1:15, 2:22, 3:24, 4:19, 5:20, 6:20, 7:12, 8:23, 9:17, 10:19, 11:9, 12:21, 13:11, 14:22, 15:11, 16:23, 17:11, 18:11|none|
|2024|1:11, 2:12, 3:20, 4:15, 5:21, 6:9, 7:13, 8:12, 9:21, 10:15, 11:15, 12:12, 13:30, 14:13, 15:15, 16:16, 17:15, 18:16|none|
|2025|1:21, 2:23, 3:11, 4:14, 5:15, 6:12, 7:22, 8:5, 9:16, 10:11, 11:12, 12:20, 13:10, 14:11, 15:13, 16:10, 17:8, 18:10|none|
|2026|1:8, 2:12, 3:21, 4:21, 5:13, 6:22|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`splits__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`overall__fp_rr`|FP/RR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`man__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man__fp_rr`|FP/RR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`zone__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone__fp_rr`|FP/RR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`single_high__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`single_high__fp_rr`|FP/RR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`two_high__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`two_high__fp_rr`|FP/RR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`two_high__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### receiving-stats.csv

Table `receiving_stats`; 468191 bytes; modified 2026-10-21T02:17:21.856091+00:00; SHA256 `3f6b623c0244742b6f64654f6c485b389dd0a57104abb0e5b2d86f4115852f28`; imported 2026-10-21T03:16:25.965534+00:00; header rows 2; raw rows 1502; valid weekly rows 1500; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`fp__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:19, 2:20, 3:22, 4:16, 5:21, 6:18, 7:11, 8:15, 9:13, 10:13, 11:15, 12:19, 13:17, 14:16, 15:13, 16:17, 17:11, 18:23|none|
|2022|1:14, 2:17, 3:23, 4:19, 5:18, 6:12, 7:15, 8:14, 9:12, 10:14, 11:13, 12:16, 13:19, 14:12, 15:17, 16:20, 17:12, 18:13|none|
|2023|1:10, 2:18, 3:20, 4:11, 5:16, 6:16, 7:13, 8:21, 9:11, 10:18, 11:12, 12:21, 13:16, 14:14, 15:13, 16:20, 17:18, 18:12|none|
|2024|1:11, 2:19, 3:18, 4:12, 5:20, 6:10, 7:14, 8:20, 9:19, 10:11, 11:17, 12:15, 13:19, 14:19, 15:14, 16:15, 17:21, 18:15|none|
|2025|1:11, 2:16, 3:11, 4:11, 5:19, 6:13, 7:19, 8:13, 9:16, 10:14, 11:11, 12:12, 13:14, 14:18, 15:13, 16:15, 17:16, 18:11|none|
|2026|1:11, 2:18, 3:18, 4:21, 5:15, 6:16|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`splits__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rte`|RTE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rte_pct`|RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yprr`|YPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tprr`|TPRR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__a_dot`|aDOT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ay`|AY (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ay_share`|AY Share (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tm_yds_pct`|TM YDS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypt`|YPT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypr`|YPR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__cr_pct`|CR % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yac`|YAC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yac_rec`|YAC/REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yaco`|YACO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__yaco_rec`|YACO/REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__xtd`|XTD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__fum`|FUM (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tm_td_pct`|TM TD % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__i20_tgt`|i20 TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__eztgt`|EZTGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__eztd`|EZTD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__1_d_rr`|1D/RR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__rate`|RATE (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`advanced__1_read`|1READ (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__1_read_pct`|1READ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__design`|DESIGN (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__design_pct`|DESIGN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ctgt`|CTGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ctgt_pct`|CTGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__deep`|DEEP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__drp`|DRP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__drp_pct`|DRP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ct`|CT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__cc`|CC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__cc_pct`|CC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__hero`|HERO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__mtf`|MTF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__mtf_rec`|MTF/REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__threat_pct`|THREAT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__yptoe`|YPTOE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__epa_tgt`|EPA/TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`alignment__wide_rte_pct`|WIDE RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`alignment__slot_rte_pct`|SLOT RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`alignment__inline_rte_pct`|INLINE RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`alignment__back_rte_pct`|BACK RTE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp`|XFP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp_g`|XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__diff`|DIFF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_rr`|FP/RR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp_rr`|XFP/RR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__rec_xfp`|RecXFP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### rushing-basic.csv

Table `rushing_basic`; 289411 bytes; modified 2026-10-21T02:14:47.435292+00:00; SHA256 `7d06ee729c776dc463f9987c9733b1d01727793e5b7b1856f43d254720391805`; imported 2026-10-21T03:16:26.316436+00:00; header rows 2; raw rows 1602; valid weekly rows 1600; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`fp__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:17, 2:14, 3:15, 4:22, 5:16, 6:17, 7:12, 8:15, 9:17, 10:12, 11:14, 12:16, 13:16, 14:14, 15:17, 16:15, 17:15, 18:18|none|
|2022|1:12, 2:15, 3:18, 4:22, 5:19, 6:16, 7:19, 8:19, 9:11, 10:18, 11:15, 12:19, 13:18, 14:15, 15:22, 16:21, 17:19, 18:16|none|
|2023|1:13, 2:17, 3:19, 4:16, 5:15, 6:12, 7:14, 8:15, 9:13, 10:21, 11:18, 12:19, 13:13, 14:14, 15:18, 16:15, 17:20, 18:18|none|
|2024|1:16, 2:23, 3:18, 4:19, 5:17, 6:19, 7:18, 8:19, 9:21, 10:14, 11:16, 12:10, 13:24, 14:14, 15:18, 16:16, 17:17, 18:17|none|
|2025|1:12, 2:17, 3:16, 4:24, 5:14, 6:13, 7:14, 8:15, 9:14, 10:21, 11:18, 12:16, 13:20, 14:19, 15:19, 16:20, 17:20, 18:16|none|
|2026|1:15, 2:16, 3:17, 4:16, 5:17, 6:9|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__att_pct`|ATT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ypc`|YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__fum`|FUM (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`gain_rates__1_pct`|1+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`gain_rates__3_pct`|3+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`gain_rates__5_pct`|5+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`gain_rates__10_pct`|10+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`gain_rates__15_pct`|15+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`gain_rates__20_pct`|20+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`gain_rates__30_pct`|30+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__i5`|i5 (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__i5_pct`|i5 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__i10`|i10 (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__i10_pct`|i10 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__i20`|i20 (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`red_zone__i20_pct`|i20 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scrambles__scrm`|SCRM (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scrambles__scrm_yds`|SCRM YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`scrambles__scrm_td`|SCRM TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tgt_pct`|TGT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec_yds`|REC YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tm_yds_pct`|TM YDS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypr`|YPR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__ypt`|YPT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__cr_pct`|CR % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec_td`|REC TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__tm_td_pct`|TM TD % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__i10_tgt`|i10 TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__i20_tgt`|i20 TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`receiving__rec_fum`|REC FUM (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fp__wo`|WO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### rushing-stats.csv

Table `rushing_stats`; 383279 bytes; modified 2026-10-21T02:15:19.725810+00:00; SHA256 `0422b733a02094a7fc0e3982a4b7941d4b927a3959ab93ffa1cb5f6dc2ae41b3`; imported 2026-10-21T03:16:26.571053+00:00; header rows 2; raw rows 1602; valid weekly rows 1600; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`player_details__name`, team=`player_details__team`, position=`player_details__pos`, native_id=`fp__player_id`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:17, 2:14, 3:15, 4:22, 5:16, 6:17, 7:12, 8:15, 9:17, 10:12, 11:14, 12:16, 13:16, 14:14, 15:17, 16:15, 17:15, 18:18|none|
|2022|1:12, 2:15, 3:18, 4:22, 5:19, 6:16, 7:19, 8:19, 9:11, 10:18, 11:15, 12:19, 13:18, 14:15, 15:22, 16:21, 17:19, 18:16|none|
|2023|1:13, 2:17, 3:19, 4:16, 5:15, 6:12, 7:14, 8:15, 9:13, 10:21, 11:18, 12:19, 13:13, 14:14, 15:18, 16:15, 17:20, 18:18|none|
|2024|1:16, 2:23, 3:18, 4:19, 5:17, 6:19, 7:18, 8:19, 9:21, 10:14, 11:16, 12:10, 13:24, 14:14, 15:18, 16:16, 17:17, 18:17|none|
|2025|1:12, 2:17, 3:16, 4:24, 5:14, 6:13, 7:14, 8:15, 9:14, 10:21, 11:18, 12:16, 13:20, 14:19, 15:19, 16:20, 17:20, 18:16|none|
|2026|1:15, 2:16, 3:17, 4:16, 5:17, 6:9|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`player_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__team`|Team (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`player_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__att_pct`|ATT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__snap_pct`|SNAP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__att`|ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__dcs_pct`|DCS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__sneak_pct`|SNEAK % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__ypc`|YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__xtd`|XTD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__fum`|FUM (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`rushing__1_d`|1D (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__exp_run_pct`|EXP RUN % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__exp_yds`|EXP YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__exp_yds_pct`|EXP YDS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__i5_pct`|i5 % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__td_rate`|TD RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__stuff_pct`|STUFF % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ryoe`|RYOE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ryoe_att`|RYOE/ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__ybc_att`|YBC/ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__hit_pct`|HIT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__yaco_att`|YACO/ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__yaco_pct`|YACO % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__mtf`|MTF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__mtf_a`|MTF/A (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__epa_a`|EPA/A (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`advanced__epa`|EPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone_concept__zone_att`|ZONE ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone_concept__zone_att_pct`|ZONE ATT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone_concept__zone_yds`|ZONE YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone_concept__zone_td`|ZONE TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone_concept__zone_ypc`|ZONE YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`zone_concept__zone_succ_pct`|ZONE SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_gap_concept__man_att`|MAN ATT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_gap_concept__man_att_pct`|MAN ATT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_gap_concept__man_yds`|MAN YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_gap_concept__man_td`|MAN TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_gap_concept__man_ypc`|MAN YPC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`man_gap_concept__man_succ_pct`|MAN SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fp__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp`|XFP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__fp_g`|FP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__xfp_g`|XFP/G (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__diff`|DIFF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fp__player_id`|player_id (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|

### shadow-index.csv

Table `shadow_index`; 5783570 bytes; modified 2026-10-21T02:25:25.199785+00:00; SHA256 `7b0c97a259ce5404a5ceb77227b2acf1a987868704a23a228c978818cc38a2b1`; imported 2026-10-21T03:16:27.487109+00:00; header rows 2; raw rows 50002; valid weekly rows 50000; malformed 0; calendar/summary exclusions 2; selector conflicts 47122.

Selected keys: season=`matchup__sea`, week=`matchup__wk`, name=`matchup__receiver`, team=`matchup__off`, position=`matchup__pos`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:821, 2:725, 3:670, 4:617, 5:573, 6:531, 7:461, 8:580, 9:526, 10:526, 11:535, 12:524, 13:490, 14:522, 15:568, 16:565, 17:568, 18:579|none|
|2022|1:778, 2:688, 3:606, 4:550, 5:514, 6:473, 7:456, 8:491, 9:441, 10:431, 11:454, 12:562, 13:506, 14:436, 15:508, 16:507, 17:509, 18:543|none|
|2023|1:749, 2:682, 3:593, 4:543, 5:458, 6:516, 7:419, 8:533, 9:501, 10:491, 11:475, 12:514, 13:413, 14:501, 15:507, 16:539, 17:516, 18:513|none|
|2024|1:666, 2:595, 3:538, 4:513, 5:482, 6:451, 7:464, 8:506, 9:481, 10:423, 11:494, 12:421, 13:527, 14:415, 15:501, 16:533, 17:489, 18:485|none|
|2025|1:725, 2:666, 3:520, 4:524, 5:457, 6:462, 7:486, 8:399, 9:443, 10:430, 11:459, 12:462, 13:477, 14:407, 15:497, 16:512, 17:456, 18:459|none|
|2026|1:484, 2:473, 3:511, 4:499, 5:452, 6:459|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`season`|Season (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`matchup`|# (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`matchup__sea`|SEA (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`matchup__wk`|WK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`matchup__receiver`|Receiver (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`matchup__off`|OFF (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`matchup__pos`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`matchup__defender`|Defender (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`matchup__def`|DEF (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`matchup__pos__2`|POS (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`pre_snap_alignment__lwr`|LWR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pre_snap_alignment__rwr`|RWR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pre_snap_alignment__slot`|SLOT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pre_snap_alignment__rtes`|RTES (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pre_snap_alignment__tot`|TOT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`pre_snap_alignment__shadow_pct`|SHADOW % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__tgt`|TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__rec`|REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__yds`|YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__td`|TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`production__fp`|FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`production__fp_t`|FP/T (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`primary_coverage__pri_tgt`|PRI TGT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`primary_coverage__pri_rec`|PRI REC (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`primary_coverage__pri_yds`|PRI YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`primary_coverage__pri_td`|PRI TD (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`primary_coverage__pri_int`|PRI INT (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`primary_coverage__pri_rate`|PRI RATE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`primary_coverage__pri_fp`|PRI FP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`primary_coverage__pri_fp_t`|PRI FP/T (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`primary_coverage__step_pct`|STEP+ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`primary_coverage__blanketed_pct`|BLANKETED % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|

### team-defense.csv

Table `team_defense`; 1430825 bytes; modified 2026-10-21T02:21:48.538503+00:00; SHA256 `d8559a935ddc72ec3abc05c06b590815918c37eca74e936baa21572fd66e705f`; imported 2026-10-21T03:16:30.569185+00:00; header rows 2; raw rows 2302; valid weekly rows 2300; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`team_details__name`, team=`None`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:26, 2:26, 3:26, 4:26, 5:26, 6:23, 7:20, 8:23, 9:24, 10:21, 11:23, 12:23, 13:22, 14:22, 15:25, 16:25, 17:25, 18:25|none|
|2022|1:26, 2:26, 3:26, 4:26, 5:26, 6:22, 7:22, 8:23, 9:21, 10:21, 11:23, 12:25, 13:23, 14:20, 15:25, 16:25, 17:23, 18:25|none|
|2023|1:26, 2:26, 3:26, 4:26, 5:24, 6:24, 7:20, 8:25, 9:22, 10:22, 11:21, 12:25, 13:19, 14:24, 15:25, 16:25, 17:25, 18:25|none|
|2024|1:26, 2:26, 3:26, 4:26, 5:23, 6:22, 7:23, 8:25, 9:25, 10:22, 11:22, 12:19, 13:25, 14:20, 15:25, 16:25, 17:25, 18:25|none|
|2025|1:26, 2:26, 3:26, 4:26, 5:23, 6:24, 7:23, 8:20, 9:23, 10:22, 11:23, 12:22, 13:25, 14:22, 15:25, 16:25, 17:25, 18:25|none|
|2026|1:26, 2:26, 3:26, 4:26, 5:24, 6:22|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`team_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__play_pct`|PLAY % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__w_l_t`|W-L-T (header inference; vendor definition unverified)|text|0.00|unknown|unverified text/units; excluded from numeric model features|
|`record__win_pct`|WIN % (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`record__pf`|PF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__pa`|PA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__diff`|DIFF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__to`|TO +/- (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__plays`|PLAYS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__y_p`|Y/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__top`|TOP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__pace`|PACE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__avg_start`|AVG START (header inference; vendor definition unverified)|numeric|0.09|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__dr`|DR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__pts_dr`|PTS/DR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__scr_pct`|SCR % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__td_pct`|TD % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__fg_pct`|FG % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__punt_pct`|PUNT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa`|EPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa_ru`|EPA/RU (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`success__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`success__pass_succ_pct`|PASS SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`success__rush_succ_pct`|RUSH SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`explosive__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`explosive__pass_exp_pct`|PASS EXP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`explosive__rush_exp_pct`|RUSH EXP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`turnovers__to`|TO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`turnovers__to_dr_pct`|TO/DR % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__man_pct`|MAN % (header inference; vendor definition unverified)|numeric|17.61|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__zone_pct`|ZONE % (header inference; vendor definition unverified)|numeric|17.61|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__1_high_pct`|1-HIGH % (header inference; vendor definition unverified)|numeric|17.61|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`coverage__2_high_pct`|2-HIGH % (header inference; vendor definition unverified)|numeric|17.61|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__base_pct`|BASE % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__sub_pct`|SUB % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__press_pct`|PRESS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__sacks`|SACKS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__sack_pct`|SACK % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__blitz_pct`|BLITZ % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__box`|BOX (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__proe`|PROE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__pen`|PEN (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__pen_yds`|PEN YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__pen_epa`|PEN EPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fantasy__qb_fpg`|QB FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__rb_fpg`|RB FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__wr_fpg`|WR FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__te_fpg`|TE FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|

### team-offense.csv

Table `team_offense`; 1453083 bytes; modified 2026-10-21T02:21:23.805861+00:00; SHA256 `e09f26a2cdcc6b479ca3967dd9d60c825b6636e47aa2df6b4e446c0925cff845`; imported 2026-10-21T03:16:31.299187+00:00; header rows 2; raw rows 2302; valid weekly rows 2300; malformed 0; calendar/summary exclusions 2; selector conflicts 0.

Selected keys: season=`splits__season`, week=`splits__week`, name=`team_details__name`, team=`None`, position=`None`, native_id=`None`, game_id=`None`.

|Season|Weeks and row counts|Missing weeks|
|---|---|---|
|2021|1:26, 2:26, 3:26, 4:26, 5:26, 6:23, 7:20, 8:23, 9:24, 10:21, 11:23, 12:23, 13:22, 14:22, 15:25, 16:25, 17:25, 18:25|none|
|2022|1:26, 2:26, 3:26, 4:26, 5:26, 6:23, 7:22, 8:23, 9:21, 10:21, 11:23, 12:25, 13:23, 14:20, 15:25, 16:25, 17:23, 18:25|none|
|2023|1:26, 2:26, 3:26, 4:26, 5:24, 6:24, 7:20, 8:25, 9:22, 10:22, 11:21, 12:25, 13:19, 14:24, 15:25, 16:25, 17:25, 18:25|none|
|2024|1:26, 2:26, 3:26, 4:26, 5:23, 6:22, 7:23, 8:25, 9:25, 10:22, 11:22, 12:19, 13:25, 14:20, 15:25, 16:25, 17:25, 18:25|none|
|2025|1:26, 2:26, 3:26, 4:26, 5:23, 6:24, 7:23, 8:20, 9:23, 10:22, 11:23, 12:22, 13:25, 14:22, 15:25, 16:25, 17:25, 18:25|none|
|2026|1:26, 2:26, 3:26, 4:26, 5:24, 6:21|none|

|Qualified column|Header / inferred definition|Type|Missing %|As-of class|Treatment|
|---|---|---|---:|---|---|
|`team_details__rank`|Rank (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__name`|Name (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`team_details__g`|G (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__season`|SEASON (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__week`|WEEK (header inference; vendor definition unverified)|numeric|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__opp`|OPP (header inference; vendor definition unverified)|text|0.00|pregame-valid|identifier; never an outcome feature|
|`splits__play_pct`|PLAY % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__w_l_t`|W-L-T (header inference; vendor definition unverified)|text|0.00|unknown|unverified text/units; excluded from numeric model features|
|`record__win_pct`|WIN % (header inference; vendor definition unverified)|numeric|0.00|unknown|publication/units unverified; historical lag only where numeric and unambiguous|
|`record__pf`|PF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__pa`|PA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__diff`|DIFF (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`record__to`|TO +/- (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__plays`|PLAYS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__y_p`|Y/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__top`|TOP (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__pace`|PACE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`volume_pace__avg_start`|AVG START (header inference; vendor definition unverified)|numeric|0.09|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__dr`|DR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__pts_dr`|PTS/DR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__scr_pct`|SCR % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__td_pct`|TD % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__fg_pct`|FG % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`drives__punt_pct`|PUNT % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa`|EPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa_p`|EPA/P (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa_dr`|EPA/DR (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa_db`|EPA/DB (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`epa__epa_ru`|EPA/RU (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`success__succ_pct`|SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`success__pass_succ_pct`|PASS SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`success__rush_succ_pct`|RUSH SUCC % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`explosive__exp_pct`|EXP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`explosive__pass_exp_pct`|PASS EXP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`explosive__rush_exp_pct`|RUSH EXP % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`turnovers__to`|TO (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`turnovers__to_dr_pct`|TO/DR % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__pass_pct`|PASS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__proe`|PROE (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__motion_pct`|MOTION % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__pa_pct`|PA % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__press_pct`|PRESS % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__sacks`|SACKS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__sack_pct`|SACK % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__11_p_pct`|11P % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__11_p_epa_p`|11P EPA/P (header inference; vendor definition unverified)|numeric|0.13|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__12_p_pct`|12P % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__12_p_epa_p`|12P EPA/P (header inference; vendor definition unverified)|numeric|2.74|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__21_p_pct`|21P % (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`tendencies__21_p_epa_p`|21P EPA/P (header inference; vendor definition unverified)|numeric|41.22|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__pen`|PEN (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__pen_yds`|PEN YDS (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`penalties__pen_epa`|PEN EPA (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|completed-week observation; numeric values permitted only after strict lag|
|`fantasy__qb_fpg`|QB FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__rb_fpg`|RB FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__wr_fpg`|WR FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|
|`fantasy__te_fpg`|TE FPG (header inference; vendor definition unverified)|numeric|0.00|outcome-contaminated|excluded fantasy/market/ranking/projection field|

## Revisions

|Table|Status|Overlapping entity-weeks|Changed values|
|---|---|---:|---:|
|bell_cow_report|unchanged hash|6300|0|
|coach_records|unchanged hash|8570|0|
|cornerbacks|unchanged hash|4700|0|
|coverage_matrix|unchanged hash|2904|0|
|fantasy_points_allowed_qb|unchanged hash|2904|0|
|fantasy_points_allowed_rb|unchanged hash|2904|0|
|fantasy_points_allowed_te|unchanged hash|2888|0|
|fantasy_points_allowed_wr|unchanged hash|2904|0|
|injury_reports|unchanged hash|8342|0|
|lineup_combos_db|unchanged hash|10600|0|
|lineup_combos_front|unchanged hash|9700|0|
|lineup_combos_ol|unchanged hash|6759|0|
|lineup_combos_rb|unchanged hash|11867|0|
|lineup_combos_skill|unchanged hash|10500|0|
|lineup_combos_te|unchanged hash|13600|0|
|lineup_combos_wr|unchanged hash|12600|0|
|pace|unchanged hash|2904|0|
|passing_basic|unchanged hash|1200|0|
|passing_depth_of_target|unchanged hash|1800|0|
|passing_situation|unchanged hash|1000|0|
|passing_stats|unchanged hash|1200|0|
|playcaller_stats|unchanged hash|2600|0|
|rb_wr_efficiency|unchanged hash|3200|0|
|receiving_alignment|unchanged hash|3200|0|
|receiving_basic|unchanged hash|1500|0|
|receiving_separation_by_alignment|unchanged hash|2900|0|
|receiving_separation_by_breaks|unchanged hash|2500|0|
|receiving_separation_by_coverage|unchanged hash|2600|0|
|receiving_separation_by_role|unchanged hash|2900|0|
|receiving_separation_by_routes|unchanged hash|1600|0|
|receiving_situation|unchanged hash|1700|0|
|receiving_stats|unchanged hash|1500|0|
|rushing_basic|unchanged hash|1600|0|
|rushing_stats|unchanged hash|1600|0|
|shadow_index|unchanged hash|50000|0|
|team_defense|unchanged hash|2300|0|
|team_offense|unchanged hash|2300|0|

The private REVISION_LOG.json includes changed-value count and mean/max absolute revision by column. No comparable prior snapshot means revision frequency is unknown, not zero.

## Entity and timing limitations

Exact normalized full names must resolve to a unique GSIS ID and agree with the completed source-week team roster. Synthetic Defense labels are never assigned a player ID. Unmatched labels and all raw evidence remain private. Native vendor player IDs are retained as crosswalk evidence, never assumed to be GSIS. Conflicting entity/week rows are excluded from direct player joins; explicitly labelled team/split aggregates may be constructed from earlier observations. Missing history remains missing on the identical control and challenger sample. Current shadow assignments and injuries have no verified pregame timestamp and cannot enter target-week predictors.
