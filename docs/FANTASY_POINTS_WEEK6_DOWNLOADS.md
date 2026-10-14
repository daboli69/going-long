# Week 6 download audit and update receipt

Audited October 13 against the 136 inbox CSVs and 26 files in `Inbox/Week 6`.
This list concerns completed **2026 Week 5** and **2026 season totals through Week 5**. No historical-season downloads are requested.

## Original download gaps (before the second download batch)

| Dataset | Completed Week 5 only | 2026 season to date, through Week 5 | Reason |
|---|---|---|---|
| Routes Run by alignment | Needed | Needed | Existing dedicated alignment report stops at Week 4. New Separation by Routes is useful route-tree data, but does not replace wide/slot/inline/backfield route detail. |
| Receiving Advanced | Already supplied | Needed | `receiving-stats.csv` is one-game Week 5 evidence, not updated season totals. |
| Bell Cow | Already supplied | Needed | New bell-cow report covers one game; old season report reaches four games. |
| Rushing Advanced | Already supplied | Needed | New rushing-stats report covers one game; old season report reaches four games. |
| Efficiency / XFP | Already supplied | Needed | New RB/WR efficiency is one-game evidence; old season report reaches four games. |
| Run/Pass by situation | Needed | Needed | New team-offense report gives weekly overall tendencies; it does not replace the down, distance, score-state and field-position report. |
| Offensive Snaps | Optional weekly addition | Needed | Existing 2026 export reaches four games. |
| Receiving Man vs Zone / Single-high vs Two-high | Optional weekly addition | Needed | QB Passing Situation does not replace receiver coverage splits. |
| Separation by Alignment | Optional weekly addition | Needed | New routes and coverage separation reports are different breakdowns. |
| Separation by Breaks | Optional weekly addition | Needed | Existing 2026 break-type report reaches four games. |
| Separation by Routes | Already supplied | Needed | New route-tree separation is Week 5 only. |

## Refresh the upcoming Week 6 matchup reports

- QB Coverage Matchup.
- WR Coverage Matchup.
- Offensive Line vs Defensive Line / Line Matchups.

These are **forward-looking Week 6 matchups**, based on the latest completed-season evidence. Existing exports were captured with four-game inputs for the preceding slate. New OL lineup combinations describe line units; they are not the upcoming OL-versus-DL matchup report.

## Already supplied; no duplicate download requested

Updated coverage matrix; QB passing statistics, depth and situation; season-long team defense; QB/RB/TE/WR points allowed; receiving alignment allowed; pace; coaching records; playcaller variants; OL unit combinations; separation by coverage.

The WR `(3)/(4)/(5)` files share a signature and do not identify their alignment filter internally. They remain separate source variants; no overall/outside/slot assignment is guessed. The combined Receiving Points Allowed report explicitly labels OUTER and SLOT and can support those splits.

## Weekly folder convention

For `Week N`, updated season totals cover completed games through Week N−1, allowing team byes. Prior-week exports cover **only Week N−1**, kept separate from totals. Going forward, `(1)` declares that prior-week counterpart; files contradicting that declaration are held. The initial Week 6 batch has pre-existing collision suffixes on some season-long files, so its scopes are checked against game counts and the supplied operator clarification.

Keep 2021–2025 history unchanged. Do not download historical replacements to fill these current-season gaps.

## October 13 second-batch verification

145 CSVs now scanned, 35 in Week 6. 33 current-folder datasets accepted plus five verified prior-week raw captures retained separately (38 inputs total). Updated season totals now supplied for Routes/Alignment, Receiving Advanced, Bell Cow, Rushing Advanced, Efficiency/XFP, receiver coverage splits, Separation by Alignment and Separation by Routes. Role separation is also supplied and identified separately from route-tree separation. Earlier prior-week inputs overwritten by these totals are retained from checksum-verified local raw archives; weekly and cumulative counts are never added together.

Still not independently located as fresh complete exports: Offensive Snaps; Run/Pass by situation; Separation by Breaks; refreshed forward QB Coverage Matchup, WR Coverage Matchup and OL-vs-DL Line Matchups. Current team-offense, OL unit and role-separation files do not replace those distinct reports.

Two G=1 separation exports are held because they are outside the declared weekly `(1)` convention: `receiving-separation-by-alignment.csv` and `receiving-separation-by-coverage (2).csv`. Current season variants remain usable. Their observation week is not guessed from receipt time.

These are local ingestion results, not confirmation that hosted forecasts use the private data. Publication requires server storage and uploader configuration; no source CSV or numeric metric table is included in public build artifacts.
