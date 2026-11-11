# FantasyPoints data audit, 2026-11-11

Read-only audit of the import behind the Week 10 forecast (`data/cache/fpds/amendment6/imports/caafc43aebec94ba0ca5`), branch claude/projections-w10 at eb32de32. Run by a subagent; the check scripts are in the session scratchpad (`dataaudit/q2.py`, `q2b.py`, `q3.py`, `q3b.py`). VERIFIED means a script showed it. LIKELY means code reading only.

## Defects, most severe first

1. **The historical base files are cut off at round row counts (VERIFIED).** 25 of 37 base CSVs hold an exact multiple of 100 rows (receiving 1,500, rushing 1,600, passing 1,200, team offense 2,300). For 2026 weeks 1 to 6 the receiving table has 11 to 21 players per week; weeks 7 to 9 have 209 to 301. The cut keeps the top-ranked player-games, so it selects on outcome. Those rows cover 11 to 21% of nflverse targets and 25 to 39% of carries in weeks 1 to 6. `lab/fpds_research/ingest.py:70` sets `possible_export_cap` and nothing stops on it.
2. **Team offense and team defense have no PIT, SEA, SF, TB, TEN or WAS rows from 2021 through 2026 week 6 (VERIFIED).** Same cut, alphabetical tail. Playcaller stats miss 1 to 6 teams per week in weeks 1 to 6.
3. **Share columns are blank for weeks 7 to 9 (VERIFIED).** The weekly export has no within-game share column and the adapter writes a blank (`lab/fpds_weekly_adapter.py:148`). 13 selected metrics (route, target, attempt, snap and play shares) stop at week 6.
4. **The position filter differs between drops (VERIFIED).** Week 7 and 8 receiving exports have no running backs (80 to 82% of targets). Week 9 has them. Rushing exports have no quarterbacks in weeks 7 to 9 (82 to 86% of carries).
5. **Week 7 has no points-allowed rows for RB, TE or WR (VERIFIED).** The files were not in the folder; `receiving-points-allowed.csv` is not a registered table. Week 8 TE lacks ATL.
6. **Week 8 has three different `fantasy-points-allowed-wr` files (VERIFIED).** The name cleaner strips "(1)" and "(2)", so all three map to one table and the last one converted wins. The other two are LIKELY split views.

## CSV usage

- Week 9 folder: 31 CSVs, all matched and imported. One .docx ignored.
- Not read: `receiving-points-allowed.csv` (weeks 7, 8), 118 loose `*Export*.csv` files in the Inbox root, the Inbox `Week 6` and `_held_by_claude` folders.
- Lineup-combination tables (db, front, rb, skill, te, wr) were not in the week 7, 8 or 9 folders. Their data stops at week 6.
- Only two forecasts use FantasyPoints columns in the frozen configuration: receptions and rushing yards. Receiving yards, anytime TD, first TD, passing yards, passing TDs, margin, total and winner run the control arm and read no FantasyPoints column.
- 1,561 imported columns, 441 selected (28%), with caps of 12 metrics per table and 20 feature columns.

## 2026 quality

| Check | Result |
|---|---|
| Rows per week, team tables | Match the schedule except defects 2 and 5 |
| Duplicate player-week keys | 0 in player stat tables |
| Players that fail to join | 0 in receiving, rushing, passing; 129 shadow-index rows; 180 coach-record rows |
| Impossible values | No negative counts; negatives only in yards and ratio columns |
| Bye, total or season rows treated as games | None |

## Cross-check with nflverse (2026 weeks 1 to 9)

nflverse is current: 136 of 136 completed games, all with play-by-play.

| Stat | Matched rows | Exact | Mean abs. difference |
|---|---|---|---|
| Targets | 657 of 819 (unmatched rows have 0 targets) | 84.2% | 0.18 |
| Receptions | 657 | 100% | 0 |
| Receiving yards | 657 | 99.4% | 0.02 |
| Rush attempts | 287 of 287 | 100% | 0 |
| Rush yards | 287 | 99.7% | 0.003 |

FantasyPoints targets are lower in 74 of 75 disagreements, LIKELY a charting definition (uncatchable balls). The values that are present are accurate. The problem is which rows are present.

## Week 10 early run versus gated run

The early Week 10 run (r002, 2026-11-10T22:43Z, gate bypassed) and the gated rerun (r003, 2026-11-11T04:03Z) used the same import, player features and labels. They differ in training rows: the 24-hour availability clock released Week 9 at 2026-11-11T01:15Z, so r002 trained on 4,940 rushing rows through Week 8 and r003 on 4,987 through Week 9.

Refitting each rushing-yards stack member twice under both conditions gave identical repeat fits, so the models are deterministic. Mean running back prediction without and with Week 9: linear 31.4 and 22.5, hist 46.0 and 45.2, xgboost 44.7 and 44.7, mlp 126.6 and 49.6. The mlp member's highest prediction was 380.0 yards without Week 9 and 105.1 with it.

r003 is the valid run. The mlp member has 785 input columns and about 5,000 training rows, and nothing bounds a member's prediction before stacking. The reason Week 9 matters this much is not verified.
