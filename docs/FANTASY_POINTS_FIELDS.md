# Fantasy Points tables and field use classes

Generated from `config/fantasy_points_tables.json` and `scripts/fp_ingest/fields.py` (column names only, no licensed values).
Regenerate after changing either file. Classes are a boundary, not a score: nothing here feeds a model.

| Class | Meaning |
| --- | --- |
| DERIVED | role / deployment / opportunity share that can become a trend or matchup feature |
| RESEARCH | efficiency / skill / matchup measure: a hypothesis needing historical + chronological OOS testing, calibration, Champion comparison and human approval |
| CURRENT | descriptive count that can be shown as current evidence with its week |
| REDUNDANT | GOING already derives an equal or better value (nflverse / expected usage); cross-check only |
| DO_NOT_USE | export artifact (`Rank`) |
| UNREVIEWED | new column nobody has classified; never used until reviewed |

## Defensive coverage matrix (team) (`coverage_matrix`)

Team defence: man/zone, middle-of-field look and Cover 0/1/2/3/4/6 rates with fantasy points allowed per dropback. Level: team.

- **RESEARCH** (15): `Man/Zone.MAN %`, `Man/Zone.FP/DB`, `Man/Zone.ZONE %`, `Man/Zone.FP/DB#2`, `Middle of Field Look (Closed/Open).1-HI/MOF C %`, `Middle of Field Look (Closed/Open).FP/DB`, `Middle of Field Look (Closed/Open).2-HI/MOF O %`, `Middle of Field Look (Closed/Open).FP/DB#2`, `Coverages.COVER 0 %`, `Coverages.COVER 1 %`, `Coverages.COVER 2 %`, `Coverages.COVER 2 MAN %`, `Coverages.COVER 3 %`, `Coverages.COVER 4 %`, `Coverages.COVER 6 %`

## Efficiency (rushing, receiving, total, expected fantasy points) (`efficiency`)

Per-player rushing and receiving efficiency plus XFP/XTD expectation; season to date. Level: player.

- **DERIVED** (3): `Efficiency.EXP RUN %`, `Efficiency.EXP REC %`, `Efficiency.EXP PLAY %`
- **RESEARCH** (7): `Efficiency.YACO/ATT`, `Efficiency.MTF/ATT`, `Efficiency.YPRR`, `Efficiency.YACO/REC`, `Efficiency.MTF/REC`, `Efficiency.MTF/TOUCH`, `Efficiency.YACO/TOUCH`
- **CURRENT** (9): `Rushing.YACO`, `Rushing.MTF`, `Rushing.EXP`, `Receiving.RTE`, `Receiving.YACO`, `Receiving.MTF`, `Receiving.EXP`, `Total.MTF`, `Total.YACO`
- **REDUNDANT** (26): `Rushing.ATT`, `Rushing.YDS`, `Rushing.TD`, `Receiving.TGT`, `Receiving.REC`, `Receiving.YDS`, `Receiving.TD`, `Receiving.AY`, `Receiving.YAC`, `Total.TOUCH`, `Total.YFS`, `Total.TD`, `Efficiency.YPC`, `Efficiency.YPT`, `Efficiency.YAC/REC`, `Efficiency.YFS/TOUCH`, `Efficiency.RuYDS/G`, `Efficiency.RecYDS/G` ... (+8 more)

## Offensive line vs defensive front matchups (next game) (`line_matchups`)

Team rush/pass grades, pressure and run-block metrics paired with the next opponent defence (teams on bye are absent). Level: team. Forward-looking: `OPP`/matchup columns describe the next game.

- **RESEARCH** (8): `Offense Stats.RUSH GRADE`, `Offense Stats.PASS GRADE`, `Offense Stats.ADJ YBC/ATT`, `Offense Stats.PRESS %`, `Offense Stats.PrROE`, `Defense Stats.ADJ YBC/ATT`, `Defense Stats.PRESS %`, `Defense Stats.PrROE`
- **CURRENT** (2): `Offense Stats.YBCO`, `Defense Stats.YBCO`
- **REDUNDANT** (2): `Offense Stats.TM ATT`, `Defense Stats.ATT`

## Offensive snaps (total, rushing, passing, inside 5/10/20) (`offense_snaps`)

Snap counts and snap share with goal-line and red-zone splits. Level: player.

- **DERIVED** (9): `Inside 5.Snaps`, `Inside 5.TM Snaps`, `Inside 5.Snap %`, `Inside 10.Snaps`, `Inside 10.TM Snaps`, `Inside 10.Snap %`, `Inside 20.Snaps`, `Inside 20.TM Snaps`, `Inside 20.Snap %`
- **REDUNDANT** (11): `Total.Snaps`, `Total.TM Snaps`, `Total.Snap %`, `Rushing.Snaps`, `Rushing.TM Snaps`, `Rushing.Snap %`, `Passing.Snaps`, `Passing.TM Snaps`, `Passing.Snap %`, `FPTS.FP/G`, `FPTS.FP`

## Passing advanced (QB) (`passing_advanced`)

QB accuracy, pressure, time-to-throw, depth and fantasy production. Level: player.

- **DERIVED** (4): `Passing Advanced.Deep Throw %`, `Passing Advanced.1Read %`, `Passing Advanced.CHK %`, `Passing Advanced.RPO %`
- **RESEARCH** (17): `Passing Advanced.CPOE`, `Passing Advanced.YAC %`, `Passing Advanced.ADJ CMP %`, `Passing Advanced.ACC %`, `Passing Advanced.OFF %`, `Passing Advanced.HERO %`, `Passing Advanced.TWT %`, `Passing Advanced.DROP %`, `Passing Advanced.TTT`, `Passing Advanced.TTP`, `Passing Advanced.TTSK`, `Passing Advanced.TTSC`, `Passing Advanced.PRESS %`, `Passing Advanced.PRESS SK %`, `Passing Advanced.PrROE`, `FPTS.FP/DB`, `FPTS.FP/OPP`
- **CURRENT** (9): `Passing.DB`, `Passing Advanced.Deep Throw`, `Passing Advanced.EZATT`, `Passing Advanced.DROP YDS`, `Passing Advanced.QB SK`, `Passing Advanced.QBP`, `Passing Advanced.TA`, `Passing Advanced.BAT`, `Passing Advanced.SPK`
- **REDUNDANT** (23): `Passing.ATT`, `Passing.CMP`, `Passing.CMP %`, `Passing.YDS`, `Passing.YDS/G`, `Passing.YPA`, `Passing.TD`, `Passing.INT`, `Passing.1D`, `Passing.RATE`, `Passing.SACK`, `Passing.SACK %`, `Passing.SK YDS`, `Passing.ANY/A`, `Scrambles.SCRM`, `Scrambles.YDS`, `Scrambles.TD`, `Passing Advanced.aDOT` ... (+5 more)

## Passing basic (QB box score) (`passing_basic`)

QB box score: attempts, completions, yards, TDs, sacks, rushing and scrambles, fantasy points. Level: player.

- **RESEARCH** (2): `FPTS.FP/DB`, `FPTS.FP/OPP`
- **CURRENT** (1): `Passing.DB`
- **REDUNDANT** (23): `Passing.ATT`, `Passing.CMP`, `Passing.CMP %`, `Passing.YDS`, `Passing.YDS/G`, `Passing.YPA`, `Passing.TD`, `Passing.INT`, `Passing.1D`, `Passing.RATE`, `Passing.SACK`, `Passing.SACK %`, `Passing.SK YDS`, `Passing.ANY/A`, `Total Rushing.ATT`, `Total Rushing.YDS`, `Total Rushing.TD`, `Scrambles.SCRM` ... (+5 more)

## Passing by depth (QB) (`passing_depth`)

QB attempts, completions, yards and rate by depth bucket. Level: player.

- **CURRENT** (10): `Overall.HERO`, `Overall.TWT`, `Behind LOS.HERO`, `Behind LOS.TWT`, `0-9 Yards.HERO`, `0-9 Yards.TWT`, `10-19 Yards.HERO`, `10-19 Yards.TWT`, `20+ Yards.HERO`, `20+ Yards.TWT`
- **REDUNDANT** (35): `Overall.ATT`, `Overall.CMP`, `Overall.YDS`, `Overall.TD`, `Overall.INT`, `Overall.RATE`, `Overall.CATCH %`, `Behind LOS.ATT`, `Behind LOS.CMP`, `Behind LOS.YDS`, `Behind LOS.TD`, `Behind LOS.INT`, `Behind LOS.RATE`, `Behind LOS.CATCH %`, `0-9 Yards.ATT`, `0-9 Yards.CMP`, `0-9 Yards.YDS`, `0-9 Yards.TD` ... (+17 more)

## QB vs coverage matchup (next game) (`qb_coverage_matchup`)

QB production against each coverage family and the next opponent defence mix (OPP is the upcoming opponent). Level: player. Forward-looking: `OPP`/matchup columns describe the next game.

- **DERIVED** (1): `Matchup.DB/G`
- **RESEARCH** (23): `Matchup.FP/DB`, `Matchup.EXP FP/DB`, `Matchup.COV GRADE`, `Man.DEF MAN %`, `Man.DEF FP/DB`, `Man.QB MAN %`, `Man.QB FP/DB`, `Cover 2.DEF COVER 2 %`, `Cover 2.DEF FP/DB`, `Cover 2.QB COVER 2 %`, `Cover 2.QB FP/DB`, `Cover 3.DEF COVER 3 %`, `Cover 3.DEF FP/DB`, `Cover 3.QB Cover 3 %`, `Cover 3.QB FP/DB`, `Cover 4.DEF COVER 4 %`, `Cover 4.DEF FP/DB`, `Cover 4.QB Cover 4 %` ... (+5 more)
- **CURRENT** (1): `Matchup.DB`

## Receiving advanced (`receiving_advanced`)

Route share, targets, air yards, first-read, designed targets, alignment route split, expected fantasy points. Level: player.

- **DERIVED** (10): `Receiving.RTE %`, `Receiving.TPRR`, `Advanced.1READ %`, `Advanced.CTGT %`, `Advanced.DESIGN %`, `Advanced.CC %`, `Advanced.WIDE RTE %`, `Advanced.SLOT RTE %`, `Advanced.INLINE RTE %`, `Advanced.BACK RTE %`
- **RESEARCH** (10): `Receiving.CR %`, `Receiving.YPRR`, `Receiving.YACO/REC`, `Advanced.MTF/REC`, `Advanced.1D/RR`, `Advanced.DRP %`, `Advanced.THREAT`, `Advanced.YPTOE`, `FPTS.FP/RR`, `FPTS.XFP/RR`
- **CURRENT** (14): `Receiving.RTE`, `Receiving.YACO`, `Advanced.i20 TGT`, `Advanced.EZTGT`, `Advanced.EZTD`, `Advanced.DP TGT`, `Advanced.1READ`, `Advanced.MTF`, `Advanced.DRP`, `Advanced.CTGT`, `Advanced.DESIGN`, `Advanced.CT`, `Advanced.CC`, `Advanced.HERO`
- **REDUNDANT** (23): `Receiving.aDOT`, `Receiving.AY`, `Receiving.AY Share`, `Receiving.TGT`, `Receiving.TGT/G`, `Receiving.TGT %`, `Receiving.REC`, `Receiving.YDS`, `Receiving.RecYDS/G`, `Receiving.TM YDS %`, `Receiving.YPT`, `Receiving.YPR`, `Receiving.YAC`, `Receiving.YAC/REC`, `Receiving.TD`, `Receiving.TM TD %`, `Advanced.1D`, `Advanced.RATE` ... (+5 more)

## Receiving basic (box score) (`receiving_basic`)

Targets, receptions, yards, market shares, inside-10/20 targets, PPR and non-PPR fantasy points. Level: player.

- **RESEARCH** (1): `Receiving.CR %`
- **CURRENT** (2): `Receiving.i10`, `Receiving.i20 TGT`
- **REDUNDANT** (15): `Receiving.TGT`, `Receiving.TGT %`, `Receiving.REC`, `Receiving.YDS`, `Receiving.TM YDS %`, `Receiving.YPR`, `Receiving.YPT`, `Receiving.RecYDS/G`, `Receiving.TD`, `Receiving.TM TD %`, `Receiving.FUM`, `FPTS.FP/G`, `FPTS.FP`, `FPTS.PPR`, `FPTS.NON-PPR`

## Receiving: man vs zone, single-high vs two-high (`receiving_man_vs_zone`)

Per-route production against man, zone, single-high and two-high shells. Level: player.

- **DERIVED** (5): `Overall.TPRR`, `Man.TPRR`, `Zone.TPRR`, `Single-High.TPRR`, `Two-High.TPRR`
- **RESEARCH** (10): `Overall.YPRR`, `Overall.FP/RR`, `Man.YPRR`, `Man.FP/RR`, `Zone.YPRR`, `Zone.FP/RR`, `Single-High.YPRR`, `Single-High.FP/RR`, `Two-High.YPRR`, `Two-High.FP/RR`
- **CURRENT** (5): `Overall.RTE`, `Man.RTE`, `Zone.RTE`, `Single-High.RTE`, `Two-High.RTE`

## Routes run by alignment (`receiving_routes_run`)

Routes, targets and per-route production split by wide/slot/inline/backfield. Level: player.

- **DERIVED** (18): `Overall.TPRR`, `Overall.RTE %`, `Wide.WIDE RTE %`, `Wide.TM RTE %`, `Wide.TPRR`, `Wide.RTE %`, `Slot.SLOT RTE %`, `Slot.TM RTE %`, `Slot.TPRR`, `Slot.RTE %`, `Inline.INLINE RTE %`, `Inline.TM RTE %`, `Inline.TPRR`, `Inline.RTE %`, `Backfield.BACK RTE %`, `Backfield.TM RTE %`, `Backfield.TPRR`, `Backfield.RTE %`
- **RESEARCH** (5): `Overall.YPRR`, `Wide.YPRR`, `Slot.YPRR`, `Inline.YPRR`, `Backfield.YPRR`
- **CURRENT** (5): `Overall.RTE`, `Wide.RTE`, `Slot.RTE`, `Inline.RTE`, `Backfield.RTE`
- **REDUNDANT** (5): `Overall.TGT`, `Wide.TGT`, `Slot.TGT`, `Inline.TGT`, `Backfield.TGT`

## Separation by alignment (`receiving_separation_by_alignment`)

Separation score and win rate overall and from wide/slot/inline/backfield. Level: player.

- **DERIVED** (5): `Overall.TPRR`, `Wide.TPRR`, `Slot.TPRR`, `Inline.TPRR`, `Backfield.TPRR`
- **RESEARCH** (20): `Overall.SEP SCORE`, `Overall.YPRR`, `Overall.WIN RATE`, `Overall.+1 Rate`, `Overall.+2 Rate`, `Overall.+3 Rate`, `Overall.Neg Rate`, `Overall.ADOR`, `Wide.SEP SCORE`, `Wide.YPRR`, `Wide.WIN RATE`, `Slot.SEP SCORE`, `Slot.YPRR`, `Slot.WIN RATE`, `Inline.SEP SCORE`, `Inline.YPRR`, `Inline.WIN RATE`, `Backfield.SEP SCORE` ... (+2 more)
- **CURRENT** (5): `Overall.RTE`, `Wide.RTE`, `Slot.RTE`, `Inline.RTE`, `Backfield.RTE`
- **REDUNDANT** (5): `Overall.TGT`, `Overall.REC`, `Overall.YDS`, `Overall.TD`, `Overall.AY`

## Separation by route break type (`receiving_separation_by_breaks`)

Separation score and win rate by horizontal/vertical/static/shallow route breaks. Level: player.

- **DERIVED** (11): `Overall.TPRR`, `Horizontally Breaking.RTE %`, `Horizontally Breaking.TPRR`, `Vertically Breaking.RTE %`, `Vertically Breaking.TPRR`, `Static.RTE %`, `Static.TPRR`, `Shallow/Underneath.RTE %`, `Shallow/Underneath.TPRR`, `Backfield.RTE %`, `Backfield.TPRR`
- **RESEARCH** (18): `Overall.SEP SCORE`, `Overall.YPRR`, `Overall.WIN RATE`, `Horizontally Breaking.SEP SCORE`, `Horizontally Breaking.YPRR`, `Horizontally Breaking.WIN RATE`, `Vertically Breaking.SEP SCORE`, `Vertically Breaking.YPRR`, `Vertically Breaking.WIN RATE`, `Static.SEP SCORE`, `Static.YPRR`, `Static.WIN RATE`, `Shallow/Underneath.SEP SCORE`, `Shallow/Underneath.YPRR`, `Shallow/Underneath.WIN RATE`, `Backfield.SEP SCORE`, `Backfield.YPRR`, `Backfield.WIN RATE`
- **CURRENT** (6): `Overall.RTE`, `Horizontally Breaking.RTE`, `Vertically Breaking.RTE`, `Static.RTE`, `Shallow/Underneath.RTE`, `Backfield.RTE`

## Separation by coverage (`receiving_separation_by_coverage`)

Separation score and win rate against man, zone, red zone and Cover 2/3/4/6. Level: player.

- **DERIVED** (4): `Overall.TPRR`, `Man.TPRR`, `Zone.TPRR`, `Red Zone.TPRR`
- **RESEARCH** (20): `Overall.SEP SCORE`, `Overall.YPRR`, `Overall.WIN RATE`, `Man.SEP SCORE`, `Man.YPRR`, `Man.WIN RATE`, `Zone.SEP SCORE`, `Zone.YPRR`, `Zone.WIN RATE`, `Red Zone.SEP SCORE`, `Red Zone.YPRR`, `Red Zone.WIN RATE`, `Cover 2.SEP SCORE`, `Cover 2.WIN RATE`, `Cover 3.SEP SCORE`, `Cover 3.WIN RATE`, `Cover 4.SEP SCORE`, `Cover 4.WIN RATE` ... (+2 more)
- **CURRENT** (8): `Overall.RTE`, `Man.RTE`, `Zone.RTE`, `Red Zone.RTE`, `Cover 2.RTE`, `Cover 3.RTE`, `Cover 4.RTE`, `Cover 6.RTE`

## Separation by route type (`receiving_separation_by_routes`)

Separation, route share and win rate by route tree (slant, out, dig, hitch, comeback, corner, post, go, ...). Level: player.

- **DERIVED** (25): `Overall.TPRR`, `Slant.RTE %`, `Slant.TPRR`, `Out.RTE %`, `Out.TPRR`, `In/Dig.RTE %`, `In/Dig.TPRR`, `Hitch.RTE %`, `Hitch.TPRR`, `Comeback.RTE %`, `Comeback.TPRR`, `Corner.RTE %`, `Corner.TPRR`, `Post.RTE %`, `Post.TPRR`, `Go.RTE %`, `Go.TPRR`, `Crossers.RTE %` ... (+7 more)
- **RESEARCH** (50): `Overall.SEP SCORE`, `Overall.YPRR`, `Overall.WIN RATE`, `Slant.SEP SCORE`, `Slant.YPRR`, `Slant.ADOR`, `Slant.WIN RATE`, `Out.SEP SCORE`, `Out.YPRR`, `Out.ADOR`, `Out.WIN RATE`, `In/Dig.SEP SCORE`, `In/Dig.YPRR`, `In/Dig.ADOR`, `In/Dig.WIN RATE`, `Hitch.SEP SCORE`, `Hitch.YPRR`, `Hitch.ADOR` ... (+32 more)
- **CURRENT** (13): `Overall.RTE`, `Slant.RTE`, `Out.RTE`, `In/Dig.RTE`, `Hitch.RTE`, `Comeback.RTE`, `Corner.RTE`, `Post.RTE`, `Go.RTE`, `Crossers.RTE`, `Screens.RTE`, `Flat.RTE`, `Backfield.RTE`
- **REDUNDANT** (1): `Overall.TGT`

## Team run/pass report by situation (`run_pass_report`)

Team snaps, pass and rush counts and rates by half, field position, score state, distance and down. Level: team.

- **DERIVED** (26): `Overall.PASS %`, `Overall.RUSH %`, `1st Half.PASS %`, `1st Half.RUSH %`, `2nd Half.PASS %`, `2nd Half.RUSH %`, `Inside 10.PASS %`, `Inside 10.RUSH %`, `Inside 20.PASS %`, `Inside 20.RUSH %`, `Leading By 7+.PASS %`, `Leading By 7+.RUSH %`, `Neutral.PASS %`, `Neutral.RUSH %`, `Trailing By 7+.PASS %`, `Trailing By 7+.RUSH %`, `<5 Yds to Go.PASS %`, `<5 Yds to Go.RUSH %` ... (+8 more)
- **CURRENT** (26): `Overall.PASS`, `Overall.RUSH`, `1st Half.PASS`, `1st Half.RUSH`, `2nd Half.PASS`, `2nd Half.RUSH`, `Inside 10.PASS`, `Inside 10.RUSH`, `Inside 20.PASS`, `Inside 20.RUSH`, `Leading By 7+.PASS`, `Leading By 7+.RUSH`, `Neutral.PASS`, `Neutral.RUSH`, `Trailing By 7+.PASS`, `Trailing By 7+.RUSH`, `<5 Yds to Go.PASS`, `<5 Yds to Go.RUSH` ... (+8 more)
- **REDUNDANT** (13): `Overall.SNAPS`, `1st Half.SNAPS`, `2nd Half.SNAPS`, `Inside 10.SNAPS`, `Inside 20.SNAPS`, `Leading By 7+.SNAPS`, `Neutral.SNAPS`, `Trailing By 7+.SNAPS`, `<5 Yds to Go.SNAPS`, `5-9 Yds to Go.SNAPS`, `10+ Yds to Go.SNAPS`, `1st Down.SNAPS`, `3rd Down.SNAPS`

## Rushing advanced (`rushing_advanced`)

Explosive/success/stuff rates, yards before/after contact, zone vs man/gap concept splits, expected fantasy points. Level: player.

- **DERIVED** (4): `Advanced.EXP RUN %`, `Advanced.i5 %`, `Zone Concept.ATT %`, `Man/Gap Concept.ATT %`
- **RESEARCH** (10): `Advanced.EXP YDS %`, `Advanced.TD RATE`, `Advanced.Success %`, `Advanced.STUFF %`, `Advanced.MTF/ATT`, `Advanced.YACO/ATT`, `Advanced.YACO %`, `Advanced.YBCO/ATT`, `Zone Concept.Success %`, `Man/Gap Concept.Success %`
- **CURRENT** (3): `Advanced.EXP YDS`, `Advanced.MTF`, `Advanced.YACO`
- **REDUNDANT** (19): `Rushing.ATT`, `Rushing.YDS`, `Rushing.RuYDS/G`, `Rushing.YPC`, `Rushing.TD`, `Rushing.FUM`, `Rushing.1D`, `Zone Concept.ATT`, `Zone Concept.YDS`, `Zone Concept.TD`, `Zone Concept.YPC`, `Man/Gap Concept.ATT`, `Man/Gap Concept.YDS`, `Man/Gap Concept.TD`, `Man/Gap Concept.YPC`, `FPTS.FP/G`, `FPTS.FP`, `FPTS.XFP` ... (+1 more)

## Rushing basic (box score) (`rushing_basic`)

Rushing and receiving box score with carry-length buckets and inside-5/10/20 carries, weighted opportunity. Level: player.

- **DERIVED** (10): `Rushing.1+ %`, `Rushing.3+ %`, `Rushing.5+ %`, `Rushing.10+ %`, `Rushing.15+ %`, `Rushing.20+ %`, `Rushing.30+ %`, `Rushing.i5 %`, `Rushing.i10 %`, `Rushing.i20 %`
- **RESEARCH** (1): `Receiving.CR %`
- **CURRENT** (5): `Rushing.i5`, `Rushing.i10`, `Rushing.i20`, `Receiving.i10`, `Receiving.i20 TGT`
- **REDUNDANT** (24): `Rushing.ATT`, `Rushing.YDS`, `Rushing.RuYDS/G`, `Rushing.YPC`, `Rushing.TD`, `Rushing.FUM`, `Rushing.SCRM`, `Rushing.YDS#2`, `Rushing.TD#2`, `Receiving.TGT`, `Receiving.TGT %`, `Receiving.REC`, `Receiving.YDS`, `Receiving.TM YDS %`, `Receiving.YPR`, `Receiving.YPT`, `Receiving.RecYDS/G`, `Receiving.TD` ... (+6 more)

## Backfield opportunity share (bell cow) (`rushing_bell_cow`)

Player share of team snaps, rushes, routes, targets and expected fantasy points. Level: player.

- **DERIVED** (2): `Rushing.ATT %`, `Receiving.RTE %`
- **CURRENT** (2): `Receiving.RTE`, `Receiving.DB`
- **REDUNDANT** (14): `Snaps.Snaps`, `Snaps.TM Snaps`, `Snaps.Snap %`, `Rushing.ATT`, `Rushing.TM ATT`, `Receiving.TGT`, `Receiving.TM TGT`, `Receiving.TGT %`, `FPTS.XFP`, `FPTS.TM XFP`, `FPTS.XFP %`, `FPTS.XFP/G`, `FPTS.FP/G`, `FPTS.FP`

## Receiver vs coverage matchup (next game) (`wr_coverage_matchup`)

Receiver production against each coverage family and the next opponent defence mix (OPP is the upcoming opponent). Level: player. Forward-looking: `OPP`/matchup columns describe the next game.

- **DERIVED** (6): `Matchup.RTE/G`, `Man.RTE %`, `Cover 2.RTE %`, `Cover 3.RTE %`, `Cover 4.RTE %`, `Cover 6.RTE %`
- **RESEARCH** (24): `Matchup.FP/RR`, `Matchup.EXP FP/RTE`, `Matchup.COV GRADE`, `Matchup.YPRR`, `Man.DEF MAN %`, `Man.DEF FP/DB`, `Man.FP/RTE`, `Man.YPRR`, `Cover 2.DEF COVER 2 %`, `Cover 2.DEF FP/DB`, `Cover 2.FP/RTE`, `Cover 2.YPRR`, `Cover 3.DEF COVER 3 %`, `Cover 3.DEF FP/DB`, `Cover 3.FP/RTE`, `Cover 3.YPRR`, `Cover 4.DEF COVER 4 %`, `Cover 4.DEF FP/DB` ... (+6 more)
- **CURRENT** (1): `Matchup.RTE`

